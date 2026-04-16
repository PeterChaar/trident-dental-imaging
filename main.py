"""
Trident Dental Imaging Software
Dental X-ray acquisition, viewing, and processing application.
Compatible with TWAIN-based intraoral sensors including Trident I-View.

NOTICE: This software is a viewing and workflow tool.
It is NOT a certified medical device. For primary diagnostic decisions,
use certified software (Trident Deep-View, Dexis, Carestream, etc.).
"""

import sys
import os
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QPushButton, QToolBar, QFileDialog, QDialog,
    QFormLayout, QLineEdit, QTextEdit, QComboBox, QListWidget, QListWidgetItem,
    QGroupBox, QSlider, QMessageBox, QScrollArea, QTabWidget, QDialogButtonBox,
    QDateEdit, QGraphicsView, QGraphicsScene, QInputDialog, QColorDialog,
)
from PyQt6.QtCore import Qt, QSize, QDate, QRectF
from PyQt6.QtGui import (
    QPixmap, QImage, QAction, QPainter, QPen, QColor, QWheelEvent,
    QMouseEvent, QKeySequence, QPalette,
)

import numpy as np
import cv2

import database
import audit_log
import image_processing as ip
from tooth_chart import ToothChartWidget, tooth_name
from fmx_widget import FMXWidget
from annotations import (
    ArrowItem, TextAnnotation, FreehandPath, CircleAnnotation, RectAnnotation,
    TextAnnotationDialog, TOOL_ARROW, TOOL_TEXT, TOOL_FREEHAND, TOOL_CIRCLE, TOOL_RECT,
)
from comparison_view import ComparisonWidget
from print_support import print_image
import dicom_support
import backup
import pdf_report
from odontogram import OdontogramWidget
from magnifier import MagnifierOverlay
from treatment_log import TreatmentLogWidget
from first_run_wizard import FirstRunWizard, needs_first_run
import i18n
from i18n import tr


IMAGE_STORE = os.path.join(os.path.dirname(__file__), "image_store")
ORIGINALS_STORE = os.path.join(IMAGE_STORE, "_originals")
os.makedirs(IMAGE_STORE, exist_ok=True)
os.makedirs(ORIGINALS_STORE, exist_ok=True)


def numpy_to_qpixmap(img):
    img = np.ascontiguousarray(img)
    if len(img.shape) == 2:
        h, w = img.shape
        qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
    else:
        h, w, ch = img.shape
        if ch == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = np.ascontiguousarray(img)
            qimg = QImage(img.data, w, h, w * 3, QImage.Format.Format_RGB888)
        else:
            qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8)
    return QPixmap.fromImage(qimg.copy())


# ─── Image View with Annotations ─────────────────────────────────────────

class DentalImageView(QGraphicsView):
    TOOL_NONE = "none"
    TOOL_MEASURE = "measure"
    TOOL_ARROW = TOOL_ARROW
    TOOL_TEXT = TOOL_TEXT
    TOOL_FREEHAND = TOOL_FREEHAND
    TOOL_CIRCLE = TOOL_CIRCLE
    TOOL_RECT = TOOL_RECT
    TOOL_MAGNIFIER = "magnifier"

    # Default to Trident I-View Silver (0.020 mm/px). User can re-calibrate
    # to 0.018 for Gold via Tools → Calibrate, or DICOM auto-overrides this.
    pixel_spacing_mm = (0.020, 0.020)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.pixmap_item = None
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.current_tool = self.TOOL_NONE
        self._annotations = []
        self._start = None
        self._freehand = None
        self._color = QColor(255, 255, 0)
        self.setMinimumSize(400, 300)
        self._magnifier = MagnifierOverlay()
        self._source_pixmap = None
        self.setMouseTracking(True)

    def set_image(self, pixmap):
        self.scene_.clear()
        self._annotations.clear()
        self._source_pixmap = pixmap
        self._magnifier.set_source(pixmap)
        self.pixmap_item = self.scene_.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, e: QWheelEvent):
        # Mouse wheel uses angleDelta (120 per notch). Mac touchpads often
        # deliver pixelDelta instead (smaller increments, may be 0 on angleDelta).
        # Accumulate whichever is available and zoom proportionally.
        delta = e.angleDelta().y()
        if delta == 0:
            delta = e.pixelDelta().y()
        if delta == 0:
            e.ignore()
            return
        # Scale factor proportional to scroll amount; clamped per-event
        # so a big trackpad swipe doesn't jump wildly.
        step = max(min(abs(delta) / 240.0, 0.5), 0.05)
        factor = (1.0 + step) if delta > 0 else (1.0 - step)
        self._apply_zoom(factor)
        e.accept()

    def _apply_zoom(self, factor):
        # Clamp total scale so the image can't shrink to a dot or balloon forever.
        t = self.transform()
        cur_scale = (t.m11() ** 2 + t.m12() ** 2) ** 0.5
        new_scale = cur_scale * factor
        if new_scale < 0.05 or new_scale > 40.0:
            return
        self.scale(factor, factor)

    def zoom_in(self):
        self._apply_zoom(1.25)

    def zoom_out(self):
        self._apply_zoom(1 / 1.25)

    def zoom_reset(self):
        self.resetTransform()
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def fit_to_view(self):
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def _measure_text(self, a, b):
        dx, dy = b.x() - a.x(), b.y() - a.y()
        px = (dx ** 2 + dy ** 2) ** 0.5
        if self.pixel_spacing_mm:
            mx = dx * self.pixel_spacing_mm[1]
            my = dy * self.pixel_spacing_mm[0]
            mm = (mx ** 2 + my ** 2) ** 0.5
            return f"{mm:.2f} mm"
        return f"{px:.1f} px"

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(e)
        pos = self.mapToScene(e.pos())
        t = self.current_tool

        if t == self.TOOL_MEASURE or t == self.TOOL_ARROW:
            self._start = pos
        elif t == self.TOOL_FREEHAND:
            self._freehand = FreehandPath(self._color, 2)
            self._freehand.add_point(pos)
            self.scene_.addItem(self._freehand)
            self._annotations.append(self._freehand)
        elif t in (self.TOOL_CIRCLE, self.TOOL_RECT):
            self._start = pos
        elif t == self.TOOL_TEXT:
            dlg = TextAnnotationDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.get_text():
                a = TextAnnotation(dlg.get_text(), pos, self._color, dlg.get_size())
                self.scene_.addItem(a)
                self._annotations.append(a)
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent):
        if self.current_tool == self.TOOL_MAGNIFIER and self.pixmap_item:
            self._magnifier.show_at(
                e.globalPosition().toPoint(),
                self.mapToScene(e.pos()),
            )
        if self.current_tool == self.TOOL_FREEHAND and self._freehand:
            self._freehand.add_point(self.mapToScene(e.pos()))
        else:
            super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self.current_tool == self.TOOL_MAGNIFIER:
            self._magnifier.hide_loupe()
        super().leaveEvent(e)

    def deactivate_magnifier(self):
        self._magnifier.hide_loupe()

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() != Qt.MouseButton.LeftButton:
            return super().mouseReleaseEvent(e)
        pos = self.mapToScene(e.pos())
        t = self.current_tool

        if t == self.TOOL_MEASURE and self._start:
            a = self._start
            pen = QPen(QColor(0, 255, 0), 2)
            line = self.scene_.addLine(a.x(), a.y(), pos.x(), pos.y(), pen)
            self._annotations.append(line)
            text = self._measure_text(a, pos)
            lbl = self.scene_.addText(text)
            lbl.setDefaultTextColor(QColor(0, 255, 0))
            lbl.setPos((a.x() + pos.x()) / 2, (a.y() + pos.y()) / 2)
            self._annotations.append(lbl)
            self._start = None
        elif t == self.TOOL_ARROW and self._start:
            a = self._start
            arr = ArrowItem(a.x(), a.y(), pos.x(), pos.y(), self._color, 2)
            self.scene_.addItem(arr)
            self._annotations.append(arr)
            self._start = None
        elif t == self.TOOL_FREEHAND:
            self._freehand = None
        elif t == self.TOOL_CIRCLE and self._start:
            rect = QRectF(self._start, pos).normalized()
            c = CircleAnnotation(rect, self._color, 2)
            self.scene_.addItem(c)
            self._annotations.append(c)
            self._start = None
        elif t == self.TOOL_RECT and self._start:
            rect = QRectF(self._start, pos).normalized()
            r = RectAnnotation(rect, self._color, 2)
            self.scene_.addItem(r)
            self._annotations.append(r)
            self._start = None
        else:
            super().mouseReleaseEvent(e)

    def clear_annotations(self):
        for a in self._annotations:
            self.scene_.removeItem(a)
        self._annotations.clear()

    def undo_last(self):
        if self._annotations:
            self.scene_.removeItem(self._annotations.pop())


