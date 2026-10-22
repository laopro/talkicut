---
name: talkicut
description: Give a silent screen recording a voice. Turns screen recordings, tutorials and product demos - including silent ones with no audio track - into short vertical clips with a TTS voiceover and burned captions. Use whenever someone hands over a screen recording, Loom/OBS export, demo, webinar or tutorial video and wants clips, Shorts/Reels/TikTok cuts, vertical versions, narration, subtitles, or "hacé algo con este video". Also use when SupoClip, OpusClip or a transcription-based clipper returns nothing because the video has no audio. Triggers: screen recording, grabación de pantalla, tutorial, demo, clip vertical, subtítulos, ponerle voz, sin audio, 9:16, reels, shorts, screenflow, talkicut.
---

# talkicut

A screen recording has no faces to track, and often no audio at all - so the usual clipper pipeline (transcribe → find highlights → auto-crop to faces) has nothing to work with. What works instead is: **read the recording visually, choose the story beats yourself, write the narration, then render with ffmpeg**. The name is the joke: silent film, meet the talkicut.

This skill does the mechanical parts. The two things that need judgment stay yours: where the beats are, and what the narration says.

It runs the same on Windows, macOS and Linux, under any agent that can execute shell commands, with any model - including models that cannot see images (there is a text-only path below).

## 0. Check the machine first (once per machine, ~5 s)

Commands below use `python`; on macOS/Linux use `python3` if `python` is not Python 3.

```bash
python scripts/talkicut.py doctor
```

Reports ffmpeg, which filters the build actually has, fonts, and which TTS backends are available, with the install command for the current OS. `doctor --fix` installs `edge-tts`.

If `ffmpeg` is missing: `winget install Gyan.FFmpeg` (Windows), `brew install ffmpeg` (macOS), `sudo apt install ffmpeg` (Debian/Ubuntu). Set `FFMPEG`/`FFPROBE` env vars if the binaries live somewhere unusual.

## 1. Probe before assuming

```bash
python scripts/talkicut.py probe video.mp4
```

Two facts change everything:

- **No audio stream** → no transcription is possible anywhere, by anything. You write the narration from the visuals. This is the case the AI clippers fail on.
- **No scene cuts** → one continuous take. Beat boundaries come from what is on screen, not from edit points.

`--json` gives the same data machine-readable.

## 2. Read the recording

**If you can see images** (preferred - you get context, not just text):

```bash
python scripts/talkicut.py sheet video.mp4 --every 3
```

That writes ~15-frame contact sheets with timestamps plus `sheet_meta.json`. Open them and read what the app is doing: a form being filled, a modal opening, output appearing, a result being navigated. Say it out loud - you need those words for the narration anyway, and it stops you from inventing features that are not on screen.

**If you cannot see images**, or the text is too small to read reliably:

```bash
python scripts/talkicut.py ocr video.mp4 --every 4 --lang eng+spa --out ocr.json
```

That OCRs a centre crop of each frame (skipping wallpapers and taskbars) and prints a timestamped transcript of the UI. It requires `tesseract`, and `doctor` tells you how to install it. OCR gives you labels but not layout or intent - when the user is available, confirm the beats with them instead of guessing.

Aim for 3-5 clips of 15-35 s. One idea per clip beats a 60 s clip with three.

## 3. Scaffold the plan

```bash
python scripts/talkicut.py plan video.mp4 --beats 4 --start 0 --end 60
```

Writes `video.plan.json` with equal beats snapped to the nearest real scene cut, and prints the character budget for each beat. Every `script` is empty on purpose: that is the part only you can write. Fill them in, and add a `title` when the clip needs a hook in the first seconds.

```json
{
  "source": "demo.mp4",
  "aspect": "9:16",
  "lang": "es",
  "voice": "es-AR-TomasNeural",
  "audio": "tts",
  "fit": "blur",
  "clips": [
    {"name": "01-configurar-api-key", "start": 0.5, "duration": 20,
     "title": "Esto te ahorra media hora",
     "script": "Arrancamos abriendo la app. Lo primero es configurar la clave de API: ..."},
    {"name": "02-generar", "start": 78, "duration": 18,
     "script": "Enviamos el pedido y el cuestionario se arma en vivo."}
  ]
}
```

`source` is resolved relative to the plan file, so plans stay portable between machines. Every field and its defaults: `references/plan-schema.md`.

Narration rules that survive contact with TTS:

- Write for the ear, in the language the user speaks. Short sentences, contractions, no written-prose rhythm.
- 14–16 characters per second is a natural pace. Aim for ~85% of the clip duration, so the voice is not stretched and the clip does not end mid-word.
- Say what is happening and why it matters. Do not narrate clicks — the viewer can see the cursor.
- Never invent UI, numbers or features. If a label is unreadable, describe the action generically.
- Leave the last second or two without speech.

More: `references/narration.md`.

## 4. Render

```bash
python scripts/talkicut.py render plan.json
```

