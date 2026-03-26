"""analyzer 모듈 속성 기반 테스트 (Property 2, 16, 17, 18, 19, 20)."""

import os
import tempfile
import wave

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analyzer import run_analysis, validate_config
from errors import AudioAnalyzerError
from models import AnalysisConfig


SR = 16000


def _make_wav_file(duration_sec: float, sr: int = SR, seed: int = 42) -> str:
    """임시 WAV 파일을 생성하고 경로를 반환한다."""
    rng = np.random.default_rng(seed)
    n_samples = max(1, int(sr * duration_sec))
    samples = (rng.uniform(-0.5, 0.5, n_samples) * 32767).astype(np.int16)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return tmp.name


# ── Property 2: 짧은 파일 오류 반환 ──────────────────────────────────────────

@settings(max_examples=20)
@given(
    duration=st.floats(min_value=0.01, max_value=0.99, allow_nan=False),
)
def test_property2_short_file_error(duration):
    """Feature: audio-quality-analyzer, Property 2: 짧은 파일 오류 반환
    1초 미만 WAV 파일로 run_analysis() 호출 시 AudioAnalyzerError가 발생해야 한다.
    Validates: Requirements 1.3
    """
    short_path = _make_wav_file(duration, seed=1)
    normal_path = _make_wav_file(2.0, seed=2)

    try:
        # ref가 짧은 경우
        with pytest.raises(AudioAnalyzerError):
            run_analysis(short_path, normal_path, AnalysisConfig())
    finally:
        os.unlink(short_path)
        os.unlink(normal_path)


def test_property2_short_dif_file_error():
    """dif가 1초 미만인 경우에도 오류가 발생해야 한다."""
    normal_path = _make_wav_file(2.0, seed=1)
    short_path = _make_wav_file(0.5, seed=2)

    try:
        with pytest.raises(AudioAnalyzerError):
            run_analysis(normal_path, short_path, AnalysisConfig())
    finally:
        os.unlink(normal_path)
        os.unlink(short_path)


# ── Property 16: 결과 객체 필수 필드 포함 ────────────────────────────────────

def test_property16_result_required_fields():
    """Feature: audio-quality-analyzer, Property 16: 결과 객체 필수 필드 포함
    run_analysis() 반환 AnalysisResult에 필수 필드가 모두 포함되어야 한다.
    Validates: Requirements 11.4, 4.4
    """
    ref_path = _make_wav_file(2.0, seed=10)
    dif_path = _make_wav_file(2.0, seed=20)

    try:
        result = run_analysis(ref_path, dif_path, AnalysisConfig())

        assert result.ref_path == ref_path
        assert result.dif_path == dif_path
        assert result.analysis_timestamp is not None
        assert result.config is not None
        assert result.delay is not None
        assert result.snr_db is not None
        assert result.silence_metrics is not None
        assert result.ref_audio is not None
        assert result.dif_audio is not None
        assert result.dif_aligned is not None
        assert result.pesq_score is not None
        assert result.stoi_score is not None
        assert result.rms_diff_db is not None
        assert result.clipping_ratio is not None
        assert result.ref_noise_floor_db is not None
        assert result.dif_noise_floor_db is not None
        assert isinstance(result.ref_silence_segments, list)
        assert isinstance(result.dif_silence_segments, list)
        assert isinstance(result.false_silence_segments, list)
        assert isinstance(result.silence_leakage_segments, list)
        assert isinstance(result.error_log, list)
    finally:
        os.unlink(ref_path)
        os.unlink(dif_path)


# ── Property 17: 분석 결정론성 ────────────────────────────────────────────────

def test_property17_deterministic_analysis():
    """Feature: audio-quality-analyzer, Property 17: 분석 결정론성
    동일 입력과 동일 AnalysisConfig로 run_analysis()를 두 번 실행한 결과가 동일해야 한다.
    Validates: Requirements 12.5
    """
    ref_path = _make_wav_file(2.0, seed=30)
    dif_path = _make_wav_file(2.0, seed=40)

    try:
        config = AnalysisConfig()
        r1 = run_analysis(ref_path, dif_path, config)
        r2 = run_analysis(ref_path, dif_path, config)

        assert r1.snr_db.value == r2.snr_db.value
        assert r1.rms_diff_db.value == r2.rms_diff_db.value
        assert r1.clipping_ratio.value == r2.clipping_ratio.value
        assert r1.delay.applied_delay_ms == r2.delay.applied_delay_ms
        assert r1.delay.dtw_used == r2.delay.dtw_used
        assert r1.silence_metrics.silence_leakage == r2.silence_metrics.silence_leakage
        assert r1.silence_metrics.false_silence == r2.silence_metrics.false_silence
        np.testing.assert_array_equal(r1.dif_aligned, r2.dif_aligned)
    finally:
        os.unlink(ref_path)
        os.unlink(dif_path)


