from __future__ import annotations
import subprocess
from pathlib import Path
from typing import List, Tuple

def run(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True)

def make_scene_mp4(img_png: Path, audio_mp3: Path | None, duration: float, out_mp4: Path) -> None:
    # 무음 scene이면 duration으로만 생성
    if audio_mp3 is None or not audio_mp3.exists():
        run([
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_png),
            "-t", f"{duration:.2f}",
            "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(out_mp4)
        ])
        return

    # 오디오가 있으면 오디오 길이를 기준으로(초과 방지 위해 -shortest)
    run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img_png),
        "-i", str(audio_mp3),
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(out_mp4)
    ])

def concat_mp4(parts: List[Path], out_mp4: Path) -> None:
    # concat demuxer
    lst = out_mp4.with_suffix(".txt")
    lst.write_text("\n".join([f"file '{p.as_posix()}'" for p in parts]), encoding="utf-8")

    run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(lst),
        "-c", "copy",
        str(out_mp4)
    ])
    lst.unlink(missing_ok=True)
