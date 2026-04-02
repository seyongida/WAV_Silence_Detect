"""현대적 UI의 오디오 품질 분석기 메인 윈도우."""

import math
import os
import sys

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

import analyzer as analyzer_mod
import export as export_mod
from errors import AudioAnalyzerError
from models import AnalysisMessage, AnalysisResult


# ── 색상 팔레트 ────────────────────────────────────────────────────────────────
class Colors:
    BG = "#1a1b2e"
    SURFACE = "#232540"
    CARD = "#2a2d4a"
    CARD_HOVER = "#323660"
    BORDER = "#3d4166"
    TEXT = "#e8eaf6"
    TEXT_DIM = "#9a9cc0"
    TEXT_MUTED = "#6b6e94"
    ACCENT = "#6c63ff"
    ACCENT_HOVER = "#7b73ff"
    SUCCESS = "#4caf50"
    WARNING = "#ff9800"
    ERROR = "#f44336"
    PAIR1 = "#42a5f5"
    PAIR2 = "#ab47bc"
    REF_COLOR = "#42a5f5"
    DIF_COLOR = "#ff9800"
    FALSE_SILENCE = "#f44336"
    LEAKAGE = "#ffeb3b"


GLOBAL_STYLE = f"""
QWidget {{
    background-color: {Colors.BG};
    color: {Colors.TEXT};
    font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
    font-size: 13px;
}}
QMainWindow {{
    background-color: {Colors.BG};
}}
QScrollArea {{
    border: none;
    background-color: {Colors.BG};
}}
QScrollBar:vertical {{
    background: {Colors.SURFACE};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {Colors.BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {Colors.TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: {Colors.SURFACE};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {Colors.BORDER};
    border-radius: 4px;
    min-width: 30px;
}}
QPushButton {{
    background-color: {Colors.ACCENT};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {Colors.ACCENT_HOVER};
}}
QPushButton:disabled {{
    background-color: {Colors.BORDER};
    color: {Colors.TEXT_MUTED};
}}
QPushButton[flat="true"] {{
    background-color: transparent;
    border: 1px solid {Colors.BORDER};
    color: {Colors.TEXT};
}}
QPushButton[flat="true"]:hover {{
    background-color: {Colors.CARD};
    border-color: {Colors.ACCENT};
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {Colors.SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {Colors.TEXT};
    min-height: 24px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {Colors.ACCENT};
}}
QTableWidget {{
    background-color: {Colors.SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    gridline-color: {Colors.BORDER};
    color: {Colors.TEXT};
}}
QTableWidget::item {{
    padding: 6px 10px;
}}
QTableWidget::item:selected {{
    background-color: {Colors.ACCENT};
}}
QHeaderView::section {{
    background-color: {Colors.CARD};
    color: {Colors.TEXT};
    border: none;
    border-bottom: 2px solid {Colors.ACCENT};
    padding: 8px 10px;
    font-weight: 600;
    font-size: 12px;
}}
QTextEdit {{
    background-color: {Colors.SURFACE};
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    color: {Colors.TEXT};
    padding: 6px;
}}
QProgressBar {{
    background-color: {Colors.SURFACE};
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {Colors.ACCENT};
    border-radius: 4px;
}}
QTabWidget::pane {{
    border: 1px solid {Colors.BORDER};
    border-radius: 6px;
    background-color: {Colors.BG};
    top: -1px;
}}
QTabBar::tab {{
    background-color: {Colors.SURFACE};
    color: {Colors.TEXT_DIM};
    border: 1px solid {Colors.BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 2px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background-color: {Colors.BG};
    color: {Colors.ACCENT};
    border-bottom: 2px solid {Colors.ACCENT};
}}
QTabBar::tab:hover {{
    color: {Colors.TEXT};
    background-color: {Colors.CARD};
}}
QSplitter::handle {{
    background-color: {Colors.BORDER};
    width: 1px;
}}
"""

# matplotlib 다크 테마
MPL_STYLE = {
    "figure.facecolor": Colors.CARD,
    "axes.facecolor": Colors.SURFACE,
    "axes.edgecolor": Colors.BORDER,
    "axes.labelcolor": Colors.TEXT,
    "text.color": Colors.TEXT,
    "xtick.color": Colors.TEXT_DIM,
    "ytick.color": Colors.TEXT_DIM,
    "grid.color": Colors.BORDER,
    "grid.alpha": 0.3,
}


def _apply_mpl_style():
    for k, v in MPL_STYLE.items():
        plt.rcParams[k] = v


_apply_mpl_style()


# ── 카드 위젯 헬퍼 ─────────────────────────────────────────────────────────────

def _card(title: str = "", parent_layout: QVBoxLayout | None = None) -> tuple[QFrame, QVBoxLayout]:
    """둥근 모서리 카드 프레임 생성"""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {Colors.CARD};
            border: 1px solid {Colors.BORDER};
            border-radius: 10px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 12, 16, 12)
    layout.setSpacing(8)
    if title:
        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {Colors.TEXT}; border: none;")
        layout.addWidget(lbl)
    if parent_layout is not None:
        parent_layout.addWidget(frame)
    return frame, layout


def _stat_widget(value: str, label: str, color: str = Colors.ACCENT) -> QFrame:
    """큰 숫자 + 라벨 통계 위젯"""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {Colors.SURFACE};
            border: 1px solid {Colors.BORDER};
            border-radius: 8px;
            padding: 8px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(12, 8, 12, 8)
    layout.setSpacing(2)
    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(f"font-size: 26px; font-weight: 800; color: {color}; border: none;")
    val_lbl.setAlignment(Qt.AlignCenter)
    val_lbl.setObjectName("stat_value")
    layout.addWidget(val_lbl)
    desc_lbl = QLabel(label)
    desc_lbl.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_DIM}; border: none;")
    desc_lbl.setAlignment(Qt.AlignCenter)
    layout.addWidget(desc_lbl)
    return frame


# ── 분석 워커 ──────────────────────────────────────────────────────────────────

