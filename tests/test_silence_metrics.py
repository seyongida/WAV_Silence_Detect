"""silence_metrics 모듈 속성 기반 테스트."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from models import AnalysisConfig, Frame, SilenceMetrics, SilenceSegment
from silence_metrics import compute_silence_metrics


SR = 16000


def _make_frames(silence_pattern: list[bool], frame_ms: int = 20, hop_ms: int = 10) -> list[Frame]:
    """묵음 패턴으로 Frame 목록을 생성한다."""
    frames = []
    for i, is_silence in enumerate(silence_pattern):
        start_ms = i * hop_ms
        end_ms = start_ms + frame_ms
        samples = np.zeros(int(SR * frame_ms / 1000), dtype=np.float32)
        frames.append(
            Frame(
                index=i,
                start_ms=float(start_ms),
                end_ms=float(end_ms),
                samples=samples,
                final_silence=is_silence,
            )
        )
    return frames


def _segments_from_pattern(
    silence_pattern: list[bool], frame_ms: int = 20, hop_ms: int = 10
) -> list[SilenceSegment]:
    """묵음 패턴에서 SilenceSegment 목록을 추출한다."""
    frames = _make_frames(silence_pattern, frame_ms=frame_ms, hop_ms=hop_ms)
    segs: list[SilenceSegment] = []
    in_silence = False
    start_ms = 0.0
    for f in frames:
        if f.final_silence and not in_silence:
            in_silence = True
            start_ms = f.start_ms
        elif (not f.final_silence) and in_silence:
            in_silence = False
            segs.append(SilenceSegment(start_ms=start_ms, end_ms=f.start_ms, duration_ms=f.start_ms - start_ms))
    if in_silence and frames:
        segs.append(SilenceSegment(start_ms=start_ms, end_ms=frames[-1].end_ms, duration_ms=frames[-1].end_ms - start_ms))
    return segs


# ── Property 10: 묵음 비율 범위 ──────────────────────────────────────────────

@settings(max_examples=100)
@given(
    ref_pattern=st.lists(st.booleans(), min_size=20, max_size=200),
    dif_pattern=st.lists(st.booleans(), min_size=20, max_size=200),
)
def test_property10_silence_metrics_range(ref_pattern, dif_pattern):
    """Feature: audio-quality-analyzer, Property 10: 묵음 비율 범위
    compute_silence_metrics() 반환 silence_leakage와 false_silence가 [0.0, 1.0] 범위이어야 한다.
    Validates: Requirements 7.4, 7.5
    """
    # 두 패턴 길이를 맞춤
    min_len = min(len(ref_pattern), len(dif_pattern))
    ref_pattern = ref_pattern[:min_len]
    dif_pattern = dif_pattern[:min_len]

    ref_frames = _make_frames(ref_pattern)
    dif_frames = _make_frames(dif_pattern)
    ref_silence = _segments_from_pattern(ref_pattern)
    dif_silence = _segments_from_pattern(dif_pattern)
    config = AnalysisConfig(frame_ms=20, hop_ms=10)

    metrics, false_segs, leakage_segs = compute_silence_metrics(
        ref_frames, dif_frames, ref_silence, dif_silence, SR, config
    )

    assert 0.0 <= metrics.silence_leakage <= 1.0, (
        f"silence_leakage 범위 초과: {metrics.silence_leakage}"
    )
    assert 0.0 <= metrics.false_silence <= 1.0, (
        f"false_silence 범위 초과: {metrics.false_silence}"
    )


def test_property10_all_silence_ref_no_silence_dif():
    """ref 전체 묵음, dif 전체 비묵음 → silence_leakage == 1.0"""
    ref_pattern = [True] * 100
    dif_pattern = [False] * 100

    ref_frames = _make_frames(ref_pattern)
    dif_frames = _make_frames(dif_pattern)
    ref_silence = _segments_from_pattern(ref_pattern)
    dif_silence = _segments_from_pattern(dif_pattern)
    config = AnalysisConfig(frame_ms=20, hop_ms=10, min_silence_ms=0, silence_merge_ms=0)

    metrics, _, leakage_segs = compute_silence_metrics(
        ref_frames, dif_frames, ref_silence, dif_silence, SR, config
    )

    assert metrics.silence_leakage == pytest.approx(1.0, abs=0.01)


def test_property10_identical_patterns_zero_metrics():
    """동일 패턴 → silence_leakage == 0, false_silence == 0"""
    pattern = [False] * 50 + [True] * 30 + [False] * 20

    ref_frames = _make_frames(pattern)
    dif_frames = _make_frames(pattern)
    segs = _segments_from_pattern(pattern)
    config = AnalysisConfig(frame_ms=20, hop_ms=10)

    metrics, false_segs, leakage_segs = compute_silence_metrics(
        ref_frames, dif_frames, segs, segs, SR, config
    )

    assert metrics.silence_leakage == 0.0
    assert metrics.false_silence == 0.0