# ─── Patient Dialog ──────────────────────────────────────────────────────

class PatientDialog(QDialog):
    def __init__(self, parent=None, patient=None):
        super().__init__(parent)
        self.setWindowTitle("Add Patient" if patient is None else "Edit Patient")
        self.setMinimumWidth(420)
        layout = QFormLayout(self)

        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.dob.setDisplayFormat("yyyy-MM-dd")
        self.dob.setDate(QDate.currentDate())
        self.gender = QComboBox()
        self.gender.addItems(["", "Male", "Female", "Other"])
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.medical_history = QTextEdit()
        self.medical_history.setMaximumHeight(70)
        self.medical_history.setPlaceholderText("Allergies, conditions, medications…")
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)

        layout.addRow("First Name *:", self.first_name)
        layout.addRow("Last Name *:", self.last_name)
        layout.addRow("Date of Birth:", self.dob)
        layout.addRow("Gender:", self.gender)
        layout.addRow("Phone:", self.phone)
        layout.addRow("Email:", self.email)
        layout.addRow("Medical History:", self.medical_history)
        layout.addRow("Notes:", self.notes)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

        if patient:
            self.first_name.setText(patient.get("first_name", ""))
            self.last_name.setText(patient.get("last_name", ""))
            if patient.get("date_of_birth"):
                self.dob.setDate(QDate.fromString(patient["date_of_birth"], "yyyy-MM-dd"))
            g = patient.get("gender") or ""
            idx = self.gender.findText(g)
            if idx >= 0:
                self.gender.setCurrentIndex(idx)
            self.phone.setText(patient.get("phone") or "")
            self.email.setText(patient.get("email") or "")
            self.medical_history.setPlainText(patient.get("medical_history") or "")
            self.notes.setPlainText(patient.get("notes") or "")

    def get_data(self):
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "date_of_birth": self.dob.date().toString("yyyy-MM-dd"),
            "gender": self.gender.currentText() or None,
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "medical_history": self.medical_history.toPlainText().strip(),
            "notes": self.notes.toPlainText().strip(),
        }


class BackupSettingsDialog(QDialog):
    def __init__(self, parent=None, cfg=None):
        super().__init__(parent)
        self.setWindowTitle("Backup & Clinic Settings")
        self.setMinimumWidth(480)
        cfg = cfg or backup.load_config()
        layout = QFormLayout(self)

        self.clinic = QLineEdit(cfg.get("clinic_name", ""))
        self.doctor = QLineEdit(cfg.get("doctor_name", ""))
        self.lang = QComboBox()
        for code, label in i18n.LANGUAGES:
            self.lang.addItem(label, code)
        cur = cfg.get("language", "en")
        for i in range(self.lang.count()):
            if self.lang.itemData(i) == cur:
                self.lang.setCurrentIndex(i)
                break
        layout.addRow("Clinic name:", self.clinic)
        layout.addRow("Doctor name:", self.doctor)
        layout.addRow("Language:", self.lang)

        row = QHBoxLayout()
        self.folder = QLineEdit(cfg.get("backup_folder", ""))
        self.folder.setPlaceholderText("Pick a folder (USB drive recommended)")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.folder)
        row.addWidget(browse)
        w = QWidget()
        w.setLayout(row)
        layout.addRow("Backup folder:", w)

        from PyQt6.QtWidgets import QCheckBox, QSpinBox
        self.auto = QCheckBox("Backup automatically when closing the app")
        self.auto.setChecked(bool(cfg.get("auto_backup_on_close")))
        layout.addRow(self.auto)

        self.keep = QSpinBox()
        self.keep.setRange(1, 100)
        self.keep.setValue(int(cfg.get("keep_last_backups", 10)))
        layout.addRow("Keep last N backups:", self.keep)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choose backup folder")
        if d:
            self.folder.setText(d)

    def get_config(self):
        return {
            "clinic_name": self.clinic.text().strip() or "Dental Clinic",
            "doctor_name": self.doctor.text().strip(),
            "backup_folder": self.folder.text().strip(),
            "auto_backup_on_close": self.auto.isChecked(),
            "keep_last_backups": self.keep.value(),
            "language": self.lang.currentData() or "en",
        }


