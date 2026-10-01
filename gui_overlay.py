from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPoint, QUrl, QStringListModel, QMimeData
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QFrame, QScrollArea, QApplication, QMessageBox,
    QComboBox, QCompleter, QDialog, QFormLayout, QMenu, QAction
)
from PySide6.QtGui import QFont, QColor, QPalette, QClipboard, QPixmap, QPainter, QCursor
import os
import re
import time
import json
import urllib.request
import threading
from datetime import datetime
from skills import SkillManager


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("⚙ Settings")
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.theme_combo = QComboBox(self)
        self.theme_combo.addItems(["white", "black", "system"])
        self.theme_combo.setCurrentText(self.config.get("theme", "system"))

        self.provider_combo = QComboBox(self)
        self.provider_combo.addItems(["ollama", "lm_studio", "openai"])
        self.provider_combo.setCurrentText(self.config.get("ai_provider", "ollama"))

        self.endpoint_input = QLineEdit(self)
        self.model_combo = QComboBox(self)
        self.default_model_combo = QComboBox(self)
        self.fallback_model_combo = QComboBox(self)

        form.addRow("Theme", self.theme_combo)
        form.addRow("Provider", self.provider_combo)
        form.addRow("Endpoint", self.endpoint_input)
        form.addRow("Model", self.model_combo)
        form.addRow("Default Model", self.default_model_combo)
        form.addRow("Fallback Model", self.fallback_model_combo)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel", self)
        save_btn = QPushButton("Save", self)
        save_btn.setStyleSheet("background-color: #4f46e5; color: white; border-radius: 6px; padding: 6px 10px;")
        cancel_btn.clicked.connect(self.reject)
        save_btn.clicked.connect(self.save)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        self.provider_combo.currentIndexChanged.connect(self._refresh_provider_state)
        self._refresh_provider_state()
        self._load_saved_values()

    def _load_saved_values(self):
        provider = self.config.get("ai_provider", "ollama")
        providers = self.config.get("providers", {})
        provider_cfg = providers.get(provider, {})
        self.endpoint_input.setText(provider_cfg.get("endpoint", ""))
        self._populate_model_lists(provider_cfg.get("models", []))
        self.default_model_combo.setCurrentText(provider_cfg.get("default_model", ""))
        self.fallback_model_combo.setCurrentText(provider_cfg.get("fallback_model", ""))
        self.model_combo.setCurrentText(self.config.get("default_model", ""))

    def _refresh_provider_state(self):
        provider = self.provider_combo.currentText().lower()
        endpoint = "http://localhost:11434"
        if provider == "lm_studio":
            endpoint = "http://localhost:1234/v1"
        elif provider == "openai":
            endpoint = "https://api.openai.com/v1"
        self.endpoint_input.setText(endpoint)
        self.model_combo.clear(); self.default_model_combo.clear(); self.fallback_model_combo.clear()
        self._load_provider_models(provider, endpoint)

    def _populate_model_lists(self, models):
        self.model_combo.clear(); self.default_model_combo.clear(); self.fallback_model_combo.clear()
        for name in models:
            self.model_combo.addItem(name)
            self.default_model_combo.addItem(name)
            self.fallback_model_combo.addItem(name)

    def _load_provider_models(self, provider, endpoint):
        models = []
        try:
            if provider == "ollama":
                req = urllib.request.Request(f"{endpoint}/api/tags", method="GET")
                with urllib.request.urlopen(req, timeout=4) as r:
                    data = json.loads(r.read().decode("utf-8"))
                if isinstance(data, dict):
                    data = data.get("models", [])
                models = [m.get("name") for m in data if isinstance(m, dict) and m.get("name")]
            elif provider == "lm_studio":
                req = urllib.request.Request(f"{endpoint}/models", method="GET")
                with urllib.request.urlopen(req, timeout=4) as r:
                    data = json.loads(r.read().decode("utf-8"))
                models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
            elif provider == "openai":
                api_key = self.config.get("providers", {}).get("openai", {}).get("api_key", "")
                req = urllib.request.Request(
                    f"{endpoint}/models",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    method="GET",
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read().decode("utf-8"))
                models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict) and m.get("id")]
        except Exception:
            models = []
        self._populate_model_lists(models)

    def save(self):
        provider = self.provider_combo.currentText().lower()
        endpoint = self.endpoint_input.text().strip()
        model = self.model_combo.currentText().strip()
        default_model = self.default_model_combo.currentText().strip()
        fallback_model = self.fallback_model_combo.currentText().strip()

        self.config["theme"] = self.theme_combo.currentText()
        self.config["ai_provider"] = provider
        self.config["default_model"] = model or default_model or self.config.get("default_model", "")
        self.config["fallback_model"] = fallback_model or self.config.get("fallback_model", "")
        self.config.setdefault("providers", {})
        self.config["providers"][provider] = {
            "enabled": True,
            "endpoint": endpoint,
            "models": [self.model_combo.itemText(i) for i in range(self.model_combo.count())],
            "default_model": default_model,
            "fallback_model": fallback_model,
        }
        try:
            with open(os.path.join(os.path.dirname(__file__), "config.json"), "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        self.accept()


class QuickHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💡 Quick Help")
        self.resize(420, 300)
        self.setStyleSheet("QDialog { background: #1e1e24; color: #e4e4e7; }")

        layout = QVBoxLayout(self)
        text = (
            "Commands\n"
            "- Rewrite: shortens and polishes text\n"
            "- Long: full rewrite with more complete wording\n"
            "- Improve: refine wording and clarity\n"
            "- Summarize: key points only\n"
            "- Translate: convert to target language\n"
            "- Quick Help: show this dialog\n\n"
            "Tips\n"
            "- Leave the input blank to use clipboard text if available\n"
            "- Use the Stop button to cancel the current generation\n"
            "- Settings lets you switch theme and AI providers\n"
            "- Model selection is available in the top bar"
        )
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 11px; line-height: 1.5; color: #e4e4e7;")
        layout.addWidget(label)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class HistoryLineEdit(QLineEdit):
    def __init__(self, history_manager=None, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.history_items = []
        self.history_index = -1
        self.draft_text = ""

    def set_history_manager(self, history_manager):
        self.history_manager = history_manager

    def update_history_cache(self):
        if self.history_manager and hasattr(self.history_manager, "history"):
            raw_prompts = [h.get("prompt", "") for h in self.history_manager.history if h.get("prompt")]
            seen = set(); self.history_items = []
            for p in raw_prompts:
                p_clean = p.strip()
                if p_clean and p_clean not in seen:
                    seen.add(p_clean)
                    self.history_items.append(p_clean)
        else:
            self.history_items = []
        self.history_index = -1

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if self.history_index == -1:
                self.update_history_cache(); self.draft_text = self.text()
            if self.history_items:
                if self.history_index < len(self.history_items) - 1:
                    self.history_index += 1; self.setText(self.history_items[self.history_index])
            return
        elif event.key() == Qt.Key_Down:
            if self.history_index >= 0:
                self.history_index -= 1
                if self.history_index == -1:
                    self.setText(self.draft_text)
                else:
                    self.setText(self.history_items[self.history_index])
            return
        super().keyPressEvent(event)


class HistoryManager:
    def __init__(self, filepath=None, max_items=100):
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "history.json")
        self.filepath = filepath
        self.max_items = max_items
        self.history = self.load_history()

    def load_history(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
        return []

    def save_history(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.history[:self.max_items], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def add_started_entry(self, action: str, prompt: str, model: str = ""):
        if not prompt or not prompt.strip():
            return
        entry = {
            "id": f"{int(time.time()*1000)}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action or "ask",
            "prompt": prompt.strip(),
            "response": "",
            "model": model or "",
            "status": "started"
        }
        self.history.insert(0, entry)
        if len(self.history) > self.max_items:
            self.history = self.history[:self.max_items]
        self.save_history()

    def add_entry(self, action: str, prompt: str, response: str, model: str = "", status: str = "success"):
        if not prompt.strip() or not response.strip() or status != "success":
            return
        entry = {
            "id": f"{int(time.time()*1000)}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action or "ask",
            "prompt": prompt.strip(),
            "response": response.strip(),
            "model": model or "",
            "status": status
        }
        self.history.insert(0, entry)
        if len(self.history) > self.max_items:
            self.history = self.history[:self.max_items]
        self.save_history()

    def clear_history(self):
        self.history = []
        self.save_history()

    def search(self, query: str):
        if not query or not query.strip():
            return self.history
        q = query.strip().lower()
        return [
            h for h in self.history
            if q in h.get("prompt", "").lower() or q in h.get("response", "").lower() or q in h.get("action", "").lower()
        ]


class ThinkFilter:
    def __init__(self, on_thinking_state_change=None):
        self.buffer = ""
        self.in_think = False
        self.on_thinking_state_change = on_thinking_state_change

    def reset(self):
        self.buffer = ""; self.in_think = False

    def process_chunk(self, chunk: str) -> str:
        self.buffer += chunk
        output = ""
        while self.buffer:
            if not self.in_think:
                match_think = re.search(r'<(think|thought)>', self.buffer, re.IGNORECASE)
                if match_think:
                    start, end = match_think.span(); output += self.buffer[:start]; self.buffer = self.buffer[end:]; self.in_think = True
                    if self.on_thinking_state_change:
                        self.on_thinking_state_change(True)
                else:
                    partial_match = re.search(r'<[a-zA-Z]*$', self.buffer)
                    if partial_match:
                        prefix = partial_match.group(0)
                        if '<think>'.startswith(prefix.lower()) or '<thought>'.startswith(prefix.lower()):
                            safe_len = partial_match.start(); output += self.buffer[:safe_len]; self.buffer = self.buffer[safe_len:]; break
                    output += self.buffer; self.buffer = ""
            else:
                match_end = re.search(r'</(think|thought)>', self.buffer, re.IGNORECASE)
                if match_end:
                    start, end = match_end.span(); self.buffer = self.buffer[end:]; self.in_think = False
                    if self.on_thinking_state_change:
                        self.on_thinking_state_change(False)
                else:
                    partial_match = re.search(r'</[a-zA-Z]*$', self.buffer)
                    if partial_match:
                        prefix = partial_match.group(0)
                        if '</think>'.startswith(prefix.lower()) or '</thought>'.startswith(prefix.lower()):
                            self.buffer = self.buffer[partial_match.start():]; break
                    self.buffer = ""; break
        return output

    def flush(self) -> str:
        if not self.in_think and self.buffer:
            res = self.buffer; self.buffer = ""; return res
        self.buffer = ""; return ""


def clean_think_text(text: str) -> str:
    if not text: return text
    cleaned = re.sub(r'<(think|thought)>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<(think|thought)>.*', '', cleaned, flags=re.DOTALL | re.IGNORECASE).strip()
    intro_patterns = [
        r'^(?:sure|okay|ok|certainly|of course)[!.,]?\s*',
        r'^(?:here is|here\'s|below is|as requested|i will|let me|i have|i\'ve)[^:\n]*:\s*',
        r'^(?:here is|here\'s) (?:the |your )?(?:revised|enhanced|translated|summarized|explained|summary|result|text|output)[^:\n]*:\s*',
    ]
    for _ in range(3):
        prev = cleaned
        for pattern in intro_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE).strip()
        if cleaned == prev: break
    outro_patterns = [r'\n*(?:hope this helps|let me know if you need|is there anything else|feel free to ask)[^\n]*$']
    for pattern in outro_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned


class WorkerThread(QThread):
    chunk_received = Signal(str)
    finished = Signal()

    def __init__(self, generator_func):
        super().__init__()
        self.generator_func = generator_func
        self.cancelled = threading.Event()

    def cancel(self):
        self.cancelled.set()

    def run(self):
        try:
            for chunk in self.generator_func():
                if self.cancelled.is_set():
                    break
                self.chunk_received.emit(chunk)
        except Exception as e:
            self.chunk_received.emit(f"\n[Error: {str(e)}]")
        finally:
            self.finished.emit()


class NearbySuggestionPopup(QWidget):
    expand_requested = Signal(str, str)

    def __init__(self, ollama_service, history_manager=None, parent=None):
        super().__init__(parent)
        self.ollama = ollama_service
        self.history_manager = history_manager or HistoryManager()
        self.selected_text = ""
        self.worker = None
        self._last_action = "nearby"
        self._last_prompt = ""
        self.think_filter = ThinkFilter(on_thinking_state_change=self._on_thinking_state_changed)
        self.suggest_worker = None
        self.suggest_filter = ThinkFilter()
        self._source_hwnd = None
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        self.card = QFrame(self)
        self.card.setStyleSheet("QFrame { background-color: #1a1a20; border-radius: 10px; border: 1px solid #4338ca; }")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(6)

        self.suggest_frame = QFrame(self.card)
        self.suggest_frame.setStyleSheet("QFrame { background-color: #1a1a2e; border: 1px solid #4338ca; border-radius: 6px; }")
        self.suggest_frame.hide()
        sg_layout = QHBoxLayout(self.suggest_frame)
        sg_layout.setContentsMargins(6, 5, 6, 5)
        sg_layout.setSpacing(6)
        self.suggest_label = QLabel("", self.suggest_frame)
        self.suggest_label.setWordWrap(True); self.suggest_label.setFixedWidth(320)
        self.suggest_label.setStyleSheet("color: #a5b4fc; font-size: 11px; border: none;")
        self.suggest_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.suggest_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        sg_layout.addWidget(self.suggest_label, 1)

        self.suggest_apply_btn = QPushButton("✔ Apply", self.suggest_frame); self.suggest_apply_btn.setFixedHeight(24); self.suggest_apply_btn.setEnabled(False)
        self.suggest_apply_btn.setStyleSheet("QPushButton { background-color: #4f46e5; color: #ffffff; border-radius: 5px; padding: 2px 9px; font-size: 11px; font-weight: bold; } QPushButton:hover { background-color: #6366f1; } QPushButton:disabled { background-color: #3f3f56; color: #71717a; }")
        self.suggest_apply_btn.clicked.connect(self._apply_selection_suggestion)
        sg_layout.addWidget(self.suggest_apply_btn)

        self.suggest_copy_btn = QPushButton("📋", self.suggest_frame); self.suggest_copy_btn.setFixedSize(28, 24); self.suggest_copy_btn.setEnabled(False)
        self.suggest_copy_btn.setStyleSheet("QPushButton { background-color: #272730; color: #e4e4e7; border-radius: 5px; font-size: 11px; } QPushButton:hover { background-color: #3f3f4e; } QPushButton:disabled { color: #52525b; }")
        self.suggest_copy_btn.clicked.connect(self._copy_selection_suggestion)
        sg_layout.addWidget(self.suggest_copy_btn)

        self.suggest_dismiss_btn = QPushButton("✕", self.suggest_frame); self.suggest_dismiss_btn.setFixedSize(24, 24)
        self.suggest_dismiss_btn.setStyleSheet("QPushButton { color: #a1a1aa; background: none; border: none; font-size: 11px; font-weight: bold; } QPushButton:hover { color: #ef4444; }")
        self.suggest_dismiss_btn.clicked.connect(self.hide)
        sg_layout.addWidget(self.suggest_dismiss_btn)
        card_layout.addWidget(self.suggest_frame)

        header_row = QHBoxLayout(); header_row.setSpacing(6)
        self.model_combo = QComboBox(self.card); self.model_combo.setToolTip("Select AI Model")
        self.model_combo.setStyleSheet("QComboBox { background-color: #2e2a52; color: #a5b4fc; border: 1px solid #4338ca; border-radius: 5px; padding: 2px 6px; font-size: 10px; font-weight: bold; max-width: 150px; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1a1a20; color: #e4e4e7; selection-background-color: #3f3f56; }")
        self.refresh_model_dropdown(); self.model_combo.currentTextChanged.connect(self._on_model_changed)

        self.preview_label = QLabel("Selected text...", self.card)
        self.preview_label.setStyleSheet("color: #e4e4e7; font-size: 11px; font-weight: 500;")
        self.preview_label.setWordWrap(False); self.preview_label.setMaximumWidth(320)

        close_btn = QPushButton("✕", self.card); close_btn.setFixedSize(18, 18)
        close_btn.setStyleSheet("QPushButton { color: #a1a1aa; border: none; font-size: 11px; background: none; font-weight: bold; } QPushButton:hover { color: #ef4444; }")
        close_btn.clicked.connect(self.hide)

        header_row.addWidget(self.model_combo); header_row.addWidget(self.preview_label, 1); header_row.addWidget(close_btn)
        self._header_widgets = [self.model_combo, self.preview_label, close_btn]
        card_layout.addLayout(header_row)

        self.chips_layout = QHBoxLayout(); self.chips_layout.setSpacing(4)
        action_chips = [
            ("✍️ Rewrite", "rewrite_short"),
            ("✨ Improve", "improve"),
            ("🌐 Translate", "translate"),
            ("📝 Summary", "summarize"),
            ("📖 Explain", "explain"),
            ("💬 Ask AI", "ask"),
            ("📋 Copy", "copy"),
            ("📋 Paste", "paste"),
            ("📝 Long", "rewrite_long"),
            ("💡 Help", "quick_help"),
        ]
        self.chip_buttons = []
        for label, act in action_chips:
            btn = QPushButton(label, self.card); btn.setFixedHeight(24)
            btn.setStyleSheet("QPushButton { background-color: #27273a; color: #e4e4e7; border: 1px solid #3f3f56; border-radius: 5px; padding: 2px 7px; font-size: 10px; font-weight: 600; } QPushButton:hover { background-color: #4338ca; color: #ffffff; border-color: #6366f1; }")
            btn.clicked.connect(lambda checked, a=act: self.on_chip_clicked(a))
            self.chips_layout.addWidget(btn); self.chip_buttons.append(btn)
        card_layout.addLayout(self.chips_layout)

        self.ask_container = QWidget(self.card); ask_layout = QHBoxLayout(self.ask_container); ask_layout.setContentsMargins(0, 2, 0, 2); ask_layout.setSpacing(4)
        self.ask_input = HistoryLineEdit(self.history_manager, self.ask_container); self.ask_input.setPlaceholderText("Ask AI about this text... (Up/Down for history)")
        self.ask_input.setStyleSheet("QLineEdit { background-color: #121216; color: #f4f4f5; border: 1px solid #3f3f56; border-radius: 5px; padding: 4px 8px; font-size: 11px; } QLineEdit:focus { border: 1px solid #6366f1; }")
        self.ask_input.returnPressed.connect(self.submit_ask)
        send_btn = QPushButton("Send", self.ask_container); send_btn.setFixedHeight(24)
        send_btn.setStyleSheet("QPushButton { background-color: #4f46e5; color: #ffffff; border-radius: 5px; padding: 2px 8px; font-size: 10px; font-weight: bold; } QPushButton:hover { background-color: #6366f1; }")
        send_btn.clicked.connect(self.submit_ask)
        ask_layout.addWidget(self.ask_input); ask_layout.addWidget(send_btn); self.ask_container.hide(); card_layout.addWidget(self.ask_container)

        self.output_view = QTextEdit(self.card); self.output_view.setReadOnly(True); self.output_view.setFixedHeight(110)
        self.output_view.setStyleSheet("QTextEdit { background-color: #121216; color: #e4e4e7; border: 1px solid #272730; border-radius: 5px; padding: 6px; font-size: 11px; line-height: 1.4; }")
        self.output_view.hide(); card_layout.addWidget(self.output_view)

        self.status_label = QLabel("", self.card); self.status_label.setStyleSheet("color: #a1a1aa; font-size: 10px;"); self.status_label.hide(); card_layout.addWidget(self.status_label)
        main_layout.addWidget(self.card)

    def refresh_model_dropdown(self):
        self.model_combo.blockSignals(True); self.model_combo.clear(); models = self.ollama.get_available_models(); active_model = self.ollama.get_model_name()
        if not models: models = [active_model]
        for m in models: self.model_combo.addItem(f"⚡ {m}")
        for i in range(self.model_combo.count()):
            item_model = self.model_combo.itemText(i).replace("⚡ ", "").strip()
            if item_model == active_model: self.model_combo.setCurrentIndex(i); break
        self.model_combo.blockSignals(False)

    def _on_model_changed(self, text: str):
        if text:
            model_name = text.replace("⚡ ", "").strip(); self.ollama.set_model(model_name)

    def _set_view_visible(self, suggestion: bool):
        self.suggest_frame.setVisible(suggestion)
        for wdg in self._header_widgets: wdg.setVisible(not suggestion)
        for btn in self.chip_buttons: btn.setVisible(not suggestion)
        if not suggestion: self.ask_container.hide(); self.output_view.hide(); self.status_label.hide(); self.output_view.clear()
        if bool(self.windowFlags() & Qt.WindowDoesNotAcceptFocus) != suggestion:
            self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, suggestion)
        self.setAttribute(Qt.WA_ShowWithoutActivating, suggestion)

    def _enter_suggestion_mode(self):
        self._set_view_visible(True); self.suggest_label.setText("✍️ Checking…"); self.suggest_apply_btn.setEnabled(False); self.suggest_copy_btn.setEnabled(False)

    def _enter_full_view(self):
        self.refresh_model_dropdown(); self._set_view_visible(False)

    def _current_suggestion(self) -> str:
        sug = self.suggest_label.text().strip(); sug = re.sub(r"^(?:\s*[✨⭐]\s*)+", "", sug).strip()
        if not sug or sug == "✍️ Checking…": return ""
        return sug

    def _copy_selection_suggestion(self):
        sug = self._current_suggestion();
        if sug and self.suggest_copy_btn.isEnabled():
            QApplication.clipboard().setText(sug); self.suggest_copy_btn.setText("✓"); QTimer.singleShot(1200, lambda: self.suggest_copy_btn.setText("📋"))

    def _apply_selection_suggestion(self):
        sug = self._current_suggestion()
        if not sug or not self.suggest_apply_btn.isEnabled(): return
        src_hwnd = self._source_hwnd; snapshot = self._snapshot_clipboard(); self.hide(); QTimer.singleShot(100, lambda: self._focus_window(src_hwnd)); QTimer.singleShot(350, lambda: self._attempt_paste(src_hwnd, sug, snapshot, 0))

    def _snapshot_clipboard(self):
        try:
            mime = QApplication.clipboard().mimeData();
            if mime.hasImage():
                snap = QMimeData(); snap.setImageData(mime.imageData()); return snap
            text = mime.text(); return text or None
        except Exception: return None

    def _restore_clipboard(self, snapshot):
        try:
            if isinstance(snapshot, QMimeData): QApplication.clipboard().setMimeData(snapshot)
            elif snapshot: QApplication.clipboard().setText(snapshot)
        except Exception: pass

    def _focus_window(self, hwnd):
        if not hwnd: return
        try:
            import ctypes; u32 = ctypes.windll.user32
            if not u32.IsWindow(hwnd): return
            if u32.IsIconic(hwnd): u32.ShowWindow(hwnd, 9)
            u32.SetForegroundWindow(hwnd)
            if u32.GetForegroundWindow() != hwnd:
                u32.keybd_event(0x12, 0, 0, 0); u32.keybd_event(0x12, 0, 2, 0); u32.SetForegroundWindow(hwnd)
        except Exception: pass

    def _attempt_paste(self, src_hwnd, sug, snapshot, retry):
        try:
            if src_hwnd:
                import ctypes; fg_now = int(ctypes.windll.user32.GetForegroundWindow() or 0)
                if fg_now != src_hwnd:
                    if retry < 2:
                        self._focus_window(src_hwnd); QTimer.singleShot(300, lambda: self._attempt_paste(src_hwnd, sug, snapshot, retry + 1)); return
                    QApplication.clipboard().setText(sug); return
            QApplication.clipboard().setText(sug)
            try:
                import pyautogui; pyautogui.hotkey("ctrl", "v")
            except Exception: return
            if snapshot is not None: QTimer.singleShot(900, lambda: self._restore_clipboard(snapshot))
        except Exception: pass

    def on_chip_clicked(self, action: str):
        if action == "copy":
            if self.output_view.isVisible() and self.output_view.toPlainText().strip():
                QApplication.clipboard().setText(self.output_view.toPlainText().strip())
            else:
                QApplication.clipboard().setText(self.selected_text)
            self.status_label.setText("✓ Copied to clipboard"); self.status_label.show(); QTimer.singleShot(1500, self.hide); return
        if action == "paste":
            cb_text = QApplication.clipboard().text()
            if cb_text and cb_text.strip():
                self.selected_text = cb_text.strip(); truncated = self.selected_text.replace("\n", " ")
                if len(truncated) > 37: truncated = truncated[:37] + "..."
                self.preview_label.setText(f"📋 Pasted: \"{truncated}\"")
                self.ask_container.show(); self.ask_input.setFocus(); self.adjustSize()
            return
        if action == "ask":
            self.ask_container.show(); self.ask_input.setFocus(); self.adjustSize(); return
        if action == "quick_help":
            dlg = QuickHelpDialog(self); dlg.exec_(); return
        if action in ("rewrite_short", "rewrite_long", "improve", "feather"):
            self.run_ai_action(action); return
        self.run_ai_action(action)

    def submit_ask(self):
        prompt = self.ask_input.text().strip();
        if not prompt: return
        self._last_action = "ask"; self._last_prompt = f"{self.selected_text} -> {prompt}"
        combined_prompt = f"Context text:\n{self.selected_text}\n\nQuestion/Instruction: {prompt}"
        sys_prompt = "You are a helpful desktop assistant. Answer clearly and concisely. Do not output <think> tags."
        self._execute_streaming(combined_prompt, sys_prompt)

    def run_ai_action(self, action: str):
        self._last_action = action; self._last_prompt = self.selected_text
        sys_prompt, prompt = self.ollama.get_action_prompt(action, self.selected_text)
        self._execute_streaming(prompt, sys_prompt)

    def _execute_streaming(self, prompt: str, system_prompt: str):
        if self.worker and self.worker.isRunning():
            try: self.worker.terminate(); self.worker.wait(300)
            except Exception: pass
        self.output_view.clear(); self.output_view.show(); self.status_label.setText("💭 Generating..."); self.status_label.show(); self.think_filter.reset(); self.adjustSize()
        def _gen():
            yield from self.ollama.stream_generate(prompt, system_prompt=system_prompt)
        self.worker = WorkerThread(_gen); self.worker.chunk_received.connect(self._append_chunk); self.worker.finished.connect(self._on_finished); self.worker.start()

    def _append_chunk(self, chunk: str):
        filtered = self.think_filter.process_chunk(chunk)
        if filtered:
            self.output_view.insertPlainText(filtered); sb = self.output_view.verticalScrollBar(); sb.setValue(sb.maximum())

    def _on_finished(self):
        flushed = self.think_filter.flush();
        if flushed: self.output_view.insertPlainText(flushed)
        full = self.output_view.toPlainText(); cleaned = clean_think_text(full)
        if cleaned != full: self.output_view.setPlainText(cleaned)
        if cleaned and hasattr(self, "history_manager") and self.history_manager:
            act = getattr(self, "_last_action", "nearby"); p_val = getattr(self, "_last_prompt", self.selected_text)
            self.history_manager.add_entry(act, p_val, cleaned, model=self.ollama.get_model_name())
        self.status_label.setText("✓ Ready")

    def _on_thinking_state_changed(self, is_thinking: bool):
        if is_thinking: self.status_label.setText("💭 Thinking...")
        else: self.status_label.setText("⚡ Responding...")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape: self.hide()
        else: super().keyPressEvent(event)


class AIHelperWindow(QWidget):
    def __init__(self, ollama_service, audio_service, image_service, config, history_manager=None):
        super().__init__()
        self.ollama = ollama_service; self.audio = audio_service; self.image = image_service; self.config = config
        self.history_manager = history_manager or HistoryManager(); self.skill_manager = SkillManager(); self.selected_text = ""
        self._current_action_name = "prompt"; self._current_user_input = ""; self.think_filter = ThinkFilter(on_thinking_state_change=self._on_thinking_state_changed)
        self.init_ui(); self._detect_clipboard(); self._apply_theme(self.config.get("theme", "system"))

    def _apply_theme(self, theme_name: str):
        app = QApplication.instance();
        if not app: return
        if theme_name == "white":
            app.setStyleSheet("QWidget { background: #f5f5f5; color: #111827; } QLineEdit, QTextEdit, QComboBox, QPushButton, QFrame { background: #ffffff; color: #111827; border: 1px solid #d1d5db; } QLabel { color: #111827; }")
        elif theme_name == "black":
            app.setStyleSheet("QWidget { background: #0f172a; color: #e5e7eb; } QLineEdit, QTextEdit, QComboBox, QPushButton, QFrame { background: #111827; color: #e5e7eb; border: 1px solid #374151; } QLabel { color: #e5e7eb; }")
        else:
            app.setStyleSheet("")

    def init_ui(self):
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground); self.resize(640, 470)
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(8, 8, 8, 8)
        self.card = QFrame(self); self.card.setStyleSheet("QFrame { background-color: #1e1e24; border-radius: 12px; border: 1px solid #33333d; }")
        card_layout = QVBoxLayout(self.card); card_layout.setSpacing(6)

        top_bar = QHBoxLayout(); self.title_label = QLabel("⚡ Win AI Helper", self.card); self.title_label.setStyleSheet("color: #9d8ec1; font-weight: bold; font-size: 13px; border: none;")
        self.model_combo = QComboBox(self.card); self.model_combo.setToolTip("Select AI Model"); self.model_combo.setStyleSheet("QComboBox { background-color: #272730; color: #818cf8; border: 1px solid #3f3f4e; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1e1e24; color: #e4e4e7; selection-background-color: #3f3f4e; }")
        self.refresh_model_dropdown(); self.model_combo.currentTextChanged.connect(self._on_model_changed)

        self.skill_combo = QComboBox(self.card); self.skill_combo.setToolTip("Select Custom Skill / Output Directive"); self.skill_combo.setStyleSheet("QComboBox { background-color: #272730; color: #34d399; border: 1px solid #3f3f4e; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: bold; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1e1e24; color: #e4e4e7; selection-background-color: #3f3f4e; }")
        self.refresh_skill_dropdown(); self.skill_combo.activated.connect(self._on_skill_selected)

        self.settings_btn = QPushButton("⚙ Settings", self.card); self.settings_btn.setFixedHeight(22); self.settings_btn.setStyleSheet("QPushButton { background-color: #272730; color: #fbbf24; border: 1px solid #3f3f4e; border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold; } QPushButton:hover { background-color: #3f3f4e; border-color: #fbbf24; }")
        self.settings_btn.clicked.connect(self.open_settings)

        self.help_btn = QPushButton("💡 Help", self.card); self.help_btn.setFixedHeight(22)
        self.help_btn.setStyleSheet("QPushButton { background-color: #272730; color: #7dd3fc; border: 1px solid #3f3f4e; border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold; } QPushButton:hover { background-color: #3f3f4e; border-color: #7dd3fc; }")
        self.help_btn.clicked.connect(self.show_quick_help)

        hist_btn = QPushButton("📜 History", self.card); hist_btn.setFixedHeight(22); hist_btn.setStyleSheet("QPushButton { background-color: #272730; color: #fbbf24; border: 1px solid #3f3f4e; border-radius: 6px; padding: 2px 8px; font-size: 10px; font-weight: bold; } QPushButton:hover { background-color: #3f3f4e; border-color: #fbbf24; }")
        hist_btn.clicked.connect(self.show_history_dialog)

        close_btn = QPushButton("✕", self.card); close_btn.setFixedSize(24, 24); close_btn.setStyleSheet("QPushButton { color: #a1a1aa; border: none; font-size: 13px; background:none; } QPushButton:hover { color: #ef4444; }")
        close_btn.clicked.connect(self.hide)

        top_bar.addWidget(self.title_label); top_bar.addStretch(); top_bar.addWidget(self.model_combo); top_bar.addWidget(self.skill_combo); top_bar.addWidget(self.settings_btn); top_bar.addWidget(self.help_btn); top_bar.addWidget(hist_btn); top_bar.addWidget(close_btn)
        card_layout.addLayout(top_bar)

        status_bar = QHBoxLayout(); self.status_label = QLabel("Ready", self.card); self.status_label.setStyleSheet("color: #a1a1aa; font-size: 10px;")
        top_right_status = QLabel("", self.card); top_right_status.setFixedHeight(20)
        status_bar.addWidget(self.status_label); status_bar.addStretch(); status_bar.addWidget(top_right_status); card_layout.addLayout(status_bar)

        ctx_frame = QFrame(self.card); ctx_frame.setStyleSheet("QFrame { background-color: #272730; border-radius: 6px; padding: 8px; }"); ctx_layout = QVBoxLayout(ctx_frame)
        self.ctx_label = QLabel("", ctx_frame); self.ctx_label.setStyleSheet("color: #a1a1aa; font-size: 11px;"); self.ctx_label.setWordWrap(True); ctx_layout.addWidget(self.ctx_label); card_layout.addWidget(ctx_frame)

        self.lang_combo = QComboBox(self.card); self.lang_combo.setToolTip("Target Language for Translation"); self.lang_combo.addItems(["Tamil", "English", "Tanglish", "Hindi", "Malayalam", "Telugu", "French", "German", "Spanish", "Japanese"])
        self.lang_combo.setStyleSheet("QComboBox { background-color: #272730; color: #60a5fa; border: 1px solid #3f3f4e; border-radius: 5px; padding: 2px 6px; font-size: 10px; font-weight: bold; } QComboBox::drop-down { border: none; } QComboBox QAbstractItemView { background-color: #1e1e24; color: #e4e4e7; selection-background-color: #3f3f4e; }")

        btn_layout = QHBoxLayout(); row_btns = [("✍️ Rewrite", "rewrite_short"), ("✨ Improve", "improve"), ("📋 Plan", "plan"), ("📖 Explain", "explain"), ("🌐 Translate", "translate"), ("📝 Summarize", "summarize"), ("📝 Long", "rewrite_long")]
        for label, act in row_btns:
            btn = QPushButton(label, self.card); btn.setFixedHeight(26); btn.setToolTip(label)
            btn.setStyleSheet("QPushButton { background-color: #272730; color: #e4e4e7; border: 1px solid #3f3f4e; border-radius: 5px; padding: 2px 8px; font-size: 11px; min-width: 0; } QPushButton:hover { background-color: #3f3f4e; border-color: #71717a; }")
            btn.clicked.connect(lambda checked, a=act: self.execute_action(a)); btn_layout.addWidget(btn)
        lbl_lang = QLabel("🌐 Lang:", self.card); lbl_lang.setStyleSheet("color: #60a5fa; font-size: 10px; font-weight: bold;"); btn_layout.addWidget(lbl_lang); btn_layout.addWidget(self.lang_combo); card_layout.addLayout(btn_layout)

        media_row = QHBoxLayout(); self.voice_btn = QPushButton("🎙 Voice", self.card); self.voice_btn.setCheckable(True); self.voice_btn.setStyleSheet("QPushButton { background-color: #272730; color: #e4e4e7; border-radius: 5px; padding: 2px 8px; }"); self.voice_btn.clicked.connect(self.toggle_voice_input)
        tts_btn = QPushButton("🔊 Read Aloud", self.card); tts_btn.setFixedHeight(26); tts_btn.setStyleSheet("QPushButton { background-color: #272730; color: #e4e4e7; border-radius: 5px; padding: 2px 8px; }"); tts_btn.clicked.connect(self.read_aloud)
        img_btn = QPushButton("🖼 Image", self.card); img_btn.setFixedHeight(26); img_btn.setStyleSheet("QPushButton { background-color: #272730; color: #e4e4e7; border-radius: 5px; padding: 2px 8px; }"); img_btn.clicked.connect(self.generate_image)
        media_row.addWidget(self.voice_btn); media_row.addStretch(); media_row.addWidget(tts_btn); media_row.addWidget(img_btn); card_layout.addLayout(media_row)

        self.output_view = QTextEdit(self.card); self.output_view.setReadOnly(True); self.output_view.setStyleSheet("QTextEdit { background-color: #141418; color: #e4e4e7; border: 1px solid #272730; border-radius: 6px; padding: 8px; font-size: 12px; line-height: 1.5; }")
        card_layout.addWidget(self.output_view)

        bottom_row = QHBoxLayout(); self.input_field = HistoryLineEdit(self.history_manager, self.card); self.input_field.setPlaceholderText("Type a request, or press Enter… (Up/Down for history)")
        self.input_field.setStyleSheet("QLineEdit { background-color: #141418; color: #f4f4f5; border: 1px solid #272730; border-radius: 6px; padding: 6px 10px; font-size: 12px; } QLineEdit:focus { border: 1px solid #6366f1; }")
        self.input_field.returnPressed.connect(self.on_submit_prompt)
        self.stop_btn = QPushButton("⏹ Stop", self.card); self.stop_btn.setFixedHeight(24); self.stop_btn.setStyleSheet("QPushButton { background-color: #272730; color: #fca5a5; border-radius: 5px; padding: 2px 8px; }"); self.stop_btn.clicked.connect(self.stop_generation)
        action_row = QHBoxLayout(); action_row.setSpacing(4)
        extra_actions = [("Details", "details"), ("📋 Copy", None), ("✂️ Clear", None)]
        for label, act in extra_actions:
            abtn = QPushButton(label, self.card); abtn.setFixedHeight(24); abtn.setStyleSheet("QPushButton { background-color: #272730; color: #e4e4e7; border-radius: 5px; padding: 2px 8px; }")
            if act is None: abtn.clicked.connect(self.on_manual_action)
            else: abtn.clicked.connect(lambda checked, a=act: self.execute_action(a))
            action_row.addWidget(abtn)
        bottom_row.addWidget(self.input_field); bottom_row.addWidget(self.stop_btn); bottom_row.addLayout(action_row); card_layout.addLayout(bottom_row)

        self.writing_suggest_frame = QFrame(self.card); self.writing_suggest_frame.setStyleSheet("QFrame { background-color: #1a1a2e; border: 1px solid #4338ca; border-radius: 6px; padding: 4px; }"); self.writing_suggest_frame.hide(); ws_layout = QHBoxLayout(self.writing_suggest_frame); ws_layout.setContentsMargins(6, 4, 6, 4); ws_layout.setSpacing(6)
        self.writing_suggest_label = QLabel("", self.writing_suggest_frame); self.writing_suggest_label.setWordWrap(True); self.writing_suggest_label.setStyleSheet("color: #a5b4fc; font-size: 11px; border: none;"); self.writing_suggest_label.setTextInteractionFlags(Qt.TextSelectableByMouse); ws_layout.addWidget(self.writing_suggest_label, 1)
        self.writing_apply_btn = QPushButton("✔ Apply", self.writing_suggest_frame); self.writing_apply_btn.setFixedHeight(22); self.writing_apply_btn.setStyleSheet("QPushButton { background-color: #4f46e5; color: #ffffff; border-radius: 5px; padding: 2px 8px; font-size: 10px; font-weight: bold; } QPushButton:hover { background-color: #6366f1; }"); self.writing_apply_btn.clicked.connect(self._apply_writing_suggestion); ws_layout.addWidget(self.writing_apply_btn)
        self.writing_copy_btn = QPushButton("📋", self.writing_suggest_frame); self.writing_copy_btn.setFixedSize(26, 22); self.writing_copy_btn.setToolTip("Copy suggestion"); self.writing_copy_btn.setStyleSheet("QPushButton { background-color: #272730; color: #e4e4e7; border-radius: 5px; font-size: 11px; } QPushButton:hover { background-color: #3f3f4e; }"); self.writing_copy_btn.clicked.connect(self._copy_writing_suggestion); ws_layout.addWidget(self.writing_copy_btn)
        self.writing_dismiss_btn = QPushButton("✕", self.writing_suggest_frame); self.writing_dismiss_btn.setFixedSize(22, 22); self.writing_dismiss_btn.setStyleSheet("QPushButton { color: #a1a1aa; background: none; border: none; font-size: 11px; } QPushButton:hover { color: #ef4444; }"); self.writing_dismiss_btn.clicked.connect(self.writing_suggest_frame.hide); ws_layout.addWidget(self.writing_dismiss_btn)
        card_layout.addWidget(self.writing_suggest_frame)

        self._writing_timer = QTimer(self); self._writing_timer.setSingleShot(True); self._writing_timer.setInterval(650); self._writing_timer.timeout.connect(self._request_writing_suggestion)
        self._writing_worker = None; self._writing_think_filter = ThinkFilter(); self._writing_last_text = ""
        main_layout.addWidget(self.card)

        self.completer_words = [
            "/rewrite - Rewrite and polish text", "/enhance - Enhance vocabulary and structure", "/plan - Create step-by-step plan", "/explain - Explain concept clearly",
            "/translate - Translate text", "/summarize - Key bullet points summary", "/json - Return valid JSON format only", "/tanglish - Answer strictly in Tanglish",
            "/code - Output raw code block only", "/direct - Direct answer without explanation", "Explain step by step", "Summarize into key bullet points",
            "Rewrite in professional tone", "Translate to natural English", "Fix grammar and spelling", "Format as structured markdown table", "Generate Python script for",
        ]
        self.completer_model = QStringListModel(self.completer_words, self); self.completer = QCompleter(self.completer_model, self); self.completer.setCaseSensitivity(Qt.CaseInsensitive); self.completer.setCompletionMode(QCompleter.PopupCompletion)

        def _on_input_text_changed(text: str):
            if text.startswith("/"):
                self.input_field.setCompleter(self.completer); self.writing_suggest_frame.hide(); self._writing_timer.stop()
            else:
                self.input_field.setCompleter(None); active_skill = getattr(self.skill_manager, "active_skill_name", "")
                is_exception = active_skill in ("💻 Code Only",) or any(k in active_skill.lower() for k in ["code", "json"])
                if is_exception or text.strip().startswith(("/plan", "/code", "/json")):
                    self.writing_suggest_frame.hide(); self._writing_timer.stop()
                else:
                    stripped = text.strip();
                    if len(stripped) >= 4 and not stripped.isdigit() and any(c.isalpha() for c in stripped):
                        self._writing_timer.start()
                    else:
                        self.writing_suggest_frame.hide(); self._writing_timer.stop()
        self.input_field.textChanged.connect(_on_input_text_changed)

    def open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self._apply_theme(self.config.get("theme", "system")); self.refresh_model_dropdown(); self.status_label.setText("Settings saved")

    def show_quick_help(self):
        QuickHelpDialog(self).exec_()

    def show_history_dialog(self):
        if not hasattr(self, "history_dialog") or self.history_dialog is None or not self.history_dialog.isVisible():
            self.history_dialog = HistoryDialog(self.history_manager, parent=self); self.history_dialog.show()
        else: self.history_dialog.raise_(); self.history_dialog.activateWindow()

    def refresh_model_dropdown(self):
        self.model_combo.blockSignals(True); self.model_combo.clear(); models = self.ollama.get_available_models(); active_model = self.ollama.get_model_name()
        if not models: models = [active_model]
        for m in models: self.model_combo.addItem(m)
        idx = self.model_combo.findText(active_model); 
        if idx >= 0: self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)

    def _on_model_changed(self, model_name: str):
        if model_name: self.ollama.set_model(model_name); self.status_label.setText(f"Model: {model_name}")

    def refresh_skill_dropdown(self):
        self.skill_combo.blockSignals(True); self.skill_combo.clear(); self.skill_combo.addItem("None (Default)")
        for name in self.skill_manager.get_skill_names(): self.skill_combo.addItem(name)
        self.skill_combo.addItem("➕ Add Custom Skill...")
        active = self.skill_manager.active_skill_name; idx = self.skill_combo.findText(active)
        if idx >= 0: self.skill_combo.setCurrentIndex(idx)
        else: self.skill_combo.setCurrentIndex(0)
        self.skill_combo.blockSignals(False)

    def _on_skill_selected(self, index: int):
        selected_text = self.skill_combo.itemText(index)
        if selected_text == "➕ Add Custom Skill...":
            dlg = AddSkillDialog(self)
            if dlg.exec():
                name, prompt = dlg.get_skill_data();
                if name and prompt:
                    self.skill_manager.add_skill(name, prompt); self.skill_manager.set_active_skill(name); self.refresh_skill_dropdown(); self.status_label.setText(f"Added skill: {name}")
                else: self.refresh_skill_dropdown()
            else: self.refresh_skill_dropdown()
        else:
            self.skill_manager.set_active_skill(selected_text); self.status_label.setText(f"Skill: {selected_text}")

    def _detect_clipboard(self):
        try:
            cb_text = QApplication.clipboard().text();
            if cb_text and cb_text.strip(): self.selected_text = cb_text.strip()
        except Exception: pass

    def show_centered(self):
        screen = QApplication.primaryScreen().geometry(); x = (screen.width() - self.width()) // 2; y = (screen.height() - self.height()) // 3; self.move(x, y)
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive); self.show(); self.raise_(); self.activateWindow()

    def show_near_cursor(self):
        try:
            cursor_pos = QCursor.pos(); screen = QApplication.primaryScreen().geometry(); w, h = self.width(), self.height(); x = min(cursor_pos.x() + 15, screen.width() - w - 20); y = min(cursor_pos.y() + 15, screen.height() - h - 20); x = max(20, x); y = max(20, y); self.move(x, y)
        except Exception: self.show_centered()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive); self.show(); self.raise_(); self.activateWindow()

    def show_selection_popup(self, text: str, x: int = None, y: int = None):
        if not text or not text.strip(): return
        self.selected_text = text.strip(); self.show_with_context(self.selected_text)
        if x is not None and y is not None:
            screen = QApplication.primaryScreen().geometry(); w, h = self.width(), self.height(); pos_x = min(x + 15, screen.width() - w - 20); pos_y = min(y + 15, screen.height() - h - 20); pos_x = max(20, pos_x); pos_y = max(20, pos_y); self.move(pos_x, pos_y)
        else: self.show_near_cursor()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive); self.show(); self.raise_(); self.activateWindow()

    def show_with_context(self, context_text: str):
        self.selected_text = context_text.strip()[:200]
        if self.ctx_label.text(): self.ctx_label.setText("")
        ctx_preview = f"📋 Selected ({len(context_text)} chars)\n{self.selected_text}"; self.ctx_label.setText(ctx_preview)

    def clear_context(self):
        self.selected_text = ""; self.ctx_label.setText("")

    def on_submit_prompt(self):
        prompt = self.input_field.text().strip();
        if not prompt: return
        self._current_action_name = "prompt"; self._current_user_input = prompt; self._run_action(prompt)

    def execute_action(self, action_type: str):
        if action_type == "quick_help": self.show_quick_help(); return
        if action_type == "copy":
            content = self.output_view.toPlainText();
            if content.strip(): QApplication.clipboard().setText(content); self.status_label.setText("Copied to clipboard"); return
            self.status_label.setText("Nothing to copy"); return
        target_text = self.selected_text or self.input_field.text().strip()
        if not target_text:
            clipboard_text = QApplication.clipboard().text();
            if clipboard_text and clipboard_text.strip():
                target_text = clipboard_text.strip(); self.selected_text = target_text; self.input_field.setText(target_text)
        if not target_text:
            self.output_view.setPlainText("Please select or type text first."); return
        self._current_action_name = action_type; self._current_user_input = target_text
        target_lang = self.lang_combo.currentText() if hasattr(self, "lang_combo") else "Tamil"
        sys_prompt, prompt_text = self.ollama.get_action_prompt(action_type, target_text, target_lang=target_lang)
        self._run_action(prompt_text, system_prompt=sys_prompt)

    def _on_thinking_state_changed(self, is_thinking: bool):
        model_name = self.ollama.get_model_name();
        if is_thinking: self.status_label.setText(f"💭 Thinking via {model_name}…")
        else: self.status_label.setText(f"⚡ Generating response via {model_name}…")

    def stop_generation(self):
        if getattr(self, "worker", None) and self.worker.isRunning():
            try: self.worker.cancel();
            except Exception: pass
        self.status_label.setText("Stopped")

    def _run_action(self, user_input: str, system_prompt: str = ""):
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            try: self.worker.cancel(); self.worker.wait(500)
            except Exception: pass
        self.output_view.clear(); self.input_field.clear(); self.think_filter.reset()
        if self.config.get("history_store_initiated", True):
            self.history_manager.add_started_entry(getattr(self, "_current_action_name", "prompt"), getattr(self, "_current_user_input", user_input), self.ollama.get_model_name())
        model_name = self.ollama.get_model_name(); status_msg = f"⏳ Generating via {model_name}…"
        current_action = getattr(self, "_current_action_name", "")
        if current_action in ("rewrite", "rewrite_short", "rewrite_long", "plan", "improve", "feather"):
            combined_sys = system_prompt.strip()
        else:
            skill_prompt = self.skill_manager.get_active_skill_prompt(); combined_sys = (skill_prompt + "\n\n" + system_prompt).strip()
        def _load_and_generate():
            yield from self.ollama.stream_generate(user_input, system_prompt=combined_sys)
        self.worker = WorkerThread(_load_and_generate); self.worker.chunk_received.connect(self._append_chunk); self.worker.finished.connect(self._on_worker_finished); self.status_label.setText(status_msg); self.worker.start()

    def _append_chunk(self, chunk: str):
        filtered_text = self.think_filter.process_chunk(chunk)
        if filtered_text:
            self.output_view.insertPlainText(filtered_text); scrollbar = self.output_view.verticalScrollBar(); scrollbar.setValue(scrollbar.maximum())

    def _on_worker_finished(self):
        flushed = self.think_filter.flush();
        if flushed: self.output_view.insertPlainText(flushed)
        full_text = self.output_view.toPlainText(); cleaned = clean_think_text(full_text)
        if cleaned != full_text: self.output_view.setPlainText(cleaned)
        if cleaned and hasattr(self, "history_manager") and self.history_manager:
            act = getattr(self, "_current_action_name", "prompt"); inp = getattr(self, "_current_user_input", self.selected_text or "Prompt")
            self.history_manager.add_entry(act, inp, cleaned, model=self.ollama.get_model_name(), status="success")
        if not self.status_label.text().startswith("Copied") and not self.status_label.text().startswith("🖼"): self.status_label.setText("Ready")

    def toggle_voice_input(self):
        if not hasattr(self.audio, "start_recording"): return
        if hasattr(self, "voice_btn") and self.voice_btn.isChecked():
            self.voice_btn.setText("🔴 Recording…"); self.audio.start_recording()
        else:
            text = self.audio.stop_and_transcribe();
            if hasattr(self, "voice_btn"): self.voice_btn.setText("⏳ Transcribing…")
            def _reset_btn():
                if hasattr(self, "voice_btn"): self.voice_btn.setText("🎙 Voice")
            QTimer.singleShot(1500, _reset_btn)
            if text.strip(): self.input_field.setText(text); self.on_submit_prompt()
            else: self.status_label.setText("No speech detected. Try again.")

    def read_aloud(self):
        content = self.output_view.toPlainText().strip();
        if content: self.audio.speak(content)

    def generate_image(self):
        prompt = self.input_field.text().strip() or self.selected_text or "A beautiful landscape"
        if not prompt.strip(): self.output_view.setPlainText("Please enter a description for the image."); return
        self.status_label.setText("🖼 Generating image…")
        result_path = self.image.generate_image(prompt)
        def _show_result():
            if result_path and os.path.exists(result_path):
                try: self.output_view.setPlainText(f"✅ Image saved to:\n{result_path}")
                except Exception as e: self.status_label.setText(f"Image error: {e}")
            else: self.status_label.setText("⚠️  Image generation service not available.")
        QTimer.singleShot(200, _show_result)

    def on_manual_action(self):
        content = self.output_view.toPlainText().strip();
        if not content: self.output_view.clear(); self.input_field.clear(); self.status_label.setText("Output cleared"); return
        QApplication.clipboard().setText(content); self.status_label.setText("Copied to clipboard")

    def process_clipboard_selection(self, text: str = ""):
        if not text: text = self.selected_text or QApplication.clipboard().text()
        if not text.strip():
            self.show_near_cursor(); self.output_view.setPlainText("No selected text detected. Please select text or enter a prompt."); return
        self.selected_text = text.strip(); self.show_with_context(self.selected_text); self.show_near_cursor();
        target_lang = self.lang_combo.currentText() if hasattr(self, "lang_combo") else "Tamil"
        sys_prompt, prompt = self.ollama.get_action_prompt("rewrite_short", text[:300], target_lang=target_lang)
        self._run_action(prompt, system_prompt=sys_prompt)

    def closeEvent(self, event):
        if hasattr(self.audio, "stop_recording"):
            try: self.audio.stop_recording()
            except Exception: pass
        event.accept()

    def start_clipboard_monitor(self):
        if not self.config.get("enable_clipboard_monitor"): return
        try:
            clipboard = QApplication.clipboard()
            def on_clipboard_changed():
                text = clipboard.text();
                if text and text.strip() and text != self.selected_text:
                    self.selected_text = text.strip();
                    if self.isVisible(): self.show_with_context(self.selected_text)
            clipboard.dataChanged.connect(on_clipboard_changed)
        except Exception as e: print(f"  Clipboard monitor warning: {e}")


