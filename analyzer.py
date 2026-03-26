"""Main analysis pipeline."""

from dataclasses import dataclass
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

import numpy as np

import audio_io
import delay as delay_mod
import metrics as metrics_mod
import silence_metrics as silence_mod
import spectrum as spectrum_mod
import vad as vad_mod
from models import (
    AnalysisConfig,
    AnalysisMessage,
    AnalysisResult,
    DelayResult,
    MetricStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisConfigV2(AnalysisConfig):
    """Extended config for difference highlight overlays."""

    residual_diff_threshold: float = 0.05
    centroid_diff_threshold_hz: float = 300.0
    rolloff_diff_threshold_hz: float = 500.0


def validate_config(config: AnalysisConfig) -> list[str]:
    errors = []
    if config.hop_ms > config.frame_ms:
        errors.append(f"hop_ms({config.hop_ms}) must be <= frame_ms({config.frame_ms}).")
    if not (0 <= config.noise_floor_percentile <= 100):
        errors.append(f"noise_floor_percentile({config.noise_floor_percentile}) must be in [0, 100].")
    if not (0 <= config.vad_aggressiveness <= 3):
        errors.append(f"vad_aggressiveness({config.vad_aggressiveness}) must be in [0, 3].")
    if config.min_silence_ms <= 0:
        errors.append(f"min_silence_ms({config.min_silence_ms}) must be > 0.")
    if config.silence_merge_ms < 0:
        errors.append(f"silence_merge_ms({config.silence_merge_ms}) must be >= 0.")
    residual_thr = float(getattr(config, "residual_diff_threshold", 0.05))
    centroid_thr = float(getattr(config, "centroid_diff_threshold_hz", 300.0))
    rolloff_thr = float(getattr(config, "rolloff_diff_threshold_hz", 500.0))
    if residual_thr <= 0:
        errors.append(f"residual_diff_threshold({residual_thr}) must be > 0.")
    if centroid_thr <= 0:
        errors.append(f"centroid_diff_threshold_hz({centroid_thr}) must be > 0.")
    if rolloff_thr <= 0:
        errors.append(f"rolloff_diff_threshold_hz({rolloff_thr}) must be > 0.")
    return errors


def run_analysis(
    ref_path: str,
    dif_path: str,
    config: AnalysisConfig,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> AnalysisResult:
    error_log: list[AnalysisMessage] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    def _progress(percent: int, text: str) -> None:
        if progress_callback:
            progress_callback(percent, text)

    def _warn(msg: str) -> None:
        error_log.append(
            AnalysisMessage(
                level="warn",
                message=msg,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )
        logger.warning(msg)

    def _metric_safe(fn, *args, **kwargs) -> MetricStatus:
        try:
            value = fn(*args, **kwargs)
            if value is None:
                return MetricStatus(value=None, status="N/A")
            return MetricStatus(value=float(value), status="success")
        except Exception as e:
            reason = str(e)
            _warn(f"{fn.__name__} failed: {reason}")
            return MetricStatus(value=None, status="failed", reason=reason)

    _progress(5, "Loading files")
    ref_audio = audio_io.load_wav(ref_path)
    dif_audio_raw = audio_io.load_wav(dif_path)

    _progress(10, "Normalizing format")
    dif_audio = audio_io.normalize_format(ref_audio, dif_audio_raw)

    ref_samples = ref_audio.samples
    dif_samples = dif_audio.samples
    sr = ref_audio.sample_rate

    ref_mono = ref_samples if ref_samples.ndim == 1 else ref_samples.mean(axis=1).astype(np.float32)
    dif_mono = dif_samples if dif_samples.ndim == 1 else dif_samples.mean(axis=1).astype(np.float32)

    _progress(20, "Estimating delay")
    coarse_delay_ms = delay_mod.estimate_delay_cc(ref_mono, dif_mono, sr)
    refined_delay_ms = delay_mod.refine_delay_dtw(ref_mono, dif_mono, sr, coarse_delay_ms)
    dif_aligned_coarse = delay_mod.apply_delay(dif_mono, coarse_delay_ms, sr)
    dif_aligned_refined = delay_mod.apply_delay(dif_mono, refined_delay_ms, sr)
    coarse_mae = _alignment_mae(ref_mono, dif_aligned_coarse, sr)
    refined_mae = _alignment_mae(ref_mono, dif_aligned_refined, sr)

    if refined_mae < coarse_mae:
        applied_delay_ms = refined_delay_ms
        dif_aligned = dif_aligned_refined
        dtw_used = True
    else:
        applied_delay_ms = coarse_delay_ms
        dif_aligned = dif_aligned_coarse
        dtw_used = False

    delay_result = DelayResult(
        coarse_delay_ms=coarse_delay_ms,
        refined_delay_ms=refined_delay_ms,
        applied_delay_ms=applied_delay_ms,
        dtw_used=dtw_used,
    )

    _progress(30, "Extracting common segment")
    ref_common, dif_common = metrics_mod.extract_common_segment(ref_mono, dif_aligned, sr)

    _progress(35, "Running VAD")
    ref_frames = vad_mod.compute_frames(ref_common, sr, config)
    dif_frames = vad_mod.compute_frames(dif_common, sr, config)
    ref_silence = vad_mod.detect_silence(ref_frames, sr, config)
    dif_silence = vad_mod.detect_silence(dif_frames, sr, config)

    _progress(45, "Computing silence metrics")
    silence_metrics, false_silence_segs, leakage_segs = silence_mod.compute_silence_metrics(
        ref_frames, dif_frames, ref_silence, dif_silence, sr, config
    )

    _progress(55, "Computing quality metrics")
    snr_db = _metric_safe(metrics_mod.compute_snr, ref_common, dif_common)
    pesq_score = _metric_safe(metrics_mod.compute_pesq, ref_common, dif_common, sr)
    stoi_score = _metric_safe(metrics_mod.compute_stoi, ref_common, dif_common, sr)
    rms_diff_db = _metric_safe(metrics_mod.compute_rms_diff, ref_common, dif_common)
    clipping_ratio = _metric_safe(metrics_mod.compute_clipping, dif_common)
    ref_noise_floor_db = _metric_safe(metrics_mod.compute_noise_floor, ref_common, sr, config)
    dif_noise_floor_db = _metric_safe(metrics_mod.compute_noise_floor, dif_common, sr, config)

    _progress(75, "Computing spectrum")
    spectrum = None
    try:
        spectrum = spectrum_mod.compute_all(ref_common, dif_common, sr, config)
    except Exception as e:
        _warn(f"spectrum analysis failed: {e}")

    _progress(95, "Building result")
    result = AnalysisResult(
        ref_path=ref_path,
        dif_path=dif_path,
        analysis_timestamp=timestamp,
        config=config,
        ref_audio=ref_audio,
        dif_audio=dif_audio,
        dif_aligned=dif_aligned,
        delay=delay_result,
        ref_silence_segments=ref_silence,
        dif_silence_segments=dif_silence,
        false_silence_segments=false_silence_segs,
        silence_leakage_segments=leakage_segs,
        silence_metrics=silence_metrics,
        snr_db=snr_db,
        pesq_score=pesq_score,
        stoi_score=stoi_score,
        rms_diff_db=rms_diff_db,
        clipping_ratio=clipping_ratio,
        ref_noise_floor_db=ref_noise_floor_db,
        dif_noise_floor_db=dif_noise_floor_db,
        spectrum=spectrum,
        error_log=error_log,
    )

    _progress(100, "Done")
    return result


def _alignment_mae(ref: np.ndarray, dif_aligned: np.ndarray, sr: int) -> float:
    ref_common, dif_common = metrics_mod.extract_common_segment(ref, dif_aligned, sr)
    if len(ref_common) == 0:
        return float("inf")
    return float(np.mean(np.abs(ref_common.astype(np.float64) - dif_common.astype(np.float64))))
