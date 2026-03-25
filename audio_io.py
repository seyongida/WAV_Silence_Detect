"""파일 I/O 및 포맷 정규화 모듈."""

import numpy as np
import soundfile as sf
import scipy.signal as signal

from errors import AudioAnalyzerError, ERR_FILE_NOT_FOUND, ERR_INVALID_FORMAT, ERR_TOO_SHORT
from models import AudioData


def load_wav(path: str) -> AudioData:
    """WAV 파일을 로드하고 float32 정규화(-1.0~1.0)된 AudioData를 반환한다.

    매개변수:
        path (str): WAV 파일 경로

    반환값:
        AudioData: 정규화된 샘플, 샘플레이트, 채널 수, 길이(초), 파일 경로를 포함한 객체

    예외:
        AudioAnalyzerError(ERR_FILE_NOT_FOUND): 파일이 존재하지 않는 경우
        AudioAnalyzerError(ERR_INVALID_FORMAT): 유효한 WAV 형식이 아닌 경우
        AudioAnalyzerError(ERR_TOO_SHORT): 파일 길이가 1초 미만인 경우
    """
    import os
    if not os.path.exists(path):
        raise AudioAnalyzerError(ERR_FILE_NOT_FOUND, f"파일을 찾을 수 없습니다: {path}")

    try:
        samples, sr = sf.read(path, dtype="float32", always_2d=False)
    except Exception as e:
        raise AudioAnalyzerError(ERR_INVALID_FORMAT, f"유효하지 않은 WAV 형식입니다: {path} ({e})")

    # 모노 신호는 (n_samples,), 스테레오는 (n_samples, n_channels)
    if samples.ndim == 1:
        n_channels = 1
    else:
        n_channels = samples.shape[1]

    n_samples = samples.shape[0]
    duration_sec = n_samples / sr

    if duration_sec < 1.0:
        raise AudioAnalyzerError(ERR_TOO_SHORT, f"파일 길이가 1초 미만입니다: {duration_sec:.3f}초")

    # float32 범위 클리핑 보장 (-1.0 ~ 1.0)
    samples = np.clip(samples, -1.0, 1.0).astype(np.float32)

    return AudioData(
        samples=samples,
        sample_rate=sr,
        n_channels=n_channels,
        duration_sec=duration_sec,
        file_path=path,
    )


def resample(audio: AudioData, target_sr: int) -> AudioData:
    """지정 샘플레이트로 리샘플링한 새 AudioData를 반환한다. 원본 불변.

    매개변수:
        audio (AudioData): 원본 오디오 데이터
        target_sr (int): 목표 샘플레이트 (Hz)

    반환값:
        AudioData: 리샘플링된 새 AudioData (원본 audio는 변경되지 않음)
    """
    if audio.sample_rate == target_sr:
        # 동일 SR이면 복사본 반환 (원본 불변 보장)
        return AudioData(
            samples=audio.samples.copy(),
            sample_rate=audio.sample_rate,
            n_channels=audio.n_channels,
            duration_sec=audio.duration_sec,
            file_path=audio.file_path,
        )

    orig_samples = audio.samples
    sr_orig = audio.sample_rate

    # 리샘플링 비율 계산
    num_samples = int(round(orig_samples.shape[0] * target_sr / sr_orig))

    if orig_samples.ndim == 1:
        resampled = signal.resample(orig_samples, num_samples).astype(np.float32)
    else:
        # 다채널: 채널별 리샘플링
        channels = []
        for ch in range(orig_samples.shape[1]):
            ch_resampled = signal.resample(orig_samples[:, ch], num_samples).astype(np.float32)
            channels.append(ch_resampled)
        resampled = np.stack(channels, axis=1)

    duration_sec = resampled.shape[0] / target_sr

    return AudioData(
        samples=resampled,
        sample_rate=target_sr,
        n_channels=audio.n_channels,
        duration_sec=duration_sec,
        file_path=audio.file_path,
    )


def normalize_format(ref: AudioData, dif: AudioData) -> AudioData:
    """dif를 ref의 샘플레이트와 채널 수로 변환한 새 AudioData를 반환한다. 원본 불변.

    매개변수:
        ref (AudioData): 기준 오디오 데이터
        dif (AudioData): 비교 오디오 데이터 (변환 대상)

    반환값:
        AudioData: ref 포맷(샘플레이트, 채널 수)으로 변환된 새 AudioData (dif 원본 불변)
    """
    result = dif

    # 샘플레이트 변환
    if result.sample_rate != ref.sample_rate:
        result = resample(result, ref.sample_rate)

    # 채널 수 변환
    if result.n_channels != ref.n_channels:
        samples = result.samples
        if ref.n_channels == 1 and result.n_channels > 1:
            # 스테레오 → 모노: 채널 평균
            samples = samples.mean(axis=1).astype(np.float32)
            n_channels = 1
        elif ref.n_channels > 1 and result.n_channels == 1:
            # 모노 → 스테레오: 채널 복제
            samples = np.stack([samples] * ref.n_channels, axis=1).astype(np.float32)
            n_channels = ref.n_channels
        else:
            n_channels = result.n_channels

        result = AudioData(
            samples=samples,
            sample_rate=result.sample_rate,
            n_channels=n_channels,
            duration_sec=samples.shape[0] / result.sample_rate,
            file_path=result.file_path,
        )

    return result
