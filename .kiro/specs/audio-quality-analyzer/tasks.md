# Implementation Plan: Audio Quality Analyzer

## Overview

Python 기반 데스크톱 애플리케이션을 모듈별로 순차 구현한다. 데이터 모델 → 분석 하위 모듈 → Facade → PyQt5 UI → 저장 기능 순으로 진행하며, 각 단계에서 이전 단계의 결과를 통합한다.

## Tasks

- [x] 1. 프로젝트 구조 및 데이터 모델 설정
  - Python 3.11+ 환경 확인 및 가상환경 생성: `python -m venv venv` → `source venv/bin/activate` (Linux/macOS) 또는 `venv\Scripts\activate` (Windows)
  - `requirements.txt` 파일에 의존성 목록을 작성한다 (pytest, hypothesis, numpy, scipy, soundfile, librosa, webrtcvad, pesq, pystoi, PyQt5, matplotlib)
    - `pesq` 패키지명은 PyPI 기준 `pesq`로 확정한다 (설치: `pip install pesq`)
    - WAV 파일 로딩은 `soundfile` 라이브러리를 사용한다 (`soundfile.read()`)
  - 의존성 설치: `pip install -r requirements.txt`
  - 실행 명령 예시: `python main.py`
  - `errors.py` 파일을 생성하고 오류 코드 및 예외 클래스를 정의한다
    - `AudioAnalyzerError(code: str, message: str)` — code와 message를 속성으로 갖는 기본 예외 클래스
    - `ERR_FILE_NOT_FOUND`, `ERR_INVALID_FORMAT`, `ERR_TOO_SHORT`, `ERR_DELAY_FAILED` 오류 코드 상수 정의
    - 모든 모듈에서 예외 발생 시 `raise AudioAnalyzerError(ERR_*, "설명")` 형태로 통일한다
  - `models.py`에 `AnalysisConfig`, `AudioData`, `Frame`, `SilenceSegment`, `DelayResult`, `SilenceMetrics`, `SpectrogramData`, `SpectrumData`, `MetricStatus`, `AnalysisResult`, `AnalysisMessage` 데이터클래스를 정의한다 (기존 파일이 있는 경우 덮어쓴다)
    - 파일명 `dataclasses.py`는 파이썬 표준 라이브러리와 충돌하므로 사용하지 않는다
  - 빈 모듈 파일 생성: `main.py`, `analyzer.py`, `audio_io.py`, `delay.py`, `vad.py`, `metrics.py`, `spectrum.py`, `silence_metrics.py`, `export.py`
  - _Requirements: 13.2_

- [x] 2. `audio_io.py` — 파일 I/O 및 포맷 정규화 구현
  - [x] 2.1 `load_wav()` 구현
    - WAV 파일을 float32 정규화(-1.0~1.0)된 `AudioData`로 로드
    - 파일 없음 → `ERR_FILE_NOT_FOUND`, 잘못된 포맷 → `ERR_INVALID_FORMAT`, 1초 미만 → `ERR_TOO_SHORT` 오류 처리
    - 한글 docstring 작성
    - _Requirements: 1.2, 1.3, 3.2, 3.4, 12.1, 13.3_

  - [x] 2.2 Property 4 테스트 작성: 정규화된 샘플 범위
    - **Property 4: 정규화된 샘플 범위**
    - **Validates: Requirements 3.2**
    - `hypothesis`로 임의 정수 PCM 값 생성, `load_wav()` 반환값의 모든 샘플이 [-1.0, 1.0] 범위인지 검증

  - [x] 2.3 Property 5 테스트 작성: 잘못된 파일 형식 오류 반환
    - **Property 5: 잘못된 파일 형식 오류 반환**
    - **Validates: Requirements 3.4**
    - 임의 바이트 시퀀스로 생성한 파일에 대해 `load_wav()`가 오류를 반환하는지 검증

  - [x] 2.4 `resample()` 구현
    - 지정 샘플레이트로 리샘플링한 새 `AudioData` 반환, 원본 불변
    - 한글 docstring 작성
    - _Requirements: 1.2, 3.1, 13.3_

  - [x] 2.5 `normalize_format()` 구현
    - dif를 ref의 샘플레이트/채널 수로 변환한 새 `AudioData` 반환, 원본 불변
    - 한글 docstring 작성
    - _Requirements: 3.1, 3.3, 13.3_

  - [x] 2.6 Property 1 테스트 작성: 리샘플링 원본 불변
    - **Property 1: 리샘플링 원본 불변**
    - **Validates: Requirements 1.2, 3.3**
    - 임의 float32 배열과 임의 목표 SR로 `resample()` / `normalize_format()` 호출 후 원본 배열 불변 검증

  - [x] 2.7 Property 3 테스트 작성: 포맷 정규화 후 샘플레이트/채널 일치
    - **Property 3: 포맷 정규화 후 샘플레이트/채널 일치**
    - **Validates: Requirements 3.1**
    - 임의 SR/채널 조합으로 `normalize_format()` 호출 후 반환된 dif의 SR과 채널이 ref와 동일한지 검증

