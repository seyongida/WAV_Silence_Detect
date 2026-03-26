# Product Overview

Audio Quality Analyzer는 두 WAV 파일(ref/dif)을 비교하여 오디오 품질을 분석하는 데스크톱 도구이다.

## 핵심 기능
- ref(기준)와 dif(비교) WAV 파일 간 지연 보정 후 품질 비교
- Cross-correlation + DTW 기반 지연 추정 및 자동 보정
- log-energy + WebRTC VAD + ZCR 앙상블 묵음 검출
- 음질 지표 계산: SNR, PESQ, STOI, RMS diff, Clipping, Noise Floor
- 스펙트럼 분석: Spectrogram, Spectral Centroid/Rolloff, Pitch, ZCR
- 묵음 지표: Silence Leakage, False Silence, dif-only Silence
- JSON / CSV / PNG 결과 내보내기
- PyQt5 기반 GUI (파일 선택, 파라미터 조정, 시각화, 결과 테이블)

## 주요 사용 시나리오
ref.wav(원본)와 dif.wav(전송/변환 후 음원)를 비교하여 전송 과정에서 발생한 품질 저하, 묵음 삽입, 지연 등을 정량적으로 분석한다.

## 언어
- 코드 주석 및 문서: 한글
- 변수명/함수명/모듈명: 영문
