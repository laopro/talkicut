# Editing a whole video

`render` is not only for shorts. The same plan can cover the entire recording and join the pieces back into one file.

## The three shapes

| Goal | Plan |
|---|---|
| 3 vertical shorts | `plan video.mp4 --beats 3`, aspect `9:16` |
| Horizontal video for YouTube | `plan video.mp4 --beats 5 --full`, aspect `auto` |
| Tightened version of the same recording | `plan video.mp4 --beats 8 --full`, then delete the beats you do not want and close the gaps |

`--full` does two things: beats span `0 → duration` with no gaps, and the plan gets `"stitch": true`. Rendering then writes the individual clips **and** one joined file (`full.mp4`, or `stitch_name`).

## Horizontal without the vertical machinery

`"aspect": "auto"` keeps the source orientation. When the source shape already matches the output shape, the frame is scaled straight - no blurred fill, no crop, no wasted encode. A 1920×1080 recording comes out 1920×1080.

Use an explicit `16:9` only when the source is a different landscape shape (ultrawide, 4:3) and you want it letterboxed to 16:9.

## How the join works

Segments are rendered with identical encoder settings, so the concat demuxer copies the streams: the join takes seconds, not a second full encode. Consequences:

- Render all clips in the same run. `--only` renders a subset, so stitching is skipped with a warning.
- Keep one aspect, one fps and one audio layout for the whole plan. Per-clip `"aspect"` breaks the join.
- A failed clip aborts the stitch instead of silently producing a shorter video.

## Where to cut

The full-edit version is usually about removing dead time, not adding narration:

- **Loading, typing, dead air** → cut the gap, keep a 150–300 ms handle before and after so the cut does not feel like a glitch.
- **Repeated attempts** → keep the one that worked, mention the failed one in the narration if it matters.
- **Long scrolls** → keep the start and the result; the middle reads as waiting.
- **Speed** → for slow interactions, a 2× segment is more watchable than a 20 s static shot. `plan` does not speed up footage; if you need it, add `-filter:v setpts=0.5*PTS` to that clip's render by hand and re-time the narration script to the shorter duration.

Beat length for a full edit: **5–15 s per beat**. Shorter than 3 s feels like a stutter; longer than 20 s needs a reason (a chart being read, a long result).

## Narration for a full edit

- One sentence per beat, not per click. The visuals carry the steps.
- Keep the source audio when it carries information (a meeting, a demo with sound): `"audio": "mix"`, or `"source"` for segments with no narration.
- Transitions between beats are silence. Do not end a line with "y ahora vamos a..." - just start the next one.
- If the total is over ~4 minutes, consider splitting into chapters (separate plans), because one file with 60 beats is hard to review.

## When the request is vague

The intake in `SKILL.md` exists for this. If the user says "editame este video" with no other context:

1. Ask the three questions (destination, length, voice).
2. Default everything else and say what you defaulted: "lo dejo en 16:9, 3 minutos, voz rioplatense".
3. Produce a first pass, then offer one concrete adjustment ("¿saco los 8 s de carga del minuto 1?").
