"""Silence metrics computed by segment-set operations."""

import numpy as np

from models import AnalysisConfig, Frame, SilenceMetrics, SilenceSegment


def compute_silence_metrics(
    ref_frames: list[Frame],
    dif_frames: list[Frame],
    ref_silence: list[SilenceSegment],
    dif_silence: list[SilenceSegment],
    sr: int,
    config: AnalysisConfig,
) -> tuple[SilenceMetrics, list[SilenceSegment], list[SilenceSegment]]:
    del sr, dif_frames

    if not ref_frames:
        metrics = SilenceMetrics(
            silence_leakage=0.0,
            false_silence=0.0,
            dif_silence_count=0,
            dif_total_silence_ms=0.0,
        )
        return metrics, [], []

    total_ref_duration_ms = float(ref_frames[-1].end_ms)
    total_ref_silence_ms = float(sum(s.duration_ms for s in ref_silence))
    ref_non_silence_ms = max(total_ref_duration_ms - total_ref_silence_ms, 1e-6)

    # dif-only silence: compare silence not present in reference silence
    dif_only_silence = _difference_segments(
        base=dif_silence,
        subtract=ref_silence,
        merge_ms=float(config.silence_merge_ms),
        min_ms=float(config.min_silence_ms),
    )

    # leakage: reference silence not preserved as silence in compare
    leakage_segs = _difference_segments(
        base=ref_silence,
        subtract=dif_silence,
        merge_ms=float(config.silence_merge_ms),
        min_ms=float(config.min_silence_ms),
    )

    dif_only_total_ms = float(sum(s.duration_ms for s in dif_only_silence))
    leakage_total_ms = float(sum(s.duration_ms for s in leakage_segs))

    silence_leakage = leakage_total_ms / total_ref_silence_ms if total_ref_silence_ms > 0 else 0.0
    false_silence = dif_only_total_ms / ref_non_silence_ms

    metrics = SilenceMetrics(
        silence_leakage=float(np.clip(silence_leakage, 0.0, 1.0)),
        false_silence=float(np.clip(false_silence, 0.0, 1.0)),
        dif_silence_count=len(dif_only_silence),
        dif_total_silence_ms=dif_only_total_ms,
    )
    return metrics, dif_only_silence, leakage_segs


def _merge_then_filter(
    segments: list[SilenceSegment],
    merge_ms: float,
    min_ms: float,
) -> list[SilenceSegment]:
    if not segments:
        return []

    segs = sorted(segments, key=lambda s: s.start_ms)
    merged: list[SilenceSegment] = [segs[0]]
    for seg in segs[1:]:
        prev = merged[-1]
        gap = seg.start_ms - prev.end_ms
        if gap < merge_ms:
            new_end = max(prev.end_ms, seg.end_ms)
            merged[-1] = SilenceSegment(
                start_ms=prev.start_ms,
                end_ms=new_end,
                duration_ms=new_end - prev.start_ms,
            )
        else:
            merged.append(seg)

    return [s for s in merged if s.duration_ms >= min_ms]


def _difference_segments(
    base: list[SilenceSegment],
    subtract: list[SilenceSegment],
    merge_ms: float,
    min_ms: float,
) -> list[SilenceSegment]:
    if not base:
        return []

    pieces: list[SilenceSegment] = []
    for b in base:
        intervals = [(b.start_ms, b.end_ms)]
        for s in subtract:
            next_intervals: list[tuple[float, float]] = []
            for st, en in intervals:
                if s.end_ms <= st or s.start_ms >= en:
                    next_intervals.append((st, en))
                    continue
                if s.start_ms > st:
                    next_intervals.append((st, s.start_ms))
                if s.end_ms < en:
                    next_intervals.append((s.end_ms, en))
            intervals = next_intervals
            if not intervals:
                break
        for st, en in intervals:
            if en > st:
                pieces.append(SilenceSegment(start_ms=st, end_ms=en, duration_ms=en - st))

    return _merge_then_filter(pieces, merge_ms=merge_ms, min_ms=min_ms)