class CalibrationDialog(QDialog):
    def __init__(self, parent=None, current=None):
        super().__init__(parent)
        self.setWindowTitle("Measurement Calibration")
        layout = QFormLayout(self)
        layout.addRow(QLabel(
            "Pixel spacing in mm:\n"
            "Trident I-View Gold:   0.018 mm/px\n"
            "Trident I-View Silver: 0.020 mm/px\n"
            "(Auto-detected from DICOM files.)"
        ))
        self.sx = QLineEdit()
        self.sy = QLineEdit()
        if current:
            self.sx.setText(str(current[0]))
            self.sy.setText(str(current[1]))
        else:
            self.sx.setText("0.018")
            self.sy.setText("0.018")
        layout.addRow("X (mm/px):", self.sx)
        layout.addRow("Y (mm/px):", self.sy)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addRow(bb)

    def get(self):
        try:
            return (float(self.sx.text()), float(self.sy.text()))
        except ValueError:
            return None


# ─── Main Window ─────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trident Dental Imaging — Deep-View compatible")
        self.setMinimumSize(1400, 900)
        self.current_patient_id = None
        self.current_image_id = None
        self.current_image_path = None
        self.original_image = None
        self.processed_image = None
        self.dicom_metadata = None
        self.config = backup.load_config()

        self._build_menu()
        self._build_toolbar()
        self._build_ui()
        self.statusBar().showMessage("Ready — Select or add a patient to begin")
        self.refresh_patient_list()

        # Medical disclaimer on startup
        QMessageBox.information(
            self, "Notice",
            "This software is a viewing & workflow tool.\n\n"
            "It is NOT a certified medical device.\n\n"
            "For primary diagnostic decisions, use certified software "
            "(Trident Deep-View, Dexis, Carestream, etc.).\n\n"
            "Always verify findings with a qualified clinician."
        )

    def _make_action(self, text, slot, shortcut=None):
        a = QAction(text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        return a

    def _build_menu(self):
        m = self.menuBar()

        f = m.addMenu("&File")
        f.addAction(self._make_action("Import Image…", self.import_image, "Ctrl+I"))
        f.addAction(self._make_action("Import DICOM…", self.import_dicom))
        f.addAction(self._make_action("Export Current…", self.export_image, "Ctrl+E"))
        f.addAction(self._make_action("Export as DICOM…", self.export_dicom))
        f.addSeparator()
        f.addAction(self._make_action("Patient Report (PDF)…", self.export_patient_pdf, "Ctrl+Shift+P"))
        f.addAction(self._make_action("Print…", self.print_current, "Ctrl+P"))
        f.addSeparator()
        f.addAction(self._make_action("Backup Now…", self.backup_now))
        f.addAction(self._make_action("Restore From Backup…", self.restore_backup))
        f.addAction(self._make_action("Backup & Clinic Settings…", self.open_settings))
        f.addSeparator()
        f.addAction(self._make_action("Exit", self.close, "Ctrl+Q"))

        p = m.addMenu("&Patient")
        p.addAction(self._make_action("New Patient…", self.add_patient, "Ctrl+N"))
        p.addAction(self._make_action("Edit Patient…", self.edit_patient))
        p.addAction(self._make_action("Delete Patient", self.delete_patient))

        img = m.addMenu("&Image")
        img.addAction(self._make_action("Zoom In", self.zoom_in, "Ctrl++"))
        img.addAction(self._make_action("Zoom Out", self.zoom_out, "Ctrl+-"))
        img.addAction(self._make_action("Zoom Reset (100%)", self.zoom_reset, "Ctrl+9"))
        img.addAction(self._make_action("Fit to Window", self.fit_image, "Ctrl+0"))
        img.addAction(self._make_action("Rotate Left", lambda: self.rotate(-90), "Ctrl+["))
        img.addAction(self._make_action("Rotate Right", lambda: self.rotate(90), "Ctrl+]"))
        img.addAction(self._make_action("Flip Horizontal", self.flip_h, "Ctrl+H"))
        img.addAction(self._make_action("Flip Vertical", self.flip_v))
        img.addSeparator()
        img.addAction(self._make_action("Reset Adjustments", self.reset_adjustments, "Ctrl+R"))
        img.addAction(self._make_action("Restore Original (discard edits)", self.restore_original))

        t = m.addMenu("&Tools")
        t.addAction(self._make_action("Pan", self.enable_pan))
        t.addAction(self._make_action("Measure", self.enable_measure, "Ctrl+M"))
        t.addAction(self._make_action("Calibrate…", self.calibrate))
        t.addSeparator()
        t.addAction(self._make_action("Arrow", self.enable_arrow))
        t.addAction(self._make_action("Text", self.enable_text))
        t.addAction(self._make_action("Freehand Draw", self.enable_freehand))
        t.addAction(self._make_action("Circle", self.enable_circle))
        t.addAction(self._make_action("Rectangle", self.enable_rect))
        t.addAction(self._make_action("Magnifier", self.enable_magnifier, "Ctrl+L"))
        t.addSeparator()
        t.addAction(self._make_action("Undo Annotation", self.undo_annot, "Ctrl+Z"))
        t.addAction(self._make_action("Clear All Annotations", self.clear_annots))
        t.addAction(self._make_action("Annotation Color…", self.pick_color))

        v = m.addMenu("&View")
        v.addAction(self._make_action("Image Viewer", lambda: self.tabs.setCurrentIndex(0), "Ctrl+1"))
        v.addAction(self._make_action("Full Mouth Series", lambda: self.tabs.setCurrentIndex(1), "Ctrl+2"))
        v.addAction(self._make_action("Compare", lambda: self.tabs.setCurrentIndex(2), "Ctrl+3"))
        v.addAction(self._make_action("Odontogram", lambda: self.tabs.setCurrentIndex(3), "Ctrl+4"))
        v.addAction(self._make_action("Treatments", lambda: self.tabs.setCurrentIndex(4), "Ctrl+5"))

        a = m.addMenu("&Acquire")
        a.addAction(self._make_action("From TWAIN Device…", self.acquire_twain))
        a.addAction(self._make_action("From File…", self.import_image))

        h = m.addMenu("&Help")
        h.addAction(self._make_action("About / Medical Notice", self.show_about))

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setIconSize(QSize(20, 20))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        for label, slot in [
            ("Import", self.import_image), ("Export", self.export_image),
            ("Print", self.print_current),
        ]:
            tb.addAction(self._make_action(label, slot))
        tb.addSeparator()
        tb.addAction(self._make_action("New Patient", self.add_patient))
        tb.addSeparator()
        for label, slot in [
            ("Pan", self.enable_pan), ("Measure", self.enable_measure),
            ("Arrow", self.enable_arrow), ("Text", self.enable_text),
            ("Draw", self.enable_freehand), ("Circle", self.enable_circle),
            ("Magnify", self.enable_magnifier),
        ]:
            tb.addAction(self._make_action(label, slot))
        tb.addSeparator()
        for label, slot in [
            ("Zoom +", self.zoom_in),
            ("Zoom −", self.zoom_out),
            ("Fit", self.fit_image),
            ("Rotate L", lambda: self.rotate(-90)),
            ("Rotate R", lambda: self.rotate(90)),
            ("Flip H", self.flip_h),
        ]:
            tb.addAction(self._make_action(label, slot))
        tb.addSeparator()
        tb.addAction(self._make_action("Acquire", self.acquire_twain))
        tb.addAction(self._make_action("Compare", lambda: self.tabs.setCurrentIndex(2)))

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(2, 2, 2, 2)

        split = QSplitter(Qt.Orientation.Horizontal)
        main.addWidget(split)

        # LEFT: patients + tooth chart + images
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)

        sr = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search patients…")
        self.search.textChanged.connect(self.refresh_patient_list)
        sr.addWidget(self.search)
        bn = QPushButton("+ New")
        bn.clicked.connect(self.add_patient)
        sr.addWidget(bn)
        ll.addLayout(sr)

        self.patient_list = QListWidget()
        self.patient_list.currentItemChanged.connect(self.on_patient_selected)
        ll.addWidget(self.patient_list, 2)

        self.tooth_chart = ToothChartWidget()
        self.tooth_chart.tooth_selected.connect(self.on_tooth_selected)
        ll.addWidget(self.tooth_chart)

        tr = QHBoxLayout()
        tr.addWidget(QLabel("Images:"))
        self.tooth_filter_btn = QPushButton("Show All")
        self.tooth_filter_btn.clicked.connect(self.clear_tooth_filter)
        tr.addWidget(self.tooth_filter_btn)
        ll.addLayout(tr)

        self.image_list = QListWidget()
        self.image_list.currentItemChanged.connect(self.on_image_selected)
        ll.addWidget(self.image_list, 2)

        btns = QHBoxLayout()
        for label, slot in [("Import", self.import_image),
                            ("Delete", self.delete_image),
                            ("Compare", self.add_to_comparison)]:
            b = QPushButton(label)
            b.clicked.connect(slot)
            btns.addWidget(b)
        ll.addLayout(btns)

        tpr = QHBoxLayout()
        tpr.addWidget(QLabel("Type:"))
        self.image_type_combo = QComboBox()
        self.image_type_combo.addItems([
            "periapical", "bitewing", "panoramic", "cephalometric",
            "occlusal", "lateral", "other",
        ])
        tpr.addWidget(self.image_type_combo)
        ll.addLayout(tpr)

        left.setMaximumWidth(380)
        split.addWidget(left)

        # CENTER: tabs
        self.tabs = QTabWidget()
        self.image_view = DentalImageView()
        self.tabs.addTab(self.image_view, "Image Viewer")

        self.fmx = FMXWidget()
        self.fmx.slot_selected.connect(self.on_fmx_slot)
        self.fmx.slot_open.connect(self.on_fmx_slot_open)
        fmx_scroll = QScrollArea()
        fmx_scroll.setWidget(self.fmx)
        fmx_scroll.setWidgetResizable(True)
        self.tabs.addTab(fmx_scroll, "Full Mouth Series")

        self.comparison = ComparisonWidget()
        self.tabs.addTab(self.comparison, "Compare")

        self.odontogram = OdontogramWidget()
        self.odontogram.tooth_selected.connect(self.on_tooth_selected)
        self.odontogram.status_changed.connect(self._on_odontogram_changed)
        odo_scroll = QScrollArea()
        odo_scroll.setWidget(self.odontogram)
        odo_scroll.setWidgetResizable(True)
        self.tabs.addTab(odo_scroll, "Odontogram")

        self.treatment_log = TreatmentLogWidget()
        self.tabs.addTab(self.treatment_log, "Treatments")

        split.addWidget(self.tabs)

        # RIGHT: processing
        right = QWidget()
        rs = QScrollArea()
        rs.setWidget(right)
        rs.setWidgetResizable(True)
        rs.setMaximumWidth(300)
        rl = QVBoxLayout(right)

        fg = QGroupBox("Filter Presets")
        fgl = QVBoxLayout(fg)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(list(ip.FILTER_PRESETS.keys()))
        # Use activated (user-initiated) so programmatic changes don't loop.
        self.filter_combo.activated.connect(self._on_filter_changed)
        fgl.addWidget(self.filter_combo)
        rl.addWidget(fg)

        ag = QGroupBox("Adjustments")
        al = QFormLayout(ag)
        self.brightness = self._make_slider(-100, 100, 0)
        self.brightness_lbl = QLabel("0")
        al.addRow("Brightness:", self._slider_row(self.brightness, self.brightness_lbl))
        self.contrast = self._make_slider(-100, 100, 0)
        self.contrast_lbl = QLabel("0")
        al.addRow("Contrast:", self._slider_row(self.contrast, self.contrast_lbl))
        self.sharpen = self._make_slider(0, 30, 0)
        self.sharpen_lbl = QLabel("0.0")
        al.addRow("Sharpen:", self._slider_row(self.sharpen, self.sharpen_lbl))
        self.denoise = self._make_slider(0, 30, 0)
        self.denoise_lbl = QLabel("0")
        al.addRow("Denoise:", self._slider_row(self.denoise, self.denoise_lbl))
        rst = QPushButton("Reset")
        rst.clicked.connect(self.reset_adjustments)
        al.addRow(rst)
        rl.addWidget(ag)

        ig = QGroupBox("Image Info")
        il = QVBoxLayout(ig)
        self.info_label = QLabel("No image loaded")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size:11px;")
        il.addWidget(self.info_label)
        rl.addWidget(ig)

        dg = QGroupBox("DICOM Info")
        dl = QVBoxLayout(dg)
        self.dicom_label = QLabel("No DICOM data")
        self.dicom_label.setWordWrap(True)
        self.dicom_label.setStyleSheet("font-size:10px;")
        dl.addWidget(self.dicom_label)
        rl.addWidget(dg)

        rl.addStretch()
        split.addWidget(rs)
        split.setSizes([340, 700, 280])

        for s in (self.brightness, self.contrast, self.sharpen, self.denoise):
            s.valueChanged.connect(self.on_adjustment_changed)

    def _make_slider(self, lo, hi, val):
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(val)
        return s

    def _slider_row(self, slider, label):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(slider)
        h.addWidget(label)
        return w

    # ── Patient ──

    def refresh_patient_list(self):
        q = self.search.text().strip() if hasattr(self, "search") else ""
        self.patient_list.clear()
        for p in database.search_patients(q):
            it = QListWidgetItem(f"{p['last_name']}, {p['first_name']}")
            it.setData(Qt.ItemDataRole.UserRole, p["id"])
            self.patient_list.addItem(it)

    def on_patient_selected(self, current, previous):
        if current is None:
            self.current_patient_id = None
            self.image_list.clear()
            self.tooth_chart.clear_all_marks()
            self.odontogram.load_patient(None)
            self.treatment_log.load_patient(None)
            return
        self.current_patient_id = current.data(Qt.ItemDataRole.UserRole)
        self.refresh_image_list()
        self._mark_teeth()
        self.odontogram.load_patient(self.current_patient_id)
        self.treatment_log.load_patient(self.current_patient_id)
        p = database.get_patient(self.current_patient_id)
        if p:
            self.statusBar().showMessage(
                f"Patient: {p['first_name']} {p['last_name']} — ID {p['id']}")
            audit_log.log("patient_opened", patient_id=p["id"])

    def _mark_teeth(self):
        self.tooth_chart.clear_all_marks()
        if not self.current_patient_id:
            return
        for img in database.get_patient_images(self.current_patient_id):
            tn = img.get("tooth_number")
            if tn:
                try:
                    self.tooth_chart.mark_has_image(int(tn))
                except (ValueError, TypeError):
                    pass

    def add_patient(self):
        dlg = PatientDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            if not d["first_name"] or not d["last_name"]:
                QMessageBox.warning(self, "Error", "First and last name required.")
                return
            pid = database.add_patient(**d)
            audit_log.log("patient_added", patient_id=pid,
                          details=f"{d['first_name']} {d['last_name']}")
            self.refresh_patient_list()

    def edit_patient(self):
        if not self.current_patient_id:
            QMessageBox.information(self, "Info", "Select a patient first.")
            return
        p = database.get_patient(self.current_patient_id)
        dlg = PatientDialog(self, p)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            database.update_patient(self.current_patient_id, **dlg.get_data())
            audit_log.log("patient_edited", patient_id=self.current_patient_id)
            self.refresh_patient_list()

    def delete_patient(self):
        if not self.current_patient_id:
            return
        r = QMessageBox.question(self, "Confirm",
            "Delete this patient and all their images?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            pid = self.current_patient_id
            database.delete_patient(pid)
            audit_log.log("patient_deleted", patient_id=pid)
            self.current_patient_id = None
            self.refresh_patient_list()
            self.image_list.clear()
            self.tooth_chart.clear_all_marks()

    # ── Tooth chart filter ──

    def on_tooth_selected(self, fdi):
        self.statusBar().showMessage(f"Selected: {tooth_name(fdi)}")
        self.refresh_image_list(tooth_filter=fdi)
        self.tooth_filter_btn.setText(f"Show All (filtered: #{fdi})")

    def clear_tooth_filter(self):
        self.tooth_filter_btn.setText("Show All")
        self.refresh_image_list()

    # ── Images ──

    def refresh_image_list(self, tooth_filter=None):
        self.image_list.clear()
        if not self.current_patient_id:
            return
        imgs = database.get_patient_images(
            self.current_patient_id, tooth_number=tooth_filter)
        for i in imgs:
            tooth = i.get("tooth_number") or "—"
            label = f"{i['image_type']} | #{tooth} | {i['captured_at'][:16]}"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, i)
            self.image_list.addItem(it)

    def on_image_selected(self, current, previous):
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole)
        self.current_image_id = data["id"]
        path = data["file_path"]
        if path.lower().endswith(".dcm") and dicom_support.can_use_dicom():
            self._load_dicom(path)
        else:
            self.load_image(path)
            self.dicom_metadata = None
            self.dicom_label.setText("No DICOM data")
        audit_log.log("image_viewed", patient_id=self.current_patient_id,
                      image_id=data["id"])

    def load_image(self, path):
        try:
            self.original_image = ip.load_image(path)
            self.processed_image = self.original_image.copy()
            self.current_image_path = path
            self._display(self.processed_image)
            h, w = self.original_image.shape[:2]
            self.info_label.setText(
                f"File: {os.path.basename(path)}\nSize: {w} x {h}\nPath: {path}")
            self.reset_adjustments(reload=False)
            self.statusBar().showMessage(f"Loaded: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image:\n{e}")

    def _load_dicom(self, path):
        try:
            arr, meta = dicom_support.load_dicom(path)
            self.original_image = arr
            self.processed_image = arr.copy()
            self.current_image_path = path
            self.dicom_metadata = meta
            self._display(self.processed_image)
            h, w = arr.shape[:2]
            self.info_label.setText(f"DICOM: {os.path.basename(path)}\n{w} x {h}")
            self.dicom_label.setText(dicom_support.info_text(meta))
            if "pixel_spacing_mm" in meta:
                self.image_view.pixel_spacing_mm = meta["pixel_spacing_mm"]
                self.statusBar().showMessage(
                    f"DICOM — calibrated: {meta['pixel_spacing_mm'][0]:.4f} mm/px")
            self.reset_adjustments(reload=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load DICOM:\n{e}")

    def _display(self, img):
        self.image_view.set_image(numpy_to_qpixmap(img))

    def restore_original(self):
        if self.current_image_id:
            img = database.get_image(self.current_image_id)
            if img and img.get("original_path") and os.path.exists(img["original_path"]):
                self.load_image(img["original_path"])
                audit_log.log("original_restored", image_id=self.current_image_id)

    # ── Import / Export ──

    def import_image(self):
        if not self.current_patient_id:
            QMessageBox.information(self, "Info", "Select a patient first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import X-ray Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;DICOM (*.dcm);;All (*)")
        if not paths:
            return
        tooth = self.tooth_chart.get_selected()
        itype = self.image_type_combo.currentText()
        for p in paths:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            ext = os.path.splitext(p)[1]
            # Copy to originals (immutable)
            orig_name = f"patient_{self.current_patient_id}_{ts}_orig{ext}"
            orig_path = os.path.join(ORIGINALS_STORE, orig_name)
            shutil.copy2(p, orig_path)
            # Working copy
            work_name = f"patient_{self.current_patient_id}_{ts}{ext}"
            work_path = os.path.join(IMAGE_STORE, work_name)
            shutil.copy2(p, work_path)
            img_id = database.add_image(
                self.current_patient_id, work_path, image_type=itype,
                tooth_number=str(tooth) if tooth else None,
                original_path=orig_path,
            )
            audit_log.log("image_imported", patient_id=self.current_patient_id,
                          image_id=img_id, details=os.path.basename(p))
        self.refresh_image_list()
        self._mark_teeth()
        self.statusBar().showMessage(f"Imported {len(paths)} image(s).")

    def import_dicom(self):
        if not dicom_support.can_use_dicom():
            QMessageBox.warning(self, "Error", "pydicom not installed.")
            return
        self.import_image()

    def export_image(self):
        if self.processed_image is None:
            QMessageBox.information(self, "Info", "No image to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", "",
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tif);;BMP (*.bmp)")
        if path:
            cv2.imwrite(path, self.processed_image)
            audit_log.log("image_exported", image_id=self.current_image_id,
                          details=path)
            self.statusBar().showMessage(f"Exported to {path}")

    def export_dicom(self):
        if self.processed_image is None or not dicom_support.can_use_dicom():
            QMessageBox.warning(self, "Error", "No image or pydicom not installed.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export DICOM", "", "DICOM (*.dcm)")
        if not path:
            return
        name, pid = "", ""
        if self.current_patient_id:
            p = database.get_patient(self.current_patient_id)
            if p:
                name = f"{p['last_name']}^{p['first_name']}"
                pid = str(p["id"])
        dicom_support.save_dicom(path, self.processed_image,
                                 patient_name=name, patient_id=pid,
                                 pixel_spacing=self.image_view.pixel_spacing_mm)
        audit_log.log("image_exported_dicom", image_id=self.current_image_id,
                      details=path)

    def delete_image(self):
        it = self.image_list.currentItem()
        if not it:
            return
        data = it.data(Qt.ItemDataRole.UserRole)
        r = QMessageBox.question(self, "Confirm", "Delete this image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            database.delete_image(data["id"])
            # Only remove working copy; keep original for audit
            if os.path.exists(data["file_path"]):
                os.remove(data["file_path"])
            audit_log.log("image_deleted", image_id=data["id"])
            self.refresh_image_list()
            self._mark_teeth()
            self.original_image = None
            self.processed_image = None

    def print_current(self):
        if self.processed_image is None:
            QMessageBox.information(self, "Info", "No image to print.")
            return
        pm = numpy_to_qpixmap(self.processed_image)
        name = ""
        if self.current_patient_id:
            p = database.get_patient(self.current_patient_id)
            if p:
                name = f"{p['first_name']} {p['last_name']}"
        print_image(self, pm, patient_name=name)
        audit_log.log("image_printed", image_id=self.current_image_id)

    # ── Comparison ──

    def add_to_comparison(self):
        if self.processed_image is None:
            return
        pm = numpy_to_qpixmap(self.processed_image)
        lbl = os.path.basename(self.current_image_path) if self.current_image_path else "Image"
        side, ok = QInputDialog.getItem(self, "Compare", "Assign to:", ["Left", "Right"], 0, False)
        if ok:
            if side == "Left":
                self.comparison.set_left(pm, lbl)
            else:
                self.comparison.set_right(pm, lbl)
            self.tabs.setCurrentIndex(2)

    # ── FMX ──

    def on_fmx_slot(self, idx):
        if self.processed_image is None:
            self.statusBar().showMessage("Load an image first, then click FMX slot to assign.")
            return
        info = self.fmx.get_info(idx)
        if info:
            pm = numpy_to_qpixmap(self.processed_image)
            self.fmx.assign(idx, self.current_image_path, pm)
            self.statusBar().showMessage(f"Assigned to: {info['label']} ({info['teeth']})")

    def on_fmx_slot_open(self, idx):
        slot = self.fmx.slots[idx]
        if slot.image_path:
            self.load_image(slot.image_path)
            self.tabs.setCurrentIndex(0)

    # ── Filters / Adjustments ──

    def _on_filter_changed(self, _idx):
        if self.original_image is None:
            self.statusBar().showMessage("Load an image first, then pick a filter.")
            return
        name = self.filter_combo.currentText()
        self.statusBar().showMessage(f"Filter: {name}")
        self._apply()

    def apply_filter_preset(self, name):
        if self.original_image is None:
            return
        idx = self.filter_combo.findText(name)
        if idx >= 0:
            self.filter_combo.setCurrentIndex(idx)
        self._apply()

    def on_adjustment_changed(self):
        self.brightness_lbl.setText(str(self.brightness.value()))
        self.contrast_lbl.setText(str(self.contrast.value()))
        self.sharpen_lbl.setText(f"{self.sharpen.value() / 10:.1f}")
        self.denoise_lbl.setText(str(self.denoise.value()))
        self._apply()

    def _apply(self):
        if self.original_image is None:
            return
        name = self.filter_combo.currentText()
        fn = ip.FILTER_PRESETS.get(name, lambda x: x)
        img = fn(self.original_image.copy())
        b, c = self.brightness.value(), self.contrast.value()
        if b or c:
            img = ip.adjust_brightness_contrast(img, b, c)
        s = self.sharpen.value() / 10
        if s > 0:
            img = ip.sharpen(img, s)
        d = self.denoise.value()
        if d > 0:
            img = ip.denoise(img, d)
        self.processed_image = img
        self._display(img)

    def reset_adjustments(self, reload=True):
        for s in (self.brightness, self.contrast, self.sharpen, self.denoise):
            s.blockSignals(True)
            s.setValue(0)
            s.blockSignals(False)
        self.filter_combo.setCurrentIndex(0)
        self.brightness_lbl.setText("0")
        self.contrast_lbl.setText("0")
        self.sharpen_lbl.setText("0.0")
        self.denoise_lbl.setText("0")
        if reload and self.original_image is not None:
            self.processed_image = self.original_image.copy()
            self._display(self.processed_image)

    # ── Transform ──

    def rotate(self, angle):
        if self.processed_image is None:
            return
        self.processed_image = ip.rotate_image(self.processed_image, angle)
        self.original_image = ip.rotate_image(self.original_image, angle)
        self._display(self.processed_image)

    def flip_h(self):
        if self.processed_image is None:
            return
        self.processed_image = ip.flip_horizontal(self.processed_image)
        self.original_image = ip.flip_horizontal(self.original_image)
        self._display(self.processed_image)

    def flip_v(self):
        if self.processed_image is None:
            return
        self.processed_image = ip.flip_vertical(self.processed_image)
        self.original_image = ip.flip_vertical(self.original_image)
        self._display(self.processed_image)

    # ── Tools ──

    def fit_image(self):
        self.image_view.fit_to_view()

    def zoom_in(self):
        self.image_view.zoom_in()

    def zoom_out(self):
        self.image_view.zoom_out()

    def zoom_reset(self):
        self.image_view.zoom_reset()

    def _set_tool(self, tool, msg):
        if self.image_view.current_tool == DentalImageView.TOOL_MAGNIFIER \
                and tool != DentalImageView.TOOL_MAGNIFIER:
            self.image_view.deactivate_magnifier()
        self.image_view.current_tool = tool
        if tool == DentalImageView.TOOL_NONE:
            self.image_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.image_view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.statusBar().showMessage(msg)
        self.tabs.setCurrentIndex(0)

    def enable_pan(self): self._set_tool(DentalImageView.TOOL_NONE, "Pan active")
    def enable_measure(self): self._set_tool(DentalImageView.TOOL_MEASURE, "Measure — drag")
    def enable_arrow(self): self._set_tool(DentalImageView.TOOL_ARROW, "Arrow — drag")
    def enable_text(self): self._set_tool(DentalImageView.TOOL_TEXT, "Text — click to place")
    def enable_freehand(self): self._set_tool(DentalImageView.TOOL_FREEHAND, "Draw — drag")
    def enable_circle(self): self._set_tool(DentalImageView.TOOL_CIRCLE, "Circle — drag")
    def enable_rect(self): self._set_tool(DentalImageView.TOOL_RECT, "Rectangle — drag")
    def enable_magnifier(self): self._set_tool(DentalImageView.TOOL_MAGNIFIER,
                                               "Magnifier — hover over image")
    def undo_annot(self): self.image_view.undo_last()
    def clear_annots(self): self.image_view.clear_annotations()

    def pick_color(self):
        c = QColorDialog.getColor(self.image_view._color, self, "Annotation Color")
        if c.isValid():
            self.image_view._color = c

    def calibrate(self):
        dlg = CalibrationDialog(self, self.image_view.pixel_spacing_mm)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            sp = dlg.get()
            if sp:
                self.image_view.pixel_spacing_mm = sp
                self.statusBar().showMessage(f"Calibrated: {sp[0]:.4f} mm/px")

    # ── TWAIN ──

    def acquire_twain(self):
        try:
            import twain
        except ImportError:
            QMessageBox.information(self, "TWAIN Not Available",
                "TWAIN acquisition requires Windows + 'twain' package.\n\n"
                "On the clinic PC:\n"
                "1. Install Trident I-View drivers\n"
                "2. Run: pip install twain\n\n"
                "On macOS, use File > Import Image to load captured files.")
            return
        if not self.current_patient_id:
            QMessageBox.information(self, "Info", "Select a patient first.")
            return
        try:
            sm = twain.SourceManager(0)
            src = sm.OpenSource()
            if src is None:
                return
            src.RequestAcquire(0, 0)
            info = src.GetImageInfo()
            if info:
                handle = src.XferImageNatively()
                if handle:
                    twain.DIBToBMFile(handle, "_twain_temp.bmp")
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    name = f"patient_{self.current_patient_id}_{ts}.png"
                    orig = os.path.join(ORIGINALS_STORE, f"patient_{self.current_patient_id}_{ts}_orig.png")
                    dest = os.path.join(IMAGE_STORE, name)
                    img = cv2.imread("_twain_temp.bmp", cv2.IMREAD_GRAYSCALE)
                    cv2.imwrite(orig, img)
                    cv2.imwrite(dest, img)
                    os.remove("_twain_temp.bmp")
                    tooth = self.tooth_chart.get_selected()
                    img_id = database.add_image(
                        self.current_patient_id, dest, "periapical",
                        tooth_number=str(tooth) if tooth else None,
                        original_path=orig)
                    audit_log.log("image_acquired_twain",
                                  patient_id=self.current_patient_id, image_id=img_id)
                    self.refresh_image_list()
                    self.load_image(dest)
            src.destroy()
            sm.destroy()
        except Exception as e:
            QMessageBox.critical(self, "Acquisition Error", str(e))

    # ── Odontogram ──

    def _on_odontogram_changed(self):
        if self.current_patient_id:
            audit_log.log("tooth_status_changed",
                          patient_id=self.current_patient_id)

    # ── Backup / Restore / Settings ──

    def open_settings(self):
        dlg = BackupSettingsDialog(self, self.config)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_cfg = dlg.get_config()
            lang_changed = new_cfg.get("language") != self.config.get("language")
            self.config.update(new_cfg)
            backup.save_config(self.config)
            if lang_changed:
                i18n.set_language(self.config.get("language", "en"))
                QMessageBox.information(self, "Language",
                    "Language will fully apply the next time you start the app.")
            self.statusBar().showMessage("Settings saved.")

    def backup_now(self):
        folder = self.config.get("backup_folder") or ""
        if not folder:
            QMessageBox.information(self, "Backup",
                "No backup folder set. Choose one in File → Backup & Clinic Settings.")
            self.open_settings()
            folder = self.config.get("backup_folder") or ""
            if not folder:
                return
        try:
            path = backup.backup_now(folder)
            removed = backup.prune_old_backups(
                folder, int(self.config.get("keep_last_backups", 10)))
            audit_log.log("backup_created", details=path)
            msg = f"Backup created:\n{path}"
            if removed:
                msg += f"\n\n(Pruned {removed} older backup(s).)"
            QMessageBox.information(self, "Backup complete", msg)
        except Exception as e:
            QMessageBox.critical(self, "Backup failed", str(e))

    def restore_backup(self):
        r = QMessageBox.warning(self, "Restore from backup",
            "Restoring will OVERWRITE the current database with the backup.\n"
            "A safety snapshot of the current DB will be saved first.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose backup to restore",
            self.config.get("backup_folder", ""), "Backups (*.zip)")
        if not path:
            return
        try:
            backup.restore_backup(path)
            audit_log.log("backup_restored", details=path)
            QMessageBox.information(self, "Restore complete",
                "Restored. The app will now reload patient data.")
            self.current_patient_id = None
            self.current_image_id = None
            self.image_list.clear()
            self.tooth_chart.clear_all_marks()
            self.odontogram.load_patient(None)
            self.refresh_patient_list()
        except Exception as e:
            QMessageBox.critical(self, "Restore failed", str(e))

    # ── PDF Patient Report ──

    def export_patient_pdf(self):
        if not self.current_patient_id:
            QMessageBox.information(self, "Info", "Select a patient first.")
            return
        p = database.get_patient(self.current_patient_id)
        if not p:
            return
        default_name = f"{p['last_name']}_{p['first_name']}_report.pdf".replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save patient report",
            os.path.join(os.path.expanduser("~"), default_name),
            "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            images = database.get_patient_images(self.current_patient_id)
            statuses = database.get_tooth_statuses(self.current_patient_id)
            pdf_report.generate_report(
                path, p, images,
                tooth_statuses=statuses,
                clinic=self.config.get("clinic_name", "Dental Clinic"),
                doctor=self.config.get("doctor_name", ""),
            )
            audit_log.log("pdf_report_generated",
                          patient_id=self.current_patient_id, details=path)
            QMessageBox.information(self, "Report ready", f"PDF saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Report failed", str(e))

    # ── Close hook ──

    def closeEvent(self, event):
        if self.config.get("auto_backup_on_close") and self.config.get("backup_folder"):
            try:
                path = backup.backup_now(self.config["backup_folder"])
                backup.prune_old_backups(
                    self.config["backup_folder"],
                    int(self.config.get("keep_last_backups", 10)))
                audit_log.log("backup_auto_on_close", details=path)
            except Exception as e:
                QMessageBox.warning(self, "Auto-backup failed",
                    f"Could not complete auto-backup:\n{e}")
        event.accept()

    def show_about(self):
        QMessageBox.information(self, "About",
            "Trident Dental Imaging (Deep-View compatible workflow)\n\n"
            "This software is a VIEWING and WORKFLOW tool.\n"
            "It is NOT a certified medical device.\n\n"
            "Features:\n"
            "• Patient records with FDI tooth chart\n"
            "• Image acquisition via TWAIN (Windows) or file import\n"
            "• DICOM import/export\n"
            "• FMX (Full Mouth Series) template — 20 slots\n"
            "• Radiological filters (CLAHE, sharpen, invert, pseudocolor, etc.)\n"
            "• Measurements with DICOM-calibrated or custom mm/px\n"
            "• Annotations (arrow, text, freehand, circle, rectangle)\n"
            "• Side-by-side comparison\n"
            "• Print with custom header/patient info\n"
            "• Multi-image patient PDF report\n"
            "• Odontogram (per-tooth status: caries, filled, crown, implant…)\n"
            "• Automatic backup of DB + images (optional USB folder)\n"
            "• Restore from backup (safety snapshot kept)\n"
            "• Audit log of all actions (medical traceability)\n"
            "• Immutable originals preserved separately\n\n"
            "For primary diagnostics, use certified software "
            "(Trident Deep-View, Dexis, Carestream, etc.)")


def main():
    database.init_db()
    audit_log.init_audit_table()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    cfg = backup.load_config()
    if needs_first_run(cfg):
        wiz = FirstRunWizard(cfg=cfg)
        if wiz.exec() == QDialog.DialogCode.Accepted:
            cfg = wiz.result_config()
            backup.save_config(cfg)
    i18n.set_language(cfg.get("language", "en"))

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    pal.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(35, 35, 35))
    app.setPalette(pal)

    w = MainWindow()
    w.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
