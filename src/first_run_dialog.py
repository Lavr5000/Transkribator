"""First-run dialog: pick a microphone, prove it works, done.

The whole "self-setup on a stranger's Windows" is this window. It replaces a
tooltip that told the user the hotkey and nothing else — which is useless if
the default input device is the wrong one, and there was no way to find out
except dictating into the void.

The 3-second test runs through the SAME recorder and the same transcription
worker the app uses: no second capture stream (the persistent stream would
fight it), and nothing blocking on the Qt thread.
"""

import logging
import threading
import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QVBoxLayout,
)

logger = logging.getLogger("transkribator")

PROBE_SECONDS = 3.0
SILENCE_DBFS = -60.0   # below this the microphone is not hearing anything


class FirstRunDialog(QDialog):
    """Device picker + a 3 s microphone test. Also reachable from Settings."""

    _probe_done = pyqtSignal(float, str, str)   # peak_dbfs, text, error

    def __init__(self, config, recorder, transcribe_fn, parent=None):
        super().__init__(parent)
        self.config = config
        self.recorder = recorder
        self.transcribe_fn = transcribe_fn
        self._cancelled = False
        self._probing = False

        self.setWindowTitle("Transkribator — проверка микрофона")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Выберите микрофон и проверьте, что он слышит.</b>"))

        self.device_combo = QComboBox()
        self.device_combo.addItem("Системный по умолчанию", ("", ""))
        for _idx, name, api in self.recorder.list_input_devices():
            self.device_combo.addItem(f"{api} · {name}", (name, api))
        self._select_configured_device()
        layout.addWidget(self.device_combo)

        buttons = QHBoxLayout()
        self.test_btn = QPushButton(f"Проба {int(PROBE_SECONDS)} с")
        self.test_btn.clicked.connect(self._start_probe)
        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.clicked.connect(self._cancel_probe)
        self.cancel_btn.setEnabled(False)
        buttons.addWidget(self.test_btn)
        buttons.addWidget(self.cancel_btn)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)          # busy indicator
        self.progress.hide()
        layout.addWidget(self.progress)

        self.result_label = QLabel("Нажмите «Проба» и говорите — здесь появится текст.")
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.result_label)

        hotkey = (self.config.hotkey or "ctrl+shift+space").replace("+", "+").upper()
        layout.addWidget(QLabel(f"Горячая клавиша: {hotkey} (средняя кнопка мыши)"))

        self.done_btn = QPushButton("Готово")
        self.done_btn.clicked.connect(self._finish)
        layout.addWidget(self.done_btn)

        self._probe_done.connect(self._on_probe_done)

    # ---------------------------------------------------------------- #

    def _select_configured_device(self):
        want = (self.config.audio_device_name or "", self.config.audio_hostapi or "")
        if not want[0]:
            return
        for i in range(self.device_combo.count()):
            name, api = self.device_combo.itemData(i)
            if name == want[0] and api.lower() == want[1].lower():
                self.device_combo.setCurrentIndex(i)
                return

    def _set_busy(self, busy: bool):
        self._probing = busy
        self.test_btn.setEnabled(not busy)
        self.device_combo.setEnabled(not busy)
        self.done_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(busy)
        self.progress.setVisible(busy)

    def _start_probe(self):
        if self._probing:
            return
        self._cancelled = False
        self._set_busy(True)
        self.result_label.setText("Говорите…")
        name, api = self.device_combo.currentData()
        threading.Thread(target=self._probe_worker, args=(name, api),
                         daemon=True, name="mic-probe").start()

    def _cancel_probe(self):
        """Cancel leaves the recorder idle — never half-recording."""
        self._cancelled = True
        self.cancel_btn.setEnabled(False)
        self.result_label.setText("Отменяю…")

    def _probe_worker(self, name, api):
        peak, text, error = -120.0, "", ""
        try:
            current = (self.recorder.device_name or "", self.recorder.device_hostapi or "")
            if (name, api.lower() if api else "") != (current[0], current[1].lower()):
                if not self.recorder.switch_device(name, api):
                    raise RuntimeError("не удалось открыть выбранный микрофон")
            elif not self.recorder.stream_alive():
                self.recorder.open_stream()

            if self._cancelled:
                return
            if self.recorder.start() != "started":
                raise RuntimeError("микрофон ещё готовится, повторите через секунду")

            deadline = time.monotonic() + PROBE_SECONDS
            while time.monotonic() < deadline and not self._cancelled:
                time.sleep(0.05)
            audio = self.recorder.stop()

            if self._cancelled:
                return
            if audio is None or not len(audio):
                raise RuntimeError("запись не получилась — кадры не пришли")

            peak = self.recorder.last_peak_dbfs
            if peak > SILENCE_DBFS:
                text = self.transcribe_fn(audio) or ""
        except Exception as e:
            logger.warning("FIRST_RUN_PROBE_FAILED | %s: %s", type(e).__name__, e)
            error = str(e)
        finally:
            self._probe_done.emit(peak, text, error)

    def _on_probe_done(self, peak, text, error):
        self._set_busy(False)
        if self._cancelled:
            self.result_label.setText("Проба отменена.")
        elif error:
            self.result_label.setText(f"<span style='color:#c0392b'>Ошибка: {error}</span>")
        elif peak <= SILENCE_DBFS:
            self.result_label.setText(
                f"<b>Сигнала нет</b> (пик {peak:.0f} dBFS). Проверьте, тот ли микрофон "
                "выбран и не выключен ли он в системе.")
        else:
            shown = text.strip() or "(речь не распознана — попробуйте говорить громче)"
            self.result_label.setText(f"Пик {peak:.0f} dBFS. Распознано: <b>{shown}</b>")

    def _finish(self):
        name, api = self.device_combo.currentData()
        self.config.audio_device_name = name
        self.config.audio_hostapi = api
        self.config.audio_device_legacy_index = -1
        self.config.first_run = False
        self.config.save()
        self.accept()
