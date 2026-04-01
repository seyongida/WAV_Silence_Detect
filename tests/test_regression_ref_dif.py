"""실제 샘플 기반 회귀 테스트.

정답지:
Pair1. B_iOS_ref.wav + B_iOS_dif_1.wav → 묵음(digital_zero) 1회 (약 1초 후)
Pair2. B_iOS_ref.wav + B_iOS_dif_gain.wav → 깨짐(gain_drop) 1회 (약 2.5초 후)
Pair3. B_dating_SPEAKER_01.wav + B_iOS_ixiO_20260327_172033_cut.wav → 묵음 1회 (약 73초 후)
Pair4. B_dating_SPEAKER_01.wav + B_iOS_ixiO_20260327_172033_gain.wav → 깨짐 1회 (약 73초 후)
"""

import os

import numpy as np
import pytest

from analyzer import run_analysis
from models import AnalysisConfig


B_REF = os.path.join("sample_audio", "B_iOS_ref.wav")
B_DIF_1 = os.path.join("sample_audio", "B_iOS_dif_1.wav")
B_DIF_GAIN = os.path.join("sample_audio", "B_iOS_dif_gain.wav")
DATING_REF = os.path.join("sample_audio", "B_dating_SPEAKER_01.wav")
DATING_DIF_CUT = os.path.join("sample_audio", "B_iOS_ixiO_20260327_172033_cut.wav")
DATING_DIF_GAIN = os.path.join("sample_audio", "B_iOS_ixiO_20260327_172033_gain.wav")
REF_PATH = os.path.join("sample_audio", "ref.wav")
DIF_PATH = os.path.join("sample_audio", "dif_2+shift.wav")


class TestPair1:
    """Pair1: B_iOS_ref + B_iOS_dif_1 → 묵음 1회 (약 1초)."""

    @pytest.fixture
    def config(self):
        return AnalysisConfig()

    def test_detects_single_digital_zero(self, config):
        if not (os.path.exists(B_REF) and os.path.exists(B_DIF_1)):
            pytest.skip("B_iOS sample files not present")

        result = run_analysis(B_REF, B_DIF_1, config)

        digital_zeros = [
            s for s in result.anomaly_segments
            if s.anomaly_type == "digital_zero"
        ]
        assert len(digital_zeros) == 1, (
            f"Expected 1 digital_zero, got {len(digital_zeros)}: "
            f"{[(s.start_ms, s.end_ms, s.anomaly_type) for s in result.anomaly_segments]}"
        )

        seg = digital_zeros[0]
        assert 900 <= seg.start_ms <= 1150, f"start_ms={seg.start_ms}"
        assert 1050 <= seg.end_ms <= 1250, f"end_ms={seg.end_ms}"

    def test_no_gain_drop(self, config):
        if not (os.path.exists(B_REF) and os.path.exists(B_DIF_1)):
            pytest.skip("B_iOS sample files not present")

        result = run_analysis(B_REF, B_DIF_1, config)
        gain_drops = [
            s for s in result.anomaly_segments
            if s.anomaly_type == "gain_drop"
        ]
        assert len(gain_drops) == 0


class TestPair2:
    """Pair2: B_iOS_ref + B_iOS_dif_gain → 깨짐 1회 (약 2.5초)."""

    @pytest.fixture
    def config(self):
        return AnalysisConfig()

    def test_detects_single_gain_drop(self, config):
        if not (os.path.exists(B_REF) and os.path.exists(B_DIF_GAIN)):
            pytest.skip("B_iOS sample files not present")

        result = run_analysis(B_REF, B_DIF_GAIN, config)

        gain_drops = [
            s for s in result.anomaly_segments
            if s.anomaly_type == "gain_drop"
        ]
        assert len(gain_drops) == 1, (
            f"Expected 1 gain_drop, got {len(gain_drops)}: "
            f"{[(s.start_ms, s.end_ms, s.anomaly_type) for s in result.anomaly_segments]}"
        )

        seg = gain_drops[0]
        assert 2500 <= seg.start_ms <= 2900, f"start_ms={seg.start_ms}"
        assert 2700 <= seg.end_ms <= 3000, f"end_ms={seg.end_ms}"

    def test_no_digital_zero(self, config):
        if not (os.path.exists(B_REF) and os.path.exists(B_DIF_GAIN)):
            pytest.skip("B_iOS sample files not present")

        result = run_analysis(B_REF, B_DIF_GAIN, config)
        digital_zeros = [
            s for s in result.anomaly_segments
            if s.anomaly_type == "digital_zero"
        ]
        assert len(digital_zeros) == 0


