"""Settings dialog for the application."""
import json

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QComboBox,
    QCheckBox, QGroupBox, QTabWidget, QButtonGroup,
    QMessageBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QLineEdit, QAbstractItemView,
    QSlider, QToolTip,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCursor

from config import WHISPER_MODELS, SHERPA_MODELS, PODLODKA_MODELS, GROQ_MODELS, LANGUAGES, BACKENDS, MOUSE_BUTTONS, PASTE_METHODS, QUALITY_PROFILES, MODEL_METADATA
from widgets import COLORS, COLORS_HEX, DIALOG_STYLESHEET, DictionaryEntryDialog


class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None, history_manager=None):
        super().__init__(parent)
        self.config = config
        self.history_manager = history_manager
        self.setWindowTitle("Настройки")
        self.setMinimumSize(450, 500)
        self.setStyleSheet(DIALOG_STYLESHEET)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._setup_ui()
        self._drag_position = None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("Настройки")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 14px;
                color: white;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #e94560;
            }
        """)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._create_settings_tab()
        self._create_dictionary_tab()
        self._create_history_tab()

    def _create_settings_tab(self):
        """Create settings tab - minimal version."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        content = QWidget()
        scroll_layout = QVBoxLayout(content)

        # === Quality Profile Selection ===
        quality_group = QGroupBox("Профиль качества")
        quality_layout = QVBoxLayout(quality_group)

        self.quality_profile_group = QButtonGroup()
        self.quality_profile_buttons = {}

        for profile_id in ["fast", "balanced", "quality"]:
            profile_info = QUALITY_PROFILES[profile_id]
            btn = QPushButton(profile_info["description"])
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['bg_mid']};
                    color: {COLORS['text_primary']};
                    border: 2px solid {COLORS['border']};
                    border-radius: 8px;
                    padding: 12px 8px;
                    text-align: center;
                    font-size: 12px;
                }}
                QPushButton:checked {{
                    background-color: {COLORS['accent_primary']};
                    border-color: {COLORS['accent_secondary']};
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent_primary']};
                }}
            """)
            self.quality_profile_buttons[profile_id] = btn
            self.quality_profile_group.addButton(btn, int(profile_id == "fast") + int(profile_id == "balanced") * 2 + int(profile_id == "quality") * 3)
            quality_layout.addWidget(btn)

        current_profile = self.config.quality_profile if self.config else "quality"
        if current_profile in self.quality_profile_buttons:
            self.quality_profile_buttons[current_profile].setChecked(True)

        scroll_layout.addWidget(quality_group)

        # === Basic settings: auto_copy, auto_paste, sound ===
        basic_group = QGroupBox("Основные")
        basic_layout = QVBoxLayout(basic_group)

        self.auto_copy_cb = QCheckBox("Авто-копирование")
        self.auto_paste_cb = QCheckBox("Авто-вставка")
        self.sound_feedback_cb = QCheckBox("Звуковой сигнал (старт/стоп)")

        if self.config:
            self.auto_copy_cb.setChecked(self.config.auto_copy)
            self.auto_paste_cb.setChecked(self.config.auto_paste)
            self.sound_feedback_cb.setChecked(self.config.sound_feedback)

        basic_layout.addWidget(self.auto_copy_cb)
        basic_layout.addWidget(self.auto_paste_cb)
        basic_layout.addWidget(self.sound_feedback_cb)
        scroll_layout.addWidget(basic_group)

        # === Advanced settings (collapsed by default) ===
        advanced_group = QGroupBox("Расширенные настройки")
        advanced_group.setCheckable(True)
        advanced_group.setChecked(False)  # Collapsed by default
        advanced_layout = QVBoxLayout(advanced_group)
        self._advanced_group = advanced_group

        # Info label
        advanced_layout.addWidget(QLabel(f"Бэкенд: {self.config.backend if self.config else 'N/A'}"))
        advanced_layout.addWidget(QLabel(f"Модель: {self.config.model_size if self.config else 'N/A'}"))

        # Backend combo
        backend_group = QGroupBox("Движок")
        backend_layout = QVBoxLayout(backend_group)
        self.backend_combo = QComboBox()
        for bid, bname in BACKENDS.items():
            self.backend_combo.addItem(bname, bid)
        if self.config:
            self.backend_combo.setCurrentIndex(list(BACKENDS.keys()).index(self.config.backend))
        backend_layout.addWidget(self.backend_combo)
        advanced_layout.addWidget(backend_group)

        # Model combo
        model_group = QGroupBox("Модель")
        model_layout = QVBoxLayout(model_group)
        self.model_combo = QComboBox()
        self._update_model_options()
        model_layout.addWidget(self.model_combo)

        self.model_info_label = QLabel()
        self.model_info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")
        model_layout.addWidget(self.model_info_label)

        advanced_layout.addWidget(model_group)

        # Language combo
        lang_group = QGroupBox("Язык")
        lang_layout = QVBoxLayout(lang_group)
        self.lang_combo = QComboBox()
        for lid, lname in LANGUAGES.items():
            self.lang_combo.addItem(lname, lid)
        if self.config and self.config.language in LANGUAGES:
            self.lang_combo.setCurrentIndex(list(LANGUAGES.keys()).index(self.config.language))
        lang_layout.addWidget(self.lang_combo)
        advanced_layout.addWidget(lang_group)

        # Behavior group (advanced — paste method, always_top, post_process)
        behavior_group = QGroupBox("Поведение")
        behavior_layout = QVBoxLayout(behavior_group)

        paste_method_label = QLabel("Метод вставки:")
        paste_method_label.setStyleSheet("margin-top: 5px;")
        self.paste_method_combo = QComboBox()
        for mid, mname in PASTE_METHODS.items():
            self.paste_method_combo.addItem(mname, mid)
        if self.config and self.config.paste_method in PASTE_METHODS:
            self.paste_method_combo.setCurrentIndex(
                list(PASTE_METHODS.keys()).index(self.config.paste_method)
            )

        self.always_top_cb = QCheckBox("Поверх окон")
        self.post_process_cb = QCheckBox("Пост-обработка")

        if self.config:
            self.always_top_cb.setChecked(self.config.always_on_top)
            self.post_process_cb.setChecked(self.config.enable_post_processing)

        behavior_layout.addWidget(paste_method_label)
        behavior_layout.addWidget(self.paste_method_combo)
        behavior_layout.addWidget(self.always_top_cb)
        behavior_layout.addWidget(self.post_process_cb)
        advanced_layout.addWidget(behavior_group)

        # Mouse button group
        mouse_group = QGroupBox("Кнопка мыши")
        mouse_layout = QVBoxLayout(mouse_group)

        self.enable_mouse_button_cb = QCheckBox("Использовать кнопку мыши для записи")
        if self.config:
            self.enable_mouse_button_cb.setChecked(self.config.enable_mouse_button)
        mouse_layout.addWidget(self.enable_mouse_button_cb)

        self.mouse_button_combo = QComboBox()
        for bid, bname in MOUSE_BUTTONS.items():
            self.mouse_button_combo.addItem(bname, bid)
        if self.config and self.config.mouse_button in MOUSE_BUTTONS:
            self.mouse_button_combo.setCurrentIndex(
                list(MOUSE_BUTTONS.keys()).index(self.config.mouse_button)
            )
        mouse_layout.addWidget(self.mouse_button_combo)

        advanced_layout.addWidget(mouse_group)

        # VAD Settings group
        vad_group = QGroupBox("Голосовая активность (VAD)")
        vad_layout = QVBoxLayout(vad_group)

        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Порог:")
        threshold_label.setFixedWidth(80)
        threshold_layout.addWidget(threshold_label)

        self.vad_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_threshold_slider.setRange(0, 100)
        vad_layout.addWidget(QLabel("Чувствительность детекции речи"))
        vad_layout.addWidget(self.vad_threshold_slider)

        self.vad_threshold_value = QLabel("0.50")
        self.vad_threshold_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vad_threshold_value.setFixedWidth(50)
        vad_layout.addWidget(self.vad_threshold_value)

        threshold_positions = QHBoxLayout()
        threshold_positions.addWidget(QLabel("Тихий"))
        threshold_positions.addStretch()
        threshold_positions.addWidget(QLabel("Чувствительный"))
        vad_layout.addLayout(threshold_positions)

        vad_layout.addSpacing(10)
        vad_layout.addWidget(QLabel("Мин. тишина перед остановкой:"))

        silence_layout = QHBoxLayout()
        self.min_silence_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_silence_slider.setRange(100, 3000)
        vad_layout.addWidget(self.min_silence_slider)

        self.min_silence_value = QLabel("800мс")
        self.min_silence_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.min_silence_value.setFixedWidth(60)
        vad_layout.addWidget(self.min_silence_value)

        silence_positions = QHBoxLayout()
        silence_positions.addWidget(QLabel("Коротко"))
        silence_positions.addStretch()
        silence_positions.addWidget(QLabel("Долго"))
        vad_layout.addLayout(silence_positions)

        vad_layout.addSpacing(10)
        vad_reset_btn = QPushButton("Сбросить настройки VAD")
        vad_reset_btn.clicked.connect(self._reset_vad_defaults)
        vad_layout.addWidget(vad_reset_btn)

        advanced_layout.addWidget(vad_group)

        # Auto-Stop group
        auto_stop_group = QGroupBox("Автостоп при тишине")
        auto_stop_layout = QVBoxLayout(auto_stop_group)

        self.auto_stop_cb = QCheckBox("Автоматически останавливать запись при тишине")
        self.auto_stop_cb.setToolTip("Запись прекратится если тишина длится дольше указанного времени")
        auto_stop_layout.addWidget(self.auto_stop_cb)

        auto_stop_layout.addSpacing(5)
        auto_stop_layout.addWidget(QLabel("Время тишины (секунд):"))
        self.auto_stop_slider = QSlider(Qt.Orientation.Horizontal)
        self.auto_stop_slider.setRange(10, 100)  # 1.0 - 10.0 seconds (value / 10)
        self.auto_stop_value = QLabel()
        auto_stop_layout.addWidget(self.auto_stop_slider)
        auto_stop_layout.addWidget(self.auto_stop_value)

        advanced_layout.addWidget(auto_stop_group)

        # Noise Reduction group
        noise_group = QGroupBox("Шумоподавление")
        noise_layout = QVBoxLayout(noise_group)

        self.webrtc_enabled_cb = QCheckBox("Включить обработку WebRTC")
        self.webrtc_enabled_cb.setToolTip("Шумоподавление и автоматическая регулировка усиления")
        noise_layout.addWidget(self.webrtc_enabled_cb)

        noise_layout.addSpacing(5)
        noise_layout.addWidget(QLabel("Уровень подавления шума:"))

        self.noise_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.noise_level_slider.setRange(0, 4)
        noise_layout.addWidget(self.noise_level_slider)

        self.noise_level_value = QLabel("Умеренно")
        self.noise_level_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        noise_layout.addWidget(self.noise_level_value)

        noise_positions = QHBoxLayout()
        noise_positions.addWidget(QLabel("Выкл"))
        noise_positions.addWidget(QLabel("Слабо"))
        noise_positions.addWidget(QLabel("Умеренно"))
        noise_positions.addWidget(QLabel("Сильно"))
        noise_positions.addWidget(QLabel("Очень"))
        noise_layout.addLayout(noise_positions)

        self.noise_status_label = QLabel("(Активно)")
        self.noise_status_label.setStyleSheet(f"color: {COLORS['accent_secondary']}; font-size: 11px;")
        noise_layout.addWidget(self.noise_status_label)

        noise_layout.addSpacing(10)
        noise_reset_btn = QPushButton("Сбросить настройки шума")
        noise_reset_btn.clicked.connect(self._reset_noise_defaults)
        noise_layout.addWidget(noise_reset_btn)

        advanced_layout.addWidget(noise_group)

        scroll_layout.addWidget(advanced_group)
        scroll_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self.tabs.addTab(tab, "Настройки")

    def _create_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        if self.config:
            stats = QGroupBox("Статистика")
            stats_layout = QVBoxLayout(stats)
            self.stats_words = QLabel(f"Слов: {self.config.total_words:,}")
            self.stats_recordings = QLabel(f"Всего записей (за время использования): {self.config.total_recordings:,}")
            self.stats_saved = QLabel(f"Время: {self.config.total_seconds_saved/60:.1f} мин")
            stats_layout.addWidget(self.stats_words)
            stats_layout.addWidget(self.stats_recordings)
            stats_layout.addWidget(self.stats_saved)
            layout.addWidget(stats)

        # Search field
        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Поиск по тексту...")
        self.history_search.textChanged.connect(self._filter_history)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.history_search)
        layout.addLayout(search_layout)

        # History table
        history_group = QGroupBox("История")
        history_layout = QVBoxLayout(history_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["#", "Время", "Текст", "Слов", "Backend"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.cellDoubleClicked.connect(self._copy_history_on_double_click)
        history_layout.addWidget(self.history_table)

        # Buttons row
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("Копировать")
        copy_btn.clicked.connect(self._copy_history_entry)
        btn_layout.addWidget(copy_btn)

        export_btn = QPushButton("Экспорт")
        export_btn.clicked.connect(self._export_history)
        btn_layout.addWidget(export_btn)

        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(self._clear_history)
        btn_layout.addWidget(clear_btn)

        history_layout.addLayout(btn_layout)
        layout.addWidget(history_group)

        self.tabs.addTab(tab, "История")
        self._update_history_display()

    def _create_dictionary_tab(self):
        """Create the user dictionary tab for custom corrections."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск:")
        self.dictionary_search = QLineEdit()
        self.dictionary_search.setPlaceholderText("Введите текст для поиска...")
        self.dictionary_search.textChanged.connect(self._filter_dictionary)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.dictionary_search)
        layout.addLayout(search_layout)

        self.dictionary_table = QTableWidget()
        self.dictionary_table.setColumnCount(3)
        self.dictionary_table.setHorizontalHeaderLabels(["Неправильно", "Правильно", "С учетом регистра"])
        self.dictionary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.dictionary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.dictionary_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.dictionary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.dictionary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.dictionary_table)

        buttons_layout = QHBoxLayout()

        self.dict_add_btn = QPushButton("Добавить")
        self.dict_add_btn.clicked.connect(self._add_dictionary_entry)
        buttons_layout.addWidget(self.dict_add_btn)

        self.dict_edit_btn = QPushButton("Изменить")
        self.dict_edit_btn.clicked.connect(self._edit_dictionary_entry)
        buttons_layout.addWidget(self.dict_edit_btn)

        self.dict_delete_btn = QPushButton("Удалить")
        self.dict_delete_btn.clicked.connect(self._delete_dictionary_entry)
        buttons_layout.addWidget(self.dict_delete_btn)

        layout.addLayout(buttons_layout)

        io_layout = QHBoxLayout()

        self.dict_import_btn = QPushButton("Импорт")
        self.dict_import_btn.clicked.connect(self._import_dictionary)
        io_layout.addWidget(self.dict_import_btn)

        self.dict_export_btn = QPushButton("Экспорт")
        self.dict_export_btn.clicked.connect(self._export_dictionary)
        io_layout.addWidget(self.dict_export_btn)

        layout.addLayout(io_layout)

        self.tabs.addTab(tab, "Словарь")
        self._update_dictionary_display()

    def _update_dictionary_display(self):
        if not hasattr(self, 'dictionary_table'):
            return

        self.dictionary_table.setRowCount(0)

        if not self.config:
            return

        for entry in self.config.user_dictionary:
            row = self.dictionary_table.rowCount()
            self.dictionary_table.insertRow(row)
            self.dictionary_table.setItem(row, 0, QTableWidgetItem(entry.get("wrong", "")))
            self.dictionary_table.setItem(row, 1, QTableWidgetItem(entry.get("correct", "")))

            case_sensitive = entry.get("case_sensitive", False)
            case_item = QTableWidgetItem("Да" if case_sensitive else "Нет")
            case_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.dictionary_table.setItem(row, 2, case_item)

    def _filter_dictionary(self, text: str):
        search_text = text.lower()
        for row in range(self.dictionary_table.rowCount()):
            show = False
            for col in range(2):
                item = self.dictionary_table.item(row, col)
                if item and search_text in item.text().lower():
                    show = True
                    break
            self.dictionary_table.setRowHidden(row, not show)

    def _add_dictionary_entry(self):
        dialog = DictionaryEntryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            entry = dialog.get_entry()
            self.config.user_dictionary.append(entry)
            self.config.save()
            self._update_dictionary_display()
            if hasattr(self, 'transcriber'):
                self.transcriber.set_user_dictionary(self.config.user_dictionary)

    def _edit_dictionary_entry(self):
        selected = self.dictionary_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Предупреждение", "Выберите запись для изменения")
            return

        row = self.dictionary_table.currentRow()
        wrong = self.dictionary_table.item(row, 0).text()
        correct = self.dictionary_table.item(row, 1).text()
        case_sensitive = self.dictionary_table.item(row, 2).text() == "Да"

        dialog = DictionaryEntryDialog(self, wrong, correct, case_sensitive)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            entry = dialog.get_entry()
            self.config.user_dictionary[row] = entry
            self.config.save()
            self._update_dictionary_display()
            if hasattr(self, 'transcriber'):
                self.transcriber.set_user_dictionary(self.config.user_dictionary)

    def _delete_dictionary_entry(self):
        selected = self.dictionary_table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "Предупреждение", "Выберите запись для удаления")
            return

        row = self.dictionary_table.currentRow()
        wrong = self.config.user_dictionary[row].get("wrong", "")

        reply = QMessageBox.question(
            self, "Подтверждение",
            f'Удалить запись "{wrong}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            del self.config.user_dictionary[row]
            self.config.save()
            self._update_dictionary_display()
            if hasattr(self, 'transcriber'):
                self.transcriber.set_user_dictionary(self.config.user_dictionary)

    def _import_dictionary(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Импорт словаря", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported = json.load(f)

                existing_wrongs = {e.get("wrong") for e in self.config.user_dictionary}
                for entry in imported:
                    wrong = entry.get("wrong")
                    if wrong and wrong not in existing_wrongs:
                        self.config.user_dictionary.append(entry)
                        existing_wrongs.add(wrong)

                self.config.save()
                self._update_dictionary_display()
                if hasattr(self, 'transcriber'):
                    self.transcriber.set_user_dictionary(self.config.user_dictionary)

                QMessageBox.information(self, "Успех", f"Импортировано записей: {len(imported)}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать: {e}")

    def _export_dictionary(self):
        if not self.config.user_dictionary:
            QMessageBox.information(self, "Информация", "Словарь пуст")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт словаря", "dictionary.json", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config.user_dictionary, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, "Успех", f"Экспортировано записей: {len(self.config.user_dictionary)}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось экспортировать: {e}")

    def _update_model_options(self):
        self.model_combo.clear()
        if not self.config:
            return
        backend = self.backend_combo.currentData() or self.config.backend
        models = {"whisper": WHISPER_MODELS, "sherpa": SHERPA_MODELS, "podlodka-turbo": PODLODKA_MODELS, "groq": GROQ_MODELS}.get(backend, {})

        sorted_models = sorted(models.items(), key=lambda x: MODEL_METADATA.get(x[0], {}).get("rtf", 1.0))

        for mid, mname in sorted_models:
            meta = MODEL_METADATA.get(mid, {})
            ram = meta.get("ram_mb", "?")
            desc = meta.get("description", "")
            display_text = f"{mid} — {ram}MB — {desc}"
            self.model_combo.addItem(display_text, mid)

        if self.config.model_size in models:
            self.model_combo.setCurrentIndex(list(models.keys()).index(self.config.model_size))

    def _update_history_display(self, entries=None):
        if not self.history_manager:
            return
        if entries is None:
            entries = self.history_manager.get_history()
        self.history_table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            self.history_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.history_table.setItem(i, 1, QTableWidgetItem(e.timestamp))
            # Truncate long text for display
            display_text = e.text[:80] + "..." if len(e.text) > 80 else e.text
            item = QTableWidgetItem(display_text)
            item.setToolTip(e.text)  # Full text on hover
            self.history_table.setItem(i, 2, item)
            self.history_table.setItem(i, 3, QTableWidgetItem(str(e.word_count)))
            self.history_table.setItem(i, 4, QTableWidgetItem(e.backend))

    def _filter_history(self, query: str):
        if not self.history_manager:
            return
        entries = self.history_manager.search_history(query)
        self._update_history_display(entries)

    def _copy_history_entry(self):
        row = self.history_table.currentRow()
        if row < 0:
            return
        text_item = self.history_table.item(row, 2)
        if text_item:
            full_text = text_item.toolTip() or text_item.text()
            try:
                import pyperclip
                pyperclip.copy(full_text)
                QToolTip.showText(QCursor.pos(), "Скопировано", self.history_table)
            except ImportError:
                pass

    def _copy_history_on_double_click(self, row: int, column: int):
        self.history_table.selectRow(row)
        self._copy_history_entry()

    def _export_history(self):
        if not self.history_manager:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Экспорт истории", "", "Text Files (*.txt)"
        )
        if not filepath:
            return
        entries = self.history_manager.get_history()
        with open(filepath, "w", encoding="utf-8") as f:
            for i, e in enumerate(entries, 1):
                f.write(f"[{i}] {e.timestamp} | {e.backend} | {e.word_count} слов\n")
                f.write(f"{e.text}\n\n")

    def _clear_history(self):
        if self.history_manager:
            self.history_manager.clear_history()
            self._update_history_display()

    def update_stats_display(self):
        if self.config:
            self.stats_words.setText(f"Слов: {self.config.total_words:,}")
            self.stats_recordings.setText(f"Всего записей (за время использования): {self.config.total_recordings:,}")
            self.stats_saved.setText(f"Время: {self.config.total_seconds_saved/60:.1f} мин")

    def _reset_vad_defaults(self):
        self.vad_threshold_slider.setValue(50)
        self.min_silence_slider.setValue(800)

    def _noise_level_changed(self, value: int):
        labels = ["Выкл", "Слабо", "Умеренно", "Сильно", "Очень сильно"]
        self.noise_level_value.setText(labels[value] if 0 <= value < len(labels) else "Умеренно")

    def _reset_noise_defaults(self):
        self.webrtc_enabled_cb.setChecked(True)
        self.noise_level_slider.setValue(2)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_position:
            self.move(event.globalPosition().toPoint() - self._drag_position)
