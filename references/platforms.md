# Platforms

One script, every OS. This file is what to install and what to expect where.

## Requirements

| Need | Windows | macOS | Linux |
|---|---|---|---|
| Python 3.9+ | `winget install Python.Python.3.12` | preinstalled or `brew install python` | `sudo apt install python3` |
| ffmpeg + ffprobe | `winget install Gyan.FFmpeg` | `brew install ffmpeg` (add a full build for captions, see below) | `sudo apt install ffmpeg` |
| Best-quality TTS | `python -m pip install --user edge-tts` (needs internet) | same | same |
| Offline TTS fallback | built in (PowerShell `System.Speech`) | built in (`say`) | `sudo apt install espeak-ng` |
| OCR (optional) | `winget install UB-Mannheim.TesseractOCR` | `brew install tesseract` | `sudo apt install tesseract-ocr tesseract-ocr-spa` |

`ffmpeg` builds that matter: you need `libass` for captions, `boxblur`, `loudnorm`, `drawtext`.
Good default builds: **gyan.dev** (Windows), distro package (Linux). Homebrew's `ffmpeg` 9 on macOS ships **without** `libass`/`freetype`, so captions are skipped there (with a warning) until you install a full build - e.g. a static build from evermeet.cx, or a tap that still bundles libass.
`doctor` reports exactly which of these the installed build has.

## Voices

`edge-tts` (free, no key, needs network) — good picks by language:

| Lang | Voice |
|---|---|
| es-AR | `es-AR-TomasNeural`, `es-AR-ElenaNeural` |
| es-MX | `es-MX-JorgeNeural` |
| es-ES | `es-ES-AlvaroNeural`, `es-ES-ElviraNeural` |
| en-US | `en-US-AndrewNeural`, `en-US-AvaNeural` |
| en-GB | `en-GB-RyanNeural`, `en-GB-SoniaNeural` |
| pt-BR | `pt-BR-AntonioNeural` |
| fr-FR | `fr-FR-RemyMultilingualNeural` |
| de-DE | `de-DE-ConradNeural` |
| it-IT | `it-IT-DiegoNeural` |

Full list: `edge-tts --list-voices` (add `--voice` with the short name).

OS voices (`--tts system`, offline, no word timings):

- **Windows** — `[System.Speech.Synthesis.SpeechSynthesizer]::new().GetInstalledVoices() | % { $_.VoiceInfo.Name }`.
  Spanish is only present if a Spanish language pack / SAPI voice is installed. Otherwise the clip is narrated with an English voice reading Spanish text — check with a short test first.
- **macOS** — `say -v '?'`. `Mónica`, `Paulina`, `Jorge` are common Spanish voices.
- **Linux** — `espeak-ng --voices`. Robotic, but works with zero network and zero install on most distros.

System voices ignore `--voice` if the name is not installed: the backend picks the OS default instead of failing.

## Environment variables

| Var | Purpose |
|---|---|
| `FFMPEG`, `FFPROBE` | Point at specific binaries (scoop/choco/conda installs, CI images). |
| `TALKICUT_CACHE` | Where synthesized audio is cached (`%LOCALAPPDATA%\talkicut` on Windows, `~/Library/Caches/talkicut` on macOS, `$XDG_CACHE_HOME/talkicut` elsewhere). |

## Headless / CI

Everything runs without a display. Note that:

- `selftest` is the smoke test: it builds a synthetic video, renders two clips, verifies resolution/audio/duration, and exits non-zero on failure.
- Renders are CPU-only and deterministic; `--jobs N` parallelizes across clips.
- No network is needed with `--tts system`; `edge-tts` needs outbound HTTPS to Microsoft's speech endpoint.

## Known breakage

| Symptom | Cause | Fix |
|---|---|---|
| `Fontconfig error: Cannot load default config file` | Windows ffmpeg build without fontconfig at runtime | harmless when a font file is passed explicitly; the script only uses `drawtext` if the font is found |
| `Could not create a libass track when reading file` | absolute Windows path inside the filtergraph | already handled: subtitle files are passed relative to a temp cwd |
| `loudnorm` missing | minimal/buildroot ffmpeg | audio is written unnormalized; acceptable, or install a full build |
| edge-tts `403`/`403 Invalid response status` | service change or blocked network | `--tts system` |
| `say: voice not found` | macOS voice not installed | System Settings → Accessibility → Spoken Content → add the language |
| Output plays but no captions | ffmpeg without `libass` | install a full build; `doctor` shows it |
| Very slow render | 4K/60 source | `--preset faster --crf 23` |