class AnalysisWorker(QThread):
    """단일 페어 분석 워커"""
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
                self.ref_path, self.dif_path, self.config,
                progress_callback=lambda p, t: self.progress.emit(p, t),
            )
            self.finished.emit(result)
        except AudioAnalyzerError as e:
            self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            self.error.emit(str(e))


class DualAnalysisWorker(QThread):
    """두 페어를 순차 분석하는 워커"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object, object)
    error = pyqtSignal(str)

    def __init__(self, ref1: str, dif1: str, ref2: str, dif2: str, config):
        super().__init__()
        self.ref1, self.dif1 = ref1, dif1
        self.ref2, self.dif2 = ref2, dif2
        self.config = config

    def run(self):
        try:
            r1 = analyzer_mod.run_analysis(
                self.ref1, self.dif1, self.config,
                progress_callback=lambda p, t: self.progress.emit(p // 2, f"[Pair 1] {t}"),
            )
            r2 = analyzer_mod.run_analysis(
                self.ref2, self.dif2, self.config,
                progress_callback=lambda p, t: self.progress.emit(50 + p // 2, f"[Pair 2] {t}"),
            )
            self.finished.emit(r1, r2)
        except AudioAnalyzerError as e:
            self.error.emit(f"[{e.code}] {e.message}")
        except Exception as e:
            self.error.emit(str(e))



# ── 파일 선택 패널 ─────────────────────────────────────────────────────────────

class FilePairWidget(QFrame):
    """ref/dif 한 쌍의 파일 선택 위젯"""

    def __init__(self, pair_label: str, accent_color: str, parent=None):
        super().__init__(parent)
        self._ref_path = ""
        self._dif_path = ""
        self._accent = accent_color
        self._init_ui(pair_label)

    def _init_ui(self, pair_label: str):
        self.setStyleSheet(f"""
            FilePairWidget {{
                background-color: {Colors.CARD};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)

        header = QLabel(f"  {pair_label}")
        header.setStyleSheet(f"""
            font-size: 14px; font-weight: 700; color: {self._accent};
            border: none;
        """)
        layout.addWidget(header)

        # ref 행
        ref_row = QHBoxLayout()
        ref_tag = QLabel("REF")
        ref_tag.setFixedWidth(36)
        ref_tag.setAlignment(Qt.AlignCenter)
        ref_tag.setStyleSheet(f"""
            background-color: {Colors.REF_COLOR}; color: white;
            border-radius: 4px; font-size: 10px; font-weight: 700;
            padding: 2px 0px; border: none;
        """)
        self._ref_label = QLabel("파일을 선택하세요")
        self._ref_label.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 12px; border: none;")
        self._ref_label.setWordWrap(True)
        ref_btn = QPushButton("선택")
        ref_btn.setFixedWidth(60)
        ref_btn.setProperty("flat", True)
        ref_btn.clicked.connect(self._select_ref)
        ref_row.addWidget(ref_tag)
        ref_row.addWidget(self._ref_label, 1)
        ref_row.addWidget(ref_btn)
        layout.addLayout(ref_row)

        # dif 행
        dif_row = QHBoxLayout()
        dif_tag = QLabel("DIF")
        dif_tag.setFixedWidth(36)
        dif_tag.setAlignment(Qt.AlignCenter)
        dif_tag.setStyleSheet(f"""
            background-color: {Colors.DIF_COLOR}; color: white;
            border-radius: 4px; font-size: 10px; font-weight: 700;
            padding: 2px 0px; border: none;
        """)
        self._dif_label = QLabel("파일을 선택하세요")
        self._dif_label.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 12px; border: none;")
        self._dif_label.setWordWrap(True)
        dif_btn = QPushButton("선택")
        dif_btn.setFixedWidth(60)
        dif_btn.setProperty("flat", True)
        dif_btn.clicked.connect(self._select_dif)
        dif_row.addWidget(dif_tag)
        dif_row.addWidget(self._dif_label, 1)
        dif_row.addWidget(dif_btn)
        layout.addLayout(dif_row)

    def _select_ref(self):
        path, _ = QFileDialog.getOpenFileName(self, "REF WAV 선택", "", "WAV (*.wav)")
        if path:
            self._ref_path = path
            self._ref_label.setText(os.path.basename(path))
            self._ref_label.setToolTip(path)
            self._ref_label.setStyleSheet(f"color: {Colors.TEXT}; font-size: 12px; border: none;")

    def _select_dif(self):
        path, _ = QFileDialog.getOpenFileName(self, "DIF WAV 선택", "", "WAV (*.wav)")
        if path:
            self._dif_path = path
            self._dif_label.setText(os.path.basename(path))
            self._dif_label.setToolTip(path)
            self._dif_label.setStyleSheet(f"color: {Colors.TEXT}; font-size: 12px; border: none;")

    def get_ref_path(self) -> str:
        return self._ref_path

    def get_dif_path(self) -> str:
        return self._dif_path

    def has_files(self) -> bool:
        return bool(self._ref_path and self._dif_path)

    def set_paths(self, ref: str, dif: str):
        if ref and os.path.exists(ref):
            self._ref_path = ref
            self._ref_label.setText(os.path.basename(ref))
            self._ref_label.setToolTip(ref)
            self._ref_label.setStyleSheet(f"color: {Colors.TEXT}; font-size: 12px; border: none;")
        if dif and os.path.exists(dif):
            self._dif_path = dif
            self._dif_label.setText(os.path.basename(dif))
            self._dif_label.setToolTip(dif)
            self._dif_label.setStyleSheet(f"color: {Colors.TEXT}; font-size: 12px; border: none;")


class FilePanel(QWidget):
    """파일 선택 영역 (Pair 1 + Pair 2)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        info = QLabel("WAV 파일 | 모노/스테레오 지원 | 권장 길이 10분 이내")
        info.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(info)

        # Pair 1 / Pair 2 가로 나란히 배치
        pair_row = QHBoxLayout()
        pair_row.setSpacing(10)
        self.pair1 = FilePairWidget("Pair 1", Colors.PAIR1)
        self.pair2 = FilePairWidget("Pair 2 (선택)", Colors.PAIR2)
        pair_row.addWidget(self.pair1)
        pair_row.addWidget(self.pair2)
        layout.addLayout(pair_row)

        # 기본 샘플 파일 로드
        sample_ref = os.path.join("sample_audio", "ref.wav")
        sample_dif = os.path.join("sample_audio", "dif_2+shift.wav")
        self.pair1.set_paths(sample_ref, sample_dif)

    def get_pair1(self) -> tuple[str, str]:
        return self.pair1.get_ref_path(), self.pair1.get_dif_path()

    def get_pair2(self) -> tuple[str, str]:
        return self.pair2.get_ref_path(), self.pair2.get_dif_path()

    def has_pair1(self) -> bool:
        return self.pair1.has_files()

    def has_pair2(self) -> bool:
        return self.pair2.has_files()


# ── 파라미터 패널 ──────────────────────────────────────────────────────────────

class ParamPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        spin_style = f"""
            QSpinBox, QDoubleSpinBox {{
                background-color: {Colors.SURFACE};
                color: {Colors.TEXT};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 2px 4px;
            }}
        """
        tip_style = f"color: {Colors.TEXT_DIM}; font-size: 10px; border: none; padding: 0px;"
        lbl_style = f"color: {Colors.TEXT}; font-size: 12px; font-weight: 500; border: none;"

        def _make_group(title: str) -> tuple[QFrame, QGridLayout]:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {Colors.CARD};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 8px;
                }}
            """)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 12)
            cl.setSpacing(6)
            t = QLabel(title)
            t.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {Colors.ACCENT}; border: none;")
            cl.addWidget(t)
            g = QGridLayout()
            g.setSpacing(4)
            g.setColumnStretch(1, 1)
            g.setColumnStretch(3, 1)
            cl.addLayout(g)
            return card, g

        def _label(text):
            l = QLabel(text)
            l.setStyleSheet(lbl_style)
            l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return l

        def _tip(text):
            l = QLabel(text)
            l.setStyleSheet(tip_style)
            l.setWordWrap(True)
            return l

        def _add_param(grid, row, col, label_text, widget, tip_text):
            """파라미터 1개를 그리드에 추가 (라벨 + 위젯 + 설명)."""
            c = col * 3
            grid.addWidget(_label(label_text), row * 2, c, 1, 1)
            widget.setStyleSheet(spin_style)
            widget.setFixedWidth(80)
            grid.addWidget(widget, row * 2, c + 1, 1, 1)
            grid.addWidget(_tip(tip_text), row * 2 + 1, c, 1, 2)

        # ── VAD / 묵음 검출 그룹 ──
        vad_card, vad_grid = _make_group("🔇 VAD / 묵음 검출")

        self._frame_ms = QSpinBox(); self._frame_ms.setRange(5, 100); self._frame_ms.setValue(20)
        self._hop_ms = QSpinBox(); self._hop_ms.setRange(1, 100); self._hop_ms.setValue(10)
        self._noise_floor = QDoubleSpinBox(); self._noise_floor.setRange(0, 100); self._noise_floor.setValue(15)
        self._energy_margin = QDoubleSpinBox(); self._energy_margin.setRange(0, 50); self._energy_margin.setValue(10)
        self._vad_aggressiveness = QSpinBox(); self._vad_aggressiveness.setRange(0, 3); self._vad_aggressiveness.setValue(2)
        self._zcr_threshold = QDoubleSpinBox(); self._zcr_threshold.setRange(0, 1); self._zcr_threshold.setDecimals(3); self._zcr_threshold.setSingleStep(0.01); self._zcr_threshold.setValue(0.1)
        self._min_silence_ms = QSpinBox(); self._min_silence_ms.setRange(1, 2000); self._min_silence_ms.setValue(200)
        self._silence_merge_ms = QSpinBox(); self._silence_merge_ms.setRange(0, 1000); self._silence_merge_ms.setValue(50)

        _add_param(vad_grid, 0, 0, "Frame (ms)", self._frame_ms,
                   "분석 프레임 길이")
        _add_param(vad_grid, 0, 1, "Hop (ms)", self._hop_ms,
                   "프레임 이동 간격")
        _add_param(vad_grid, 1, 0, "Noise floor %", self._noise_floor,
                   "에너지 하위 백분위수로 잡음 바닥 추정")
        _add_param(vad_grid, 1, 1, "Energy margin (dB)", self._energy_margin,
                   "잡음 바닥 위 묵음 판정 마진")
        _add_param(vad_grid, 2, 0, "VAD aggressiveness", self._vad_aggressiveness,
                   "WebRTC VAD 민감도 (0=관대, 3=엄격)")
        _add_param(vad_grid, 2, 1, "ZCR threshold", self._zcr_threshold,
                   "영교차율 묵음 판정 임계값")
        _add_param(vad_grid, 3, 0, "Min silence (ms)", self._min_silence_ms,
                   "이보다 짧은 묵음 구간 무시")
        _add_param(vad_grid, 3, 1, "Silence merge (ms)", self._silence_merge_ms,
                   "이보다 가까운 묵음 구간 병합")

        layout.addWidget(vad_card)

        # ── 이상 검출 그룹 ──
        anomaly_card, anomaly_grid = _make_group("⚡ 이상 검출 (묵음/깨짐)")

        self._speech_strong_rms = QDoubleSpinBox(); self._speech_strong_rms.setRange(0.001, 0.5); self._speech_strong_rms.setDecimals(3); self._speech_strong_rms.setSingleStep(0.005); self._speech_strong_rms.setValue(0.03)
        self._zero_peak_threshold = QDoubleSpinBox(); self._zero_peak_threshold.setRange(0.0001, 0.01); self._zero_peak_threshold.setDecimals(4); self._zero_peak_threshold.setSingleStep(0.0001); self._zero_peak_threshold.setValue(0.0005)
        self._gain_drop_ratio = QDoubleSpinBox(); self._gain_drop_ratio.setRange(0.1, 0.9); self._gain_drop_ratio.setDecimals(2); self._gain_drop_ratio.setSingleStep(0.05); self._gain_drop_ratio.setValue(0.4)
        self._gain_drop_ratio_strict = QDoubleSpinBox(); self._gain_drop_ratio_strict.setRange(0.1, 0.9); self._gain_drop_ratio_strict.setDecimals(2); self._gain_drop_ratio_strict.setSingleStep(0.05); self._gain_drop_ratio_strict.setValue(0.35)
        self._gain_drop_min_corr = QDoubleSpinBox(); self._gain_drop_min_corr.setRange(0.0, 1.0); self._gain_drop_min_corr.setDecimals(2); self._gain_drop_min_corr.setSingleStep(0.05); self._gain_drop_min_corr.setValue(0.3)
        self._prior_activity = QDoubleSpinBox(); self._prior_activity.setRange(0.001, 0.1); self._prior_activity.setDecimals(3); self._prior_activity.setSingleStep(0.005); self._prior_activity.setValue(0.01)
        self._min_anomaly_ms = QSpinBox(); self._min_anomaly_ms.setRange(10, 500); self._min_anomaly_ms.setValue(50)
        self._min_anomaly_b_ms = QSpinBox(); self._min_anomaly_b_ms.setRange(10, 500); self._min_anomaly_b_ms.setValue(120)
        self._anomaly_gap_frames = QSpinBox(); self._anomaly_gap_frames.setRange(0, 10); self._anomaly_gap_frames.setValue(3)

        _add_param(anomaly_grid, 0, 0, "Speech RMS", self._speech_strong_rms,
                   "ref 확실한 음성 판정 RMS 임계값")
        _add_param(anomaly_grid, 0, 1, "Zero peak", self._zero_peak_threshold,
                   "dif 디지털 제로 판정 peak 임계값")
        _add_param(anomaly_grid, 1, 0, "Drop ratio A", self._gain_drop_ratio,
                   "깨짐 A: 주변 대비 ratio 임계값")
        _add_param(anomaly_grid, 1, 1, "Drop ratio B", self._gain_drop_ratio_strict,
                   "깨짐 B: 더 엄격한 ratio 임계값")
        _add_param(anomaly_grid, 2, 0, "Min corr A", self._gain_drop_min_corr,
                   "깨짐 A: 최소 파형 상관계수")
        _add_param(anomaly_grid, 2, 1, "Prior activity", self._prior_activity,
                   "직전 dif 활성 판정 peak (전환 구간 오탐 제외)")
        _add_param(anomaly_grid, 3, 0, "Min anomaly (ms)", self._min_anomaly_ms,
                   "묵음/깨짐 A 최소 지속 시간")
        _add_param(anomaly_grid, 3, 1, "Min anomaly B (ms)", self._min_anomaly_b_ms,
                   "깨짐 B 최소 지속 시간")
        _add_param(anomaly_grid, 4, 0, "Gap frames B", self._anomaly_gap_frames,
                   "깨짐 B gap 허용 프레임 수")

        layout.addWidget(anomaly_card)

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
            speech_strong_rms=self._speech_strong_rms.value(),
            zero_peak_threshold=self._zero_peak_threshold.value(),
            gain_drop_ratio=self._gain_drop_ratio.value(),
            gain_drop_ratio_strict=self._gain_drop_ratio_strict.value(),
            gain_drop_min_corr=self._gain_drop_min_corr.value(),
            prior_activity_threshold=self._prior_activity.value(),
            min_anomaly_ms=self._min_anomaly_ms.value(),
            min_anomaly_b_ms=self._min_anomaly_b_ms.value(),
            anomaly_gap_frames=self._anomaly_gap_frames.value(),
        )

    def validate(self) -> list[str]:
        return analyzer_mod.validate_config(self.get_config())


