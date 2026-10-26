#!/usr/bin/env python3
"""talkicut: give a silent screen recording a voice, then cut it into vertical clips.

Named after the moment cinema stopped being silent. A screen recording with no
audio is the modern silent film: no transcript, nothing for an AI clipper to
grab. talkicut reads the recording, writes the narration, speaks it, and burns
word-synced captions into a 9:16 clip.

Commands (all offline-safe, all cross-platform):

  doctor    check ffmpeg, fonts, TTS engines; --fix installs edge-tts
  probe     inspect a video: duration, resolution, audio, scene cuts
  plan      scaffold plan.json from probe + beat detection
  sheet     timestamped contact sheets so a human or a vision model can read the flow
  ocr       sample frames and OCR them (for agents/models without vision)
  render    turn a plan.json into finished clips
  verify    check a folder of rendered clips for the usual silent failures
  selftest  generate a synthetic video and render it end to end (no user files needed)

Design rules this script follows, because the skill must work on any machine:
  * never assume a tool exists - detect it, degrade, and say what to install
  * never assume vision - ocr and probe give a text-only path
  * never assume network - system TTS backends work offline
  * never assume Windows - every OS-specific bit is isolated in one function
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

VERSION = "3.3.0"
TOOL = "talkicut"
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

# lang -> good default edge voice (neural, no API key, free)
EDGE_VOICES = {
    "es": "es-AR-TomasNeural",
    "es-ar": "es-AR-TomasNeural",
    "es-mx": "es-MX-JorgeNeural",
    "es-es": "es-ES-AlvaroNeural",
    "en": "en-US-AndrewNeural",
    "en-us": "en-US-AndrewNeural",
    "en-gb": "en-GB-RyanNeural",
    "pt": "pt-BR-AntonioNeural",
    "pt-br": "pt-BR-AntonioNeural",
    "fr": "fr-FR-RemyMultilingualNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
    "ja": "ja-JP-KeitaNeural",
    "hi": "hi-IN-MadhurNeural",
}

# espeak-ng language codes for offline fallback
ESPEAK_LANGS = {"es": "es", "en": "en-us", "pt": "pt-br", "fr": "fr", "de": "de", "it": "it", "ja": "ja", "hi": "hi"}

FFMPEG = os.environ.get("FFMPEG") or shutil.which("ffmpeg") or ""
FFPROBE = os.environ.get("FFPROBE") or shutil.which("ffprobe") or ""


# ----------------------------------------------------------------------------- shell


def run(cmd, cwd=None, timeout=None, check=False):
    """Run a command, never raise on a non-zero exit. Returns (code, stdout, stderr)."""
    if not cmd or not cmd[0]:
        return 127, "", "no executable given"
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s: {cmd[0]}"
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:2000])
    return p.returncode, p.stdout, p.stderr


def ffmpeg_filters():
    """Filter names this ffmpeg build actually has. Cached per process.

    The -filters table is `flags name  in->out  description`, where flags are
    two or three characters (TSC / T. / ..) - parsing by token position rather
    than a fixed width survives every ffmpeg version seen so far.
    """
    global _FILTERS
    if _FILTERS is None:
        code, out, _ = run([FFMPEG, "-hide_banner", "-filters"])
        names = set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and "->" in line and re.fullmatch(r"[A-Z.]{1,3}", parts[0]):
                names.add(parts[1])
        _FILTERS = names
    return _FILTERS


_FILTERS = None


def has_filter(name):
    return name in ffmpeg_filters()


def probe_media(path):
    """Structured media info. Works for audio-only files too."""
    code, out, err = run([FFPROBE, "-v", "error", "-print_format", "json",
                          "-show_format", "-show_streams", str(path)])
    if code != 0:
        raise SystemExit(f"ffprobe failed on {path}: {err.strip()[:300]}")
    data = json.loads(out or "{}")
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float(data.get("format", {}).get("duration") or 0)
    fps = 0.0
    if video and video.get("r_frame_rate", "0/0") not in ("0/0", ""):
        num, _, den = video["r_frame_rate"].partition("/")
        try:
            fps = round(float(num) / float(den or 1), 3)
        except ZeroDivisionError:
            fps = 0.0
    return {
        "path": str(Path(path).resolve()),
        "duration": round(dur, 3),
        "width": int(video["width"]) if video else 0,
        "height": int(video["height"]) if video else 0,
        "fps": fps,
        "video_codec": video.get("codec_name") if video else None,
        "has_audio": bool(audio),
        "audio_codec": audio.get("codec_name") if audio else None,
        "audio_channels": int(audio.get("channels") or 0) if audio else 0,
        "sample_rate": int(audio.get("sample_rate") or 0) if audio else 0,
    }


def duration_of(path):
    code, out, _ = run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)])
    try:
        return float(out.strip())
    except ValueError:
        return 0.0


# ------------------------------------------------------------------------------ tts


class TtsUnavailable(RuntimeError):
    pass


@dataclass
class Speech:
    audio: Path
    duration: float
    words: list = field(default_factory=list)   # [(offset, duration, text)]
    engine: str = "none"
    rate: int = 0


def cache_dir():
    env = os.environ.get("TALKICUT_CACHE")
    if env:
        return Path(env).expanduser()
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif IS_MAC:
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "talkicut"


def edge_available():
    try:
        import edge_tts  # noqa: F401
        return True
    except Exception:
        return False


def edge_speak(text, voice, rate_pct, out_dir: Path, tag: str) -> Speech:
    import asyncio

    import edge_tts

    mp3 = out_dir / f"{tag}.mp3"
    words = []

    async def go():
        comm = edge_tts.Communicate(text, voice, rate=f"{rate_pct:+d}%", boundary="WordBoundary")
        with open(mp3, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                    words.append((chunk["offset"] / 1e7, chunk["duration"] / 1e7, chunk["text"]))

    try:
        asyncio.run(go())
    except Exception as exc:  # network down, voice gone, service change...
        raise TtsUnavailable(f"edge-tts failed: {exc}") from exc
    if not mp3.exists() or mp3.stat().st_size == 0:
        raise TtsUnavailable("edge-tts produced no audio")
    return Speech(mp3, duration_of(mp3), words, "edge", rate_pct)


def system_tts_available():
    if IS_WIN:
        return bool(shutil.which("powershell") or shutil.which("pwsh"))
    if IS_MAC:
        return bool(shutil.which("say"))
    return bool(shutil.which("espeak-ng") or shutil.which("espeak"))


def system_speak(text, voice, lang, out_dir: Path, tag: str) -> Speech:
    """Offline fallback. No word timings, so captions get proportional timing."""
    txt = out_dir / f"{tag}.txt"
    txt.write_text(text, encoding="utf-8")

    if IS_WIN:
        exe = shutil.which("powershell") or shutil.which("pwsh")
        if not exe:
            raise TtsUnavailable("PowerShell not found")
        out = out_dir / f"{tag}.wav"
        select = f"$s.SelectVoice('{voice}');" if voice else ""
        # text via file: no quoting/escaping bugs with quotes or unicode in the script
        ps = ("Add-Type -AssemblyName System.Speech;"
              f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;{select}"
              f"$s.SetOutputToWaveFile('{out}');"
              f"$t = Get-Content -Raw -Encoding UTF8 '{txt}';"
              "$s.Speak($t); $s.Dispose()")
        code, _, err = run([exe, "-NoProfile", "-NonInteractive", "-Command", ps], timeout=600)
        if code != 0 or not out.exists():
            raise TtsUnavailable(f"System.Speech failed: {err.strip()[:300]}")
        return Speech(out, duration_of(out), [], "system-windows")

    if IS_MAC:
        out = out_dir / f"{tag}.aiff"
        cmd = ["say", "-f", str(txt), "-o", str(out)]
        if voice:
            cmd += ["-v", voice]
        code, _, err = run(cmd, timeout=600)
        if code != 0 or not out.exists():
            raise TtsUnavailable(f"say failed: {err.strip()[:300]}")
        return Speech(out, duration_of(out), [], "system-macos")

    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise TtsUnavailable("espeak-ng not installed (sudo apt install espeak-ng)")
    out = out_dir / f"{tag}.wav"
    code, _, err = run([exe, "-f", str(txt), "-w", str(out), "-v", ESPEAK_LANGS.get(lang, lang)],
                       timeout=600)
    if code != 0 or not out.exists():
        raise TtsUnavailable(f"espeak failed: {err.strip()[:300]}")
    return Speech(out, duration_of(out), [], "system-espeak")


def make_speech(text, engine, voice, lang, clip_dur, out_dir: Path, tag: str) -> Speech:
    """Synth speech, shrinking it to fit the clip. Cache by content so reruns are fast."""
    key = hashlib.sha1(f"{engine}|{voice}|{lang}|{text}".encode("utf-8")).hexdigest()[:16]
    cache = cache_dir() / "tts" / key

    if cache.with_suffix(".json").exists():
        meta = json.loads(cache.with_suffix(".json").read_text(encoding="utf-8"))
        audio = cache.with_suffix(meta["ext"])
        if audio.exists():
            return Speech(audio, meta["duration"], [tuple(w) for w in meta["words"]],
                          meta["engine"], meta.get("rate", 0))

    attempts = []
    if engine in ("auto", "edge"):
        attempts.append("edge")
    if engine in ("auto", "system"):
        attempts.append("system")
    if engine == "none":
        raise TtsUnavailable("engine=none")

    last = None
    for eng in attempts:
        try:
            if eng == "edge":
                if not edge_available():
                    raise TtsUnavailable("edge-tts not installed (pip install edge-tts)")
                chosen_voice = voice or EDGE_VOICES.get(lang.lower(), EDGE_VOICES["en"])
                for rate in (0, 5, 10, 15, 20, 25, 35):
                    sp = edge_speak(text, chosen_voice, rate, out_dir, tag)
                    if sp.duration <= clip_dur - 0.8 or rate == 35:
                        break
                sp.engine, sp.rate = "edge", rate
            else:
                if not system_tts_available():
                    raise TtsUnavailable("no offline TTS found")
                sp = system_speak(text, voice, lang, out_dir, tag)
                if sp.duration > clip_dur - 0.3:
                    print(f"  ! voice {sp.duration:.1f}s does not fit clip {clip_dur:.1f}s "
                          f"(system TTS cannot be sped up); tail gets cut")
        except TtsUnavailable as exc:
            last = exc
            continue

        cache.parent.mkdir(parents=True, exist_ok=True)
        ext = sp.audio.suffix
        # write-then-rename: two parallel clips can finish at the same moment
        tmp_audio = cache.with_suffix(ext + ".part")
        shutil.copyfile(sp.audio, tmp_audio)
        os.replace(tmp_audio, cache.with_suffix(ext))
        meta_tmp = cache.with_suffix(".json.part")
        meta_tmp.write_text(json.dumps({
            "ext": ext, "duration": sp.duration, "words": sp.words,
            "engine": sp.engine, "rate": sp.rate,
        }, ensure_ascii=False), encoding="utf-8")
        os.replace(meta_tmp, cache.with_suffix(".json"))
        return sp

    raise TtsUnavailable(str(last) if last else "no TTS backend available")


# ------------------------------------------------------------------------- captions


def proportional_words(text, duration):
    """Turn plain text into fake word timings when the TTS gives none.

    Weighted by characters, which tracks speech pace well enough that captions
    never drift more than a beat across a 15-30s clip.
    """
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if not words:
        return []
    weights = [len(w) + 1 for w in words]
    total = sum(weights)
    out, t = [], 0.0
    for w, weight in zip(words, weights):
        d = duration * weight / total
        out.append((t, d, w))
        t += d
    return out


def ass_color(hex_color, default="&H00FFFFFF"):
    m = re.match(r"^#?([0-9a-fA-F]{6})$", hex_color or "")
    if not m:
        return default
    r, g, b = m.group(1)[0:2], m.group(1)[2:4], m.group(1)[4:6]
    return f"&H00{b}{g}{r}".upper()


STYLE_PRESETS = {
    # caption looks that survive the two places these clips get watched: a phone
    # in one hand, and a platform UI that eats the bottom 20% of the frame.
    "clean": {"size": 54, "margin_v": 110, "max_chars": 30},
    "tiktok": {"size": 64, "margin_v": 300, "max_chars": 22},
    "bold": {"size": 70, "margin_v": 320, "max_chars": 18},
}

CJK_LANGS = {"ja", "zh", "ko", "th"}


def group_lines(words, max_chars=30, max_words=6):
    """Split word timings into caption lines that fit a 9:16 frame."""
    lines, cur = [], []
    for w in words:
        cur.append(w)
        if len(" ".join(c[2] for c in cur)) >= max_chars or len(cur) >= max_words:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)

    # a trailing one- or two-word line reads like a stutter, so fold it into the line before
    merged = []
    for line in lines:
        if merged and len(line) <= 2 and len(merged[-1]) + len(line) <= max_words + 3:
            merged[-1] = merged[-1] + line
        else:
            merged.append(line)
    return merged


def resolve_style(style, width, height, lang="es"):
    """Preset < plan overrides < geometry defaults."""
    style = style if isinstance(style, dict) else {}
    merged = dict(STYLE_PRESETS.get(str(style.get("preset", "")), {}))
    merged.update({k: v for k, v in style.items() if k != "preset"})
    cjk = str(lang).lower().split("-")[0] in CJK_LANGS
    return {
        "size": int(merged.get("size") or round(width * 0.054)),
        "margin_v": int(merged.get("margin_v") or round(height * 0.078)),
        "margin_h": int(merged.get("margin_h") or round(width * 0.055)),
        "font": merged.get("font") or "Arial",
        "color": merged.get("color", "#FFFFFF"),
        "outline_color": merged.get("outline_color", "#000000"),
        "max_chars": int(merged.get("max_chars") or (14 if cjk else 30)),
        "max_words": int(merged.get("max_words") or (5 if cjk else 6)),
    }


def build_ass(lines, path, width, height, style, title=None, dur=None):
    def ts(t):
        return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"

    size = style["size"]
    primary = ass_color(style["color"])
    outline = ass_color(style["outline_color"])
    border = max(2, round(size * 0.08))
    tsize = round(size * 1.3)

    header = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {width}", f"PlayResY: {height}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{style['font']},{size},{primary},{primary},{outline},&H64000000,1,0,0,0,"
        f"100,100,0,0,1,{border},1,2,{style['margin_h']},{style['margin_h']},{style['margin_v']},1",
        f"Style: Title,{style['font']},{tsize},{primary},{primary},{outline},&H00000000,1,0,0,0,"
        f"100,100,0,0,1,{max(3, round(tsize * 0.1))},2,8,{style['margin_h']},{style['margin_h']},"
        f"{round(height * 0.11)},1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    body = []
    if title:
        title_end = min(3.2, (dur or 3.2) * 0.4)
        safe = str(title).replace("{", "(").replace("}", ")")
        body.append(f"Dialogue: 0,0:00:00.00,{ts(title_end)},Title,,0,0,0,," 
                    f"{{\\fad(180,220)\\t(0,320,\\fscx106\\fscy106)}}{safe}")
    for i, line in enumerate(lines):
        start = line[0][0]
        natural_end = line[-1][0] + line[-1][1] + 0.12
        if i + 1 < len(lines):
            # never overlap the next line: libass would stack both on screen at once
            natural_end = min(natural_end, lines[i + 1][0][0] - 0.04)
        end = max(natural_end, start + 0.25)
        text = " ".join(c[2] for c in line).replace("\n", " ")
        text = text.replace("{", "(").replace("}", ")")  # braces are ASS override syntax
        body.append(f"Dialogue: 0,{ts(start)},{ts(end)},Cap,,0,0,0,,{{\\fad(70,70)}}{text}")

    if len(body) > 1:
        times = [ln[0][0] for ln in lines]
        if len(times) > 1:
            read_time = (times[-1] - times[0]) / (len(times) - 1)
            if read_time < 0.45:
                print(f"  ! captions are fast ({read_time:.2f}s per line): shorten the script "
                      f"or drop --no-captions", file=sys.stderr)
    Path(path).write_text("\n".join(header + body) + "\n", encoding="utf-8")


def write_srt(lines, path):
    """Companion subtitle file for platforms that take captions separately (YouTube, LinkedIn)."""

    def ts(t):
        h, rem = divmod(max(0.0, t), 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"

    out = []
    for i, line in enumerate(lines, 1):
        start = line[0][0]
        end = line[-1][0] + line[-1][1] + 0.12
        if i < len(lines):
            end = min(end, lines[i][0][0] - 0.04)   # same no-overlap rule as the burn-in
        end = max(end, start + 0.25)
        text = " ".join(c[2] for c in line).replace("\n", " ")
        out.append(f"{i}\n{ts(start)} --> {ts(end)}\n{text}\n")
    Path(path).write_text("\n".join(out), encoding="utf-8")


# ------------------------------------------------------------------------- fonts/os


def find_font():
    candidates = []
    if IS_WIN:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        candidates = [rf"{windir}\Fonts\arialbd.ttf", rf"{windir}\Fonts\segoeuib.ttf",
                      rf"{windir}\Fonts\calibrib.ttf"]
    elif IS_MAC:
        candidates = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                      "/System/Library/Fonts/Helvetica.ttc",
                      "/System/Library/Fonts/SFNS.ttf"]
    else:
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
                      "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                      "/usr/share/fonts/liberation-sans/LiberationSans-Bold.ttf",
                      "/usr/share/fonts/noto/NotoSans-Bold.ttf"]
    for c in candidates:
        if Path(c).exists():
            return c
    return ""


def filter_path(path):
    """Escape a path for use inside an ffmpeg filtergraph string.

    Only the Windows drive colon needs escaping - and exactly once, otherwise
    the backslash itself gets escaped and ffmpeg reports a missing file.
    """
    p = str(path).replace("\\", "/")
    if IS_WIN and len(p) > 1 and p[1] == ":":
        p = p[0] + "\\:" + p[2:]
    return p.replace("'", r"\'")


# ------------------------------------------------------------------------- commands


def cmd_doctor(args):
    checks = []

    def add(name, ok, detail, fix=""):
        checks.append({"check": name, "ok": ok, "detail": detail, "fix": fix})

    add("python", sys.version_info >= (3, 9),
        platform.python_version(), "install Python 3.9+")

    if shutil.which(FFMPEG):
        _, out, _ = run([FFMPEG, "-hide_banner", "-version"])
        ver = out.splitlines()[0] if out else "unknown"
        add("ffmpeg", True, ver[:120])
    else:
        add("ffmpeg", False, "not found", "Windows: winget install Gyan.FFmpeg | "
            "macOS: brew install ffmpeg | Debian/Ubuntu: sudo apt install ffmpeg")

    add("ffprobe", bool(shutil.which(FFPROBE)), FFPROBE or "not found", "ships with ffmpeg")

    for filt, why in (("boxblur", "blurred background"), ("ass", "burned captions"),
                      ("loudnorm", "audio normalization"), ("drawtext", "timestamped sheets")):
        ok = has_filter(filt)
        add(f"filter:{filt}", ok, "available" if ok else "missing",
            "use a full ffmpeg build (gyan.dev on Windows, evermeet on macOS, "
            "the distro package on Linux)" if not ok else "")

    font = find_font()
    add("font", bool(font), font or "none found", "install a TrueType font "
        "(DejaVu/Liberation on Linux); only affects sheet timestamps")

    add("edge-tts", edge_available(),
        "installed" if edge_available() else "not installed (needs internet, best quality)",
        f"{sys.executable} -m pip install --user edge-tts")

    sys_tts = system_tts_available()
    detail = ("PowerShell System.Speech" if IS_WIN else "say" if IS_MAC else "espeak-ng")
    add("offline-tts", sys_tts, f"{detail}: {'found' if sys_tts else 'missing'} (no internet needed)",
        "Windows/macOS: built in | Debian/Ubuntu: sudo apt install espeak-ng")

    add("tesseract", bool(shutil.which("tesseract")), "optional, for OCR of frames",
        "Windows: winget install UB-Mannheim.TesseractOCR | macOS: brew install tesseract | "
        "Linux: sudo apt install tesseract-ocr")

    if args.fix and not edge_available():
        print("installing edge-tts...")
        code, out, err = run([sys.executable, "-m", "pip", "install", "--user", "-q", "edge-tts"],
                             timeout=300)
        print(out.strip() or err.strip() or ("installed" if code == 0 else f"failed ({code})"))
        for c in checks:
            if c["check"] == "edge-tts":
                c["ok"], c["detail"] = edge_available(), "installed"

    ok_count = sum(1 for c in checks if c["ok"])
    # only these gate a render: voice and OCR are optional by design
    required = {"python", "ffmpeg", "ffprobe", "filter:boxblur", "filter:ass"}
    required_ok = all(c["ok"] for c in checks if c["check"] in required)
    if args.json:
        print(json.dumps({"ok": required_ok, "os": platform.system(),
                          "python": platform.python_version(), "checks": checks}, indent=2))
        return 0 if required_ok else 1
    for c in checks:
        mark = "OK  " if c["ok"] else "MISS"
        print(f"[{mark}] {c['check']:<18} {c['detail']}")
        if not c["ok"] and c["fix"]:
            print(f"       fix: {c['fix']}")
    print(f"\n{ok_count}/{len(checks)} checks passed")
    return 0 if required_ok else 1


def scene_cuts(video, threshold=0.03):
    """Timestamps where the picture changes enough to count as a cut."""
    _, _, err = run([FFMPEG, "-hide_banner", "-i", str(video), "-filter:v",
                     f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"])
    times = []
    for line in err.splitlines():
        if "pts_time:" in line:
            try:
                times.append(float(line.split("pts_time:")[1].split()[0]))
            except (IndexError, ValueError):
                pass
    grouped = []
    for t in sorted(times):
        if grouped and t - grouped[-1] < 1.5:
            continue
        grouped.append(round(t, 2))
    return grouped


def cmd_probe(args):
    info = probe_media(args.video)
    cuts = [] if args.no_scene else scene_cuts(args.video, args.threshold)

    if args.json:
        print(json.dumps({**info, "scene_cuts": cuts}, indent=2))
        return 0

    print(f"file       {info['path']}")
    print(f"duration   {info['duration']}s")
    print(f"video      {info['width']}x{info['height']} @ {info['fps']}fps ({info['video_codec']})")
    if info["has_audio"]:
        print(f"audio      {info['audio_codec']} {info['sample_rate']}Hz "
              f"{info['audio_channels']}ch -> transcription is possible, but narration still wins "
              f"on silent screen recordings")
    else:
        print("audio      NONE -> no transcription possible: write the narration from the visuals")
    if cuts:
        print(f"cuts       {', '.join(f'{c:.1f}s' for c in cuts)}")
        if len(cuts) <= 3:
            print("           almost one continuous take: pick beats from what is on screen")
        else:
            print("           group these into 3-5 story beats, not one clip per cut")
    else:
        print("cuts       none: continuous take, choose beats by content")
    print(f"\nnext: python {Path(__file__).name} sheet \"{args.video}\"  "
          f"# then read the images and write plan.json")
    return 0


def cmd_sheet(args):
    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    info = probe_media(args.video)
    tmp = Path(tempfile.mkdtemp(prefix="tc-sheet-"))
    font = find_font()
    label = ""
    if font and not args.no_labels and has_filter("drawtext"):
        label = (f",drawtext=fontfile='{filter_path(font)}':text='%{{pts\\:hms}}':x=6:y=6:"
                 f"fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.7")
    cols, rows = args.cols, args.rows
    per = cols * rows
    vf = f"fps=1/{args.every},scale={args.tile_width}:-1{label}"
    code, _, err = run([FFMPEG, "-hide_banner", "-v", "error", "-i", args.video, "-vf", vf,
                        "-y", str(tmp / "f_%04d.jpg")])
    if code != 0:
        print(f"frame extraction failed: {err.strip()[:400]}", file=sys.stderr)
        return 1
    frames = sorted(tmp.glob("f_*.jpg"))
    if not frames:
        print("no frames extracted (is the file a video?)", file=sys.stderr)
        return 1
    if args.max_sheets > 0:
        frames = frames[: args.max_sheets * per]   # token budget: fewer images to read

    sheets = []
    for i in range(0, len(frames), per):
        sheet = out / f"sheet_{i // per + 1}.jpg"
        run([FFMPEG, "-hide_banner", "-v", "error", "-start_number", str(i + 1),
             "-i", str(tmp / "f_%04d.jpg"), "-vf", f"tile={cols}x{rows}", "-frames:v", "1",
             "-y", str(sheet)])
        if sheet.exists():
            start = i * args.every
            end = min((i + per) * args.every, info["duration"])
            sheets.append({"path": str(sheet.resolve()), "from": round(start, 1), "to": round(end, 1)})

    meta = {"video": info, "every": args.every, "sheets": sheets,
            "frames": [{"index": n + 1, "time": round(n * args.every, 2), "path": str(f)}
                       for n, f in enumerate(frames)]}
    (out / "sheet_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if args.keep_frames:
        shutil.copytree(tmp, out / "frames", dirs_exist_ok=True)

    if args.json:
        print(json.dumps(meta, indent=2))
    else:
        for s in sheets:
            print(f"{s['path']}  covers {s['from']}s-{s['to']}s")
        print(f"{out / 'sheet_meta.json'}  (frame times for OCR / citation)")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


def cmd_ocr(args):
    exe = shutil.which("tesseract")
    if not exe:
        print("tesseract not found. Install it, or read the sheets visually instead.\n"
              "  Windows: winget install UB-Mannheim.TesseractOCR\n"
              "  macOS:   brew install tesseract\n"
              "  Linux:   sudo apt install tesseract-ocr", file=sys.stderr)
        return 1
    info = probe_media(args.video)
    tmp = Path(tempfile.mkdtemp(prefix="tc-ocr-"))
    # crop the middle band: UI content usually sits there, taskbars and wallpapers do not
    crop = f"crop=iw:ih*{args.vertical_span}:0:ih*{(1 - args.vertical_span) / 2},"
    run([FFMPEG, "-hide_banner", "-v", "error", "-i", args.video,
         "-vf", f"fps=1/{args.every},{crop}scale=1600:-1", "-y", str(tmp / "f_%04d.png")])
    frames = sorted(tmp.glob("f_*.png"))
    chunks = []
    for n, frame in enumerate(frames):
        code, out, _ = run([exe, str(frame), "stdout", "-l", args.lang, "--psm", "6"])
        text = " ".join(out.split())
        if text:
            chunks.append({"time": round(n * args.every, 1), "text": text})
    result = {"video": info, "frames": len(frames), "segments": chunks}
    if args.json:
        print(json.dumps(result, indent=2))
    elif args.brief:
        print(f"{len(frames)} frames, {len(chunks)} with text -> {args.out or 'stdout'}")
    else:
        for c in chunks:
            print(f"{c['time']:>7.1f}s  {c['text']}")
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


ASPECTS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "16:9": (1920, 1080), "4:5": (1080, 1350)}
ASPECT_CHOICES = list(ASPECTS) + ["auto"]


def resolve_aspect(aspect, info):
    """`auto` keeps the recording's own orientation: landscape stays landscape."""
    aspect = str(aspect or "9:16")
    if aspect != "auto":
        return aspect if aspect in ASPECTS else "9:16"
    w, h = info.get("width") or 0, info.get("height") or 0
    if not w or not h:
        return "9:16"
    if abs(w - h) <= h * 0.05:
        return "1:1"
    return "16:9" if w > h else "9:16"


