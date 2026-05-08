# fretboard-utils — Claude guidelines

## Demo / example output

### Human readability
- Always print **at least two blank lines** between diagrams when listing multiple patterns.
- Never run diagrams back-to-back with a single blank line or no separator.

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

### What NOT to do
- Do not always pick the widest interval available — that produces uniformly safe, timid patterns.
- Do not always move monotonically up the neck across strings.
- Do not generate 5 examples that all look structurally identical (same angle, same interval width).
