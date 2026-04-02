"""silence_metrics 모듈 테스트."""

import numpy as np
import pytest

from models import AnalysisConfig, AnomalySegment, SilenceSegment
from silence_metrics import detect_anomalies, compute_silence_metrics, _difference_segments


@pytest.fixture
def config():
    return AnalysisConfig()


class TestDetectAnomalies:
    """detect_anomalies 함수 테스트."""

    def test_identical_signals_no_anomaly(self, config):
        """ref와 dif가 동일하면 이상 구간 없음."""
        sr = 16000
        t = np.linspace(0, 1.0, sr, dtype=np.float32)
        sig = 0.3 * np.sin(2 * np.pi * 440 * t)
        result = detect_anomalies(sig, sig.copy(), sr, config)
        assert result == []

    def test_digital_zero_detected(self, config):
        """dif 중간에 디지털 제로 삽입 시 검출."""
        sr = 16000
        duration = 1.0
        n = int(sr * duration)
        t = np.linspace(0, duration, n, dtype=np.float32)
        ref = 0.3 * np.sin(2 * np.pi * 440 * t)
        dif = ref.copy()

        # 300~500ms 구간을 디지털 제로로
        zero_start = int(0.3 * sr)
        zero_end = int(0.5 * sr)
        dif[zero_start:zero_end] = 0.0

        result = detect_anomalies(ref, dif, sr, config)
        assert len(result) >= 1

        seg = result[0]
        assert seg.anomaly_type == "digital_zero"
        assert seg.start_ms >= 250
        assert seg.end_ms <= 550
        assert seg.duration_ms >= 50

    def test_gain_drop_detected(self, config):
        """dif 중간에 gain이 크게 떨어지면 검출."""
        sr = 16000
        n = int(sr * 1.0)
        t = np.linspace(0, 1.0, n, dtype=np.float32)
        ref = 0.3 * np.sin(2 * np.pi * 440 * t)
        dif = ref.copy()

        # 400~700ms 구간 gain을 -20dB로 (파형 유지 → corr 높음 → Type A)
        drop_start = int(0.4 * sr)
        drop_end = int(0.7 * sr)
        dif[drop_start:drop_end] *= 0.1

        result = detect_anomalies(ref, dif, sr, config)
        assert len(result) >= 1
        seg = result[0]
        assert seg.anomaly_type == "gain_drop"
        assert seg.start_ms >= 350
        assert seg.end_ms <= 750

    def test_ref_silence_excluded(self, config):
        """ref가 묵음인 구간은 판정에서 제외."""
        sr = 16000
        n = int(sr * 1.0)
        ref = np.zeros(n, dtype=np.float32)
        dif = np.zeros(n, dtype=np.float32)

        result = detect_anomalies(ref, dif, sr, config)
        assert result == []

    def test_empty_input(self, config):
        """빈 입력 처리."""
        result = detect_anomalies(
            np.array([], dtype=np.float32),
            np.array([], dtype=np.float32),
            16000, config,
        )
        assert result == []

    def test_short_anomaly_filtered(self, config):
        """10ms 디지털 제로는 최소 지속시간 미만으로 필터링."""
        sr = 16000
        n = int(sr * 1.0)
        t = np.linspace(0, 1.0, n, dtype=np.float32)
        ref = 0.3 * np.sin(2 * np.pi * 440 * t)
        dif = ref.copy()

        # 10ms만 제로 → 최소 50ms 미만이므로 필터링
        s = int(0.5 * sr)
        e = s + int(0.01 * sr)
        dif[s:e] = 0.0

        result = detect_anomalies(ref, dif, sr, config)
        assert result == []