def cmd_plan(args):
    """Scaffold a plan.json: equal beats snapped to the nearest scene cut.

    The empty scripts are the point - they mark exactly where a human or an agent
    has to look at the footage and decide what each beat is about.
    """
    info = probe_media(args.video)
    total_start = max(0.0, args.start or 0.0)
    total_end = min(info["duration"], args.end or info["duration"])
    if total_end - total_start < 2:
        raise SystemExit(f"nothing to plan between {total_start}s and {total_end}s")
    beats = max(1, args.beats)
    cuts = scene_cuts(args.video, args.threshold)

    step = (total_end - total_start) / beats
    bounds = [total_start]
    for i in range(1, beats):
        target = total_start + step * i
        near = [c for c in cuts if abs(c - target) <= step * 0.35]
        bounds.append(min(near, key=lambda c: abs(c - target)) if near else round(target, 2))
    bounds.append(total_end)

    clips = []
    for i in range(beats):
        start, end = bounds[i], bounds[i + 1]
        clips.append({
            "name": f"{i + 1:02d}-beat",
            "start": round(start, 2),
            "duration": round(end - start, 2),
            "script": "",
        })

    src = Path(args.video).resolve()
    out = Path(args.out).expanduser() if args.out else src.with_suffix(".plan.json")
    try:
        # keep plans portable: relative source when it lives next to the plan
        source_value = os.path.relpath(src, out.parent).replace("\\", "/") \
            if out.parent in src.parents else str(src)
    except ValueError:      # different drives on Windows
        source_value = str(src)

    plan = {"source": source_value, "aspect": args.aspect or ("auto" if args.full else "9:16"),
            "lang": args.lang, "audio": "tts", "clips": clips}
    if args.full:
        plan["stitch"] = True
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps({"plan": str(out), "clips": clips, "stitch": bool(args.full)}, indent=2))
        return 0
    if args.brief:
        print(f"{out}: {len(clips)} beats" + (" -> stitched" if args.full else ""))
        return 0
    print(f"plan: {out}\n")
    for c in clips:
        budget = int(c["duration"] * 15 * 0.85)
        print(f"  {c['name']:<10} {c['start']:>7.2f}s +{c['duration']:>5.1f}s   script ~{budget} chars")
    print(f"\n{len(clips)} beats, snapped to the nearest cut within {step * 0.35:.1f}s")
    print("fill the scripts, then: talkicut render " + str(out.name))
    return 0


