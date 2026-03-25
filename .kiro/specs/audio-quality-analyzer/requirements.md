# Requirements Document

## Introduction

음성 품질 분석 도구(Audio Quality Analyzer)는 기준 음원(ref.wav)과 비교 음원(dif.wav)을 입력받아,
두 음원 간의 품질 차이를 정량적으로 측정하고 시각화하는 Python 기반 데스크톱 애플리케이션입니다.
지연 보정, VAD 기반 묵음 분석, SNR/PESQ/STOI 등 다양한 음질 지표를 계산하며,
결과는 GUI를 통해 파형 시각화와 함께 표시됩니다.


## Glossary

- **Analyzer**: 음성 분석 로직을 담당하는 모듈 (analyzer.py 및 하위 모듈)
- **UI**: 사용자 인터페이스를 담당하는 모듈 (main.py)
- **ref**: 기준 음원 (reference WAV 파일)
- **dif**: 비교 음원 (degraded/different WAV 파일)
- **Frame**: 분석 단위 오디오 구간 (기본값 20ms, Analysis_Config로 조정 가능)
- **Hop**: 프레임 이동 간격 (기본값 10ms, Analysis_Config로 조정 가능)
- **VAD**: Voice Activity Detection — 음성 구간 감지 알고리즘
- **Silence**: 묵음 구간 — 에너지와 VAD 기준을 모두 충족하는 구간
- **Non-speech**: VAD=0(비음성)으로 판정된 구간. 에너지가 존재할 수 있으며 Silence와 구분된다.
- **Non-Silence**: Silence로 판정되지 않은 구간. ref의 Non-Silence 구간은 묵음 지표(False_Silence) 계산의 기준이 된다.
- **Analysis_Config**: UI에서 사용자가 설정하는 분석 파라미터 집합 (Frame 길이, Hop 길이, VAD aggressiveness 등)
- **Silence_Leakage**: ref 묵음 구간에서 dif에 소리가 감지되는 비율
- **False_Silence**: ref Non-Silence 구간에서 dif가 묵음으로 판정되는 비율
- **SNR**: Signal-to-Noise Ratio — 신호 대 잡음비 (dB)
- **PESQ**: Perceptual Evaluation of Speech Quality (ITU-T P.862) — 지각적 음질 평가 점수
- **STOI**: Short-Time Objective Intelligibility — 음성 명료도 지수 (0~1)
- **ZCR**: Zero Crossing Rate — 영교차율, 유/무성음 구분 보조 지표
- **Noise_Floor**: 프레임별 log-energy 분포에서 Analysis_Config의 백분위수 기준으로 추정한 적응형 잡음 레벨 (기본값 15%, Analysis_Config로 조정 가능)
- **DTW**: Dynamic Time Warping — 세부 시간 정렬 알고리즘
- **Cross_Correlation**: 두 신호 간 전체 지연 추정에 사용하는 상관 분석
- **Clipping**: 오디오 신호가 최대 진폭을 초과하여 왜곡되는 현상
- **Spectral_Centroid**: 스펙트럼의 무게중심 주파수 — 음질 열화 감지 지표
- **Spectral_Rolloff**: 전체 스펙트럼 에너지의 일정 비율이 포함되는 주파수 — 음질 열화 감지 지표
- **RMS**: Root Mean Square — 신호의 실효값 에너지

---

## Requirements

### Requirement 1: 분석 지원 범위

**User Story:** 개발자로서, 도구가 지원하는 파일 포맷과 분석 범위를 명확히 알고 싶습니다. 그래야 지원 범위 외 파일로 인한 오류를 사전에 방지할 수 있습니다.

#### Acceptance Criteria

