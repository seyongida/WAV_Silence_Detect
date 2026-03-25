"""Regression tests for ref.wav/dif.wav silence detection behavior."""

import os
import numpy as np
import pytest

from analyzer import run_analysis
from analyzer import run_analysis as run_analysis_v2
from models import AnalysisConfig, Frame, SilenceSegment
from silence_metrics import compute_silence_metrics
from silence_metrics import compute_silence_metrics as compute_silence_metrics_v2


SR = 16000
REF_PATH = os.path.join("sample_audio", "ref.wav")
DIF_PATH = os.path.join("sample_audio", "dif_2+shift.wav")


def _make_frames(silence_pattern: list[bool], frame_ms: int = 20, hop_ms: int = 10) -> list[Frame]:
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


def _segments_from_pattern(silence_pattern: list[bool], frame_ms: int = 20, hop_ms: int = 10) -> list[SilenceSegment]:
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
            segs.append(
                SilenceSegment(
                    start_ms=start_ms,
                    end_ms=f.start_ms,
                    duration_ms=f.start_ms - start_ms,
                )
            )
    if in_silence and frames:
        segs.append(
            SilenceSegment(
                start_ms=start_ms,
                end_ms=frames[-1].end_ms,
                duration_ms=frames[-1].end_ms - start_ms,
            )
        )
    return segs


def test_regression_identical_patterns_have_zero_error():
    pattern = [False] * 100
    for i in range(30, 40):
        pattern[i] = True

    ref_frames = _make_frames(pattern)
    dif_frames = _make_frames(pattern)
    segs = _segments_from_pattern(pattern)
    config = AnalysisConfig(frame_ms=20, hop_ms=10)

    metrics, false_segs, leakage_segs = compute_silence_metrics(
        ref_frames, dif_frames, segs, segs, SR, config
    )

    assert metrics.false_silence == 0.0
    assert metrics.silence_leakage == 0.0
    assert len(false_segs) == 0
    assert len(leakage_segs) == 0


def test_regression_v2_identical_patterns_are_zero_error():
    pattern = [False] * 100
    for i in range(30, 40):
        pattern[i] = True

    ref_frames = _make_frames(pattern)
    dif_frames = _make_frames(pattern)
    segs = _segments_from_pattern(pattern)
    config = AnalysisConfig(frame_ms=20, hop_ms=10)

    metrics, false_segs, leakage_segs = compute_silence_metrics_v2(
        ref_frames, dif_frames, segs, segs, SR, config
    )

    assert metrics.false_silence == 0.0
    assert metrics.silence_leakage == 0.0
    assert false_segs == []
    assert leakage_segs == []


def test_regression_ref_dif_reports_no_over_split_false_silence():
    if not (os.path.exists(REF_PATH) and os.path.exists(DIF_PATH)):
        pytest.skip("sample_audio/ref.wav or sample_audio/dif_2+shift.wav not present")
    result = run_analysis(REF_PATH, DIF_PATH, AnalysisConfig())
    assert len(result.false_silence_segments) == 2


def test_regression_ref_dif_v2_reports_two_major_false_silence_segments():
    if not (os.path.exists(REF_PATH) and os.path.exists(DIF_PATH)):
        pytest.skip("sample_audio/ref.wav or sample_audio/dif_2+shift.wav not present")
    result = run_analysis_v2(REF_PATH, DIF_PATH, AnalysisConfig())
    assert len(result.false_silence_segments) == 2
    assert result.silence_metrics.dif_silence_count == 2
    assert result.silence_metrics.dif_total_silence_ms == 550.0
    assert result.delay.dtw_used is False
    assert result.snr_db.value is not None
    assert result.snr_db.value > 10.0