WIKI_API = "https://commons.wikimedia.org/w/api.php"
HTTP_UA = f"{TOOL}/{VERSION} (+https://github.com/laopro/talkicut)"


def http_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wiki_images(query, limit):
    """Search Wikimedia Commons for freely licensed stills. No key, no account."""
    params = {
        "action": "query", "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": "6",
        "gsrlimit": str(max(4, min(limit * 6, 40))),
        "prop": "imageinfo", "iiprop": "url|extmetadata|size",
        "iiurlwidth": "1600", "format": "json", "formatversion": "2",
    }
    data = http_json(f"{WIKI_API}?{urllib.parse.urlencode(params)}")
    found = []
    for page in data.get("query", {}).get("pages", []):
        ii = (page.get("imageinfo") or [{}])[0]
        url = ii.get("thumburl") or ii.get("url")
        if not url:
            continue
        if (ii.get("width") or 0) and ii["width"] < 800:
            continue
        meta = ii.get("extmetadata") or {}

        def field(key):
            return re.sub(r"<[^>]+>", "", str((meta.get(key) or {}).get("value") or "")).strip()

        found.append({
            "url": url, "page": ii.get("descriptionurl") or "",
            "title": field("ObjectName") or page.get("title", "").removeprefix("File:"),
            "creator": field("Artist") or "unknown",
            "license": field("LicenseShortName") or "see source",
            "w": ii.get("width") or 0, "h": ii.get("height") or 0,
        })
    return found


