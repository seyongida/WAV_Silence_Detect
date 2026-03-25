# Design Document: Audio Quality Analyzer

## Overview

Audio Quality Analyzer는 기준 음원(ref.wav)과 비교 음원(dif.wav)을 입력받아 두 음원 간의 품질 차이를 정량적으로 측정하고 시각화하는 Python 기반 데스크톱 애플리케이션이다.

핵심 설계 원칙:
- **UI/분석 완전 분리**: `main.py`는 PyQt5 UI만 담당하고, 모든 분석 로직은 `analyzer.py` 및 하위 모듈에 위치한다.
- **부분 실패 허용**: PESQ, STOI 등 선택적 지표 계산 실패 시 나머지 분석은 계속 진행한다.
- **결정론적 처리**: 동일 입력과 동일 `AnalysisConfig`에 대해 항상 동일한 결과를 반환한다.
- **원본 불변**: 리샘플링 및 포맷 변환은 분석 전용 임시 신호에만 적용하며 원본 파일을 변경하지 않는다.

---

## Architecture

### 전체 구조

```
┌────────────────────────────────────────────────────────────────┐
│                        main.py (PyQt5 UI)                      │
│  ┌──────────┐  ┌─────────────────┐  ┌────────────────────────┐ │
│  │ FilePanel│  │ ParamPanel      │  │ ResultPanel + LogPanel │ │
│  │ (파일선택)│  │(AnalysisConfig) │  │ (파형/스펙트로그램/수치)  │ │
│  └──────────┘  └─────────────────┘  └────────────────────────┘ │
│                        │ QThread                               │
└────────────────────────┼───────────────────────────────────────┘
                         │ run_analysis(ref_path, dif_path, config)
                         ▼
┌───────────────────────────────────────────────────────────────┐
│                     analyzer.py (Facade)                      │
│    run_analysis(ref_path, dif_path, config) → AnalysisResult  │
└──┬──────────┬──────────┬──────────┬──────────┬───────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
audio_io  delay.py   vad.py   metrics.py  spectrum.py
.py                              │
                          silence_metrics.py
                                        export.py (저장)
```

### 분석 파이프라인 (순서)

```
1.  audio_io.load_wav()               → ref_audio, dif_audio (AudioData)
2.  audio_io.normalize_format()       → dif_audio (ref 포맷으로 변환)
3.  delay.estimate_delay_cc()         → coarse_delay_ms (Cross-correlation)
4.  delay.refine_delay_dtw()          → refined_delay_ms (DTW ±500ms 윈도우)
5.  delay.apply_delay()               → dif_aligned (정렬된 dif 신호)
    └─ DelayResult(coarse, refined, applied, dtw_used) 생성
6.  metrics.extract_common_segment()  → ref_common, dif_common (공통 구간 추출)
7.  vad.compute_frames(ref, ...)      → ref_frames
    vad.compute_frames(dif_aligned, ...) → dif_frames
8.  vad.detect_silence(ref_frames, ...)   → ref_silence (Frame 필드도 채워짐)
    vad.detect_silence(dif_frames, ...)   → dif_silence (Frame 필드도 채워짐)
9.  silence_metrics.compute_silence_metrics(ref_frames, dif_frames, ref_silence, dif_silence, ...) → SilenceMetrics, false_silence_segments, silence_leakage_segments
10. metrics.compute_snr()             → snr_db (공통 구간 기준)
11. metrics.compute_pesq()            → pesq_score (실패 시 None)
12. metrics.compute_stoi()            → stoi_score (실패 시 None)
13. metrics.compute_rms_diff()        → rms_diff_db
14. metrics.compute_clipping()        → clipping_ratio
15. metrics.compute_noise_floor()     → ref_noise_floor_db, dif_noise_floor_db
16. spectrum.compute_all()            → SpectrumData
17. → AnalysisResult (집계)
```

---

## Components and Interfaces

### `main.py` — PyQt5 UI

