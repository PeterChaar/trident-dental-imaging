"""Odontogram — per-tooth status tracking (caries, filled, crown, extracted, etc.).

Saves status per patient in the tooth_status DB table. Right-click a tooth to
set / change its status. Colors match common dental-chart conventions."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog,
    QFormLayout, QComboBox, QTextEdit, QDialogButtonBox, QMenu, QGridLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction

import database
from tooth_chart import (
    UPPER_RIGHT, UPPER_LEFT, LOWER_LEFT, LOWER_RIGHT, tooth_name,
)


STATUSES = [
    ("healthy",    "Healthy",      "#2e7d32", "#ffffff"),
    ("caries",     "Caries",       "#c62828", "#ffffff"),
    ("filled",     "Filled",       "#1565c0", "#ffffff"),
    ("crown",      "Crown",        "#f9a825", "#000000"),
    ("root_canal", "Root Canal",   "#6a1b9a", "#ffffff"),
    ("extracted",  "Extracted",    "#424242", "#ffffff"),
    ("missing",    "Missing",      "#212121", "#888888"),
    ("implant",    "Implant",      "#00838f", "#ffffff"),
    ("bridge",     "Bridge",       "#ad1457", "#ffffff"),
    ("sealant",    "Sealant",      "#558b2f", "#ffffff"),
]
STATUS_MAP = {k: (label, bg, fg) for k, label, bg, fg in STATUSES}


class ToothStatusDialog(QDialog):
    def __init__(self, fdi, current=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Set status — {tooth_name(fdi)}")
        self.setMinimumWidth(360)
        f = QFormLayout(self)

        self.status = QComboBox()
        for key, label, _, _ in STATUSES:
            self.status.addItem(label, key)
        if current:
            for i, (k, _, _, _) in enumerate(STATUSES):
                if k == current.get("status"):
                    self.status.setCurrentIndex(i)
                    break
        f.addRow("Status:", self.status)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        if current and current.get("notes"):
            self.notes.setPlainText(current["notes"])
        f.addRow("Notes:", self.notes)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Reset
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.reset_clicked = False
        bb.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self._reset)
        f.addRow(bb)

    def _reset(self):
        self.reset_clicked = True
        self.accept()

    def result_data(self):
        if self.reset_clicked:
            return None
        return {
            "status": self.status.currentData(),
            "notes": self.notes.toPlainText().strip() or None,
        }


class OdontogramTooth(QPushButton):
    right_clicked = pyqtSignal(int)
    left_clicked = pyqtSignal(int)

    def __init__(self, fdi, parent=None):
        super().__init__(str(fdi), parent)
        self.fdi = fdi
        self.status = None
        self.has_image = False
        self.setFixedSize(44, 56)
        self.setToolTip(tooth_name(fdi))
        self._apply_style()
        self.clicked.connect(lambda: self.left_clicked.emit(self.fdi))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda _pos: self.right_clicked.emit(self.fdi)
        )

    def set_status(self, status):
        self.status = status
        self._apply_style()

    def set_has_image(self, v):
        self.has_image = v
        self._apply_style()

    def _apply_style(self):
        if self.status and self.status in STATUS_MAP:
            _, bg, fg = STATUS_MAP[self.status]
        else:
            bg, fg = "#3a3a3a", "#ddd"
        border = "#4caf50" if self.has_image else "#555"
        self.setStyleSheet(
            f"QPushButton {{ background:{bg}; color:{fg}; border:2px solid {border};"
            f" border-radius:6px; font-weight:bold; font-size:10px;"
            f" text-align:center; padding-top:2px; }}"
            f"QPushButton:hover {{ border-color:#5cacee; }}"
        )


class OdontogramWidget(QWidget):
    tooth_selected = pyqtSignal(int)
    status_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.patient_id = None
        self.buttons = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        title = QLabel("Odontogram — left-click to select, right-click to set status")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight:bold; color:#ddd; font-size:12px;")
        layout.addWidget(title)

        lbl_u = QLabel("UPPER (Maxillary)")
        lbl_u.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_u.setStyleSheet("color:#aaa; font-size:10px;")
        layout.addWidget(lbl_u)

        upper = QHBoxLayout()
        upper.setSpacing(2)
        upper.addStretch()
        for n in UPPER_RIGHT + UPPER_LEFT:
            b = OdontogramTooth(n)
            b.right_clicked.connect(self._edit_status)
            b.left_clicked.connect(self.tooth_selected.emit)
            self.buttons[n] = b
            upper.addWidget(b)
            if n == 11:
                sep = QLabel("|")
                sep.setStyleSheet("color:#888;")
                sep.setFixedWidth(10)
                upper.addWidget(sep)
        upper.addStretch()
        layout.addLayout(upper)

        layout.addSpacing(4)

        lower = QHBoxLayout()
        lower.setSpacing(2)
        lower.addStretch()
        for n in LOWER_LEFT + LOWER_RIGHT:
            b = OdontogramTooth(n)
            b.right_clicked.connect(self._edit_status)
            b.left_clicked.connect(self.tooth_selected.emit)
            self.buttons[n] = b
            lower.addWidget(b)
            if n == 31:
                sep = QLabel("|")
                sep.setStyleSheet("color:#888;")
                sep.setFixedWidth(10)
                lower.addWidget(sep)
        lower.addStretch()
        layout.addLayout(lower)

        lbl_l = QLabel("LOWER (Mandibular)")
        lbl_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_l.setStyleSheet("color:#aaa; font-size:10px;")
        layout.addWidget(lbl_l)

        layout.addSpacing(8)
        layout.addWidget(self._legend())

    def _legend(self):
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        grid.addWidget(QLabel("<b>Legend:</b>"), 0, 0)
        col = 1
        row = 0
        for key, label, bg, fg in STATUSES:
            sw = QLabel(f"  {label}  ")
            sw.setStyleSheet(
                f"background:{bg}; color:{fg}; border:1px solid #555;"
                f" border-radius:3px; padding:2px 6px; font-size:10px;"
            )
            grid.addWidget(sw, row, col)
            col += 1
            if col > 5:
                col = 0
                row += 1
        return box

    def load_patient(self, patient_id):
        self.patient_id = patient_id
        for b in self.buttons.values():
            b.set_status(None)
            b.set_has_image(False)
        if patient_id is None:
            return
        statuses = database.get_tooth_statuses(patient_id)
        for fdi, row in statuses.items():
            if fdi in self.buttons:
                self.buttons[fdi].set_status(row.get("status"))
                if row.get("notes"):
                    self.buttons[fdi].setToolTip(
                        f"{tooth_name(fdi)}\nStatus: {row.get('status')}\n"
                        f"Notes: {row.get('notes')}"
                    )

        images_by_tooth = set()
        for img in database.get_patient_images(patient_id):
            t = img.get("tooth_number")
            if t:
                try:
                    images_by_tooth.add(int(t))
                except (TypeError, ValueError):
                    pass
        for fdi, b in self.buttons.items():
            b.set_has_image(fdi in images_by_tooth)

    def mark_has_image(self, fdi, v=True):
        if fdi in self.buttons:
            self.buttons[fdi].set_has_image(v)

    def _edit_status(self, fdi):
        if self.patient_id is None:
            return
        current = database.get_tooth_statuses(self.patient_id).get(fdi)
        dlg = ToothStatusDialog(fdi, current, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.result_data()
        if data is None:
            database.clear_tooth_status(self.patient_id, fdi)
            self.buttons[fdi].set_status(None)
        else:
            database.set_tooth_status(
                self.patient_id, fdi, data["status"], notes=data.get("notes")
            )
            self.buttons[fdi].set_status(data["status"])
            if data.get("notes"):
                self.buttons[fdi].setToolTip(
                    f"{tooth_name(fdi)}\nStatus: {data['status']}\n"
                    f"Notes: {data['notes']}"
                )
        self.status_changed.emit()