1. THE UI SHALL 지원 파일 형식(WAV), 지원 샘플레이트(8kHz, 16kHz, 32kHz, 44.1kHz, 48kHz), 지원 채널(모노/스테레오), 권장 파일 길이(최대 10분), 최소 파일 길이(1초 이상)를 GUI 내에 명시한다.
2. THE Analyzer SHALL 입력 샘플레이트가 8kHz, 16kHz, 32kHz, 44.1kHz, 48kHz 중 하나인 경우 정상 처리하며, 내부 분석 시 알고리즘 요구사항에 따라 자동 리샘플링 처리한다. 리샘플링은 분석 전용 임시 신호에만 적용하며 원본 신호를 변경하지 않는다.
3. IF 선택된 파일의 길이가 1초 미만인 경우, THEN THE Analyzer SHALL 최소 길이 미달 오류 메시지를 반환하고 분석을 중단한다.
4. IF 선택된 파일의 길이가 10분을 초과하는 경우, THEN THE UI SHALL 권장 길이 초과 경고 메시지를 표시하되 분석은 계속 진행할 수 있도록 한다.

---

### Requirement 2: 파일 선택 및 품질 측정 실행

**User Story:** 개발자로서, GUI에서 ref.wav와 dif.wav를 선택하고 품질 측정 버튼을 눌러 분석을 실행하고 싶습니다. 그래야 별도의 CLI 없이 간편하게 음성 품질을 확인할 수 있습니다.

#### Acceptance Criteria

1. THE UI SHALL ref.wav 파일과 dif.wav 파일을 각각 선택할 수 있는 파일 선택 컨트롤을 제공한다.
2. WHEN 두 파일이 모두 선택된 상태에서 사용자가 '품질 측정' 버튼을 누르면, THE UI SHALL Analyzer를 호출하여 분석을 시작한다.
3. IF 파일이 하나라도 선택되지 않은 상태에서 '품질 측정' 버튼이 눌리면, THEN THE UI SHALL 파일 미선택 안내 메시지를 표시하고 분석을 시작하지 않는다.
4. WHILE 분석이 진행 중인 경우, THE UI SHALL 프로그레스 바와 단계별 상태 텍스트(예: "포맷 정규화 중...", "지연 보정 중...", "VAD 분석 중...", "음질 지표 계산 중...", "시각화 생성 중...")를 표시하고 '품질 측정' 버튼을 비활성화한다. 분석은 백그라운드 스레드(QThread)에서 실행되어 UI가 응답 불능 상태가 되지 않도록 한다.
5. THE UI SHALL 분석 로직을 포함하지 않으며, 모든 계산은 Analyzer 모듈을 통해 수행된다.

---

### Requirement 3: 오디오 포맷 정규화

**User Story:** 개발자로서, ref와 dif의 포맷이 달라도 자동으로 통일되기를 원합니다. 그래야 포맷 불일치로 인한 분석 오류를 방지할 수 있습니다.

#### Acceptance Criteria

1. WHEN dif 파일의 샘플레이트 또는 채널 수가 ref 파일과 다른 경우, THE Analyzer SHALL dif 오디오를 ref의 포맷(샘플레이트, 채널 수)으로 변환한다.
2. THE Analyzer SHALL 내부 분석을 위해 ref와 dif를 정규화된 부동소수점 파형(-1.0~1.0)으로 변환한다.
3. THE Analyzer SHALL 변환된 dif 오디오를 메모리 내에서만 사용하며, 원본 dif 파일을 덮어쓰지 않는다.
4. IF 파일이 유효한 WAV 형식이 아닌 경우, THEN THE Analyzer SHALL 파일 형식 오류 메시지를 반환한다.

---

### Requirement 4: 지연 보정 (2단계)

**User Story:** 개발자로서, ref와 dif 사이의 시간 지연이 자동으로 보정되기를 원합니다. 그래야 지연으로 인한 잘못된 품질 측정을 방지할 수 있습니다.

#### Acceptance Criteria