```python
class MainWindow(QMainWindow):
    """메인 윈도우: 파일 선택, 파라미터 패널, 결과 패널을 포함한다.
    
    AnalysisWorker.finished 시그널 수신 시:
    - AnalysisResult.error_log를 LogPanel에 반영 (append_message 호출)
    - ResultPanel.update_result(result) 호출
    UI 조립 및 시그널 연결 책임은 MainWindow에 집중한다.
    """

class AnalysisWorker(QThread):
    """백그라운드 분석 스레드. analyzer.run_analysis()를 호출하고 진행 상황을 시그널로 전달한다."""
    progress = pyqtSignal(int, str)   # (percent, status_text)
    finished = pyqtSignal(object)     # AnalysisResult
    error = pyqtSignal(str)           # error_message

class FilePanel(QWidget):
    """ref/dif 파일 선택 컨트롤 및 파일 정보 표시."""

class ParamPanel(QWidget):
    """AnalysisConfig 파라미터 입력 패널. 유효성 검증 포함.
    
    표시 파라미터:
    - Frame 길이 (ms, 기본값 20)
    - Hop 길이 (ms, 기본값 10)
    - Noise_Floor 백분위수 (%, 기본값 15)
    - Energy_Margin (dB, 기본값 10.0)
    - VAD_Aggressiveness (정수 0~3, 기본값 2)
    - ZCR 임계값 (기본값 0.1)
    - 최소 묵음 지속 시간 (ms, 기본값 200)
    - 묵음 병합 간격 (ms, 기본값 50)
    """

class ResultPanel(QWidget):
    """분석 결과 표시: 파형, 스펙트로그램, 수치 지표, 시계열 그래프.
    
    - ref silence 오버레이 체크박스: 기본값 hidden (체크 해제)
    - dif silence 오버레이는 항상 표시
    - False_Silence 오버레이: AnalysisResult.false_silence_segments 사용 (빨간색)
    - Silence_Leakage 오버레이: AnalysisResult.silence_leakage_segments 사용 (노란색)
    - 지연 보정 결과(DelayResult) 수치 표시 영역 포함
    """

class LogPanel(QWidget):
    """분석 로그 표시 패널. AnalysisMessage 목록을 level별 색상으로 표시한다.
    
    - info: 기본 색상
    - warn: 주황색
    - error: 빨간색
    """

    def append_message(self, msg: "AnalysisMessage") -> None:
        """AnalysisMessage를 로그 영역에 추가한다."""

    def clear(self) -> None:
        """로그 영역을 초기화한다."""
```


### `analyzer.py` — Facade

```python
def run_analysis(
    ref_path: str,
    dif_path: str,
    config: AnalysisConfig,
    progress_callback: Callable[[int, str], None] | None = None
) -> AnalysisResult:
    """전체 분석 파이프라인을 순서대로 실행하고 AnalysisResult를 반환한다."""

def validate_config(config: AnalysisConfig) -> list[str]:
    """AnalysisConfig의 유효성을 검증하고 오류 메시지 목록을 반환한다.

    검증 규칙:
    - hop_ms <= frame_ms
    - noise_floor_percentile: 0 ~ 100
    - vad_aggressiveness: 0 ~ 3
    - min_silence_ms > 0
    - silence_merge_ms >= 0

    반환값: 오류 메시지 목록 (빈 목록이면 유효)
    """
```

### `audio_io.py` — 파일 I/O 및 포맷 정규화

```python
def load_wav(path: str) -> AudioData:
    """WAV 파일을 로드하고 float32 정규화(-1.0~1.0)된 AudioData를 반환한다.
    
    입력: WAV 파일 경로
    반환: AudioData (samples, sample_rate, n_channels, duration_sec, file_path)
    오류: 파일 없음 → ERR_FILE_NOT_FOUND, 잘못된 포맷 → ERR_INVALID_FORMAT,
          1초 미만 → ERR_TOO_SHORT
    """

def normalize_format(ref: AudioData, dif: AudioData) -> AudioData:
    """dif를 ref의 샘플레이트와 채널 수로 변환한 새 AudioData를 반환한다. 원본 불변.
    
    입력: ref AudioData, dif AudioData
    반환: ref 포맷으로 변환된 새 AudioData (dif 원본 불변)
    """

def resample(audio: AudioData, target_sr: int) -> AudioData:
    """지정 샘플레이트로 리샘플링한 새 AudioData를 반환한다. 원본 불변.
    
    입력: AudioData, 목표 샘플레이트 (Hz)
    반환: 리샘플링된 새 AudioData
    """
```

### `delay.py` — 지연 보정

