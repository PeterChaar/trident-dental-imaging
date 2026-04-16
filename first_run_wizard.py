"""First-run setup wizard — runs on first launch (no config.json) or when
invoked manually. Collects clinic name, doctor, language, backup folder."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QFileDialog, QHBoxLayout, QWidget,
    QSpinBox,
)

import backup
import i18n


class WelcomePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Welcome")
        self.setSubTitle("Let's set up your clinic — takes about 1 minute.")

        layout = QVBoxLayout(self)
        msg = QLabel(
            "This wizard will configure:\n\n"
            "  •  Clinic name and doctor (shown on reports)\n"
            "  •  Interface language (English or Arabic)\n"
            "  •  Automatic backup folder (a USB drive is recommended)\n\n"
            "You can change any of these later from File → Backup & Clinic Settings."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        note = QLabel(
            "<b>Medical notice:</b> This software is a viewing and workflow "
            "tool. It is NOT a certified medical device. Always confirm "
            "diagnoses with certified software and clinical examination."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#f0ad4e; padding-top:12px;")
        layout.addWidget(note)


class ClinicPage(QWizardPage):
    def __init__(self, cfg):
        super().__init__()
        self.setTitle("Clinic Information")
        self.setSubTitle("These appear on PDF reports and prints.")

        f = QFormLayout(self)
        self.clinic = QLineEdit(cfg.get("clinic_name") or "")
        self.clinic.setPlaceholderText("e.g. Bekaa Valley Dental")
        self.doctor = QLineEdit(cfg.get("doctor_name") or "")
        self.doctor.setPlaceholderText("e.g. Dr. Khoury")

        self.lang = QComboBox()
        for code, label in i18n.LANGUAGES:
            self.lang.addItem(label, code)
        cur = cfg.get("language", "en")
        for i in range(self.lang.count()):
            if self.lang.itemData(i) == cur:
                self.lang.setCurrentIndex(i)
                break

        f.addRow("Clinic name:", self.clinic)
        f.addRow("Doctor name:", self.doctor)
        f.addRow("Language:", self.lang)

        self.registerField("clinic_name*", self.clinic)
        self.registerField("doctor_name", self.doctor)
        self.registerField("language", self.lang, "currentData")


class BackupPage(QWizardPage):
    def __init__(self, cfg):
        super().__init__()
        self.setTitle("Backup")
        self.setSubTitle(
            "Pick a folder — ideally on a USB drive you keep separate from "
            "the clinic PC. The app can back up automatically when you close it."
        )

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.folder = QLineEdit(cfg.get("backup_folder") or "")
        self.folder.setPlaceholderText("e.g. E:\\TridentBackups")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.folder)
        row.addWidget(browse)
        holder = QWidget()
        holder.setLayout(row)

        form = QFormLayout()
        form.addRow("Backup folder:", holder)

        self.auto = QCheckBox("Backup automatically when closing the app")
        self.auto.setChecked(bool(cfg.get("auto_backup_on_close", True)))

        self.keep = QSpinBox()
        self.keep.setRange(1, 100)
        self.keep.setValue(int(cfg.get("keep_last_backups", 10)))
        form.addRow("Keep last N backups:", self.keep)

        layout.addLayout(form)
        layout.addWidget(self.auto)

        hint = QLabel(
            "If you skip this, you can set it up later from "
            "File → Backup & Clinic Settings. Patient data safety depends on backups."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888; padding-top:10px; font-size:11px;")
        layout.addWidget(hint)

        self.registerField("backup_folder", self.folder)
        self.registerField("auto_backup_on_close", self.auto)
        self.registerField("keep_last_backups", self.keep)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choose backup folder")
        if d:
            self.folder.setText(d)


class FirstRunWizard(QWizard):
    def __init__(self, parent=None, cfg=None):
        super().__init__(parent)
        self.cfg = cfg or backup.load_config()
        self.setWindowTitle("Trident Dental Imaging — First-run setup")
        self.setMinimumSize(640, 460)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

        self.addPage(WelcomePage())
        self.addPage(ClinicPage(self.cfg))
        self.addPage(BackupPage(self.cfg))
        self.setButtonText(QWizard.WizardButton.FinishButton, "Finish")

    def result_config(self):
        self.cfg.update({
            "clinic_name": self.field("clinic_name") or "Dental Clinic",
            "doctor_name": self.field("doctor_name") or "",
            "language": self.field("language") or "en",
            "backup_folder": self.field("backup_folder") or "",
            "auto_backup_on_close": bool(self.field("auto_backup_on_close")),
            "keep_last_backups": int(self.field("keep_last_backups") or 10),
            "first_run_done": True,
        })
        return self.cfg


def needs_first_run(cfg):
    return not cfg.get("first_run_done") and not cfg.get("clinic_name", "").strip()
