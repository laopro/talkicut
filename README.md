# talkicut

**Give a silent screen recording a voice, then cut it into vertical clips. Or describe a video and let it build one.**

A screen recording with no audio track is the modern silent film: no transcript, nothing for an AI clipper to select. talkicut reads the recording, helps you choose the beats, writes nothing for you, speaks the narration you wrote, and burns word-synced captions into a 9:16 clip.

No footage? Give it a topic. `storyboard` scaffolds the beats, `fetch` downloads freely licensed images from Wikimedia Commons, and `render` turns them into a moving, narrated video with attribution.

Plain Python + ffmpeg. No API keys, no accounts, no cloud. Works on Windows, macOS and Linux, under any agent that can run a shell, with any model - including models that cannot see images.

```
 recording.mp4 ──▶ probe/sheet/ocr ──▶ plan.json ──▶ render ──▶ clips/
   (silent)          (read the UI)      (beats +        (TTS +      1080x1920
                                         narration)      captions)   .mp4 + .srt + .jpg
```

## Install

Clone it straight into the folder your agent reads as skills:

```bash
# OpenCode
git clone https://github.com/laopro/talkicut.git ~/.config/opencode/skills/talkicut

# Claude Code / Claude Desktop
git clone https://github.com/laopro/talkicut.git ~/.claude/skills/talkicut

# Codex / Cursor / anything that reads .agents/skills
git clone https://github.com/laopro/talkicut.git .agents/skills/talkicut
```

Or copy the folder anywhere and point your agent's skill directory at it:

```bash
./install.sh                 # macOS / Linux, defaults to ~/.config/opencode/skills
.\install.ps1                # Windows (PowerShell)
./install.sh ~/.claude/skills
```

Requirements: Python 3.9+ and `ffmpeg`/`ffprobe` with `libass`, `boxblur` and `loudnorm`. Optional: [`edge-tts`](https://github.com/rany2/edge-tts) for the good voices (`doctor --fix` installs it); without it, the OS voice is used offline.

> macOS note: Homebrew's `ffmpeg` 9 build ships without `libass`, so captions are skipped (with a warning). Use a full build - a static one from evermeet.cx, or any tap that bundles libass - if you want burned captions. Everything else renders fine with the Homebrew build.

## Use it

Just hand your agent the recording:

> "acá tenés la grabación de mi app (no tiene audio), sacale 3 clips verticales para reels con subtítulos"

The agent follows `SKILL.md`. By hand it is five commands:

```bash
python scripts/talkicut.py doctor                  # what this machine has
python scripts/talkicut.py probe demo.mp4          # duration, audio, scene cuts
python scripts/talkicut.py sheet demo.mp4          # timestamped contact sheets
python scripts/talkicut.py plan demo.mp4 --beats 4 # scaffold plan.json (--full to cover the whole video)
python scripts/talkicut.py render plan.json        # -> ./clips
python scripts/talkicut.py verify clips            # catch the silent failures
```

With no recording at all:

```bash
python scripts/talkicut.py storyboard "un reel sobre las IA actuales" --beats 4 --seconds 28 --out reel.plan.json
python scripts/talkicut.py fetch reel.plan.json --n 2   # Wikimedia Commons -> media/ + credits.txt
python scripts/talkicut.py render reel.plan.json
python scripts/talkicut.py verify clips
```

The agent researches the topic with its own web tools, writes the narration and one image query per beat, and cites its sources in `credits`. The pipeline does not invent facts.

`selftest` renders a synthetic video end to end, so you can tell "my plan is wrong" apart from "this machine is broken".

## What you get

- 1080x1920 (or 1:1, 4:5, 16:9), full screen visible over a blurred fill - no UI is cropped away
- `--aspect auto` keeps a horizontal recording horizontal, scaled straight with no blur
- burned captions in three presets (`clean`, `tiktok`, `bold`), word-synced when edge-tts is available
- optional hook title for the first seconds of each clip
- audio normalized to -16 LUFS, with a silent AAC track when there is no voice
- `manifest.json`, plus optional `.srt` and `.jpg` per clip
- `--stitch` joins the clips in plan order into one file: a full-video edit with the same encode
- prompt-only reels: Ken Burns push + pan over fetched stills, crossfades, beats that last exactly as long as the narration, and `credits.txt` with every image license
- `+faststart` so platforms start processing the upload immediately

## Commands

| Command | What it does |
|---|---|
| `doctor` | checks ffmpeg, filters, fonts and TTS backends, with install commands for your OS |
| `probe` | duration, resolution, audio, scene cuts, as text or `--json` |
| `plan` | scaffolds `plan.json` with beats snapped to real cuts, and a character budget per beat |
| `storyboard` | scaffolds a plan from a prompt, for videos with no source footage |
| `fetch` | downloads freely licensed images for the plan's queries, plus attribution; `--sheet` writes a contact sheet to review them |
| `sheet` | contact sheets with timestamps, for vision models |
| `ocr` | timestamped UI transcript, for models without vision |
| `render` | plan -> finished clips |
| `verify` | every clip in a folder: streams, duration, size, mean volume |
| `selftest` | synthetic end-to-end run, no user files touched |

`render` flags: `--audio tts|source|mix`, `--tts auto|edge|system|none`, `--voice`, `--lang`, `--aspect auto|9:16|4:5|1:1|16:9`, `--fit blur|cover|pad`, `--style clean|tiktok|bold`, `--stitch [name]`, `--srt`, `--thumbnail`, `--dry-run`, `--brief`, `--only`, `--force`, `--jobs`, `--json`.

## Why it works like this

- **Blurred fill, not crop.** Screen content is landscape; cropping to 9:16 destroys the UI. `--fit cover` exists for footage that can lose its edges, `--fit pad` for flat backgrounds.
- **Manual beats, mechanical render.** No virality model pretends to know your story. The agent reads the screen, you write the words, the pipeline does the rest.
- **Rate fitting, not time-stretching.** When the narration is too long, the voice is re-synthesized faster; `atempo` makes TTS sound drunk.
- **Capability detection.** The script asks ffmpeg which filters exist and asks the OS which voices exist, then degrades visibly instead of dying.

## Documentation

- `SKILL.md` - the agent workflow, decisions and failure table
- `references/editing.md` - full-video editing, horizontal output, stitching, pacing
- `references/auto-video.md` - prompt-only videos: research, image queries, licensing, text-only beats
- `references/plan-schema.md` - every plan field and default
- `references/narration.md` - pacing math, hooks, per-language notes
- `references/platforms.md` - install matrix, voices per OS, known breakage
- `references/ffmpeg-notes.md` - filter chains and the bugs behind them
- `assets/plan.example.json` - copy-paste starting point

## Limits

- It does not choose highlights for you: no ASR and no virality model. Beat selection and narration are the judgment part.
- A full edit is built from the beats you define; it does not detect silences or dead time automatically.
- Prompt-only videos use stills from Wikimedia Commons, not stock video. `fetch` ranks by title and photo-ness and `--sheet` shows every pick, but a wrong image is always possible: look at the sheet before publishing.
- Captions are word-synced only with edge-tts; OS voices get proportional timing (good to ~0.3 s over a 30 s clip).
- Face-tracking crops are out of scope - screen content should stay uncropped anyway.

## License

MIT. See `LICENSE`.
