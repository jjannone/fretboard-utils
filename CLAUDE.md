# fretboard-utils — Claude guidelines

## Demo / example output

### Human readability
- Output each diagram in its **own separate markdown code block** in the response.
  Blank lines between diagrams are stripped by the renderer; separator lines are ugly.
  A new ``` fence between each diagram is the only reliable visual break.

### Pattern variety
- **Interval size**: semitones (m2) and whole tones (M2) are fine and often more interesting
  than always defaulting to wide spans. Use `min_stretch=0` or `min_stretch=1` freely.
- **Neck angle**: don't default to a uniform ascending drift. Patterns can be:
  - Straight across (same fret range on every string)
  - Jump (low strings at one position, high strings at a completely different one)
  - Arch (ascend then descend, or descend then ascend, within one pattern)
  - Drift (gradual movement, but can go down as well as up)
  - Mix: straight → jump → straight, etc.
- **Dissonance**: pleasant or aggressive dissonance is welcome. Semitone clashes against
  open/capo drones are often the most interesting choice, not a mistake to avoid.
- Vary all of the above *across* a set of examples — if one pattern drifts up, the next
  shouldn't also drift up.

### Stretch profiles
Use `STRETCH_PROFILES` from `fretboard.py` to drive per-string interval variety:
- `'tight'` — all strings m2/M2 (0–2)
- `'wide'`  — all strings m3–P4 (3–5)
- `'bass_tight'` / `'bass_wide'` — tight or wide on bass three, opposite on treble three
- `'growing'` / `'shrinking'` — span increases or decreases string by string
- `'alternating'` — odd/even strings alternate between tight and wide

Mix shapes and profiles: e.g. arch shape + alternating stretch, or sweep + shrinking.

### Spider capo
- **Always use spider capo** in generated examples unless the user explicitly says not to.
- Max physically-sensible capo fret is **4**.
- Capo tones that clash with the scale are *features*, not errors — note them in the label.
- **Never capo all 6 strings at the same fret** — that is just a transposition and should
  instead be expressed as the equivalent key with no capo.
  Rule: if capo would go all the way across at fret N, transpose the root DOWN by N semitones
  and use no capo. Example: G altered + capo 1 all strings → F# (Gb) altered, no capo.
- **Rarely more than one `'X'` string per pattern**, but this is a guideline not a hard rule.
  `X` means "fretted normally, no open/capo drone shown on this string."
- Choose capo fret and which strings get it based on which drone tones are harmonically
  interesting (in-scale, dissonant, or a mix) — don't default to all-six every time.

## Before generating patterns — READ THIS FILE FIRST
Before writing any demo or example code, re-read this file in full so all rules are active.
Checklist:
- [ ] Each diagram in its own code block
- [ ] Spider capo used (unless explicitly excluded)
- [ ] No more than one X string
- [ ] Intervals varied (not all seconds, not all wide)
- [ ] Shapes varied across examples (straight, jump, arch, drift, sweep — not all the same)
- [ ] Stretch profile varies across examples

### What NOT to do
- Do not always pick the widest interval available — that produces uniformly safe, timid patterns.
- Do not always move monotonically up the neck across strings.
- Do not generate examples that all look structurally identical (same angle, same interval width).
- Do not omit spider capo unless asked.
- Do not use more than one X string in a pattern.
