# Audio Quality Analyzer

ref(원본 전송음)와 dif(수신 녹음본) WAV 파일을 비교하여 지연 보정, 이상 구간 검출(묵음/깨짐), 음질 지표, 스펙트럼 분석을 수행하는 데스크톱 도구입니다.

## 핵심 기능

- Cross-correlation + DTW 기반 지연 추정 및 자동 보정
- 주변 대비 ratio 급변 + correlation 기반 이상 구간 검출 (묵음/깨짐)
- 음질 지표: SNR, PESQ, STOI, RMS diff, Clipping, Noise Floor
- 스펙트럼 분석: Spectrogram, Spectral Centroid/Rolloff, Pitch, ZCR
- JSON / CSV / PNG / HTML 결과 내보내기
- PyQt5 다크 테마 GUI, 듀얼 페어 비교 분석

## 이상 검출 알고리즘

ref 대비 dif의 묵음과 음깨짐을 사람이 느끼는 수준으로 감지합니다.

- 프레임별 ref/dif RMS, peak, correlation 계산 (20ms 프레임, 10ms 홉)
- 주변 1초 구간의 ratio 중앙값 대비 급격한 하락 검출
- `digital_zero` (묵음): dif peak ≈ 0 + ref 음성 구간, 최소 50ms
- `gain_drop` (깨짐 Type A): ratio 급락 + correlation > 0.3, 최소 50ms
- `gain_drop` (깨짐 Type B): ratio 급락 + 100ms 이상 지속 (gap 허용 병합)
- 묵음 직후 200ms 이내의 distortion은 복구 과정으로 제외

## 실행 방법

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 테스트

```powershell
venv\Scripts\python -m pytest tests/ -q
```

`sample_audio/` 디렉토리에 WAV 파일이 없으면 일부 회귀 테스트는 skip됩니다.

## 모듈 구조

| 파일 | 역할 |
|---|---|
| `main.py` | PyQt5 GUI 엔트리포인트 |
| `analyzer.py` | 분석 파이프라인 Facade |
| `audio_io.py` | WAV 로드, 포맷 정규화, 리샘플링 |
| `delay.py` | Cross-correlation + DTW 지연 보정 |
| `vad.py` | 묵음 판별 앙상블 (log-energy + WebRTC VAD + ZCR) |
| `silence_metrics.py` | 이상 구간 검출 (주변 대비 ratio 급변 + correlation) |
| `metrics.py` | SNR, PESQ, STOI, RMS, Clipping, Noise Floor |
| `spectrum.py` | 스펙트럼 분석 |
| `export.py` | JSON / CSV / PNG / HTML 저장 |
| `models.py` | 데이터 모델 (dataclass) |
| `errors.py` | 오류 코드 및 예외 클래스 |
| `tests/` | pytest 테스트 |
| `unused_scripts/` | 미사용 레거시 스크립트 |

## 출력 데이터 해석

| 지표 | 설명 |
|---|---|
| Delay | 적용된 최종 지연(ms). coarse/refined 중 MAE가 낮은 값 자동 선택 |
| 이상 검출 (묵음) | dif에서 디지털 제로 구간 수 (0 = 정상) |
| 이상 검출 (깨짐) | dif에서 gain 변조 구간 수 (0 = 정상) |
| SNR (dB) | 높을수록 ref와 유사 |
| PESQ | 1.0~4.5, 높을수록 음질 좋음 |
| STOI | 0.0~1.0, 높을수록 명료도 유사 |
| RMS diff (dB) | 0에 가까울수록 레벨 유사 |
| Clipping | 0에 가까울수록 좋음 |
| Noise floor (dB) | 낮을수록 조용한 배경 |

## 주의사항

- PESQ는 C++ 컴파일러가 필요하며, 미설치 시 N/A로 표시됩니다.
- 삽입/삭제 편집이 큰 파일은 DTW refine이 불안정할 수 있어 자동 fallback(coarse) 로직을 사용합니다.

### PESQ 설치 (Windows)

```powershell
# Microsoft C++ Build Tools 설치 필요: https://visualstudio.microsoft.com/visual-cpp-build-tools/
venv\Scripts\python -m pip install pesq
```

## 단일 스크립트 (다른 프로젝트에서 import)

`audio_anomaly_detector.py` 파일 하나만으로 이상 검출 기능을 사용할 수 있습니다.
GUI, 스펙트럼 분석 등 부가 기능 없이 핵심 검출 결과만 반환합니다.

```python
from audio_anomaly_detector import detect_dif_only_events

events = detect_dif_only_events("ref.wav", "dif.wav")
for e in events:
    print(f"#{e['index']} [{e['type']}] {e['duration_ms']:.0f}ms "
          f"({e['start_s']:.3f}s ~ {e['end_s']:.3f}s)")
```

필수 라이브러리: `numpy`, `scipy`, `soundfile`

CLI로도 실행 가능합니다:
```powershell
python audio_anomaly_detector.py ref.wav dif.wav
```

사용 예시는 `sample_usage.py`를 참고하세요.
