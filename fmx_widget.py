"""Full Mouth Series (FMX) 20-slot template widget."""

from PyQt6.QtWidgets import QWidget, QGridLayout, QLabel, QVBoxLayout, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QMouseEvent


FMX_SLOTS = [
    {"row": 0, "col": 0, "label": "UR Molar", "type": "periapical", "teeth": "18-16"},
    {"row": 0, "col": 1, "label": "UR Premolar", "type": "periapical", "teeth": "15-14"},
    {"row": 0, "col": 2, "label": "UR Canine", "type": "periapical", "teeth": "13"},
    {"row": 0, "col": 3, "label": "U Anterior R", "type": "periapical", "teeth": "12-11"},
    {"row": 0, "col": 4, "label": "U Anterior L", "type": "periapical", "teeth": "21-22"},
    {"row": 0, "col": 5, "label": "UL Canine", "type": "periapical", "teeth": "23"},
    {"row": 0, "col": 6, "label": "UL Premolar", "type": "periapical", "teeth": "24-25"},
    {"row": 0, "col": 7, "label": "UL Molar", "type": "periapical", "teeth": "26-28"},
    {"row": 1, "col": 0, "colspan": 2, "label": "BW R Molar", "type": "bitewing", "teeth": "16-18/46-48"},
    {"row": 1, "col": 2, "colspan": 2, "label": "BW R Premolar", "type": "bitewing", "teeth": "14-15/44-45"},
    {"row": 1, "col": 4, "colspan": 2, "label": "BW L Premolar", "type": "bitewing", "teeth": "24-25/34-35"},
    {"row": 1, "col": 6, "colspan": 2, "label": "BW L Molar", "type": "bitewing", "teeth": "26-28/36-38"},
    {"row": 2, "col": 0, "label": "LR Molar", "type": "periapical", "teeth": "48-46"},
    {"row": 2, "col": 1, "label": "LR Premolar", "type": "periapical", "teeth": "45-44"},
    {"row": 2, "col": 2, "label": "LR Canine", "type": "periapical", "teeth": "43"},
    {"row": 2, "col": 3, "label": "L Anterior R", "type": "periapical", "teeth": "42-41"},
    {"row": 2, "col": 4, "label": "L Anterior L", "type": "periapical", "teeth": "31-32"},
    {"row": 2, "col": 5, "label": "LL Canine", "type": "periapical", "teeth": "33"},
    {"row": 2, "col": 6, "label": "LL Premolar", "type": "periapical", "teeth": "34-35"},
    {"row": 2, "col": 7, "label": "LL Molar", "type": "periapical", "teeth": "36-38"},
]


class FMXSlot(QLabel):
    slot_clicked = pyqtSignal(int)
    slot_double_clicked = pyqtSignal(int)

    def __init__(self, index, info, parent=None):
        super().__init__(parent)
        self.index = index
        self.info = info
        self.image_path = None
        self._pix = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(100, 80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._empty()

    def _empty(self):
        self.setText(f"{self.info['label']}\n{self.info['teeth']}")
        self.setStyleSheet(
            "QLabel { background:#2a2a2a; border:2px dashed #555; color:#888;"
            " font-size:10px; padding:4px; }"
            "QLabel:hover { border-color:#2a82da; }"
        )

    def set_image(self, path, pixmap=None):
        self.image_path = path
        self._pix = pixmap if pixmap else QPixmap(path)
        scaled = self._pix.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(scaled)
        self.setStyleSheet(
            "QLabel { background:#1a1a1a; border:2px solid #2e7d32; padding:2px; }"
            "QLabel:hover { border-color:#2a82da; }"
        )

    def clear_image(self):
        self.image_path = None
        self._pix = None
        self._empty()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._pix:
            self.setPixmap(self._pix.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.slot_clicked.emit(self.index)
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self.slot_double_clicked.emit(self.index)
        super().mouseDoubleClickEvent(e)


class FMXWidget(QWidget):
    slot_selected = pyqtSignal(int)
    slot_open = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slots = []
        layout = QVBoxLayout(self)
        title = QLabel("Full Mouth Series (FMX)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #ddd;")
        layout.addWidget(title)
        grid = QGridLayout()
        grid.setSpacing(3)
        for i, info in enumerate(FMX_SLOTS):
            w = FMXSlot(i, info)
            w.slot_clicked.connect(self.slot_selected.emit)
            w.slot_double_clicked.connect(self.slot_open.emit)
            cs = info.get("colspan", 1)
            grid.addWidget(w, info["row"], info["col"], 1, cs)
            self.slots.append(w)
        layout.addLayout(grid)

    def assign(self, idx, path, pixmap=None):
        if 0 <= idx < len(self.slots):
            self.slots[idx].set_image(path, pixmap)

    def clear_slot(self, idx):
        if 0 <= idx < len(self.slots):
            self.slots[idx].clear_image()

    def clear_all(self):
        for s in self.slots:
            s.clear_image()

    def get_info(self, idx):
        return FMX_SLOTS[idx] if 0 <= idx < len(FMX_SLOTS) else None