```python
def estimate_delay_cc(ref: np.ndarray, dif: np.ndarray, sr: int) -> float:
    """Cross-correlation 기반 전체 지연량(ms)을 추정한다.
    
    입력: ref 신호, dif 신호, 샘플레이트
    반환: 추정된 coarse 지연량 (ms)
    """

def refine_delay_dtw(
    ref: np.ndarray,
    dif: np.ndarray,
    sr: int,
    coarse_delay_ms: float
) -> float:
    """coarse_delay_ms 기준 ±500ms 윈도우 내에서 DTW로 세부 지연 보정량(ms)을 추정한다.
    DTW는 지연량 추정에만 사용하며, 비선형 워핑은 신호에 적용하지 않는다.
    
    입력: ref 신호, dif 신호, 샘플레이트, coarse 지연량 (ms)
    반환: 세부 보정된 지연량 (ms)
    """

def apply_delay(dif: np.ndarray, delay_ms: float, sr: int) -> np.ndarray:
    """지연 보정을 적용한 정렬된 dif 신호를 반환한다.
    DelayResult는 analyzer.run_analysis()에서 coarse/refined 결과와
    실제 적용 지연량(applied_delay_ms)을 조합해 생성한다.

    입력: dif 신호, 적용할 지연량 (ms), 샘플레이트
    반환: 정렬된 dif 신호 (단일 시간축 shift 적용)
    """
```


### `vad.py` — 묵음 판별

```python
def compute_frames(
    audio: np.ndarray,
    sr: int,
    config: AnalysisConfig
) -> list[Frame]:
    """오디오를 config의 frame_ms/hop_ms 기준으로 분할하여 Frame 목록을 반환한다.
    ref와 dif_aligned 각각에 대해 별도로 호출한다.

    입력: 오디오 신호, 샘플레이트, AnalysisConfig
    반환: Frame 목록
    """

def detect_silence(
    frames: list[Frame],
    sr: int,
    config: AnalysisConfig
) -> list[SilenceSegment]:
    """Frame 목록을 입력받아 log-energy, webrtcvad, ZCR 앙상블로 묵음 구간 목록을 반환한다.
    각 Frame의 log_energy, zcr, vad_speech, energy_silence, final_silence 필드를 채운다.
    webrtcvad 처리 시 필요에 따라 16kHz로 내부 리샘플링한다.

    입력: Frame 목록 (compute_frames() 결과), 샘플레이트, AnalysisConfig
    반환: SilenceSegment 목록 (min_silence_ms 이상, silence_merge_ms 간격 병합 적용)
    """

def _compute_log_energy(frame: np.ndarray) -> float:
    """프레임의 log-energy를 계산한다."""

def _compute_zcr(frame: np.ndarray) -> float:
    """프레임의 Zero Crossing Rate를 계산한다."""

def _run_webrtcvad(
    frames: list[Frame],
    sr: int,
    aggressiveness: int
) -> list[bool]:
    """webrtcvad로 각 Frame의 VAD 결과(True=음성) 목록을 반환한다.
    필요 시 각 프레임 샘플을 16kHz로 내부 리샘플링하여 처리한다.
    반환 목록의 인덱스는 입력 frames와 1:1 대응한다."""
```

### `metrics.py` — 음질 지표

```python
def extract_common_segment(
    ref: np.ndarray,
    dif_aligned: np.ndarray,
    sr: int
) -> tuple[np.ndarray, np.ndarray]:
    """지연 보정 후 시간적으로 겹치는 공통 구간(ref_common, dif_common)을 추출하여 반환한다.
    
    입력: ref 신호, 정렬된 dif 신호, 샘플레이트
    반환: (ref_common, dif_common) — 동일 길이의 공통 구간 신호
    """

def compute_snr(ref_common: np.ndarray, dif_common: np.ndarray) -> float:
    """지연 보정 후 공통 구간(ref_common, dif_common)만을 입력으로 받아 SNR(dB)을 계산한다.
    
    입력: ref 공통 구간, dif 공통 구간
    반환: SNR (dB)
    """

def compute_pesq(
    ref_common: np.ndarray,
    dif_common: np.ndarray,
    sr: int
) -> float | None:
    """지연 보정 후 공통 구간(ref_common, dif_common)을 입력으로 받아 PESQ MOS-LQO 점수를 계산한다.
    48kHz 입력은 내부적으로 16kHz로 리샘플링하여 광대역 모드로 처리한다.
    
    입력: ref 공통 구간, dif 공통 구간, 샘플레이트
    반환: PESQ MOS-LQO [1.0, 4.5], 계산 불가(라이브러리 미설치 등) 시 None
    """

def compute_stoi(
    ref_common: np.ndarray,
    dif_common: np.ndarray,
    sr: int
) -> float | None:
    """지연 보정 후 공통 구간(ref_common, dif_common)을 입력으로 받아 STOI 음성 명료도 지수를 계산한다.
    
    입력: ref 공통 구간, dif 공통 구간, 샘플레이트
    반환: STOI [0.0, 1.0], 계산 불가 시 None
    """

def compute_rms_diff(ref_common: np.ndarray, dif_common: np.ndarray) -> float:
    """공통 구간(ref_common, dif_common) 기준 RMS 에너지 차이(dB)를 반환한다.
    
    입력: ref 공통 구간, dif 공통 구간
    반환: RMS 에너지 차이 (dB, dif - ref 기준)
    """

def compute_clipping(audio: np.ndarray) -> float:
    """진폭이 ±1.0의 99.5% 이상인 샘플 비율(클리핑 비율)을 반환한다.
    
    입력: 오디오 신호
    반환: 클리핑 비율 [0.0, 1.0]
    """

def compute_noise_floor(audio: np.ndarray, sr: int, config: AnalysisConfig) -> float:
    """프레임별 log-energy 하위 percentile 기반 배경 잡음 레벨(dB)을 추정한다.
    
    입력: 오디오 신호, 샘플레이트, AnalysisConfig (noise_floor_percentile 사용)
    반환: 배경 잡음 레벨 (dB)
    """
```


