# Changelog

## [1.3.0] - 2026-03-26

### GUI 레이아웃 개선 (2차)
- 상세 지표 테이블: 스크롤바 제거(`ScrollBarAlwaysOff`) + 행 수 기반 `setFixedHeight` 자동 계산으로 스크롤 없이 전체 표시
- 분석 파라미터: `QFormLayout` 단일 컬럼 → `QGridLayout` 2컬럼 배치로 변경하여 좌우 여백 최소화
- 파일 선택 패널: Pair 1 / Pair 2를 세로 나열에서 `QHBoxLayout` 가로 나란히 배치로 변경

## [1.2.0] - 2026-03-26

### GUI 레이아웃 개선
- 상세 지표 테이블의 고정 높이 제한(`maxHeight`) 제거 → 스크롤 없이 전체 지표를 한눈에 확인 가능
- 분석 파라미터 패널을 접기/펼치기(토글) 방식으로 변경 → 초기에는 숨김 처리하여 화면을 깔끔하게 유지
- 기존 파일 선택 + 파라미터 좌우 분할(`QSplitter`) 레이아웃을 세로 배치로 변경

### 차트 시간축 정렬
- Spectral Centroid / Rolloff 차트의 x축을 프레임 인덱스에서 시간(초) 단위로 변환
- 파형, 잔차, 스펙트로그램, 스펙트럼 트렌드 등 모든 시간축 차트의 x범위(`xlim`)를 `(0, max_time)`으로 통일하여 0초~끝 시간이 시각적으로 정렬되도록 개선

## [1.1.0] - 2026-03-26

### GUI 전면 리디자인
- 다크 테마 기반 현대적 UI로 전면 교체 (Fusion 스타일 + 커스텀 색상 팔레트)
- 카드 기반 레이아웃, 둥근 모서리, 통일된 색상 체계로 시인성 대폭 개선
- matplotlib 차트도 다크 테마 적용 (magma colormap 등)
- 한글 UI 라벨 적용 (버튼, 메뉴, 지표 해석 등)

### 듀얼 페어 비교 분석 기능 추가
- 음원 파일 4개(ref1/dif1, ref2/dif2) 입력 지원
- Pair 1, Pair 2를 한 번에 분석하고 결과를 좌우 나란히 비교 가능
- Pair 2는 선택 사항으로, 기존처럼 2개 파일만으로도 정상 동작
- `DualAnalysisWorker` 추가: 두 페어를 순차 분석하는 QThread 워커
- `ResultContainer`: 싱글/듀얼 모드 자동 전환 결과 컨테이너
- JSON/CSV/PNG 내보내기 시 듀얼 모드면 `_pair2` 접미사로 두 번째 결과 자동 저장

### 내부 구조 변경
- `FilePanel`: `FilePairWidget` 기반으로 재구성 (Pair 1 + Pair 2)
- `ResultPanel` → `SingleResultPanel`로 리네이밍 및 독립 패널화
- 통계 요약 카드 위젯(`_stat_widget`) 도입: 핵심 지표를 큰 숫자로 즉시 확인 가능
- 지표 테이블 해석 컬럼 한글화

## [1.0.0] - 초기 버전

- ref/dif WAV 파일 비교 분석 (단일 페어)
- Cross-correlation + DTW 지연 추정 및 자동 보정
- log-energy + WebRTC VAD + ZCR 앙상블 묵음 검출
- 음질 지표: SNR, PESQ, STOI, RMS diff, Clipping, Noise Floor
- 스펙트럼 분석: Spectrogram, Spectral Centroid/Rolloff, Pitch, ZCR
- 묵음 지표: Silence Leakage, False Silence, dif-only Silence
- JSON / CSV / PNG 결과 내보내기
- PyQt5 기반 GUI