- [x] 3. `delay.py` — 지연 보정 구현
  - [x] 3.1 `estimate_delay_cc()` 구현
    - Cross-correlation 기반 전체 지연량(ms) 추정
    - 한글 docstring 작성
    - _Requirements: 4.1, 13.3_

  - [x] 3.2 Property 6 테스트 작성: 지연 추정 정확도 (라운드 트립)
    - **Property 6: 지연 추정 정확도 (라운드 트립)**
    - **Validates: Requirements 4.1, 4.4**
    - 임의 신호와 알려진 지연량 d(ms)로 `estimate_delay_cc()` 추정값이 d ± 10ms 이내인지 검증 (허용 오차: 고정 10ms)

  - [x] 3.3 `refine_delay_dtw()` 구현
    - coarse_delay_ms 기준 ±500ms 윈도우 내 DTW 세부 보정량 추정
    - 비선형 워핑 미적용, 지연량 추정에만 사용
    - 한글 docstring 작성
    - _Requirements: 4.2, 13.3_

  - [x] 3.4 `apply_delay()` 구현
    - 단일 시간축 shift로 정렬된 dif 신호 반환
    - 한글 docstring 작성
    - _Requirements: 4.3, 13.3_

- [x] 4. `vad.py` — 묵음 판별 구현
  - [x] 4.1 `compute_frames()` 구현
    - `AnalysisConfig`의 `frame_ms`/`hop_ms` 기준으로 `Frame` 목록 반환
    - 각 Frame에 시작/종료 시간(ms) 인덱스 포함
    - 한글 docstring 작성
    - _Requirements: 5.1, 5.2, 5.3, 13.3_

  - [x] 4.2 Property 7 테스트 작성: 프레임 분할 커버리지
    - **Property 7: 프레임 분할 커버리지**
    - **Validates: Requirements 5.1, 5.2, 5.3**
    - 임의 길이 신호와 임의 config로 `compute_frames()` 반환 목록이 전체 구간을 커버하고 각 프레임 길이가 `frame_ms`와 일치하는지 검증

  - [x] 4.3 `_compute_log_energy()`, `_compute_zcr()` 구현
    - 프레임별 log-energy 및 ZCR 계산
    - _Requirements: 6.1, 6.5, 13.5_

  - [x] 4.4 `_run_webrtcvad()` 구현
    - webrtcvad로 각 Frame의 VAD 결과 목록 반환
    - 지원 범위 외 SR은 16kHz로 내부 리샘플링 후 원본 시간축 재매핑
    - _Requirements: 6.4, 13.5_

  - [x] 4.5 `detect_silence()` 구현
    - log-energy, webrtcvad, ZCR 앙상블로 묵음 구간 목록 반환
    - 앙상블 조건: `(energy_silence AND vad_silence) OR (energy_silence AND ZCR ≤ threshold)`
    - `min_silence_ms` 미만 구간 제외, `silence_merge_ms` 미만 간격 병합
    - 각 Frame의 `log_energy`, `zcr`, `vad_speech`, `energy_silence`, `final_silence` 필드 채움
    - 한글 docstring 작성
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 13.3_

  - [x] 4.6 Property 8 테스트 작성: 최소 묵음 지속 시간 준수
    - **Property 8: 최소 묵음 지속 시간 준수**
    - **Validates: Requirements 6.7**
    - 의도된 묵음/비묵음 패턴을 가진 합성 오디오에서 `compute_frames()`로 생성된 Frame 목록으로 `detect_silence()` 반환 모든 `SilenceSegment.duration_ms ≥ config.min_silence_ms` 검증

  - [x] 4.7 Property 9 테스트 작성: 묵음 구간 병합
    - **Property 9: 묵음 구간 병합**
    - **Validates: Requirements 6.8**
    - 인접 묵음 구간을 가진 합성 오디오에서 `compute_frames()`로 생성된 Frame 목록으로 반환된 인접 두 `SilenceSegment` 간격이 `silence_merge_ms` 이상인지 검증

