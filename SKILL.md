---
name: talkicut
description: Makes finished short videos (reels, shorts, TikTok, YouTube) from a bare topic or a screen recording - spoken hook, real on-topic footage and images from the web, animated data charts, word-by-word captions, NCS music - using only Python + ffmpeg, no API keys. Triggers: video, reel, short, TikTok, hazme un video, video sobre, edit this recording, grabación de pantalla, subtítulos, ponerle voz, 9:16, talkicut.
---

# talkicut

You research and write one small JSON plan; one command renders the finished video. Any OS, any model, no keys.

`T` below = `python3 <folder of this SKILL.md>/scripts/talkicut.py` (use the absolute path; work in any empty folder).

## Topic -> video

1. Research with your web tools, then write `v.plan.json`:

```json
{
  "angle": "Most people think X, but actually Y, because Z.",
  "lang": "es",
  "voice": "es-MX-JorgeNeural",
  "clips": [
    {"title": "Casi nadie sabe esto:", "script": "El juego que todos dan por muerto es el más vendido de la historia.", "video": "minecraft survival gameplay no commentary 4k"},
    {"script": "Ya pasó los trescientos millones de copias.", "chart": {"type": "counter", "value": 300000000, "label": "copias vendidas", "source": "Mojang, 2023"}},
    {"script": "Lleva quince años con actualizaciones gratis. ¿Tú todavía lo juegas?", "query": "minecraft creeper steve wallpaper"}
  ]
}
```

2. `T make v.plan.json --out ~/video.mp4`

`make` does the rest: installs anything missing (neural voice, yt-dlp, Pillow), downloads the visuals and an NCS track, speaks, captions, crossfades. Its last line must read `voice=edge, music=yes`; a `!` line says what to fix. Then open `media/sheet.jpg` once: wrong picture -> delete that beat's `media`, change its `query`, `make` again.

Defaults you do not write: 9:16, each beat as long as its voice, hook spoken on beat 1, music, stereo -16 LUFS. Optional: `"aspect": "16:9"`, `"music_query": "NCS chill"`, per-clip `"name"`, `"duration"` (a maximum).

## Angle first

A list of true facts is boring. Research until `angle` is one sentence: **"Most people think X, but actually Y, because Z."** Look for a number that contradicts intuition, the cause behind a famous fact, a near-failure or reversal, what it costs the viewer, or a myth the data contradicts.

| Topic | Shape that works |
|---|---|
| news / trend | what changed -> why now -> who wins/loses -> what it means for you |
| product / tech | the claim -> the catch -> the number that proves it -> buy or wait |
| history / person | the moment it almost failed -> the decision -> the outcome today |
| science / nature | the weird fact -> how it works -> the scale (chart) |
| how-to | the mistake everyone makes -> the fix -> the result |

Order: hook (the tension, not the topic name) -> context -> evidence (chart) -> twist -> a question to the viewer.
Banned: definitions everyone knows, "Hoy hablaremos de", unlinked facts, ending on a number.

## Beats

3-6 beats, one idea each, 60-110 characters of `script`. Each beat has ONE visual:

| visual | when | example |
|---|---|---|
| `"video"` | anything that moves: games, sports, places, products | `"gta v gameplay no commentary 4k"` |
| `"query"` | a specific thing to show | `"nvidia rtx 5090 card"` |
| `"chart"` | any number, ranking, comparison, trend | below |
| none | a punchline or quote | big animated text |

- Beat 1 `title` is the spoken hook: `¿Sabías que...` / `Nadie te dijo esto:` / `Lo que no te cuentan:` / `El error que casi todos cometen:` - then its `script` delivers the fact.
- Mix visuals (footage -> chart -> image); never three photos in a row.
- Searches in English: concrete nouns + the brand or name.
- Write what is said, not what is typed: `Xbox Series X y S`, `19 de noviembre`; no `|`, `/`, `&`, no abbreviations.
- `voice` sets the accent: `es-MX-JorgeNeural`, `es-AR-TomasNeural`, `es-ES-AlvaroNeural`, `en-US-AndrewNeural`, `pt-BR-AntonioNeural`. Without it, `lang` picks one.
- Never invent numbers. Every chart value needs a `source`; it is printed on screen.

```json
"chart": {"type": "counter", "value": 300000000, "label": "copias vendidas", "source": "Mojang, 2023"}
"chart": {"type": "bar", "title": "Millones de copias", "labels": ["Minecraft", "GTA V"], "values": [300, 200], "compact": false, "source": "..."}
"chart": {"type": "line", "title": "Precio RAM 32 GB (USD)", "labels": ["2024", "2025", "2026"], "values": [90, 120, 450], "prefix": "$", "source": "..."}
"chart": {"type": "table", "title": "...", "columns": ["Juego", "Año"], "rows": [["Minecraft", "2011"]], "source": "..."}
```

## Screen recording -> clips

```bash
T probe video.mp4 --json
T sheet video.mp4 --max-sheets 2 --every 6     # no vision: T ocr video.mp4 --every 6 --out ocr.json, then grep it
T plan video.mp4 --beats 4 --full              # writes video.plan.json; fill each beat's script
T render video.plan.json --stitch --brief
```

Say what happens on screen in each beat: that sentence is the narration. Details: `references/editing.md`.

## Flags

`make`: `--style tiktok|clean|bold`, `--voice NAME`, `--music "NCS ..."`, `--from wiki` (free-licence images only). `render`: `--only name --force` (one beat), `--aspect 16:9`, `--srt`, `--thumbnail`. `T doctor --fix` checks and repairs the machine.

## Fixes

| Symptom | Fix |
|---|---|
| `ROBOTIC OFFLINE VOICE` / `voice=system` | never deliver it: `T doctor --fix`, check the network, `make` again |
| `music=NO` / `no footage` | `T doctor --fix` (yt-dlp), or make the search more concrete |
| beat renders as text, no picture | its search found nothing: rewrite `query`/`video` with concrete English nouns |
| wrong / watermarked picture | delete that beat's `media`, change `query`, `make` again |
| `filter ass missing` | install a full ffmpeg build (captions need libass) |
| chart failed | `values` must be numbers |

## Token budget

Write the plan in one go, run `make` once, look at `media/sheet.jpg` once. Do not read `manifest.json`, `ocr.json` or rendered frames. Open `references/plan-schema.md` only when a field is unclear.
