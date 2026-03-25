"""Main desktop UI for audio comparison analysis."""

import os
import sys

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import analyzer as analyzer_mod
import export as export_mod
from errors import AudioAnalyzerError
from models import AnalysisMessage, AnalysisResult


class AnalysisWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, ref_path: str, dif_path: str, config):
        super().__init__()
        self.ref_path = ref_path
        self.dif_path = dif_path
        self.config = config

    def run(self):
        try:
            result = analyzer_mod.run_analysis(
                self.ref_path,
                self.dif_path,
                self.config,
                progress_callback=lambda p, t: self.progress.emit(p, t),
            )
            self.finished.emit(result)
        except AudioAnalyzerError as e:
            self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            self.error.emit(str(e))


class FilePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._ref_path = ""
        self._dif_path = ""
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Input format: WAV | Supports mono/stereo | Recommended duration: <= 10 min"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#4b5563;")
        layout.addWidget(info)

        ref_group = QGroupBox("Reference Audio")
        ref_layout = QHBoxLayout(ref_group)
        self._ref_label = QLabel("No file selected")
        self._ref_label.setWordWrap(True)
        ref_btn = QPushButton("Select")
        ref_btn.clicked.connect(self._select_ref)
        ref_layout.addWidget(self._ref_label, 1)
        ref_layout.addWidget(ref_btn)
        layout.addWidget(ref_group)

        dif_group = QGroupBox("Compare Audio")
        dif_layout = QHBoxLayout(dif_group)
        self._dif_label = QLabel("No file selected")
        self._dif_label.setWordWrap(True)
        dif_btn = QPushButton("Select")
        dif_btn.clicked.connect(self._select_dif)
        dif_layout.addWidget(self._dif_label, 1)
        dif_layout.addWidget(dif_btn)
        layout.addWidget(dif_group)

        sample_ref = os.path.join("sample_audio", "ref.wav")
        sample_dif = os.path.join("sample_audio", "dif_2+shift.wav")
        if os.path.exists(sample_ref):
            self._ref_path = sample_ref
            self._ref_label.setText(sample_ref)
        if os.path.exists(sample_dif):
            self._dif_path = sample_dif
            self._dif_label.setText(sample_dif)

    def _select_ref(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select reference WAV", "", "WAV (*.wav)")
        if path:
            self._ref_path = path
            self._ref_label.setText(path)

    def _select_dif(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select compare WAV", "", "WAV (*.wav)")
        if path:
            self._dif_path = path
            self._dif_label.setText(path)

    def get_ref_path(self) -> str:
        return self._ref_path

    def get_dif_path(self) -> str:
        return self._dif_path


class ParamPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        group = QGroupBox("Analysis Parameters")
        form = QFormLayout(group)

        self._frame_ms = QSpinBox()
        self._frame_ms.setRange(5, 100)
        self._frame_ms.setValue(20)
        form.addRow("Frame (ms)", self._frame_ms)

        self._hop_ms = QSpinBox()
        self._hop_ms.setRange(1, 100)
        self._hop_ms.setValue(10)
        form.addRow("Hop (ms)", self._hop_ms)

        self._noise_floor = QDoubleSpinBox()
        self._noise_floor.setRange(0.0, 100.0)
        self._noise_floor.setValue(15.0)
        form.addRow("Noise floor percentile", self._noise_floor)

        self._energy_margin = QDoubleSpinBox()
        self._energy_margin.setRange(0.0, 50.0)
        self._energy_margin.setValue(10.0)
        form.addRow("Energy margin (dB)", self._energy_margin)

        self._vad_aggressiveness = QSpinBox()
        self._vad_aggressiveness.setRange(0, 3)
        self._vad_aggressiveness.setValue(2)
        form.addRow("VAD aggressiveness", self._vad_aggressiveness)

        self._zcr_threshold = QDoubleSpinBox()
        self._zcr_threshold.setRange(0.0, 1.0)
        self._zcr_threshold.setDecimals(3)
        self._zcr_threshold.setSingleStep(0.01)
        self._zcr_threshold.setValue(0.1)
        form.addRow("ZCR threshold", self._zcr_threshold)

        self._min_silence_ms = QSpinBox()
        self._min_silence_ms.setRange(1, 2000)
        self._min_silence_ms.setValue(200)
        form.addRow("Min silence (ms)", self._min_silence_ms)

        self._silence_merge_ms = QSpinBox()
        self._silence_merge_ms.setRange(0, 1000)
        self._silence_merge_ms.setValue(50)
        form.addRow("Silence merge gap (ms)", self._silence_merge_ms)

        self._residual_thr = QDoubleSpinBox()
        self._residual_thr.setRange(0.001, 1.0)
        self._residual_thr.setDecimals(3)
        self._residual_thr.setValue(0.05)
        form.addRow("Residual highlight", self._residual_thr)

        self._centroid_thr = QDoubleSpinBox()
        self._centroid_thr.setRange(1.0, 10000.0)
        self._centroid_thr.setValue(300.0)
        form.addRow("Centroid highlight (Hz)", self._centroid_thr)

        self._rolloff_thr = QDoubleSpinBox()
        self._rolloff_thr.setRange(1.0, 20000.0)
        self._rolloff_thr.setValue(500.0)
        form.addRow("Rolloff highlight (Hz)", self._rolloff_thr)

        layout = QVBoxLayout(self)
        layout.addWidget(group)

    def get_config(self):
        return analyzer_mod.AnalysisConfigV2(
            frame_ms=self._frame_ms.value(),
            hop_ms=self._hop_ms.value(),
            noise_floor_percentile=self._noise_floor.value(),
            energy_margin_db=self._energy_margin.value(),
            vad_aggressiveness=self._vad_aggressiveness.value(),
            zcr_threshold=self._zcr_threshold.value(),
            min_silence_ms=self._min_silence_ms.value(),
            silence_merge_ms=self._silence_merge_ms.value(),
            residual_diff_threshold=self._residual_thr.value(),
            centroid_diff_threshold_hz=self._centroid_thr.value(),
            rolloff_diff_threshold_hz=self._rolloff_thr.value(),
        )

    def validate(self) -> list[str]:
        return analyzer_mod.validate_config(self.get_config())


class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Analysis Log"))
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumHeight(130)
        layout.addWidget(self._text)

    def append_message(self, msg: AnalysisMessage) -> None:
        color_map = {"warn": "#d97706", "error": "#dc2626", "info": "#0f172a"}
        color = color_map.get(msg.level, "#0f172a")
        self._text.append(f'<span style="color:{color}">[{msg.level.upper()}] {msg.message}</span>')

    def clear(self) -> None:
        self._text.clear()


class ResultPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: AnalysisResult | None = None
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        scroll.setWidget(container)

        # Critical summary panel
        summary_group = QGroupBox("Primary Outcome (Most Important)")
        summary_layout = QGridLayout(summary_group)
        self._dif_only_count_big = QLabel("-")
        self._dif_only_count_big.setStyleSheet("font-size:28px;font-weight:700;color:#111827;")
        self._dif_only_total_big = QLabel("-")
        self._dif_only_total_big.setStyleSheet("font-size:28px;font-weight:700;color:#111827;")
        summary_layout.addWidget(QLabel("dif-only silence count"), 0, 0)
        summary_layout.addWidget(self._dif_only_count_big, 1, 0)
        summary_layout.addWidget(QLabel("dif-only total silence (ms)"), 0, 1)
        summary_layout.addWidget(self._dif_only_total_big, 1, 1)
        self._layout.addWidget(summary_group)

        detail_group = QGroupBox("dif-only silence events")
        detail_layout = QVBoxLayout(detail_group)
        self._dif_only_table = QTableWidget(0, 4)
        self._dif_only_table.setHorizontalHeaderLabels(["Count #", "Duration (ms)", "Start (s, ref axis)", "End (s, ref axis)"])
        self._dif_only_table.verticalHeader().setVisible(False)
        detail_layout.addWidget(self._dif_only_table)
        self._layout.addWidget(detail_group)

        self._metrics_label = QLabel("Analysis result appears here.")
        self._metrics_label.setWordWrap(True)
        self._layout.addWidget(self._metrics_label)

        self._show_ref_silence = QCheckBox("Show ref silence overlay")
        self._show_ref_silence.setChecked(False)
        self._show_ref_silence.stateChanged.connect(self._redraw)
        self._layout.addWidget(self._show_ref_silence)

        self._metric_table = QTableWidget(0, 4)
        self._metric_table.setHorizontalHeaderLabels(["Metric", "Value", "Reference Range", "How to Read"])
        self._metric_table.verticalHeader().setVisible(False)
        self._layout.addWidget(self._metric_table)

        self._waveform_fig, self._waveform_ax = plt.subplots(2, 1, figsize=(10, 4), sharex=True)
        self._waveform_canvas = FigureCanvas(self._waveform_fig)
        self._layout.addWidget(self._waveform_canvas)
        self._layout.addWidget(QLabel("Waveforms: global alignment and silence overlays."))

        self._diff_fig, self._diff_ax = plt.subplots(1, 1, figsize=(10, 2.2), sharex=False)
        self._diff_canvas = FigureCanvas(self._diff_fig)
        self._layout.addWidget(self._diff_canvas)
        self._layout.addWidget(QLabel("Residual (ref - dif): spikes indicate local mismatch."))

        self._spec_fig, self._spec_axes = plt.subplots(2, 1, figsize=(10, 4), sharex=True)
        self._spec_canvas = FigureCanvas(self._spec_fig)
        self._layout.addWidget(self._spec_canvas)
        self._layout.addWidget(QLabel("Spectrograms: ref (top), delay-corrected dif (bottom)."))

        self._ts_fig, self._ts_axes = plt.subplots(2, 1, figsize=(10, 3), sharex=True)
        self._ts_canvas = FigureCanvas(self._ts_fig)
        self._layout.addWidget(self._ts_canvas)
        self._layout.addWidget(QLabel("Centroid/Rolloff trends with difference highlights."))

        self._apply_figure_margins()

    def update_result(self, result: AnalysisResult) -> None:
        self._result = result
        self._update_top_summary()
        self._update_metrics_label()
        self._update_metric_table()
        self._redraw()

    def _fmt(self, metric) -> str:
        if metric.value is None:
            return f"N/A ({metric.reason or metric.status})"
        return f"{metric.value:.4f}"

    def _update_top_summary(self):
        r = self._result
        if r is None:
            return
        sm = r.silence_metrics
        self._dif_only_count_big.setText(str(sm.dif_silence_count))
        self._dif_only_total_big.setText(f"{sm.dif_total_silence_ms:.1f}")

        self._dif_only_table.setRowCount(len(r.false_silence_segments))
        for i, seg in enumerate(r.false_silence_segments):
            self._dif_only_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self._dif_only_table.setItem(i, 1, QTableWidgetItem(f"{seg.duration_ms:.1f}"))
            self._dif_only_table.setItem(i, 2, QTableWidgetItem(f"{seg.start_ms / 1000.0:.3f}"))
            self._dif_only_table.setItem(i, 3, QTableWidgetItem(f"{seg.end_ms / 1000.0:.3f}"))
        self._dif_only_table.resizeColumnsToContents()

    def _update_metrics_label(self):
        r = self._result
        if r is None:
            return
        sm = r.silence_metrics
        d = r.delay
        self._metrics_label.setText(
            f"<b>Delay:</b> {d.applied_delay_ms:.1f} ms (coarse: {d.coarse_delay_ms:.1f}, refined: {d.refined_delay_ms:.1f}, dtw_used: {d.dtw_used})<br>"
            f"<b>SNR:</b> {self._fmt(r.snr_db)} dB &nbsp;&nbsp; <b>PESQ:</b> {self._fmt(r.pesq_score)} &nbsp;&nbsp; <b>STOI:</b> {self._fmt(r.stoi_score)}<br>"
            f"<b>RMS diff:</b> {self._fmt(r.rms_diff_db)} dB &nbsp;&nbsp; <b>Clipping:</b> {self._fmt(r.clipping_ratio)}<br>"
            f"<b>ref Noise Floor:</b> {self._fmt(r.ref_noise_floor_db)} dB &nbsp;&nbsp; <b>dif Noise Floor:</b> {self._fmt(r.dif_noise_floor_db)} dB<br>"
            f"<b>Silence Leakage:</b> {sm.silence_leakage:.4f} &nbsp;&nbsp; <b>False Silence:</b> {sm.false_silence:.4f}"
        )

    def _update_metric_table(self):
        r = self._result
        if r is None:
            return
        sm = r.silence_metrics
        rows = [
            ("SNR (dB)", self._fmt(r.snr_db), ">20 good, >30 very good", "Higher is better."),
            ("PESQ", self._fmt(r.pesq_score), "1.0 to 4.5", "Higher is better perceived quality."),
            ("STOI", self._fmt(r.stoi_score), "0.0 to 1.0", "Higher is better intelligibility."),
            ("RMS diff (dB)", self._fmt(r.rms_diff_db), "Around 0 dB", "Closer to 0 means similar loudness."),
            ("Clipping ratio", self._fmt(r.clipping_ratio), "0.0 to 1.0", "Closer to 0 is better."),
            ("ref Noise Floor (dB)", self._fmt(r.ref_noise_floor_db), "-100 to -20", "More negative is quieter."),
            ("dif Noise Floor (dB)", self._fmt(r.dif_noise_floor_db), "-100 to -20", "Compare against ref."),
            ("Silence Leakage", f"{sm.silence_leakage:.4f}", "0.0 to 1.0", "Ref silence broken in dif."),
            ("False Silence", f"{sm.false_silence:.4f}", "0.0 to 1.0", "Ref non-silence became silence in dif."),
        ]
        self._metric_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                self._metric_table.setItem(i, j, QTableWidgetItem(value))
        self._metric_table.resizeColumnsToContents()

    def _cfg(self, name: str, default_value: float) -> float:
        if self._result is None:
            return default_value
        return float(getattr(self._result.config, name, default_value))

    @staticmethod
    def _mask_to_spans(mask: np.ndarray, min_len: int = 1, merge_gap: int = 0) -> list[tuple[int, int]]:
        raw: list[tuple[int, int]] = []
        start = None
        for i, v in enumerate(mask):
            if v and start is None:
                start = i
            elif (not v) and start is not None:
                raw.append((start, i))
                start = None
        if start is not None:
            raw.append((start, len(mask)))
        if not raw:
            return []
        merged = [raw[0]]
        for s, e in raw[1:]:
            ps, pe = merged[-1]
            if s - pe <= merge_gap:
                merged[-1] = (ps, e)
            else:
                merged.append((s, e))
        return [(s, e) for s, e in merged if (e - s) >= min_len]

    def _redraw(self):
        r = self._result
        if r is None:
            return

        sr = r.ref_audio.sample_rate
        ref_samples = r.ref_audio.samples
        dif_aligned = r.dif_aligned
        if ref_samples.ndim > 1:
            ref_samples = ref_samples.mean(axis=1)

        n = min(len(ref_samples), len(dif_aligned))
        ref_common = ref_samples[:n]
        dif_common = dif_aligned[:n]
        t = np.arange(n) / sr

        for ax in self._waveform_ax:
            ax.cla()
        self._waveform_ax[0].plot(t, ref_common, linewidth=0.5, color="#2563eb")
        self._waveform_ax[0].set_title("ref waveform")
        self._waveform_ax[0].set_ylabel("Amplitude")
        self._waveform_ax[1].plot(t, dif_common, linewidth=0.5, color="#d97706")
        self._waveform_ax[1].set_title("dif waveform (delay-corrected)")
        self._waveform_ax[1].set_ylabel("Amplitude")
        self._waveform_ax[1].set_xlabel("Time (s)")

        for seg in r.dif_silence_segments:
            for ax in self._waveform_ax:
                ax.axvspan(seg.start_ms / 1000.0, seg.end_ms / 1000.0, alpha=0.24, color="#fb923c")
        if self._show_ref_silence.isChecked():
            for seg in r.ref_silence_segments:
                for ax in self._waveform_ax:
                    ax.axvspan(seg.start_ms / 1000.0, seg.end_ms / 1000.0, alpha=0.16, color="#60a5fa")
        for seg in r.false_silence_segments:
            for ax in self._waveform_ax:
                ax.axvspan(seg.start_ms / 1000.0, seg.end_ms / 1000.0, alpha=0.30, color="#ef4444")
        for seg in r.silence_leakage_segments:
            for ax in self._waveform_ax:
                ax.axvspan(seg.start_ms / 1000.0, seg.end_ms / 1000.0, alpha=0.20, color="#facc15")
        self._waveform_fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.11, hspace=0.25)
        self._waveform_canvas.draw()

        self._diff_ax.cla()
        residual = ref_common - dif_common
        self._diff_ax.plot(t, residual, color="#7c3aed", linewidth=0.6)
        thr = self._cfg("residual_diff_threshold", 0.05)
        mask = np.abs(residual) >= thr
        if len(t) > 1:
            dt = float(t[1] - t[0])
            spans = self._mask_to_spans(mask, min_len=max(1, int(round(0.03 / dt))), merge_gap=max(0, int(round(0.02 / dt))))
        else:
            spans = []
        for s, e in spans:
            self._diff_ax.axvspan(float(t[s]), float(t[e - 1]), alpha=0.22, color="#ef4444")
        self._diff_ax.axhline(0.0, color="#111827", linewidth=0.7, alpha=0.6)
        self._diff_ax.set_title("Residual waveform (ref - dif)")
        self._diff_ax.set_xlabel("Time (s)")
        self._diff_ax.set_ylabel("Amplitude")
        self._diff_fig.subplots_adjust(left=0.08, right=0.985, top=0.90, bottom=0.20)
        self._diff_canvas.draw()

        for ax in self._spec_axes:
            ax.cla()
        if r.spectrum is not None:
            ref_spec = r.spectrum.ref_spectrogram
            dif_spec = r.spectrum.dif_spectrogram
            self._spec_axes[0].pcolormesh(ref_spec.times, ref_spec.frequencies, ref_spec.magnitude_db, shading="auto", cmap="viridis")
            self._spec_axes[0].set_title("ref spectrogram")
            self._spec_axes[0].set_ylabel("Frequency (Hz)")
            self._spec_axes[1].pcolormesh(dif_spec.times, dif_spec.frequencies, dif_spec.magnitude_db, shading="auto", cmap="viridis")
            self._spec_axes[1].set_title("dif spectrogram (delay-corrected)")
            self._spec_axes[1].set_ylabel("Frequency (Hz)")
            self._spec_axes[1].set_xlabel("Time (s)")
        else:
            for ax in self._spec_axes:
                ax.text(0.5, 0.5, "Not available", ha="center", va="center", transform=ax.transAxes)
        self._spec_fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.11, hspace=0.25)
        self._spec_canvas.draw()

        for ax in self._ts_axes:
            ax.cla()
        if r.spectrum is not None:
            sp = r.spectrum
            self._ts_axes[0].plot(sp.ref_centroid, label="ref", color="#2563eb", linewidth=0.8)
            self._ts_axes[0].plot(sp.dif_centroid, label="dif", color="#d97706", linewidth=0.8)
            cdiff = np.abs(sp.ref_centroid - sp.dif_centroid)
            for s, e in self._mask_to_spans(cdiff >= self._cfg("centroid_diff_threshold_hz", 300.0), min_len=3, merge_gap=2):
                self._ts_axes[0].axvspan(float(s), float(e - 1), alpha=0.22, color="#ef4444")
            self._ts_axes[0].set_title("Spectral Centroid")
            self._ts_axes[0].set_ylabel("Hz")
            self._ts_axes[0].legend(fontsize=8)

            self._ts_axes[1].plot(sp.ref_rolloff, label="ref", color="#2563eb", linewidth=0.8)
            self._ts_axes[1].plot(sp.dif_rolloff, label="dif", color="#d97706", linewidth=0.8)
            rdiff = np.abs(sp.ref_rolloff - sp.dif_rolloff)
            for s, e in self._mask_to_spans(rdiff >= self._cfg("rolloff_diff_threshold_hz", 500.0), min_len=3, merge_gap=2):
                self._ts_axes[1].axvspan(float(s), float(e - 1), alpha=0.22, color="#ef4444")
            self._ts_axes[1].set_title("Spectral Rolloff")
            self._ts_axes[1].set_ylabel("Hz")
            self._ts_axes[1].set_xlabel("Frame index")
            self._ts_axes[1].legend(fontsize=8)
        else:
            for ax in self._ts_axes:
                ax.text(0.5, 0.5, "Not available", ha="center", va="center", transform=ax.transAxes)
        self._ts_fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.13, hspace=0.30)
        self._ts_canvas.draw()

    def _apply_figure_margins(self):
        # Keep the same left/right figure margins so x-axis start/end align visually.
        self._waveform_fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.11, hspace=0.25)
        self._diff_fig.subplots_adjust(left=0.08, right=0.985, top=0.90, bottom=0.20)
        self._spec_fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.11, hspace=0.25)
        self._ts_fig.subplots_adjust(left=0.08, right=0.985, top=0.93, bottom=0.13, hspace=0.30)

    def get_figures(self) -> list:
        return [self._waveform_fig, self._diff_fig, self._spec_fig, self._ts_fig]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Quality Analyzer")
        self.resize(1300, 920)
        self._worker: AnalysisWorker | None = None
        self._result: AnalysisResult | None = None
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(
            """
            QWidget { font-size: 12px; }
            QGroupBox { font-weight: 600; border: 1px solid #d1d5db; border-radius: 8px; margin-top: 8px; padding-top: 8px; }
            QPushButton { padding: 6px 10px; font-weight: 600; }
            QTableWidget { gridline-color: #e5e7eb; alternate-background-color: #f8fafc; }
            QLabel { color: #0f172a; }
            """
        )
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        top_splitter = QSplitter(Qt.Horizontal)
        self._file_panel = FilePanel()
        self._param_panel = ParamPanel()
        top_splitter.addWidget(self._file_panel)
        top_splitter.addWidget(self._param_panel)
        top_splitter.setSizes([500, 430])
        main_layout.addWidget(top_splitter)

        btn_layout = QHBoxLayout()
        self._analyze_btn = QPushButton("Run Analysis")
        self._analyze_btn.clicked.connect(self._start_analysis)
        btn_layout.addWidget(self._analyze_btn)

        self._save_json_btn = QPushButton("Save JSON")
        self._save_json_btn.clicked.connect(self._save_json)
        self._save_json_btn.setEnabled(False)
        btn_layout.addWidget(self._save_json_btn)

        self._save_csv_btn = QPushButton("Save CSV")
        self._save_csv_btn.clicked.connect(self._save_csv)
        self._save_csv_btn.setEnabled(False)
        btn_layout.addWidget(self._save_csv_btn)

        self._save_png_btn = QPushButton("Save PNG")
        self._save_png_btn.clicked.connect(self._save_png)
        self._save_png_btn.setEnabled(False)
        btn_layout.addWidget(self._save_png_btn)
        btn_layout.addStretch(1)
        main_layout.addLayout(btn_layout)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_label = QLabel("")
        main_layout.addWidget(self._progress_bar)
        main_layout.addWidget(self._progress_label)

        self._result_panel = ResultPanel()
        main_layout.addWidget(self._result_panel, 1)

        self._log_panel = LogPanel()
        main_layout.addWidget(self._log_panel)

    def _start_analysis(self):
        ref_path = self._file_panel.get_ref_path()
        dif_path = self._file_panel.get_dif_path()
        if not ref_path or not dif_path:
            QMessageBox.warning(self, "File selection required", "Select both ref and dif WAV files.")
            return

        errors = self._param_panel.validate()
        if errors:
            QMessageBox.warning(self, "Invalid parameters", "\n".join(errors))
            return

        self._log_panel.clear()
        self._analyze_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)

        self._worker = AnalysisWorker(ref_path, dif_path, self._param_panel.get_config())
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, percent: int, text: str):
        self._progress_bar.setValue(percent)
        self._progress_label.setText(text)

    def _on_finished(self, result: AnalysisResult):
        self._result = result
        self._analyze_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._progress_label.setText("Analysis complete")

        if result.error_log:
            for msg in result.error_log:
                self._log_panel.append_message(msg)
        else:
            self._log_panel.append_message(
                AnalysisMessage(level="info", message="No warnings or errors.", timestamp=result.analysis_timestamp)
            )

        self._result_panel.update_result(result)
        self._save_json_btn.setEnabled(True)
        self._save_csv_btn.setEnabled(True)
        self._save_png_btn.setEnabled(True)

    def _on_error(self, error_msg: str):
        self._analyze_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._progress_label.setText("Error")
        QMessageBox.critical(self, "Analysis error", error_msg)

    def _save_json(self):
        if self._result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON", "result.json", "JSON (*.json)")
        if path:
            export_mod.save_json(self._result, path)

    def _save_csv(self):
        if self._result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "result.csv", "CSV (*.csv)")
        if path:
            export_mod.save_csv(self._result, path)

    def _save_png(self):
        if self._result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save PNG", "result.png", "PNG (*.png)")
        if path:
            export_mod.save_png(self._result_panel.get_figures(), path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
