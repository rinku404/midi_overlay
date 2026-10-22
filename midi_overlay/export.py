"""Turns rendered frames into a video file by piping raw RGBA frames into ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

# format -> (file extension, ffmpeg output arguments, keeps transparency)
FORMATS = {
    # ProRes 4444 with alpha: imports cleanly into DaVinci Resolve, Premiere, Vegas, Final Cut
    "mov": (".mov", ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                     "-vendor", "apl0"], True),
    # VP9 with alpha: much smaller files; works in Resolve, Shotcut, Kdenlive, OBS, browsers
    "webm": (".webm", ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "28",
                       "-auto-alt-ref", "0", "-row-mt", "1"], True),
    # Opaque H.264 over a solid colour, for editors without alpha support (key it out)
    "mp4": (".mp4", ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "medium"], False),
    # One transparent PNG per frame
    "png": ("", [], True),
}


def find_ffmpeg(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # optional: ships its own ffmpeg binary, handy on Windows
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    raise RuntimeError("ffmpeg not found. Install it (winget install ffmpeg) or run: pip install imageio-ffmpeg")


def _progress(done: int, total: int, started: float):
    elapsed = time.time() - started
    rate = done / elapsed if elapsed else 0
    remaining = (total - done) / rate if rate else 0
    sys.stderr.write(f"\r  frame {done}/{total}  {100 * done / total:5.1f}%  "
                     f"{rate:5.1f} fps  ~{remaining:4.0f}s left ")
    sys.stderr.flush()


def render_video(layout, out: Path, fmt: str, fps: float, start: float, duration: float,
                 offset: float = 0.0, background: str = "#00FF00", ffmpeg: str | None = None):
    """Renders `duration` seconds of output video. Output time T shows MIDI time T + start - offset."""
    ext, codec_args, alpha = FORMATS[fmt]
    total = max(1, round(duration * fps))
    width, height = layout.width, layout.height
    bg = None if alpha else Image.new("RGBA", (width, height), background)

    def frame(i: int) -> Image.Image:
        img = layout.render(start + i / fps - offset)
        if bg is not None:
            img = Image.alpha_composite(bg, img)
        return img

    started = time.time()
    if fmt == "png":
        out.mkdir(parents=True, exist_ok=True)
        digits = len(str(total))
        for i in range(total):
            frame(i).save(out / f"frame_{i:0{digits}d}.png", compress_level=1)
            if i % 10 == 0 or i == total - 1:
                _progress(i + 1, total, started)
        sys.stderr.write("\n")
        return

    if out.suffix.lower() != ext:
        out = out.with_suffix(ext)
    cmd = [find_ffmpeg(ffmpeg), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{width}x{height}", "-r", str(fps), "-i", "-",
           *codec_args, str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(total):
            proc.stdin.write(frame(i).tobytes())
            if i % 10 == 0 or i == total - 1:
                _progress(i + 1, total, started)
    except BrokenPipeError:
        pass
    finally:
        proc.stdin.close()
        code = proc.wait()
    sys.stderr.write("\n")
    if code != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {code}")
    return out