1. THE Analyzer SHALL Cross_Correlation 기반 1단계 지연 추정을 다운샘플링된 신호에 적용하여 전체 지연량(ms)을 추정한다.
2. WHEN 1단계 지연 추정이 완료된 경우, THE Analyzer SHALL 추정된 지연 지점 기준 ±500ms 윈도우 내에서만 DTW를 적용하여 세부 지연 보정량을 추정한다. DTW는 세부 지연 보정량 추정에만 사용하며, 이후 묵음 판별 및 품질 지표 비교는 보정된 단일 시간축 shift를 기준으로 수행한다. DTW 경로 기반 비선형 워핑은 적용하지 않는다.
3. THE Analyzer SHALL 지연 보정 후 정렬된 dif 신호를 이후 모든 분석 단계에 사용한다.
4. THE Analyzer SHALL 추정된 전체 지연량(ms)을 분석 결과에 포함하여 반환한다.
5. THE UI SHALL 지연 보정 완료 후 추정된 지연량(ms)을 결과 화면의 상단 요약 영역에 명확히 표시한다.

---

### Requirement 5: 프레임 분할 및 Analysis_Config 파라미터 패널

**User Story:** 개발자로서, 오디오가 일정한 단위로 분할되어 프레임별 분석이 가능하기를 원합니다. 그래야 시간 해상도 높은 분석이 가능합니다.

#### Acceptance Criteria

1. THE Analyzer SHALL 오디오 신호를 Analysis_Config의 Frame 길이(ms, 기본값 20ms) 단위로 분할한다.
2. THE Analyzer SHALL 인접 Frame 간 이동 간격(Hop)을 Analysis_Config의 Hop 길이(ms, 기본값 10ms)로 설정한다.
3. THE Analyzer SHALL 분할된 각 Frame에 대해 시작 시간(ms)과 종료 시간(ms)을 인덱스로 관리한다.
4. THE UI SHALL 다음 Analysis_Config 파라미터를 조정할 수 있는 파라미터 패널을 제공한다: Frame 길이(ms, 기본값 20), Hop 길이(ms, 기본값 10), Noise_Floor 백분위수(%, 기본값 15), Energy_Margin(dB, 기본값 10), VAD_Aggressiveness(정수 0~3, 기본값 2), ZCR 임계값(기본값 0.1), 최소 묵음 지속 시간(ms, 기본값 200), 묵음 병합 간격(ms, 기본값 50).
5. THE UI SHALL Analysis_Config의 각 파라미터에 기본값을 제공하며, 사용자가 변경한 값은 분석 시 Analyzer에 전달된다.
6. THE Analyzer SHALL Analysis_Config를 입력으로 받아 모든 분석 단계에 해당 파라미터를 적용한다.
7. THE UI SHALL Analysis_Config 입력값의 유효 범위를 검증하고, 유효하지 않은 경우 분석을 시작하지 않는다.

---

### Requirement 6: VAD 기반 묵음 판별

**User Story:** 개발자로서, 정확한 묵음 구간 감지를 위해 에너지와 VAD를 결합한 앙상블 방식이 적용되기를 원합니다. 그래야 단순 에너지 기반보다 신뢰도 높은 묵음 판별이 가능합니다.

#### Acceptance Criteria

1. THE Analyzer SHALL 각 Frame에 대해 log-energy를 계산한다.
2. THE Analyzer SHALL 전체 Frame의 log-energy 분포에서 Analysis_Config의 Noise_Floor 백분위수(기본값 하위 15%)를 Noise_Floor로 추정한다.
3. WHEN 특정 Frame의 log-energy가 Noise_Floor에 Analysis_Config의 Energy_Margin을 더한 값보다 낮은 경우, THE Analyzer SHALL 해당 Frame을 energy_silence로 표시한다.
4. THE Analyzer SHALL webrtcvad를 사용하여 각 Frame에 대한 VAD 결과를 계산한다. webrtcvad는 8kHz, 16kHz, 32kHz만 지원하므로, 입력 샘플레이트가 지원 범위 외인 경우 VAD 처리 전 16kHz로 리샘플링하여 적용하고, 결과는 원본 시간축으로 재매핑한다.
5. THE Analyzer SHALL 각 Frame에 대해 ZCR을 계산한다.
6. THE Analyzer SHALL 다음 조건 중 하나를 만족하는 Frame을 Silence로 최종 판정한다: (energy_silence AND vad_silence) OR (energy_silence AND ZCR이 임계값 이하)
7. THE Analyzer SHALL 연속된 Silence Frame의 총 지속 시간이 Analysis_Config의 최소 묵음 지속 시간(기본값 200ms) 미만인 경우 해당 구간을 Silence에서 제외한다.
8. THE Analyzer SHALL 인접한 두 Silence 구간 사이의 간격이 Analysis_Config의 묵음 병합 간격(기본값 50ms) 미만인 경우 두 구간을 하나의 Silence 구간으로 병합한다.

