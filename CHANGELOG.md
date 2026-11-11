# Changelog

## 4.3.0

Seventeen things two real renders got wrong, fixed.

- Footage: a second `make` reuses the clip and the music it already downloaded; videos too short to cut from are skipped; news, lives and reactions rank last; a channel logo in a top corner sends the search to the next result and is reported; `credits.txt` says which seconds were used.
- Captions: the full stop after a number, a date or a rewritten name is kept; `S.`, `EE.UU.` and `Dr.` no longer end a line; a script the voice drifted away from is reported.
- Charts: the final figure is on screen for the last second instead of a count-up caught midway; a long title shrinks before it is cut, and a cut one says so with `...`.
- Fonts: only a font that really has the accented letters is used, and `doctor` says what a missing font costs.
- `make` ends with `audio=stereo -16.x LUFS`, repeats the plan warnings on stdout, and flags sound that is off target.
- Plans: no reel warnings for an edit of a recording; a closing question in the chart title counts; missing media is reported instead of silently turning into a text beat, and `fetch` downloads it again.
- `beat_seconds` and `references/narration.md` agree on 14 characters per second.

## 4.2.1

Charts that spell the accents.

- The font search missed the folders the font packages actually use (`liberation-sans-fonts`, `google-noto`, `adwaita-sans-fonts`), so the charts fell back to a bitmap font and every accented letter came out as an empty box: "QUÉ" became "QU▯". The search now falls back to whatever font is installed, and a machine with no font at all spells the charts without accents instead of drawing boxes.
- `doctor` reports the font it found.

## 4.2.0

Captions that punctuate, and a plan that gets checked before it renders.

- Captions keep the punctuation of the script: edge-tts speaks bare words, so every comma and full stop was lost and two sentences shared one line. The script's marks are matched back onto the spoken words (numbers are spoken as words, so they are skipped, never guessed).
- `make` now checks the plan before it downloads anything and says what is missing: an empty `angle`, fewer than 3 beats, a last beat with no question. A weak model skips exactly those parts.
- `selftest` covers both.

## 4.1.0

The good result by default, not only on a machine that happens to be set up.

- `make` and `doctor --fix` install the missing pieces themselves (edge-tts, yt-dlp, Pillow); yt-dlp also works when pip left it off `PATH`.
- Falling back to the offline voice now prints `ROBOTIC OFFLINE VOICE` instead of silently shipping espeak.
- Logos and diagrams on a flat background are shown whole instead of being panned or cropped into a slice.
- `table` charts: taller rows, text sized to its column, centred in the card.
- `make --tts`.
- A fallback voice is never served from the cache: the neural voice is tried again on the next run.
- edge-tts is retried on a dropped request, so one hiccup no longer gives a single beat the offline voice.
- Footage search prefers results whose title matches and skips multi-hour uploads first.
- `duration` is optional in topic plans: a beat lasts as long as its narration, so a plan is just `angle` + `clips` with `script` and one visual. `SKILL.md` now teaches writing that plan directly and running `make` once.
- Captions never straddle two sentences.
- `make` ends with `voice=..., music=...` and a `!` line for anything that degraded.
- Audio is always stereo: mono narration played on one speaker only in some players (VLC + PipeWire), and the music was being folded to mono.

## 4.0.0

Videos that hold attention, from one plan and one command.

- `make plan.json --out video.mp4`: fetch + render + crossfaded stitch + copy in one call.
- Angle first: `storyboard` adds an `angle` field ("most think X, but actually Y, because Z") and `SKILL.md` gives a topic-agnostic recipe for finding one and shaping the beats around it; `make` warns when it is empty.
- Visuals that match the topic: `query` uses keyless web image search (Bing) ranked by relevance; new `video` field downloads only a few seconds of real footage from YouTube (yt-dlp, past the intro). `--from wiki` keeps the old free-licence-only path, now with a relevance gate.
- Motion graphics: `chart` beats render animated `counter`, `bar`, `line` and `table` cards (Pillow -> ffmpeg) with the data source on screen.
- Spoken hook: the first beat's `title` is said out loud on a coloured box; captions start after it. `storyboard` pre-fills it from a bank of hooks.
- Captions light up the word being spoken (`highlight`); vertical videos default to the `tiktok` preset above the platform UI.
- Wide stills pan across a vertical frame full-bleed instead of sitting small over a blur; text-only beats get an animated gradient and big centred captions.
- Slideshow beats crossfade into each other (footage edits keep stream-copy cuts).
- Music: `fetch` picks an NCS track by default (`music_query`), accepting only NoCopyrightSounds uploads; never a random YouTube hit.
- Downloads reject HTML disguised as images, GIFs, tiny pictures and watermarked wallpaper previews.

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
