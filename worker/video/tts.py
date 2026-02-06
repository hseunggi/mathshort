from __future__ import annotations
from pathlib import Path
from openai import OpenAI

client = OpenAI()

def make_tts_mp3(text: str, out_mp3: Path, voice: str = "alloy") -> None:
    if not text.strip():
        # 무음이면 파일 만들지 않음
        return
    # OpenAI TTS
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text
    ) as resp:
        resp.stream_to_file(out_mp3)
