# WAV Silence Detect

`ref`와 `dif` WAV를 비교해서 지연 보정, 묵음 차이, 품질 지표, 스펙트럼 차이를 분석하는 데스크톱 툴입니다.  
현재 권장 실행 엔트리포인트는 `main.py`입니다.

## 1. 현재 샘플 오디오 구성

샘플 파일은 `sample_audio/`에 있습니다.

- `sample_audio/ref.wav`
- `sample_audio/dif_2+shift.wav` (기존 `dif.wav`에서 이름 변경)
- `sample_audio/dif_shift.wav`
- `sample_audio/dif_3.wav`
- `sample_audio/sample.wav`

기본 비교 시나리오는 `ref.wav` vs `dif_2+shift.wav`입니다.

## 2. 핵심 기능 (전체)

- WAV 로드/검증 (`audio_io.py`)
  - 파일 존재, 형식 검증
  - 길이(1초 이상) 검증
  - 샘플 정규화
- 포맷 정렬 (`audio_io.py`)
  - ref 기준 sample rate/channel 정규화
- 지연 추정/보정 (`delay.py`, `analyzer.py`)
  - Cross-correlation coarse delay
  - DTW refine 후보 계산
  - v2 가드레일: coarse/refined 중 실제 정렬 오차(MAE)가 더 좋은 값 자동 선택
- 묵음 검출 (`vad.py`)
  - frame/hop 분할
  - log-energy + WebRTC VAD + ZCR 결합
  - 최소 묵음 길이 필터, 묵음 병합
- 묵음 차이 지표 (`silence_metrics.py`)
  - silence leakage
  - false silence
  - dif-only silence count/total (ref와 겹치는 묵음 제외)
- 품질 지표 (`metrics.py`)
  - SNR, PESQ(옵션), STOI, RMS diff, clipping, noise floor
- 스펙트럼 분석 (`spectrum.py`)
  - spectrogram, spectral centroid, spectral rolloff, pitch, ZCR
- 결과 내보내기 (`export.py`)
  - JSON / CSV / PNG 저장

## 3. UI 기능 (`main.py`)

- 그래프 텍스트 영문화
- Waveform 오버레이
  - dif silence
  - ref silence (표시/비표시 토글)
  - false silence
  - silence leakage
- Spectrogram 배치
  - ref(위), dif delay-corrected(아래)
- Residual waveform (`ref - dif`) 그래프
- 차이 하이라이트(음영)
  - residual
  - spectral centroid
  - spectral rolloff
- 지표 요약 라벨 + 지표 해설 테이블
  - 값, 참고 범위, 해석 가이드 제공

## 4. 분석 파라미터

기본 파라미터:

- `frame_ms`
- `hop_ms`
- `noise_floor_percentile`
- `energy_margin_db`
- `vad_aggressiveness`
- `zcr_threshold`
- `min_silence_ms`
- `silence_merge_ms`

v2 추가 파라미터:

- `residual_diff_threshold` (default `0.05`)
- `centroid_diff_threshold_hz` (default `300.0`)
- `rolloff_diff_threshold_hz` (default `500.0`)

임계값을 올리면 하이라이트 구간은 줄어들고, 내리면 더 많이 표시됩니다.

## 5. 실행 방법

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
venv\Scripts\python main.py
```

## 6. 테스트

```powershell
venv\Scripts\python -m pytest -q
```

참고:

- `sample_audio/ref.wav`, `sample_audio/dif_2+shift.wav`가 없으면 일부 회귀 테스트는 `skip`됩니다.

## 7. 파일/모듈 맵

- `main.py`: UI 엔트리포인트
- `analyzer.py`: 분석 파이프라인 (지연 보정 가드레일 포함)
- `silence_metrics.py`: dif-only silence 계산
- `main.py`, `analyzer.py`, `silence_metrics.py`: 레거시 경로
- `audio_io.py`, `delay.py`, `vad.py`, `metrics.py`, `spectrum.py`, `export.py`, `models.py`, `errors.py`: 공통 코어 모듈
- `tests/`: 활성 테스트
- `unused_scripts/`: 미사용/레거시 스크립트 보관 (git ignore)

## 8. 출력 데이터 해석 포인트

- `Delay`: 적용된 최종 지연(ms)
- `SNR`: 높을수록 ref와 유사
- `STOI`: 높을수록 명료도 유사
- `RMS diff`: 0 dB에 가까울수록 레벨 유사
- `Clipping ratio`: 0에 가까울수록 좋음
- `Noise floor`: 더 낮은(dB 음수 큼) 값이 더 조용한 배경
- `Silence leakage`: ref 묵음이 dif에서 깨진 비율
- `False silence`: ref 비묵음이 dif에서 묵음으로 판정된 비율
- `dif-only silence`: ref와 겹치지 않는 dif 추가 묵음 이벤트/총시간

## 9. 주의사항

- `PESQ`는 로컬 빌드 환경에 따라 `N/A`가 될 수 있습니다.
- 삽입/삭제 편집이 큰 파일은 DTW refine이 불안정할 수 있어 v2에서 자동 fallback(coarse) 로직을 사용합니다.