- [x] 5. Checkpoint — 핵심 분석 모듈 검증
  - 모든 테스트가 통과하는지 확인한다. 테스트 실패 항목을 정리하고 다음 작업 전에 해결한다.

- [x] 6. `metrics.py` — 음질 지표 계산 구현
  - [x] 6.1 `extract_common_segment()` 구현
    - 지연 보정 후 시간적으로 겹치는 공통 구간 추출
    - 한글 docstring 작성
    - _Requirements: 8.1, 13.3_

  - [x] 6.2 `compute_snr()` 구현
    - `SNR = 10 * log10(sum(ref^2) / sum((ref - dif)^2))` 계산
    - 한글 docstring 작성
    - _Requirements: 8.1, 13.3_

  - [x] 6.3 Property 11 테스트 작성: SNR 동일 신호 상한
    - **Property 11: SNR 동일 신호 상한**
    - **Validates: Requirements 8.1**
    - `ref_common == dif_common` 케이스에서 `compute_snr(ref_common, dif_common)` 반환값이 100 dB 초과인지 검증

  - [x] 6.4 `compute_pesq()` 구현
    - ITU-T P.862 기반 MOS-LQO 점수 계산, 48kHz → 16kHz 내부 리샘플링
    - 실패 시 `None` 반환, 실패 사유 로그 기록
    - 한글 docstring 작성
    - _Requirements: 8.2, 12.3, 13.3_

  - [x] 6.5 Property 12 테스트 작성: PESQ 점수 범위
    - **Property 12: PESQ 점수 범위**
    - **Validates: Requirements 8.2**
    - 유효한 8/16kHz 신호 쌍으로 `compute_pesq()` 반환값이 None이 아닐 때 [1.0, 4.5] 범위인지 검증

  - [x] 6.6 `compute_stoi()` 구현
    - STOI 음성 명료도 지수 계산, 실패 시 `None` 반환
    - 한글 docstring 작성
    - _Requirements: 8.3, 12.3, 13.3_

  - [x] 6.7 Property 13 테스트 작성: STOI 점수 범위
    - **Property 13: STOI 점수 범위**
    - **Validates: Requirements 8.3**
    - 유효한 신호 쌍으로 `compute_stoi()` 반환값이 None이 아닐 때 [0.0, 1.0] 범위인지 검증

  - [x] 6.8 `compute_rms_diff()` 구현
    - ref/dif 공통 구간 RMS 에너지 차이(dB) 계산
    - 한글 docstring 작성
    - _Requirements: 8.4, 13.3_

  - [x] 6.9 `compute_clipping()` 구현
    - dif 신호에서 진폭 ±1.0의 99.9% 이상인 샘플 비율 계산 (실제 음원 오탐 방지를 위해 99.9% 기준 적용)
    - 한글 docstring 작성
    - _Requirements: 8.5, 13.3_

  - [x] 6.10 Property 14 테스트 작성: Clipping 비율 계산 정확도
    - **Property 14: Clipping 비율 계산 정확도**
    - **Validates: Requirements 8.5**
    - 알려진 클리핑 샘플 수(진폭 ≥ 0.999)를 가진 신호로 `compute_clipping()` 반환값이 `(클리핑 샘플 수 / 전체 샘플 수)`와 일치하는지 검증

  - [x] 6.11 `compute_noise_floor()` 구현
    - 프레임별 log-energy 하위 percentile 기반 배경 잡음 레벨(dB) 추정
    - 한글 docstring 작성
    - _Requirements: 8.6, 13.3_