# ── Property 18: 핵심 단계 실패 시 전체 중단 ─────────────────────────────────

def test_property18_critical_failure_aborts():
    """Feature: audio-quality-analyzer, Property 18: 핵심 단계 실패 시 전체 중단
    존재하지 않는 파일로 run_analysis() 호출 시 AudioAnalyzerError가 발생해야 한다.
    Validates: Requirements 12.6
    """
    with pytest.raises(AudioAnalyzerError):
        run_analysis("nonexistent_ref.wav", "nonexistent_dif.wav", AnalysisConfig())


def test_property18_invalid_format_aborts():
    """잘못된 형식 파일로 run_analysis() 호출 시 AudioAnalyzerError가 발생해야 한다."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(b"not a wav file content")
    tmp.close()
    normal_path = _make_wav_file(2.0, seed=50)

    try:
        with pytest.raises(AudioAnalyzerError):
            run_analysis(tmp.name, normal_path, AnalysisConfig())
    finally:
        os.unlink(tmp.name)
        os.unlink(normal_path)


# ── Property 19: Config 검증 오류 감지 ────────────────────────────────────────

@settings(max_examples=100)
@given(
    hop_ms=st.integers(min_value=21, max_value=100),
)
def test_property19_hop_exceeds_frame(hop_ms):
    """Feature: audio-quality-analyzer, Property 19: Config 검증 오류 감지
    hop_ms > frame_ms인 경우 validate_config()가 오류를 반환해야 한다.
    Validates: AnalysisConfig validation constraints
    """
    config = AnalysisConfig(frame_ms=20, hop_ms=hop_ms)
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("hop_ms" in e for e in errors)


@settings(max_examples=100)
@given(
    vad_agg=st.integers(min_value=4, max_value=100),
)
def test_property19_invalid_vad_aggressiveness(vad_agg):
    """vad_aggressiveness가 0~3 범위를 벗어나면 오류를 반환해야 한다."""
    config = AnalysisConfig(vad_aggressiveness=vad_agg)
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("vad_aggressiveness" in e for e in errors)


def test_property19_invalid_noise_floor_percentile():
    """noise_floor_percentile이 0~100 범위를 벗어나면 오류를 반환해야 한다."""
    config = AnalysisConfig(noise_floor_percentile=101.0)
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("noise_floor_percentile" in e for e in errors)

    config2 = AnalysisConfig(noise_floor_percentile=-1.0)
    errors2 = validate_config(config2)
    assert len(errors2) > 0


def test_property19_invalid_min_silence_ms():
    """min_silence_ms <= 0이면 오류를 반환해야 한다."""
    config = AnalysisConfig(min_silence_ms=0)
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("min_silence_ms" in e for e in errors)


def test_property19_invalid_silence_merge_ms():
    """silence_merge_ms < 0이면 오류를 반환해야 한다."""
    config = AnalysisConfig(silence_merge_ms=-1)
    errors = validate_config(config)
    assert len(errors) > 0
    assert any("silence_merge_ms" in e for e in errors)


# ── Property 20: 유효한 Config 검증 통과 ──────────────────────────────────────

@settings(max_examples=100)
@given(
    frame_ms=st.integers(min_value=5, max_value=100),
    noise_floor=st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    vad_agg=st.integers(min_value=0, max_value=3),
    min_silence=st.integers(min_value=1, max_value=2000),
    merge_ms=st.integers(min_value=0, max_value=1000),
)
def test_property20_valid_config_passes(frame_ms, noise_floor, vad_agg, min_silence, merge_ms):
    """Feature: audio-quality-analyzer, Property 20: 유효한 Config 검증 통과
    모든 필드가 유효 범위 내에 있는 AnalysisConfig에 대해 validate_config()는 빈 목록을 반환해야 한다.
    Validates: AnalysisConfig validation constraints
    """
    # hop_ms는 frame_ms 이하로 설정
    hop_ms = max(1, frame_ms // 2)

    config = AnalysisConfig(
        frame_ms=frame_ms,
        hop_ms=hop_ms,
        noise_floor_percentile=noise_floor,
        vad_aggressiveness=vad_agg,
        min_silence_ms=min_silence,
        silence_merge_ms=merge_ms,
    )
    errors = validate_config(config)
    assert errors == [], f"유효한 Config인데 오류 반환: {errors}"
