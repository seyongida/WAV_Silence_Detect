"""오디오 분석기 데이터 모델 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class AnalysisConfig:
    """UI에서 사용자가 설정하는 분석 파라미터 집합."""

    frame_ms: int = 20                  # 프레임 길이 (ms)
    hop_ms: int = 10                    # 홉 길이 (ms)
    noise_floor_percentile: float = 15  # Noise_Floor 백분위수 (%)
    energy_margin_db: float = 10.0      # Energy_Margin (dB)
    vad_aggressiveness: int = 2         # webrtcvad aggressiveness (0~3)
    zcr_threshold: float = 0.1          # ZCR 임계값
    min_silence_ms: int = 200           # 최소 묵음 지속 시간 (ms)
    silence_merge_ms: int = 50          # 묵음 병합 간격 (ms)
    # 프레임별 이상 검출 파라미터
    anomaly_frame_ms: int = 20              # 이상 검출 프레임 길이 (ms)
    anomaly_hop_ms: int = 10                # 이상 검출 홉 길이 (ms)
    ref_silence_rms: float = 0.005          # ref 묵음 판정 RMS 임계값
    speech_strong_rms: float = 0.03         # 확실한 음성 구간 판정 RMS 임계값
    zero_peak_threshold: float = 0.0005     # dif 디지털 제로 판정 peak 임계값
    gain_drop_ratio: float = 0.4            # 깨짐 Type A ratio 임계값 (context_med 대비)
    gain_drop_ratio_strict: float = 0.35    # 깨짐 Type B ratio 임계값 (더 엄격)
    gain_drop_min_corr: float = 0.3         # 깨짐 Type A 최소 correlation
    prior_activity_threshold: float = 0.01  # 직전 dif 활성 판정 peak 임계값
    min_anomaly_ms: int = 50                # 묵음/깨짐 Type A 최소 지속 시간 (ms)
    min_anomaly_b_ms: int = 120             # 깨짐 Type B 최소 지속 시간 (ms)
    anomaly_gap_frames: int = 3             # 깨짐 Type B gap 허용 프레임 수


@dataclass
class AnalysisMessage:
    """분석 중 발생한 로그 메시지."""

    level: str      # "info" | "warn" | "error"
    message: str
    timestamp: str  # ISO 8601


@dataclass
class AudioData:
    """로드된 오디오 신호와 메타데이터."""

    samples: np.ndarray     # float32, shape: (n_samples,) 또는 (n_samples, n_channels)
    sample_rate: int
    n_channels: int
    duration_sec: float
    file_path: str


@dataclass
class Frame:
    """분석 단위 오디오 구간."""

    index: int
    start_ms: float
    end_ms: float
    samples: np.ndarray
    log_energy: float | None = None
    zcr: float | None = None
    vad_speech: bool | None = None
    energy_silence: bool | None = None
    final_silence: bool | None = None


@dataclass
class SilenceSegment:
    """묵음 구간 정보."""

    start_ms: float
    end_ms: float
    duration_ms: float


@dataclass
class AnomalySegment:
    """이상 구간 정보 (프레임별 correlation 기반 검출)."""

    start_ms: float
    end_ms: float
    duration_ms: float
    anomaly_type: str       # "digital_zero" | "gain_drop" | "distortion"
    mean_gain_db: float     # 구간 평균 gain (dB), 정상=0 근처
    mean_correlation: float # 구간 평균 Pearson correlation


@dataclass
class DelayResult:
    """지연 보정 계산 결과."""

    coarse_delay_ms: float
    refined_delay_ms: float
    applied_delay_ms: float
    dtw_used: bool


@dataclass
class SilenceMetrics:
    """묵음 관련 지표."""

    silence_leakage: float      # ref 묵음 중 dif에 소리가 있는 비율 (0~1)
    false_silence: float        # ref Non-Silence 중 dif가 묵음인 비율 (0~1)
    dif_silence_count: int      # dif 이상 구간 총 개수
    dif_total_silence_ms: float # dif 이상 구간 총 시간 (ms)


@dataclass
class SpectrogramData:
    """스펙트로그램 데이터."""

    magnitude_db: np.ndarray
    frequencies: np.ndarray
    times: np.ndarray


@dataclass
class SpectrumData:
    """스펙트럼 분석 결과."""

    ref_centroid: np.ndarray
    dif_centroid: np.ndarray
    ref_rolloff: np.ndarray
    dif_rolloff: np.ndarray
    ref_pitch: np.ndarray
    dif_pitch: np.ndarray
    mean_pitch_diff_hz: float
    ref_zcr: np.ndarray
    dif_zcr: np.ndarray
    ref_spectrogram: SpectrogramData
    dif_spectrogram: SpectrogramData


@dataclass
class MetricStatus:
    """지표 계산 상태."""

    value: Optional[float]
    status: str                 # "success" | "N/A" | "failed"
    reason: Optional[str] = None


@dataclass
class AnalysisResult:
    """전체 분석 결과."""

    ref_path: str
    dif_path: str
    analysis_timestamp: str
    config: AnalysisConfig

    ref_audio: AudioData
    dif_audio: AudioData
    dif_aligned: np.ndarray

    delay: DelayResult

    ref_silence_segments: list[SilenceSegment]
    dif_silence_segments: list[SilenceSegment]
    false_silence_segments: list[SilenceSegment]
    silence_leakage_segments: list[SilenceSegment]
    silence_metrics: SilenceMetrics

    # 이상 구간 (프레임별 correlation 기반)
    anomaly_segments: list[AnomalySegment] = field(default_factory=list)

    snr_db: MetricStatus = field(default_factory=lambda: MetricStatus(None, "N/A"))
    pesq_score: MetricStatus = field(default_factory=lambda: MetricStatus(None, "N/A"))
    stoi_score: MetricStatus = field(default_factory=lambda: MetricStatus(None, "N/A"))
    rms_diff_db: MetricStatus = field(default_factory=lambda: MetricStatus(None, "N/A"))
    clipping_ratio: MetricStatus = field(default_factory=lambda: MetricStatus(None, "N/A"))
    ref_noise_floor_db: MetricStatus = field(default_factory=lambda: MetricStatus(None, "N/A"))
    dif_noise_floor_db: MetricStatus = field(default_factory=lambda: MetricStatus(None, "N/A"))

    spectrum: Optional[SpectrumData] = None
    error_log: list[AnalysisMessage] = field(default_factory=list)