- [x] 7. `silence_metrics.py` — 묵음 지표 계산 구현
  - [x] 7.1 `compute_silence_metrics()` 구현
    - Frame 단위로 ref/dif 묵음 상태 비교
    - `Silence_Leakage`: ref 묵음 중 dif Non-Silence 비율
    - `False_Silence`: ref Non-Silence 중 dif 묵음 비율
    - dif 묵음 구간 총 개수, 총 시간(ms) 계산
    - `false_silence_segments`, `silence_leakage_segments` 구간 목록 반환 (UI 오버레이용)
    - 프레임 경계 기준 ±1 Hop 오차 허용
    - 한글 docstring 작성
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 13.3_

  - [x] 7.2 Property 10 테스트 작성: 묵음 비율 범위
    - **Property 10: 묵음 비율 범위**
    - **Validates: Requirements 7.4, 7.5**
    - ref/dif의 silence/non-silence 패턴이 알려진 Frame 목록과 대응 구간 목록으로 `compute_silence_metrics()` 반환 `silence_leakage`와 `false_silence`가 [0.0, 1.0] 범위인지 검증

- [x] 8. `spectrum.py` — 스펙트럼 분석 구현
  - [x] 8.1 `compute_spectral_centroid()`, `compute_spectral_rolloff()`, `compute_zcr()` 구현
    - 프레임별 Spectral Centroid, Rolloff, ZCR 시계열 반환
    - 한글 docstring 작성
    - _Requirements: 9.1, 9.2, 9.4, 13.3_

  - [x] 8.2 `compute_pitch()` 구현
    - 프레임별 피치(Hz) 반환, 미검출 프레임은 NaN
    - 한글 docstring 작성
    - _Requirements: 9.3, 13.3_

  - [x] 8.3 `compute_spectrogram()` 구현
    - 스펙트로그램 데이터(주파수×시간 행렬, 주파수 축, 시간 축) 반환
    - 한글 docstring 작성
    - _Requirements: 9.5, 13.3_

  - [x] 8.4 `compute_all()` 구현
    - ref와 dif_aligned에 대한 전체 스펙트럼 분석 수행, `SpectrumData` 반환
    - `mean_pitch_diff_hz`는 ref/dif 모두 유효한 피치가 검출된 프레임만 기준으로 계산
    - 내부 예외 발생 시 호출자(run_analysis)로 전파한다
    - 한글 docstring 작성
    - _Requirements: 9.3, 13.3_

  - [x] 8.5 Property 15 테스트 작성: 피치 차이 유효 프레임 한정
    - **Property 15: 피치 차이 유효 프레임 한정**
    - **Validates: Requirements 9.3**
    - 임의 피치 패턴 신호로 `SpectrumData.mean_pitch_diff_hz`가 NaN이 아닌 프레임만 기준으로 계산되는지 검증

