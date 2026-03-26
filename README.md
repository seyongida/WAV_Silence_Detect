# Audio Quality Analyzer

`ref`와 `dif` WAV를 비교해서 지연 보정, 묵음 차이, 품질 지표, 스펙트럼 차이를 분석하는 데스크톱 툴입니다.

## 1. 샘플 오디오

`sample_audio/` 디렉토리:

- `ref.wav` — 기준 음원
- `dif_2+shift.wav` — 비교 음원 (기본 비교 대상)
- `dif_shift.wav`, `dif_3.wav` — 추가 비교 음원
- `dating_SPEAKER_00.wav`, `dating_SPEAKER_00_AOS.wav` — 화자 0 샘플
- `dating_SPEAKER_01.wav`, `dating_SPEAKER_01_iOS.wav` — 화자 1 샘플

기본 비교 시나리오: `ref.wav` vs `dif_2+shift.wav`

## 2. 핵심 기능

- WAV 로드/검증, 샘플 정규화 (`audio_io.py`)
- ref 기준 sample rate/channel 포맷 정렬 (`audio_io.py`)
- Cross-correlation + DTW 지연 추정/보정, MAE 기반 자동 선택 (`delay.py`, `analyzer.py`)
- log-energy + WebRTC VAD + ZCR 앙상블 묵음 검출 (`vad.py`)
- silence leakage, false silence, dif-only silence 지표 (`silence_metrics.py`)
- SNR, PESQ, STOI, RMS diff, clipping, noise floor (`metrics.py`)
- spectrogram, spectral centroid/rolloff, pitch, ZCR (`spectrum.py`)
- JSON / CSV / PNG 결과 내보내기 (`export.py`)

## 3. UI 기능 (`main.py`)

- ref/dif 파일 선택 및 분석 파라미터 패널
- Waveform 오버레이 (dif silence, ref silence 토글, false silence, silence leakage)
- Residual waveform (ref - dif) 및 차이 하이라이트
- Spectrogram (ref 위, dif delay-corrected 아래)
- Spectral centroid/rolloff 시계열 및 차이 하이라이트
- 지표 요약 + 해설 테이블 (값, 참고 범위, 해석 가이드)
- Primary Outcome 패널 (dif-only silence count/total)

## 4. 분석 파라미터

기본 파라미터: `frame_ms`, `hop_ms`, `noise_floor_percentile`, `energy_margin_db`, `vad_aggressiveness`, `zcr_threshold`, `min_silence_ms`, `silence_merge_ms`

v2 추가 파라미터 (차이 하이라이트 임계값):
- `residual_diff_threshold` (기본 0.05)
- `centroid_diff_threshold_hz` (기본 300.0)
- `rolloff_diff_threshold_hz` (기본 500.0)

임계값을 올리면 하이라이트 구간이 줄어들고, 내리면 더 많이 표시됩니다.

## 5. 실행 방법

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 6. 테스트

```powershell
venv\Scripts\python -m pytest tests/ -q
```

`sample_audio/ref.wav`, `sample_audio/dif_2+shift.wav`가 없으면 일부 회귀 테스트는 skip됩니다.

## 7. 모듈 구조

| 파일 | 역할 |
|---|---|
| `main.py` | PyQt5 UI 엔트리포인트 |
| `analyzer.py` | 분석 파이프라인 Facade (지연 보정 가드레일 포함) |
| `audio_io.py` | WAV 로드, 포맷 정규화, 리샘플링 |
| `delay.py` | Cross-correlation + DTW 지연 보정 |
| `vad.py` | 묵음 판별 앙상블 |
| `metrics.py` | SNR, PESQ, STOI, RMS, Clipping, Noise Floor |
| `spectrum.py` | 스펙트럼 분석 (centroid, rolloff, pitch, ZCR, spectrogram) |
| `silence_metrics.py` | 묵음 지표 (leakage, false silence, dif-only) |
| `export.py` | JSON / CSV / PNG 저장 |
| `models.py` | 데이터 모델 (dataclass) |
| `errors.py` | 오류 코드 및 예외 클래스 |
| `tests/` | pytest 테스트 |
| `unused_scripts/` | 미사용 레거시 스크립트 |

## 8. 출력 데이터 해석

- `Delay`: 적용된 최종 지연(ms). coarse/refined 중 MAE가 낮은 값 자동 선택
- `SNR`: 높을수록 ref와 유사
- `PESQ`: 1.0~4.5, 높을수록 지각 품질 우수
- `STOI`: 0.0~1.0, 높을수록 명료도 유사
- `RMS diff`: 0 dB에 가까울수록 레벨 유사
- `Clipping ratio`: 0에 가까울수록 좋음 (±0.999 이상 샘플 비율)
- `Noise floor`: 더 낮은(dB 음수 큼) 값이 더 조용한 배경
- `Silence leakage`: ref 묵음이 dif에서 깨진 비율
- `False silence`: ref 비묵음이 dif에서 묵음으로 판정된 비율
- `dif-only silence`: ref와 겹치지 않는 dif 추가 묵음 이벤트/총시간

## 9. 주의사항

- `PESQ`는 C++ 컴파일러가 필요하며, 미설치 시 `N/A`로 표시됩니다. 다른 지표는 정상 계산됩니다.
- 삽입/삭제 편집이 큰 파일은 DTW refine이 불안정할 수 있어 자동 fallback(coarse) 로직을 사용합니다.

## 10. PESQ 설치 (Windows)

```powershell
# Microsoft C++ Build Tools 설치 필요: https://visualstudio.microsoft.com/visual-cpp-build-tools/
venv\Scripts\python -m pip install pesq
```