### `spectrum.py` — 스펙트럼 분석

```python
def compute_spectral_centroid(audio: np.ndarray, sr: int, config: AnalysisConfig) -> np.ndarray:
    """프레임별 Spectral Centroid 시계열(Hz)을 반환한다."""

def compute_spectral_rolloff(audio: np.ndarray, sr: int, config: AnalysisConfig) -> np.ndarray:
    """프레임별 Spectral Rolloff 시계열(Hz)을 반환한다."""

def compute_pitch(audio: np.ndarray, sr: int, config: AnalysisConfig) -> np.ndarray:
    """프레임별 피치(Hz)를 반환한다. 미검출 프레임은 NaN."""

def compute_zcr(audio: np.ndarray, sr: int, config: AnalysisConfig) -> np.ndarray:
    """프레임별 ZCR 시계열을 반환한다."""

def compute_spectrogram(audio: np.ndarray, sr: int, config: AnalysisConfig) -> SpectrogramData:
    """스펙트로그램 데이터(주파수×시간 행렬, 주파수 축, 시간 축)를 반환한다."""

def compute_all(
    ref: np.ndarray,
    dif_aligned: np.ndarray,
    sr: int,
    config: AnalysisConfig
) -> SpectrumData:
    """ref와 dif_aligned에 대한 전체 스펙트럼 분석을 수행하고 SpectrumData를 반환한다.
    분석 실패 시 예외를 발생시키며, 호출자(run_analysis)가 이를 받아 spectrum=None 처리 및 warn 로그를 기록한다.
    
    입력: ref 신호, 정렬된 dif 신호, 샘플레이트, AnalysisConfig
    반환: SpectrumData
    """
```

### `silence_metrics.py` — 묵음 지표

```python
def compute_silence_metrics(
    ref_frames: list[Frame],
    dif_frames: list[Frame],
    ref_silence: list[SilenceSegment],
    dif_silence: list[SilenceSegment],
    sr: int,
    config: AnalysisConfig
) -> tuple[SilenceMetrics, list[SilenceSegment], list[SilenceSegment]]:
    """Silence_Leakage, False_Silence, 묵음 구간 통계를 계산한다.
    Frame 단위로 ref/dif 묵음 상태를 비교하여 지표를 산출한다.

    입력: ref Frame 목록, dif Frame 목록, ref 묵음 구간 목록, dif 묵음 구간 목록,
          샘플레이트, AnalysisConfig
    반환: (SilenceMetrics, false_silence_segments, silence_leakage_segments)
          - SilenceMetrics: 수치 지표
          - false_silence_segments: False_Silence 오버레이용 구간 목록
          - silence_leakage_segments: Silence_Leakage 오버레이용 구간 목록
    """
```

### `export.py` — 결과 저장

```python
def save_json(result: AnalysisResult, path: str) -> None:
    """AnalysisResult를 JSON 파일로 저장한다.
    
    포함 내용: 입력 파일 경로, 분석 시각, AnalysisConfig, 주요 지표, 묵음 구간 정보
    입력: AnalysisResult, 저장 경로
    """

def save_png(figures: list, path: str) -> None:
    """matplotlib Figure 목록을 PNG 이미지 파일로 저장한다.
    여러 Figure는 path 기반 번호 접미사(예: _1.png, _2.png)로 저장한다.
    
    입력: matplotlib Figure 목록, 저장 경로 (기본 경로)
    """

def save_csv(result: AnalysisResult, path: str) -> None:
    """AnalysisResult의 주요 지표 요약을 CSV 파일로 저장한다.
    
    포함 내용: SNR, PESQ, STOI, RMS 차이, Clipping 비율, 묵음 통계
    입력: AnalysisResult, 저장 경로
    """
```