---

### Requirement 7: 묵음 지표 계산

**User Story:** 개발자로서, ref 기준 묵음 구간과 dif의 대응 구간을 비교한 지표를 얻고 싶습니다. 그래야 녹음 품질의 묵음 관련 문제를 정량적으로 파악할 수 있습니다.

#### Acceptance Criteria

1. THE Analyzer SHALL 지연 보정(DTW 정렬) 완료 후의 ref 시간축을 기준으로, ref의 Silence 구간에 대응하는 dif의 시간 구간을 매핑한다.
2. THE Analyzer SHALL ref와 dif 구간 매핑 시 프레임 경계 기준으로 ±1 Hop 이내의 오차를 허용한다.
3. THE Analyzer SHALL ref Silence 구간에 대응하는 dif 구간의 energy, VAD 결과, peak 진폭을 검사한다.
4. THE Analyzer SHALL Silence_Leakage를 ref 묵음 구간 중 dif에서 소리가 감지된(Non-Silence로 판정된) 구간의 비율 (0~1)로 계산한다.
5. THE Analyzer SHALL False_Silence를 다음과 같이 계산한다: ref Non-Silence 구간 중 dif가 Silence로 판정된 구간의 비율 (0~1).
6. THE Analyzer SHALL dif의 묵음 구간의 총 개수, 각 묵음 구간의 시작/종료 시간(ms) 및 지속 시간(ms), 전체 묵음 총 시간(ms)을 계산한다.

---

### Requirement 8: 음질 측정 지표 계산

**User Story:** 개발자로서, SNR, PESQ, STOI 등 표준 음질 지표를 얻고 싶습니다. 그래야 ref 대비 dif의 음질 저하 정도를 객관적으로 평가할 수 있습니다.

#### Acceptance Criteria

1. THE Analyzer SHALL 지연 보정 후 ref와 정렬된 dif의 시간적으로 겹치는 공통 구간만을 사용하여 SNR = 10 * log10(sum(ref^2) / sum((ref - dif)^2)) 를 계산한다.
2. THE Analyzer SHALL ITU-T P.862 기반 PESQ 알고리즘을 사용하여 MOS-LQO 점수(1.0~4.5)를 계산한다. PESQ는 8kHz(협대역) 및 16kHz(광대역)만 지원하며, 입력 샘플레이트가 이 외의 값(예: 48kHz)인 경우 16kHz로 다운샘플링 후 광대역(wideband) 모드로 계산한다. 리샘플링은 분석 전용 임시 신호에만 적용하며 원본 신호를 변경하지 않는다. PESQ 계산이 실패하거나 지원되지 않는 조건인 경우 해당 지표를 N/A로 처리하고 실패 사유를 로그에 기록한다.
3. THE Analyzer SHALL STOI 알고리즘을 사용하여 음성 명료도 지수(0~1)를 계산한다. STOI 계산이 실패하거나 지원되지 않는 조건인 경우 해당 지표를 N/A로 처리하고 실패 사유를 로그에 기록한다.
4. THE Analyzer SHALL ref와 dif 각각의 RMS 에너지를 계산하고 두 값의 차이(dB)를 반환한다.
5. THE Analyzer SHALL dif 신호에서 진폭이 최대값(±1.0 정규화 기준)의 99.9% 이상인 샘플의 비율을 Clipping 지표로 계산한다. (실제 음원의 Peak가 0.9999 수준으로 높아 99% 기준 시 오탐 가능성이 있으므로 99.9%로 조정)
6. THE Analyzer SHALL ref, dif 각 신호에 대해 프레임별 log-energy 하위 Analysis_Config의 Noise_Floor 백분위수(기본값 15%)를 기반으로 배경 잡음 레벨(dB)을 추정한다.