# compatibility aliases
AIHelperWindowClass = AIHelperWindow
NearbySuggestionPopupClass = NearbySuggestionPopup
HistoryManagerClass = HistoryManager


class AddSkillDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("➕ Add Custom Skill"); self.setFixedSize(400, 240)
        self.setStyleSheet("QDialog { background-color: #1e1e24; color: #e4e4e7; } QLabel { color: #a1a1aa; font-size: 11px; } QLineEdit, QTextEdit { background-color: #141418; color: #f4f4f5; border: 1px solid #272730; border-radius: 6px; padding: 6px; } QPushButton { background-color: #6366f1; color: #ffffff; border-radius: 6px; padding: 4px 12px; font-weight: bold; }")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Skill Name (e.g. 📄 Output Schema):")); self.name_input = QLineEdit(self); self.name_input.setPlaceholderText("Skill Name..."); layout.addWidget(self.name_input)
        layout.addWidget(QLabel("System Prompt Directive / Schema:")); self.prompt_input = QTextEdit(self); self.prompt_input.setPlaceholderText("e.g. Return response strictly in JSON format matching schema..."); layout.addWidget(self.prompt_input)
        btn_box = QHBoxLayout(); save_btn = QPushButton("Save Skill", self); save_btn.clicked.connect(self.accept); cancel_btn = QPushButton("Cancel", self); cancel_btn.setStyleSheet("background-color: #272730; color: #a1a1aa;"); cancel_btn.clicked.connect(self.reject); btn_box.addStretch(); btn_box.addWidget(cancel_btn); btn_box.addWidget(save_btn); layout.addLayout(btn_box)

    def get_skill_data(self):
        return self.name_input.text().strip(), self.prompt_input.toPlainText().strip()