---

## Data Models

데이터 모델은 `models.py`에 정의한다. 파일명 `dataclasses.py`는 파이썬 표준 라이브러리와 충돌하므로 사용하지 않는다.

```python
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

@dataclass
class AnalysisMessage:
    """분석 중 발생한 로그 메시지."""
    level: str      # "info" | "warn" | "error"
    message: str    # 메시지 내용
    timestamp: str  # ISO 8601 형식 (예: "2024-01-01T12:00:00.000Z")

@dataclass
class AudioData:
    """로드된 오디오 신호와 메타데이터."""
    samples: np.ndarray     # float32, shape: (n_samples,) 또는 (n_samples, n_channels)
    sample_rate: int        # 샘플레이트 (Hz)
    n_channels: int         # 채널 수
    duration_sec: float     # 길이 (초)
    file_path: str          # 원본 파일 경로

@dataclass
class Frame:
    """분석 단위 오디오 구간."""
    index: int                          # 프레임 인덱스
    start_ms: float                     # 시작 시간 (ms)
    end_ms: float                       # 종료 시간 (ms)
    samples: np.ndarray                 # 해당 구간 샘플
    log_energy: float | None = None
    zcr: float | None = None
    vad_speech: bool | None = None      # webrtcvad 결과 (True=음성)
    energy_silence: bool | None = None  # 에너지 기반 묵음 판별 결과
    final_silence: bool | None = None   # 앙상블 최종 묵음 판별 결과

@dataclass
class SilenceSegment:
    """묵음 구간 정보."""
    start_ms: float     # 시작 시간 (ms)
    end_ms: float       # 종료 시간 (ms)
    duration_ms: float  # 지속 시간 (ms)

@dataclass
class DelayResult:
    """지연 보정 계산 결과."""
    coarse_delay_ms: float      # Cross-correlation으로 추정한 coarse 지연량 (ms)
    refined_delay_ms: float     # DTW로 세부 보정한 지연량 (ms)
    applied_delay_ms: float     # 실제 적용된 최종 지연량 (ms)
    dtw_used: bool              # DTW 세부 보정 적용 여부

@dataclass
class SilenceMetrics:
    """묵음 관련 지표 (수치만 포함, 구간 목록은 AnalysisResult에서 관리)."""
    silence_leakage: float      # ref 묵음 중 dif에 소리가 있는 비율 (0~1)
    false_silence: float        # ref Non-Silence 중 dif가 묵음인 비율 (0~1)
    dif_silence_count: int      # dif 묵음 구간 총 개수
    dif_total_silence_ms: float # dif 묵음 총 시간 (ms)
    
@dataclass
class SpectrogramData:
    """스펙트로그램 데이터."""
    magnitude_db: np.ndarray    # shape: (n_freq, n_time), dB 스케일
    frequencies: np.ndarray     # 주파수 축 (Hz)
    times: np.ndarray           # 시간 축 (s)

@dataclass
class SpectrumData:
    """스펙트럼 분석 결과."""
    ref_centroid: np.ndarray        # ref Spectral Centroid 시계열 (Hz)
    dif_centroid: np.ndarray        # dif Spectral Centroid 시계열 (Hz)
    ref_rolloff: np.ndarray         # ref Spectral Rolloff 시계열 (Hz)
    dif_rolloff: np.ndarray         # dif Spectral Rolloff 시계열 (Hz)
    ref_pitch: np.ndarray           # ref 피치 시계열 (Hz, NaN=미검출)
    dif_pitch: np.ndarray           # dif 피치 시계열 (Hz, NaN=미검출)
    mean_pitch_diff_hz: float       # 유효 프레임 기준 평균 피치 차이 (Hz)
    ref_zcr: np.ndarray             # ref ZCR 시계열
    dif_zcr: np.ndarray             # dif ZCR 시계열
    ref_spectrogram: SpectrogramData
    dif_spectrogram: SpectrogramData

@dataclass
class MetricStatus:
    """지표 계산 상태."""
    value: Optional[float]      # 계산된 값 (실패 시 None)
    status: str                 # "success" | "N/A" | "failed"
    reason: Optional[str] = None  # 실패 사유 (optional)

@dataclass
class AnalysisResult:
    """전체 분석 결과."""
    # 입력 정보
    ref_path: str
    dif_path: str
    analysis_timestamp: str     # ISO 8601
    config: AnalysisConfig

    # 신호 데이터 (시각화용)
    ref_audio: AudioData
    dif_audio: AudioData        # 포맷 정규화 후
    dif_aligned: np.ndarray     # 지연 보정 후 정렬된 dif 샘플

    # 지연 보정
    delay: DelayResult          # 지연 보정 전체 결과 (coarse/refined/applied/dtw_used)

    # 묵음 구간 (시각화 및 분석용)
    ref_silence_segments: list[SilenceSegment]  # UI 기본 표시 대상이 아니며, Silence_Leakage / False_Silence 계산 및 디버깅 목적의 내부 분석 결과로 유지
    dif_silence_segments: list[SilenceSegment]  # UI에 항상 표시되는 dif 묵음 구간 목록
    false_silence_segments: list[SilenceSegment]   # False_Silence 오버레이용 구간 목록 (빨간색)
    silence_leakage_segments: list[SilenceSegment] # Silence_Leakage 오버레이용 구간 목록 (노란색)
    silence_metrics: SilenceMetrics

    # 음질 지표
    snr_db: MetricStatus
    pesq_score: MetricStatus
    stoi_score: MetricStatus
    rms_diff_db: MetricStatus
    clipping_ratio: MetricStatus
    ref_noise_floor_db: MetricStatus
    dif_noise_floor_db: MetricStatus

    # 스펙트럼 분석
    spectrum: SpectrumData | None

    # 오류 로그
    error_log: list[AnalysisMessage] = field(default_factory=list)
```


