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

`storyboard` pre-fills beat 1's `title` with a random opener from its hook bank (`¿Sabías que...`, `Nadie te dijo esto:`, `El error que casi todos cometen:`, ...). Keep it, swap for another from the printed list, or write one in the same pattern-interrupt style — but the beat always opens on a hook line, never on a flat fact.
| 2–4 | one idea each, in order: context → evidence → consequence | 6–10 s |
| last | takeaway or call to action | 4–7 s |

- 3–6 beats for 20–45 s. More than 6 needs a longer runtime, not faster speech.
- One idea per beat. If the script needs a comma splice to fit, split the beat.
- Never restate the `title` number/claim inside that beat's `script` — if the title already says "$450", the caption says what it means, not the same figure again. Repeating a fact reads as padding, not emphasis.
- 14–16 characters per second; `storyboard` prints the budget at 85% occupancy.
- Write for the ear: short sentences, no parentheses, no "como mencioné anteriormente".

## 3. Visuals per beat

One visual per beat, picked by what the beat says:

| Beat is about | Field | Source |
|---|---|---|
| something that moves (a game, a sport, a city, a product in use) | `video` | YouTube via `yt-dlp`: only `duration`+1 s is downloaded, from ~30% into the first long result (past intros) |
| a specific thing to show | `query` | Bing image search (keyless), ranked by relevance; `--from wiki` = Wikimedia Commons only |
| a number, ranking, comparison, trend | `chart` | drawn and animated locally (counter, bar, line, table) |
| a quote or punchline | nothing | animated gradient, captions big in the middle |

| Weak | Better |
|---|---|
| videogames | GTA V gameplay 4k |
| technology | data center servers |
| the future of AI | humanoid robot demo |
| money | stock market trading floor |

- English, 2-5 words, the brand or proper name in it. For footage add `gameplay`, `4k`, `no commentary`, `drone`, `b-roll`.
- `--n 2` (default) = two visuals per beat, crossfaded; footage counts as one.
- `make` writes `media/sheet.jpg`, one grid of every pick in order (first frame for footage). **Open it once.** A wrong or watermarked picture: clear that clip's `media`, change its `query`, run `make` again.

## 4. Charts

- Every value comes from a source you read; the `source` string is printed on the card.
- `counter` for one shocking number, `bar` for a ranking (<= 6 bars), `line` for a trend over time, `table` for 2-5 rows of facts.
- The voice should say what the chart means, not read every value ("cuatro veces más", not "trescientos, doscientos, ochenta y dos").
- `compact: true` (default) turns 300000000 into "300 millones"; set `false` when the title already names the unit ("millones de copias").

## 5. Rights

- `--from web` and `video` pull whatever ranks best; those files are **not** licence-checked. `credits.txt` lists every source page; fine for personal reels, check before commercial use. `--from wiki` keeps everything freely licensed.
- Music is NoCopyrightSounds only (credit required, it is in `credits.txt`), falling back to Wikimedia Commons.

## 6. Render and check

```bash
python scripts/talkicut.py storyboard "un reel sobre las IA actuales" --beats 4 --seconds 28 --out reel.plan.json
# fill title (hook), script, and one of video / query / chart per beat
python scripts/talkicut.py make reel.plan.json --out ~/Desktop/reel.mp4
```

- A beat lasts as long as its narration (+0.35 s; a chart at least 3.5 s). `duration` is the maximum.
- Stills: near the frame's shape -> Ken Burns push; wider -> full-bleed pan across; taller -> over a blurred copy. Footage is cropped to fill.
- Motion layers: footage / pans / zooms, animated charts, crossfades inside and between beats (fade / slide / zoom / wipe), the hook box popping in, and the spoken word lighting up in the captions.
- Check one frame per beat, not just the first.

## Limits

- No fact-checking: the model writes the script, so the model is responsible for what it claims.
- Web results change; obscure topics may find nothing and render as text beats. Rewrite the query.
