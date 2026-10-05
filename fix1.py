import sys

with open('gui_overlay.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 11: Add drag state to AIHelperWindow.__init__
content = content.replace(
    '        self._current_action_name = "prompt"; self._current_user_input = ""; self.think_filter = ThinkFilter(on_thinking_state_change=self._on_thinking_state_changed)\n        self.init_ui(); self._detect_clipboard(); self._apply_theme(self.config.get("theme", "system"))',
    '        self._current_action_name = "prompt"; self._current_user_input = ""; self.think_filter = ThinkFilter(on_thinking_state_change=self._on_thinking_state_changed)\n        self._drag_active = False; self._drag_start_pos = None\n        self.init_ui(); self._detect_clipboard(); self._apply_theme(self.config.get("theme", "system"))'
)

# Fix 12: Add mouse event handlers to AIHelperWindow after _detect_clipboard
old = '    def _detect_clipboard(self):\n        try:\n            cb_text = QApplication.clipboard().text();\n            if cb_text and cb_text.strip(): self.selected_text = cb_text.strip()\n        except Exception: pass\n\n    def show_centered(self):'
new = '    def _detect_clipboard(self):\n        try:\n            cb_text = QApplication.clipboard().text();\n            if cb_text and cb_text.strip(): self.selected_text = cb_text.strip()\n        except Exception: pass\n\n    def mousePressEvent(self, event: QMouseEvent):\n        if event.button() == Qt.LeftButton:\n            self._drag_active = True\n            self._drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()\n        super().mousePressEvent(event)\n\n    def mouseMoveEvent(self, event: QMouseEvent):\n        if self._drag_active and self._drag_start_pos is not None:\n            self.move(event.globalPosition().toPoint() - self._drag_start_pos)\n        super().mouseMoveEvent(event)\n\n    def mouseReleaseEvent(self, event: QMouseEvent):\n        if event.button() == Qt.LeftButton:\n            self._drag_active = False\n            self._drag_start_pos = None\n        super().mouseReleaseEvent(event)\n\n    def show_centered(self):'
content = content.replace(old, new)

with open('gui_overlay.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Part 4 done')



