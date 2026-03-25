"""vad 모듈 속성 기반 테스트."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from models import AnalysisConfig, Frame, SilenceSegment
from vad import compute_frames, detect_silence


SR = 16000


def _make_signal(n_samples: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(-1.0, 1.0, n_samples).astype(np.float32)


def _make_config(frame_ms: int = 20, hop_ms: int = 10, min_silence_ms: int = 200,
                 silence_merge_ms: int = 50) -> AnalysisConfig:
    return AnalysisConfig(
        frame_ms=frame_ms,
        hop_ms=hop_ms,
        min_silence_ms=min_silence_ms,
        silence_merge_ms=silence_merge_ms,
    )


# ── Property 7: 프레임 분할 커버리지 ──────────────────────────────────────────

@settings(max_examples=100)
@given(
    n_samples=st.integers(min_value=1600, max_value=48000),
    frame_ms=st.integers(min_value=10, max_value=40),
    hop_ms=st.integers(min_value=5, max_value=20),
)
def test_property7_frame_coverage(n_samples, frame_ms, hop_ms):
    """Feature: audio-quality-analyzer, Property 7: 프레임 분할 커버리지
    compute_frames() 반환 목록이 전체 구간을 커버하고 각 프레임 길이가 frame_ms와 일치해야 한다.
    Validates: Requirements 5.1, 5.2, 5.3
    """
    if hop_ms > frame_ms:
        hop_ms = frame_ms  # hop은 frame보다 클 수 없음

    audio = _make_signal(n_samples)
    config = _make_config(frame_ms=frame_ms, hop_ms=hop_ms)
    frames = compute_frames(audio, SR, config)

    if not frames:
        # 신호가 너무 짧아 프레임이 없는 경우는 허용
        frame_len = int(SR * frame_ms / 1000)
        assert n_samples < frame_len
        return

    expected_frame_len = int(SR * frame_ms / 1000)

    # 모든 프레임 길이가 frame_ms와 일치해야 함
    for f in frames:
        assert len(f.samples) == expected_frame_len, (
            f"프레임 {f.index} 길이 불일치: {len(f.samples)} != {expected_frame_len}"
        )

    # 첫 프레임은 0ms에서 시작
    assert frames[0].start_ms == pytest.approx(0.0, abs=1.0)

    # 마지막 프레임의 end_ms는 전체 신호 길이 이하
    total_ms = n_samples / SR * 1000.0
    assert frames[-1].end_ms <= total_ms + 1.0  # 1ms 허용 오차

    # 프레임 인덱스 연속성
    for i, f in enumerate(frames):
        assert f.index == i


# ── Property 8: 최소 묵음 지속 시간 준수 ──────────────────────────────────────

@settings(max_examples=50)
@given(
    min_silence_ms=st.integers(min_value=50, max_value=500),
    seed=st.integers(min_value=0, max_value=999),
)
def test_property8_min_silence_duration(min_silence_ms, seed):
    """Feature: audio-quality-analyzer, Property 8: 최소 묵음 지속 시간 준수
    detect_silence() 반환 모든 SilenceSegment.duration_ms >= config.min_silence_ms 이어야 한다.
    Validates: Requirements 6.7
    """
    # 묵음(0) + 비묵음 패턴 합성 신호 생성
    rng = np.random.default_rng(seed)
    sr = 16000
    # 2초 신호: 0.5초 묵음, 0.5초 신호, 0.5초 묵음, 0.5초 신호
    silence_block = np.zeros(sr // 2, dtype=np.float32)
    noise_block = rng.uniform(-0.8, 0.8, sr // 2).astype(np.float32)
    audio = np.concatenate([silence_block, noise_block, silence_block, noise_block])

    config = AnalysisConfig(
        frame_ms=20,
        hop_ms=10,
        min_silence_ms=min_silence_ms,
        silence_merge_ms=0,
        noise_floor_percentile=15,
        energy_margin_db=10.0,
        vad_aggressiveness=2,
        zcr_threshold=0.1,
    )

    frames = compute_frames(audio, sr, config)
    segments = detect_silence(frames, sr, config)

    for seg in segments:
        assert seg.duration_ms >= min_silence_ms, (
            f"묵음 구간 지속 시간 미달: {seg.duration_ms:.1f}ms < {min_silence_ms}ms"
        )


# ── Property 9: 묵음 구간 병합 ────────────────────────────────────────────────

@settings(max_examples=50)
@given(
    silence_merge_ms=st.integers(min_value=20, max_value=200),
    seed=st.integers(min_value=0, max_value=999),
)
def test_property9_silence_merge(silence_merge_ms, seed):
    """Feature: audio-quality-analyzer, Property 9: 묵음 구간 병합
    detect_silence() 반환 인접 두 SilenceSegment 간격이 silence_merge_ms 이상이어야 한다.
    Validates: Requirements 6.8
    """
    rng = np.random.default_rng(seed)
    sr = 16000
    # 충분히 긴 묵음 구간들 생성
    silence_long = np.zeros(sr, dtype=np.float32)  # 1초 묵음
    noise_long = rng.uniform(-0.8, 0.8, sr).astype(np.float32)  # 1초 신호
    audio = np.concatenate([silence_long, noise_long, silence_long, noise_long])

    config = AnalysisConfig(
        frame_ms=20,
        hop_ms=10,
        min_silence_ms=100,
        silence_merge_ms=silence_merge_ms,
        noise_floor_percentile=15,
        energy_margin_db=10.0,
        vad_aggressiveness=2,
        zcr_threshold=0.1,
    )

    frames = compute_frames(audio, sr, config)
    segments = detect_silence(frames, sr, config)

    # 인접 두 구간 간격이 silence_merge_ms 이상이어야 함
    for i in range(len(segments) - 1):
        gap = segments[i + 1].start_ms - segments[i].end_ms
        assert gap >= silence_merge_ms, (
            f"묵음 구간 간격 미달: {gap:.1f}ms < {silence_merge_ms}ms "
            f"(구간 {i}: {segments[i].end_ms:.1f}ms ~ 구간 {i+1}: {segments[i+1].start_ms:.1f}ms)"
        )
