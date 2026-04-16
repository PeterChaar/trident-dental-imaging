"""Treatment log — per-patient list of procedures performed. Each entry has
a date, tooth (optional), procedure, and free-text notes."""

from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QDialog, QFormLayout, QLineEdit, QComboBox, QDateEdit,
    QTextEdit, QDialogButtonBox, QMessageBox, QHeaderView,
)

import database
import audit_log
from tooth_chart import (
    UPPER_RIGHT, UPPER_LEFT, LOWER_LEFT, LOWER_RIGHT, tooth_name,
)


COMMON_PROCEDURES = [
    "Consultation / Exam",
    "Cleaning (Scaling)",
    "Composite Filling",
    "Amalgam Filling",
    "Root Canal Treatment",
    "Crown",
    "Bridge",
    "Extraction (Simple)",
    "Extraction (Surgical)",
    "Implant Placement",
    "Periodontal Treatment",
    "Fluoride Application",
    "Sealant",
    "Denture (Partial)",
    "Denture (Full)",
    "Bleaching / Whitening",
    "Orthodontic Adjustment",
    "X-ray Imaging",
    "Follow-up Visit",
    "Other",
]


def _all_teeth():
    return (list(reversed(UPPER_RIGHT)) + UPPER_LEFT
            + list(reversed(LOWER_LEFT)) + LOWER_RIGHT)


class TreatmentDialog(QDialog):
    def __init__(self, parent=None, record=None):
        super().__init__(parent)
        self.setWindowTitle("Treatment")
        self.setMinimumWidth(440)
        f = QFormLayout(self)

        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.date.setDate(QDate.currentDate())

        self.tooth = QComboBox()
        self.tooth.addItem("(not tooth-specific)", None)
        for n in _all_teeth():
            self.tooth.addItem(f"#{n} — {tooth_name(n).split(' - ')[1].split(' (')[0]}", n)

        self.procedure = QComboBox()
        self.procedure.setEditable(True)
        self.procedure.addItems(COMMON_PROCEDURES)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(90)
        self.notes.setPlaceholderText("Surfaces, materials, anesthesia, follow-up plan…")

        f.addRow("Date:", self.date)
        f.addRow("Tooth:", self.tooth)
        f.addRow("Procedure:", self.procedure)
        f.addRow("Notes:", self.notes)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

        if record:
            try:
                d = QDate.fromString(record.get("treatment_date", ""), "yyyy-MM-dd")
                if d.isValid():
                    self.date.setDate(d)
            except Exception:
                pass
            t = record.get("tooth_number")
            if t is not None:
                try:
                    t_int = int(t)
                    for i in range(self.tooth.count()):
                        if self.tooth.itemData(i) == t_int:
                            self.tooth.setCurrentIndex(i)
                            break
                except (TypeError, ValueError):
                    pass
            self.procedure.setCurrentText(record.get("procedure") or "")
            self.notes.setPlainText(record.get("notes") or "")

    def get_data(self):
        return {
            "treatment_date": self.date.date().toString("yyyy-MM-dd"),
            "tooth_number": self.tooth.currentData(),
            "procedure": self.procedure.currentText().strip(),
            "notes": self.notes.toPlainText().strip() or None,
        }


class TreatmentLogWidget(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.patient_id = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QHBoxLayout()
        title = QLabel("Treatment Log")
        title.setStyleSheet("font-size:14px; font-weight:bold; color:#ddd;")
        header.addWidget(title)
        header.addStretch()

        self.add_btn = QPushButton("+ Add Treatment")
        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._on_edit)
        self.del_btn = QPushButton("Delete")
        self.del_btn.clicked.connect(self._on_delete)
        for b in (self.add_btn, self.edit_btn, self.del_btn):
            header.addWidget(b)
        layout.addLayout(header)

        self.info = QLabel("No patient selected")
        self.info.setStyleSheet("color:#888; padding:6px;")
        layout.addWidget(self.info)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Date", "Tooth", "Procedure", "Notes"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(self._on_edit)
        layout.addWidget(self.table)

        self._update_enabled()

    def load_patient(self, patient_id):
        self.patient_id = patient_id
        if patient_id is None:
            self.info.setText("No patient selected")
            self.table.setRowCount(0)
            self._update_enabled()
            return
        self.info.setText(f"Patient ID: {patient_id}")
        self._refresh()
        self._update_enabled()

    def _update_enabled(self):
        on = self.patient_id is not None
        self.add_btn.setEnabled(on)
        self.edit_btn.setEnabled(on)
        self.del_btn.setEnabled(on)

    def _refresh(self):
        if self.patient_id is None:
            return
        rows = database.get_treatments(self.patient_id)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            tooth = r.get("tooth_number")
            tooth_label = f"#{tooth}" if tooth else "—"
            values = [
                r.get("treatment_date") or "",
                tooth_label,
                r.get("procedure") or "",
                (r.get("notes") or "").replace("\n", " "),
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.ItemDataRole.UserRole, r.get("id"))
                self.table.setItem(i, col, item)

    def _selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_add(self):
        if self.patient_id is None:
            return
        dlg = TreatmentDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.get_data()
        if not d["procedure"]:
            QMessageBox.warning(self, "Missing data", "Procedure is required.")
            return
        tid = database.add_treatment(
            self.patient_id,
            procedure=d["procedure"],
            tooth_number=d["tooth_number"],
            treatment_date=d["treatment_date"],
            notes=d["notes"],
        )
        audit_log.log("treatment_added", patient_id=self.patient_id,
                      details=f"{d['procedure']} ({d['treatment_date']})")
        self._refresh()
        self.changed.emit()

    def _on_edit(self, *_):
        if self.patient_id is None:
            return
        tid = self._selected_id()
        if tid is None:
            return
        rows = database.get_treatments(self.patient_id)
        record = next((r for r in rows if r["id"] == tid), None)
        if not record:
            return
        dlg = TreatmentDialog(self, record)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        d = dlg.get_data()
        if not d["procedure"]:
            QMessageBox.warning(self, "Missing data", "Procedure is required.")
            return
        # Simplest: delete + reinsert (keeps module lean without an update helper)
        database.delete_treatment(tid)
        database.add_treatment(
            self.patient_id,
            procedure=d["procedure"],
            tooth_number=d["tooth_number"],
            treatment_date=d["treatment_date"],
            notes=d["notes"],
        )
        audit_log.log("treatment_edited", patient_id=self.patient_id,
                      details=f"{d['procedure']} ({d['treatment_date']})")
        self._refresh()
        self.changed.emit()

    def _on_delete(self):
        tid = self._selected_id()
        if tid is None:
            return
        r = QMessageBox.question(self, "Confirm",
            "Delete this treatment record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        database.delete_treatment(tid)
        audit_log.log("treatment_deleted", patient_id=self.patient_id)
        self._refresh()
        self.changed.emit()
