"""Silence metrics computed by segment-set operations."""

import numpy as np

from models import AnalysisConfig, Frame, SilenceMetrics, SilenceSegment


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
    del dif_frames

    if not ref_frames:
        metrics = SilenceMetrics(
            silence_leakage=0.0,
            false_silence=0.0,
            dif_silence_count=0,
            dif_total_silence_ms=0.0,
        )
        return metrics, [], []

    total_ref_duration_ms = float(ref_frames[-1].end_ms)
    total_ref_silence_ms = float(sum(s.duration_ms for s in ref_silence))
    ref_non_silence_ms = max(total_ref_duration_ms - total_ref_silence_ms, 1e-6)

    # 방안 B: ref 묵음 경계를 margin만큼 확장하여 전환부 오탐 흡수
    margin_ms = float(getattr(config, "silence_boundary_margin_ms", 100))
    expanded_ref_silence = _expand_segments(ref_silence, margin_ms, total_ref_duration_ms)

    # dif-only silence: 확장된 ref 묵음을 빼서 경계 오탐 제거
    dif_only_silence = _difference_segments(
        base=dif_silence,
        subtract=expanded_ref_silence,
        merge_ms=float(config.silence_merge_ms),
        min_ms=float(config.min_silence_ms),
    )

    # 방안 C: dif-only 구간의 에너지를 절대 임계값으로 재검증
    if dif_audio is not None and len(dif_only_silence) > 0:
        energy_thr = float(getattr(config, "dif_only_energy_threshold_db", -40.0))
        dif_only_silence = _verify_energy(dif_only_silence, dif_audio, sr, energy_thr)

    # 잡음 소실 필터: dif가 디지털 제로이고 ref가 미세 잡음인 구간 제외
    if dif_audio is not None and ref_audio is not None and len(dif_only_silence) > 0:
        peak_thr = float(getattr(config, "noise_loss_peak_threshold", 0.002))
        ref_energy_thr = float(getattr(config, "noise_loss_ref_energy_db", -30.0))
        dif_only_silence = _filter_noise_loss(
            dif_only_silence, dif_audio, ref_audio, sr, peak_thr, ref_energy_thr,
        )

    # 디지털 제로 검출: dif가 제로이고 ref에 유의미한 소리가 있는 구간을 별도 검출하여 합산
    if dif_audio is not None and ref_audio is not None:
        dz_peak = float(getattr(config, "digital_zero_peak_threshold", 0.002))
        dz_ref_db = float(getattr(config, "digital_zero_ref_energy_db", -30.0))
        digital_zero_segs = _detect_digital_zero_segments(
            dif_audio, ref_audio, sr, config, dz_peak, dz_ref_db,
        )
        # 디지털 제로 검출 결과에도 잡음 소실 필터 적용
        if digital_zero_segs:
            peak_thr = float(getattr(config, "noise_loss_peak_threshold", 0.002))
            ref_energy_thr = float(getattr(config, "noise_loss_ref_energy_db", -30.0))
            digital_zero_segs = _filter_noise_loss(
                digital_zero_segs, dif_audio, ref_audio, sr, peak_thr, ref_energy_thr,
            )
        if digital_zero_segs:
            # 기존 dif-only와 합산 후 병합
            combined = dif_only_silence + digital_zero_segs
            dif_only_silence = _merge_then_filter(
                combined,
                merge_ms=float(config.silence_merge_ms),
                min_ms=float(config.min_silence_ms),
            )

    # leakage: ref 묵음 중 dif에 소리가 있는 구간 (원본 ref_silence 사용)
    leakage_segs = _difference_segments(
        base=ref_silence,
        subtract=dif_silence,
        merge_ms=float(config.silence_merge_ms),
        min_ms=float(config.min_silence_ms),
    )

    dif_only_total_ms = float(sum(s.duration_ms for s in dif_only_silence))
    leakage_total_ms = float(sum(s.duration_ms for s in leakage_segs))

    silence_leakage = leakage_total_ms / total_ref_silence_ms if total_ref_silence_ms > 0 else 0.0
    false_silence = dif_only_total_ms / ref_non_silence_ms

    metrics = SilenceMetrics(
        silence_leakage=float(np.clip(silence_leakage, 0.0, 1.0)),
        false_silence=float(np.clip(false_silence, 0.0, 1.0)),
        dif_silence_count=len(dif_only_silence),
        dif_total_silence_ms=dif_only_total_ms,
    )
    return metrics, dif_only_silence, leakage_segs