- [x] 9. `analyzer.py` — Facade 구현
  - [x] 9.1 `validate_config()` 구현
    - `hop_ms ≤ frame_ms`, `noise_floor_percentile` 0~100, `vad_aggressiveness` 0~3, `min_silence_ms > 0`, `silence_merge_ms ≥ 0` 검증
    - 오류 메시지 목록 반환 (빈 목록이면 유효)
    - 한글 docstring 작성
    - _Requirements: 5.7, 13.3_

  - [x] 9.2 Property 19 테스트 작성: Config 검증 오류 감지
    - **Property 19: Config 검증 오류 감지**
    - **Validates: AnalysisConfig validation constraints**
    - 범위 위반 `AnalysisConfig`로 `validate_config()` 반환값이 비어 있지 않은지 검증

  - [x] 9.3 Property 20 테스트 작성: 유효한 Config 검증 통과
    - **Property 20: 유효한 Config 검증 통과**
    - **Validates: AnalysisConfig validation constraints**
    - 유효 범위 내 `AnalysisConfig`로 `validate_config()` 반환값이 빈 목록인지 검증

  - [x] 9.4 `run_analysis()` 구현
    - 설계 문서의 분석 파이프라인 순서(1~17단계)대로 하위 모듈 호출
    - `progress_callback`으로 진행률(percent, status_text) 전달
    - 핵심 단계 실패 시 전체 중단, 선택적 단계 실패 시 `MetricStatus(value=None, status="N/A")` 처리
    - 선택적 지표 함수의 반환값과 예외를 `MetricStatus`로 변환한다
    - `spectrum.compute_all()` 예외 발생 시 `spectrum=None` 처리 및 `AnalysisMessage(level='warn')` 기록
    - compute_silence_metrics() 반환값으로부터 `silence_metrics`, `false_silence_segments`, `silence_leakage_segments`를 `AnalysisResult`에 반영
    - `AnalysisResult` 반환 (모든 필수 필드 포함)
    - 결정론적 처리: 난수 시드 필요 시 `seed=42` 고정
    - 한글 docstring 작성
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.x, 6.x, 7.x, 8.x, 9.x, 12.3, 12.5, 12.6, 13.3_

  - [x] 9.5 Property 16 테스트 작성: 결과 객체 필수 필드 포함
    - **Property 16: 결과 객체 필수 필드 포함**
    - **Validates: Requirements 11.4, 4.4**
    - 임의 유효 입력 쌍으로 `run_analysis()` 반환 `AnalysisResult`에 필수 필드가 모두 포함되는지 검증

  - [x] 9.6 Property 17 테스트 작성: 분석 결정론성
    - **Property 17: 분석 결정론성**
    - **Validates: Requirements 12.5**
    - 동일 입력과 동일 `AnalysisConfig`로 `run_analysis()` 두 번 실행 결과가 모든 수치 지표에서 동일한지 검증

  - [x] 9.7 Property 18 테스트 작성: 핵심 단계 실패 시 전체 중단
    - **Property 18: 핵심 단계 실패 시 전체 중단**
    - **Validates: Requirements 12.6**
    - 손상된 파일 입력으로 `run_analysis()`가 부분 결과 없이 오류를 반환하는지 검증

  - [x] 9.8 Property 2 테스트 완성: 짧은 파일 오류 반환
    - **Property 2: 짧은 파일 오류 반환**
    - **Validates: Requirements 1.3**
    - 0~0.99초 합성 WAV로 `run_analysis()` 오류 반환 검증

- [x] 10. Checkpoint — 전체 분석 파이프라인 검증
  - 모든 테스트가 통과하는지 확인한다. 테스트 실패 항목을 정리하고 다음 작업 전에 해결한다.

- [x] 11. `export.py` — 결과 저장 구현
  - [x] 11.1 `save_json()` 구현
    - `AnalysisResult`를 JSON 파일로 저장 (입력 파일 경로, 분석 시각, `AnalysisConfig`, 주요 지표, 묵음 구간 정보(dif/ref silence, false_silence_segments, silence_leakage_segments) 포함)
    - 한글 docstring 작성
    - _Requirements: 11.1, 11.4, 13.3_

  - [x] 11.2 `save_csv()` 구현
    - 주요 지표 요약을 CSV 한 행으로 저장 (SNR, PESQ, STOI, RMS 차이, Clipping 비율, 묵음 통계)
    - 한글 docstring 작성
    - _Requirements: 11.3, 13.3_

  - [x] 11.3 `save_png()` 구현
    - matplotlib Figure 목록을 PNG 파일로 저장 (복수 Figure는 번호 접미사 적용)
    - 한글 docstring 작성
    - _Requirements: 11.2, 13.3_

  - [x] 11.4 export 검증: JSON 필수 필드 존재 확인
    - `save_json()` 저장 후 파일을 다시 읽어 `ref_path`, `dif_path`, `analysis_timestamp`, `config`, `snr_db`, `silence_metrics` 필수 필드가 존재하는지 검증

  - [x] 11.5 export 검증: CSV 헤더 및 데이터 행 존재 확인
    - `save_csv()` 저장 후 파일을 다시 읽어 헤더 행과 최소 1개의 데이터 행이 존재하는지 검증

  - [x] 11.6 export 검증: PNG 파일 생성 확인
    - `save_png()` 저장 후 지정 경로에 PNG 파일이 실제로 생성되었는지 검증

