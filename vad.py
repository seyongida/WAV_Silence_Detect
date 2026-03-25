"""묵음 판별 모듈 (log-energy, webrtcvad, ZCR 앙상블)."""

import numpy as np
import scipy.signal as signal

from models import AnalysisConfig, Frame, SilenceSegment


def compute_frames(
    audio: np.ndarray,
    sr: int,
    config: AnalysisConfig,
) -> list[Frame]:
    """오디오를 config의 frame_ms/hop_ms 기준으로 분할하여 Frame 목록을 반환한다.

    매개변수:
        audio (np.ndarray): 오디오 신호 (1D 또는 2D)
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): 분석 파라미터 (frame_ms, hop_ms 사용)

    반환값:
        list[Frame]: 각 Frame에 시작/종료 시간(ms) 및 샘플 포함
    """
    mono = _to_mono(audio)
    frame_len = int(sr * config.frame_ms / 1000)
    hop_len = int(sr * config.hop_ms / 1000)

    if frame_len <= 0:
        frame_len = 1
    if hop_len <= 0:
        hop_len = 1

    frames = []
    idx = 0
    frame_index = 0

    while idx + frame_len <= len(mono):
        start_ms = idx / sr * 1000.0
        end_ms = (idx + frame_len) / sr * 1000.0
        frame_samples = mono[idx: idx + frame_len].copy()

        frames.append(Frame(
            index=frame_index,
            start_ms=start_ms,
            end_ms=end_ms,
            samples=frame_samples,
        ))
        idx += hop_len
        frame_index += 1

    return frames


def detect_silence(
    frames: list[Frame],
    sr: int,
    config: AnalysisConfig,
) -> list[SilenceSegment]:
    """Frame 목록을 입력받아 log-energy, webrtcvad, ZCR 앙상블로 묵음 구간 목록을 반환한다.

    각 Frame의 log_energy, zcr, vad_speech, energy_silence, final_silence 필드를 채운다.
    webrtcvad 처리 시 필요에 따라 16kHz로 내부 리샘플링한다.

    매개변수:
        frames (list[Frame]): compute_frames() 결과
        sr (int): 샘플레이트 (Hz)
        config (AnalysisConfig): 분석 파라미터

    반환값:
        list[SilenceSegment]: min_silence_ms 이상, silence_merge_ms 간격 병합 적용된 묵음 구간 목록
    """
    if not frames:
        return []

    # 1. log-energy 및 ZCR 계산
    for frame in frames:
        frame.log_energy = _compute_log_energy(frame.samples)
        frame.zcr = _compute_zcr(frame.samples)

    # 2. Noise Floor 추정 (하위 percentile)
    energies = np.array([f.log_energy for f in frames], dtype=np.float32)
    noise_floor = float(np.percentile(energies, config.noise_floor_percentile))
    threshold = noise_floor + config.energy_margin_db

    # 3. energy_silence 판정
    for frame in frames:
        frame.energy_silence = frame.log_energy < threshold

    # 4. webrtcvad 실행
    vad_results = _run_webrtcvad(frames, sr, config.vad_aggressiveness)
    for frame, vad_speech in zip(frames, vad_results):
        frame.vad_speech = vad_speech

    # 5. 앙상블 최종 판정
    # (energy_silence AND vad_silence) OR (energy_silence AND ZCR <= threshold)
    for frame in frames:
        vad_silence = not frame.vad_speech
        energy_sil = frame.energy_silence
        zcr_low = frame.zcr <= config.zcr_threshold
        frame.final_silence = (energy_sil and vad_silence) or (energy_sil and zcr_low)

    # 6. 연속 묵음 구간 추출
    raw_segments = _extract_silence_segments(frames)

    # 7. min_silence_ms 미만 제거
    filtered = [s for s in raw_segments if s.duration_ms >= config.min_silence_ms]

    # 8. silence_merge_ms 미만 간격 병합
    merged = _merge_segments(filtered, config.silence_merge_ms)

    return merged


def _compute_log_energy(frame: np.ndarray) -> float:
    """프레임의 log-energy를 계산한다.

    매개변수:
        frame (np.ndarray): 프레임 샘플

    반환값:
        float: log-energy (dB)
    """
    energy = float(np.sum(frame.astype(np.float64) ** 2))
    if energy <= 0:
        return -100.0
    return float(10.0 * np.log10(energy + 1e-10))


