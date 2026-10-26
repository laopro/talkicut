---
name: talkicut
description: Turns screen recordings or a bare topic into finished videos with TTS narration, burned captions, motion and optional music, using only Python + ffmpeg. Use for reels, shorts, tutorials, demos, voiceover, subtitles, or when AI clippers fail on silent footage. Triggers: screen recording, grabación de pantalla, tutorial, demo, clip, subtítulos, ponerle voz, reel, 9:16, 16:9, talkicut.
---

# talkicut

Silent recording (or just a topic) in, finished video out. You read the footage, pick beats, write narration; the script renders. Any OS, any model, no API keys.

## Pick the shape

| Wants | Do |
|---|---|
| reels / shorts / TikTok | 2–5 clips, 15–35 s, `--aspect 9:16` |
| YouTube / course | one clip or ordered beats, `--aspect auto` |
| "edit the whole video" | beats over the full recording + `"stitch": true` |
| no footage, just a topic | `storyboard` → research → `fetch` → `render` |

Ambiguous? Ask at most 3 questions with defaults (destination, length, voice). Never ask for timestamps or a transcript: `probe` and `sheet` do that.

## Commands (from the skill folder)

```bash
python scripts/talkicut.py doctor
python scripts/talkicut.py probe video.mp4 --json
python scripts/talkicut.py sheet video.mp4 --max-sheets 2 --every 6
python scripts/talkicut.py plan video.mp4 --beats 4 --full
python scripts/talkicut.py render video.plan.json --brief
python scripts/talkicut.py verify clips --brief
```

Look at one or two sheet frames, say what happens, and that sentence is the narration. No vision: `ocr video.mp4 --every 6 --out ocr.json`, then grep it. No cuts means one take: cut by content.

## Prompt only (no footage)

1. Research with web tools; keep the URLs.
2. `storyboard "prompt" --beats 5 --seconds 30 --out reel.plan.json`
3. Fill each `script` (14–16 chars/s, one idea) and a literal English `query`.
4. `fetch reel.plan.json --n 1 --music "NCS progressive house"` → images, credits, track. Check `media/sheet.jpg`.
5. `render --stitch` + `verify`.

## Plan rules

- 14–16 chars/s, aim ~85% of the clip; too long means cut words, not tempo.
- Write for the ear; never invent labels, numbers or features.
- `audio`: `tts` | `source` | `mix`. `aspect`: `auto` | `9:16` | `4:5` | `1:1` | `16:9`. `title` burns a hook for ~3 s.
- Full schema: `references/plan-schema.md` (only open it when a field is unclear).

## Render flags

`--audio tts|source|mix`, `--tts auto|edge|system|none`, `--voice`, `--lang`, `--aspect`, `--fit auto|blur|cover|pad`, `--style clean|tiktok|bold`, `--music file|url`, `--music-volume 0.08`, `--stitch`, `--srt`, `--thumbnail`, `--only a,b`, `--force`, `--jobs N`, `--dry-run`, `--json`, `--brief`.

Output: `clips/` beside the plan + `manifest.json` + `credits.txt`.

## Token budget

- `--brief` by default; `--json` only for fields you need.
- One sheet, ~15 frames, instead of six images. Grep `ocr.json`; never paste it whole.
- Edit the plan and re-render with `--only name --force`; do not regenerate untouched clips.
- Do not re-read rendered frames: `manifest.json` has duration, size, audio.
- Open a reference file only when the task actually needs it.

## Fixes

| Symptom | Fix |
|---|---|
| `edge-tts failed` | `--tts system` (System.Speech / `say` / `espeak-ng`) |
| `filter ass missing` | ffmpeg build without libass: captions skipped, install a full build |
| captions drift or stack | keep `max_chars` ≤ 30 |
| stitch fails | render all clips in one run; `--only` cannot stitch a subset |
| `fetch` finds nothing | concrete English nouns ("data center servers"), or a text-only beat |
| image off-topic | rewrite the query; Wikimedia matches words, not meaning |

## Files

- `scripts/talkicut.py` — doctor, probe, plan, storyboard, fetch, sheet, ocr, render, verify, selftest.
- `references/` — `plan-schema` (fields), `auto-video` (prompt-only), `editing` (full edits), `narration`, `platforms`, `ffmpeg-notes`.