- [x] 12. `main.py` — PyQt5 UI 구현
  - [x] 12.1 `FilePanel` 구현
    - ref/dif 파일 선택 컨트롤 및 파일 정보 표시
    - 지원 파일 형식, 샘플레이트, 채널, 권장/최소 길이 GUI 내 명시
    - _Requirements: 1.1, 2.1, 13.1, 13.4_

  - [x] 12.2 `ParamPanel` 구현
    - `AnalysisConfig` 파라미터 입력 패널 (8개 파라미터, 기본값 포함)
    - 유효 범위 검증 (`validate_config()` 호출), 유효하지 않으면 분석 시작 불가
    - _Requirements: 5.4, 5.5, 5.7, 13.4_

  - [x] 12.3 `AnalysisWorker` (QThread) 구현
    - 백그라운드에서 `analyzer.run_analysis()` 호출
    - `progress(int, str)`, `finished(object)`, `error(str)` 시그널 정의
    - _Requirements: 2.2, 2.4, 13.4_

  - [x] 12.4 `LogPanel` 구현
    - `AnalysisMessage` 목록을 level별 색상으로 표시 (info: 기본, warn: 주황, error: 빨강)
    - `append_message()`, `clear()` 메서드 구현
    - _Requirements: 12.2, 12.4, 13.4_

  - [x] 12.5 `ResultPanel` 구현
    - `update_result(result: AnalysisResult)` 메서드를 구현하여 분석 결과를 UI에 반영한다
    - 파형(시간-진폭) ref/dif 동일 시간 축 표시
    - dif Silence 오버레이 항상 표시 (주황색, alpha=0.25), ref Silence 체크박스로 토글 (기본 숨김, 파란색, alpha=0.2)
    - False_Silence 구간 빨간색(alpha=0.3) 오버레이: `AnalysisResult.false_silence_segments` 사용
    - Silence_Leakage 구간 노란색(alpha=0.25) 오버레이: `AnalysisResult.silence_leakage_segments` 사용
    - 스펙트로그램, Spectral_Centroid/Rolloff 시계열 그래프 표시
    - SNR, PESQ, STOI, RMS 차이, Clipping 비율, 배경 잡음 레벨, Silence_Leakage, False_Silence, 묵음 총 시간, 묵음 개수, 추정 지연량 수치 표시
    - spectrum is None인 경우 스펙트럼/시계열 영역에 "분석 불가" 메시지를 표시한다
    - `DelayResult` 수치 표시 영역 포함
    - 스크롤 가능한 결과 영역
    - _Requirements: 4.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 13.4_

  - [x] 12.6 `MainWindow` 구현 및 전체 UI 통합
    - `FilePanel`, `ParamPanel`, `ResultPanel`, `LogPanel` 통합
    - '품질 측정' 버튼: 파일 미선택 시 안내 메시지, 분석 중 비활성화
    - 10분 초과 파일 경고 메시지 표시 (분석은 계속 진행)
    - 분석 중 프로그레스 바 및 단계별 상태 텍스트 표시
    - 핵심 단계 오류 시 모달 다이얼로그, 선택적 지표 실패 시 LogPanel에 N/A 표시
    - `AnalysisWorker.finished` 시그널 수신 시 `MainWindow`가 `AnalysisResult.error_log`를 `LogPanel`에 반영하고 `ResultPanel.update_result()`를 호출한다
    - JSON/PNG/CSV 저장 버튼 및 파일 경로 선택 다이얼로그 연결
    - _Requirements: 1.4, 2.2, 2.3, 2.4, 2.5, 11.1, 11.2, 11.3, 12.2, 12.4, 13.1, 13.4_

- [x] 13. Final Checkpoint — 전체 통합 검증
  - 모든 테스트가 통과하는지 확인한다. 테스트 실패 항목을 정리하고 다음 작업 전에 해결한다.

## Notes

- `*` 표시 서브태스크는 선택적 테스트 태스크로, MVP 구현 시 건너뛸 수 있다
- 각 태스크는 이전 태스크의 결과를 기반으로 하며, 고아 코드가 없도록 단계별로 통합한다
- 속성 기반 테스트는 `hypothesis` 라이브러리를 사용하며 각 테스트당 최소 100회 실행한다
- 모든 public 함수에 한글 docstring을 작성한다
- 결정론적 처리가 필요한 경우 `seed=42`를 사용한다
