# Changelog

## 3.1.0

Horizontal output and full-video edits, with a smaller token footprint.

- `--aspect auto` keeps the recording's orientation; when the source already matches the target shape it is scaled straight, without the blur pass.
- `plan --full` + `stitch`: beats covering the whole video are joined into one file with stream copy, so a full edit costs a single encode.
- `--stitch [name]`, `--brief` on `render`, `plan`, `verify` and `ocr`, `--max-sheets` on `sheet`.
- `references/editing.md`: cut placement, beat length, narration for long edits, horizontal workflow.
- `SKILL.md` trimmed by a fifth: a short intake (three questions, defaults) and progressive disclosure into `references/`.
- Skill description trimmed so it costs less context on every turn.

## 3.0.0

Renamed to **talkicut**. New commands and output options, still zero dependencies beyond ffmpeg and Python.

- `plan` scaffolds `plan.json` from probe + scene cuts, with a character budget per beat.
- `verify` checks a folder of clips for missing audio, wrong size, impossible durations and off-target loudness.
- `--fit blur|cover|pad`, `--style clean|tiktok|bold`, `--srt`, `--thumbnail`, `--dry-run`.
- Per-clip `title` hook card, burned in with a fade.
- `manifest.json` per render, merged across `--only` runs.
- CJK/Thai caption widths, libass wrapping inside margins, `.srt` timings clamped like the burn-in.
- Windows consoles in non-UTF-8 codepages no longer crash on accented output.
- Output defaults to `clips/` next to the plan instead of next to the video.

## 2.0.0

- Caption grouping fixed: no more stacked or stuttering lines.
- Rate fitting for narration that overruns, TTS cache, `--jobs`.
- `doctor`, `probe`, `sheet`, `ocr`, `render`, `selftest`.

## 1.0.0

- First working pipeline: blurred fill, ASS burn-in, system TTS fallback.
