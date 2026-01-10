"""Download script for speech recognition models.

This script helps download models for different backends:
- Whisper models (base, small, medium)
- Sherpa-ONNX models (GigaAM v2 Russian)
"""
import argparse
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.backends.sherpa_backend import SherpaBackend


def download_sherpa_model(model_name: str, target_dir: Path = None):
    """Download Sherpa-ONNX model from HuggingFace.

    Args:
        model_name: Model identifier (giga-am-v2-ru, giga-am-ru)
        target_dir: Target directory (optional)
    """
    print(f"[INFO] Downloading Sherpa-ONNX model: {model_name}")
    print(f"[INFO] Target directory: {target_dir or 'default'}")

    try:
        model_path = SherpaBackend.download_model(model_name, target_dir)
        print(f"[SUCCESS] Model downloaded successfully to: {model_path}")
        return model_path
    except Exception as e:
        print(f"[ERROR] Failed to download model: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Download speech recognition models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download GigaAM v2 Russian model
  python scripts/download_models.py --backend sherpa --model giga-am-v2-ru

  # Download GigaAM v1 Russian model
  python scripts/download_models.py --backend sherpa --model giga-am-ru

  # List available Sherpa models
  python scripts/download_models.py --list-sherpa
        """
    )

    parser.add_argument(
        "--backend",
        choices=["sherpa", "whisper"],
        default="sherpa",
        help="Backend to download model for"
    )

    parser.add_argument(
        "--model",
        type=str,
        help="Model name/size (e.g., giga-am-v2-ru, base, small)"
    )

    parser.add_argument(
        "--target-dir",
        type=Path,
        help="Target directory for model files"
    )

    parser.add_argument(
        "--list-sherpa",
        action="store_true",
        help="List available Sherpa-ONNX models"
    )

    args = parser.parse_args()

    # List available models
    if args.list_sherpa:
        print("[INFO] Available Sherpa-ONNX models:")
        models = SherpaBackend.get_available_models()
        for name, info in models.items():
            print(f"\n  {name}")
            print(f"    Name: {info['name']}")
            print(f"    Language: {info['language']}")
            print(f"    URL: {info['url']}")
        return

    # Download model
    if not args.model:
        parser.error("--model is required unless --list-sherpa is used")

    if args.backend == "sherpa":
        download_sherpa_model(args.model, args.target_dir)
    elif args.backend == "whisper":
        print("[INFO] Whisper models are auto-downloaded on first use by faster-whisper")
        print("[INFO] No manual download needed.")


if __name__ == "__main__":
    main()
