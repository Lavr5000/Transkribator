#!/usr/bin/env python3
"""
Transcriber wrapper for Transcriber Server.
Simplified version that uses Whisper backend (more reliable).
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from transcriber import Transcriber

# Use Whisper backend (more reliable than Sherpa)
# If you want Sherpa, change backend="sherpa" and model_size="giga-am-v2-ru"
transcriber = Transcriber(
    backend="whisper",  # Changed from "sherpa" to "whisper"
    model_size="base",  # Changed from "giga-am-v2-ru" to "base"
    device="cpu",
    language="ru",  # Russian language
    enable_post_processing=True
)

print("Transcriber initialized successfully")
print(f"Backend: {transcriber.backend}")
print(f"Model: {transcriber.model_size}")
