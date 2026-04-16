"""Interactive dental tooth chart widget using FDI (ISO 3950) numbering."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

UPPER_RIGHT = [18, 17, 16, 15, 14, 13, 12, 11]
UPPER_LEFT = [21, 22, 23, 24, 25, 26, 27, 28]
LOWER_LEFT = [38, 37, 36, 35, 34, 33, 32, 31]
LOWER_RIGHT = [41, 42, 43, 44, 45, 46, 47, 48]

TOOTH_NAMES = {
    1: "Central Incisor", 2: "Lateral Incisor", 3: "Canine",
    4: "First Premolar", 5: "Second Premolar",
    6: "First Molar", 7: "Second Molar", 8: "Third Molar (Wisdom)",
}


def tooth_name(fdi):
    q = fdi // 10
    t = fdi % 10
    quad = {1: "Upper Right", 2: "Upper Left", 3: "Lower Left", 4: "Lower Right"}
    return f"{quad.get(q, '?')} - {TOOTH_NAMES.get(t, '?')} (#{fdi})"


class ToothButton(QPushButton):
    tooth_clicked = pyqtSignal(int)

    def __init__(self, fdi, parent=None):
        super().__init__(str(fdi), parent)
        self.fdi = fdi
        self.has_image = False
        self.is_selected = False
        self.setFixedSize(38, 38)
        self.setToolTip(tooth_name(fdi))
        self.clicked.connect(lambda: self.tooth_clicked.emit(self.fdi))
        self._update_style()

    def set_has_image(self, v):
        self.has_image = v
        self._update_style()

    def set_selected(self, v):
        self.is_selected = v
        self._update_style()

    def _update_style(self):
        if self.is_selected:
            bg, fg, bd = "#2a82da", "white", "#5cacee"
        elif self.has_image:
            bg, fg, bd = "#2e7d32", "white", "#4caf50"
        else:
            bg, fg, bd = "#444", "#ccc", "#666"
        self.setStyleSheet(
            f"QPushButton {{ background: {bg}; color: {fg}; border: 2px solid {bd};"
            f" border-radius: 5px; font-weight: bold; font-size: 10px; }}"
            f"QPushButton:hover {{ border-color: #5cacee; }}"
        )


class ToothChartWidget(QWidget):
    tooth_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = {}
        self._selected = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        title = QLabel("Dental Chart (FDI)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; color: #ddd;")
        layout.addWidget(title)

        lbl_u = QLabel("UPPER (Maxillary)")
        lbl_u.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_u.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(lbl_u)

        upper = QHBoxLayout()
        upper.setSpacing(1)
        for n in UPPER_RIGHT + UPPER_LEFT:
            b = ToothButton(n)
            b.tooth_clicked.connect(self._on_click)
            self.buttons[n] = b
            upper.addWidget(b)
            if n == 11:
                sep = QLabel("|")
                sep.setStyleSheet("color: #888;")
                sep.setFixedWidth(8)
                upper.addWidget(sep)
        layout.addLayout(upper)

        div = QLabel("─" * 40)
        div.setAlignment(Qt.AlignmentFlag.AlignCenter)
        div.setStyleSheet("color: #666;")
        layout.addWidget(div)

        lower = QHBoxLayout()
        lower.setSpacing(1)
        for n in LOWER_LEFT + LOWER_RIGHT:
            b = ToothButton(n)
            b.tooth_clicked.connect(self._on_click)
            self.buttons[n] = b
            lower.addWidget(b)
            if n == 31:
                sep = QLabel("|")
                sep.setStyleSheet("color: #888;")
                sep.setFixedWidth(8)
                lower.addWidget(sep)
        layout.addLayout(lower)

        lbl_l = QLabel("LOWER (Mandibular)")
        lbl_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_l.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(lbl_l)

    def _on_click(self, fdi):
        if self._selected and self._selected in self.buttons:
            self.buttons[self._selected].set_selected(False)
        self._selected = fdi
        self.buttons[fdi].set_selected(True)
        self.tooth_selected.emit(fdi)

    def mark_has_image(self, fdi, v=True):
        if fdi in self.buttons:
            self.buttons[fdi].set_has_image(v)

    def clear_all_marks(self):
        for b in self.buttons.values():
            b.set_has_image(False)
            b.set_selected(False)
        self._selected = None

    def get_selected(self):
        return self._selected
