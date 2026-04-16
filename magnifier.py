"""Magnifier/loupe — circular floating widget showing a zoomed region of the
image at the cursor. Useful for inspecting caries detail without changing the
main view's zoom. Toggled on/off from the toolbar."""

from PyQt6.QtCore import Qt, QPoint, QRect
from PyQt6.QtGui import QPainter, QPixmap, QPen, QColor, QBrush, QRegion
from PyQt6.QtWidgets import QWidget


class MagnifierOverlay(QWidget):
    SIZE = 220          # on-screen diameter in px
    ZOOM = 3.0          # magnification factor

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._source = QPixmap()
        self._scene_pos = None
        # Circular mask
        reg = QRegion(0, 0, self.SIZE, self.SIZE, QRegion.RegionType.Ellipse)
        self.setMask(reg)

    def set_source(self, pixmap):
        self._source = pixmap or QPixmap()

    def show_at(self, global_pos, scene_pos):
        """Show the loupe near the cursor, sampling source at scene_pos."""
        self._scene_pos = scene_pos
        offset = QPoint(30, 30)
        self.move(global_pos + offset)
        if not self.isVisible():
            self.show()
        self.update()

    def hide_loupe(self):
        self._scene_pos = None
        self.hide()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        p.setBrush(QBrush(QColor(20, 20, 20)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, self.SIZE, self.SIZE)

        if not self._source.isNull() and self._scene_pos is not None:
            sample_size = int(self.SIZE / self.ZOOM)
            sx = int(self._scene_pos.x() - sample_size / 2)
            sy = int(self._scene_pos.y() - sample_size / 2)
            src_rect = QRect(sx, sy, sample_size, sample_size)
            dst_rect = QRect(0, 0, self.SIZE, self.SIZE)
            p.drawPixmap(dst_rect, self._source, src_rect)

        pen = QPen(QColor(255, 220, 0), 3)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(1, 1, self.SIZE - 2, self.SIZE - 2)

        cx = self.SIZE // 2
        p.setPen(QPen(QColor(255, 220, 0), 1))
        p.drawLine(cx - 10, cx, cx + 10, cx)
        p.drawLine(cx, cx - 10, cx, cx + 10)
        p.end()
