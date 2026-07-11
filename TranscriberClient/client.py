"""CLI client for remote audio transcription with auto-detection of connection method."""
import ipaddress
import os
import requests
import sys
import socket
import time
from pathlib import Path
from urllib.parse import urlparse
from tqdm import tqdm
from typing import List, Optional

# Server list comes from the environment — no endpoints are hardcoded:
#   set TRANSKRIBATOR_SERVERS=http://100.x.y.z:8000,http://192.168.1.10:8000
# Plain HTTP exposes the API key and your audio to anything on the path, so
# http:// is only accepted for loopback / RFC1918 LAN / Tailscale (100.64/10)
# hosts. Anything else needs TRANSKRIBATOR_ALLOW_INSECURE=1 (not recommended).
API_KEY = os.environ.get("TRANSCRIBER_API_KEY", "")


def _host_is_private(host: str) -> bool:
    """True when every resolved address of host is loopback/LAN/Tailscale."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False  # unresolvable — treat as insecure
    addrs = {info[4][0] for info in infos}
    if not addrs:
        return False
    for addr in addrs:
        ip = ipaddress.ip_address(addr)
        if not (ip.is_loopback or ip.is_private or ip in ipaddress.ip_network("100.64.0.0/10")):
            return False
    return True


def get_servers() -> List[str]:
    """Read and validate server URLs from TRANSKRIBATOR_SERVERS."""
    raw = os.environ.get("TRANSKRIBATOR_SERVERS", "")
    if not raw.strip():
        print("✗ Не задан TRANSKRIBATOR_SERVERS.")
        print("  Пример: set TRANSKRIBATOR_SERVERS=http://100.x.y.z:8000")
        return []
    allow_insecure = os.environ.get("TRANSKRIBATOR_ALLOW_INSECURE") == "1"
    servers = []
    for url in (u.strip().rstrip("/") for u in raw.split(",") if u.strip()):
        parsed = urlparse(url)
        if parsed.scheme == "http" and not allow_insecure and not _host_is_private(parsed.hostname or ""):
            print(f"✗ Отклонён небезопасный адрес: {url}")
            print("  http:// разрешён только для loopback/LAN/Tailscale-адресов.")
            print("  Для остальных используйте https:// или TRANSKRIBATOR_ALLOW_INSECURE=1.")
            continue
        servers.append(url)
    return servers


def _headers() -> dict:
    return {"X-API-Key": API_KEY} if API_KEY else {}


def find_available_server() -> Optional[str]:
    """Find first available server."""
    for server_url in get_servers():
        try:
            response = requests.get(f"{server_url}/health", timeout=3)
            if response.status_code == 200:
                return server_url
        except requests.exceptions.RequestException:
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
        print("  2. Сервер запущен (python server.py)")
        print("  3. TRANSKRIBATOR_SERVERS указывает на правильный адрес")
        return ""

    print(f"✓ Сервер найден: {server_url}")

    # Step 1: Upload file
    print(f"\n[1/3] Загрузка файла: {file_path.name}")
    print(f"      Размер: {file_path.stat().st_size / 1024 / 1024:.2f} MB")

    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{server_url}/transcribe",
                files={"file": f},
                headers=_headers(),
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
                status_response = requests.get(f"{server_url}/status/{task_id}", headers=_headers(), timeout=10)
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
        result_response = requests.get(f"{server_url}/result/{task_id}", headers=_headers(), timeout=30)
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
            print(f"✓ Сервер доступен: {server_url}")
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
