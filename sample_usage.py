"""
audio_anomaly_detector 사용 예시 스크립트
========================================

이 스크립트는 audio_anomaly_detector.py의 detect_dif_only_events() 함수를
호출하는 방법을 보여줍니다.

■ 실행 방법
  python sample_usage.py

■ 필수 조건
  - audio_anomaly_detector.py 가 같은 디렉토리에 있어야 합니다.
  - pip install numpy scipy soundfile
  - sample_audio/ 디렉토리에 테스트용 WAV 파일이 있어야 합니다.
    (파일이 없으면 해당 Pair는 건너뜁니다)
"""

import os
from audio_anomaly_detector import detect_dif_only_events


def analyze_pair(ref_path: str, dif_path: str, description: str):
    """한 쌍의 WAV 파일을 분석하고 결과를 출력하는 예시 함수."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"  ref: {ref_path}")
    print(f"  dif: {dif_path}")
    print(f"{'='*60}")

    # 파일 존재 확인
    if not os.path.exists(ref_path) or not os.path.exists(dif_path):
        print("  ⚠ 파일이 없어 건너뜁니다.")
        return

    # ★ 핵심: 이 함수 하나만 호출하면 됩니다 ★
    events = detect_dif_only_events(ref_path, dif_path)

    # 결과 출력
    if not events:
        print("  ✓ 이상 없음 (dif-only 이벤트 0건)")
    else:
        print(f"  이벤트 {len(events)}건 검출:")
        for e in events:
            print(f"    #{e['index']} [{e['type']}] "
                  f"{e['duration_ms']:.0f}ms "
                  f"({e['start_s']:.3f}s ~ {e['end_s']:.3f}s) "
                  f"gain={e['gain_db']:.1f}dB")


if __name__ == "__main__":
    base = "sample_audio/"

    # Pair 1: 묵음 1회 (약 1초 후)
    analyze_pair(
        base + "B_iOS_ref.wav",
        base + "B_iOS_dif_1.wav",
        "Pair 1: 묵음 검출 테스트",
    )

    # Pair 2: 깨짐 1회 (약 2.5초 후)
    analyze_pair(
        base + "B_iOS_ref.wav",
        base + "B_iOS_dif_gain.wav",
        "Pair 2: 깨짐 검출 테스트",
    )

    # Pair 3: 정상 (이상 0건)
    analyze_pair(
        base + "A_dating_SPEAKER_00.wav",
        base + "A_Android_ixiO_20260327_172033.wav",
        "Pair 3: 정상 음원 테스트 (이상 0건 기대)",
    )

    # ─── 다른 프로젝트에서 import 하여 사용하는 예시 ───
    print(f"\n{'='*60}")
    print("  [코드 예시] 다른 프로젝트에서 import 하여 사용")
    print(f"{'='*60}")
    print("""
    from audio_anomaly_detector import detect_dif_only_events

    # 분석 실행
    events = detect_dif_only_events("ref.wav", "dif.wav")

    # 결과 활용
    if not events:
        print("정상")
    else:
        for e in events:
            if e["type"] == "묵음":
                print(f"묵음 발생: {e['start_s']}s ~ {e['end_s']}s")
            elif e["type"] == "깨짐":
                print(f"깨짐 발생: {e['start_s']}s ~ {e['end_s']}s")
    """)
