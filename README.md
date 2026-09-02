<p align="center">
  <img src="Transkribator_Icon.png" alt="Transkribator" width="120">
</p>

<h1 align="center">Transkribator</h1>

<p align="center">
  <b>Voice-to-text for your desktop. Speak — it types.</b><br>
  Offline · Free · Russian-first · Windows
</p>

<p align="center">
  <a href="https://github.com/Lavr5000/Transkribator/releases/latest">
    <img src="https://img.shields.io/github/v/release/Lavr5000/Transkribator?style=for-the-badge&label=Download&color=blue" alt="Download">
  </a>
  <a href="https://t.me/ai_vibes_coding_ru">
    <img src="https://img.shields.io/badge/Telegram-AI_Vibes-blue?style=for-the-badge&logo=telegram" alt="Telegram">
  </a>
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="License">
</p>

---

## По-русски

**Что это.** Транскрибатор превращает речь в текст и вставляет его в то окно, где
стоит курсор. Нажали `Ctrl+Shift+Space` (или среднюю кнопку мыши), сказали, нажали
ещё раз — текст на месте. Всё считается на вашем компьютере: интернет не нужен,
аккаунт не нужен, ключей и подписок нет.

**Установка (Windows 10/11).**

1. Скачайте ZIP со страницы [релизов](https://github.com/Lavr5000/Transkribator/releases/latest).
2. Распакуйте в любую папку.
3. Запустите `Transkribator.exe`.

При первом запуске Windows покажет синее окно SmartScreen — программа не подписана
сертификатом (это платно, у проекта его нет). Нажмите **«Подробнее» → «Выполнить в
любом случае»**. Скачивайте только со страницы релизов выше.

Первое окно попросит выбрать микрофон и предложит пробу на 3 секунды: скажите
что-нибудь и убедитесь, что появился текст и уровень сигнала. Если написано
«Сигнала нет» — выбран не тот микрофон.

**Требования.** Windows 10 или 11, 64 бита. Место на диске: ~390 МБ распакованной
папки (из них 215 МБ — сама модель распознавания, она лежит внутри и ничего не
докачивает). Оперативная память: см. таблицу System Requirements ниже. Видеокарта
не нужна — всё считается на процессоре. Интернет не нужен вообще.

**Честно о качестве.** Насколько хорошо распознаётся именно ваша речь, зависит от
микрофона, шума в комнате и мощности машины — универсального ответа нет, проверьте
пробой на 3 секунды. Часть параметров (чувствительность к тишине, словарь ваших
терминов, профиль качества) настраивается прямо в приложении. Код открыт: если
чего-то не хватает — попросите ИИ-агента, например Claude Code, доработать
программу под себя.

---

## What it does

Transkribator turns your voice into text and pastes it directly into any active window. Press a hotkey, speak, release — done. No cloud, no API keys, no limits. Everything runs locally on your machine.

## Features

- **Instant voice input** — press `Ctrl+Shift+Space`, speak, text appears where your cursor is
- **100% offline** — your voice never leaves your computer
- **Russian-first** — powered by Sherpa-ONNX with the `giga-am-v3-ru-punct` model, optimized for Russian speech
- **Smart post-processing** — automatic capitalization, punctuation, and correction of common recognition errors
- **Custom dictionary** — add your own words and corrections
- **Compact UI** — tiny always-on-top window that stays out of your way
- **System tray** — minimizes to tray, launches at startup

## Download

### Ready-to-use EXE (Windows)

Go to [**Releases**](https://github.com/Lavr5000/Transkribator/releases/latest), download the ZIP archive, extract, and run `Transkribator.exe`. No installation or Python required.

### From source

```bash
git clone https://github.com/Lavr5000/Transkribator.git
cd Transkribator
python -m venv venv
venv\Scripts\activate
pip install ".[nlp]"
python main.py
```

Optional extra: `.[nlp]` adds the pymorphy3 dictionaries used for Russian morphology corrections. There is one engine — Sherpa-ONNX, running locally.

## Usage

1. Launch `Transkribator.exe` (or `python main.py`)
2. Click the microphone button or press `Ctrl+Shift+Space`
3. Speak
4. Press the hotkey again — text is pasted into the active window

### Settings

- **Quality profile**: Fast / Balanced / Quality
- **Language**: Russian (default)
- **Custom dictionary**: Add corrections for domain-specific terms

## System Requirements

| | Minimum | Recommended |
|---|---------|-------------|
| **OS** | Windows 10 | Windows 11 |
| **RAM** | 4 GB | 8 GB |
| **Disk** | 500 MB | 1 GB |
| **Python** | 3.10+ (from source only) | 3.13 |

GPU is optional — Sherpa-ONNX runs efficiently on CPU.

## Tech Stack

- **Speech recognition**: [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx) with GigaAM v3 (`giga-am-v3-ru-punct`)
- **GUI**: PyQt6
- **Hotkeys**: pynput
- **Audio**: sounddevice + numpy
- **Build**: PyInstaller

## Crash Reporting & Watchdog

Transkribator includes a built-in crash reporting system:

- **Automatic crash reports** — on unhandled exceptions, a JSON report is saved to `%LOCALAPPDATA%/WhisperTyping/WhisperTyping/crashes/` with exception details, system info, and recent log lines
- **C-level fault handler** — catches segfaults and fatal errors via Python's `faulthandler` module
- **Watchdog** — `scripts/watchdog.py` runs the app as a subprocess, auto-restarts on crash (max 3 restarts in 5 minutes)

### Running with watchdog

```bash
python scripts/watchdog.py
```

## License

MIT — free for personal and commercial use.

## Links

- [Portfolio: AI Vibes](https://ai-vibes.ru) — all projects
- [Telegram: AI Vibes](https://t.me/ai_vibes_coding_ru) — updates and discussion
- [YouTube](https://www.youtube.com/@Lavr5000) — demos and tutorials
- [Releases](https://github.com/Lavr5000/Transkribator/releases) — download latest version