class HistoryDialog(QDialog):
    def __init__(self, history_manager, parent=None):
        super().__init__(parent); self.history_manager = history_manager; self.setWindowTitle("📜 AI Generation History"); self.setFixedSize(580, 520); self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint); self.setStyleSheet("QDialog { background-color: #1e1e24; color: #e4e4e7; } QLabel { font-family: 'Segoe UI', sans-serif; } QPushButton { font-family: 'Segoe UI', sans-serif; border-radius: 5px; font-size: 11px; } QLineEdit { background-color: #141418; color: #f4f4f5; border: 1px solid #272730; border-radius: 6px; padding: 6px; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(12, 12, 12, 12); layout.setSpacing(8)
        top_bar = QHBoxLayout(); self.search_input = QLineEdit(self); self.search_input.setPlaceholderText("🔍 Search history..."); self.search_input.textChanged.connect(self.refresh_list)
        clear_btn = QPushButton("🗑 Clear History", self); clear_btn.setStyleSheet("QPushButton { background-color: #272730; color: #ef4444; padding: 4px 10px; font-weight: bold; } QPushButton:hover { background-color: #ef4444; color: #ffffff; }"); clear_btn.clicked.connect(self.clear_all)
        top_bar.addWidget(self.search_input, 1); top_bar.addWidget(clear_btn); layout.addLayout(top_bar)
        self.scroll = QScrollArea(self); self.scroll.setWidgetResizable(True); self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.scroll_content = QWidget(); self.scroll_layout = QVBoxLayout(self.scroll_content); self.scroll_layout.setContentsMargins(0, 0, 0, 0); self.scroll_layout.setSpacing(8)
        self.scroll.setWidget(self.scroll_content); layout.addWidget(self.scroll, 1); self.refresh_list()

    def refresh_list(self):
        while self.scroll_layout.count() > 0:
            item = self.scroll_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        query = self.search_input.text().strip(); items = self.history_manager.search(query)
        if not items:
            empty_lbl = QLabel("No history items found.", self.scroll_content); empty_lbl.setStyleSheet("color: #71717a; font-size: 12px; font-style: italic; margin: 20px 0;"); empty_lbl.setAlignment(Qt.AlignCenter); self.scroll_layout.addWidget(empty_lbl)
        else:
            for item in items: self.scroll_layout.addWidget(self._create_item_card(item))
        self.scroll_layout.addStretch()

    def _create_item_card(self, item: dict) -> QFrame:
        card = QFrame(self.scroll_content); card.setStyleSheet("QFrame { background-color: #272730; border-radius: 8px; border: 1px solid #33333d; padding: 6px; }")
        card_layout = QVBoxLayout(card); card_layout.setSpacing(4)
        header = QHBoxLayout(); act_name = item.get("action", "action").upper(); badge = QLabel(f"⚡ {act_name}", card); badge.setStyleSheet("color: #818cf8; font-weight: bold; font-size: 10px; background: #3730a3; border-radius: 4px; padding: 2px 6px;")
        time_lbl = QLabel(item.get("timestamp", ""), card); time_lbl.setStyleSheet("color: #a1a1aa; font-size: 10px;")
        del_btn = QPushButton("🗑", card); del_btn.setFixedSize(22, 22); del_btn.setStyleSheet("QPushButton { color: #a1a1aa; background: none; border: none; font-size: 12px; } QPushButton:hover { color: #ef4444; }")
        del_btn.clicked.connect(lambda checked, id_val=item.get("id"): self._delete_item(id_val))
        header.addWidget(badge); header.addWidget(time_lbl); header.addStretch(); header.addWidget(del_btn); card_layout.addLayout(header)
        prompt_text = item.get("prompt", ""); prompt_hdr = QLabel("<b>User Request Prompt:</b>", card); prompt_hdr.setStyleSheet("color: #a5b4fc; font-size: 10px;"); card_layout.addWidget(prompt_hdr)
        prompt_box = QTextEdit(card); prompt_box.setReadOnly(True); prompt_box.setFixedHeight(48); prompt_box.setPlainText(prompt_text); prompt_box.setStyleSheet("QTextEdit { background-color: #1c1c22; color: #e4e4e7; border: 1px solid #3730a3; border-radius: 5px; font-size: 11px; padding: 4px; font-weight: 500; }")
        card_layout.addWidget(prompt_box)
        resp_hdr = QLabel("<b>AI Response:</b>", card); resp_hdr.setStyleSheet("color: #34d399; font-size: 10px;"); card_layout.addWidget(resp_hdr)
        resp_box = QTextEdit(card); resp_box.setReadOnly(True); resp_box.setFixedHeight(75); resp_box.setPlainText(item.get("response", "")); resp_box.setStyleSheet("QTextEdit { background-color: #141418; color: #f4f4f5; border: 1px solid #1f1f24; border-radius: 5px; font-size: 11px; padding: 4px; }")
        card_layout.addWidget(resp_box)
        bot_row = QHBoxLayout(); copy_prompt_btn = QPushButton("📋 Copy Prompt", card); copy_prompt_btn.setFixedHeight(22); copy_prompt_btn.setStyleSheet("QPushButton { background-color: #3730a3; color: #ffffff; padding: 2px 8px; font-weight: 500; } QPushButton:hover { background-color: #4f46e5; }")
        def _copy_prompt(p_val=prompt_text):
            QApplication.clipboard().setText(p_val); copy_prompt_btn.setText("✓ Copied Prompt!"); QTimer.singleShot(1500, lambda: copy_prompt_btn.setText("📋 Copy Prompt"))
        copy_prompt_btn.clicked.connect(_copy_prompt)
        copy_resp_btn = QPushButton("📋 Copy Response", card); copy_resp_btn.setFixedHeight(22); copy_resp_btn.setStyleSheet("QPushButton { background-color: #3f3f4e; color: #ffffff; padding: 2px 8px; font-weight: 500; } QPushButton:hover { background-color: #6366f1; }")
        def _copy_resp(r_val=item.get("response", "")):
            QApplication.clipboard().setText(r_val); copy_resp_btn.setText("✓ Copied Response!"); QTimer.singleShot(1500, lambda: copy_resp_btn.setText("📋 Copy Response"))
        copy_resp_btn.clicked.connect(_copy_resp)
        bot_row.addWidget(copy_prompt_btn); bot_row.addStretch(); bot_row.addWidget(copy_resp_btn); card_layout.addLayout(bot_row)
        return card

    def _delete_item(self, entry_id: str):
        self.history_manager.delete_entry(entry_id); self.refresh_list()

    def clear_all(self):
        reply = QMessageBox.question(self, "Clear History", "Are you sure you want to clear all history?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes: self.history_manager.clear_history(); self.refresh_list()


# module-level names expected by main.py
AIHelperWindow = AIHelperWindow
NearbySuggestionPopup = NearbySuggestionPopup
HistoryManager = HistoryManager
