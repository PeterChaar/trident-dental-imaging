"""Print support with customizable layouts."""

from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QCheckBox, QDialogButtonBox, QGroupBox,
    QFormLayout, QLineEdit, QTextEdit,
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QFont, QColor, QPageLayout, QPageSize
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog


class PrintDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Print Settings")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        hg = QGroupBox("Header")
        hl = QFormLayout(hg)
        self.clinic = QLineEdit("Dental Clinic")
        self.doctor = QLineEdit()
        self.patient = QLineEdit()
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)
        hl.addRow("Clinic:", self.clinic)
        hl.addRow("Doctor:", self.doctor)
        hl.addRow("Patient:", self.patient)
        hl.addRow("Notes:", self.notes)
        layout.addWidget(hg)

        og = QGroupBox("Options")
        ol = QVBoxLayout(og)
        self.inc_date = QCheckBox("Include date")
        self.inc_date.setChecked(True)
        self.inc_header = QCheckBox("Include header")
        self.inc_header.setChecked(True)
        self.inc_patient = QCheckBox("Include patient info")
        self.inc_patient.setChecked(True)
        ol.addWidget(self.inc_date)
        ol.addWidget(self.inc_header)
        ol.addWidget(self.inc_patient)
        layout.addWidget(og)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)


def print_image(parent, pixmap, patient_name="", image_info=""):
    dlg = PrintDialog(parent)
    dlg.patient.setText(patient_name)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageOrientation(QPageLayout.Orientation.Portrait)

    preview = QPrintPreviewDialog(printer, parent)
    preview.setWindowTitle("Print Preview")

    def render(p):
        _paint(p, pixmap, dlg, patient_name, image_info)

    preview.paintRequested.connect(render)
    preview.exec()


def _paint(printer, pixmap, dlg, patient_name, image_info):
    painter = QPainter(printer)
    page = printer.pageRect(QPrinter.Unit.DevicePixel)
    w, h = page.width(), page.height()
    y = 20.0

    if dlg.inc_header.isChecked():
        painter.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(QRectF(0, y, w, 40),
                         Qt.AlignmentFlag.AlignCenter,
                         dlg.clinic.text() or "Dental Clinic")
        y += 50
        doc = dlg.doctor.text()
        if doc:
            painter.setFont(QFont("Arial", 11))
            painter.drawText(QRectF(0, y, w, 25),
                             Qt.AlignmentFlag.AlignCenter, f"Dr. {doc}")
            y += 30

    if dlg.inc_patient.isChecked() and patient_name:
        painter.setFont(QFont("Arial", 12))
        painter.drawText(QRectF(20, y, w - 40, 25),
                         Qt.AlignmentFlag.AlignLeft,
                         f"Patient: {patient_name}")
        y += 30

    if dlg.inc_date.isChecked():
        painter.setFont(QFont("Arial", 10))
        painter.drawText(QRectF(20, y, w - 40, 20),
                         Qt.AlignmentFlag.AlignLeft,
                         f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        y += 25

    y += 10
    iw = w - 40
    ih = h - y - 80
    scaled = pixmap.scaled(int(iw), int(ih),
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    painter.drawPixmap(int((w - scaled.width()) / 2), int(y), scaled)
    y += scaled.height() + 15

    notes = dlg.notes.toPlainText().strip()
    if notes:
        painter.setFont(QFont("Arial", 9))
        painter.drawText(QRectF(20, y, w - 40, 60),
                         Qt.TextFlag.TextWordWrap, f"Notes: {notes}")

    painter.setFont(QFont("Arial", 8))
    painter.setPen(QColor(128, 128, 128))
    painter.drawText(QRectF(0, h - 30, w, 20),
                     Qt.AlignmentFlag.AlignCenter,
                     "Trident Dental Imaging — For reference use. Always confirm diagnosis with certified software.")
    painter.end()
