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
Use spider capo configs in examples. Max physically-sensible fret is 4.
Capo tones that clash with the scale are *features*, not errors — note them in the label.

### What NOT to do
- Do not always pick the widest interval available — that produces uniformly safe, timid patterns.
- Do not always move monotonically up the neck across strings.
- Do not generate 5 examples that all look structurally identical (same angle, same interval width).
- Do not omit spider capo variants when generating examples for a scale.