---

### Requirement 9: 스펙트럼 및 추가 분석 지표 계산

**User Story:** 개발자로서, 스펙트럼 특성과 피치 연속성 비교 결과를 얻고 싶습니다. 그래야 주파수 영역에서의 음질 열화를 감지할 수 있습니다.

#### Acceptance Criteria

1. THE Analyzer SHALL ref와 dif 각각의 Spectral_Centroid 시계열을 계산한다.
2. THE Analyzer SHALL ref와 dif 각각의 Spectral_Rolloff 시계열을 계산한다.
3. THE Analyzer SHALL ref와 dif 모두에서 유효한 피치가 검출된 Frame에 한해, 프레임별 절대 피치 차이의 평균값(Hz)을 반환한다.
4. THE Analyzer SHALL ref와 dif 각각의 ZCR 시계열을 계산한다.
5. THE Analyzer SHALL ref와 dif 각각의 스펙트로그램 데이터를 계산하여 시각화에 사용할 수 있는 형태로 반환한다.

---

### Requirement 10: 결과 시각화

**User Story:** 개발자로서, 분석 결과가 파형과 함께 GUI에 시각적으로 표시되기를 원합니다. 그래야 수치만으로는 파악하기 어려운 음질 문제를 직관적으로 확인할 수 있습니다.

#### Acceptance Criteria

1. THE UI SHALL ref와 dif의 파형(시간-진폭)을 동일한 시간 축으로 나란히 또는 겹쳐서 표시한다.
2. THE UI SHALL 파형 그래프 위에 ref와 dif 각각의 Silence 구간을 구분 가능한 색상으로 반투명 오버레이로 표시한다. ref Silence는 파란색 계열(alpha=0.2), dif Silence는 주황색 계열(alpha=0.25)로 표시하여 파형과의 시인성을 확보한다.
3. THE UI SHALL 파형 그래프 위에 ref Silence 구간 표시 여부를 제어할 수 있는 체크박스를 제공한다. 기본값은 숨김(hidden)이다.
4. THE UI SHALL False_Silence 구간(ref Non-Silence 구간 중 dif가 묵음인 구간)을 빨간색 계열(alpha=0.3)로 별도 표시하여 가장 중요한 품질 문제를 시각적으로 강조한다.
5. THE UI SHALL Silence_Leakage 구간(ref 묵음 구간 중 dif에 소리가 있는 구간)을 노란색 계열(alpha=0.25)로 표시한다.
6. THE UI SHALL ref와 dif의 스펙트로그램을 표시한다.
7. THE UI SHALL SNR, PESQ, STOI, RMS 차이, Clipping 비율, 배경 잡음 레벨, Silence_Leakage, False_Silence, 묵음 총 시간, 묵음 개수, 추정 지연량을 수치로 표시한다.
8. THE UI SHALL Spectral_Centroid와 Spectral_Rolloff의 시계열 그래프를 표시한다.
9. THE UI SHALL 모든 시각화 요소를 스크롤 가능한 결과 영역 내에 표시한다.
10. THE UI SHALL 가독성 확보를 위해 세부 색상값과 alpha는 UI 구현에서 소폭 조정할 수 있다.

---

### Requirement 11: 결과 저장

**User Story:** 개발자로서, 분석 결과를 다양한 형식으로 저장하고 싶습니다. 그래야 결과를 외부 도구에서 활용하거나 기록으로 보관할 수 있습니다.

#### Acceptance Criteria

