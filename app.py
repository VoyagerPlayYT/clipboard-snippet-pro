import sys
import os
import sqlite3
from datetime import datetime
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QFont, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QLabel,
    QTabWidget, QTextEdit, QDialog, QComboBox, QMessageBox, QFrame,
    QSplitter
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "clipboard_manager.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS clipboard_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL UNIQUE,
            is_pinned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS snippets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tag TEXT DEFAULT 'Общее',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Первичные сниппеты для мгновенной демонстрации родителям
    cur.execute("SELECT COUNT(*) FROM snippets")
    if cur.fetchone()[0] == 0:
        cur.executemany("""
            INSERT INTO snippets (title, content, tag)
            VALUES (?, ?, ?)
        """, [
            ("💳 Номер карты для перевода (Сбербанк)", "2202 2000 1234 5678 (Иван И.)", "Финансы"),
            ("🏡 Домашний адрес для доставки курьеров", "г. Москва, ул. Ленина, д. 42, кв. 108, подъезд 3, код 38К", "Личное"),
            ("📶 Гостевой пароль домашнего Wi-Fi", "HomeFamily_5G_SuperSecure2026!", "Сеть"),
            ("🐍 Python FastAPI стартовый шаблон", "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/')\ndef root(): return {'status': 'ok'}", "Код"),
            ("✉️ Шаблон делового письма", "Здравствуйте! Направляю вам обновленную версию документации и проекта. С уважением.", "Переписка")
        ])

    conn.commit()
    conn.close()


init_db()


class AddSnippetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создать новый сниппет • Obsidian & Amber")
        self.resize(440, 360)
        self.setStyleSheet("""
            QDialog {
                background-color: #0D0D0F;
                color: #F8FAFC;
            }
            QLabel {
                color: #94A3B8;
                font-size: 12px;
                font-weight: 600;
            }
            QLineEdit, QTextEdit, QComboBox {
                background-color: #141418;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                color: #F8FAFC;
                padding: 8px 12px;
                font-size: 13px;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid #F59E0B;
                background-color: #1A1A22;
            }
            QPushButton {
                background-color: #F59E0B;
                color: #0D0D0F;
                border-radius: 10px;
                padding: 10px 18px;
                font-weight: 700;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #D97706;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Название сниппета:"))
        self.title_input = QLineEdit(self)
        self.title_input.setPlaceholderText("Например: Домашний адрес или Wi-Fi")
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("Категория (Тег):"))
        self.tag_input = QComboBox(self)
        self.tag_input.addItems(["Личное", "Финансы", "Сеть", "Код", "Переписка", "Другое"])
        layout.addWidget(self.tag_input)

        layout.addWidget(QLabel("Содержимое сниппета:"))
        self.content_input = QTextEdit(self)
        self.content_input.setPlaceholderText("Введите текст, который будет копироваться в буфер...")
        layout.addWidget(self.content_input)

        btn_box = QHBoxLayout()
        self.save_btn = QPushButton("💾 Сохранить сниппет", self)
        self.save_btn.clicked.connect(self.save_snippet)
        btn_box.addWidget(self.save_btn)
        layout.addLayout(btn_box)

    def save_snippet(self):
        title = self.title_input.text().strip()
        content = self.content_input.toPlainText().strip()
        tag = self.tag_input.currentText()

        if not title or not content:
            QMessageBox.warning(self, "Внимание", "Заполните название и текст сниппета")
            return

        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO snippets (title, content, tag) VALUES (?, ?, ?)", (title, content, tag))
        conn.commit()
        conn.close()
        self.accept()


class ClipboardManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clipboard & Snippet Manager Pro • VoyagerTeam Lab")
        self.resize(800, 600)
        self.setMinimumSize(700, 500)
        self.last_clipboard_text = ""
        self.is_monitoring = True

        self.apply_styles()
        self.init_ui()

        # Подключаем слушатель буфера обмена
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)

        # Загружаем данные
        self.load_history()
        self.load_snippets()

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0D0D0F;
            }
            QWidget {
                font-family: 'Segoe UI', 'Inter', sans-serif;
                color: #F8FAFC;
            }
            QLineEdit {
                background-color: #141418;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                padding: 12px 16px;
                color: #F8FAFC;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #F59E0B;
                background-color: #181820;
            }
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #141418;
                color: #94A3B8;
                padding: 10px 22px;
                margin-right: 6px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                font-weight: 600;
                font-size: 13px;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background: #F59E0B;
                color: #0D0D0F;
                font-weight: 700;
            }
            QListWidget {
                background-color: #111115;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 16px;
                padding: 8px;
                outline: none;
            }
            QListWidget::item {
                background-color: #16161C;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 12px;
                margin-bottom: 8px;
                padding: 12px;
                color: #F8FAFC;
                font-size: 13px;
            }
            QListWidget::item:hover {
                background-color: #1D1D26;
                border: 1px solid rgba(245, 158, 11, 0.5);
            }
            QListWidget::item:selected {
                background-color: #242432;
                border: 1px solid #F59E0B;
                color: #FCD34D;
            }
            QPushButton {
                background-color: #F59E0B;
                color: #0D0D0F;
                border-radius: 10px;
                padding: 9px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #D97706;
            }
        """)

    def init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header bar
        header_layout = QHBoxLayout()
        title_label = QLabel("⚡ Clipboard & Snippet Pro", self)
        title_label.setStyleSheet("font-size: 18px; font-weight: 800; color: #FFFFFF;")
        header_layout.addWidget(title_label)

        sub_label = QLabel("Obsidian & Electric Amber", self)
        sub_label.setStyleSheet("color: #F59E0B; font-size: 11px; font-weight: 700; background: rgba(245, 158, 11, 0.15); padding: 3px 8px; border-radius: 6px;")
        header_layout.addWidget(sub_label)

        header_layout.addStretch()

        self.status_label = QLabel("● Мониторинг буфера активен", self)
        self.status_label.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 700; background: rgba(16, 185, 129, 0.1); padding: 4px 10px; border-radius: 8px;")
        header_layout.addWidget(self.status_label)

        layout.addLayout(header_layout)

        # Search bar
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("🔍 Поиск по сниппетам и истории буфера обмена...")
        self.search_input.textChanged.connect(self.filter_current_tab)
        layout.addWidget(self.search_input)

        # Tabs
        self.tabs = QTabWidget(self)

        # Tab 1: Clipboard History
        history_widget = QWidget()
        hist_layout = QVBoxLayout(history_widget)
        hist_layout.setContentsMargins(0, 10, 0, 0)
        self.history_list = QListWidget(self)
        self.history_list.itemDoubleClicked.connect(self.copy_history_item)
        hist_layout.addWidget(self.history_list)

        hist_ctrl_layout = QHBoxLayout()
        copy_hint = QLabel("💡 Двойной клик копирует запись обратно в буфер", self)
        copy_hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        hist_ctrl_layout.addWidget(copy_hint)
        hist_ctrl_layout.addStretch()

        clear_hist_btn = QPushButton("🗑 Очистить историю", self)
        clear_hist_btn.setStyleSheet("background-color: #262630; color: #E2E8F0; border: 1px solid rgba(255, 255, 255, 0.08);")
        clear_hist_btn.clicked.connect(self.clear_history)
        hist_ctrl_layout.addWidget(clear_hist_btn)
        hist_layout.addLayout(hist_ctrl_layout)

        self.tabs.addTab(history_widget, "🕒 История буфера")

        # Tab 2: Snippets
        snippets_widget = QWidget()
        snip_layout = QVBoxLayout(snippets_widget)
        snip_layout.setContentsMargins(0, 10, 0, 0)
        self.snippets_list = QListWidget(self)
        self.snippets_list.itemDoubleClicked.connect(self.copy_snippet_item)
        snip_layout.addWidget(self.snippets_list)

        snip_ctrl_layout = QHBoxLayout()
        add_snip_btn = QPushButton("+ Добавить новый сниппет", self)
        add_snip_btn.clicked.connect(self.open_add_snippet)
        snip_ctrl_layout.addWidget(add_snip_btn)
        snip_ctrl_layout.addStretch()
        snip_layout.addLayout(snip_ctrl_layout)

        self.tabs.addTab(snippets_widget, "⭐ Сниппеты")
        layout.addWidget(self.tabs)

        # Footer toast
        self.toast_label = QLabel("", self)
        self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.setStyleSheet("color: #F59E0B; font-weight: 700; font-size: 12px; padding: 4px;")
        layout.addWidget(self.toast_label)

    def on_clipboard_changed(self):
        text = self.clipboard.text().strip()
        if not text or text == self.last_clipboard_text:
            return

        self.last_clipboard_text = text
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO clipboard_history (content)
            VALUES (?)
            ON CONFLICT(content) DO UPDATE SET created_at = CURRENT_TIMESTAMP
        """, (text,))
        conn.commit()
        conn.close()

        self.load_history()
        self.show_toast(f"📥 Сохранено в историю: {text[:30]}...")

    def load_history(self, filter_text=""):
        self.history_list.clear()
        conn = get_db()
        cur = conn.cursor()
        if filter_text:
            cur.execute("SELECT id, content, created_at FROM clipboard_history WHERE content LIKE ? ORDER BY created_at DESC LIMIT 50", (f"%{filter_text}%",))
        else:
            cur.execute("SELECT id, content, created_at FROM clipboard_history ORDER BY created_at DESC LIMIT 50")
        rows = cur.fetchall()
        conn.close()

        for r in rows:
            preview = r["content"].replace("\n", " ")
            if len(preview) > 90:
                preview = preview[:90] + "..."
            item = QListWidgetItem(f"[{r['created_at'][11:16]}]  {preview}")
            item.setData(Qt.ItemDataRole.UserRole, r["content"])
            self.history_list.addItem(item)

    def load_snippets(self, filter_text=""):
        self.snippets_list.clear()
        conn = get_db()
        cur = conn.cursor()
        if filter_text:
            cur.execute("SELECT id, title, content, tag FROM snippets WHERE title LIKE ? OR content LIKE ? ORDER BY id DESC", (f"%{filter_text}%", f"%{filter_text}%"))
        else:
            cur.execute("SELECT id, title, content, tag FROM snippets ORDER BY id DESC")
        rows = cur.fetchall()
        conn.close()

        for r in rows:
            item = QListWidgetItem(f"[{r['tag']}]  {r['title']}\n→ {r['content'][:80]}")
            item.setData(Qt.ItemDataRole.UserRole, r["content"])
            self.snippets_list.addItem(item)

    def filter_current_tab(self, text):
        query = text.strip()
        self.load_history(query)
        self.load_snippets(query)

    def copy_history_item(self, item):
        content = item.data(Qt.ItemDataRole.UserRole)
        self.clipboard.setText(content)
        self.show_toast("✅ Скопировано в буфер обмена!")

    def copy_snippet_item(self, item):
        content = item.data(Qt.ItemDataRole.UserRole)
        self.clipboard.setText(content)
        self.show_toast("✅ Сниппет скопирован в буфер!")

    def open_add_snippet(self):
        dialog = AddSnippetDialog(self)
        if dialog.exec():
            self.load_snippets()
            self.show_toast("✨ Новый сниппет успешно сохранён!")

    def clear_history(self):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM clipboard_history")
        conn.commit()
        conn.close()
        self.load_history()
        self.show_toast("История буфера очищена")

    def show_toast(self, message):
        self.toast_label.setText(message)
        QTimer.singleShot(2500, lambda: self.toast_label.setText(""))


def main():
    app = QApplication(sys.argv)
    window = ClipboardManagerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