def _expand_segments(
    segments: list[SilenceSegment],
    margin_ms: float,
    max_ms: float,
) -> list[SilenceSegment]:
    """묵음 구간 양쪽 경계를 margin_ms만큼 확장한 뒤 겹치는 구간을 병합한다."""
    if not segments or margin_ms <= 0:
        return list(segments)

    expanded: list[SilenceSegment] = []
    for s in segments:
        new_start = max(0.0, s.start_ms - margin_ms)
        new_end = min(max_ms, s.end_ms + margin_ms)
        expanded.append(SilenceSegment(
            start_ms=new_start,
            end_ms=new_end,
            duration_ms=new_end - new_start,
        ))

    # 확장 후 겹치는 구간 병합
    expanded.sort(key=lambda s: s.start_ms)
    merged: list[SilenceSegment] = [expanded[0]]
    for seg in expanded[1:]:
        prev = merged[-1]
        if seg.start_ms <= prev.end_ms:
            new_end = max(prev.end_ms, seg.end_ms)
            merged[-1] = SilenceSegment(
                start_ms=prev.start_ms,
                end_ms=new_end,
                duration_ms=new_end - prev.start_ms,
            )
        else:
            merged.append(seg)

    return merged


def _verify_energy(
    segments: list[SilenceSegment],
    audio: np.ndarray,
    sr: int,
    threshold_db: float,
) -> list[SilenceSegment]:
    """dif-only 구간의 실제 에너지가 절대 임계값 이하인지 재검증한다.

    임계값을 초과하는 구간(실제로 소리가 있는 구간)은 제거한다.
    """
    mono = audio if audio.ndim == 1 else audio.mean(axis=1).astype(np.float32)
    verified: list[SilenceSegment] = []

    for seg in segments:
        start_idx = int(seg.start_ms / 1000.0 * sr)
        end_idx = int(seg.end_ms / 1000.0 * sr)
        start_idx = max(0, min(start_idx, len(mono)))
        end_idx = max(start_idx, min(end_idx, len(mono)))

        if end_idx <= start_idx:
            continue

        chunk = mono[start_idx:end_idx].astype(np.float64)
        energy = float(np.sum(chunk ** 2) / len(chunk))
        if energy <= 0:
            log_energy = -100.0
        else:
            log_energy = float(10.0 * np.log10(energy + 1e-10))

        # 에너지가 임계값 이하인 경우만 진짜 묵음으로 인정
        if log_energy <= threshold_db:
            verified.append(seg)

    return verified


def _filter_noise_loss(
    segments: list[SilenceSegment],
    dif_audio: np.ndarray,
    ref_audio: np.ndarray,
    sr: int,
    dif_peak_threshold: float,
    ref_energy_threshold_db: float,
) -> list[SilenceSegment]:
    """dif가 디지털 제로이고 ref가 미세 잡음인 구간을 제외한다.

    전송 과정에서 미세 배경 잡음이 소실되어 dif에 디지털 제로가 생긴 경우,
    이를 "새로 삽입된 묵음"이 아닌 "잡음 소실"로 간주하여 dif-only에서 제거한다.
    """
    dif_mono = dif_audio if dif_audio.ndim == 1 else dif_audio.mean(axis=1).astype(np.float32)
    ref_mono = ref_audio if ref_audio.ndim == 1 else ref_audio.mean(axis=1).astype(np.float32)
    result: list[SilenceSegment] = []

    for seg in segments:
        si = int(seg.start_ms / 1000.0 * sr)
        ei = int(seg.end_ms / 1000.0 * sr)
        si = max(0, min(si, len(dif_mono)))
        ei = max(si, min(ei, len(dif_mono)))

        if ei <= si:
            continue

        dif_chunk = dif_mono[si:ei]
        dif_peak = float(np.max(np.abs(dif_chunk)))

        # dif가 디지털 제로에 가까운지 확인
        if dif_peak < dif_peak_threshold:
            # ref 해당 구간의 에너지 확인
            ref_si = max(0, min(si, len(ref_mono)))
            ref_ei = max(ref_si, min(ei, len(ref_mono)))
            if ref_ei > ref_si:
                ref_chunk = ref_mono[ref_si:ref_ei].astype(np.float64)
                ref_energy = float(np.sum(ref_chunk ** 2) / len(ref_chunk))
                ref_log_e = 10.0 * np.log10(ref_energy + 1e-10) if ref_energy > 0 else -100.0

                # ref도 미세 잡음 수준이면 잡음 소실로 간주 → 제외
                if ref_log_e <= ref_energy_threshold_db:
                    continue

        result.append(seg)

    return result


