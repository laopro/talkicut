# Narration for clips

TTS reads what you write, literally. Written prose sounds wrong in its mouth; spoken prose sounds right.

## Pacing

| Language | Natural rate | 20 s clip fits |
|---|---|---|
| Spanish | 14–16 chars/s | ~260 chars |
| English | 15–17 chars/s | ~290 chars |
| Portuguese | 14–16 chars/s | ~260 chars |
| French | 13–15 chars/s | ~250 chars |
| German | 12–14 chars/s | ~230 chars |

Target **85% of the clip duration** in speech. That leaves air at the end, and the material can be pushed up to +35% rate if you overshoot — but you should not need it. The script picks the slowest rate that fits.

If you write 400 characters for a 20 s clip, no rate fixes it. Cut words.

## Shape of a 20–30 s clip

1. **Hook (2–3 s).** The outcome, not the setup: "Así se arma un examen completo en treinta segundos." Never "En este video vamos a ver…".
2. **Action (the body).** Present tense, active voice, one idea per sentence. Describe what changed on screen, not the click that changed it.
3. **Payoff (2–4 s).** What the viewer now has: "Y ya está listo para compartir."

## Do

- Present tense: "pegamos la clave y la guardamos".
- Concrete nouns from the UI: "el panel de configuración", not "esa parte de ahí".
- One clause per breath. Commas are rests; periods are stops.
- Numbers as words when short: "diez preguntas" reads better than "10 preguntas".
- Say the value: "no la tenés que pegar cada vez" beats "queda persistida".

## Don't

- Don't narrate the cursor or the scroll.
- Don't invent features that are not on screen. If a label is unreadable in the frames, describe the action generically ("abrimos la configuración de la API").
- Don't start with "hola, bienvenidos a mi canal" — that is 0:03 of dead air.
- Don't use symbols TTS stumbles on: `→`, `&`, `%`, `°`, long dashes. Write "y", "por ciento".
- Don't leave a sentence unfinished at the clip boundary. Trim the clip, not the sentence.

## Example — Spanish, 20 s, screen recording of a quiz generator

> Arrancamos abriendo la app. Lo primero es configurar la clave de API: elegimos el proveedor, pegamos la clave y la guardamos. Sin eso, el cuestionario no se puede generar.

~190 chars ≈ 13 s of speech in a 20 s clip — comfortable, with room for the visuals to breathe.

## Example — English, 18 s, silent demo

> One prompt is all it takes. Type the topic, pick a difficulty, hit generate — and the quiz writes itself, question by question, while you watch.

## Captions are not the script

The script has punctuation for the voice; the caption track splits at 30 characters and 6 words, and each line lives at least a quarter second. If captions read too fast, the fix is a shorter script, not a bigger font.

## When the language is not yours

Write in the language the user speaks, and let `--lang` pick the voice. If you cannot judge pacing in that language, aim low (12 chars/s) and leave air — better slow than clipped. Never machine-translate the user's own product vocabulary: keep their nouns.