# ── 로그 패널 ──────────────────────────────────────────────────────────────────

class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel("분석 로그")
        lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_DIM};")
        layout.addWidget(lbl)
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumHeight(100)
        layout.addWidget(self._text)

    def append_message(self, msg: AnalysisMessage) -> None:
        color_map = {"warn": Colors.WARNING, "error": Colors.ERROR, "info": Colors.TEXT_DIM}
        color = color_map.get(msg.level, Colors.TEXT)
        self._text.append(f'<span style="color:{color}">[{msg.level.upper()}] {msg.message}</span>')

    def clear(self) -> None:
        self._text.clear()


# ── 단일 결과 패널 ─────────────────────────────────────────────────────────────

class SingleResultPanel(QWidget):
    """한 페어의 분석 결과를 표시하는 패널"""

    def __init__(self, pair_label: str = "", parent=None):
        super().__init__(parent)
        self._result: AnalysisResult | None = None
        self._pair_label = pair_label
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        outer.addWidget(scroll)

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setSpacing(12)
        self._layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(container)

        # 핵심 요약 통계 카드
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._stat_dif_count = _stat_widget("-", "dif-only 음성 깨짐 수", Colors.ERROR)
        self._stat_dif_total = _stat_widget("-", "dif-only 깨짐 (ms)", Colors.WARNING)
        stats_row.addWidget(self._stat_dif_count)
        stats_row.addWidget(self._stat_dif_total)
        self._layout.addLayout(stats_row)

        # dif-only 이벤트 테이블
        _, tbl_layout = _card("dif-only 이벤트", self._layout)
        self._dif_only_table = QTableWidget(0, 5)
        self._dif_only_table.setHorizontalHeaderLabels(["#", "구분", "길이 (ms)", "시작 (s)", "종료 (s)"])
        self._dif_only_table.verticalHeader().setVisible(False)
        self._dif_only_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._dif_only_table.setMaximumHeight(200)
        tbl_layout.addWidget(self._dif_only_table)

        # 지표 요약 텍스트
        _, info_layout = _card("분석 지표", self._layout)
        self._metrics_label = QLabel("분석 결과가 여기에 표시됩니다.")
        self._metrics_label.setWordWrap(True)
        self._metrics_label.setStyleSheet(f"color: {Colors.TEXT}; font-size: 12px; line-height: 1.6; border: none;")
        info_layout.addWidget(self._metrics_label)

        # 지표 테이블 (스크롤 없이 전체 표시)
        _, mtbl_layout = _card("상세 지표", self._layout)
        self._metric_table = QTableWidget(0, 4)
        self._metric_table.setHorizontalHeaderLabels(["지표", "값", "참고 범위", "해석"])
        self._metric_table.verticalHeader().setVisible(False)
        self._metric_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._metric_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._metric_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        mtbl_layout.addWidget(self._metric_table)

        # 차트들
        self._waveform_fig, self._waveform_ax = plt.subplots(2, 1, figsize=(10, 3.5), sharex=True)
        self._waveform_canvas = FigureCanvas(self._waveform_fig)
        self._layout.addWidget(self._waveform_canvas)

        self._diff_fig, self._diff_ax = plt.subplots(1, 1, figsize=(10, 2))
        self._diff_canvas = FigureCanvas(self._diff_fig)
        self._layout.addWidget(self._diff_canvas)

        self._normdiff_fig, self._normdiff_ax = plt.subplots(1, 1, figsize=(10, 2))
        self._normdiff_canvas = FigureCanvas(self._normdiff_fig)
        self._layout.addWidget(self._normdiff_canvas)

        self._spec_fig, self._spec_axes = plt.subplots(2, 1, figsize=(10, 3.5), sharex=True)
        self._spec_canvas = FigureCanvas(self._spec_fig)
        self._layout.addWidget(self._spec_canvas)

        self._ts_fig, self._ts_axes = plt.subplots(2, 1, figsize=(10, 2.8), sharex=True)
        self._ts_canvas = FigureCanvas(self._ts_fig)
        self._layout.addWidget(self._ts_canvas)

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
        self._stat_dif_count.findChild(QLabel, "stat_value").setText(str(sm.dif_silence_count))
        self._stat_dif_total.findChild(QLabel, "stat_value").setText(f"{sm.dif_total_silence_ms:.0f}")

        # anomaly_segments + false_silence_segments 통합 이벤트 테이블
        events: list[tuple[str, float, float, float]] = []

        # anomaly_segments에서 이벤트 수집
        for seg in r.anomaly_segments:
            if seg.anomaly_type == "digital_zero":
                label = "묵음"
            elif seg.anomaly_type == "gain_drop":
                label = "깨짐"
            else:
                label = "깨짐"
            events.append((label, seg.duration_ms, seg.start_ms, seg.end_ms))

        # anomaly가 비어있으면 false_silence_segments 폴백
        if not events:
            for seg in r.false_silence_segments:
                events.append(("묵음", seg.duration_ms, seg.start_ms, seg.end_ms))

        events.sort(key=lambda x: x[2])

        self._dif_only_table.setRowCount(len(events))
        for i, (label, dur, start, end) in enumerate(events):
            self._dif_only_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            item_label = QTableWidgetItem(label)
            if label == "깨짐":
                item_label.setForeground(QColor(Colors.ERROR))
            else:
                item_label.setForeground(QColor(Colors.WARNING))
            self._dif_only_table.setItem(i, 1, item_label)
            self._dif_only_table.setItem(i, 2, QTableWidgetItem(f"{dur:.1f}"))
            self._dif_only_table.setItem(i, 3, QTableWidgetItem(f"{start / 1000:.3f}"))
            self._dif_only_table.setItem(i, 4, QTableWidgetItem(f"{end / 1000:.3f}"))

    def _update_metrics_label(self):
        r = self._result
        if r is None:
            return
        sm = r.silence_metrics
        d = r.delay

        # anomaly 요약
        n_zero = sum(1 for s in r.anomaly_segments if s.anomaly_type == "digital_zero")
        n_gain = sum(1 for s in r.anomaly_segments if s.anomaly_type == "gain_drop")
        anomaly_text = f"<b>이상 검출:</b> 묵음 {n_zero}건, 깨짐 {n_gain}건"

        self._metrics_label.setText(
            f"<b>Delay:</b> {d.applied_delay_ms:.1f} ms "
            f"(coarse: {d.coarse_delay_ms:.1f}, refined: {d.refined_delay_ms:.1f}, DTW: {d.dtw_used})<br>"
            f"{anomaly_text}<br>"
            f"<b>SNR:</b> {self._fmt(r.snr_db)} dB &nbsp; "
            f"<b>PESQ:</b> {self._fmt(r.pesq_score)} &nbsp; "
            f"<b>STOI:</b> {self._fmt(r.stoi_score)}<br>"
            f"<b>RMS diff:</b> {self._fmt(r.rms_diff_db)} dB &nbsp; "
            f"<b>Clipping:</b> {self._fmt(r.clipping_ratio)}<br>"
            f"<b>ref NF:</b> {self._fmt(r.ref_noise_floor_db)} dB &nbsp; "
            f"<b>dif NF:</b> {self._fmt(r.dif_noise_floor_db)} dB"
        )

    def _update_metric_table(self):
        r = self._result
        if r is None:
            return
        sm = r.silence_metrics
        n_zero = sum(1 for s in r.anomaly_segments if s.anomaly_type == "digital_zero")
        n_gain = sum(1 for s in r.anomaly_segments if s.anomaly_type == "gain_drop")
        rows = [
            ("이상 검출 (묵음)", str(n_zero), "0 = 정상", "dif에서 디지털 제로 구간 수"),
            ("이상 검출 (깨짐)", str(n_gain), "0 = 정상", "dif에서 gain 변조 구간 수"),
            ("이상 총 시간 (ms)", f"{sm.dif_total_silence_ms:.0f}", "0 = 정상", "이상 구간 총 지속 시간"),
            ("SNR (dB)", self._fmt(r.snr_db), ">20 good, >30 very good", "높을수록 좋음"),
            ("PESQ", self._fmt(r.pesq_score), "1.0 ~ 4.5", "높을수록 음질 좋음"),
            ("STOI", self._fmt(r.stoi_score), "0.0 ~ 1.0", "높을수록 명료도 좋음"),
            ("RMS diff (dB)", self._fmt(r.rms_diff_db), "0 dB 근처", "0에 가까울수록 유사"),
            ("Clipping", self._fmt(r.clipping_ratio), "0.0 ~ 1.0", "0에 가까울수록 좋음"),
            ("ref NF (dB)", self._fmt(r.ref_noise_floor_db), "-100 ~ -20", "낮을수록 조용"),
            ("dif NF (dB)", self._fmt(r.dif_noise_floor_db), "-100 ~ -20", "ref와 비교"),
        ]
        self._metric_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self._metric_table.setItem(i, j, item)
        # 행 수에 맞게 테이블 높이 자동 조절 (스크롤 제거)
        header_h = self._metric_table.horizontalHeader().height()
        row_h = sum(self._metric_table.rowHeight(i) for i in range(len(rows)))
        self._metric_table.setFixedHeight(header_h + row_h + 4)

    def _cfg(self, name: str, default_value: float) -> float:
        if self._result is None:
            return default_value
        return float(getattr(self._result.config, name, default_value))

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

        # 파형
        for ax in self._waveform_ax:
            ax.cla()
        self._waveform_ax[0].plot(t, ref_common, linewidth=0.4, color=Colors.REF_COLOR)
        self._waveform_ax[0].set_title("ref", fontsize=10, color=Colors.TEXT)
        self._waveform_ax[0].set_ylabel("Amp", fontsize=9)
        self._waveform_ax[1].plot(t, dif_common, linewidth=0.4, color=Colors.DIF_COLOR)
        self._waveform_ax[1].set_title("dif (delay-corrected)", fontsize=10, color=Colors.TEXT)
        self._waveform_ax[1].set_ylabel("Amp", fontsize=9)
        self._waveform_ax[1].set_xlabel("Time (s)", fontsize=9)

        # ref 기준으로 y축 범위 통일
        ref_ylim = self._waveform_ax[0].get_ylim()
        self._waveform_ax[1].set_ylim(ref_ylim)

        # anomaly_segments만 음영 (묵음=빨강, 깨짐=노랑)
        for seg in r.anomaly_segments:
            color = Colors.FALSE_SILENCE if seg.anomaly_type == "digital_zero" else Colors.LEAKAGE
            alpha = 0.30 if seg.anomaly_type == "digital_zero" else 0.25
            for ax in self._waveform_ax:
                ax.axvspan(seg.start_ms / 1000, seg.end_ms / 1000, alpha=alpha, color=color)
        self._waveform_fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.13, hspace=0.30)
        self._waveform_canvas.draw()

        # 잔차
        self._diff_ax.cla()
        residual = ref_common - dif_common
        self._diff_ax.plot(t, residual, color="#7c3aed", linewidth=0.5)
        self._diff_ax.axhline(0, color=Colors.TEXT_MUTED, linewidth=0.5, alpha=0.5)
        self._diff_ax.set_title("Residual (ref - dif)", fontsize=10, color=Colors.TEXT)
        self._diff_ax.set_xlabel("Time (s)", fontsize=9)
        self._diff_ax.set_ylabel("Amp", fontsize=9)
        self._diff_fig.subplots_adjust(left=0.07, right=0.98, top=0.88, bottom=0.22)
        self._diff_canvas.draw()

        # 음량 정규화 잔차 (dif 음량을 ref에 맞춘 뒤 ref - dif_scaled)
        self._normdiff_ax.cla()
        ref_rms = np.sqrt(np.mean(ref_common ** 2))
        dif_rms = np.sqrt(np.mean(dif_common ** 2))
        if dif_rms > 1e-12:
            gain = ref_rms / dif_rms
        else:
            gain = 1.0
        dif_scaled = dif_common * gain
        norm_residual = ref_common - dif_scaled
        # 볼륨 차이를 dB로 계산 (ref 기준 dif가 얼마나 크거나 작은지)
        if ref_rms > 1e-12 and dif_rms > 1e-12:
            vol_diff_db = 20 * np.log10(dif_rms / ref_rms)
        else:
            vol_diff_db = 0.0
        self._normdiff_ax.plot(t, norm_residual, color="#0ea5e9", linewidth=0.5)
        self._normdiff_ax.axhline(0, color=Colors.TEXT_MUTED, linewidth=0.5, alpha=0.5)
        sign = "+" if vol_diff_db >= 0 else ""
        # dif가 ref의 몇 배인지 (소수점 둘째 자리 올림)
        vol_ratio = dif_rms / ref_rms if ref_rms > 1e-12 else 0.0
        vol_ratio_ceil = math.ceil(vol_ratio * 100) / 100
        self._normdiff_ax.set_title(
            f"Residual – Volume Normalized (dif = {vol_ratio_ceil:.2f}× ref, {sign}{vol_diff_db:.2f} dB)",
            fontsize=10, color=Colors.TEXT,
        )
        self._normdiff_ax.set_xlabel("Time (s)", fontsize=9)
        self._normdiff_ax.set_ylabel("Amp", fontsize=9)
        self._normdiff_fig.subplots_adjust(left=0.07, right=0.98, top=0.88, bottom=0.22)
        self._normdiff_canvas.draw()

        # 스펙트로그램
        for ax in self._spec_axes:
            ax.cla()
        if r.spectrum is not None:
            ref_spec = r.spectrum.ref_spectrogram
            dif_spec = r.spectrum.dif_spectrogram
            self._spec_axes[0].pcolormesh(ref_spec.times, ref_spec.frequencies, ref_spec.magnitude_db, shading="auto", cmap="magma")
            self._spec_axes[0].set_title("ref spectrogram", fontsize=10, color=Colors.TEXT)
            self._spec_axes[0].set_ylabel("Freq (Hz)", fontsize=9)
            self._spec_axes[1].pcolormesh(dif_spec.times, dif_spec.frequencies, dif_spec.magnitude_db, shading="auto", cmap="magma")
            self._spec_axes[1].set_title("dif spectrogram", fontsize=10, color=Colors.TEXT)
            self._spec_axes[1].set_ylabel("Freq (Hz)", fontsize=9)
            self._spec_axes[1].set_xlabel("Time (s)", fontsize=9)
        else:
            for ax in self._spec_axes:
                ax.text(0.5, 0.5, "N/A", ha="center", va="center", transform=ax.transAxes, color=Colors.TEXT_MUTED)
        self._spec_fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.13, hspace=0.30)
        self._spec_canvas.draw()

        # 스펙트럼 트렌드 (프레임 인덱스 → 시간(초) 변환하여 스펙트로그램과 축 정렬)
        for ax in self._ts_axes:
            ax.cla()
        if r.spectrum is not None:
            sp = r.spectrum
            hop_sec = self._cfg("hop_ms", 10) / 1000.0
            n_frames_c = len(sp.ref_centroid)
            t_centroid = np.arange(n_frames_c) * hop_sec
            n_frames_r = len(sp.ref_rolloff)
            t_rolloff = np.arange(n_frames_r) * hop_sec

            self._ts_axes[0].plot(t_centroid, sp.ref_centroid, label="ref", color=Colors.REF_COLOR, linewidth=0.7)
            self._ts_axes[0].plot(t_centroid[:len(sp.dif_centroid)], sp.dif_centroid, label="dif", color=Colors.DIF_COLOR, linewidth=0.7)
            self._ts_axes[0].set_title("Spectral Centroid", fontsize=10, color=Colors.TEXT)
            self._ts_axes[0].set_ylabel("Hz", fontsize=9)
            self._ts_axes[0].legend(fontsize=8, facecolor=Colors.CARD, edgecolor=Colors.BORDER, labelcolor=Colors.TEXT)

            self._ts_axes[1].plot(t_rolloff, sp.ref_rolloff, label="ref", color=Colors.REF_COLOR, linewidth=0.7)
            self._ts_axes[1].plot(t_rolloff[:len(sp.dif_rolloff)], sp.dif_rolloff, label="dif", color=Colors.DIF_COLOR, linewidth=0.7)
            self._ts_axes[1].set_title("Spectral Rolloff", fontsize=10, color=Colors.TEXT)
            self._ts_axes[1].set_ylabel("Hz", fontsize=9)
            self._ts_axes[1].set_xlabel("Time (s)", fontsize=9)
            self._ts_axes[1].legend(fontsize=8, facecolor=Colors.CARD, edgecolor=Colors.BORDER, labelcolor=Colors.TEXT)

            # 모든 시간축 차트의 x범위를 동일하게 맞춤
            max_time = t[-1] if len(t) > 0 else 0
            for ax in [*self._waveform_ax, self._diff_ax, self._normdiff_ax, *self._spec_axes, *self._ts_axes]:
                ax.set_xlim(0, max_time)
        else:
            for ax in self._ts_axes:
                ax.text(0.5, 0.5, "N/A", ha="center", va="center", transform=ax.transAxes, color=Colors.TEXT_MUTED)
        self._ts_fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.15, hspace=0.35)
        self._ts_canvas.draw()

    def _apply_figure_margins(self):
        self._waveform_fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.13, hspace=0.30)
        self._diff_fig.subplots_adjust(left=0.07, right=0.98, top=0.88, bottom=0.22)
        self._normdiff_fig.subplots_adjust(left=0.07, right=0.98, top=0.88, bottom=0.22)
        self._spec_fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.13, hspace=0.30)
        self._ts_fig.subplots_adjust(left=0.07, right=0.98, top=0.93, bottom=0.15, hspace=0.35)

    def get_figures(self) -> list:
        return [self._waveform_fig, self._diff_fig, self._normdiff_fig, self._spec_fig, self._ts_fig]


