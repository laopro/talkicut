# ffmpeg notes for screen recordings

Every item here came out of a real render session; each is a bug that cost time.

## Verticalise a landscape recording

```
[0:v]split=2[bg][fg];
[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=18:2[b];
[fg]scale=1080:-2[f];
[b][f]overlay=(W-w)/2:(H-h)/2
```

`boxblur=18:2` is the balance point: still reads as colour context, blurry enough not to compete with the content.

Two alternatives in the same slot (`--fit`):

```
# cover: fill and centre-crop. Fuller frame, but the edges of the UI are gone
[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920

# pad: fit inside the frame, flat bars. Safest for text-heavy UI, looks like TV
[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x0E0E12
```

## Wrapping captions, not overflowing them

`WrapStyle: 2` means "no word wrapping" — long lines then draw straight off the frame edge, which is what a bold 70 px caption does on a 1080 px frame. `WrapStyle: 0` wraps inside the horizontal margins instead, so the `max_chars` heuristic becomes a comfort setting rather than a hard limit. Keep both: the heuristic picks sane breaks, libass prevents disasters.

## Never put absolute Windows paths in a filtergraph

`:` separates filter options, so `C:/x/cap.ass` breaks the parse, and escaping it correctly is one backslash away from a different bug. The reliable trick: write the subtitle file into the ffmpeg working directory and pass a bare filename (`ass=cap-00.ass`) with `cwd=` set on the subprocess. No escaping at all.

If you must pass a path, escape the drive colon exactly once: `C\:/x/y.ass`, and quote it.

## Apply `ass` after `overlay`

libass maps `PlayResX/Y` onto the frame it receives. Before the overlay the frame is the short foreground strip (1080×608), so a 58 px caption becomes ~18 px. Order matters:

```
[b][f]overlay=...,ass=cap-00.ass,format=yuv420p
```

## Prevent stacked captions

`end = max(last_word_end + 0.12, start + 0.25)`, then **clamp to the next line's start − 0.04**. Without the clamp, short proportional timings plus a minimum duration make two dialogue events overlap and libass renders both, one above the other. That bug looks like "captions are out of order" and is not a timing problem at all.

## ASS essentials

- `PlayResX`/`PlayResY` = final frame size.
- `Alignment=2` anchors bottom; `MarginV` ≈ 8% of height clears phone UI.
- Colours are `&HAABBGGRR` — alpha first, then blue-green-red, the reverse of `#RRGGBB`.
- Braces `{}` start an override block; strip or replace them in caption text.

## `drawtext` without fontconfig

Windows builds frequently print `Fontconfig error: Cannot load default config file` and fail. Pass `fontfile='C\:/Windows/Fonts/arialbd.ttf'` explicitly, and always have a code path that skips `drawtext` so sheet generation degrades instead of dying.

## Detect filters, don't assume

`ffmpeg -filters` prints `flags name in->out description`, with flags of two or three characters (`TSC`, `T.`, `..`). Parse by token position, check for `->`, and treat the name as `parts[1]`; fixed-width column parsing breaks across versions.

## Audio

| Need | Filter |
|---|---|
| Narration only | `[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]` |
| Original only | `[0:a]loudnorm=...[aout]` |
| Duck original under narration | `[0:a]volume=0.22[bgm];[1:a]loudnorm=...[vo];[bgm][vo]amix=inputs=2:duration=longest:normalize=0[aout]` |
| No audio at all | add `-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000` and map it |

Always `-t <duration>` on the output. `anullsrc` is infinite, and `-shortest` alone can end a clip early when TTS is shorter than the visuals.

## Contact sheets

```
fps=1/3,scale=384:-1,drawtext=...text='%{pts\:hms}'...,tile=5x3
```

384 px tiles keep a 15-frame sheet near 1900 px wide: one image read instead of fifteen. The escaped colon inside `%{pts\:hms}` is required.

## Scene detection

```
select='gt(scene,0.03)',showinfo
```

`0.03` catches UI-wide changes. Screen recordings often report nothing — that is information, not failure: it means the recording is one continuous take and beats must be chosen by content.

## Verification commands

```
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height -of csv=p=0 out.mp4
ffmpeg -hide_banner -i out.mp4 -af volumedetect -f null - 2>&1 | grep mean_volume
ffmpeg -y -ss 4 -i out.mp4 -frames:v 1 preview.jpg
```

One frame per clip catches caption collisions, unreadable contrast over dark UI, and off-by-one start times. Check them before delivering.

## Encoding

`libx264 -preset veryfast -crf 21 -pix_fmt yuv420p -movflags +faststart`, AAC 160 kbps 48 kHz. `+faststart` moves the moov atom up front so platforms start processing immediately instead of stalling the upload.
