# Tech Stack

## 언어
- Python 3.10+ (type hints, `float | None`, `list[str]` 등 사용)

## 주요 라이브러리
- **numpy / scipy**: 신호 처리, 리샘플링, cross-correlation, spectrogram
- **soundfile**: WAV 파일 I/O
- **webrtcvad-wheels**: WebRTC VAD (Windows pre-built)
- **pystoi**: STOI 음성 명료도 지수
- **pesq** (선택): PESQ MOS-LQO (C++ 빌드 도구 필요, 미설치 시 N/A 처리)
- **PyQt5**: 데스크톱 GUI
- **matplotlib**: 차트/시각화 (Qt5Agg 백엔드)
- **hypothesis**: Property-based testing

## 테스트
- **pytest** 사용
- **hypothesis**로 속성 기반 테스트 (PBT) 작성
- 테스트 파일: `tests/` 디렉토리, `test_*.py` 네이밍

## 빌드 & 실행 명령어

```bash
# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 앱 실행
python main.py

# 테스트 실행
python -m pytest tests/ -q
```

## 코딩 컨벤션
- 주석은 한글로 작성
- 복잡한 로직에만 주석 추가
- 새 기능 추가 시 테스트 코드 필수
- dataclass 기반 데이터 모델 (`models.py`)
- 커스텀 예외 클래스 사용 (`errors.py`의 `AudioAnalyzerError`)
- 지표 계산 실패 시 `MetricStatus(value=None, status="N/A")` 패턴으로 graceful 처리
