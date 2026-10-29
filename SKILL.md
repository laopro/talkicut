---
name: talkicut
description: Makes finished short videos (reels, shorts, TikTok, YouTube) from a bare topic or a screen recording - spoken hook, real on-topic footage and images from the web, animated data charts, word-by-word captions, NCS music - using only Python + ffmpeg, no API keys. Triggers: video, reel, short, TikTok, hazme un video, video sobre, edit this recording, grabación de pantalla, subtítulos, ponerle voz, 9:16, talkicut.
---

# talkicut

You write the plan (research, script, what to show); the script finds the visuals and renders. Any OS, any model, no keys.

## Topic only (most requests) - 3 steps

```bash
python scripts/talkicut.py storyboard "tema" --beats 4 --seconds 25 --out v.plan.json
# fill v.plan.json (rules below)
python scripts/talkicut.py make v.plan.json --out ~/Desktop/video.mp4
```

`make` downloads visuals + NCS music, renders, crossfades the beats and copies the result. Then open `media/sheet.jpg` once: a wrong picture -> clear that beat's `media`, change its `query`, run `make` again.

## Angle first (any topic)

A list of true facts is boring. Before any beat, research until you can fill `angle` with one sentence:
**"Most people think X, but actually Y, because Z."** Can't? Research more; don't write yet.

Where angles hide, for any subject:
- a number that contradicts intuition (scale, cost, speed, odds)
- the cause behind a famous fact, or who actually profits
- a near-failure, a reversal, a "almost didn't happen"
- what it means for the viewer (money, time, health, their phone, their job)
- a myth most people repeat, and what the data says

| Topic type | Shape that works |
|---|---|
| news / trend | what changed -> why now -> who wins/loses -> what it means for you |
| product / tech | the claim -> the catch -> the number that proves it -> buy or wait |
| history / person | the moment it almost failed -> the decision -> the outcome today |
| science / nature | the weird fact -> how it works in one image -> the scale (chart) |
| how-to / tips | the mistake everyone makes -> the fix -> the result |

Story order: hook = the tension (not the topic name) -> context in one beat -> evidence (chart) -> the twist/answer -> a question to the viewer. Each beat must make the next one necessary.

Banned: definitions everyone knows, "es muy popular/famoso", opening with "Hoy hablaremos de", facts with no link between them, ending on a number.

## Filling the plan

Each beat: a `script` (what the voice says, 14-16 chars per second of `duration`) and ONE visual:

| visual | when | example |
|---|---|---|
| `"video": "..."` | anything that moves: games, sports, places, products, people | `"minecraft survival gameplay no commentary 4k"` |
| `"query": "..."` | a specific thing to show | `"nvidia rtx 5090 card"` |
| `"chart": {...}` | any number, ranking, comparison, trend | see below |
| nothing | a punchline or quote | big animated text |

- Beat 1 `title` is the **spoken hook** (pre-filled from a bank; keep or swap). Its `script` then delivers the surprising fact.
- Mix visuals: footage -> chart -> image beats; never three photos in a row.
- Last beat ends on a question or a call to action (`¿Tú qué opinas?`), never on a flat number.
- Searches in English, concrete nouns + the brand/name (`"GTA V gameplay"`, not `"videogames"`).
- 3-6 beats for 15-40 s. One idea per beat. Write for the ear; never invent numbers.

### Charts (real data only)

Research with your web tools first; every value needs a `source` (it is printed on screen).

```json
"chart": {"type": "counter", "value": 300000000, "label": "copias vendidas", "source": "Mojang, 2023"}
"chart": {"type": "bar", "title": "Millones de copias", "labels": ["Minecraft", "GTA V"], "values": [300, 200], "compact": false, "source": "..."}
"chart": {"type": "line", "title": "Precio RAM 32 GB (USD)", "labels": ["2024", "2025", "2026"], "values": [90, 120, 450], "prefix": "$", "source": "..."}
"chart": {"type": "table", "title": "...", "columns": ["Juego", "Año", "Ventas"], "rows": [["Minecraft", "2011", "300 M"]], "source": "..."}
```

## Screen recording / footage

```bash
python scripts/talkicut.py probe video.mp4 --json
python scripts/talkicut.py sheet video.mp4 --max-sheets 2 --every 6
python scripts/talkicut.py plan video.mp4 --beats 4 --full
python scripts/talkicut.py render video.plan.json --stitch --brief
```

Look at one or two sheet frames, say what happens: that sentence is the narration. No vision: `ocr video.mp4 --every 6 --out ocr.json`, then grep it. Chart beats work here too.

## Useful flags

`make|render`: `--style tiktok|clean|bold`, `--voice es-MX-JorgeNeural`. `fetch`: `--from wiki` (free licences only), `--music "NCS ..."`, `--n 2`. `render`: `--only name --force` re-renders one beat, `--aspect 16:9`, `--srt`, `--thumbnail`.

## Token budget

- `make` + `--brief` output; never paste `ocr.json` or `manifest.json` whole.
- Look at `media/sheet.jpg` once, not every image; do not re-read rendered frames.
- Open `references/plan-schema.md` only when a field is unclear.

## Fixes

| Symptom | Fix |
|---|---|
| `edge-tts failed` | `--tts system` |
| `filter ass missing` | install a full ffmpeg build (captions need libass) |
| beat renders as text, no picture | its search found nothing usable: rewrite `query`/`video` with concrete English nouns |
| wrong / watermarked picture | clear that beat's `media`, change `query`, `make` again |
| `no footage` | `yt-dlp` missing (`pip install yt-dlp`) or the search is too vague |
| chart failed | Pillow missing (`pip install pillow`) or `values` not numbers |

## Files

- `scripts/talkicut.py` - doctor, storyboard, fetch, make, render, verify, probe, plan, sheet, ocr, selftest.
- `assets/topic.plan.example.json` - a complete topic-only plan to copy.
- `references/` - `plan-schema` (every field), `auto-video` (topic-only details), `editing`, `narration`, `platforms`, `ffmpeg-notes`.