1. THE UI SHALL 분석 결과를 JSON 파일로 저장할 수 있다. 저장 경로는 사용자가 선택한다.
2. THE UI SHALL 시각화 결과(파형, 스펙트로그램, 시계열 그래프)를 PNG 파일로 저장할 수 있다.
3. THE UI SHALL 주요 지표를 CSV 파일로 요약 저장할 수 있다. CSV는 한 행으로 표현 가능한 수치 지표를 포함한다.
4. THE Analyzer SHALL 저장용 결과 객체에 다음을 포함한다: 입력 파일 경로(ref/dif), 분석 시각(ISO 8601), Analysis_Config 전체, 주요 수치 지표(SNR/PESQ/STOI/RMS/Clipping/Silence_Leakage/False_Silence 등), ref 및 dif의 묵음 구간 목록(시작/종료/지속 시간), 지표별 상태값(success / N/A / failed) 및 실패 사유(optional)를 포함한다.

---

### Requirement 12: 오류 처리 및 부분 실패 허용

**User Story:** 개발자로서, 일부 지표 계산이 실패하더라도 나머지 분석 결과를 확인하고 싶습니다. 그래야 환경 제약으로 인한 부분 실패가 전체 분석을 중단시키지 않습니다.

#### Acceptance Criteria

1. THE Analyzer SHALL 파일 읽기 실패 시 명확한 오류 코드(예: ERR_FILE_NOT_FOUND, ERR_INVALID_FORMAT)를 반환한다.
2. THE UI SHALL 오류 메시지를 사용자에게 표시하고 애플리케이션을 종료하지 않는다.
3. THE Analyzer SHALL 일부 선택적 지표(PESQ, STOI, Spectral 분석 등) 계산 실패 시 가능한 나머지 분석 결과를 계속 반환한다.
4. THE UI SHALL 실패한 지표를 N/A로 표시하고 실패 사유를 로그 패널에 표시한다.
5. THE Analyzer SHALL 분석 안정성을 위해 동일한 입력과 동일한 Analysis_Config로 반복 실행 시 항상 동일한 결과를 반환한다(결정론적 처리). 난수 시드가 필요한 경우 고정 시드(seed=42)를 사용한다.
6. THE Analyzer SHALL 핵심 전처리 단계(파일 읽기, 포맷 정규화, 지연 보정, 프레임 분할)가 실패한 경우 전체 분석을 중단하고 오류를 반환한다.

---

### Requirement 13: 모듈 구조 및 코드 품질

**User Story:** 개발자로서, UI와 분석 로직이 명확히 분리되고 한글 주석이 포함된 코드를 원합니다. 그래야 유지보수와 기능 확장이 용이합니다.

#### Acceptance Criteria

1. THE UI SHALL main.py 파일 하나에만 구현되며, 분석 로직 코드를 포함하지 않는다.
2. THE Analyzer SHALL 다음 모듈 구조로 구현된다:
   - `main.py`: PyQt5 기반 UI 전담, Analyzer 호출만 수행
   - `analyzer.py`: 분석 파사드(facade) — 하위 모듈을 조합하여 전체 분석 흐름 제어
   - `audio_io.py`: 파일 로드, 포맷 정규화, 리샘플링
   - `delay.py`: Cross-correlation 및 DTW 기반 지연 보정
   - `vad.py`: 묵음 판별 앙상블 (log-energy, webrtcvad, ZCR)
   - `metrics.py`: SNR, PESQ, STOI, RMS, Clipping, 배경 잡음 레벨 계산
   - `spectrum.py`: Spectral_Centroid, Spectral_Rolloff, 피치, ZCR 시계열, 스펙트로그램
   - `silence_metrics.py`: Silence_Leakage, False_Silence, 묵음 구간 통계
3. THE Analyzer SHALL 모든 public 함수에 한글 docstring으로 함수의 목적, 입력 파라미터(이름, 타입, 설명), 반환값(타입, 설명)을 명시한다.
4. THE UI SHALL 주요 UI 이벤트 핸들러 및 public 메서드에 한글 주석 또는 docstring으로 목적, 입력, 반환값을 설명한다.
5. THE Analyzer SHALL 각 분석 함수가 단일 책임을 가지도록 기능별로 분리된 함수로 구현된다.