---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system.*

### Property 1: 리샘플링 원본 불변

*For any* 오디오 신호와 목표 샘플레이트에 대해, `resample()` 또는 `normalize_format()` 호출 후 원본 `AudioData.samples` 배열은 변경되지 않아야 한다.

**Validates: Requirements 1.2, 3.3**

---

### Property 2: 짧은 파일 오류 반환

*For any* 길이가 1초 미만인 WAV 파일에 대해, `run_analysis()`는 분석 결과 대신 오류를 반환해야 한다.

**Validates: Requirements 1.3**

---

### Property 3: 포맷 정규화 후 샘플레이트/채널 일치

*For any* 샘플레이트 또는 채널 수가 다른 ref/dif 쌍에 대해, `normalize_format()` 호출 후 반환된 dif의 샘플레이트와 채널 수는 ref와 동일해야 한다.

**Validates: Requirements 3.1**

---

### Property 4: 정규화된 샘플 범위

*For any* 유효한 WAV 파일에 대해, `load_wav()` 호출 후 반환된 `AudioData.samples`의 모든 값은 [-1.0, 1.0] 범위 내에 있어야 한다.

**Validates: Requirements 3.2**

---

### Property 5: 잘못된 파일 형식 오류 반환

*For any* 유효한 WAV 형식이 아닌 파일 경로에 대해, `load_wav()`는 파일 형식 오류를 반환해야 한다.

**Validates: Requirements 3.4**

---

### Property 6: 지연 추정 정확도 (라운드 트립)

*For any* 오디오 신호와 알려진 지연량 d(ms)에 대해, 신호를 d만큼 이동시킨 후 `estimate_delay_cc()`로 추정한 지연량은 d에 근접해야 한다 (허용 오차: ±10ms).

**Validates: Requirements 4.1, 4.4**

---

### Property 7: 프레임 분할 커버리지

*For any* 오디오 신호와 `AnalysisConfig`에 대해, `compute_frames(audio, sr, config)`가 반환하는 프레임 목록은 전체 오디오 구간을 빠짐없이 커버해야 하며, 각 프레임의 길이는 `frame_ms`와 일치해야 한다 (마지막 프레임 제외).

**Validates: Requirements 5.1, 5.2, 5.3**

---

### Property 8: 최소 묵음 지속 시간 준수

*For any* Frame 목록과 `AnalysisConfig`에 대해, `detect_silence()`가 반환하는 모든 `SilenceSegment`의 `duration_ms`는 `config.min_silence_ms` 이상이어야 한다.

**Validates: Requirements 6.7**

---

### Property 9: 묵음 구간 병합

*For any* Frame 목록과 `AnalysisConfig`에 대해, `detect_silence()`가 반환하는 인접한 두 `SilenceSegment` 사이의 간격은 `config.silence_merge_ms` 이상이어야 한다.

**Validates: Requirements 6.8**

---

### Property 10: 묵음 비율 범위

*For any* ref/dif Frame 목록과 묵음 구간 목록에 대해, `compute_silence_metrics()`가 반환하는 `silence_leakage`와 `false_silence`는 모두 [0.0, 1.0] 범위 내에 있어야 한다.

