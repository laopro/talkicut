# Videos from a prompt, no footage

`storyboard` → research → `fetch` → `render` builds a complete video when the user gives a topic instead of a file.

The script cannot research and cannot write: **you** are the model. The pipeline only scaffolds beats, downloads freely licensed images, and renders narration + captions + motion.

## 1. Research before writing

- Use your own web tools. Open at least three sources; prefer primary ones (papers, official blogs, statistics agencies) over aggregators.
- Every number, date and claim in the narration must come from a source you actually read. If two sources disagree, say "según X" or drop the claim.
- Date the facts: "en 2026" beats "hoy" in a video that will be watched next year.
- Keep the URLs. They go into the plan's `credits` so the description can cite them.

```
credits: [
  {"title": "AI Index Report 2026", "creator": "Stanford HAI", "license": "CC BY 4.0",
   "url": "https://hai.stanford.edu/ai-index"}
]
```

`fetch` appends image attribution to the same array; a hand-written entry with `url` and no `page` is fine.

## 2. Beats

`storyboard "prompt" --beats 5 --seconds 30` splits the duration evenly. Adjust `duration` per beat before writing.

| Position | Job | Length |
|---|---|---|
| 1 | hook: the surprising claim or the question | 3–6 s |
| 2–4 | one idea each, in order: context → evidence → consequence | 6–10 s |
| last | takeaway or call to action | 4–7 s |

- 3–6 beats for 20–45 s. More than 6 needs a longer runtime, not faster speech.
- One idea per beat. If the script needs a comma splice to fit, split the beat.
- 14–16 characters per second; `storyboard` prints the budget at 85% occupancy.
- Write for the ear: short sentences, no parentheses, no "como mencioné anteriormente".

## 3. Image queries

`fetch` searches Wikimedia Commons, which matches **words in file names and descriptions**, not meaning. Literal and concrete wins.

| Weak | Better |
|---|---|
| the future of AI | artificial intelligence robot |
| technology | data center servers |
| innovation | computer chip macro |
| climate change | glacier melting |
| money | stock market trading floor |

- English, 2–4 nouns. Add a qualifier when the subject is ambiguous (`Nvidia GPU`, `humanoid robot`).
- `--n 2` gives the renderer two stills per beat (crossfaded). Use `--n 1` for text-heavy beats.
- Abstract beats (a definition, a quote, a statistic) often work better with **no image**: leave `media` empty and the beat renders on a dark canvas with its title and captions.
- `fetch --sheet` writes `media/sheet.jpg`, one grid of every chosen image in order. **Open it before rendering.** Search results include diagrams, logos and unrelated photos; a wrong image is worse than a text-only beat. To replace one, clear that clip's `media` and change its `query`, then fetch again.

## 4. Licensing and attribution

- Wikimedia Commons files are freely licensed, but most require attribution (CC BY, CC BY-SA) and some are non-commercial (NC) or no-derivatives (ND).
- `fetch` writes `media/credits.txt` and adds each file to `plan["credits"]`; `render` copies it to `clips/credits.txt`. **Ship that file** with the video, or paste it into the description.
- Do not crop out watermarks or signatures. Do not claim the images as your own.
- If the user needs commercial use, check the license in `credits.txt` first and drop NC files.

## 5. Render and check

```bash
python scripts/talkicut.py storyboard "un reel sobre las IA actuales" --beats 4 --seconds 28 --out reel.plan.json
# fill script + query + credits
python scripts/talkicut.py fetch reel.plan.json --n 2 --sheet --music "Elektronomia Sky High NCS"
python scripts/talkicut.py render reel.plan.json --style tiktok --srt --thumbnail
python scripts/talkicut.py verify clips --brief
```

- No `source` means slideshow mode: each image gets a share of the beat, a 14% Ken Burns push with a directional pan, and a crossfade into the next still.
- A slideshow beat lasts as long as its narration (+0.35 s), so captions and voice end together. `duration` in the plan is the maximum; the renderer shrinks the beat instead of leaving silence.
- `fit: auto` (the default) fills the frame when the photo is already close to its shape and shows it whole over a blurred copy otherwise. Force `cover` for full-bleed or `blur` for every still.
- Motion comes from four layers: Ken Burns push + pan, crossfades (fade / slide / zoom / wipe), a 10 px progress bar, and captions/titles that fade and pop in.
- `--music` loops a track under the voice at 8%, with a fade at both ends. Pass a local file, a YouTube/NCS URL, or a search string: `fetch --music "NCS progressive house"` downloads the top hit with `yt-dlp` (falls back to Wikimedia Commons when yt-dlp is missing). Keep the credit in `credits.txt`; NCS requires it.
- `aspect: auto` on a slideshow follows the first image; set `9:16` or `16:9` explicitly when it matters.
- Re-running `fetch` skips clips that already have `media`. Delete the entry (or the file) to re-fetch a bad image.
- Check one frame per beat, not just the first: captions over a busy photo are the usual failure.

## Limits

- Images only. There is no keyless stock-video source; a beat that needs motion should come from the user's own footage.
- No fact-checking: the model writes the script, so the model is responsible for what it claims.
- Search quality is Wikimedia's. Obscure or very recent topics may have nothing usable; fall back to text-only beats.
