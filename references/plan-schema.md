# plan.json schema

Everything except `source` and `clips` is optional.

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
| `source` | string | required | Path to the video. Relative paths resolve **against the plan file's folder**, so a plan survives being moved between machines. |
| `clips` | array | required | Non-empty. See below. |
| `out` | string | `./clips` next to the plan | Output folder. `--out` wins over this. |
| `aspect` | string | `9:16` | `9:16`, `1:1`, `4:5`, `16:9`, or `auto` (keep the recording's orientation: landscape stays landscape). |
| `lang` | string | `es` | `es`, `en`, `pt`, `fr`, `de`, `it`, `ja`, `hi` pick good defaults for voice and offline TTS. CJK/Thai get shorter caption lines automatically. |
| `voice` | string | language default | edge-tts voice id (`es-AR-TomasNeural`) or an OS voice name (`Microsoft Sabina Desktop`, `Mónica`, …). An empty string means "the sensible default for `lang`". |
| `audio` | string | `tts` | `tts` = narration replaces original audio. `source` = keep original only **and skip narration even if a `script` exists** (captions still follow the script, proportionally timed). `mix` = original ducked to 22% under the narration. |
| `fit` | string | `blur` | How the landscape source fills the frame: `blur` (blurred copy behind, keeps every pixel), `cover` (centre crop, loses edges), `pad` (flat bars). When the source already has the target shape, it is scaled straight and this is ignored. `--fit` sets it for the whole run. |
| `stitch` | bool | `false` | Render all clips, then join them in plan order into one file. Same settings for every clip; `--only` skips stitching. `--stitch [name]` overrides it. |
| `stitch_name` | string | `full` | Basename of the joined file. |
| `captions_style` | object | see below | Preset plus typography overrides. |

## Clip fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | string | `clip-01` | Becomes the filename. Sanitized: unsafe characters stripped, spaces to dashes. |
| `start` | number | `0` | Seconds into the source. |
| `duration` | number | rest of video | Clamped to what is left of the source. |
| `script` | string | `""` | Narration. Empty = no voice, no captions, silent audio track. |
| `narration` | string | — | Alias for `script`. |
| `voice` | string | plan value | Override the voice for one clip (useful when quoting someone else). |
| `lang` | string | plan value | Override the language for one clip. |
| `aspect` | string | plan value | Override the frame for one clip (e.g. one 1:1 for a feed post). |
| `audio` | string | plan value | Override the audio mode for one clip. |
| `fit` | string | plan value | Override the framing for one clip (`blur`, `cover`, `pad`). |
| `title` | string | `""` | Hook card burned in at the top for the first ~3 s, with a fade. Independent of `script`, so a silent clip can still have a title. |
| `captions_style` | object | plan value | Override caption typography for one clip. |

`script` may also be inherited from the top level if you prefer to keep one narration string per clip file, but in practice per-clip is what you want.

## captions_style

| Field | Default | Notes |
|---|---|---|
| `preset` | `clean` | `clean` (54 px, low), `tiktok` (64 px, above the platform UI), `bold` (70 px, loudest). Individual fields below override the preset. |
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
- **`stitch`** joins clips with stream copy (same encoder settings everywhere), so a full-video edit costs one encode, not two. A failed clip aborts the join instead of producing a shorter video.

## Minimal plan

```json
{"source": "screen.mov", "clips": [{"name": "hook", "start": 4, "duration": 12, "script": "Mira esto."}]}
```
