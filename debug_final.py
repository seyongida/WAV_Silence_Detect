"""에너지 드롭 검출 검증."""

import numpy as np
import audio_io, delay as delay_mod, metrics as metrics_mod
import vad as vad_mod, silence_metrics as silence_mod
from silence_metrics import _detect_digital_zero_segments
from models import AnalysisConfig

ref_path = "sample_audio/B_dating_SPEAKER_01.wav"

for label, dif_path in [
    ("cut (120ms 묵음 삽입)", "sample_audio/B_iOS_ixiO_20260327_172033_cut.wav"),
    ("원본 (묵음 없음)", "sample_audio/B_iOS_ixiO_20260327_172033.wav"),
]:
    ref_audio = audio_io.load_wav(ref_path)
    dif_audio_raw = audio_io.load_wav(dif_path)
    dif_audio = audio_io.normalize_format(ref_audio, dif_audio_raw)
    sr = ref_audio.sample_rate
    ref_mono = ref_audio.samples if ref_audio.samples.ndim == 1 else ref_audio.samples.mean(axis=1).astype(np.float32)
    dif_mono = dif_audio.samples if dif_audio.samples.ndim == 1 else dif_audio.samples.mean(axis=1).astype(np.float32)
    delay_ms = delay_mod.estimate_delay_cc(ref_mono, dif_mono, sr)
    dif_aligned = delay_mod.apply_delay(dif_mono, delay_ms, sr)
    ref_common, dif_common = metrics_mod.extract_common_segment(ref_mono, dif_aligned, sr)

    print(f"\n=== {label} ===")

    for min_sil in [200, 100]:
        config = AnalysisConfig(min_silence_ms=min_sil)
        rf = vad_mod.compute_frames(ref_common, sr, config)
        df = vad_mod.compute_frames(dif_common, sr, config)
        rs = vad_mod.detect_silence(rf, sr, config)
        ds = vad_mod.detect_silence(df, sr, config)
        m, do, _ = silence_mod.compute_silence_metrics(
            rf, df, rs, ds, sr, config, dif_audio=dif_common, ref_audio=ref_common,
        )
        print(f"  min_sil={min_sil}: dif-only={m.dif_silence_count} ({m.dif_total_silence_ms:.0f}ms)")
        for s in do:
            print(f"    [{s.start_ms:.0f}~{s.end_ms:.0f}] {s.duration_ms:.0f}ms")

    # 디지털 제로 검출만 단독 테스트
    config = AnalysisConfig(min_silence_ms=100)
    segs = _detect_digital_zero_segments(dif_common, ref_common, sr, config, 0.002, -30.0)
    print(f"  digital_zero 단독: {len(segs)}")
    for s in segs:
        print(f"    [{s.start_ms:.0f}~{s.end_ms:.0f}] {s.duration_ms:.0f}ms")