def _compute_zcr(frame: np.ndarray) -> float:
    """프레임의 Zero Crossing Rate를 계산한다.

    매개변수:
        frame (np.ndarray): 프레임 샘플

    반환값:
        float: ZCR (0~1)
    """
    if len(frame) <= 1:
        return 0.0
    signs = np.sign(frame.astype(np.float32))
    crossings = np.sum(np.abs(np.diff(signs)) > 0)
    return float(crossings / (len(frame) - 1))


def _run_webrtcvad(
    frames: list[Frame],
    sr: int,
    aggressiveness: int,
) -> list[bool]:
    """webrtcvad로 각 Frame의 VAD 결과(True=음성) 목록을 반환한다.

    webrtcvad는 8kHz, 16kHz, 32kHz만 지원하므로, 지원 범위 외 SR은 16kHz로 내부 리샘플링한다.
    반환 목록의 인덱스는 입력 frames와 1:1 대응한다.

    매개변수:
        frames (list[Frame]): Frame 목록
        sr (int): 샘플레이트 (Hz)
        aggressiveness (int): webrtcvad aggressiveness (0~3)

    반환값:
        list[bool]: 각 Frame의 VAD 결과 (True=음성)
    """
    try:
        import webrtcvad
    except ImportError:
        # webrtcvad 미설치 시 모두 음성으로 처리 (에너지 기반만 사용)
        return [True] * len(frames)

    SUPPORTED_SR = {8000, 16000, 32000}
    vad_sr = sr if sr in SUPPORTED_SR else 16000
    need_resample = (sr not in SUPPORTED_SR)

    vad = webrtcvad.Vad(aggressiveness)
    results = []

    for frame in frames:
        samples = frame.samples.copy()

        if need_resample:
            n_out = int(len(samples) * vad_sr / sr)
            if n_out < 1:
                results.append(False)
                continue
            samples = signal.resample(samples, n_out).astype(np.float32)

        # webrtcvad는 10ms, 20ms, 30ms 프레임만 지원
        # 프레임 길이를 지원 크기로 맞춤
        valid_frame_ms = [10, 20, 30]
        frame_ms_actual = len(samples) / vad_sr * 1000.0
        closest_ms = min(valid_frame_ms, key=lambda x: abs(x - frame_ms_actual))
        target_len = int(vad_sr * closest_ms / 1000)

        if len(samples) < target_len:
            samples = np.pad(samples, (0, target_len - len(samples)))
        else:
            samples = samples[:target_len]

        # float32 → int16 PCM
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

        try:
            is_speech = vad.is_speech(pcm, vad_sr)
        except Exception:
            is_speech = True  # 오류 시 음성으로 처리

        results.append(is_speech)

    return results


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _to_mono(audio: np.ndarray) -> np.ndarray:
    """다채널 신호를 모노로 변환한다."""
    if audio.ndim == 1:
        return audio.astype(np.float32)
    return audio.mean(axis=1).astype(np.float32)


def _extract_silence_segments(frames: list[Frame]) -> list[SilenceSegment]:
    """연속된 final_silence=True 프레임을 SilenceSegment로 변환한다."""
    segments = []
    in_silence = False
    seg_start_ms = 0.0

    for frame in frames:
        if frame.final_silence and not in_silence:
            in_silence = True
            seg_start_ms = frame.start_ms
        elif not frame.final_silence and in_silence:
            in_silence = False
            end_ms = frame.start_ms
            duration_ms = end_ms - seg_start_ms
            segments.append(SilenceSegment(
                start_ms=seg_start_ms,
                end_ms=end_ms,
                duration_ms=duration_ms,
            ))

    # 마지막 프레임까지 묵음인 경우
    if in_silence and frames:
        end_ms = frames[-1].end_ms
        duration_ms = end_ms - seg_start_ms
        segments.append(SilenceSegment(
            start_ms=seg_start_ms,
            end_ms=end_ms,
            duration_ms=duration_ms,
        ))

    return segments


def _merge_segments(
    segments: list[SilenceSegment],
    merge_ms: float,
) -> list[SilenceSegment]:
    """인접 묵음 구간 사이 간격이 merge_ms 미만이면 병합한다."""
    if not segments:
        return []

    merged = [segments[0]]
    for seg in segments[1:]:
        prev = merged[-1]
        gap = seg.start_ms - prev.end_ms
        if gap < merge_ms:
            # 병합
            new_end = seg.end_ms
            merged[-1] = SilenceSegment(
                start_ms=prev.start_ms,
                end_ms=new_end,
                duration_ms=new_end - prev.start_ms,
            )
        else:
            merged.append(seg)

    return merged