# ── 결과 컨테이너 (싱글/듀얼 전환) ────────────────────────────────────────────

class ResultContainer(QWidget):
    """싱글 모드: 1개 ResultPanel, 듀얼 모드: 좌우 2개 ResultPanel"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splitter = QSplitter(Qt.Horizontal)
        self._panel1 = SingleResultPanel("Pair 1")
        self._panel2 = SingleResultPanel("Pair 2")
        self._splitter.addWidget(self._panel1)
        self._splitter.addWidget(self._panel2)
        layout.addWidget(self._splitter)

        # 초기: 싱글 모드
        self._panel2.setVisible(False)

    def show_single(self, result: AnalysisResult):
        self._panel2.setVisible(False)
        self._panel1.update_result(result)

    def show_dual(self, result1: AnalysisResult, result2: AnalysisResult):
        self._panel2.setVisible(True)
        self._splitter.setSizes([500, 500])
        self._panel1.update_result(result1)
        self._panel2.update_result(result2)

    def get_all_figures(self) -> list:
        figs = self._panel1.get_figures()
        if self._panel2.isVisible():
            figs += self._panel2.get_figures()
        return figs

    def get_results(self) -> list[AnalysisResult | None]:
        results = []
        if self._panel1._result is not None:
            results.append(self._panel1._result)
        if self._panel2.isVisible() and self._panel2._result is not None:
            results.append(self._panel2._result)
        return results


# ── 메인 윈도우 ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Quality Analyzer")
        self.resize(1500, 960)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(GLOBAL_STYLE)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(8)

        # 상단 타이틀 바
        title_row = QHBoxLayout()
        app_title = QLabel("Audio Quality Analyzer")
        app_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.ACCENT};")
        title_row.addWidget(app_title)
        title_row.addStretch()
        root.addLayout(title_row)

        # 상단 영역: 파일 선택
        self._file_panel = FilePanel()
        root.addWidget(self._file_panel)

        # 분석 파라미터 (접기/펼치기)
        self._param_toggle_btn = QPushButton("▶  분석 파라미터")
        self._param_toggle_btn.setProperty("flat", True)
        self._param_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {Colors.BORDER};
                color: {Colors.TEXT_DIM};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {Colors.CARD};
                border-color: {Colors.ACCENT};
                color: {Colors.TEXT};
            }}
        """)
        self._param_toggle_btn.clicked.connect(self._toggle_params)
        root.addWidget(self._param_toggle_btn)

        self._param_panel = ParamPanel()
        self._param_panel.setVisible(False)
        root.addWidget(self._param_panel)

        # 버튼 행
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._analyze_btn = QPushButton("▶  분석 시작")
        self._analyze_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT};
                font-size: 14px; font-weight: 700;
                padding: 10px 28px; border-radius: 8px;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_HOVER}; }}
            QPushButton:disabled {{ background-color: {Colors.BORDER}; color: {Colors.TEXT_MUTED}; }}
        """)
        self._analyze_btn.clicked.connect(self._start_analysis)
        btn_row.addWidget(self._analyze_btn)

        for text, slot, name in [
            ("JSON 저장", self._save_json, "_save_json_btn"),
            ("CSV 저장", self._save_csv, "_save_csv_btn"),
            ("PNG 저장", self._save_png, "_save_png_btn"),
            ("HTML 저장", self._save_html, "_save_html_btn"),
        ]:
            btn = QPushButton(text)
            btn.setProperty("flat", True)
            btn.setEnabled(False)
            btn.clicked.connect(slot)
            setattr(self, name, btn)
            btn_row.addWidget(btn)

        btn_row.addStretch()
        root.addLayout(btn_row)

        # 프로그레스
        prog_row = QHBoxLayout()
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(f"color: {Colors.TEXT_DIM}; font-size: 11px;")
        prog_row.addWidget(self._progress_bar, 1)
        prog_row.addWidget(self._progress_label)
        root.addLayout(prog_row)

        # 결과 영역
        self._result_container = ResultContainer()
        root.addWidget(self._result_container, 1)

        # 로그
        self._log_panel = LogPanel()
        root.addWidget(self._log_panel)

    def _toggle_params(self):
        visible = not self._param_panel.isVisible()
        self._param_panel.setVisible(visible)
        arrow = "▼" if visible else "▶"
        self._param_toggle_btn.setText(f"{arrow}  분석 파라미터")

    def _start_analysis(self):
        has1 = self._file_panel.has_pair1()
        has2 = self._file_panel.has_pair2()

        if not has1:
            QMessageBox.warning(self, "파일 선택 필요", "Pair 1의 ref/dif 파일을 모두 선택하세요.")
            return

        errors = self._param_panel.validate()
        if errors:
            QMessageBox.warning(self, "파라미터 오류", "\n".join(errors))
            return

        self._log_panel.clear()
        self._analyze_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)

        config = self._param_panel.get_config()
        ref1, dif1 = self._file_panel.get_pair1()

        if has2:
            ref2, dif2 = self._file_panel.get_pair2()
            self._worker = DualAnalysisWorker(ref1, dif1, ref2, dif2, config)
            self._worker.progress.connect(self._on_progress)
            self._worker.finished.connect(self._on_dual_finished)
            self._worker.error.connect(self._on_error)
            self._worker.start()
        else:
            self._worker = AnalysisWorker(ref1, dif1, config)
            self._worker.progress.connect(self._on_progress)
            self._worker.finished.connect(self._on_single_finished)
            self._worker.error.connect(self._on_error)
            self._worker.start()

    def _on_progress(self, percent: int, text: str):
        self._progress_bar.setValue(percent)
        self._progress_label.setText(text)

    def _on_single_finished(self, result: AnalysisResult):
        self._analyze_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._progress_label.setText("분석 완료")
        self._log_results(result)
        self._result_container.show_single(result)
        self._enable_save_buttons()

    def _on_dual_finished(self, result1: AnalysisResult, result2: AnalysisResult):
        self._analyze_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._progress_label.setText("분석 완료 (2 pairs)")
        self._log_results(result1)
        self._log_results(result2)
        self._result_container.show_dual(result1, result2)
        self._enable_save_buttons()

    def _log_results(self, result: AnalysisResult):
        if result.error_log:
            for msg in result.error_log:
                self._log_panel.append_message(msg)
        else:
            self._log_panel.append_message(
                AnalysisMessage(level="info", message="경고/오류 없음.", timestamp=result.analysis_timestamp)
            )

    def _enable_save_buttons(self):
        self._save_json_btn.setEnabled(True)
        self._save_csv_btn.setEnabled(True)
        self._save_png_btn.setEnabled(True)
        self._save_html_btn.setEnabled(True)

    def _on_error(self, error_msg: str):
        self._analyze_btn.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._progress_label.setText("오류 발생")
        QMessageBox.critical(self, "분석 오류", error_msg)

    def _save_json(self):
        results = self._result_container.get_results()
        if not results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "JSON 저장", "result.json", "JSON (*.json)")
        if path:
            export_mod.save_json(results[0], path)
            if len(results) > 1:
                base, ext = os.path.splitext(path)
                export_mod.save_json(results[1], f"{base}_pair2{ext}")

    def _save_csv(self):
        results = self._result_container.get_results()
        if not results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", "result.csv", "CSV (*.csv)")
        if path:
            export_mod.save_csv(results[0], path)
            if len(results) > 1:
                base, ext = os.path.splitext(path)
                export_mod.save_csv(results[1], f"{base}_pair2{ext}")

    def _save_png(self):
        results = self._result_container.get_results()
        if not results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "PNG 저장", "result.png", "PNG (*.png)")
        if path:
            export_mod.save_png(self._result_container.get_all_figures(), path)

    def _save_html(self):
        results = self._result_container.get_results()
        if not results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "HTML 저장", "report.html", "HTML (*.html)")
        if path:
            # 각 result에 대응하는 figure 리스트 구성
            figs_per_result = [self._result_container._panel1.get_figures()]
            if len(results) > 1:
                figs_per_result.append(self._result_container._panel2.get_figures())
            export_mod.save_html(results, figs_per_result, path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
