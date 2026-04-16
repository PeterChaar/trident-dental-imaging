"""Annotation tools — arrow, text, freehand, circle, rectangle."""

import math
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsLineItem, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsEllipseItem, QGraphicsRectItem,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QDialogButtonBox, QSpinBox,
)
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QColor, QFont, QPainterPath, QBrush, QPolygonF


TOOL_ARROW = "arrow"
TOOL_TEXT = "text"
TOOL_FREEHAND = "freehand"
TOOL_CIRCLE = "circle"
TOOL_RECT = "rect"


class ArrowItem(QGraphicsLineItem):
    def __init__(self, x1, y1, x2, y2, color=QColor(255, 255, 0), width=2):
        super().__init__(x1, y1, x2, y2)
        self.setPen(QPen(color, width))
        self._color = color

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        line = self.line()
        angle = math.atan2(line.dy(), line.dx())
        size = 12
        p1 = line.p2()
        p2 = QPointF(p1.x() - size * math.cos(angle - math.pi / 6),
                     p1.y() - size * math.sin(angle - math.pi / 6))
        p3 = QPointF(p1.x() - size * math.cos(angle + math.pi / 6),
                     p1.y() - size * math.sin(angle + math.pi / 6))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._color))
        painter.drawPolygon(QPolygonF([p1, p2, p3]))


class TextAnnotation(QGraphicsTextItem):
    def __init__(self, text, pos, color=QColor(255, 255, 0), size=14):
        super().__init__(text)
        self.setPos(pos)
        self.setDefaultTextColor(color)
        self.setFont(QFont("Arial", size, QFont.Weight.Bold))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)


class FreehandPath(QGraphicsPathItem):
    def __init__(self, color=QColor(255, 255, 0), width=2):
        super().__init__()
        self.setPen(QPen(color, width, Qt.PenStyle.SolidLine,
                         Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        self._path = QPainterPath()
        self._started = False

    def add_point(self, pt):
        if not self._started:
            self._path.moveTo(pt)
            self._started = True
        else:
            self._path.lineTo(pt)
        self.setPath(self._path)


class CircleAnnotation(QGraphicsEllipseItem):
    def __init__(self, rect, color=QColor(255, 255, 0), width=2):
        super().__init__(rect)
        self.setPen(QPen(color, width))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)


class RectAnnotation(QGraphicsRectItem):
    def __init__(self, rect, color=QColor(255, 255, 0), width=2):
        super().__init__(rect)
        self.setPen(QPen(color, width))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)


class TextAnnotationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Text Annotation")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Text:"))
        self.text_input = QLineEdit()
        layout.addWidget(self.text_input)
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Font size:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(8, 48)
        self.size_spin.setValue(14)
        size_row.addWidget(self.size_spin)
        layout.addLayout(size_row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_text(self):
        return self.text_input.text().strip()

    def get_size(self):
        return self.size_spin.value()
