import sys, os, shutil, sqlite3, subprocess, csv, base64
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import (
    Qt, QByteArray, QRectF, QPointF, QSize, QTimer, QVariantAnimation, QPropertyAnimation,
    QEasingCurve, QAbstractAnimation
)
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QDialog, QFormLayout, QTextEdit, QFileDialog, QHeaderView, QFrame,
    QTabWidget, QGroupBox, QGraphicsOpacityEffect, QStyledItemDelegate,
    QStyle, QStyleOptionViewItem, QSizePolicy
)

APP_NAME = "بانک اطلاعات مربیان فردیس"
STATUSES = ["در انتظار بررسی", "تأیید اولیه", "نیازمند تکمیل رزومه", "رد شده", "غیرفعال"]
CATEGORIES = ["خوشنویسی", "موسیقی", "هنرهای تجسمی", "نمایش و تئاتر", "صنایع‌دستی", "ادبیات و شعر", "قرآن و معارف", "مهارت‌های فرهنگی", "ورزش و تندرستی", "سایر"]
ALLOWED = "رزومه و سوابق (*.pdf *.doc *.docx *.rtf *.odt *.jpg *.jpeg *.png);;همه فایل‌ها (*.*)"

# رنگ نشان وضعیت‌ها در جدول: (رنگ متن, رنگ پس‌زمینه)
STATUS_COLORS = {
    "در انتظار بررسی": ("#8a5a00", "#fff1cf"),
    "تأیید اولیه": ("#0f6b3a", "#dcf4e6"),
    "نیازمند تکمیل رزومه": ("#1d4f91", "#e0ecfb"),
    "رد شده": ("#a12a2a", "#fde2e2"),
    "غیرفعال": ("#5b6672", "#e8ecf0"),
}

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(n):
    return str(n).translate(FA_DIGITS)


def data_root():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    root = base / "BankMorabianFardis"
    (root / "Resumes").mkdir(parents=True, exist_ok=True)
    (root / "Backup").mkdir(exist_ok=True)
    return root