def candidate_score(query, cand):
    """Rank by what the file says about itself: words beat silence, photos beat diagrams."""
    tokens = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
    text = f"{cand.get('title', '')}".lower()
    score = sum(3 for t in tokens if t in text)
    if cand.get("url", "").lower().split("?")[0].endswith((".jpg", ".jpeg")):
        score += 2
    bad = ("logo", "icon", "map", "diagram", "chart", "poster", "cover", "drawing",
           "illustration", "screenshot", "coat of arms", "flag", "portrait", "sign")
    score -= sum(4 for word in bad if word in text)
    w, h = cand.get("w") or 0, cand.get("h") or 0
    if w and h:
        ar = w / h
        if 1.15 <= ar <= 2.0:
            score += 1          # landscape photos sit better in a video frame
        if ar > 3 or ar < 0.5:
            score -= 3
    return score


def make_sheet(paths, out, cell=360, cols=4):
    """One contact sheet of the chosen stills, so a human or a model can veto them."""
    paths = [Path(p) for p in paths][:12]
    if not paths:
        return None
    rows = (len(paths) + cols - 1) // cols
    inputs, chains = [], []
    for i, p in enumerate(paths):
        inputs += ["-i", str(p)]
        chains.append(f"[{i}:v]scale={cell}:{cell}:force_original_aspect_ratio=decrease,"
                      f"pad={cell}:{cell}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]")
    graph = ";".join(chains) + ";" + "".join(f"[v{i}]" for i in range(len(paths))) + \
        f"concat=n={len(paths)}:v=1:a=0,tile={cols}x{rows}:padding=6:margin=6[out]"
    code, _, err = run([FFMPEG, "-hide_banner", "-v", "error", "-y", *inputs,
                        "-filter_complex", graph, "-map", "[out]", "-frames:v", "1", str(out)])
    return out if code == 0 else None


