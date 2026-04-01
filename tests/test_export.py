"""export 모듈 검증 테스트."""

import csv
import json
import os
import tempfile
import wave

import numpy as np
import pytest
import matplotlib
matplotlib.use("Agg")  # 헤드리스 환경에서 PNG 저장
import matplotlib.pyplot as plt

from analyzer import run_analysis
from export import save_csv, save_json, save_png
from models import AnalysisConfig


SR = 16000


def _make_wav_file(duration_sec: float = 2.0, sr: int = SR, seed: int = 42) -> str:
    """임시 WAV 파일을 생성하고 경로를 반환한다."""
    rng = np.random.default_rng(seed)
    n_samples = int(sr * duration_sec)
    samples = (rng.uniform(-0.5, 0.5, n_samples) * 32767).astype(np.int16)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return tmp.name


def _get_result():
    """테스트용 AnalysisResult를 생성한다."""
    ref_path = _make_wav_file(seed=1)
    dif_path = _make_wav_file(seed=2)
    result = run_analysis(ref_path, dif_path, AnalysisConfig())
    return result, ref_path, dif_path


# ── 11.4 export 검증: JSON 필수 필드 존재 확인 ────────────────────────────────

def test_export_json_required_fields():
    """save_json() 저장 후 필수 필드가 존재하는지 검증한다."""
    result, ref_path, dif_path = _get_result()
    tmp_json = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp_json.close()

    try:
        save_json(result, tmp_json.name)

        with open(tmp_json.name, "r", encoding="utf-8") as f:
            data = json.load(f)

        required_fields = [
            "ref_path", "dif_path", "analysis_timestamp",
            "config", "snr_db", "silence_metrics",
        ]
        for field in required_fields:
            assert field in data, f"JSON에 필수 필드 '{field}'가 없습니다"
    finally:
        os.unlink(tmp_json.name)
        os.unlink(ref_path)
        os.unlink(dif_path)


# ── 11.5 export 검증: CSV 헤더 및 데이터 행 존재 확인 ─────────────────────────

def test_export_csv_header_and_data_row():
    """save_csv() 저장 후 헤더 행과 최소 1개의 데이터 행이 존재하는지 검증한다."""
    result, ref_path, dif_path = _get_result()
    tmp_csv = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp_csv.close()

    try:
        save_csv(result, tmp_csv.name)

        with open(tmp_csv.name, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert len(rows) >= 2, f"CSV 행 수 부족: {len(rows)} (헤더 + 데이터 최소 2행 필요)"
        assert len(rows[0]) > 0, "CSV 헤더 행이 비어 있습니다"
        assert len(rows[1]) > 0, "CSV 데이터 행이 비어 있습니다"
    finally:
        os.unlink(tmp_csv.name)
        os.unlink(ref_path)
        os.unlink(dif_path)


# ── 11.6 export 검증: PNG 파일 생성 확인 ──────────────────────────────────────

def test_export_png_file_created():
    """save_png() 저장 후 PNG 파일이 실제로 생성되었는지 검증한다."""
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])

    tmp_png = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_png.close()
    os.unlink(tmp_png.name)  # 파일 삭제 후 save_png가 생성하는지 확인

    try:
        save_png([fig], tmp_png.name)
        assert os.path.exists(tmp_png.name), f"PNG 파일이 생성되지 않았습니다: {tmp_png.name}"
        assert os.path.getsize(tmp_png.name) > 0, "PNG 파일이 비어 있습니다"
    finally:
        plt.close(fig)
        if os.path.exists(tmp_png.name):
            os.unlink(tmp_png.name)


def test_export_png_multiple_figures():
    """복수 Figure 저장 시 번호 접미사가 붙은 파일들이 생성되는지 검증한다."""
    figs = [plt.subplots()[0] for _ in range(3)]
    tmp_dir = tempfile.mkdtemp()
    base_path = os.path.join(tmp_dir, "output.png")

    try:
        save_png(figs, base_path)
        for i in range(1, 4):
            expected = os.path.join(tmp_dir, f"output_{i}.png")
            assert os.path.exists(expected), f"PNG 파일이 없습니다: {expected}"
    finally:
        for fig in figs:
            plt.close(fig)
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── HTML 내보내기 검증 ────────────────────────────────────────────────────────

from export import save_html


def test_export_html_file_created():
    """save_html() 저장 후 HTML 파일이 생성되고 필수 콘텐츠가 포함되는지 검증한다."""
    result, ref_path, dif_path = _get_result()
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])

    tmp_html = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    tmp_html.close()

    try:
        save_html([result], [[fig]], tmp_html.name)
        assert os.path.exists(tmp_html.name), "HTML 파일이 생성되지 않았습니다"
        assert os.path.getsize(tmp_html.name) > 0, "HTML 파일이 비어 있습니다"

        with open(tmp_html.name, "r", encoding="utf-8") as f:
            content = f.read()

        # 기본 HTML 구조 확인
        assert "<!DOCTYPE html>" in content
        assert "Audio Quality Analyzer Report" in content
        # 지표 테이블 확인
        assert "SNR" in content
        assert "PESQ" in content
        assert "STOI" in content
        assert "이상 검출" in content
        # 차트 이미지 (base64) 포함 확인
        assert "data:image/png;base64," in content
        # 이벤트 테이블 확인
        assert "dif-only" in content
    finally:
        plt.close(fig)
        os.unlink(tmp_html.name)
        os.unlink(ref_path)
        os.unlink(dif_path)


def test_export_html_dual_results():
    """듀얼 모드(2개 결과) HTML 저장 시 Pair 1, Pair 2가 모두 포함되는지 검증한다."""
    result1, ref1, dif1 = _get_result()
    result2, ref2, dif2 = _get_result()
    fig1, _ = plt.subplots()
    fig2, _ = plt.subplots()

    tmp_html = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    tmp_html.close()

    try:
        save_html([result1, result2], [[fig1], [fig2]], tmp_html.name)

        with open(tmp_html.name, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Pair 1" in content
        assert "Pair 2" in content
        # 듀얼 레이아웃 CSS 클래스 확인
        assert "dual" in content
    finally:
        plt.close(fig1)
        plt.close(fig2)
        os.unlink(tmp_html.name)
        os.unlink(ref1)
        os.unlink(dif1)
        os.unlink(ref2)
        os.unlink(dif2)
