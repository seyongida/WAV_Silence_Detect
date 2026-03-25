"""audio_io 모듈 속성 기반 테스트."""

import io
import os
import struct
import tempfile
import wave

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from audio_io import load_wav, normalize_format, resample
from errors import AudioAnalyzerError, ERR_INVALID_FORMAT, ERR_TOO_SHORT
from models import AnalysisConfig, AudioData


# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────────

def _make_wav_file(samples: np.ndarray, sr: int, n_channels: int) -> str:
    """임시 WAV 파일을 생성하고 경로를 반환한다."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sr)
        # float32 → int16 변환
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
        wf.writeframes(pcm.tobytes())
    return tmp.name


def _make_audio_data(samples: np.ndarray, sr: int = 16000) -> AudioData:
    """테스트용 AudioData 객체를 생성한다."""
    n_channels = 1 if samples.ndim == 1 else samples.shape[1]
    return AudioData(
        samples=samples.astype(np.float32),
        sample_rate=sr,
        n_channels=n_channels,
        duration_sec=samples.shape[0] / sr,
        file_path="test",
    )


# ── Property 4: 정규화된 샘플 범위 ────────────────────────────────────────────

@settings(max_examples=100)
@given(
    pcm_values=st.lists(
        st.integers(min_value=-32768, max_value=32767),
        min_size=100,
        max_size=1000,
    )
)
def test_property4_normalized_sample_range(pcm_values):
    """Feature: audio-quality-analyzer, Property 4: 정규화된 샘플 범위
    load_wav() 반환값의 모든 샘플이 [-1.0, 1.0] 범위 내에 있어야 한다.
    Validates: Requirements 3.2
    """
    # 1초 이상 보장을 위해 16kHz 기준 16000 샘플로 패딩
    sr = 16000
    padded = pcm_values + [0] * max(0, sr - len(pcm_values))
    samples = np.array(padded, dtype=np.int16)

    tmp_path = None
    try:
        tmp_path = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path.close()
        with wave.open(tmp_path.name, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(samples.tobytes())

        audio = load_wav(tmp_path.name)
        assert np.all(audio.samples >= -1.0), "샘플 최솟값이 -1.0 미만입니다"
        assert np.all(audio.samples <= 1.0), "샘플 최댓값이 1.0 초과입니다"
    finally:
        if tmp_path and os.path.exists(tmp_path.name):
            os.unlink(tmp_path.name)


# ── Property 5: 잘못된 파일 형식 오류 반환 ────────────────────────────────────

@settings(max_examples=100)
@given(
    data=st.binary(min_size=1, max_size=1024).filter(
        lambda b: not b.startswith(b"RIFF")
    )
)
def test_property5_invalid_format_error(data):
    """Feature: audio-quality-analyzer, Property 5: 잘못된 파일 형식 오류 반환
    유효한 WAV 형식이 아닌 파일에 대해 load_wav()가 AudioAnalyzerError를 발생시켜야 한다.
    Validates: Requirements 3.4
    """
    tmp_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(data)
        tmp.close()
        tmp_path = tmp.name

        with pytest.raises(AudioAnalyzerError) as exc_info:
            load_wav(tmp_path)
        assert exc_info.value.code == ERR_INVALID_FORMAT
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── Property 1: 리샘플링 원본 불변 ────────────────────────────────────────────

VALID_SAMPLE_RATES = [8000, 16000, 22050, 44100, 48000]

@settings(max_examples=100)
@given(
    n_samples=st.integers(min_value=8000, max_value=32000),
    src_sr=st.sampled_from(VALID_SAMPLE_RATES),
    tgt_sr=st.sampled_from(VALID_SAMPLE_RATES),
)
def test_property1_resample_immutability(n_samples, src_sr, tgt_sr):
    """Feature: audio-quality-analyzer, Property 1: 리샘플링 원본 불변
    resample() 호출 후 원본 AudioData.samples 배열이 변경되지 않아야 한다.
    Validates: Requirements 1.2, 3.3
    """
    rng = np.random.default_rng(42)
    original_samples = rng.uniform(-1.0, 1.0, n_samples).astype(np.float32)
    original_copy = original_samples.copy()

    audio = _make_audio_data(original_samples, sr=src_sr)
    _ = resample(audio, tgt_sr)

    np.testing.assert_array_equal(
        audio.samples, original_copy,
        err_msg="resample() 호출 후 원본 samples가 변경되었습니다"
    )


@settings(max_examples=100)
@given(
    n_samples=st.integers(min_value=8000, max_value=32000),
    ref_sr=st.sampled_from(VALID_SAMPLE_RATES),
    dif_sr=st.sampled_from(VALID_SAMPLE_RATES),
)
def test_property1_normalize_format_immutability(n_samples, ref_sr, dif_sr):
    """Feature: audio-quality-analyzer, Property 1: normalize_format() 원본 불변
    normalize_format() 호출 후 원본 dif AudioData.samples 배열이 변경되지 않아야 한다.
    Validates: Requirements 1.2, 3.3
    """
    rng = np.random.default_rng(42)
    ref_samples = rng.uniform(-1.0, 1.0, n_samples).astype(np.float32)
    dif_samples = rng.uniform(-1.0, 1.0, n_samples).astype(np.float32)
    dif_copy = dif_samples.copy()

    ref = _make_audio_data(ref_samples, sr=ref_sr)
    dif = _make_audio_data(dif_samples, sr=dif_sr)
    _ = normalize_format(ref, dif)

    np.testing.assert_array_equal(
        dif.samples, dif_copy,
        err_msg="normalize_format() 호출 후 원본 dif.samples가 변경되었습니다"
    )


# ── Property 3: 포맷 정규화 후 샘플레이트/채널 일치 ───────────────────────────

@settings(max_examples=100)
@given(
    n_samples=st.integers(min_value=8000, max_value=32000),
    ref_sr=st.sampled_from(VALID_SAMPLE_RATES),
    dif_sr=st.sampled_from(VALID_SAMPLE_RATES),
    ref_channels=st.integers(min_value=1, max_value=2),
    dif_channels=st.integers(min_value=1, max_value=2),
)
def test_property3_normalize_format_sr_channels(n_samples, ref_sr, dif_sr, ref_channels, dif_channels):
    """Feature: audio-quality-analyzer, Property 3: 포맷 정규화 후 샘플레이트/채널 일치
    normalize_format() 호출 후 반환된 dif의 SR과 채널이 ref와 동일해야 한다.
    Validates: Requirements 3.1
    """
    rng = np.random.default_rng(42)

    if ref_channels == 1:
        ref_samples = rng.uniform(-1.0, 1.0, n_samples).astype(np.float32)
    else:
        ref_samples = rng.uniform(-1.0, 1.0, (n_samples, ref_channels)).astype(np.float32)

    if dif_channels == 1:
        dif_samples = rng.uniform(-1.0, 1.0, n_samples).astype(np.float32)
    else:
        dif_samples = rng.uniform(-1.0, 1.0, (n_samples, dif_channels)).astype(np.float32)

    ref = AudioData(
        samples=ref_samples,
        sample_rate=ref_sr,
        n_channels=ref_channels,
        duration_sec=n_samples / ref_sr,
        file_path="ref_test",
    )
    dif = AudioData(
        samples=dif_samples,
        sample_rate=dif_sr,
        n_channels=dif_channels,
        duration_sec=n_samples / dif_sr,
        file_path="dif_test",
    )

    result = normalize_format(ref, dif)

    assert result.sample_rate == ref.sample_rate, (
        f"샘플레이트 불일치: {result.sample_rate} != {ref.sample_rate}"
    )
    assert result.n_channels == ref.n_channels, (
        f"채널 수 불일치: {result.n_channels} != {ref.n_channels}"
    )
