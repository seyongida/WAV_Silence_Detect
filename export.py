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

    config_data = {
            "frame_ms": result.config.frame_ms,
            "hop_ms": result.config.hop_ms,
            "noise_floor_percentile": result.config.noise_floor_percentile,
            "energy_margin_db": result.config.energy_margin_db,
            "vad_aggressiveness": result.config.vad_aggressiveness,
            "zcr_threshold": result.config.zcr_threshold,
            "min_silence_ms": result.config.min_silence_ms,
            "silence_merge_ms": result.config.silence_merge_ms,
            "speech_strong_rms": result.config.speech_strong_rms,
            "zero_peak_threshold": result.config.zero_peak_threshold,
            "gain_drop_ratio": result.config.gain_drop_ratio,
            "gain_drop_ratio_strict": result.config.gain_drop_ratio_strict,
            "gain_drop_min_corr": result.config.gain_drop_min_corr,
            "prior_activity_threshold": result.config.prior_activity_threshold,
            "min_anomaly_ms": result.config.min_anomaly_ms,
            "min_anomaly_a_ms": result.config.min_anomaly_a_ms,
            "min_anomaly_b_ms": result.config.min_anomaly_b_ms,
            "anomaly_gap_frames": result.config.anomaly_gap_frames,
        }

    data = {
        "ref_path": result.ref_path,
        "dif_path": result.dif_path,
        "analysis_timestamp": result.analysis_timestamp,
        "config": config_data,
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
        "anomaly_segments": [
            {
                "start_ms": s.start_ms, "end_ms": s.end_ms,
                "duration_ms": s.duration_ms, "type": s.anomaly_type,
                "mean_gain_db": s.mean_gain_db,
            }
            for s in getattr(result, "anomaly_segments", [])
        ],
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


def _fig_to_base64(fig, dpi: int = 150) -> str:
    """matplotlib Figure를 base64 PNG 문자열로 변환한다."""
    import base64
    import io
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _metric_val(m) -> str:
    if m.value is None:
        return f"N/A ({m.reason or m.status})"
    return f"{m.value:.4f}"


def _build_result_html(result: AnalysisResult, figures: list, label: str) -> str:
    """단일 분석 결과를 HTML 섹션으로 변환한다."""
    sm = result.silence_metrics
    d = result.delay

    # anomaly 집계
    anomalies = getattr(result, "anomaly_segments", [])
    n_zero = sum(1 for s in anomalies if s.anomaly_type == "digital_zero")
    n_gain = sum(1 for s in anomalies if s.anomaly_type == "gain_drop")

    # 요약 통계
    stats = f"""
    <div class="stats-row">
      <div class="stat-card"><div class="stat-val err">{sm.dif_silence_count}</div><div class="stat-lbl">dif-only 음성 깨짐 수</div></div>
      <div class="stat-card"><div class="stat-val warn">{sm.dif_total_silence_ms:.0f}</div><div class="stat-lbl">dif-only 깨짐 (ms)</div></div>
    </div>"""

    # dif-only 이벤트 테이블
    events = []
    for seg in anomalies:
        lbl = "묵음" if seg.anomaly_type == "digital_zero" else "깨짐"
        events.append((lbl, seg.duration_ms, seg.start_ms, seg.end_ms))
    if not events:
        for seg in result.false_silence_segments:
            events.append(("묵음", seg.duration_ms, seg.start_ms, seg.end_ms))
    events.sort(key=lambda x: x[2])

    seg_rows = ""
    for i, (lbl, dur, start, end) in enumerate(events):
        seg_rows += f"<tr><td>{i+1}</td><td>{lbl}</td><td>{dur:.1f}</td><td>{start/1000:.3f}</td><td>{end/1000:.3f}</td></tr>\n"
    seg_table = f"""
    <div class="card">
      <h3>dif-only 이벤트</h3>
      <table><thead><tr><th>#</th><th>구분</th><th>길이 (ms)</th><th>시작 (s)</th><th>종료 (s)</th></tr></thead>
      <tbody>{seg_rows if seg_rows else '<tr><td colspan="5">없음</td></tr>'}</tbody></table>
    </div>"""

    # 분석 지표 요약
    info = f"""
    <div class="card">
      <h3>분석 지표</h3>
      <p><b>Delay:</b> {d.applied_delay_ms:.1f} ms (coarse: {d.coarse_delay_ms:.1f}, refined: {d.refined_delay_ms:.1f}, DTW: {d.dtw_used})</p>
      <p><b>이상 검출:</b> 묵음 {n_zero}건, 깨짐 {n_gain}건</p>
      <p><b>SNR:</b> {_metric_val(result.snr_db)} dB &nbsp; <b>PESQ:</b> {_metric_val(result.pesq_score)} &nbsp; <b>STOI:</b> {_metric_val(result.stoi_score)}</p>
      <p><b>RMS diff:</b> {_metric_val(result.rms_diff_db)} dB &nbsp; <b>Clipping:</b> {_metric_val(result.clipping_ratio)}</p>
      <p><b>ref NF:</b> {_metric_val(result.ref_noise_floor_db)} dB &nbsp; <b>dif NF:</b> {_metric_val(result.dif_noise_floor_db)} dB</p>
    </div>"""

    # 상세 지표 테이블
    metric_rows_data = [
        ("이상 검출 (묵음)", str(n_zero), "0 = 정상", "dif에서 디지털 제로 구간 수"),
        ("이상 검출 (깨짐)", str(n_gain), "0 = 정상", "dif에서 gain 변조 구간 수"),
        ("이상 총 시간 (ms)", f"{sm.dif_total_silence_ms:.0f}", "0 = 정상", "이상 구간 총 지속 시간"),
        ("SNR (dB)", _metric_val(result.snr_db), "&gt;20 good, &gt;30 very good", "높을수록 좋음"),
        ("PESQ", _metric_val(result.pesq_score), "1.0 ~ 4.5", "높을수록 음질 좋음"),
        ("STOI", _metric_val(result.stoi_score), "0.0 ~ 1.0", "높을수록 명료도 좋음"),
        ("RMS diff (dB)", _metric_val(result.rms_diff_db), "0 dB 근처", "0에 가까울수록 유사"),
        ("Clipping", _metric_val(result.clipping_ratio), "0.0 ~ 1.0", "0에 가까울수록 좋음"),
        ("ref NF (dB)", _metric_val(result.ref_noise_floor_db), "-100 ~ -20", "낮을수록 조용"),
        ("dif NF (dB)", _metric_val(result.dif_noise_floor_db), "-100 ~ -20", "ref와 비교"),
    ]
    m_rows = ""
    for name, val, ref_range, desc in metric_rows_data:
        m_rows += f"<tr><td>{name}</td><td>{val}</td><td>{ref_range}</td><td>{desc}</td></tr>\n"
    metric_table = f"""
    <div class="card">
      <h3>상세 지표</h3>
      <table><thead><tr><th>지표</th><th>값</th><th>참고 범위</th><th>해석</th></tr></thead>
      <tbody>{m_rows}</tbody></table>
    </div>"""

    # 차트 이미지 (base64)
    charts_html = ""
    for fig in figures:
        b64 = _fig_to_base64(fig)
        charts_html += f'<div class="chart"><img src="data:image/png;base64,{b64}" /></div>\n'

    return f"""
    <div class="result-section">
      <h2>{label}</h2>
      <p class="meta">ref: {result.ref_path}<br>dif: {result.dif_path}<br>분석 시각: {result.analysis_timestamp}</p>
      {stats}{seg_table}{info}{metric_table}{charts_html}
    </div>"""


def save_html(
    results: list[AnalysisResult],
    figures_per_result: list[list],
    path: str,
) -> None:
    """분석 결과 전체를 self-contained HTML 파일로 저장한다.

    매개변수:
        results: AnalysisResult 목록 (1~2개)
        figures_per_result: 각 result에 대응하는 matplotlib Figure 리스트의 리스트
        path: 저장 경로
    """
    sections = ""
    for i, (result, figs) in enumerate(zip(results, figures_per_result)):
        label = f"Pair {i + 1}" if len(results) > 1 else "분석 결과"
        sections += _build_result_html(result, figs, label)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audio Quality Analyzer Report</title>
<style>
  :root {{ --bg: #181a20; --card: #23262f; --border: #333; --accent: #6c5ce7;
           --text: #e0e0e0; --dim: #888; --err: #e74c3c; --warn: #f39c12;
           --p1: #6c5ce7; --p2: #00b894; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ color: var(--accent); font-size: 22px; margin-bottom: 20px; }}
  h2 {{ color: var(--accent); font-size: 18px; margin: 24px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  h3 {{ color: var(--text); font-size: 14px; margin-bottom: 8px; }}
  .meta {{ color: var(--dim); font-size: 12px; margin-bottom: 12px; line-height: 1.6; }}
  .stats-row {{ display: flex; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }}
  .stat-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 12px 18px; text-align: center; flex: 1; min-width: 120px; }}
  .stat-val {{ font-size: 22px; font-weight: 700; }}
  .stat-lbl {{ font-size: 11px; color: var(--dim); margin-top: 4px; }}
  .stat-val.err {{ color: var(--err); }} .stat-val.warn {{ color: var(--warn); }}
  .stat-val.p1 {{ color: var(--p1); }} .stat-val.p2 {{ color: var(--p2); }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 14px; margin-bottom: 14px; }}
  .card p {{ font-size: 13px; line-height: 1.7; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 6px 10px; border: 1px solid var(--border); text-align: left; }}
  th {{ background: #2a2d36; font-weight: 600; }}
  .chart {{ margin: 10px 0; }} .chart img {{ width: 100%; border-radius: 6px; }}
  .dual {{ display: flex; gap: 20px; }} .dual > .result-section {{ flex: 1; min-width: 0; }}
  @media (max-width: 900px) {{ .dual {{ flex-direction: column; }} }}
</style>
</head>
<body>
<h1>Audio Quality Analyzer Report</h1>
<div class="{'dual' if len(results) > 1 else ''}">
{sections}
</div>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
