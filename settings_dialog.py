"""
Settings Dialog for Win AI Helper
Handles theme selection, AI provider configuration, model selection, and defaults
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, 
    QLineEdit, QPushButton, QLabel, QTabWidget, QWidget, QSpinBox,
    QCheckBox, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
import json
import urllib.request
import threading


class ModelLoaderThread(QThread):
    """Background thread for loading models from AI providers"""
    models_loaded = Signal(list)
    error_occurred = Signal(str)
    
    def __init__(self, endpoint, provider):
        super().__init__()
        self.endpoint = endpoint
        self.provider = provider
    
    def run(self):
        try:
            if self.provider == "ollama":
                self._load_ollama_models()
            elif self.provider == "lm_studio":
                self._load_lm_studio_models()
            elif self.provider == "openai":
                self._load_openai_models()
        except Exception as e:
            self.error_occurred.emit(f"Failed to load models: {str(e)}")
    
    def _load_ollama_models(self):
        """Load models from Ollama endpoint"""
        try:
            url = f"{self.endpoint}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                models = [m['name'] for m in data.get('models', [])]
                self.models_loaded.emit(models)
        except Exception as e:
            self.error_occurred.emit(f"Ollama connection failed: {str(e)}")
    
    def _load_lm_studio_models(self):
        """Load models from LM Studio endpoint"""
        try:
            url = f"{self.endpoint}/models"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                models = [m['id'] for m in data.get('data', [])]
                self.models_loaded.emit(models)
        except Exception as e:
            self.error_occurred.emit(f"LM Studio connection failed: {str(e)}")
    
    def _load_openai_models(self):
        """Load models from OpenAI endpoint"""
        try:
            api_key = getattr(self, 'api_key', '')
            url = f"{self.endpoint}/models"
            req = urllib.request.Request(url)
            req.add_header('Authorization', f'Bearer {api_key}')
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                models = [m['id'] for m in data.get('data', [])]
                self.models_loaded.emit(models)
        except Exception as e:
            self.error_occurred.emit(f"OpenAI connection failed: {str(e)}")


class SettingsDialog(QDialog):
    """Main settings dialog with theme, provider, and model configuration"""
    settings_changed = Signal()
    
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("⚙️ Settings")
        self.resize(600, 500)
        self.model_loader_thread = None
        
        self._build_ui()
        self._load_saved_values()
        self._setup_connections()
    
    def _build_ui(self):
        """Build the settings UI with tabs"""
        main_layout = QVBoxLayout(self)
        
        # Tab widget for different setting sections
        tabs = QTabWidget()
        
        # Theme Tab
        theme_tab = self._build_theme_tab()
        tabs.addTab(theme_tab, "🎨 Theme")
        
        # Provider Tab
        provider_tab = self._build_provider_tab()
        tabs.addTab(provider_tab, "🤖 AI Provider")
        
        # History Tab
        history_tab = self._build_history_tab()
        tabs.addTab(history_tab, "📜 History")
        
        main_layout.addWidget(tabs)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("💾 Save Settings")
        save_btn.clicked.connect(self._save_settings)
        button_layout.addWidget(save_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        main_layout.addLayout(button_layout)
    
    def _build_theme_tab(self):
        """Build theme selection tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        label = QLabel("Select Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["white", "black", "system"])
        
        layout.addRow(label, self.theme_combo)
        layout.addRow(QLabel("Restart the application for theme changes to take effect."))
        
        return widget
    
    def _build_provider_tab(self):
        """Build AI provider configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Provider selection
        provider_layout = QFormLayout()
        
        label = QLabel("AI Provider:")
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["ollama", "lm_studio", "openai"])
        provider_layout.addRow(label, self.provider_combo)
        
        layout.addLayout(provider_layout)
        
        # Provider-specific settings
        self.provider_settings = QFormLayout()
        
        # Endpoint
        self.endpoint_input = QLineEdit()
        self.provider_settings.addRow("Endpoint:", self.endpoint_input)
        
        # API Key (for OpenAI)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.provider_settings.addRow("API Key:", self.api_key_input)
        
        # Load Models Button
        self.load_models_btn = QPushButton("🔄 Load Available Models")
        self.load_models_btn.clicked.connect(self._load_provider_models)
        self.provider_settings.addRow(self.load_models_btn)
        
        layout.addLayout(self.provider_settings)
        
        # Default Model selection
        model_group = QGroupBox("Model Configuration")
        model_layout = QFormLayout(model_group)
        
        self.default_model_combo = QComboBox()
        self.default_model_combo.setEditable(True)
        model_layout.addRow("Default Model:", self.default_model_combo)
        
        self.fallback_model_combo = QComboBox()
        self.fallback_model_combo.setEditable(True)
        model_layout.addRow("Fallback Model:", self.fallback_model_combo)
        
        layout.addWidget(model_group)
        layout.addStretch()
        
        return widget
    
    def _build_history_tab(self):
        """Build history configuration tab"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # Store successful responses only
        self.history_success_only = QCheckBox("Store successful responses only")
        layout.addRow(self.history_success_only)
        
        # Store initiated requests
        self.history_initiated = QCheckBox("Store all initiated requests")
        layout.addRow(self.history_initiated)
        
        layout.addRow(QLabel("When enabled, all requests are captured in history,\nnot just successful ones."))
        
        return widget
    
    def _load_saved_values(self):
        """Load current configuration values into UI elements"""
        # Theme
        theme = self.config.get("theme", "system")
        self.theme_combo.setCurrentText(theme)
        
        # Provider
        current_provider = self.config.get("ai_provider", "ollama")
        self.provider_combo.setCurrentText(current_provider)
        
        # Load provider settings
        self._refresh_provider_state()
        
        # History settings
        self.history_success_only.setChecked(
            not self.config.get("history_store_success_only", False)
        )
        self.history_initiated.setChecked(
            self.config.get("history_store_initiated", True)
        )
    
    def _refresh_provider_state(self):
        """Update provider settings based on selected provider"""
        provider = self.provider_combo.currentText()
        provider_config = self.config.get("providers", {}).get(provider, {})
        
        self.endpoint_input.setText(provider_config.get("endpoint", ""))
        self.api_key_input.setText(provider_config.get("api_key", ""))
        
        # Show/hide API key field based on provider
        if provider == "openai":
            self.provider_settings.labelForField(self.api_key_input).show()
            self.api_key_input.show()
        else:
            self.provider_settings.labelForField(self.api_key_input).hide()
            self.api_key_input.hide()
        
        # Load model lists
        self._populate_model_lists(provider_config.get("models", []))
    
    def _populate_model_lists(self, models):
        """Populate model dropdown lists"""
        self.default_model_combo.clear()
        self.fallback_model_combo.clear()
        
        if models:
            self.default_model_combo.addItems(models)
            self.fallback_model_combo.addItems(models)
    
    def _load_provider_models(self):
        """Load models from the selected provider"""
        provider = self.provider_combo.currentText()
        endpoint = self.endpoint_input.text()
        
        if not endpoint:
            QMessageBox.warning(self, "Error", "Please enter an endpoint URL")
            return
        
        self.load_models_btn.setText("⏳ Loading...")
        self.load_models_btn.setEnabled(False)
        
        # Create and start loader thread
        self.model_loader_thread = ModelLoaderThread(endpoint, provider)
        self.model_loader_thread.models_loaded.connect(self._on_models_loaded)
        self.model_loader_thread.error_occurred.connect(self._on_model_load_error)
        self.model_loader_thread.start()
    
    def _on_models_loaded(self, models):
        """Handle successful model loading"""
        self.load_models_btn.setText("✓ Models Loaded")
        self.load_models_btn.setEnabled(True)
        self._populate_model_lists(models)
        
        # Update config with loaded models
        provider = self.provider_combo.currentText()
        if "providers" not in self.config:
            self.config["providers"] = {}
        if provider not in self.config["providers"]:
            self.config["providers"][provider] = {}
        self.config["providers"][provider]["models"] = models
    
    def _on_model_load_error(self, error_msg):
        """Handle model loading error"""
        self.load_models_btn.setText("🔄 Load Available Models")
        self.load_models_btn.setEnabled(True)
        QMessageBox.warning(self, "Error", error_msg)
    
    def _setup_connections(self):
        """Setup signal connections"""
        self.provider_combo.currentTextChanged.connect(self._refresh_provider_state)
    
    def _save_settings(self):
        """Save settings back to config"""
        self.config["theme"] = self.theme_combo.currentText()
        self.config["ai_provider"] = self.provider_combo.currentText()
        
        # Update provider config
        provider = self.provider_combo.currentText()
        if "providers" not in self.config:
            self.config["providers"] = {}
        if provider not in self.config["providers"]:
            self.config["providers"][provider] = {}
        
        self.config["providers"][provider]["endpoint"] = self.endpoint_input.text()
        self.config["providers"][provider]["api_key"] = self.api_key_input.text()
        self.config["providers"][provider]["default_model"] = self.default_model_combo.currentText()
        self.config["providers"][provider]["fallback_model"] = self.fallback_model_combo.currentText()
        
        # History settings
        self.config["history_store_success_only"] = not self.history_success_only.isChecked()
        self.config["history_store_initiated"] = self.history_initiated.isChecked()
        
        self.settings_changed.emit()
        QMessageBox.information(self, "Success", "Settings saved successfully!")
        self.accept()
