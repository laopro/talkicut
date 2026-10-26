# Changelog

## 3.3.2

Less noise, fewer tokens.

- Removed the top progress bar: it read as a watermark and clipped against platform UI.
- `SKILL.md` rewritten from 152 to 77 lines (~9 KB to ~3.9 KB), with a hard "token budget" section: `--brief` first, one contact sheet, grep `ocr.json`, re-render with `--only`, and open references only when needed.

## 3.3.1

Better music, quieter.

- `--music` and `fetch --music` accept a YouTube/NCS/SoundCloud URL or a search string; tracks come from `yt-dlp` (NCS and friends) and fall back to Wikimedia Commons when it is missing.
- Default music level dropped to 8% under the voice: present, never fighting the narration.
- NCS-style tracks get their title and page written to `credits.txt`, since the licence requires credit.

## 3.3.0

Motion graphics and music, so a slideshow reel reads as an edit.

- `--music track.mp3` loops a track under the narration at 14% (`--music-volume`), with a fade in and out. It is applied after stitching, so the music runs once over the whole video instead of restarting at every beat.
- `fetch --music "electronic music loop"` picks a freely licensed track from Wikimedia Commons (12-600 s, <= 30 MB, CC0/BY preferred), saves it as `media/music.*`, sets `plan.music` and adds it to `credits.txt`.
- A thin progress bar runs across the top of every slideshow clip.
- Titles pop in with a scale + fade; captions fade instead of snapping on.
- Crossfades now cycle through fade, slide, zoom and wipe instead of using fade for every junction.

## 3.2.1

Prompt-only videos that actually move, stay in sync, and show the subject.

- Slideshow beats now last as long as their narration (+0.35 s): no more silence after the last caption, which read as subtitles drifting.
- Ken Burns rewritten: `zoompan` gets a single frame per still, so the push and pan really animate; 14% zoom, four pan directions, crossfades between stills.
- `fit: auto` for stills: full-bleed when the photo already matches the frame, whole image over a blurred copy otherwise. No more giant crops of vertical product shots.
- `fetch` ranks candidates by title match, photo format and aspect, and penalises logos, diagrams, maps and charts.
- `fetch --sheet` writes `media/sheet.jpg` with the chosen images in order, so the agent or the user can veto a bad pick before rendering.
- Credits are deduplicated per clip when a clip is re-fetched, and entries without a `page` no longer crash.

## 3.2.0

Videos from a prompt, with no footage at all.

- `storyboard "prompt"` scaffolds a source-less plan with beats, durations and a character budget.
- `fetch plan.json` downloads freely licensed images from Wikimedia Commons for each clip's `query`, fills `media`, and writes `media/credits.txt` with attribution.
- Render accepts plans without `source`: images become Ken Burns clips (alternating zoom, 30 fps, cropped to fill) and reuse the existing TTS, captions, title and audio pipeline.
- A beat with no image renders on a dark canvas with its title and captions, so statistics and quotes need no stock photo.
- `aspect: auto` on a slideshow follows the first image's orientation.
- `credits.txt` is copied to the output folder and linked from `manifest.json`.
- `references/auto-video.md`: research rules, beat lengths, Wikimedia query writing, licensing and attribution.
- `SKILL.md`: prompt-only workflow section and two new failure-table rows.

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
