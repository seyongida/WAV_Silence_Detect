# Project Structure

```
├── main.py                 # PyQt5 GUI 엔트리포인트 (MainWindow, 패널 위젯)
├── analyzer.py             # 분석 파이프라인 Facade (AnalysisConfigV2, run_analysis)
├── audio_io.py             # WAV 로드, float32 정규화, 리샘플링, 포맷 정렬
├── delay.py                # Cross-correlation + DTW 지연 추정/보정
├── vad.py                  # 묵음 판별 앙상블 (log-energy, webrtcvad, ZCR)
├── silence_metrics.py      # 묵음 지표 (leakage, false silence, dif-only)
├── metrics.py              # 음질 지표 (SNR, PESQ, STOI, RMS, Clipping, Noise Floor)
├── spectrum.py             # 스펙트럼 분석 (centroid, rolloff, pitch, ZCR, spectrogram)
├── export.py               # JSON / CSV / PNG 결과 저장
├── models.py               # 데이터 모델 (dataclass 정의)
├── errors.py               # 오류 코드 상수 및 AudioAnalyzerError 예외 클래스
├── requirements.txt        # pip 의존성
├── tests/                  # pytest 테스트
│   ├── test_analyzer_properties.py   # analyzer PBT (Property 2, 16~20)
│   ├── test_delay.py                 # delay PBT (Property 6)
│   ├── test_audio_io.py
│   ├── test_metrics.py
│   ├── test_silence_metrics.py
│   ├── test_spectrum.py
│   ├── test_vad.py
│   ├── test_export.py
│   └── test_regression_ref_dif.py    # 실제 샘플 기반 회귀 테스트
├── sample_audio/           # 테스트용 WAV 샘플
└── unused_scripts/         # 미사용 레거시 코드 (수정 불필요)
```

## 아키텍처 패턴
- **Facade 패턴**: `analyzer.run_analysis()`가 전체 파이프라인을 조율
- **파이프라인 흐름**: 파일 로드 → 포맷 정규화 → 지연 추정/보정 → VAD → 묵음 지표 → 음질 지표 → 스펙트럼 → 결과 조립
- **모듈 분리**: 각 분석 단계가 독립 모듈로 분리되어 있음
- **UI 분리**: `main.py`는 순수 UI, 분석 로직은 `analyzer.py` 이하 모듈에 위임
- **QThread**: 분석은 `AnalysisWorker` 스레드에서 비동기 실행
