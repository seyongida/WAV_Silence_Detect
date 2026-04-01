"""이상 구간 검출 모듈 (주변 대비 ratio 급변 + correlation 기반).

알고리즘 개요:
1. 프레임별 ref/dif RMS, peak, correlation 계산 (20ms 프레임, 10ms 홉)
2. 주변 1초 구간의 ratio 중앙값(context_med) 대비 급격한 하락 검출
3. 묵음(digital_zero): dif_peak ≈ 0 + ref 음성 구간
4. 깨짐 Type A(gain_drop): ratio 급락 + correlation 높음 (파형 유사, gain만 변화)
5. 깨짐 Type B(distortion): ratio 급락 + 100ms 이상 지속 (gap 허용 병합)
6. 묵음 직후 200ms 이내의 distortion은 복구 과정으로 제외
"""

import numpy as np

from models import (
    AnalysisConfig,
    AnomalySegment,
    Frame,
    SilenceMetrics,
    SilenceSegment,
)


def compute_silence_metrics(
    ref_frames: list[Frame],
    dif_frames: list[Frame],
    ref_silence: list[SilenceSegment],
    dif_silence: list[SilenceSegment],
    sr: int,
    config: AnalysisConfig,
    dif_audio: np.ndarray | None = None,
    ref_audio: np.ndarray | None = None,
) -> tuple[SilenceMetrics, list[SilenceSegment], list[SilenceSegment]]:
    """이상 구간을 검출하고 SilenceMetrics를 반환한다."""
    if ref_audio is None or dif_audio is None or len(ref_audio) == 0:
        empty = SilenceMetrics(
            silence_leakage=0.0, false_silence=0.0,
            dif_silence_count=0, dif_total_silence_ms=0.0,
        )
        return empty, [], []

    anomalies = detect_anomalies(ref_audio, dif_audio, sr, config)

    false_silence_segs = [
        SilenceSegment(start_ms=a.start_ms, end_ms=a.end_ms, duration_ms=a.duration_ms)
        for a in anomalies
    ]

    leakage_segs = _compute_leakage(ref_silence, dif_silence, config)

    total_duration_ms = len(ref_audio) / sr * 1000.0
    total_ref_silence_ms = sum(s.duration_ms for s in ref_silence)
    ref_non_silence_ms = max(total_duration_ms - total_ref_silence_ms, 1e-6)

    dif_only_total_ms = sum(s.duration_ms for s in false_silence_segs)
    leakage_total_ms = sum(s.duration_ms for s in leakage_segs)

    silence_leakage = leakage_total_ms / total_ref_silence_ms if total_ref_silence_ms > 0 else 0.0
    false_silence = dif_only_total_ms / ref_non_silence_ms

    metrics = SilenceMetrics(
        silence_leakage=float(np.clip(silence_leakage, 0.0, 1.0)),
        false_silence=float(np.clip(false_silence, 0.0, 1.0)),
        dif_silence_count=len(anomalies),
        dif_total_silence_ms=dif_only_total_ms,
    )
    return metrics, false_silence_segs, leakage_segs


