# Changelog

## [1.7.0] - 2026-03-31

### 잡음 소실(noise loss) 필터 추가
- dif가 디지털 제로(peak < 0.002)이고 ref가 미세 잡음(energy ≤ -30dB)인 구간을 dif-only 묵음에서 제외
- 전송 과정에서 미세 배경 잡음이 소실된 구간을 "새로 삽입된 묵음"이 아닌 "잡음 소실"로 간주
- `silence_metrics.py`에 `_filter_noise_loss()` 함수 추가
- `compute_silence_metrics()`에 `ref_audio` 파라미터 추가 (하위 호환: 기본값 None)
- `analyzer.py`에서 `ref_common` 신호를 `compute_silence_metrics`에 전달
- `models.py`의 `AnalysisConfig`에 `noise_loss_peak_threshold`(기본 0.002), `noise_loss_ref_energy_db`(기본 -30dB) 파라미터 추가
- GUI에 Noise loss peak, Noise loss ref (dB) 파라미터 위젯 추가
- 디버깅용 임시 스크립트 6개 정리 삭제

### 테스트
- `tests/test_silence_boundary_energy.py`에 잡음 소실 필터 테스트 6건 추가 (총 18건)
  - `_filter_noise_loss` 단위 테스트 5건 (dif 제로+ref 잡음 제거, dif 제로+ref 음성 유지, dif 비제로 유지, 혼합, 빈 입력)
  - 통합 테스트 1건 (`compute_silence_metrics`에서 잡음 소실 필터 적용 검증)

## [1.6.0] - 2026-03-31

### dif-only 묵음 경계 오탐 제거 (방안 B + C)
- 방안 B: ref 묵음 구간 양쪽 경계를 `silence_boundary_margin_ms`(기본 100ms)만큼 확장한 뒤 차집합 수행 → 묵음↔음성 전환부에 걸친 오탐 흡수
- 방안 C: 차집합 후 남은 dif-only 구간의 실제 에너지를 `dif_only_energy_threshold_db`(기본 -40dB) 절대 임계값으로 재검증 → 소리가 있는 구간 제거
- `silence_metrics.py`에 `_expand_segments()`, `_verify_energy()` 함수 추가
- `compute_silence_metrics()`에 `dif_audio` 파라미터 추가 (하위 호환: 기본값 None)
- `analyzer.py`에서 `dif_common` 신호를 `compute_silence_metrics`에 전달
- `models.py`의 `AnalysisConfig`에 `silence_boundary_margin_ms`, `dif_only_energy_threshold_db` 파라미터 추가
- GUI에 Boundary margin (ms), Energy thr (dB) 파라미터 위젯 추가

### 테스트
- `tests/test_silence_boundary_energy.py` 추가 (12건)
  - `_expand_segments` 단위 테스트 5건 (양쪽 확장, 경계 클램핑, 겹침 병합, margin=0, 빈 입력)
  - `_verify_energy` 단위 테스트 3건 (무음 통과, 유음 제거, 혼합)
  - 통합 테스트 3건 (경계 오탐 제거, 정상 dif-only 유지, 에너지 재검증 제거)
  - Hypothesis PBT 1건 (확장 구간 범위 불변 속성)

## [1.5.1] - 2026-03-31

### dif-only 묵음 검출 불일치 원인 분석
- Pair1(전체 음원)에서 dif-only 묵음 수 1로 검출되나, 해당 구간만 slice한 Pair2에서는 0으로 검출되는 현상 조사
- 원인 분석 결과 5가지 요인 식별:
  1. **지연 보정(delay) 차이**: slice 음원은 이미 정렬된 상태인데 cross-correlation + DTW가 다른 delay를 추정하여 정렬을 깨뜨릴 수 있음
  2. **Noise Floor 동적 임계값 변화**: 전체 음원 vs slice 구간의 에너지 분포 차이로 `noise_floor_percentile` 기반 threshold가 달라짐
  3. **`extract_common_segment` 길이 자르기**: delay 보정 후 공통 구간 범위가 달라져 묵음 구간이 분석 범위에서 제외될 수 있음
  4. **`min_silence_ms` (200ms) 경계 필터링**: 시간 축 미세 변화로 경계값 구간이 필터링됨
  5. **`silence_merge_ms` (50ms) 병합 차이**: slice 경계에서 병합 결과가 달라질 수 있음