**Validates: Requirements 7.4, 7.5**

---

### Property 11: SNR 동일 신호 상한

*For any* 오디오 신호 ref에 대해, `ref_common == dif_common`인 케이스에서 `compute_snr(ref_common, dif_common)`는 매우 큰 값(예: > 100 dB)을 반환해야 한다.

**Validates: Requirements 8.1**

---

### Property 12: PESQ 점수 범위

*For any* 유효한 ref/dif 쌍에 대해, `compute_pesq()`가 `None`이 아닌 값을 반환할 때 그 값은 [1.0, 4.5] 범위 내에 있어야 한다.

**Validates: Requirements 8.2**

---

### Property 13: STOI 점수 범위

*For any* 유효한 ref/dif 쌍에 대해, `compute_stoi()`가 `None`이 아닌 값을 반환할 때 그 값은 [0.0, 1.0] 범위 내에 있어야 한다.

**Validates: Requirements 8.3**

---

### Property 14: Clipping 비율 계산 정확도

*For any* 알려진 클리핑 샘플 수를 가진 신호에 대해, `compute_clipping()`이 반환하는 비율은 (클리핑 샘플 수 / 전체 샘플 수)와 일치해야 한다.

**Validates: Requirements 8.5**

---

### Property 15: 피치 차이 유효 프레임 한정

*For any* ref/dif 쌍에 대해, `SpectrumData.mean_pitch_diff_hz`는 ref와 dif 모두에서 유효한 피치(NaN이 아닌 값)가 검출된 프레임만을 기준으로 계산되어야 한다.

**Validates: Requirements 9.3**

---

### Property 16: 결과 객체 필수 필드 포함

*For any* 유효한 분석 실행에 대해, `run_analysis()`가 반환하는 `AnalysisResult`는 `ref_path`, `dif_path`, `analysis_timestamp`, `config`, `delay`, `snr_db`, `silence_metrics` 필드를 항상 포함해야 한다.

**Validates: Requirements 11.4, 4.4**

---

### Property 17: 분석 결정론성

*For any* 동일한 ref/dif 파일 쌍과 동일한 `AnalysisConfig`에 대해, `run_analysis()`를 두 번 실행한 결과는 모든 수치 지표에서 동일해야 한다.

**Validates: Requirements 12.5**

---

### Property 18: 핵심 단계 실패 시 전체 중단

*For any* 파일 읽기 또는 포맷 정규화가 실패하는 입력에 대해, `run_analysis()`는 부분 결과를 반환하지 않고 오류를 반환해야 한다.

**Validates: Requirements 12.6**

---

### Property 19: Config 검증 오류 감지

*For any* `AnalysisConfig`에 대해, `hop_ms > frame_ms`이거나 `vad_aggressiveness`가 0~3 범위를 벗어나거나 `noise_floor_percentile`이 0~100 범위를 벗어나는 경우, `validate_config()`는 비어 있지 않은 오류 메시지 목록을 반환해야 한다.

**Validates: AnalysisConfig validation constraints (hop_ms, vad_aggressiveness, noise_floor_percentile 범위 규칙)**

---

### Property 20: 유효한 Config 검증 통과

*For any* 모든 필드가 유효 범위 내에 있는 `AnalysisConfig`에 대해, `validate_config()`는 빈 목록을 반환해야 한다.

**Validates: AnalysisConfig validation constraints**


---

## Error Handling

### 오류 클래스

모든 분석 오류는 `errors.py`에 정의된 `AudioAnalyzerError`를 사용한다.

```python
class AudioAnalyzerError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code        # 오류 코드 상수 (ERR_* 형태)
        self.message = message  # 사람이 읽을 수 있는 오류 설명
        super().__init__(message)

# 오류 코드 상수
ERR_FILE_NOT_FOUND  = "ERR_FILE_NOT_FOUND"
ERR_INVALID_FORMAT  = "ERR_INVALID_FORMAT"
ERR_TOO_SHORT       = "ERR_TOO_SHORT"
ERR_DELAY_FAILED    = "ERR_DELAY_FAILED"
```

모든 모듈에서 예외 발생 시 `raise AudioAnalyzerError(ERR_*, "설명")` 형태로 통일한다.

### 오류 분류