def detect_anomalies(
    ref_audio: np.ndarray,
    dif_audio: np.ndarray,
    sr: int,
    config: AnalysisConfig,
) -> list[AnomalySegment]:
    """주변 대비 ratio 급변 + correlation 기반 이상 구간 검출.

    알고리즘:
    1. 20ms 프레임 / 10ms 홉으로 ref_rms, dif_rms, dif_peak, correlation 계산
    2. 주변 1초 구간(현재 ±200ms 제외)의 ratio 중앙값 계산
    3. 묵음: dif_peak < 0.0005 + ref_rms > 0.03
    4. 깨짐 A: ratio < context_med*0.4 + corr > 0.3 (gain만 변화)
    5. 깨짐 B: ratio < context_med*0.4 + 100ms+ 지속 (gap 허용 병합)
    6. 묵음 직후 200ms 이내 distortion 제외
    """
    hop_ms = config.anomaly_hop_ms
    frame_len = int(sr * config.anomaly_frame_ms / 1000)
    hop_len = int(sr * hop_ms / 1000)
    if frame_len <= 0 or hop_len <= 0:
        return []

    n = min(len(ref_audio), len(dif_audio))
    if n < frame_len:
        return []

    ref = ref_audio[:n].astype(np.float32)
    dif = dif_audio[:n].astype(np.float32)
    n_frames = (n - frame_len) // hop_len + 1
    if n_frames <= 0:
        return []

    ref_rms, dif_rms, dif_peak, frame_corr = _compute_frame_features(
        ref, dif, frame_len, hop_len, n_frames,
    )

    speech = ref_rms > config.ref_silence_rms
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(ref_rms > 0.005, dif_rms / ref_rms, 1.0)

    # 주변 ratio 중앙값 계산
    context_med = _compute_context_median(ratio, speech, hop_ms, n_frames)

    # 묵음 검출
    speech_strong = ref_rms > 0.03
    zero_mask = speech_strong & (dif_peak < 0.0005)
    silence_segs = _find_segments(zero_mask, hop_ms, min_frames=5)

    # 깨짐 Type A: ratio 급락 + correlation 높음
    ratio_drop = ratio < context_med * 0.4
    not_zero = dif_peak >= 0.001
    gain_a_mask = speech_strong & ratio_drop & not_zero & (frame_corr > 0.3)
    gain_a_segs = _find_segments(gain_a_mask, hop_ms, min_frames=5)

    # 깨짐 Type B: ratio 급락 + 120ms+ (gap 허용 병합, Type A 제외)
    # Type A보다 엄격한 ratio 임계값(0.35)과 긴 최소 지속시간으로 오탐 방지
    ratio_drop_strict = ratio < context_med * 0.35
    gain_b_base = speech_strong & ratio_drop_strict & not_zero & ~gain_a_mask
    gain_b_segs = _find_segments_with_gap(gain_b_base, hop_ms, min_frames=12, max_gap=3)

    # 묵음 직후 200ms 이내의 distortion 제외
    silence_ends = [e_ms for _, e_ms, _ in silence_segs]
    gain_b_segs = [
        seg for seg in gain_b_segs
        if not any(abs(seg[0] - se) < 200 for se in silence_ends)
    ]

    # AnomalySegment 조립
    results: list[AnomalySegment] = []

    for s_ms, e_ms, _ in silence_segs:
        idx_s, idx_e = int(s_ms / hop_ms), min(int(e_ms / hop_ms), n_frames)
        results.append(AnomalySegment(
            start_ms=float(s_ms), end_ms=float(e_ms),
            duration_ms=float(e_ms - s_ms),
            anomaly_type="digital_zero",
            mean_gain_db=-100.0,
            mean_correlation=float(np.mean(frame_corr[idx_s:idx_e])) if idx_e > idx_s else 0.0,
        ))

    for s_ms, e_ms, _ in gain_a_segs:
        idx_s, idx_e = int(s_ms / hop_ms), min(int(e_ms / hop_ms), n_frames)
        avg_ratio = float(np.mean(ratio[idx_s:idx_e])) if idx_e > idx_s else 0.0
        gain_db = float(20.0 * np.log10(avg_ratio + 1e-10))
        results.append(AnomalySegment(
            start_ms=float(s_ms), end_ms=float(e_ms),
            duration_ms=float(e_ms - s_ms),
            anomaly_type="gain_drop",
            mean_gain_db=gain_db,
            mean_correlation=float(np.mean(frame_corr[idx_s:idx_e])) if idx_e > idx_s else 0.0,
        ))

    for s_ms, e_ms, _ in gain_b_segs:
        idx_s, idx_e = int(s_ms / hop_ms), min(int(e_ms / hop_ms), n_frames)
        avg_ratio = float(np.mean(ratio[idx_s:idx_e])) if idx_e > idx_s else 0.0
        gain_db = float(20.0 * np.log10(avg_ratio + 1e-10))
        results.append(AnomalySegment(
            start_ms=float(s_ms), end_ms=float(e_ms),
            duration_ms=float(e_ms - s_ms),
            anomaly_type="gain_drop",
            mean_gain_db=gain_db,
            mean_correlation=float(np.mean(frame_corr[idx_s:idx_e])) if idx_e > idx_s else 0.0,
        ))

    results.sort(key=lambda s: s.start_ms)
    return results