Output goes to `clips/` next to the plan. Per clip it synthesizes the voice, aligns timings into an `.ass` subtitle track, composites the recording into the frame, burns captions, adds an optional hook title, normalizes audio to −16 LUFS, and writes `manifest.json` for the calling agent.

| Flag | When you need it |
|---|---|
| `--audio tts \| source \| mix` | replace the original audio, keep it, or duck it under the narration |
| `--tts auto \| edge \| system \| none` | `auto` tries edge-tts (best voice) then the OS voice |
| `--voice` / `--lang` | pick a specific edge voice, or a language for the offline voice |
| `--aspect 9:16 \| 1:1 \| 4:5 \| 16:9` | per plan or per clip (`"aspect"` on a clip overrides) |
| `--fit blur \| cover \| pad` | blurred fill (keeps every pixel), centre crop (fuller frame), or flat bars |
| `--style clean \| tiktok \| bold` | caption preset; `tiktok` sits above the platform UI, `bold` is the loud one |
| `--srt` / `--thumbnail` | companion `.srt` and `.jpg` cover per clip |
| `--dry-run` | print the exact ffmpeg command, render nothing |
| `--no-voiceover` / `--no-captions` | render the visuals only |
| `--only a,b` `--force` `--jobs 4` | re-render a subset, overwrite existing, render in parallel |
| `--json` | machine-readable result for the calling agent |

Caption size, position and colors can also be set per plan or per clip with `"captions_style"`; `--style` is just the preset name plus overrides.

## 5. Verify — a broken render is silent about being broken

```bash
python scripts/talkicut.py verify clips
```

Checks every `.mp4` in the folder: video and audio streams present, duration sane, resolution matching the aspect, mean volume between −24 and −9 dB (defaults). Exits non-zero and names the clip when something is wrong. `--json` for the calling agent.

Then look at one frame where a caption is visible:

```bash
ffmpeg -y -ss 4 -i clips/01-*.mp4 -frames:v 1 preview.jpg
```

The caption must not collide with UI text, and must not be cut off at the edges. This is the step that catches 90% of the mistakes.

`python scripts/talkicut.py selftest` does the whole pipeline end to end on a synthetic video, so you can tell "my plan is wrong" apart from "this machine is broken".

## When something is missing

| Symptom | Do this |
|---|---|
| `ffmpeg/ffprobe not found` | see §0; or set `FFMPEG`/`FFPROBE` |
| `edge-tts failed` (offline, proxy, service change) | `--tts system` uses the OS voice: PowerShell System.Speech (Windows), `say` (macOS), `espeak-ng` (Linux). No network, no word timings — captions fall back to proportional timing automatically. |
| `filter ass missing` | that ffmpeg build has no libass: captions are skipped with a warning. Install a full build (gyan.dev, evermeet, distro package). |
| Captions drift or stack | check `sheet_meta.json` timings; keep `max_chars` ≤ 30. Overlap is prevented by clamping each line to the next one's start. |
| Caption text runs off screen | libass wraps inside the margins; lower `"size"` or `max_chars` in `captions_style`, or pick `--style clean`. |
| Voice does not fit the clip | the script is too long for that duration — cut words, not tempo. Rate is pushed up to +35% before giving up. |
| Video turns out to be 4K/60 | fine, but `--preset faster --crf 23` keeps render time sane. |
| Plan has unicode/space paths | supported: source paths are resolved relative to the plan, and subtitle files are passed to ffmpeg relative to a temp cwd so no shell escaping is involved. |

## Why it is built this way

- **Blurred background fill instead of cropping.** Screen content is landscape; cropping to 9:16 destroys the UI. Scaling the frame to the target width and filling the rest with a blurred copy of itself keeps every pixel. `--fit cover` exists for footage that can lose its edges, `--fit pad` for flat backgrounds.
- **Captions after the overlay.** libass maps `PlayResX/Y` onto whatever frame it receives; applied before the overlay (a short foreground strip) captions come out microscopic.
- **Rate fitting, not time-stretching.** Re-synthesizing at a higher rate keeps the voice natural; `atempo` makes TTS sound drunk. If +35% still does not fit, the script is too long.
- **A silent audio track is not optional.** Some platforms and schedulers reject video-only files, so every output gets an AAC track.
- **Capability detection, not version checks.** The script asks ffmpeg which filters exist and asks the OS which voices exist, then degrades in a way the caller can see in `--json`.
- **One subtitle source for burn-in and `.srt`.** The same grouped lines feed libass and the `.srt`, so the exported captions match the picture exactly.

## Files

- `scripts/talkicut.py` — doctor, probe, plan, sheet, ocr, render, verify, selftest. No dependencies beyond ffmpeg and Python 3.9+; `edge-tts` is optional.
- `references/plan-schema.md` — every field, defaults, examples.
- `references/narration.md` — pacing math, per-language notes, hooks and endings.
- `references/platforms.md` — install matrix, voice names per OS, common breakage.
- `references/ffmpeg-notes.md` — filter chains and the bugs that cost time.
- `assets/plan.example.json` — copy-paste starting point.