ROOT = data_root()
DB_PATH = ROOT / "coaches.db"


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS coaches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_code TEXT UNIQUE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT,
            specialty TEXT,
            education TEXT,
            experience TEXT,
            availability TEXT,
            status TEXT DEFAULT 'در انتظار بررسی',
            notes TEXT,
            created_at TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            added_at TEXT,
            FOREIGN KEY(coach_id) REFERENCES coaches(id) ON DELETE CASCADE
        )""")
        # سازگاری با پایگاه داده نسخه آزمایشی قبلی، در صورت وجود
        columns = {r["name"] for r in con.execute("PRAGMA table_info(coaches)").fetchall()}
        if "availability" not in columns:
            con.execute("ALTER TABLE coaches ADD COLUMN availability TEXT")


# ----------------------------------------------------------------------------
# ظاهر برنامه: فونت، پالت رنگ ثابت (مستقل از حالت تیره/روشن سیستم) و استایل
# ----------------------------------------------------------------------------
FONT_FAMILY = "Vazirmatn"


def load_fonts():
    """فونت وزیرمتن داخل برنامه ذخیره شده تا روی هر سیستمی فارسی یکسان دیده شود."""
    try:
        from fonts_data import FONT_REGULAR, FONT_MEDIUM, FONT_BOLD
        ok = False
        for data in (FONT_REGULAR, FONT_MEDIUM, FONT_BOLD):
            if QFontDatabase.addApplicationFontFromData(QByteArray(base64.b64decode(data))) != -1:
                ok = True
        return ok
    except Exception:
        return False


def light_palette():
    """پالت روشن صریح؛ علت باگ «متن سفید روی کادر سفید» در حالت Dark مک همین بود که
    رنگ متن از سیستم می‌آمد ولی پس‌زمینه کادرها سفید ثابت بود."""
    p = QPalette()
    roles = {
        QPalette.Window: "#f3f6fa", QPalette.WindowText: "#1f2d3a",
        QPalette.Base: "#ffffff", QPalette.AlternateBase: "#f7fafc",
        QPalette.Text: "#1f2d3a", QPalette.PlaceholderText: "#8a99a8",
        QPalette.Button: "#e6eef3", QPalette.ButtonText: "#17324d",
        QPalette.ToolTipBase: "#17324d", QPalette.ToolTipText: "#ffffff",
        QPalette.Highlight: "#176b75", QPalette.HighlightedText: "#ffffff",
        QPalette.Link: "#176b75", QPalette.BrightText: "#ffffff",
    }
    for role, color in roles.items():
        p.setColor(QPalette.Active, role, QColor(color))
        p.setColor(QPalette.Inactive, role, QColor(color))
        p.setColor(QPalette.Disabled, role, QColor(color))
    p.setColor(QPalette.Disabled, QPalette.Text, QColor("#9aa8b5"))
    p.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#9aa8b5"))
    p.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#9aa8b5"))
    return p


STYLE = """
* { font-family: "Vazirmatn"; font-size: 14px; color: #1f2d3a; }
QMainWindow, QDialog { background: #f3f6fa; }
QWidget#page { background: transparent; }

QFrame#banner {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #17324d, stop:1 #176b75);
    border-radius: 16px;
}
QLabel#header { background: transparent; color: #ffffff; font-size: 26px; font-weight: 700; }
QLabel#subtitle { background: transparent; color: #cfe5ec; font-size: 13px; }
QLabel#count { background: #e1edf2; color: #17324d; border-radius: 12px; padding: 4px 14px; font-weight: 600; }
QLabel#selected { color: #526579; }
QLabel#hint { background: #fff6e8; color: #7b4b16; border: 1px solid #f1d9b0; border-radius: 12px; padding: 14px; }
QLabel#error { color: #b93636; font-weight: 500; }
QLabel#dlgTitle { color: #17324d; font-size: 19px; font-weight: 700; }
QLabel#boxText { color: #33475b; line-height: 160%; }
QLabel#noticeText { color: #1f2d3a; font-size: 14px; }
QLabel#noticeTitle { color: #17324d; font-size: 16px; font-weight: 700; }

QLineEdit, QTextEdit, QComboBox {
    background: #ffffff; color: #1f2d3a;
    border: 1.5px solid #d3dde6; border-radius: 10px; padding: 7px 12px;
    selection-background-color: #176b75; selection-color: #ffffff;
}
QLineEdit:hover, QTextEdit:hover, QComboBox:hover { border: 1.5px solid #a9bfcd; }
QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1.5px solid #176b75; }
QLineEdit[invalid="true"] { border: 1.5px solid #d64545; background: #fff7f7; }
QComboBox { padding-left: 34px; }
QComboBox::drop-down { border: 0; width: 30px; subcontrol-origin: padding; subcontrol-position: center left; }
QComboBox::down-arrow { image: none; width: 0px; height: 0px; }
QComboBox QAbstractItemView {
    background: #ffffff; color: #1f2d3a; border: 1px solid #d3dde6; border-radius: 8px;
    selection-background-color: #d3ebee; selection-color: #0f3d44; outline: 0; padding: 4px;
}

QTabWidget::pane { border: 0; background: transparent; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: transparent; color: #526579; padding: 10px 24px; margin: 0 0 8px 8px;
    border-radius: 12px; font-weight: 600;
}
QTabBar::tab:selected { background: #ffffff; color: #176b75; }
QTabBar::tab:hover:!selected { background: #e3edf2; }

QTableWidget {
    background: #ffffff; alternate-background-color: #f7fafc; color: #1f2d3a;
    border: 1px solid #dbe4ec; border-radius: 14px; gridline-color: transparent; outline: 0;
}
QTableWidget::item { padding: 4px 8px; border: 0; }
QTableWidget::item:hover { background: #eef6f8; }
QTableWidget::item:selected { background: #d3ebee; color: #0f3d44; }
QHeaderView { background: transparent; }
QHeaderView::section {
    background: #eaf1f5; color: #17324d; padding: 11px 8px; border: 0; font-weight: 700;
}
QTableCornerButton::section { background: #eaf1f5; border: 0; }

QGroupBox {
    background: #ffffff; border: 1px solid #dbe4ec; border-radius: 14px;
    margin-top: 18px; padding: 22px 18px 16px 18px; font-weight: 700;
}
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top right; padding: 0 12px; margin-right: 14px; background: #f3f6fa; color: #176b75; font-size: 15px; }

QScrollBar:vertical { background: transparent; width: 12px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: #c3d0db; border-radius: 4px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: #9fb3c3; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px 4px; }
QScrollBar::handle:horizontal { background: #c3d0db; border-radius: 4px; min-width: 36px; }
QScrollBar::handle:horizontal:hover { background: #9fb3c3; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QToolTip { background: #17324d; color: #ffffff; border: 0; padding: 6px 10px; }
"""


def apply_theme(app):
    load_fonts()
    app.setStyle("Fusion")
    app.setPalette(light_palette())
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(STYLE)


def fade_in(widget, duration=240, start=0.0):
    """محو شدن نرم هنگام نمایش یک بخش."""
    eff = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(eff)
    anim = QPropertyAnimation(eff, b"opacity", widget)
    anim.setDuration(duration); anim.setStartValue(start); anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: QTimer.singleShot(0, lambda: widget.setGraphicsEffect(None)))
    widget._fade_anim = anim
    anim.start()


def fade_window(win, duration=200):
    win.setWindowOpacity(0.0)
    anim = QPropertyAnimation(win, b"windowOpacity", win)
    anim.setDuration(duration); anim.setStartValue(0.0); anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    win._win_anim = anim
    anim.start()


class AnimButton(QPushButton):
    """دکمه با تغییر رنگ نرم هنگام قرار گرفتن ماوس و کلیک."""
    COLORS = {  # عادی، هاور، فشرده، متن
        "primary": ("#176b75", "#1e8591", "#10535b", "#ffffff"),
        "secondary": ("#e3edf2", "#d3e2ea", "#c2d6e1", "#17324d"),
        "danger": ("#d64545", "#e25a5a", "#b53636", "#ffffff"),
    }

    def __init__(self, text, kind="primary", parent=None):
        super().__init__(text, parent)
        self.kind = kind
        self._base, self._hover, self._press, self._fg = [QColor(c) for c in self.COLORS[kind]]
        self._cur = QColor(self._base)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set_color)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(40)

    def _set_color(self, c):
        self._cur = QColor(c); self.update()

    def _go(self, target):
        self._anim.stop()
        self._anim.setStartValue(self._cur)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, e): self._go(self._hover); super().enterEvent(e)
    def leaveEvent(self, e): self._go(self._base); super().leaveEvent(e)
    def mousePressEvent(self, e): self._go(self._press); super().mousePressEvent(e)
    def mouseReleaseEvent(self, e):
        self._go(self._hover if self.rect().contains(e.position().toPoint()) else self._base)
        super().mouseReleaseEvent(e)

    def sizeHint(self):
        return QSize(self.fontMetrics().horizontalAdvance(self.text()) + 40, 42)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        enabled = self.isEnabled()
        p.setPen(Qt.NoPen)
        p.setBrush(self._cur if enabled else QColor("#d5dee6"))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        f = self.font(); f.setWeight(QFont.Medium); p.setFont(f)
        p.setPen(self._fg if enabled else QColor("#8a99a8"))
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        if self.hasFocus() and self.focusPolicy() != Qt.NoFocus:
            p.setPen(QColor(23, 107, 117, 140)); p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 8, 8)


class ArrowCombo(QComboBox):
    """لیست کشویی با فلش رسم‌شده (فلش پیش‌فرض Qt با استایل سفارشی نمایش داده نمی‌شود)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(40)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#5b6b7b")); pen.setWidthF(2.0); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        cx, cy = 20, self.height() / 2 + 1
        p.drawPolyline([QPointF(cx - 5, cy - 3), QPointF(cx, cy + 2), QPointF(cx + 5, cy - 3)])


class StatusDelegate(QStyledItemDelegate):
    """نمایش وضعیت به‌صورت برچسب رنگی داخل جدول."""
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)
        fg, bg = STATUS_COLORS.get(text, ("#334155", "#e8ecf0"))
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        fm = painter.fontMetrics()
        width = min(fm.horizontalAdvance(text) + 28, option.rect.width() - 10)
        r = QRectF(0, 0, width, 28)
        r.moveCenter(QRectF(option.rect).center())
        painter.setPen(Qt.NoPen); painter.setBrush(QColor(bg))
        painter.drawRoundedRect(r, 14, 14)
        painter.setPen(QColor(fg))
        painter.drawText(r, Qt.AlignCenter, fm.elidedText(text, Qt.ElideRight, int(r.width()) - 14))
        painter.restore()


class Notice(QDialog):
    """پنجره پیام فارسی و هماهنگ با ظاهر برنامه (جایگزین QMessageBox)."""
    KINDS = {
        "info": ("i", "#176b75", "#dff1f3"), "ok": ("✓", "#0f6b3a", "#dcf4e6"),
        "warn": ("!", "#9a6a00", "#fff1cf"), "ask": ("?", "#176b75", "#dff1f3"),
        "danger": ("!", "#a12a2a", "#fde2e2"),
    }

    def __init__(self, parent, kind, title, text, buttons):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(440)
        glyph, fg, bg = self.KINDS[kind]
        root = QVBoxLayout(self); root.setContentsMargins(26, 24, 26, 20); root.setSpacing(18)
        row = QHBoxLayout(); row.setSpacing(16)
        icon = QLabel(glyph); icon.setFixedSize(46, 46); icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:23px; font-size:22px; font-weight:700;")
        row.addWidget(icon, 0, Qt.AlignTop)
        col = QVBoxLayout(); col.setSpacing(6)
        t = QLabel(title); t.setObjectName("noticeTitle"); col.addWidget(t)
        m = QLabel(text); m.setObjectName("noticeText"); m.setWordWrap(True)
        m.setTextInteractionFlags(Qt.TextSelectableByMouse); col.addWidget(m)
        row.addLayout(col, 1)
        root.addLayout(row)
        bar = QHBoxLayout(); bar.setSpacing(10)
        for label, btn_kind, result in buttons:
            b = AnimButton(label, btn_kind); b.setMinimumWidth(96)
            b.clicked.connect(lambda checked=False, r=result: self.done(r))
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)

    def showEvent(self, e):
        super().showEvent(e); fade_window(self, 170)


def notify(parent, kind, title, text):
    Notice(parent, kind, title, text, [("تأیید", "primary", 1)]).exec()


def confirm(parent, title, text, yes="بله", no="خیر", danger=False):
    d = Notice(parent, "danger" if danger else "ask", title, text,
               [(yes, "danger" if danger else "primary", 1), (no, "secondary", 0)])
    return d.exec() == 1


class CoachDialog(QDialog):
    def __init__(self, parent=None, row=None):
        super().__init__(parent)
        self.setWindowTitle("ثبت / ویرایش اطلاعات مربی")
        self.setMinimumWidth(620)
        self.setLayoutDirection(Qt.RightToLeft)
        self.row = row
        root = QVBoxLayout(self); root.setContentsMargins(28, 24, 28, 22); root.setSpacing(16)
        title = QLabel("ویرایش پرونده مربی" if row else "ثبت پرونده مربی جدید"); title.setObjectName("dlgTitle")
        root.addWidget(title)
        form = QFormLayout()
        form.setHorizontalSpacing(18); form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        root.addLayout(form)
        self.first = QLineEdit()
        self.last = QLineEdit()
        self.phone = QLineEdit()
        self.specialty = ArrowCombo(); self.specialty.setEditable(True); self.specialty.addItems(CATEGORIES)
        self.education = QLineEdit()
        self.experience = QTextEdit(); self.experience.setFixedHeight(96); self.experience.setTabChangesFocus(True)
        self.availability = QLineEdit(); self.availability.setPlaceholderText("مثلاً صبح‌ها، عصرها، روزهای زوج...")
        self.status = ArrowCombo(); self.status.addItems(STATUSES)
        self.notes = QTextEdit(); self.notes.setFixedHeight(76); self.notes.setTabChangesFocus(True)
        for label, widget in [
            ("نام *", self.first), ("نام خانوادگی *", self.last),
            ("شماره تماس", self.phone), ("رشته / تخصص اصلی", self.specialty),
            ("تحصیلات و مدارک تخصصی", self.education),
            ("خلاصه سوابق تدریس و فعالیت", self.experience),
            ("زمان‌های همکاری", self.availability), ("وضعیت بررسی", self.status),
            ("یادداشت کارشناسی", self.notes)
        ]: form.addRow(label, widget)
        self.error = QLabel(""); self.error.setObjectName("error"); self.error.hide()
        root.addWidget(self.error)
        buttons = QHBoxLayout(); buttons.setSpacing(10)
        save = AnimButton("ذخیره پرونده", "primary"); cancel = AnimButton("انصراف", "secondary")
        save.setMinimumWidth(130); cancel.setMinimumWidth(100)
        save.setDefault(True)
        save.clicked.connect(self.accept); cancel.clicked.connect(self.reject)
        buttons.addWidget(save); buttons.addWidget(cancel); buttons.addStretch(1)
        root.addLayout(buttons)
        for w in (self.first, self.last):
            w.textChanged.connect(lambda _=None, w=w: self._mark(w, False))
        if row:
            self.first.setText(row["first_name"] or "")
            self.last.setText(row["last_name"] or "")
            self.phone.setText(row["phone"] or "")
            self.specialty.setCurrentText(row["specialty"] or "")
            self.education.setText(row["education"] or "")
            self.experience.setPlainText(row["experience"] or "")
            self.availability.setText(row["availability"] or "")
            self.status.setCurrentText(row["status"] or STATUSES[0])
            self.notes.setPlainText(row["notes"] or "")

    def _mark(self, widget, bad):
        widget.setProperty("invalid", bad)
        widget.style().unpolish(widget); widget.style().polish(widget)

    def accept(self):
        # اعتبارسنجی داخل همان پنجره تا با خالی بودن نام، اطلاعات واردشده از بین نرود
        missing = [w for w in (self.first, self.last) if not w.text().strip()]
        for w in (self.first, self.last):
            self._mark(w, w in missing)
        if missing:
            self.error.setText("نام و نام خانوادگی الزامی است."); self.error.show()
            missing[0].setFocus()
            return
        super().accept()

    def showEvent(self, e):
        super().showEvent(e); fade_window(self, 200)

    def values(self):
        return [self.first.text().strip(), self.last.text().strip(), self.phone.text().strip(),
                self.specialty.currentText().strip(), self.education.text().strip(),
                self.experience.toPlainText().strip(), self.availability.text().strip(),
                self.status.currentText(), self.notes.toPlainText().strip()]


class MainWindow(QMainWindow):
    NO_SELECTION = "برای افزودن یا مشاهده رزومه، ابتدا یک پرونده را انتخاب کنید."

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1240, 780)
        self.setMinimumSize(1000, 640)
        self.current_id = None
        central = QWidget(); central.setLayoutDirection(Qt.RightToLeft); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(24, 20, 24, 18); root.setSpacing(14)

        banner = QFrame(); banner.setObjectName("banner")
        bl_ = QVBoxLayout(banner); bl_.setContentsMargins(20, 18, 20, 18); bl_.setSpacing(4)
        header = QLabel("بانک اطلاعات مربیان فردیس"); header.setObjectName("header"); header.setAlignment(Qt.AlignCenter)
        bl_.addWidget(header)
        subtitle = QLabel("سامانه شناسایی، ارزیابی و ساماندهی مربیان و فعالان فرهنگی و هنری سازمان فرهنگی شهرداری فردیس")
        subtitle.setAlignment(Qt.AlignCenter); subtitle.setObjectName("subtitle"); bl_.addWidget(subtitle)
        root.addWidget(banner)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)

        page = QWidget(); page.setObjectName("page")
        layout = QVBoxLayout(page); layout.setContentsMargins(0, 4, 0, 0); layout.setSpacing(12)
        tools = QHBoxLayout(); tools.setSpacing(10)
        self.search = QLineEdit(); self.search.setPlaceholderText("جست‌وجو: نام، نام خانوادگی، تخصص، شماره تماس یا کد پرونده")
        self.search.setClearButtonEnabled(True); self.search.setMinimumHeight(40)
        self.search.textChanged.connect(self.load_rows); tools.addWidget(self.search, 1)
        self.filter_status = ArrowCombo(); self.filter_status.addItems(["همه وضعیت‌ها"] + STATUSES)
        self.filter_status.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed); self.filter_status.setMinimumWidth(190)
        self.filter_status.currentTextChanged.connect(self.load_rows); tools.addWidget(self.filter_status)
        add = AnimButton("＋ پرونده جدید", "primary"); add.clicked.connect(self.add_coach); tools.addWidget(add)
        edit = AnimButton("ویرایش", "secondary"); edit.clicked.connect(self.edit_coach); tools.addWidget(edit)
        delete = AnimButton("حذف", "danger"); delete.clicked.connect(self.delete_coach); tools.addWidget(delete)
        layout.addLayout(tools)
        counter = QHBoxLayout()
        self.count_label = QLabel(f"تعداد پرونده‌ها: {fa(0)}"); self.count_label.setObjectName("count")
        counter.addWidget(self.count_label); counter.addStretch(1); layout.addLayout(counter)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["کد پرونده", "نام", "نام خانوادگی", "تخصص", "شماره تماس", "تحصیلات", "وضعیت", "تاریخ ثبت"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        hh = self.table.horizontalHeader(); hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents); hh.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        hh.setMinimumSectionSize(90); hh.setHighlightSections(False)
        self.table.verticalHeader().setVisible(False); self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setShowGrid(False); self.table.setAlternatingRowColors(True)
        self.table.setMouseTracking(True); self.table.setFocusPolicy(Qt.StrongFocus)
        self.table.setItemDelegateForColumn(6, StatusDelegate(self.table))
        self.table.itemSelectionChanged.connect(self.selection_changed); self.table.doubleClicked.connect(self.edit_coach)
        layout.addWidget(self.table, 1)
        filebar = QHBoxLayout(); filebar.setSpacing(10)
        self.selected_label = QLabel(self.NO_SELECTION); self.selected_label.setObjectName("selected")
        filebar.addWidget(self.selected_label, 1)
        addfile = AnimButton("افزودن رزومه / سوابق", "secondary"); addfile.clicked.connect(self.add_attachment); filebar.addWidget(addfile)
        viewfile = AnimButton("مشاهده فایل‌های پرونده", "secondary"); viewfile.clicked.connect(self.view_attachments); filebar.addWidget(viewfile)
        layout.addLayout(filebar)
        self.tabs.addTab(page, "پرونده مربیان")

        info = QWidget(); info.setObjectName("page")
        il = QVBoxLayout(info); il.setContentsMargins(0, 4, 0, 0); il.setSpacing(12)
        box = QGroupBox("دامنه نسخه اول")
        bl = QVBoxLayout(box)
        txt = QLabel("این نسخه برای شناسایی و ارزیابی اولیه مربیان طراحی شده است. فقط اطلاعات حرفه‌ای، تخصص‌ها، تحصیلات، سوابق و رزومه دریافت می‌شود. هیچ فیلد یا بخشی برای کد ملی و مدارک هویتی در این نسخه وجود ندارد. مدارک هویتی در صورت انعقاد قرارداد، توسط واحد حقوقی دریافت خواهد شد.")
        txt.setWordWrap(True); txt.setObjectName("boxText"); bl.addWidget(txt)
        il.addWidget(box)
        backup = AnimButton("تهیه نسخه پشتیبان از پایگاه داده و فایل‌های رزومه", "primary"); backup.clicked.connect(self.backup); il.addWidget(backup)
        export = AnimButton("خروجی اکسل‌خوان (CSV) از فهرست مربیان", "secondary"); export.clicked.connect(self.export_csv); il.addWidget(export)
        openfolder = AnimButton("باز کردن پوشه اطلاعات نرم‌افزار", "secondary"); openfolder.clicked.connect(self.open_data_folder); il.addWidget(openfolder)
        for b in (backup, export, openfolder): b.setMinimumHeight(46)
        warning = QLabel("نکته: اطلاعات فقط روی همین رایانه ذخیره می‌شود. از پوشه پشتیبان در محل امن نگهداری کنید."); warning.setWordWrap(True); warning.setObjectName("hint"); il.addWidget(warning)
        il.addStretch(); self.tabs.addTab(info, "پشتیبان‌گیری و راهنما")
        self.tabs.currentChanged.connect(lambda i: fade_in(self.tabs.widget(i), 260, 0.1))
        self.load_rows()

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_shown_once", False):
            self._shown_once = True; fade_window(self, 260)

    def load_rows(self):
        q = self.search.text().strip() if hasattr(self, "search") else ""
        status = self.filter_status.currentText() if hasattr(self, "filter_status") else "همه وضعیت‌ها"
        sql = "SELECT * FROM coaches WHERE (first_name LIKE ? OR last_name LIKE ? OR specialty LIKE ? OR phone LIKE ? OR file_code LIKE ?)"
        args = [f"%{q}%"] * 5
        if status != "همه وضعیت‌ها": sql += " AND status=?"; args.append(status)
        sql += " ORDER BY id DESC"
        with connect() as con: rows = con.execute(sql, args).fetchall()
        self.table.setRowCount(0)
        for r in rows:
            i = self.table.rowCount(); self.table.insertRow(i)
            vals = [r["file_code"], r["first_name"], r["last_name"], r["specialty"], r["phone"], r["education"], r["status"], ("\u202a" + (r["created_at"] or "")[:16] + "\u202c") if r["created_at"] else ""]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v or "")); item.setTextAlignment(Qt.AlignCenter); self.table.setItem(i, c, item)
            self.table.item(i, 0).setData(Qt.UserRole, r["id"])
        self.count_label.setText(f"تعداد پرونده‌های نمایش‌داده‌شده: {fa(len(rows))}")
        self.current_id = None; self.selected_label.setText(self.NO_SELECTION)

    def selection_changed(self):
        items = self.table.selectedItems()
        self.current_id = self.table.item(items[0].row(), 0).data(Qt.UserRole) if items else None
        self.selected_label.setText(f"کد پرونده انتخاب‌شده: {self.table.item(items[0].row(), 0).text()}" if items else "پرونده‌ای انتخاب نشده است.")

    def need_selection(self):
        notify(self, "info", "انتخاب پرونده", "ابتدا یک پرونده را انتخاب کنید.")

    def add_coach(self):
        d = CoachDialog(self)
        if d.exec() == QDialog.Accepted:
            v = d.values()
            if not v[0] or not v[1]: notify(self, "warn", "اطلاعات ناقص", "نام و نام خانوادگی الزامی است."); return
            with connect() as con:
                cur = con.execute("""INSERT INTO coaches(first_name,last_name,phone,specialty,education,experience,availability,status,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""", v + [datetime.now().strftime("%Y-%m-%d %H:%M")])
                con.execute("UPDATE coaches SET file_code=? WHERE id=?", (f"ART-{cur.lastrowid:05d}", cur.lastrowid))
            self.load_rows()

    def edit_coach(self):
        if not self.current_id: self.need_selection(); return
        with connect() as con: row = con.execute("SELECT * FROM coaches WHERE id=?", (self.current_id,)).fetchone()
        d = CoachDialog(self, row)
        if d.exec() == QDialog.Accepted:
            v = d.values()
            if not v[0] or not v[1]: notify(self, "warn", "اطلاعات ناقص", "نام و نام خانوادگی الزامی است."); return
            with connect() as con:
                con.execute("""UPDATE coaches SET first_name=?,last_name=?,phone=?,specialty=?,education=?,experience=?,availability=?,status=?,notes=? WHERE id=?""", v + [self.current_id])
            self.load_rows()

    def delete_coach(self):
        if not self.current_id: self.need_selection(); return
        if confirm(self, "تأیید حذف", "پرونده مربی و پیوند فایل‌های رزومه آن حذف شود؟", yes="بله، حذف شود", no="انصراف", danger=True):
            with connect() as con: con.execute("DELETE FROM coaches WHERE id=?", (self.current_id,))
            self.load_rows()

    def add_attachment(self):
        if not self.current_id: self.need_selection(); return
        files, _ = QFileDialog.getOpenFileNames(self, "انتخاب رزومه و سوابق", "", ALLOWED)
        if not files: return
        with connect() as con:
            row = con.execute("SELECT file_code FROM coaches WHERE id=?", (self.current_id,)).fetchone()
            folder = ROOT / "Resumes" / row["file_code"]; folder.mkdir(parents=True, exist_ok=True)
            for src in files:
                srcp = Path(src); dest = folder / srcp.name; n = 1
                while dest.exists(): dest = folder / f"{srcp.stem}_{n}{srcp.suffix}"; n += 1
                shutil.copy2(srcp, dest)
                con.execute("INSERT INTO attachments(coach_id,title,stored_path,added_at) VALUES(?,?,?,?)", (self.current_id, srcp.name, str(dest), datetime.now().isoformat(timespec="minutes")))
        notify(self, "ok", "ثبت فایل", "فایل‌های انتخاب‌شده به پرونده مربی پیوست شدند.")

    def view_attachments(self):
        if not self.current_id: self.need_selection(); return
        with connect() as con: docs = con.execute("SELECT * FROM attachments WHERE coach_id=? ORDER BY id DESC", (self.current_id,)).fetchall()
        if not docs: notify(self, "info", "فایل‌های پرونده", "برای این پرونده رزومه یا فایلی ثبت نشده است."); return
        dlg = QDialog(self); dlg.setWindowTitle("رزومه و سوابق پرونده"); dlg.setLayoutDirection(Qt.RightToLeft); dlg.resize(540, 340)
        lay = QVBoxLayout(dlg); lay.setContentsMargins(26, 22, 26, 22); lay.setSpacing(10)
        t = QLabel("فایل‌های پیوست‌شده به پرونده"); t.setObjectName("dlgTitle"); lay.addWidget(t)
        for doc in docs:
            b = AnimButton(doc["title"], "secondary"); b.clicked.connect(lambda checked=False, p=doc["stored_path"]: self.open_file(p)); lay.addWidget(b)
        lay.addStretch(1)
        dlg.showEvent = lambda e, d=dlg: (QDialog.showEvent(d, e), fade_window(d, 180))
        dlg.exec()

    def open_file(self, path):
        if not Path(path).exists(): notify(self, "warn", "فایل پیدا نشد", "فایل پیوست در مسیر ذخیره‌شده وجود ندارد."); return
        if os.name == "nt": os.startfile(path)
        elif sys.platform == "darwin": subprocess.Popen(["open", path])
        else: subprocess.Popen(["xdg-open", path])

    def open_data_folder(self):
        if os.name == "nt": os.startfile(str(ROOT))
        elif sys.platform == "darwin": subprocess.Popen(["open", str(ROOT)])
        else: subprocess.Popen(["xdg-open", str(ROOT)])

    def backup(self):
        dest = QFileDialog.getExistingDirectory(self, "محل ذخیره نسخه پشتیبان")
        if not dest: return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = Path(dest) / f"Backup_BankMorabian_{stamp}"
        shutil.copytree(ROOT, target)
        notify(self, "ok", "پشتیبان‌گیری", f"نسخه پشتیبان با موفقیت ایجاد شد:\n{target}")

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره فهرست مربیان", "فهرست_مربیان.csv", "CSV (*.csv)")
        if not path: return
        with connect() as con: rows = con.execute("SELECT file_code,first_name,last_name,phone,specialty,education,experience,availability,status,notes,created_at FROM coaches ORDER BY id").fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f); writer.writerow(["کد پرونده","نام","نام خانوادگی","تلفن","تخصص","تحصیلات","سوابق","زمان همکاری","وضعیت","یادداشت","تاریخ ثبت"])
            for r in rows: writer.writerow(list(r))
        notify(self, "ok", "خروجی", "فهرست مربیان با موفقیت ذخیره شد.")


def main():
    init_db()
    app = QApplication(sys.argv); app.setLayoutDirection(Qt.RightToLeft)
    apply_theme(app)
    window = MainWindow(); window.show(); sys.exit(app.exec())

if __name__ == "__main__": main()