class TestDifferenceSegments:
    """_difference_segments 함수 테스트."""

    def test_no_overlap(self):
        base = [SilenceSegment(100, 200, 100)]
        subtract = [SilenceSegment(300, 400, 100)]
        result = _difference_segments(base, subtract, merge_ms=50, min_ms=50)
        assert len(result) == 1
        assert result[0].start_ms == 100

    def test_full_overlap(self):
        base = [SilenceSegment(100, 200, 100)]
        subtract = [SilenceSegment(50, 250, 200)]
        result = _difference_segments(base, subtract, merge_ms=50, min_ms=50)
        assert result == []

    def test_partial_overlap(self):
        base = [SilenceSegment(100, 300, 200)]
        subtract = [SilenceSegment(150, 250, 100)]
        result = _difference_segments(base, subtract, merge_ms=10, min_ms=40)
        assert len(result) == 2


class TestComputeSilenceMetrics:
    """compute_silence_metrics 통합 테스트."""

    def test_with_digital_zero(self, config):
        """디지털 제로가 있는 경우 false_silence > 0."""
        sr = 16000
        n = int(sr * 1.0)
        t = np.linspace(0, 1.0, n, dtype=np.float32)
        ref = 0.3 * np.sin(2 * np.pi * 440 * t)
        dif = ref.copy()
        dif[int(0.3*sr):int(0.6*sr)] = 0.0

        from vad import compute_frames, detect_silence
        ref_frames = compute_frames(ref, sr, config)
        dif_frames = compute_frames(dif, sr, config)
        ref_silence = detect_silence(ref_frames, sr, config)
        dif_silence = detect_silence(dif_frames, sr, config)

        metrics, false_segs, leak_segs = compute_silence_metrics(
            ref_frames, dif_frames, ref_silence, dif_silence,
            sr, config, dif_audio=dif, ref_audio=ref,
        )

        assert metrics.dif_silence_count >= 1
        assert metrics.dif_total_silence_ms > 0
        assert metrics.false_silence > 0
        assert len(false_segs) >= 1


class TestPriorDifActivityFilter:
    """자연 묵음→음성 전환 구간 오탐 제외 테스트."""

    def test_transition_zone_excluded(self, config):
        """직전에 ref/dif 모두 묵음이었다가 ref만 먼저 시작하는 구간은 제외."""
        sr = 16000
        n = int(sr * 2.0)
        ref = np.zeros(n, dtype=np.float32)
        dif = np.zeros(n, dtype=np.float32)

        # 0~1초: ref/dif 모두 묵음
        # 1.0초~: ref에 음성 시작, dif는 1.1초부터 시작 (100ms 지연)
        t_speech = np.linspace(0, 0.9, int(sr * 0.9), dtype=np.float32)
        speech = 0.3 * np.sin(2 * np.pi * 440 * t_speech)
        ref_start = int(1.0 * sr)
        ref[ref_start:ref_start + len(speech)] = speech
        dif_start = int(1.1 * sr)
        dif[dif_start:dif_start + len(speech)] = speech[:n - dif_start] if dif_start + len(speech) > n else speech

        result = detect_anomalies(ref, dif, sr, config)
        # 1.0~1.1초 구간이 digital_zero로 검출되면 안 됨
        zero_segs = [a for a in result if a.anomaly_type == "digital_zero"]
        assert len(zero_segs) == 0, f"전환 구간 오탐: {zero_segs}"

    def test_real_silence_still_detected(self, config):
        """직전에 dif 활성 신호가 있었던 진짜 묵음은 정상 검출."""
        sr = 16000
        n = int(sr * 2.0)
        t = np.linspace(0, 2.0, n, dtype=np.float32)
        ref = 0.3 * np.sin(2 * np.pi * 440 * t)
        dif = ref.copy()

        # 1.0~1.2초 구간을 디지털 제로로 (직전에 dif 활성 신호 있음)
        zero_start = int(1.0 * sr)
        zero_end = int(1.2 * sr)
        dif[zero_start:zero_end] = 0.0

        result = detect_anomalies(ref, dif, sr, config)
        zero_segs = [a for a in result if a.anomaly_type == "digital_zero"]
        assert len(zero_segs) >= 1, "진짜 묵음이 검출되어야 함"
        assert zero_segs[0].start_ms >= 950
        assert zero_segs[0].end_ms <= 1250