def _detect_digital_zero_segments(
    dif_audio: np.ndarray,
    ref_audio: np.ndarray,
    sr: int,
    config: AnalysisConfig,
    dif_peak_threshold: float,
    ref_energy_threshold_db: float,
) -> list[SilenceSegment]:
    """dif에서 인위적으로 삽입된 묵음을 직접 검출한다.

    두 가지 조건 중 하나를 만족하면 인위적 묵음으로 판정:
    1. dif가 디지털 제로(peak < threshold)이고 ref에 유의미한 소리가 있는 경우
    2. dif의 에너지가 ref보다 energy_drop_db 이상 낮은 경우 (에너지 드롭)
    """
    dif_mono = dif_audio if dif_audio.ndim == 1 else dif_audio.mean(axis=1).astype(np.float32)
    ref_mono = ref_audio if ref_audio.ndim == 1 else ref_audio.mean(axis=1).astype(np.float32)

    frame_len = int(sr * config.frame_ms / 1000)
    hop_len = int(sr * config.hop_ms / 1000)
    if frame_len <= 0 or hop_len <= 0:
        return []

    min_len = min(len(dif_mono), len(ref_mono))
    energy_drop_db = float(getattr(config, "energy_drop_db", 20.0))

    flags: list[tuple[float, float, bool]] = []
    idx = 0
    while idx + frame_len <= min_len:
        start_ms = idx / sr * 1000.0
        end_ms = (idx + frame_len) / sr * 1000.0

        dif_chunk = dif_mono[idx:idx + frame_len]
        ref_chunk = ref_mono[idx:idx + frame_len].astype(np.float64)

        dif_peak = float(np.max(np.abs(dif_chunk)))
        dif_e = float(np.sum(dif_chunk.astype(np.float64) ** 2) / frame_len)
        ref_e = float(np.sum(ref_chunk ** 2) / frame_len)

        dif_le = 10.0 * np.log10(dif_e + 1e-10) if dif_e > 0 else -100.0
        ref_le = 10.0 * np.log10(ref_e + 1e-10) if ref_e > 0 else -100.0

        # 조건 1: dif 디지털 제로 + ref 유의미한 소리
        cond1 = dif_peak < dif_peak_threshold and ref_le > ref_energy_threshold_db
        # 조건 2: 에너지 드롭 (ref - dif > threshold, 단 dif가 충분히 낮을 때만)
        cond2 = (ref_le - dif_le) > energy_drop_db and dif_le < -70.0

        flags.append((start_ms, end_ms, cond1 or cond2))
        idx += hop_len

    # 연속된 True 구간을 SilenceSegment로 변환
    segments: list[SilenceSegment] = []
    in_seg = False
    seg_start = 0.0

    for start_ms, end_ms, is_drop in flags:
        if is_drop and not in_seg:
            in_seg = True
            seg_start = start_ms
        elif not is_drop and in_seg:
            in_seg = False
            segments.append(SilenceSegment(start_ms=seg_start, end_ms=start_ms, duration_ms=start_ms - seg_start))

    if in_seg and flags:
        last_end = flags[-1][1]
        segments.append(SilenceSegment(start_ms=seg_start, end_ms=last_end, duration_ms=last_end - seg_start))

    return _merge_then_filter(segments, merge_ms=float(config.silence_merge_ms), min_ms=float(config.min_silence_ms))


def _merge_then_filter(
    segments: list[SilenceSegment],
    merge_ms: float,
    min_ms: float,
) -> list[SilenceSegment]:
    if not segments:
        return []

    segs = sorted(segments, key=lambda s: s.start_ms)
    merged: list[SilenceSegment] = [segs[0]]
    for seg in segs[1:]:
        prev = merged[-1]
        gap = seg.start_ms - prev.end_ms
        if gap < merge_ms:
            new_end = max(prev.end_ms, seg.end_ms)
            merged[-1] = SilenceSegment(
                start_ms=prev.start_ms,
                end_ms=new_end,
                duration_ms=new_end - prev.start_ms,
            )
        else:
            merged.append(seg)

    return [s for s in merged if s.duration_ms >= min_ms]


def _difference_segments(
    base: list[SilenceSegment],
    subtract: list[SilenceSegment],
    merge_ms: float,
    min_ms: float,
) -> list[SilenceSegment]:
    if not base:
        return []

    pieces: list[SilenceSegment] = []
    for b in base:
        intervals = [(b.start_ms, b.end_ms)]
        for s in subtract:
            next_intervals: list[tuple[float, float]] = []
            for st, en in intervals:
                if s.end_ms <= st or s.start_ms >= en:
                    next_intervals.append((st, en))
                    continue
                if s.start_ms > st:
                    next_intervals.append((st, s.start_ms))
                if s.end_ms < en:
                    next_intervals.append((s.end_ms, en))
            intervals = next_intervals
            if not intervals:
                break
        for st, en in intervals:
            if en > st:
                pieces.append(SilenceSegment(start_ms=st, end_ms=en, duration_ms=en - st))

    return _merge_then_filter(pieces, merge_ms=merge_ms, min_ms=min_ms)