def _compute_frame_features(
    ref: np.ndarray, dif: np.ndarray,
    frame_len: int, hop_len: int, n_frames: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """프레임별 RMS, peak, correlation 계산."""
    ref_rms = np.zeros(n_frames)
    dif_rms = np.zeros(n_frames)
    dif_peak = np.zeros(n_frames)
    frame_corr = np.zeros(n_frames)

    for i in range(n_frames):
        s = i * hop_len
        e = s + frame_len
        r = ref[s:e].astype(np.float64)
        d = dif[s:e].astype(np.float64)
        ref_rms[i] = np.sqrt(np.mean(r ** 2))
        dif_rms[i] = np.sqrt(np.mean(d ** 2))
        dif_peak[i] = np.max(np.abs(d))
        if np.std(r) > 1e-8 and np.std(d) > 1e-8:
            frame_corr[i] = np.corrcoef(r, d)[0, 1]
        else:
            frame_corr[i] = 0.0

    return ref_rms, dif_rms, dif_peak, frame_corr


def _compute_context_median(
    ratio: np.ndarray, speech: np.ndarray,
    hop_ms: int, n_frames: int,
) -> np.ndarray:
    """각 프레임의 주변 1초 구간(현재 ±200ms 제외) ratio 중앙값 계산."""
    context_win = int(1000 / hop_ms)
    exclude_half = int(200 / hop_ms)
    context_med = np.ones(n_frames)

    for i in range(n_frames):
        left_s = max(0, i - context_win)
        left_e = max(0, i - exclude_half)
        right_s = min(n_frames, i + exclude_half)
        right_e = min(n_frames, i + context_win)
        indices = list(range(left_s, left_e)) + list(range(right_s, right_e))
        if indices:
            ctx = [ratio[j] for j in indices if speech[j]]
            if len(ctx) > 5:
                context_med[i] = np.median(ctx)

    return context_med


def _find_segments(
    mask: np.ndarray, hop_ms: int, min_frames: int = 3,
) -> list[tuple[int, int, int]]:
    """연속 True 구간을 (start_ms, end_ms, n_frames) 리스트로 반환."""
    segs: list[tuple[int, int, int]] = []
    in_seg = False
    start = 0
    for i in range(len(mask) + 1):
        active = i < len(mask) and mask[i]
        if active and not in_seg:
            in_seg = True
            start = i
        elif not active and in_seg:
            in_seg = False
            length = i - start
            if length >= min_frames:
                segs.append((start * hop_ms, i * hop_ms, length))
    return segs


def _find_segments_with_gap(
    mask: np.ndarray, hop_ms: int,
    min_frames: int = 3, max_gap: int = 2,
) -> list[tuple[int, int, int]]:
    """gap 허용 병합: max_gap 이하의 False 구간을 무시하고 연속으로 취급."""
    segs: list[tuple[int, int, int]] = []
    in_seg = False
    start = 0
    gap_count = 0
    last_active = 0

    for i in range(len(mask)):
        if mask[i]:
            if not in_seg:
                in_seg = True
                start = i
            gap_count = 0
            last_active = i
        else:
            if in_seg:
                gap_count += 1
                if gap_count > max_gap:
                    in_seg = False
                    length = last_active - start + 1
                    if length >= min_frames:
                        segs.append((start * hop_ms, (last_active + 1) * hop_ms, length))

    if in_seg:
        length = last_active - start + 1
        if length >= min_frames:
            segs.append((start * hop_ms, (last_active + 1) * hop_ms, length))

    return segs


def _compute_leakage(
    ref_silence: list[SilenceSegment],
    dif_silence: list[SilenceSegment],
    config: AnalysisConfig,
) -> list[SilenceSegment]:
    """ref 묵음 중 dif에 소리가 있는 구간."""
    return _difference_segments(
        base=ref_silence, subtract=dif_silence,
        merge_ms=float(config.silence_merge_ms),
        min_ms=float(config.min_silence_ms),
    )


def _difference_segments(
    base: list[SilenceSegment],
    subtract: list[SilenceSegment],
    merge_ms: float, min_ms: float,
) -> list[SilenceSegment]:
    """base에서 subtract를 빼고 병합/필터링."""
    if not base:
        return []

    result: list[SilenceSegment] = []
    for seg in base:
        remaining = [(seg.start_ms, seg.end_ms)]
        for sub in subtract:
            new_remaining = []
            for s, e in remaining:
                if sub.end_ms <= s or sub.start_ms >= e:
                    new_remaining.append((s, e))
                else:
                    if sub.start_ms > s:
                        new_remaining.append((s, sub.start_ms))
                    if sub.end_ms < e:
                        new_remaining.append((sub.end_ms, e))
            remaining = new_remaining
        for s, e in remaining:
            result.append(SilenceSegment(start_ms=s, end_ms=e, duration_ms=e - s))

    if not result:
        return []
    result.sort(key=lambda x: x.start_ms)
    merged = [result[0]]
    for seg in result[1:]:
        prev = merged[-1]
        if seg.start_ms - prev.end_ms < merge_ms:
            new_end = max(prev.end_ms, seg.end_ms)
            merged[-1] = SilenceSegment(
                start_ms=prev.start_ms, end_ms=new_end,
                duration_ms=new_end - prev.start_ms,
            )
        else:
            merged.append(seg)

    return [s for s in merged if s.duration_ms >= min_ms]