class TestPair3:
    """Pair3: B_dating_SPEAKER_01 + cut → 묵음 1회 (약 73초)."""

    @pytest.fixture
    def config(self):
        return AnalysisConfig()

    def test_detects_single_digital_zero(self, config):
        if not (os.path.exists(DATING_REF) and os.path.exists(DATING_DIF_CUT)):
            pytest.skip("Dating sample files not present")

        result = run_analysis(DATING_REF, DATING_DIF_CUT, config)

        digital_zeros = [
            s for s in result.anomaly_segments
            if s.anomaly_type == "digital_zero"
        ]
        assert len(digital_zeros) == 1, (
            f"Expected 1 digital_zero, got {len(digital_zeros)}: "
            f"{[(s.start_ms, s.end_ms, s.anomaly_type) for s in result.anomaly_segments]}"
        )

        seg = digital_zeros[0]
        assert 72000 <= seg.start_ms <= 73000, f"start_ms={seg.start_ms}"
        assert 72000 <= seg.end_ms <= 73500, f"end_ms={seg.end_ms}"


class TestPair4:
    """Pair4: B_dating_SPEAKER_01 + gain → 깨짐 1회 (약 73초)."""

    @pytest.fixture
    def config(self):
        return AnalysisConfig()

    def test_detects_single_gain_drop(self, config):
        if not (os.path.exists(DATING_REF) and os.path.exists(DATING_DIF_GAIN)):
            pytest.skip("Dating sample files not present")

        result = run_analysis(DATING_REF, DATING_DIF_GAIN, config)

        gain_drops = [
            s for s in result.anomaly_segments
            if s.anomaly_type == "gain_drop"
        ]
        assert len(gain_drops) == 1, (
            f"Expected 1 gain_drop, got {len(gain_drops)}: "
            f"{[(s.start_ms, s.end_ms, s.anomaly_type) for s in result.anomaly_segments]}"
        )

        seg = gain_drops[0]
        assert 72000 <= seg.start_ms <= 73000, f"start_ms={seg.start_ms}"
        assert 72500 <= seg.end_ms <= 73500, f"end_ms={seg.end_ms}"

    def test_no_digital_zero(self, config):
        if not (os.path.exists(DATING_REF) and os.path.exists(DATING_DIF_GAIN)):
            pytest.skip("Dating sample files not present")

        result = run_analysis(DATING_REF, DATING_DIF_GAIN, config)
        digital_zeros = [
            s for s in result.anomaly_segments
            if s.anomaly_type == "digital_zero"
        ]
        assert len(digital_zeros) == 0


class TestLegacySamples:
    """기존 ref.wav/dif_2+shift.wav 호환 테스트."""

    def test_ref_dif_shift_detects_anomalies(self):
        if not (os.path.exists(REF_PATH) and os.path.exists(DIF_PATH)):
            pytest.skip("sample_audio/ref.wav or dif_2+shift.wav not present")

        result = run_analysis(REF_PATH, DIF_PATH, AnalysisConfig())
        assert result.delay.applied_delay_ms != 0.0


A_DATING_REF = os.path.join("sample_audio", "A_dating_SPEAKER_00.wav")
A_ANDROID_DIF = os.path.join("sample_audio", "A_Android_ixiO_20260327_172033.wav")


class TestPair5:
    """Pair5: A_dating_SPEAKER_00 + A_Android → 정상 (이상 0건)."""

    @pytest.fixture
    def config(self):
        return AnalysisConfig()

    def test_no_anomalies(self, config):
        if not (os.path.exists(A_DATING_REF) and os.path.exists(A_ANDROID_DIF)):
            pytest.skip("A_dating/A_Android sample files not present")

        result = run_analysis(A_DATING_REF, A_ANDROID_DIF, config)
        assert len(result.anomaly_segments) == 0, (
            f"Expected 0 anomalies, got {len(result.anomaly_segments)}: "
            f"{[(s.start_ms, s.end_ms, s.anomaly_type) for s in result.anomaly_segments]}"
        )