- 코드 수정 없이 분석만 진행 (개선 방향 도출 완료, 추후 반영 예정)

## [1.5.0] - 2026-03-27

### HTML 리포트 내보내기 기능 추가
- 분석 결과 전체(요약 통계, 지표 테이블, 차트)를 self-contained HTML 파일로 저장하는 기능 추가
- 차트는 base64 PNG로 인라인 삽입되어 HTML 파일 하나만 공유하면 브라우저에서 모든 정보 확인 가능
- 다크 테마 CSS 적용, 반응형 레이아웃 지원
- 싱글/듀얼 모드 모두 지원 (듀얼 시 Pair 1 / Pair 2 좌우 배치)
- GUI에 "HTML 저장" 버튼 추가 (PNG 저장 옆)
- `export.py`에 `save_html()`, `_fig_to_base64()`, `_build_result_html()` 함수 추가

### 테스트
- `tests/test_export.py`에 HTML 내보내기 테스트 2건 추가
  - 싱글 결과 HTML 생성 및 필수 콘텐츠(지표, 차트 base64, 테이블) 포함 검증
  - 듀얼 결과 HTML 생성 시 Pair 1 / Pair 2 및 듀얼 레이아웃 포함 검증

## [1.4.2] - 2026-03-27

### 음량 정규화 잔차 차트 타이틀 개선
- `gain=0.5000` → `dif = 0.50× ref` 형태로 변경하여 직관적으로 "몇 배"인지 표시
- 소수점 둘째 자리에서 올림(ceil) 처리
- `×` 단위 표기 추가
- 예시: `Residual – Volume Normalized (dif = 0.50× ref, -6.02 dB)`

## [1.4.1] - 2026-03-27

### 음량 정규화 잔차 차트에 볼륨 차이(dB) 표기 추가
- 차트 타이틀에 ref 대비 dif의 볼륨 차이를 dB 단위로 표시 (예: `dif vol: -6.02 dB vs ref`)
- dif가 ref보다 크면 양수(+), 작으면 음수(-) 부호로 직관적 확인 가능
- 계산식: `20 * log10(dif_rms / ref_rms)`
- 양쪽 모두 무음이거나 dif가 무음인 경우 0.0 dB 폴백

### 테스트
- `tests/test_volume_normalized_residual.py` 확장 (8건 → 10건)
  - dB 부호 규칙 검증 테스트 추가 (`test_vol_diff_db_sign_convention`)
  - Hypothesis PBT: `vol_diff_db = 20*log10(scale)` 관계 검증 추가 (`test_vol_diff_db_matches_scale`)
  - 기존 테스트에 dB 값 정확도 assertion 추가

## [1.4.0] - 2026-03-27

### 음량 정규화 잔차(Volume-Normalized Residual) 차트 추가
- 기존 `Residual (ref - dif)` 차트 바로 아래에 음량 정규화 잔차 차트 신규 추가
- dif의 전체 RMS를 ref의 RMS에 맞추는 gain을 계산하여 dif를 스케일링한 뒤 `ref - dif_scaled`을 표시
- 볼륨 차이만 존재하는 두 신호의 경우 잔차가 0으로 표시되어, 순수 파형 차이만 시각적으로 확인 가능
- 차트 타이틀에 적용된 gain 값 표시 (예: `gain=2.0000`)
- 기존 잔차 차트와 동일한 threshold 하이라이트 적용
- Pair 1 / Pair 2 모두 동일하게 적용
- PNG 내보내기 시 새 차트 포함

### 테스트
- `tests/test_volume_normalized_residual.py` 추가 (8건)
  - 동일 신호, 볼륨만 다른 신호, 파형이 다른 신호, 무음 신호 등 케이스별 검증
  - Hypothesis PBT: 임의 양수 스케일 × 동일 파형 → 정규화 후 잔차 ≈ 0 속성 검증

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