| 오류 유형 | 코드 | 처리 방식 |
|---|---|---|
| 파일 없음 | `ERR_FILE_NOT_FOUND` | 전체 분석 중단, UI에 메시지 표시 |
| 잘못된 포맷 | `ERR_INVALID_FORMAT` | 전체 분석 중단, UI에 메시지 표시 |
| 파일 길이 미달 | `ERR_TOO_SHORT` | 전체 분석 중단, UI에 메시지 표시 |
| PESQ 계산 실패 | — | `MetricStatus(value=None, status="N/A")`, 로그 기록, 분석 계속 |
| STOI 계산 실패 | — | `MetricStatus(value=None, status="N/A")`, 로그 기록, 분석 계속 |
| 스펙트럼 분석 실패 | — | `spectrum=None`, 로그 기록, 분석 계속 |
| 지연 보정 실패 | `ERR_DELAY_FAILED` | 전체 분석 중단, UI에 메시지 표시 |

### 핵심 단계 vs 선택적 단계

- **핵심 단계** (실패 시 전체 중단): 파일 읽기, 포맷 정규화, 지연 보정, 프레임 분할
- **선택적 단계** (실패 시 N/A 처리): PESQ, STOI, 스펙트럼 분석, 피치 분석

### UI 오류 표시

- 핵심 단계 오류: 모달 다이얼로그로 표시
- 선택적 지표 실패: LogPanel에 표시, 해당 지표는 "N/A"로 표시

---

## Testing Strategy

### 이중 테스트 접근법

단위 테스트와 속성 기반 테스트를 함께 사용하여 포괄적인 커버리지를 확보한다.

**단위 테스트** — 구체적인 예시, 경계 조건, 통합 지점 검증:
- 알려진 지연량을 가진 합성 신호로 지연 추정 정확도 검증
- 특정 클리핑 패턴을 가진 신호로 Clipping 비율 계산 검증
- 포맷이 다른 ref/dif 쌍으로 정규화 동작 검증
- 1초 미만 파일로 오류 반환 검증
- 잘못된 WAV 파일로 오류 코드 검증

**속성 기반 테스트** — 임의 입력에 대한 보편적 속성 검증:
- 라이브러리: `hypothesis` (Python)
- 최소 반복 횟수: 각 속성 테스트당 100회 이상
- 각 테스트에 설계 문서 속성 참조 태그 포함

### 속성 기반 테스트 설정

```python
from hypothesis import given, settings
from hypothesis import strategies as st

@settings(max_examples=100)
@given(st....)
def test_property_N_description():
    # Feature: audio-quality-analyzer, Property N: <property_text>
    ...
```

### 속성별 테스트 매핑

| 속성 | 테스트 유형 | 생성 전략 |
|---|---|---|
| Property 1: 리샘플링 원본 불변 | property | 임의 float32 배열, 임의 목표 SR |
| Property 2: 짧은 파일 오류 | property | 0~0.99초 길이 합성 WAV |
| Property 3: 포맷 정규화 | property | 임의 SR/채널 조합 |
| Property 4: 샘플 범위 | property | 임의 정수 PCM 값 |
| Property 5: 잘못된 파일 오류 | property | 임의 바이트 시퀀스 |
| Property 6: 지연 추정 | property | 임의 신호 + 알려진 지연, 허용 오차 ±10ms |
| Property 7: 프레임 커버리지 | property | 임의 길이 신호 + 임의 config |
| Property 8: 최소 묵음 지속 | property | 임의 Frame 목록 (에너지 패턴 다양) |
| Property 9: 묵음 병합 | property | 인접 묵음 구간을 가진 Frame 목록 |
| Property 10: 묵음 비율 범위 | property | 임의 Frame 목록 + 묵음 구간 목록 |
| Property 11: SNR 동일 신호 | example | ref == dif 케이스 |
| Property 12: PESQ 범위 | property | 유효한 8/16kHz 신호 쌍 |
| Property 13: STOI 범위 | property | 유효한 신호 쌍 |
| Property 14: Clipping 정확도 | property | 알려진 클리핑 패턴 신호 |
| Property 15: 피치 차이 한정 | property | 임의 피치 패턴 신호 |
| Property 16: 결과 필수 필드 | property | 임의 유효 입력 쌍 |
| Property 17: 결정론성 | property | 임의 유효 입력 쌍 |
| Property 18: 핵심 실패 중단 | property | 손상된 파일 입력 |
| Property 19: Config 검증 오류 감지 | property | 범위 위반 AnalysisConfig |
| Property 20: 유효한 Config 검증 통과 | property | 유효 범위 내 AnalysisConfig |

### 의존성

```
pytest
hypothesis
numpy
scipy
soundfile
librosa
webrtcvad
pesq
pystoi
PyQt5
matplotlib
```
