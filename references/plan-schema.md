# plan.json schema

`clips` is required. `source` is required unless the clips bring their own `media`, `query` or `script`: then the plan renders as a slideshow, with no source video.

```json
{
  "source": "demo.mp4",
  "out": "clips",
  "aspect": "9:16",
  "lang": "es",
  "voice": "es-AR-TomasNeural",
  "audio": "tts",
  "fit": "blur",
  "stitch": false,
  "captions_style": {"preset": "tiktok", "size": 58, "color": "#FFFFFF", "max_chars": 30},
  "clips": [
    {"name": "01-hook", "start": 0.5, "duration": 20, "title": "Mira esto", "script": "..."}
  ]
}
```

## Top level

| Field | Type | Default | Notes |
|---|---|---|---|
| `source` | string | required for footage plans | Path to the video. Relative paths resolve **against the plan file's folder**, so a plan survives being moved between machines. Omit it for a slideshow. |
| `clips` | array | required | Non-empty. See below. |
| `out` | string | `./clips` next to the plan | Output folder. `--out` wins over this. |
| `aspect` | string | `9:16` | `9:16`, `1:1`, `4:5`, `16:9`, or `auto` (keep the recording's orientation: landscape stays landscape). |
| `lang` | string | `es` | `es`, `en`, `pt`, `fr`, `de`, `it`, `ja`, `hi` pick good defaults for voice and offline TTS. CJK/Thai get shorter caption lines automatically. |
| `voice` | string | language default | edge-tts voice id (`es-AR-TomasNeural`) or an OS voice name (`Microsoft Sabina Desktop`, `Mónica`, …). An empty string means "the sensible default for `lang`". |
| `audio` | string | `tts` | `tts` = narration replaces original audio. `source` = keep original only **and skip narration even if a `script` exists** (captions still follow the script, proportionally timed). `mix` = original ducked to 22% under the narration. |
| `fit` | string | `auto` | How the source fills the frame: `auto` (straight when the shapes match, `blur` otherwise; stills choose per image), `blur` (blurred copy behind, keeps every pixel), `cover` (centre crop, loses edges), `pad` (flat bars). `--fit` sets it for the whole run. |
| `stitch` | bool | `false` | Render all clips, then join them in plan order into one file. Same settings for every clip; `--only` skips stitching. `--stitch [name]` overrides it. |
| `stitch_name` | string | `full` | Basename of the joined file. |
| `prompt` | string | `""` | The user's request, kept for reference when `storyboard` writes the plan. Ignored by `render`. |
| `music` | string | `""` | Audio track looped under the mix at 8%, faded in/out. Path relative to the plan, or a YouTube/SoundCloud URL downloaded with `yt-dlp`. `fetch` fills it. |
| `music_query` | string | `NCS progressive house` | What `fetch` searches when `music` is empty. Only NoCopyrightSounds uploads are accepted; no match falls back to Wikimedia Commons. |
| `credits` | array | `[]` | Attribution entries `{title, creator, license, url, page, clip}`. `fetch` appends image licenses; `render` copies them to `credits.txt` in the output folder. |
| `captions_style` | object | see below | Preset plus typography overrides. |

## Clip fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | `clip-01` | Becomes the filename. Sanitized: unsafe characters stripped, spaces to dashes. |
| `start` | number | `0` | Seconds into the source. |
| `duration` | number | rest of video | Clamped to what is left of the source. On a slideshow it is the maximum: the clip shrinks to the narration length so captions never end before the voice. |
| `media` | array | `[]` | Image or video paths for a slideshow clip; relative paths resolve against the plan. Split evenly over the beat and crossfaded. Stills near the frame's shape get a Ken Burns push, wider ones pan across full-bleed, taller ones sit over a blurred copy; videos are cropped to fill. Empty (and no `chart`) = text beat: animated gradient, captions big in the centre. |
| `query` | string | `""` | English image search used by `fetch` (web by default, `--from wiki` for Wikimedia only). Ignored by `render`. |
| `video` | string | `""` | YouTube search used by `fetch`: downloads only `duration`+1 s of real footage from ~30% into the first long-enough result. Counts as one of the `--n` visuals. |
| `chart` | object | — | Animated motion-graphics card instead of footage; see **chart** below. `media`/`query` are ignored for the beat. |
| `say_title` | bool | `true` on the first clip | Speak the `title` before the `script` (the hook). Captions start after it. |
| `script` | string | `""` | Narration. Empty = no voice, no captions, silent audio track. |
| `narration` | string | — | Alias for `script`. |
| `voice` | string | plan value | Override the voice for one clip (useful when quoting someone else). |
| `lang` | string | plan value | Override the language for one clip. |
| `aspect` | string | plan value | Override the frame for one clip (e.g. one 1:1 for a feed post). |
| `audio` | string | plan value | Override the audio mode for one clip. |
| `fit` | string | plan value | Override the framing for one clip (`blur`, `cover`, `pad`). |
| `title` | string | `""` | Text on a coloured box at the top, popped in. On the first clip it is the spoken hook and stays while it is said; elsewhere ~3 s. On a `chart` clip it becomes the chart's heading when the chart has none. |
| `captions_style` | object | plan value | Override caption typography for one clip. |

## chart

Every number must come from a source you read; put it in `source` — it is printed on the card.

| `type` | Fields | Animation |
|---|---|---|
| `counter` | `value`, `label`, optional `from` | big number counts up, accent underline grows |
| `bar` | `labels`, `values`, optional `highlight` (index; default: the largest) | horizontal bars grow one after another, values count up |
| `line` | `labels` (x), `values` | line draws left to right, the head shows the current value |
| `table` | `columns`, `rows` (list of lists), optional `highlight` (row index) | rows slide in one by one |

Shared: `title`, `source`, `prefix` (`"$"`), `suffix` (`" %"`), `decimals`, `compact` (default `true`: 300000000 → "300 millones"; `false` prints the number as given).

```json
{"name": "03-data", "script": "GTA cinco vendió doscientos millones.",
 "chart": {"type": "bar", "title": "Millones de copias", "labels": ["Minecraft", "GTA V"],
           "values": [300, 200], "compact": false, "source": "Mojang 2023, Take-Two 2024"}}
```

`script` may also be inherited from the top level if you prefer to keep one narration string per clip file, but in practice per-clip is what you want.

## captions_style

| Field | Default | Notes |
|---|---|---|
| `preset` | `tiktok` for 9:16 / 4:5, else `clean` | `clean` (54 px, low), `tiktok` (64 px, above the platform UI), `bold` (70 px, loudest). Individual fields below override the preset. |
| `highlight` | `#FFD21F` | Colour of the word being spoken. `null` = plain lines. |
| `title_box` | `#FF2D55` | Box colour behind the `title` hook. |
| `size` | `6% of width` (~58 px at 1080) | Font size in output pixels. |
| `color` | `#FFFFFF` | Fill colour, `#RRGGBB`. |
| `outline_color` | `#000000` | Stroke, keeps text readable over light UI. |
| `font` | `Arial` | Any installed family name; libass falls back if missing. |
| `max_chars` | `30` (`14` for ja/zh/ko/th) | Line break threshold. libass wraps inside the margins, but above ~34 the breaks look bad. |
| `max_words` | `6` (`5` for ja/zh/ko/th) | Second break condition, keeps fast speech readable. |
| `margin_v` | `7.8% of height` (~150 px) | Distance from the bottom. Raise it if the recording has its own bottom bar. |
| `margin_h` | `5.5% of width` | Side margins. |

## Behaviour worth knowing

- **Missing keys are defaulted, unknown keys are ignored.** A plan never fails on a typo in an optional field; it fails loudly only on a missing source, an empty `clips` array, or a non-numeric `start`/`duration`.
- **Existing outputs are skipped** unless `--force`. Re-running a plan after editing one script is cheap: use `--only name --force`.
- **TTS is cached** in `TALKICUT_CACHE` (default: `%LOCALAPPDATA%\talkicut` on Windows, `~/Library/Caches` on macOS, `$XDG_CACHE_HOME` on Linux) keyed by text + voice + engine, so re-renders do not re-synthesize.
- **Every render writes `manifest.json`** next to the clips: tool version, plan path, source, aspect, fit, style, and one entry per clip with duration, size, audio, voice and captions.
- **`--json`** prints `{"ok": bool, "out_dir": ..., "clips": [{name, path, duration, width, height, has_audio, voice, captions, title}]}` — parse it instead of scraping the human output.
- **`--srt` and `--thumbnail`** write `<name>.srt` and `<name>.jpg` beside each clip, from the same grouped lines used for burn-in.
- **`stitch`** on a footage plan joins clips with stream copy (one encode for a full edit). On a slideshow it crossfades between beats (one extra encode). A failed clip aborts the join instead of producing a shorter video.
- **No `source` = slideshow.** Each beat is a chart, footage, stills or a text beat, then goes through the same TTS and caption path. The beat lasts as long as its voice (a chart at least 3.5 s), so there is no silence after the last caption. `aspect: auto` follows the first image; set `9:16` or `16:9` when it matters.
- **`fetch` edits the plan in place.** It fills `media` only for clips with a `query`/`video`, no `chart` and no media yet, appends sources to `credits`, picks music, and writes `media/credits.txt`. Re-running skips filled clips, so a bad image is replaced by deleting that clip's `media`.
- **`make plan.json --out video.mp4`** = `fetch --sheet` + `render --stitch final --force` + copy. The cheapest call for an agent.
- **`credits.txt`** lands in the output folder next to `manifest.json`; `manifest.credits` points to it.
- **Music** is applied after stitching, so the track runs once over the whole video instead of restarting at every beat. Without `stitch`, each rendered clip gets its own copy.

## Minimal plan

```json
{"source": "screen.mov", "clips": [{"name": "hook", "start": 4, "duration": 12, "script": "Mira esto."}]}
```

A prompt-only plan, before and after `fetch`:

```json
{"aspect": "9:16", "clips": [
  {"name": "01-hook", "duration": 6, "title": "¿Sabías que...", "script": "La IA ya no es ciencia ficción.", "video": "humanoid robot demo"},
  {"name": "02-data", "duration": 6, "script": "...", "chart": {"type": "counter", "value": 1000000, "label": "...", "source": "..."}},
  {"name": "03-close", "duration": 5, "script": "¿Tú qué opinas?", "query": "artificial intelligence robot"}
]}
```
