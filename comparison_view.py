"""Side-by-side image comparison."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSplitter,
    QGraphicsView, QGraphicsScene,
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QWheelEvent


class ComparisonPanel(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.pixmap_item = None
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMinimumSize(300, 250)
        self.setStyleSheet("border:1px solid #555; background:#1a1a1a;")

    def set_image(self, pixmap):
        self.scene.clear()
        self.pixmap_item = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def clear_image(self):
        self.scene.clear()
        self.pixmap_item = None

    def wheelEvent(self, e: QWheelEvent):
        f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def fit(self):
        if self.pixmap_item:
            self.fitInView(self.pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)


class ComparisonWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        t = QLabel("Image Comparison — side-by-side")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("font-weight:bold; font-size:13px; color:#ddd;")
        layout.addWidget(t)

        controls = QHBoxLayout()
        for label, fn in [("Fit Left", lambda: self.left.fit()),
                          ("Fit Right", lambda: self.right.fit()),
                          ("Fit Both", self._fit_both)]:
            b = QPushButton(label)
            b.clicked.connect(fn)
            controls.addWidget(b)
        controls.addStretch()
        layout.addLayout(controls)

        sp = QSplitter(Qt.Orientation.Horizontal)
        lc = QWidget()
        ll = QVBoxLayout(lc)
        ll.setContentsMargins(0, 0, 0, 0)
        self.left_label = QLabel("Left")
        self.left_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_label.setStyleSheet("color:#aaa; font-size:11px;")
        ll.addWidget(self.left_label)
        self.left = ComparisonPanel()
        ll.addWidget(self.left)

        rc = QWidget()
        rl = QVBoxLayout(rc)
        rl.setContentsMargins(0, 0, 0, 0)
        self.right_label = QLabel("Right")
        self.right_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_label.setStyleSheet("color:#aaa; font-size:11px;")
        rl.addWidget(self.right_label)
        self.right = ComparisonPanel()
        rl.addWidget(self.right)

        sp.addWidget(lc)
        sp.addWidget(rc)
        layout.addWidget(sp)

    def set_left(self, pixmap, label=""):
        self.left.set_image(pixmap)
        if label:
            self.left_label.setText(f"Left — {label}")

    def set_right(self, pixmap, label=""):
        self.right.set_image(pixmap)
        if label:
            self.right_label.setText(f"Right — {label}")

    def _fit_both(self):
        self.left.fit()
        self.right.fit()
