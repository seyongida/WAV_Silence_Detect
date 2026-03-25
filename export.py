"""결과 저장 모듈 (JSON, CSV, PNG)."""

import csv
import json
import os
from dataclasses import asdict
from typing import Any

import numpy as np

from models import AnalysisResult


def _to_serializable(obj: Any) -> Any:
    """numpy 배열 등 JSON 직렬화 불가 객체를 변환한다."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, float) and (obj != obj):  # NaN
        return None
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(v) for v in obj]
    return obj


def save_json(result: AnalysisResult, path: str) -> None:
    """AnalysisResult를 JSON 파일로 저장한다.

    포함 내용: 입력 파일 경로, 분석 시각, AnalysisConfig, 주요 지표, 묵음 구간 정보

    매개변수:
        result (AnalysisResult): 분석 결과
        path (str): 저장 경로
    """
    def _seg_list(segs):
        return [{"start_ms": s.start_ms, "end_ms": s.end_ms, "duration_ms": s.duration_ms}
                for s in segs]

    def _metric(m):
        return {"value": m.value, "status": m.status, "reason": m.reason}

    data = {
        "ref_path": result.ref_path,
        "dif_path": result.dif_path,
        "analysis_timestamp": result.analysis_timestamp,
        "config": {
            "frame_ms": result.config.frame_ms,
            "hop_ms": result.config.hop_ms,
            "noise_floor_percentile": result.config.noise_floor_percentile,
            "energy_margin_db": result.config.energy_margin_db,
            "vad_aggressiveness": result.config.vad_aggressiveness,
            "zcr_threshold": result.config.zcr_threshold,
            "min_silence_ms": result.config.min_silence_ms,
            "silence_merge_ms": result.config.silence_merge_ms,
        },
        "snr_db": _metric(result.snr_db),
        "pesq_score": _metric(result.pesq_score),
        "stoi_score": _metric(result.stoi_score),
        "rms_diff_db": _metric(result.rms_diff_db),
        "clipping_ratio": _metric(result.clipping_ratio),
        "ref_noise_floor_db": _metric(result.ref_noise_floor_db),
        "dif_noise_floor_db": _metric(result.dif_noise_floor_db),
        "delay": {
            "coarse_delay_ms": result.delay.coarse_delay_ms,
            "refined_delay_ms": result.delay.refined_delay_ms,
            "applied_delay_ms": result.delay.applied_delay_ms,
            "dtw_used": result.delay.dtw_used,
        },
        "silence_metrics": {
            "silence_leakage": result.silence_metrics.silence_leakage,
            "false_silence": result.silence_metrics.false_silence,
            "dif_silence_count": result.silence_metrics.dif_silence_count,
            "dif_total_silence_ms": result.silence_metrics.dif_total_silence_ms,
        },
        "ref_silence_segments": _seg_list(result.ref_silence_segments),
        "dif_silence_segments": _seg_list(result.dif_silence_segments),
        "false_silence_segments": _seg_list(result.false_silence_segments),
        "silence_leakage_segments": _seg_list(result.silence_leakage_segments),
        "error_log": [
            {"level": m.level, "message": m.message, "timestamp": m.timestamp}
            for m in result.error_log
        ],
    }

    data = _to_serializable(data)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_csv(result: AnalysisResult, path: str) -> None:
    """AnalysisResult의 주요 지표 요약을 CSV 파일로 저장한다.

    포함 내용: SNR, PESQ, STOI, RMS 차이, Clipping 비율, 묵음 통계

    매개변수:
        result (AnalysisResult): 분석 결과
        path (str): 저장 경로
    """
    headers = [
        "ref_path", "dif_path", "analysis_timestamp",
        "snr_db", "pesq_score", "stoi_score",
        "rms_diff_db", "clipping_ratio",
        "ref_noise_floor_db", "dif_noise_floor_db",
        "applied_delay_ms",
        "silence_leakage", "false_silence",
        "dif_silence_count", "dif_total_silence_ms",
    ]

    row = [
        result.ref_path,
        result.dif_path,
        result.analysis_timestamp,
        result.snr_db.value,
        result.pesq_score.value,
        result.stoi_score.value,
        result.rms_diff_db.value,
        result.clipping_ratio.value,
        result.ref_noise_floor_db.value,
        result.dif_noise_floor_db.value,
        result.delay.applied_delay_ms,
        result.silence_metrics.silence_leakage,
        result.silence_metrics.false_silence,
        result.silence_metrics.dif_silence_count,
        result.silence_metrics.dif_total_silence_ms,
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(row)


def save_png(figures: list, path: str) -> None:
    """matplotlib Figure 목록을 PNG 이미지 파일로 저장한다.

    여러 Figure는 path 기반 번호 접미사(예: _1.png, _2.png)로 저장한다.

    매개변수:
        figures (list): matplotlib Figure 목록
        path (str): 저장 경로 (기본 경로)
    """
    if not figures:
        return

    base, ext = os.path.splitext(path)
    if not ext:
        ext = ".png"

    if len(figures) == 1:
        figures[0].savefig(path, dpi=150, bbox_inches="tight")
    else:
        for i, fig in enumerate(figures, start=1):
            out_path = f"{base}_{i}{ext}"
            fig.savefig(out_path, dpi=150, bbox_inches="tight")
