"""CLI client for remote audio transcription with auto-detection of connection method."""
import requests
import sys
import socket
import time
from pathlib import Path
from tqdm import tqdm
from typing import Optional

# Try local first (VPN disabled), then remote (VPN enabled or no local access)
SERVERS = [
    "http://192.168.31.9:8000",  # Local network (VPN disabled)
    "http://elated-dhawan-remote.serveo.net:8000"  # Through serveo.net
]


def find_available_server() -> Optional[str]:
    """Find first available server."""
    for server_url in SERVERS:
        try:
            response = requests.get(f"{server_url}/health", timeout=3)
            if response.status_code == 200:
                return server_url
        except:
            continue
    return None


def transcribe_file(file_path: Path) -> str:
    """
    Upload audio file to remote server, wait for transcription, download result.

    Args:
        file_path: Path to audio file

    Returns:
        Transcribed text
    """
    # Find available server
    print("🔍 Поиск сервера...")
    server_url = find_available_server()

    if not server_url:
        print("✗ Сервер недоступен!")
        print("\nПроверьте что:")
        print("  1. Удаленный ПК включён")
        print("  2. Сервер запущен (AUTOSTART_FINAL.bat)")
        print("  3. VPN выключен или включен (оба режима работают)")
        return ""

    # Determine connection type
    if server_url == SERVERS[0]:
        connection_type = "🏠 Локальная сеть (VPN выключен)"
    else:
        connection_type = "🌐 Через интернет (serveo.net)"

    print(f"✓ Сервер найден: {connection_type}")

    # Step 1: Upload file
    print(f"\n[1/3] Загрузка файла: {file_path.name}")
    print(f"      Размер: {file_path.stat().st_size / 1024 / 1024:.2f} MB")

    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{server_url}/transcribe",
                files={"file": f},
                timeout=60
            )
    except requests.exceptions.RequestException as e:
        print(f"      ✗ Ошибка соединения: {e}")
        return ""

    if response.status_code != 200:
        print(f"      ✗ Ошибка загрузки: {response.status_code}")
        print(f"      {response.text}")
        return ""

    task_id = response.json()["task_id"]
    print(f"      ✓ Task ID: {task_id}")
    print(f"      Файл: {response.json()['filename']}")

    # Step 2: Wait for completion
    print(f"\n[2/3] Транскрибация...")

    start_time = time.time()
    check_interval = 2  # seconds

    with tqdm(desc="Прогресс", unit="сек") as pbar:
        while True:
            try:
                status_response = requests.get(f"{server_url}/status/{task_id}", timeout=10)
                status = status_response.json()
            except requests.exceptions.RequestException as e:
                pbar.close()
                print(f"\n      ✗ Ошибка проверки статуса: {e}")
                return ""

            if status["status"] == "completed":
                elapsed = time.time() - start_time
                pbar.close()
                print(f"      ✓ Готово! (за {elapsed:.1f} сек)")
                break
            elif status["status"] == "failed":
                pbar.close()
                print(f"      ✗ Ошибка транскрибации")
                print(f"      {status.get('error', 'Unknown error')}")
                return ""

            time.sleep(check_interval)
            pbar.update(check_interval)

    # Step 3: Download result
    print(f"\n[3/3] Получение результата...")

    try:
        result_response = requests.get(f"{server_url}/result/{task_id}", timeout=30)
        if result_response.status_code != 200:
            print(f"      ✗ Ошибка загрузки результата: {result_response.status_code}")
            return ""
    except requests.exceptions.RequestException as e:
        print(f"      ✗ Ошибка соединения: {e}")
        return ""

    text = result_response.text

    # Save to file
    downloads_dir = Path.cwd() / "downloads"
    downloads_dir.mkdir(exist_ok=True)

    output_path = downloads_dir / f"{file_path.stem}.txt"
    output_path.write_text(text, encoding="utf-8")

    print(f"      ✓ Сохранено: {output_path}")

    return text


def check_server_health() -> bool:
    """
    Check if remote server is accessible.

    Returns:
        True if server is healthy
    """
    print("🔍 Проверка состояния сервера...")

    server_url = find_available_server()

    if not server_url:
        print("✗ Сервер недоступен")
        print("\nВозможные причины:")
        print("  • Удаленный ПК выключен")
        print("  • Сервер не запущен")
        print("  • Проблемы с сетью")
        return False

    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()

            # Determine connection type
            if server_url == SERVERS[0]:
                connection = "🏠 Локальная сеть"
            else:
                connection = "🌐 Через интернет (serveo.net)"

            print(f"✓ Сервер доступен: {connection}")
            print(f"  Статус: {data['status']}")
            print(f"  Модель: {data.get('model', 'base')}")
            return True
        else:
            print(f"✗ Сервер вернул ошибку: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Не удалось подключиться: {e}")
        return False


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("🎙️  Remote Transcriber Client")
        print("\nИспользование:")
        print("  python client.py <audio_file>          # Транскрибировать файл")
        print("  python client.py --health              # Проверить состояние сервера")
        print("  python client.py --help                # Показать справку")
        sys.exit(1)

    # Parse arguments
    if sys.argv[1] == "--health":
        check_server_health()
        sys.exit(0)

    elif sys.argv[1] == "--help":
        print("🎙️  Remote Transcriber Client")
        print("\nИспользование:")
        print("  python client.py <audio_file>          # Транскрибировать файл")
        print("  python client.py --health              # Проверить состояние сервера")
        print("\nПоддерживаемые форматы:")
        print("  .mp3, .wav, .m4a, .ogg, .flac")
        print("\nПодключение:")
        print("  • Автоматически определяет VPN статус")
        print("  • Работает при включённом и выключенном VPN")
        sys.exit(0)

    # Transcribe file
    file_path = Path(sys.argv[1])

    if not file_path.exists():
        print(f"✗ Файл не найден: {file_path}")
        sys.exit(1)

    # Check if it's an audio file
    audio_extensions = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".wma"}
    if file_path.suffix.lower() not in audio_extensions:
        print(f"⚠ Предупреждение: {file_path.suffix} может не поддерживаться")
        print(f"  Рекомендуемые форматы: {', '.join(audio_extensions)}")

    print("\n" + "="*50)
    print("🎙️  REMOTE TRANSCRIBER")
    print("="*50 + "\n")

    text = transcribe_file(file_path)

    if text:
        print("\n" + "="*50)
        print("📝 РЕЗУЛЬТАТ ТРАНСКРИБАЦИИ")
        print("="*50 + "\n")
        print(text)
        print("\n" + "="*50)

        # Word count
        words = len(text.split())
        chars = len(text)
        print(f"\n📊 Статистика: {words} слов, {chars} символов")
        print(f"📁 Файл сохранён: downloads/{file_path.stem}.txt")
    else:
        print("\n✗ Не удалось выполнить транскрибацию")
        sys.exit(1)


if __name__ == "__main__":
    main()
