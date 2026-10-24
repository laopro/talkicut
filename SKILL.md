---
name: talkicut
description: Turn screen recordings, tutorials, demos and webinars - silent ones included - into short clips or one fully edited video, with TTS narration and burned captions. Use for vertical shorts, horizontal edits, voiceover, subtitles, or when SupoClip/OpusClip finds nothing because the source has no audio. Triggers: screen recording, grabación de pantalla, tutorial, demo, clip, subtítulos, ponerle voz, sin audio, editar el video completo, reels, shorts, 9:16, 16:9, talkicut.
---

# talkicut

Silent screen recording in, voiced video out. Built for the case AI clippers fail on: **no audio means no transcript**, so nothing can be "auto-selected". You read the footage, choose the cuts, write the narration; the script does the rest.

Works on Windows, macOS and Linux, under any agent that can run a shell, with any model - including models that cannot see images.

## Pick the shape first

| The user wants | Do this |
|---|---|
| Shorts / reels / TikTok / "clips" | 2–5 clips, 15–35 s each, `--aspect 9:16` (default) |
| A horizontal video, YouTube, a course | one clip or in-order segments, `--aspect auto` (keeps 16:9) |
| "Edit the whole video" | beats covering the full recording + `"stitch": true` → one file |

If it is not obvious, ask **at most three questions** and offer defaults so the user can answer with one word:

1. "¿Para dónde es: reels/shorts vertical, YouTube horizontal, o el video completo editado?" (default: 3 vertical clips)
2. "¿Cuánto dura el resultado?" (default: 20–30 s per clip, or the original length for a full edit)
3. "¿Voz en español neutro/rioplatense, o preferís sin voz y solo cortes?" (default: the voice for their language)

Do not ask for timestamps, transcript or scene list: that is your job, from `probe` and `sheet`.

## 0. Check the machine (once)

```bash
python scripts/talkicut.py doctor          # add --fix to install edge-tts
```

If ffmpeg is missing: `winget install Gyan.FFmpeg` / `brew install ffmpeg` / `sudo apt install ffmpeg`. Captions need a build with `libass`; `doctor` says whether yours has it. Set `FFMPEG`/`FFPROBE` if the binaries live elsewhere.

## 1. Read the footage

```bash
python scripts/talkicut.py probe video.mp4        # duration, audio, scene cuts
python scripts/talkicut.py sheet video.mp4        # contact sheets with timestamps
```

Look at the sheets and say out loud what happens: a form filled, a modal, output appearing. That sentence is your narration. No scene cuts means one continuous take - cut by content, not by edit points.

No vision? Use `ocr video.mp4 --every 5 --out ocr.json` (needs tesseract) and confirm the beats with the user. Coarser beats are fine; invented UI is not.

## 2. Build the plan

```bash
python scripts/talkicut.py plan video.mp4 --beats 4 --full
```

`plan` writes `video.plan.json` with beats snapped to real cuts and a character budget per beat. `--full` makes the beats cover the whole video and marks it for stitching. Empty `script` fields are the part only you write.

```json
{
  "source": "demo.mp4", "aspect": "auto", "lang": "es", "audio": "tts",
  "stitch": true,
  "clips": [
    {"name": "01-hook", "start": 0, "duration": 18, "title": "Esto te ahorra media hora", "script": "..."},
    {"name": "02-paso", "start": 20, "duration": 22, "script": "..."}
  ]
}
```

- 14–16 characters per second; aim for ~85% of the clip so the voice is not squeezed.
- Write for the ear. Say what matters, not what the cursor does.
- Never invent labels, numbers or features.
- `audio`: `tts` replaces the sound, `source` keeps it (no narration), `mix` ducks it under the voice.
- `aspect`: omit or `auto` to keep the recording's shape; `9:16`, `4:5`, `1:1` to reframe.
- `title` burns a hook for the first ~3 s.

Every field: `references/plan-schema.md`. Full-video workflow: `references/editing.md`.

## 3. Render

```bash
python scripts/talkicut.py render plan.json --brief
```

| Need | Flag |
|---|---|
| narration / original audio / both | `--audio tts \| source \| mix` |
| voice engine and voice | `--tts auto\|edge\|system\|none`, `--voice`, `--lang` |
| frame shape | `--aspect auto \| 9:16 \| 4:5 \| 1:1 \| 16:9` |
| framing | `--fit blur \| cover \| pad` (matching shapes scale straight, no blur) |
| caption look | `--style clean \| tiktok \| bold` |
| extras | `--srt`, `--thumbnail`, `--dry-run`, `--json` |
| one file from all clips | `--stitch` or plan `"stitch": true` |
| subset / overwrite / parallel | `--only a,b`, `--force`, `--jobs 4` |

Output goes to `clips/` beside the plan, with `manifest.json`.

## 4. Verify before delivering

```bash
python scripts/talkicut.py verify clips --brief
```

Checks every mp4: streams present, length sane, shape right, loudness between −24 and −9 dB. Then look at one frame with a caption:

```bash
ffmpeg -y -ss 4 -i clips/01-hook.mp4 -frames:v 1 preview.jpg
```

Caption inside the frame, not colliding with UI text. `selftest` proves the pipeline itself works on this machine.

## Cheapest path (token budget)

- `probe --json` and `plan --json` instead of reading whole files; both are small.
- One `sheet` with `--max-sheets 2 --every 6` instead of six images: ~15 frames still read the flow.
- `ocr --every 6 --out ocr.json`, then `grep` the json; never paste the whole transcript into the conversation.
- `render --brief` and `verify --brief` print one line each; `--json` only when you need fields.
- Never re-read a rendered frame unless the user asks: the manifest already says duration, size, audio and captions per clip.
- Keep the plan in one file and edit it; do not regenerate clips you did not change (`--only name --force`).

## When something is missing

| Symptom | Fix |
|---|---|
| `edge-tts failed` (offline/proxy) | `--tts system`: System.Speech (Windows), `say` (macOS), `espeak-ng` (Linux). Captions switch to proportional timing. |
| `filter ass missing` | build without libass (Homebrew ffmpeg 9 is one): captions are skipped with a warning; install a full build to burn them. |
| Captions drift or stack | keep `max_chars` ≤ 30; overlap is clamped to the next line. |
| Voice does not fit | the script is too long: cut words, not tempo (+35% is the limit). |
| Stitch fails | render all clips in one run; `--only` cannot stitch a subset. |
| 4K/60 footage | `--preset faster --crf 23`; keep libx264, hardware encoders are not worth the breakage. |

## Files

- `scripts/talkicut.py` — doctor, probe, plan, sheet, ocr, render, verify, selftest. Only ffmpeg + Python 3.9+; `edge-tts` optional.
- `references/editing.md` — full-video editing, horizontal output, stitching, pacing.
- `references/plan-schema.md` — every field and default.
- `references/narration.md` — pacing math, hooks, per-language notes.
- `references/platforms.md` — install matrix, voices per OS, known breakage.
- `references/ffmpeg-notes.md` — filter chains and the bugs behind them.