def download_image(url, dest_dir: Path, stem: str):
    """Download one image, keeping an extension ffmpeg can trust from the magic bytes."""
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read(15_000_000)
    if len(data) < 8_000:
        raise ValueError("file too small")
    if data[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        ext = ".webp"
    elif data[:4] == b"GIF8":
        ext = ".gif"
    else:
        ext = ".jpg"
    dest = dest_dir / f"{stem}{ext}"
    dest.write_bytes(data)
    return dest


AUDIO_EXTS = (".mp3", ".ogg", ".oga", ".opus", ".wav", ".flac", ".m4a")


def wiki_audio(query, limit=6):
    """Search Wikimedia Commons for a freely licensed music track (no key)."""
    params = {
        "action": "query", "generator": "search",
        "gsrsearch": f"filetype:audio {query}", "gsrnamespace": "6",
        "gsrlimit": str(min(limit * 3, 20)), "prop": "imageinfo",
        "iiprop": "url|size|extmetadata", "format": "json", "formatversion": "2",
    }
    data = http_json(f"{WIKI_API}?{urllib.parse.urlencode(params)}")
    found = []
    for page in data.get("query", {}).get("pages", []):
        ii = (page.get("imageinfo") or [{}])[0]
        url = ii.get("url") or ""
        ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
        dur = float(ii.get("duration") or 0)
        if not url or ext not in AUDIO_EXTS or dur < 12 or dur > 600:
            continue
        if (ii.get("size") or 0) > 30_000_000:
            continue
        meta = ii.get("extmetadata") or {}

        def field(key):
            return re.sub(r"<[^>]+>", "", str((meta.get(key) or {}).get("value") or "")).strip()

        license_name = field("LicenseShortName")
        title = field("ObjectName") or page.get("title", "").removeprefix("File:")
        score = 3 if license_name.lower() in ("cc0", "public domain") else 1
        score -= 1 if dur > 360 else 0
        score += sum(2 for token in re.findall(r"[a-z]+", query.lower())
                     if token in page.get("title", "").lower())
        found.append({"url": url, "page": ii.get("descriptionurl") or "", "title": title,
                      "creator": field("Artist") or "unknown",
                      "license": license_name or "see source", "duration": dur, "score": score})
    found.sort(key=lambda c: c["score"], reverse=True)
    return found


def download_audio(url, dest_dir: Path, stem: str):
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = resp.read(40_000_000)
    if len(data) < 20_000:
        raise ValueError("file too small")
    ext = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if ext not in AUDIO_EXTS:
        ext = ".mp3"
    dest = dest_dir / f"{stem}{ext}"
    dest.write_bytes(data)
    return dest


def cmd_fetch(args):
    """Fill a plan's image slots from Wikimedia Commons, with attribution."""
    plan_path = Path(args.plan).expanduser().resolve()
    if not plan_path.exists():
        raise SystemExit(f"plan not found: {plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    clips = plan.get("clips") or []
    if not clips:
        raise SystemExit("plan has no clips")
    media_dir = (plan_path.parent / args.out).resolve()
    media_dir.mkdir(parents=True, exist_ok=True)
    credits = plan.get("credits") or []
    used = {(c.get("clip"), c.get("url")) for c in credits}

    filled = 0
    for i, clip in enumerate(clips):
        query = str(clip.get("query") or "").strip()
        if not query or clip.get("media"):
            continue
        try:
            candidates = wiki_images(query, args.n)
            candidates.sort(key=lambda c: candidate_score(query, c), reverse=True)
            credits = [c for c in credits if c.get("clip") != clip.get("name")]
            used = {(c.get("clip"), c.get("url")) for c in credits}
        except (OSError, ValueError) as exc:
            print(f"  ! {clip.get('name', i + 1)}: search failed ({exc})", file=sys.stderr)
            continue
        got = []
        for j, cand in enumerate(candidates[: args.n]):
            try:
                path = download_image(cand["url"], media_dir,
                                      f"{clip.get('name', f'clip-{i + 1:02d}')}-{j + 1}")
            except (OSError, ValueError) as exc:
                print(f"  ! {clip.get('name')}: download failed ({exc})", file=sys.stderr)
                continue
            got.append(str(path.relative_to(plan_path.parent)).replace("\\", "/"))
            key = (clip.get("name"), cand["url"])
            if key not in used:
                credits.append({"clip": clip.get("name"), "title": cand["title"],
                                "creator": cand["creator"], "license": cand["license"],
                                "url": cand["url"], "page": cand["page"]})
                used.add(key)
        if got:
            clip["media"] = got
            filled += 1
            print(f"  {clip.get('name')}: {len(got)} image(s) for \"{query}\"")
        else:
            print(f"  ! {clip.get('name')}: nothing usable for \"{query}\"", file=sys.stderr)

    if args.music:
        try:
            tracks = wiki_audio(args.music)
        except (OSError, ValueError) as exc:
            tracks = []
            print(f"  ! music search failed ({exc})", file=sys.stderr)
        if tracks:
            pick = tracks[0]
            try:
                path = download_audio(pick["url"], media_dir, "music")
                plan["music"] = str(path.relative_to(plan_path.parent)).replace("\\", "/")
                credits = [c for c in credits if c.get("clip") != "music"]
                credits.append({"clip": "music", "title": pick["title"],
                                "creator": pick["creator"], "license": pick["license"],
                                "url": pick["url"], "page": pick["page"]})
                print(f"  music: {pick['title']} ({pick['license']}, {pick['duration']:.0f}s)")
            except (OSError, ValueError) as exc:
                print(f"  ! music download failed ({exc})", file=sys.stderr)
        else:
            print("  ! no usable music track found", file=sys.stderr)

    plan["credits"] = credits
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    if credits:
        lines = [f"{c.get('title', '')} — {c.get('creator', '')} — {c.get('license', '')} — "
                 f"{c.get('page') or c.get('url', '')}" for c in credits]
        (media_dir / "credits.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{filled} clip(s) with media, {len(credits)} credit(s) -> {media_dir}")
    picked = [m for c in clips for m in (c.get("media") or [])]
    if args.sheet and picked:
        sheet = make_sheet(picked, media_dir / "sheet.jpg")
        if sheet:
            print(f"sheet: {sheet}")
            for i, m in enumerate(picked[:12], 1):
                print(f"  {i:>2}. {Path(m).name}")
    pending = [c for c in clips if str(c.get("query") or "").strip() and not c.get("media")]
    return 1 if pending else 0


def cmd_storyboard(args):
    """Scaffold a plan for a video that has no source footage: beats + image queries."""
    beats = max(1, args.beats)
    total = max(2.0, args.seconds)
    dur = round(total / beats, 2)
    clips = [{"name": f"{i + 1:02d}-beat", "duration": dur, "title": "",
              "script": "", "query": ""} for i in range(beats)]
    plan = {"prompt": args.prompt, "aspect": args.aspect, "lang": args.lang,
            "audio": "tts", "clips": clips}
    out = Path(args.out).expanduser() if args.out else Path("reel.plan.json")
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json:
        print(json.dumps({"plan": str(out), "clips": clips}, indent=2))
        return 0
    print(f"plan: {out}\n")
    for c in clips:
        print(f"  {c['name']:<10} {c['duration']:>5.1f}s   script ~{int(c['duration'] * 15 * 0.85)} chars")
    print(f"\nfill script + query per beat, then: talkicut fetch {out.name} && talkicut render {out.name}")
    return 0


def cmd_verify(args):
    """Catch the silent failures: no audio track, wrong size, silent or clipped audio."""
    root = Path(args.dir).expanduser()
    files = sorted(root.glob("*.mp4")) if root.is_dir() else [root]
    if not files:
        raise SystemExit(f"no .mp4 files in {root}")
    rows, problems_total = [], 0
    for f in files:
        info = probe_media(f)
        _, _, err = run([FFMPEG, "-hide_banner", "-i", str(f), "-af", "volumedetect",
                         "-f", "null", "-"])
        m = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", err)
        mean = float(m.group(1)) if m else None
        problems = []
        if not info["has_audio"]:
            problems.append("no audio track")
        if info["width"] == 0:
            problems.append("no video stream")
        if info["duration"] < 1:
            problems.append("shorter than 1s")
        if mean is not None and mean < args.min_volume:
            problems.append(f"quiet ({mean:.1f} dB)")
        if mean is not None and mean > args.max_volume:
            problems.append(f"loud ({mean:.1f} dB)")
        problems_total += len(problems)
        rows.append({"file": f.name, "duration": info["duration"],
                     "size": f"{info['width']}x{info['height']}" if info["width"] else "-",
                     "mean_db": mean, "problems": problems})

    if args.json:
        print(json.dumps({"ok": problems_total == 0, "clips": rows}, indent=2))
        return 0 if problems_total == 0 else 1
    if args.brief:
        print(f"{len(rows)} clips, {problems_total} problem(s)")
        return 0 if problems_total == 0 else 1

    print(f"{'file':<38} {'dur':>7} {'size':>11} {'dB':>7}  status")
    for r in rows:
        status = "ok" if not r["problems"] else ", ".join(r["problems"])
        db = f"{r['mean_db']:.1f}" if r["mean_db"] is not None else "-"
        print(f"{r['file'][:38]:<38} {r['duration']:>7.1f} {r['size']:>11} {db:>7}  {status}")
    print(f"\n{len(rows)} clips, {problems_total} problem(s)")
    return 0 if problems_total == 0 else 1


def load_plan(path):
    plan_path = Path(path).expanduser().resolve()
    if not plan_path.exists():
        raise SystemExit(f"plan not found: {plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    # source paths are relative to the plan file: plans stay portable between machines
    src_value = plan.get("source")
    if src_value:
        src = Path(src_value).expanduser()
        if not src.is_absolute():
            src = plan_path.parent / src
        if not src.exists():
            raise SystemExit(f"source video not found: {src}")
        plan["source"] = str(src.resolve())
    else:
        # no source: a slideshow plan built from fetched images
        plan["source"] = None

    clips = plan.get("clips")
    if not isinstance(clips, list) or not clips:
        raise SystemExit("plan needs a non-empty 'clips' array")
    if not plan["source"] and not any(
            isinstance(c, dict) and (c.get("media") or c.get("query") or c.get("script") or c.get("title"))
            for c in clips):
        raise SystemExit("plan needs a 'source' video, or clips with 'media'/'query'/'script'")
    seen = {}
    for i, clip in enumerate(clips):
        if not isinstance(clip, dict):
            raise SystemExit(f"clip #{i + 1} must be an object")
        clip.setdefault("name", f"clip-{i + 1:02d}")
        name = re.sub(r"[^\w\-. ]+", "", str(clip["name"])).strip().replace(" ", "-") or f"clip-{i + 1:02d}"
        # duplicate names would silently overwrite each other's file
        if name in seen:
            seen[name] += 1
            name = f"{name}-{seen[name]}"
        else:
            seen[name] = 1
        clip["name"] = name
        clip.setdefault("start", 0)
        for key in ("start", "duration"):
            if clip.get(key) not in (None, ""):
                try:
                    clip[key] = float(clip[key])
                except (TypeError, ValueError):
                    raise SystemExit(f"clip '{clip['name']}': {key} must be a number")
        media = clip.get("media")
        if isinstance(media, str):
            media = [media]
        if media:
            clip["media"] = [str((plan_path.parent / str(m)).resolve() if not Path(str(m)).is_absolute()
                                 else Path(str(m))) for m in media]
    plan["_path"] = str(plan_path)
    return plan


def build_broll(clip, width, height, dur, work: Path, index: int, fit="blur"):
    """Stills into motion: Ken Burns, crossfades, and a frame that keeps the subject whole."""
    media = [Path(p) for p in (clip.get("media") or []) if Path(p).exists()]
    out = work / f"broll-{index:02d}.mp4"
    fps = 30
    if not media:
        # a beat without an image is still a beat: dark canvas, captions carry it
        cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y", "-f", "lavfi",
               "-i", f"color=c=0x111318:s={width}x{height}:r={fps}:d={dur}",
               "-t", f"{dur}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-pix_fmt", "yuv420p", str(out)]
        code, _, err = run(cmd, cwd=work)
        if code != 0:
            print(f"  ! {clip['name']}: could not build the canvas: {err.strip()[:300]}", file=sys.stderr)
            return None
        return out

    n = len(media)
    xf = round(min(0.5, dur / n * 0.3), 3) if n > 1 and has_filter("xfade") else 0.0
    seg = round((dur + (n - 1) * xf) / n, 3)
    frames = max(2, int(round(seg * fps)))
    blur = ",boxblur=24:2" if has_filter("boxblur") else ""

    def frame_mode(img):
        """auto: fill the frame when the photo is already close to it, otherwise show it whole."""
        if fit != "auto":
            return fit
        try:
            dims = probe_media(img)
            ar = dims["width"] / dims["height"] if dims["height"] else 0
        except SystemExit:
            ar = 0
        return "cover" if ar and abs(ar - width / height) <= 0.22 * (width / height) else "blur"

    inputs, chains = [], []
    for i, img in enumerate(media):
        inputs += ["-i", str(img)]
        cover = frame_mode(img) == "cover"
        zin = i % 2 == 0
        z = f"1+0.14*on/{frames}" if zin else f"1.14-0.14*on/{frames}"
        if i % 4 == 0:
            px, py = f"(iw-iw/zoom)*on/{frames}", "(ih-ih/zoom)/2"
        elif i % 4 == 1:
            px, py = f"(iw-iw/zoom)*(1-on/{frames})", "(ih-ih/zoom)/2"
        elif i % 4 == 2:
            px, py = "(iw-iw/zoom)/2", f"(ih-ih/zoom)*on/{frames}"
        else:
            px, py = "(iw-iw/zoom)/2", f"(ih-ih/zoom)*(1-on/{frames})"

        if cover:
            cw = int(width * 1.16) // 2 * 2
            ch = int(height * 1.16) // 2 * 2
            base = (f"[{i}:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,"
                    f"crop={cw}:{ch}")
        else:
            cw = int(width * 1.1) // 2 * 2
            ch = int(height * 1.1) // 2 * 2
            fg_w, fg_h = int(cw * 0.94) // 2 * 2, int(ch * 0.94) // 2 * 2
            base = (f"[{i}:v]split=2[bg{i}][fg{i}];"
                    f"[bg{i}]scale={cw}:{ch}:force_original_aspect_ratio=increase,"
                    f"crop={cw}:{ch}{blur}[b{i}];"
                    f"[fg{i}]scale={fg_w}:{fg_h}:force_original_aspect_ratio=decrease[f{i}];"
                    f"[b{i}][f{i}]overlay=(W-w)/2:(H-h)/2")
        chains.append(
            f"{base},zoompan=z='{z}':x='{px}':y='{py}':d={frames}:s={width}x{height}:"
            f"fps={fps},setsar=1[v{i}]"
        )

    if n > 1 and xf > 0:
        parts = [f"[v0]"]
        prev = "[v0]"
        for i in range(1, n):
            off = round(i * (seg - xf), 3)
            trans = ("fade", "slideleft", "zoomin", "wipeup")[(i - 1) % 4]
            parts.append(f"{prev}[v{i}]xfade=transition={trans}:duration={xf}:offset={off}[x{i}]")
            prev = f"[x{i}]"
        graph = ";".join(chains + parts[1:]) + f";{prev}format=yuv420p[v]"
    elif n > 1:
        graph = ";".join(chains + ["".join(f"[v{i}]" for i in range(n))
                                  + f"concat=n={n}:v=1:a=0,format=yuv420p[v]"])
    else:
        graph = chains[0] + ";[v0]format=yuv420p[v]"

    code, _, err = run([FFMPEG, "-hide_banner", "-v", "error", "-y", *inputs,
                        "-filter_complex", graph, "-map", "[v]", "-t", f"{dur}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-r", str(fps), str(out)], cwd=work)
    if code != 0:
        print(f"  ! {clip['name']}: could not build b-roll: {err.strip()[:300]}", file=sys.stderr)
        return None
    return out


def render_clip(clip, plan, opts, work: Path, index: int):
    info = opts["info"]
    src_dur = info["duration"]
    start = max(0.0, float(clip.get("start") or 0))
    dur = float(clip.get("duration") or 0) or (src_dur - start)
    if plan.get("source"):
        dur = round(min(dur, src_dur - start), 3)
    else:
        dur = round(dur, 3)
    if dur <= 0.2:
        return {"name": clip["name"], "ok": False,
                "error": "clip needs a positive duration" if not plan.get("source")
                         else "clip is outside the video"}

    aspect = resolve_aspect(clip.get("aspect") or plan.get("aspect") or opts["aspect"], info)
    width, height = ASPECTS.get(aspect, ASPECTS["9:16"])
    script = (clip.get("script") or clip.get("narration") or "").strip()
    lang = clip.get("lang") or plan.get("lang") or opts["lang"]
    fit = clip.get("fit") or plan.get("fit") or opts["fit"]
    out_path = opts["out_dir"] / f"{clip['name']}.mp4"
    if out_path.exists() and not opts["force"]:
        return {"name": clip["name"], "ok": True, "skipped": True, "path": str(out_path),
                "duration": duration_of(out_path)}

    audio_mode = clip.get("audio") or plan.get("audio") or opts["audio"]
    # "source" means: the original audio is the sound of this clip, so no narration is generated
    want_voice = bool(script) and opts["voiceover"] and audio_mode != "source"

    speech = None
    if want_voice:
        try:
            speech = make_speech(script, opts["tts"], clip.get("voice") or plan.get("voice") or opts["voice"],
                                 lang, dur, work, f"tts-{index:02d}")
            # a slideshow beat lasts as long as its voice: no dead air after the last caption
            if not plan.get("source"):
                dur = round(max(2.2, min(dur, speech.duration + 0.35)), 3)
            print(f"  {clip['name']}: voice {speech.engine} {speech.duration:.1f}s / clip {dur:.1f}s",
                  file=sys.stderr)
        except TtsUnavailable as exc:
            print(f"  ! {clip['name']}: no voice ({exc})", file=sys.stderr)

    src_path, src_start, src_info = plan["source"], start, info
    if not plan.get("source"):
        broll = build_broll(clip, width, height, dur, work, index, fit)
        if not broll:
            return {"name": clip["name"], "ok": False, "error": "b-roll build failed"}
        src_path, src_start = str(broll), 0.0
        src_info = {**info, "width": width, "height": height, "has_audio": False, "duration": dur}

    inputs = ["-ss", f"{src_start}", "-t", f"{dur}", "-i", src_path]
    if speech:
        inputs += ["-i", str(speech.audio)]

    # If the source already has the target shape (16:9 video, 16:9 out) scale it
    # straight: no blurred fill, no wasted encode.
    src_ar = (src_info["width"] / src_info["height"]) if src_info.get("height") else 0
    same_shape = src_ar and abs(src_ar - width / height) < 0.02

    # Three ways to fill a frame of a different shape. "blur" keeps every pixel
    # (right for UI), "cover" crops for a fuller frame, "pad" uses a flat colour.
    if same_shape or fit == "pad":
        vf = (f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
              f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x0E0E12")
    elif fit == "cover":
        vf = (f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
              f"crop={width}:{height}")
    else:
        vf = (f"[0:v]split=2[bg][fg];"
              f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
              f"crop={width}:{height}")
        if has_filter("boxblur"):
            vf += ",boxblur=18:2"
        vf += (f"[b];[fg]scale={width}:-2[f];[b][f]overlay=(W-w)/2:(H-h)/2")

    style = resolve_style(clip.get("captions_style") or plan.get("captions_style") or
                          opts["captions_style"], width, height, lang)
    captions_on = False
    title = (clip.get("title") or "").strip()
    if (script or title) and opts["captions"] and has_filter("ass"):
        words = (speech.words or proportional_words(script, min(speech.duration, dur))) if speech \
            else proportional_words(script, dur)
        lines = group_lines(words, style["max_chars"], style["max_words"]) if words else []
        ass = work / f"cap-{index:02d}.ass"
        build_ass(lines, ass, width, height, style, title=title or None, dur=dur)
        vf += f",ass=cap-{index:02d}.ass"   # relative to cwd: no path escaping anywhere
        captions_on = bool(lines)
        if opts["srt"] and lines:
            write_srt(lines, opts["out_dir"] / f"{clip['name']}.srt")

    # a thin progress bar is the cheapest motion graphic that makes a slideshow feel edited
    if not plan.get("source") and has_filter("drawbox") and dur > 0:
        vf += (f",drawbox=x=0:y=0:w='iw*min(t/{dur},1)':h=10:"
               f"color=0xFF3B5C@0.9:t=fill")

    vf += ",format=yuv420p"

    maps, filters = [], []
    if speech:
        maps = ["-map", "0:v", "-map", "1:a"]
    elif audio_mode in ("source", "mix") and src_info["has_audio"]:
        maps = ["-map", "0:v", "-map", "0:a"]
    else:
        inputs += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
        maps = ["-map", "0:v", "-map", str(sum(1 for x in inputs if x == "-i") - 1)]

    # audio graph: tts alone, source alone, or source ducked under the narration
    if speech and audio_mode == "mix" and src_info["has_audio"]:
        filters.append("[0:a]volume=0.22[bgm]")
        filters.append("[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[vo]")
        filters.append("[bgm][vo]amix=inputs=2:duration=longest:normalize=0[aout]")
    elif speech:
        filters.append("[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    elif audio_mode in ("source", "mix") and src_info["has_audio"]:
        filters.append("[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    else:
        filters.append(f"[{int(maps[-1])}:a]aformat=sample_rates=48000:channel_layouts=stereo[aout]")

    graph = vf + "[v];" + ";".join(filters)
    cmd = [FFMPEG, "-hide_banner", "-v", "error", "-y", *inputs,
           "-filter_complex", graph, "-map", "[v]", "-map", "[aout]",
           "-t", f"{dur}", "-c:v", "libx264", "-preset", opts["preset"], "-crf", str(opts["crf"]),
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
    if opts["fps"]:
        cmd += ["-r", str(opts["fps"])]
    cmd += ["-movflags", "+faststart", str(out_path)]

    if opts["dry_run"]:
        print(" ".join(shlex.quote(str(x)) for x in cmd), file=sys.stderr)
        return {"name": clip["name"], "ok": True, "dry_run": True, "path": str(out_path),
                "duration": dur}

    code, _, err = run(cmd, cwd=work, timeout=opts["timeout"])
    if code != 0:
        return {"name": clip["name"], "ok": False, "error": err.strip()[:600]}

    if opts["thumbnail"]:
        thumb = opts["out_dir"] / f"{clip['name']}.jpg"
        run([FFMPEG, "-hide_banner", "-v", "error", "-y", "-ss", f"{min(dur * 0.4, max(0.0, dur - 0.2))}",
             "-i", str(out_path), "-frames:v", "1", "-q:v", "3", str(thumb)])

    out_info = probe_media(out_path)
    return {"name": clip["name"], "ok": True, "path": str(out_path),
            "duration": out_info["duration"], "width": out_info["width"],
            "height": out_info["height"], "has_audio": out_info["has_audio"],
            "voice": speech.engine if speech else None,
            "voice_seconds": round(speech.duration, 1) if speech else None,
            "captions": captions_on, "title": title or None,
            "script_chars": len(script)}


def stitch_clips(clips, results, out_dir: Path, name: str):
    """Join the rendered segments into one video, in plan order.

    Segments come from the same encoder settings, so the concat demuxer can copy
    the streams instead of re-encoding the whole timeline.
    """
    by_name = {r["name"]: r for r in results}
    paths = []
    for clip in clips:
        r = by_name.get(clip["name"])
        if not r or not r.get("ok") or not r.get("path") or not Path(r["path"]).exists():
            return None, f"missing clip {clip['name']}"
        paths.append(Path(r["path"]).resolve())

    listing = out_dir / f".{name}.concat.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in paths), encoding="utf-8")
    out = out_dir / f"{name}.mp4"
    try:
        code, _, err = run([FFMPEG, "-hide_banner", "-v", "error", "-y",
                            "-f", "concat", "-safe", "0", "-i", str(listing),
                            "-c", "copy", "-movflags", "+faststart", str(out)])
    finally:
        listing.unlink(missing_ok=True)
    if code != 0 or not out.exists():
        return None, err.strip()[:400]
    return out, None


def add_music(video: Path, music: Path, volume=0.14):
    """Loop a track under the existing audio, fade it in and out. Video is copied, not re-encoded."""
    dur = duration_of(video)
    if dur <= 0.5:
        return False
    tmp = video.with_name(video.stem + ".music" + video.suffix)
    fade_out = max(0.0, dur - 1.6)
    graph = (f"[1:a]volume={volume},afade=t=in:st=0:d=0.7,"
             f"afade=t=out:st={fade_out:.2f}:d=1.6[m];"
             f"[0:a][m]amix=inputs=2:duration=first:normalize=0[a]")
    code, _, err = run([FFMPEG, "-hide_banner", "-v", "error", "-y", "-i", str(video),
                        "-stream_loop", "-1", "-i", str(music), "-filter_complex", graph,
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
                        "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(tmp)])
    if code != 0:
        print(f"  ! music failed on {video.name}: {err.strip()[:200]}", file=sys.stderr)
        if tmp.exists():
            tmp.unlink()
        return False
    os.replace(tmp, video)
    return True


def cmd_render(args):
    plan = load_plan(args.plan)
    if plan.get("source"):
        info = probe_media(plan["source"])
    else:
        info = {"path": None, "duration": 0.0, "width": 0, "height": 0, "fps": 0.0,
                "video_codec": None, "has_audio": False, "audio_codec": None,
                "audio_channels": 0, "sample_rate": 0}
        # `aspect: auto` on a slideshow follows the first image's orientation
        first_media = next((m for c in plan["clips"] for m in (c.get("media") or [])
                            if Path(m).exists()), None)
        if first_media:
            try:
                dims = probe_media(first_media)
                info["width"], info["height"] = dims["width"], dims["height"]
            except SystemExit:
                pass
    out_dir = Path(args.out or plan.get("out") or (Path(plan["_path"]).parent / "clips")).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    music = args.music or plan.get("music")
    if music:
        mp = Path(music).expanduser()
        if not mp.is_absolute():
            mp = Path(plan["_path"]).parent / mp
        if mp.exists():
            music = str(mp.resolve())
        else:
            print(f"  ! music not found: {mp}", file=sys.stderr)
            music = None
    work = Path(tempfile.mkdtemp(prefix="tc-render-"))
    plan_style = dict(plan.get("captions_style") or {})
    plan_style["preset"] = args.style or plan_style.get("preset") or "clean"
    opts = {
        "info": info, "out_dir": out_dir, "force": args.force, "aspect": args.aspect,
        "voice": args.voice or plan.get("voice") or "",
        "lang": plan.get("lang") or args.lang, "tts": args.tts,
        "voiceover": not args.no_voiceover, "captions": not args.no_captions,
        "captions_style": plan_style,
        "audio": plan.get("audio") or args.audio, "crf": args.crf, "preset": args.preset,
        "fps": args.fps, "timeout": args.timeout,
        "fit": args.fit or plan.get("fit") or "auto", "dry_run": args.dry_run,
        "srt": args.srt, "thumbnail": args.thumbnail,
    }
    clips = plan["clips"]
    if args.only:
        wanted = {n.strip() for n in args.only.split(",")}
        clips = [c for c in clips if c["name"] in wanted]
        if not clips:
            raise SystemExit(f"--only matched nothing; plan has: "
                             f"{', '.join(c['name'] for c in plan['clips'])}")

    log = sys.stderr if args.json else sys.stdout
    if plan.get("source"):
        print(f"source: {plan['source']} ({info['duration']:.1f}s, "
              f"{info['width']}x{info['height']})", file=log)
    else:
        print(f"source: slideshow ({len(clips)} beats, images only)", file=log)
    plan_aspect = resolve_aspect(plan.get("aspect") or opts["aspect"], info)
    print(f"out:    {out_dir}  ({len(clips)} clips, aspect {plan_aspect})", file=log)

    if args.jobs > 1:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            results = list(pool.map(lambda ic: render_clip(ic[1], plan, opts, work, ic[0]),
                                    enumerate(clips)))
    else:
        results = [render_clip(c, plan, opts, work, i) for i, c in enumerate(clips)]

    ok = [r for r in results if r.get("ok")]
    bad = [r for r in results if not r.get("ok")]

    manifest = {
        "tool": TOOL, "version": VERSION, "plan": plan.get("_path"),
        "source": plan["source"], "aspect": plan_aspect, "fit": opts["fit"],
        "style": opts["captions_style"].get("preset"),
        "created": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "clips": results,
    }
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        # a --only run must not erase what the previous run recorded about the other clips
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8")).get("clips", [])
            fresh = {c["name"] for c in results}
            manifest["clips"] = [c for c in old if c.get("name") not in fresh] + results
            manifest["clips"].sort(key=lambda c: c.get("name", ""))
        except (OSError, ValueError, TypeError):
            pass
    stitch = args.stitch or plan.get("stitch")
    if stitch and len(clips) == 1 and not args.only:
        print("  - single clip: stitch skipped (the clip is the video)", file=sys.stderr)
        stitch = None
    if stitch and args.only:
        print("  ! stitch skipped: --only renders a subset", file=sys.stderr)
    elif stitch and not bad and not args.dry_run:
        name = plan.get("stitch_name") or (stitch if isinstance(stitch, str) else "full")
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", str(name)).strip("-") or "full"
        stitched, err = stitch_clips(clips, results, out_dir, name)
        if stitched:
            manifest["stitched"] = str(stitched)
            print(f"stitched: {stitched}", file=log)
        else:
            print(f"  ! stitch failed: {err}", file=sys.stderr)
            bad.append({"name": name, "error": err})

    if music and not args.dry_run:
        targets = []
        if manifest.get("stitched"):
            targets = [Path(manifest["stitched"])]
        else:
            targets = [Path(r["path"]) for r in results
                       if r.get("ok") and not r.get("skipped") and r.get("path")]
        for target in targets:
            if add_music(target, Path(music), args.music_volume):
                manifest["music"] = str(Path(music))
        if manifest.get("music"):
            print(f"music: {Path(music).name}", file=log)

    credits = plan.get("credits") or []
    if credits and not args.dry_run:
        lines = [f"{c.get('title', '')} - {c.get('creator', '')} ({c.get('license', '')}) "
                 f"{c.get('page') or c.get('url', '')}" for c in credits]
        (out_dir / "credits.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        manifest["credits"] = "credits.txt"

    if not args.dry_run:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps({"ok": not bad, "out_dir": str(out_dir), "clips": results,
                          "stitched": manifest.get("stitched")}, indent=2))
    elif args.brief:
        line = f"{len(ok)}/{len(results)} clips -> {out_dir}"
        if manifest.get("stitched"):
            line += f"  (+ {Path(manifest['stitched']).name})"
        print(line)
    else:
        for r in results:
            if r.get("ok"):
                tag = "skipped" if r.get("skipped") else f"{r['duration']:.1f}s"
                print(f"  [ok] {r['name']}.mp4  {tag}"
                      + (f"  voice={r.get('voice')}" if r.get("voice") else ""))
            else:
                print(f"  [!!] {r['name']}: {r['error'][:300]}", file=sys.stderr)
        print(f"\n{len(ok)}/{len(results)} clips in {out_dir}")
        missing = [r for r in ok if not r.get("skipped") and not r.get("has_audio")]
        if missing:
            print("warning: some outputs have no audio track: "
                  + ", ".join(r["name"] for r in missing), file=sys.stderr)

    if args.keep_temp:
        print(f"temp kept: {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    return 0 if not bad else 1


def cmd_selftest(args):
    """Prove the pipeline works on this machine without touching user files."""
    out = Path(args.out or tempfile.mkdtemp(prefix="tc-selftest-")).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    src = out / "source.mp4"
    print(f"selftest dir: {out}")
    if not src.exists():
        code, _, err = run([FFMPEG, "-hide_banner", "-v", "error", "-y",
                            "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=16",
                            "-f", "lavfi", "-i", "sine=frequency=420:duration=16",
                            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
                            "-shortest", str(src)])
        if code != 0:
            print(f"could not build the test video: {err[:400]}", file=sys.stderr)
            return 1

    plan = {
        "source": src.name,   # relative to the plan file, which lives beside it
        "aspect": "9:16",
        "lang": args.lang,
        "audio": "mix",
        "clips": [
            {"name": "selftest-voiced", "start": 0, "duration": 6,
             "script": "This is the self test. The voice and the captions both come from the same "
                       "pipeline that renders real clips."},
            {"name": "selftest-silent", "start": 8, "duration": 4,
             "script": "", "audio": "source"},
        ],
    }
    plan_path = out / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    ns = argparse.Namespace(plan=str(plan_path), out=str(out / "clips"), force=True,
                            aspect="9:16", voice=None, lang=args.lang, tts=args.tts,
                            no_voiceover=args.no_voiceover, no_captions=False, audio="mix",
                            crf=24, preset="veryfast", fps=None, timeout=600, only=None,
                            jobs=1, json=False, keep_temp=False, fit="blur",
                            dry_run=False, srt=True, thumbnail=True, style="tiktok",
                            stitch=None, brief=False, music=None, music_volume=0.14)
    code = cmd_render(ns)

    checks = []
    for clip in plan["clips"]:
        p = out / "clips" / f"{clip['name']}.mp4"
        exists = p.exists()
        info = probe_media(p) if exists else {}
        checks.append((clip["name"], exists and info.get("width") == 1080
                       and info.get("height") == 1920 and info.get("has_audio")
                       and abs(info.get("duration", 0) - clip["duration"]) < 1.0,
                       f"{info.get('width')}x{info.get('height')} {info.get('duration')}s "
                       f"audio={info.get('has_audio')}" if exists else "missing"))
    print()
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    passed = all(c[1] for c in checks) and code == 0
    print(f"\nselftest {'PASSED' if passed else 'FAILED'}"
          + ("" if args.keep or args.out else f"  (files removed; rerun with --keep to inspect)"))
    if not (args.keep or args.out):
        shutil.rmtree(out, ignore_errors=True)
    return 0 if passed else 1


# ----------------------------------------------------------------------------- main


def main(argv=None):
    # a cp1252 console on Windows dies on any non-latin character; never let that stop a render
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        prog="talkicut", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"{TOOL} {VERSION}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="check this machine and say what to install")
    d.add_argument("--json", action="store_true")
    d.add_argument("--fix", action="store_true", help="install edge-tts if missing")
    d.set_defaults(func=cmd_doctor)

    p = sub.add_parser("probe", help="inspect a video: duration, audio, scene cuts")
    p.add_argument("video")
    p.add_argument("--threshold", type=float, default=0.03)
    p.add_argument("--no-scene", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_probe)

    pl = sub.add_parser("plan", help="scaffold plan.json with beat boundaries")
    pl.add_argument("video")
    pl.add_argument("--beats", type=int, default=4)
    pl.add_argument("--start", type=float)
    pl.add_argument("--end", type=float)
    pl.add_argument("--out", help="defaults to <video>.plan.json")
    pl.add_argument("--aspect", choices=ASPECT_CHOICES,
                    help="default 9:16; 'auto' keeps the recording's orientation (16:9 stays 16:9)")
    pl.add_argument("--lang", default="es")
    pl.add_argument("--threshold", type=float, default=0.03)
    pl.add_argument("--full", action="store_true",
                    help="beats cover the whole video and render stitches them into one file")
    pl.add_argument("--brief", action="store_true", help="one line of output")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=cmd_plan)

    sb = sub.add_parser("storyboard", help="scaffold a plan for a prompt-only video (no footage)")
    sb.add_argument("prompt")
    sb.add_argument("--beats", type=int, default=5)
    sb.add_argument("--seconds", type=float, default=30)
    sb.add_argument("--aspect", default="9:16", choices=ASPECT_CHOICES)
    sb.add_argument("--lang", default="es")
    sb.add_argument("--out")
    sb.add_argument("--json", action="store_true")
    sb.set_defaults(func=cmd_storyboard)

    fe = sub.add_parser("fetch", help="download freely licensed images for a plan's queries")
    fe.add_argument("plan")
    fe.add_argument("--n", type=int, default=2, help="images per clip")
    fe.add_argument("--out", default="media", help="folder next to the plan")
    fe.add_argument("--sheet", action="store_true", help="write a contact sheet of the chosen images")
    fe.add_argument("--music", metavar="QUERY", help="also fetch a freely licensed music track")
    fe.set_defaults(func=cmd_fetch)

    s = sub.add_parser("sheet", help="timestamped contact sheets")
    s.add_argument("video")
    s.add_argument("--every", type=float, default=3.0, help="seconds between frames")
    s.add_argument("--out", default="./sheets")
    s.add_argument("--cols", type=int, default=5)
    s.add_argument("--rows", type=int, default=3)
    s.add_argument("--tile-width", type=int, default=384)
    s.add_argument("--max-sheets", type=int, default=0,
                   help="cap the number of sheets; fewer images to read")
    s.add_argument("--no-labels", action="store_true")
    s.add_argument("--keep-frames", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_sheet)

    o = sub.add_parser("ocr", help="OCR sampled frames (for models without vision)")
    o.add_argument("video")
    o.add_argument("--every", type=float, default=4.0)
    o.add_argument("--lang", default="eng+spa")
    o.add_argument("--vertical-span", type=float, default=0.72,
                   help="fraction of frame height to OCR, centred")
    o.add_argument("--out")
    o.add_argument("--json", action="store_true")
    o.add_argument("--brief", action="store_true")
    o.set_defaults(func=cmd_ocr)

    r = sub.add_parser("render", help="render clips from a plan.json")
    r.add_argument("plan")
    r.add_argument("--out")
    r.add_argument("--aspect", default="9:16", choices=ASPECT_CHOICES,
                   help="9:16 shorts by default; 'auto' keeps the source orientation")
    r.add_argument("--voice", help="edge voice id or system voice name")
    r.add_argument("--lang", default="es", help="language code: es, en, pt, fr...")
    r.add_argument("--tts", default="auto", choices=["auto", "edge", "system", "none"])
    r.add_argument("--audio", default="tts", choices=["tts", "source", "mix"],
                   help="tts voiceover only, original audio only, or source ducked under the voice")
    r.add_argument("--only", help="comma-separated clip names")
    r.add_argument("--force", action="store_true", help="re-render clips that already exist")
    r.add_argument("--jobs", type=int, default=1)
    r.add_argument("--fps", type=float)
    r.add_argument("--crf", type=int, default=21)
    r.add_argument("--preset", default="veryfast")
    r.add_argument("--style", choices=list(STYLE_PRESETS),
                   help="caption preset: clean, tiktok (above the UI), bold")
    r.add_argument("--fit", choices=["auto", "blur", "cover", "pad"], default=None,
                   help="how the source fills the frame (default: auto - straight when the shape "
                        "matches, blur otherwise; stills pick per image)")
    r.add_argument("--timeout", type=int, default=1800, help="per-clip ffmpeg timeout (s)")
    r.add_argument("--no-voiceover", action="store_true")
    r.add_argument("--no-captions", action="store_true")
    r.add_argument("--srt", action="store_true", help="also write a .srt next to each clip")
    r.add_argument("--thumbnail", action="store_true", help="also write a .jpg cover per clip")
    r.add_argument("--dry-run", action="store_true", help="print the ffmpeg command, render nothing")
    r.add_argument("--music", help="audio track to loop under the narration (path)")
    r.add_argument("--music-volume", type=float, default=0.14,
                   help="music level under the voice (default: 0.14)")
    r.add_argument("--stitch", nargs="?", const="full", metavar="NAME",
                   help="join all rendered clips into NAME.mp4 (plan: \"stitch\": true)")
    r.add_argument("--brief", action="store_true", help="one line of output")
    r.add_argument("--keep-temp", action="store_true")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_render)

    v = sub.add_parser("verify", help="check a folder of clips for silent failures")
    v.add_argument("dir")
    v.add_argument("--min-volume", type=float, default=-24.0, dest="min_volume")
    v.add_argument("--max-volume", type=float, default=-9.0, dest="max_volume")
    v.add_argument("--json", action="store_true")
    v.add_argument("--brief", action="store_true")
    v.set_defaults(func=cmd_verify)

    t = sub.add_parser("selftest", help="render a synthetic video end to end")
    t.add_argument("--out")
    t.add_argument("--lang", default="en")
    t.add_argument("--tts", default="auto", choices=["auto", "edge", "system", "none"])
    t.add_argument("--no-voiceover", action="store_true")
    t.add_argument("--keep", action="store_true")
    t.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    if not FFMPEG or not FFPROBE:
        print("ffmpeg/ffprobe not found on PATH.\n"
              "  Windows: winget install Gyan.FFmpeg\n"
              "  macOS:   brew install ffmpeg\n"
              "  Linux:   sudo apt install ffmpeg\n"
              "or set FFMPEG=/path/to/ffmpeg and FFPROBE=/path/to/ffprobe",
              file=sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
