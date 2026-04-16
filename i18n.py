"""Minimal i18n — English + Arabic. Use tr('key') to translate. Setting the
app layout direction to RTL happens at app startup based on config.language."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

LANG_EN = "en"
LANG_AR = "ar"
LANGUAGES = [(LANG_EN, "English"), (LANG_AR, "العربية")]

_current = LANG_EN

TRANSLATIONS = {
    LANG_AR: {
        # Menus
        "&File": "&ملف",
        "&Patient": "&المريض",
        "&Image": "&الصورة",
        "&Tools": "&الأدوات",
        "&View": "&عرض",
        "&Acquire": "&التقاط",
        "&Help": "&مساعدة",

        # File menu
        "Import Image…": "استيراد صورة…",
        "Import DICOM…": "استيراد DICOM…",
        "Export Current…": "تصدير الصورة الحالية…",
        "Export as DICOM…": "تصدير كـ DICOM…",
        "Patient Report (PDF)…": "تقرير المريض (PDF)…",
        "Print…": "طباعة…",
        "Backup Now…": "نسخ احتياطي الآن…",
        "Restore From Backup…": "استعادة من نسخة احتياطية…",
        "Backup & Clinic Settings…": "إعدادات النسخ والعيادة…",
        "Exit": "خروج",

        # Patient menu
        "New Patient…": "مريض جديد…",
        "Edit Patient…": "تعديل المريض…",
        "Delete Patient": "حذف المريض",

        # Image menu
        "Fit to Window": "ملاءمة للنافذة",
        "Rotate Left": "تدوير يسار",
        "Rotate Right": "تدوير يمين",
        "Flip Horizontal": "قلب أفقي",
        "Flip Vertical": "قلب عمودي",
        "Reset Adjustments": "إعادة الضبط",
        "Restore Original (discard edits)": "استعادة الأصلية (تجاهل التعديلات)",

        # Tools
        "Pan": "تحريك",
        "Measure": "قياس",
        "Calibrate…": "معايرة…",
        "Arrow": "سهم",
        "Text": "نص",
        "Freehand Draw": "رسم حر",
        "Circle": "دائرة",
        "Rectangle": "مستطيل",
        "Magnifier": "مكبّرة",
        "Undo Annotation": "تراجع",
        "Clear All Annotations": "مسح جميع التعليقات",
        "Annotation Color…": "لون التعليق…",

        # View / tabs
        "Image Viewer": "عارض الصور",
        "Full Mouth Series": "سلسلة الفم الكاملة",
        "Compare": "مقارنة",
        "Odontogram": "خريطة الأسنان",
        "Treatments": "العلاجات",

        # Common
        "Search patients…": "بحث عن مريض…",
        "+ New": "+ جديد",
        "Images:": "الصور:",
        "Show All": "عرض الكل",
        "Import": "استيراد",
        "Delete": "حذف",
        "Type:": "النوع:",
        "Ready": "جاهز",
        "OK": "موافق",
        "Cancel": "إلغاء",
        "Save": "حفظ",
        "Reset": "إعادة",
        "Error": "خطأ",
        "Info": "معلومة",
        "Confirm": "تأكيد",
        "Yes": "نعم",
        "No": "لا",

        # Patient dialog
        "First Name *:": "الاسم الأول *:",
        "Last Name *:": "اسم العائلة *:",
        "Date of Birth:": "تاريخ الميلاد:",
        "Gender:": "الجنس:",
        "Phone:": "الهاتف:",
        "Email:": "البريد الإلكتروني:",
        "Medical History:": "التاريخ الطبي:",
        "Notes:": "ملاحظات:",
        "Male": "ذكر",
        "Female": "أنثى",
        "Other": "آخر",

        # Odontogram statuses
        "Healthy": "سليم",
        "Caries": "تسوس",
        "Filled": "محشو",
        "Crown": "تاج",
        "Root Canal": "علاج عصب",
        "Extracted": "مقلوع",
        "Missing": "مفقود",
        "Implant": "زرع",
        "Bridge": "جسر",
        "Sealant": "مادة عازلة",

        # Treatments
        "Treatment Log": "سجل العلاجات",
        "Add Treatment": "إضافة علاج",
        "Edit Treatment": "تعديل علاج",
        "Delete Treatment": "حذف علاج",
        "Date:": "التاريخ:",
        "Tooth:": "السن:",
        "Procedure:": "الإجراء:",
        "No patient selected": "لم يتم اختيار مريض",

        # Wizard
        "Welcome": "مرحباً",
        "Clinic Setup": "إعداد العيادة",
        "Backup": "نسخ احتياطي",
        "Clinic name:": "اسم العيادة:",
        "Doctor name:": "اسم الطبيب:",
        "Backup folder:": "مجلد النسخ الاحتياطي:",
        "Browse…": "تصفح…",
        "Skip": "تخطي",
        "Finish": "إنهاء",

        # Disclaimer
        "Notice": "تنبيه طبي",
        "This software is a viewing & workflow tool.":
            "هذا البرنامج أداة عرض ومتابعة.",
        "It is NOT a certified medical device.":
            "ليس جهازاً طبياً معتمداً.",
    },
}


def set_language(lang_code):
    global _current
    _current = lang_code if lang_code in (LANG_EN, LANG_AR) else LANG_EN
    app = QApplication.instance()
    if app is not None:
        if _current == LANG_AR:
            app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        else:
            app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)


def current_language():
    return _current


def tr(text):
    """Translate text. Falls back to the English source when missing."""
    if _current == LANG_EN:
        return text
    return TRANSLATIONS.get(_current, {}).get(text, text)
