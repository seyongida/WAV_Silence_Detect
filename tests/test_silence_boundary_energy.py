"""묵음 경계 마진 확장(방안 B) + 에너지 재검증(방안 C) 테스트."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from models import AnalysisConfig, Frame, SilenceSegment
from silence_metrics import (
    _expand_segments,
    _filter_noise_loss,
    _verify_energy,
    compute_silence_metrics,
)

SR = 16000


def _make_frames(silence_pattern: list[bool], frame_ms: int = 20, hop_ms: int = 10) -> list[Frame]:
    """묵음 패턴으로 Frame 목록을 생성한다."""
    frames = []
    for i, is_silence in enumerate(silence_pattern):
        start_ms = i * hop_ms
        end_ms = start_ms + frame_ms
        samples = np.zeros(int(SR * frame_ms / 1000), dtype=np.float32)
        frames.append(Frame(
            index=i,
            start_ms=float(start_ms),
            end_ms=float(end_ms),
            samples=samples,
            final_silence=is_silence,
        ))
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
            segs.append(SilenceSegment(
                start_ms=start_ms, end_ms=f.start_ms, duration_ms=f.start_ms - start_ms,
            ))
    if in_silence and frames:
        segs.append(SilenceSegment(
            start_ms=start_ms, end_ms=frames[-1].end_ms,
            duration_ms=frames[-1].end_ms - start_ms,
        ))
    return segs


# ── _expand_segments 테스트 ───────────────────────────────────────────────────

class TestExpandSegments:
    def test_single_segment_expands_both_sides(self):
        """단일 구간이 양쪽으로 margin만큼 확장된다."""
        segs = [SilenceSegment(start_ms=200, end_ms=400, duration_ms=200)]
        result = _expand_segments(segs, margin_ms=50, max_ms=1000)
        assert len(result) == 1
        assert result[0].start_ms == 150
        assert result[0].end_ms == 450

    def test_expand_clamps_to_zero_and_max(self):
        """확장 시 0 미만이나 max 초과로 넘어가지 않는다."""
        segs = [SilenceSegment(start_ms=30, end_ms=970, duration_ms=940)]
        result = _expand_segments(segs, margin_ms=50, max_ms=1000)
        assert result[0].start_ms == 0.0
        assert result[0].end_ms == 1000.0

    def test_overlapping_segments_merge_after_expand(self):
        """확장 후 겹치는 구간이 병합된다."""
        segs = [
            SilenceSegment(start_ms=100, end_ms=200, duration_ms=100),
            SilenceSegment(start_ms=250, end_ms=350, duration_ms=100),
        ]
        # margin=60이면 [40,260]과 [190,410] → 겹침 → 병합
        result = _expand_segments(segs, margin_ms=60, max_ms=1000)
        assert len(result) == 1
        assert result[0].start_ms == 40
        assert result[0].end_ms == 410

    def test_zero_margin_returns_copy(self):
        """margin=0이면 원본과 동일한 구간을 반환한다."""
        segs = [SilenceSegment(start_ms=100, end_ms=300, duration_ms=200)]
        result = _expand_segments(segs, margin_ms=0, max_ms=1000)
        assert len(result) == 1
        assert result[0].start_ms == 100
        assert result[0].end_ms == 300

    def test_empty_segments(self):
        """빈 목록 입력 시 빈 목록 반환."""
        assert _expand_segments([], margin_ms=50, max_ms=1000) == []


# ── _verify_energy 테스트 ─────────────────────────────────────────────────────

class TestVerifyEnergy:
    def test_silent_segment_passes(self):
        """무음 구간은 에너지 재검증을 통과한다."""
        audio = np.zeros(SR, dtype=np.float32)  # 1초 무음
        segs = [SilenceSegment(start_ms=0, end_ms=500, duration_ms=500)]
        result = _verify_energy(segs, audio, SR, threshold_db=-40.0)
        assert len(result) == 1

    def test_loud_segment_rejected(self):
        """에너지가 높은 구간은 재검증에서 제거된다."""
        # 0.5 진폭 사인파 → 에너지가 -40dB보다 훨씬 높음
        t = np.linspace(0, 1, SR, dtype=np.float32)
        audio = 0.5 * np.sin(2 * np.pi * 440 * t)
        segs = [SilenceSegment(start_ms=0, end_ms=500, duration_ms=500)]
        result = _verify_energy(segs, audio, SR, threshold_db=-40.0)
        assert len(result) == 0

    def test_mixed_segments_partial_pass(self):
        """무음 구간은 통과, 유음 구간은 제거된다."""
        audio = np.zeros(SR * 2, dtype=np.float32)  # 2초
        # 후반 1초에 사인파 삽입
        t = np.linspace(0, 1, SR, dtype=np.float32)
        audio[SR:] = 0.5 * np.sin(2 * np.pi * 440 * t)

        segs = [
            SilenceSegment(start_ms=0, end_ms=500, duration_ms=500),      # 무음 구간
            SilenceSegment(start_ms=1000, end_ms=1500, duration_ms=500),  # 유음 구간
        ]
        result = _verify_energy(segs, audio, SR, threshold_db=-40.0)
        assert len(result) == 1
        assert result[0].start_ms == 0


# ── 통합 테스트: 경계 오탐 제거 ───────────────────────────────────────────────

class TestBoundaryFalsePositiveRemoval:
    def test_boundary_overlap_dif_only_removed_by_margin(self):
        """ref 묵음 경계에 걸친 dif 묵음이 margin 확장으로 제거된다.

        시나리오: ref 묵음 [0~150ms], dif 묵음 [50~250ms]
        기존 로직: 차집합 → [150~250ms] (100ms) → min_silence_ms 필터로 제거될 수도 있지만
                   min_silence_ms=50이면 남음
        새 로직: margin=100 → ref 확장 [0~250ms] → 차집합 → 없음
        """
        ref_silence = [SilenceSegment(start_ms=0, end_ms=150, duration_ms=150)]
        dif_silence = [SilenceSegment(start_ms=50, end_ms=250, duration_ms=200)]

        # 100프레임짜리 ref/dif frames (1000ms)
        ref_frames = _make_frames([False] * 100)
        dif_frames = _make_frames([False] * 100)

        config = AnalysisConfig(
            min_silence_ms=50,
            silence_merge_ms=30,
            silence_boundary_margin_ms=100,
        )

        metrics, dif_only, _ = compute_silence_metrics(
            ref_frames, dif_frames, ref_silence, dif_silence, SR, config,
        )
        assert metrics.dif_silence_count == 0

    def test_genuine_dif_only_silence_preserved(self):
        """ref 묵음과 전혀 겹치지 않는 dif-only 묵음은 유지된다.

        ref 묵음 [0~200ms], dif 묵음 [500~900ms] → margin=100 확장해도 겹치지 않음
        """
        ref_silence = [SilenceSegment(start_ms=0, end_ms=200, duration_ms=200)]
        dif_silence = [SilenceSegment(start_ms=500, end_ms=900, duration_ms=400)]

        ref_frames = _make_frames([False] * 100)
        dif_frames = _make_frames([False] * 100)

        config = AnalysisConfig(
            min_silence_ms=50,
            silence_merge_ms=30,
            silence_boundary_margin_ms=100,
        )

        metrics, dif_only, _ = compute_silence_metrics(
            ref_frames, dif_frames, ref_silence, dif_silence, SR, config,
        )
        assert metrics.dif_silence_count == 1
        assert dif_only[0].start_ms == 500

    def test_energy_verification_removes_false_dif_only(self):
        """에너지 재검증으로 실제 소리가 있는 dif-only 구간이 제거된다."""
        ref_silence = [SilenceSegment(start_ms=0, end_ms=100, duration_ms=100)]
        dif_silence = [SilenceSegment(start_ms=500, end_ms=900, duration_ms=400)]

        ref_frames = _make_frames([False] * 100)
        dif_frames = _make_frames([False] * 100)

        # dif 오디오: 500~900ms 구간에 큰 사인파 (묵음이 아님)
        duration_s = 1.0
        n_samples = int(SR * duration_s)
        dif_audio = np.zeros(n_samples, dtype=np.float32)
        start_idx = int(0.5 * SR)
        end_idx = int(0.9 * SR)
        t = np.linspace(0, 0.4, end_idx - start_idx, dtype=np.float32)
        dif_audio[start_idx:end_idx] = 0.5 * np.sin(2 * np.pi * 440 * t)

        config = AnalysisConfig(
            min_silence_ms=50,
            silence_merge_ms=30,
            silence_boundary_margin_ms=0,
            dif_only_energy_threshold_db=-40.0,
        )

        metrics, dif_only, _ = compute_silence_metrics(
            ref_frames, dif_frames, ref_silence, dif_silence, SR, config,
            dif_audio=dif_audio,
        )
        # 에너지가 높으므로 제거됨
        assert metrics.dif_silence_count == 0


# ── PBT: 확장 후 구간 속성 ────────────────────────────────────────────────────

@settings(max_examples=100)
@given(
    starts=st.lists(
        st.floats(min_value=0, max_value=9000, allow_nan=False, allow_infinity=False),
        min_size=1, max_size=10,
    ),
    margin=st.floats(min_value=0, max_value=500, allow_nan=False, allow_infinity=False),
)
def test_expand_segments_never_exceed_bounds(starts, margin):
    """확장된 구간은 항상 [0, max_ms] 범위 내에 있어야 한다."""
    max_ms = 10000.0
    segs = []
    for s in starts:
        end = min(s + 200, max_ms)
        if end > s:
            segs.append(SilenceSegment(start_ms=s, end_ms=end, duration_ms=end - s))
    if not segs:
        return

    result = _expand_segments(segs, margin_ms=margin, max_ms=max_ms)
    for seg in result:
        assert seg.start_ms >= 0.0
        assert seg.end_ms <= max_ms
        assert seg.duration_ms >= 0.0


# ── _filter_noise_loss 테스트 ─────────────────────────────────────────────────

class TestFilterNoiseLoss:
    def test_dif_zero_ref_low_noise_removed(self):
        """dif가 디지털 제로이고 ref가 미세 잡음이면 제거된다."""
        n = SR  # 1초
        dif_audio = np.zeros(n, dtype=np.float32)
        # ref: 미세 잡음 (peak=0.001, energy ≈ -60dB)
        ref_audio = np.random.randn(n).astype(np.float32) * 0.001

        segs = [SilenceSegment(start_ms=0, end_ms=500, duration_ms=500)]
        result = _filter_noise_loss(segs, dif_audio, ref_audio, SR, 0.002, -30.0)
        assert len(result) == 0

    def test_dif_zero_ref_loud_preserved(self):
        """dif가 디지털 제로이지만 ref에 실제 음성이 있으면 유지된다."""
        n = SR
        dif_audio = np.zeros(n, dtype=np.float32)
        # ref: 큰 사인파 (energy >> -30dB)
        t = np.linspace(0, 1, n, dtype=np.float32)
        ref_audio = 0.5 * np.sin(2 * np.pi * 440 * t)

        segs = [SilenceSegment(start_ms=0, end_ms=500, duration_ms=500)]
        result = _filter_noise_loss(segs, dif_audio, ref_audio, SR, 0.002, -30.0)
        assert len(result) == 1

    def test_dif_not_zero_preserved(self):
        """dif가 디지털 제로가 아니면 필터링하지 않는다."""
        n = SR
        # dif: 미세 잡음 (peak > 0.002)
        dif_audio = np.random.randn(n).astype(np.float32) * 0.01
        ref_audio = np.random.randn(n).astype(np.float32) * 0.001

        segs = [SilenceSegment(start_ms=0, end_ms=500, duration_ms=500)]
        result = _filter_noise_loss(segs, dif_audio, ref_audio, SR, 0.002, -30.0)
        assert len(result) == 1

    def test_mixed_segments(self):
        """여러 구간 중 잡음 소실 구간만 제거된다."""
        n = SR * 2  # 2초
        dif_audio = np.zeros(n, dtype=np.float32)
        ref_audio = np.zeros(n, dtype=np.float32)

        # 전반 1초: ref 미세 잡음 → 제거 대상
        ref_audio[:SR] = np.random.randn(SR).astype(np.float32) * 0.001
        # 후반 1초: ref 큰 소리 → 유지
        t = np.linspace(0, 1, SR, dtype=np.float32)
        ref_audio[SR:] = 0.5 * np.sin(2 * np.pi * 440 * t)

        segs = [
            SilenceSegment(start_ms=0, end_ms=500, duration_ms=500),
            SilenceSegment(start_ms=1000, end_ms=1500, duration_ms=500),
        ]
        result = _filter_noise_loss(segs, dif_audio, ref_audio, SR, 0.002, -30.0)
        assert len(result) == 1
        assert result[0].start_ms == 1000

    def test_empty_segments(self):
        """빈 목록 입력 시 빈 목록 반환."""
        dif_audio = np.zeros(SR, dtype=np.float32)
        ref_audio = np.zeros(SR, dtype=np.float32)
        result = _filter_noise_loss([], dif_audio, ref_audio, SR, 0.002, -30.0)
        assert result == []


class TestNoiseLossIntegration:
    def test_compute_silence_metrics_with_noise_loss_filter(self):
        """compute_silence_metrics에서 잡음 소실 필터가 적용된다."""
        n = SR * 2  # 2초
        # ref: 전체 미세 잡음
        ref_audio = np.random.randn(n).astype(np.float32) * 0.001
        # dif: 500~900ms 구간만 디지털 제로, 나머지는 ref와 유사한 잡음
        dif_audio = np.random.randn(n).astype(np.float32) * 0.001
        si = int(0.5 * SR)
        ei = int(0.9 * SR)
        dif_audio[si:ei] = 0.0

        ref_frames = _make_frames([False] * 200)
        dif_frames = _make_frames([False] * 200)

        # dif 묵음: 500~900ms
        dif_silence = [SilenceSegment(start_ms=500, end_ms=900, duration_ms=400)]
        ref_silence = []  # ref에는 묵음 없음

        config = AnalysisConfig(
            min_silence_ms=100,
            silence_merge_ms=30,
            silence_boundary_margin_ms=0,
            noise_loss_peak_threshold=0.002,
            noise_loss_ref_energy_db=-30.0,
        )

        metrics, dif_only, _ = compute_silence_metrics(
            ref_frames, dif_frames, ref_silence, dif_silence, SR, config,
            dif_audio=dif_audio, ref_audio=ref_audio,
        )
        # ref가 미세 잡음이므로 잡음 소실로 간주 → 제거
        assert metrics.dif_silence_count == 0
