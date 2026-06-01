# fretboard-utils — Claude guidelines

## Standard tab format (enshrined)

Every generated tab — 2NPS, 3NPS, **and** arpeggios — uses this per-line layout:

```
NOTE(degree)  CONFIG body|  [chord_label]
```

- **Left column** — `Note(degree)`: drone note + its interval from the root,
  spelled via `DEGREE_LABEL` (e.g. `G#(1)`, `B(3)`, `D(♯4)`, `C#(4)`). The
  interval label works for any scale size — 8-note diminished scales and the
  12-note chromatic scale included — and an out-of-scale drone simply reads as
  its own chromatic degree. For X-muted strings the implicit open-string drone
  is still labelled. Built by `drone_label(...)`.
- **CONFIG**: `0` (open), `'1'..'9'` (capo fret), `X` (muted), `|` (fretted-only).
- **body**: standard ASCII tab body, with the highest spider-capo bar's
  fret-shift already applied.
- **Right column (arp tabs only)** — `chord_label`: chord formed by drone +
  body notes on that string, e.g. `Em7 (1♭357)`, `Bdim7 (1♭5♭♭7)`. Built by
  `per_string_chord(...)`. 2NPS and 3NPS tabs do NOT carry this column.

The `decorate(diagram, root, scale, string_configs, with_chords=False)` helper
turns a plain `render()` output into this format. `render_full_set` calls it
automatically when the full_set carries metadata (root, scale, string_configs)
— which `generate_full_set` always sets.

**Important**: the decorated form is for display only; it does NOT round-trip
through `parse_diagram` (the leading string letter is replaced). Always run
`verify` on the raw diagram BEFORE decorating, which is what
`generate_full_set` already does internally.

When you write a chat reply that includes generated tabs, the chat header
(above the first code block) should still spell out the scale and capos using
`scale_spelling`, `scale_degree_labels`, `capo_summary`. The per-line
`Note(degree)` and `chord_label` come from the tab itself.

## API Reference (what's already in the repo — DO NOT re-implement)

Before writing any new naming/labeling/spelling code, check this list. All helpers
below already exist in [src/fretboard.py](src/fretboard.py). Use them.

### Constants and tables
- `OPEN_STRINGS` — dict mapping string letter to open pitch class (the *active*
  tuning; guitar EADGBe by default).
- `OPEN_MIDI` — dict mapping string letter to absolute open MIDI number (E2 = 40
  for guitar). Used by the cluster finder, which needs absolute pitch to check
  whether the strummed drones ascend across the strings.
- `NOTE_NAMES` — 12 sharps-only note names.
- `STRING_ORDER_LOW_TO_HIGH`, `STRING_ORDER_DISPLAY` — string letter orderings
  (also reflect the active tuning).
- `SCALES` — dict of scale name → list of intervals from root.
- `STRETCH_PROFILES` — preset per-string (min_stretch, max_stretch) profiles for `generate_2nps`.
- `MAX_FINGER_STEP` — global hard cap on adjacent-fingered-note distance (m3 = 3).
  See `effective_finger_step(scale)` for the per-scale cap (raised to M3 = 4 for
  scales with no minor 3rd, e.g. whole-tone).
- `DEGREE_LABEL` — semitone-interval → degree string (`'1'`, `'♭2'`, `'3'`, `'♯4'`, `'♯5'`, …).

### Instrument tunings
- The module defaults to 6-string guitar (EADGBe). To generate/render for another
  instrument, wrap the calls in `with use_tuning(name): …`. This temporarily
  rebinds the tuning globals (`OPEN_STRINGS`, the string orders, the line regex,
  `STRETCH_PROFILES`) and restores them on exit.
- Presets: `'guitar'` (EADGBe), `'bass_6'` (BEADGC, low B to high C).
- Inside a tuning block, "root on the lowest string" targets that tuning's lowest
  string (B for `bass_6`, E for guitar). String letters may differ (bass adds a
  low `B` and high `C`); all helpers key off the active `OPEN_STRINGS`.

### Pitch math
- `scale_pitches(root, scale)` → set of pitch classes in the scale. Use to test scale membership.
- `pitch_at(string, fret)` → pitch class at this string/fret.
- `note_name(string, fret)` → human note name like `'F#'`.
- `chord_tones(root, scale, degrees=(1,3,5))` → set of pitch classes for a chord built from
  the named scale degrees. Default is the diatonic triad; pass `(1, 3, 5, 7)` for the 7th chord.

### Naming / labeling (use these in chat output — don't recompute inline)
- `scale_spelling(root, scale)` → ordered list of note names, e.g. `['E', 'F', 'G#', 'A#', 'C', 'D', 'D#']`.
- `scale_degree_labels(scale)` → degree labels for the scale's intervals, e.g. `['1', '♭2', '3', '♯4', '♯5', '♭7', '7']`.
- `chord_name(root, scale, degrees)` → short chord name, e.g. `'E aug'`, `'C maj7'`, `'G#sus4'`.
  Recognises common triad and 7th-chord patterns; falls back to `Root(deg-deg-deg)` for exotic stacks.
- `drone_label(string, string_configs, root, scale)` → `'G♯(3)'`-style label showing
  the drone note and its scale-degree role on a given string.
- `capo_summary(string_configs)` → human description, e.g.
  `'capo 1 on A,G (→A♯,G♯); capo 4 on B (→D♯)'`. Returns `'no capo'` when there are no spider capos.

**When you write a chat reply describing a pattern**, the header should always include:
scale spelling (`scale_spelling` + `scale_degree_labels`), capo summary (`capo_summary`),
and chord names for arpeggios (`chord_name`). Do not omit these on follow-up replies.

### Diagram parsing / verification
- `parse_diagram(diagram)` → list of `(string, fret, body_col)` tuples. Honors the column-shift
  introduced by the highest spider-capo bar.
- `verify(diagram, root, scale)` → True iff every parsed note is in the scale.
- `all_diagram_frets_in_range(diagram, string_configs)` → True iff no body fret sits at or
  below the highest capo (the bar physically blocks those positions).

### Pickers (low-level — usually called via the generators below)
- `pick_pair(frets, target, min_stretch, max_stretch, required_pc, string_pc)` → 2-tuple of frets.
- `pick_triple(frets, target, min_span, max_span, max_step, …)` → 3-tuple of consecutive in-scale frets.
- `pick_single(frets, target, …)` → 1-tuple, the closest in-scale fret to target.
- `frets_in_scale(string, pitches, fret_min, fret_max, capo_fret)` → list of in-scale frets.

`max_stretch` (in `pick_pair`) and `max_step` (in `pick_triple`) are **hard-capped at MAX_FINGER_STEP**:
caller-passed values above the cap are silently clamped.

### Generators (low-level — return raw `{string: tuple_of_frets}` patterns)
- `generate_2nps(root, scale, …)` — 2-notes-per-string scale pattern. Knobs:
  `start_fret`, `min_stretch`, `max_stretch`, `direction`, `position_shift`,
  `string_configs`, `stretch_profile`, `pitches` override, `require_root_on_low_e`.
  `direction` is one of: `'up'` (ascending box), `'free'` (per-string target =
  `start_fret + idx·position_shift`), `'down'` (descending diagonal, ~−2/string),
  `'climb'` (gentle ascent, ~+2/string), `'fast_climb'` (steep ascent, ~+5/string).
  The `down`/`climb`/`fast_climb` slopes are defaults used when `position_shift=0`.
- `generate_3nps(root, scale, …)` — 3-notes-per-string at one position. Knobs:
  `start_fret`, `min_span`, `max_span`, `max_step`, `position_shift`, `string_configs`,
  `require_root_on_low_e`.
- `generate_arpeggio(root, scale, …)` — chord-tone pattern. Tries a 2-chord-tone pair
  within `max_stretch` (default `MAX_FINGER_STEP`) on each string and falls back to
  one chord tone where no pair fits. Default `degrees=(1, 3, 5, 7)`.
- `find_cluster_drones(root, scale, max_capo=4, max_distinct_capos=2)` —
  enumerate every spider-capo configuration whose six drone pitch classes form
  a contiguous block of scale tones. Returns ranked list of dicts with
  `'string_configs'`, `'drone_pcs'`, `'drones_midi'`, `'capo_frets'`,
  `'top_capo'`, `'ascending'`.
- `generate_cluster(root, scale, body_notes_per_string=0, …)` — pick the
  best cluster config and (optionally) add body notes. Returns
  `(string_configs, pattern)`.

### Generators (high-level — return verified, rendered ASCII diagrams)
- `generate_and_render(root, scale, …)` — 2NPS, verified.
- `generate_3nps_and_render(root, scale, …)` — 3NPS, verified.
- `generate_arpeggio_and_render(root, scale, …)` — arpeggio, verified.
- `generate_cluster_and_render(root, scale, …)` — **cluster mode**: search the
  spider-capo space for a configuration whose six drone pitches form six
  consecutive scale-tones (a stacked-seconds cluster chord when strummed).
  See "Cluster mode" below for the math and what it does and doesn't deliver.
  Knobs: `max_capo` (default 4), `max_distinct_capos` (default 2),
  `body_notes_per_string` (default 0 — drones-only diagram; >0 adds that many
  fretted in-scale notes per string, picked just above each drone), `choose`
  (which ranked candidate to use; 0 = best).
- `generate_full_set(root, scale, string_configs=None, second_capo_fret=None, …)` →
  dict with three labeled sections: `'two_note'` (**6 variants**: tight, wide,
  alternating, descending, climbing, fast climbing), `'three_note'` (3 ascending
  positions), `'arpeggio'` (triad + 7th-chord versions).
  Root is forced onto the lowest string in every diagram. Pass `second_capo_fret=N` to
  convert any `'X'` strings into a second spider capo at fret N.

### Rendering
- `render(pattern, label, width, string_configs)` — base ASCII renderer for one pattern.
  Honors capo-bar shift in the body columns.
- `render_full_set(full_set, gap)` — arranges a `generate_full_set()` result into a
  3-row grid with centred labels per column.
- `side_by_side(left, left_label, right, right_label, gap)` — two diagrams + labels.

### Validation
- `_validate_capo_count(string_configs, max_capos=2)` — raises `ValueError` if there are
  more than 2 distinct spider-capo frets. Called by every public `generate_*_and_render`.

## When to use which function

| Need | Call |
|---|---|
| Quick one-off diagram for a scale | `generate_and_render(root, scale)` |
| Higher-density single-position scale | `generate_3nps_and_render(root, scale, start_fret=…)` |
| Chord-tone outline | `generate_arpeggio_and_render(root, scale, degrees=…)` |
| Strum-a-cluster capo config | `generate_cluster_and_render(root, scale)` |
| Practice set (8 diagrams) | `generate_full_set(...)` then `render_full_set(...)` |
| Two diagrams labelled side-by-side | `side_by_side(...)` |
| Custom pattern (build the dict yourself) | `pick_pair`/`pick_triple`/`pick_single` then `render` |
| Verify a hand-written diagram | `verify(diagram, root, scale)` |
| Spell out the scale for a chat header | `scale_spelling` + `scale_degree_labels` |
| Spell out the capos for a chat header | `capo_summary` |
| Annotate a string with its drone role | `drone_label` |
| Name a chord built from scale degrees | `chord_name` |

## Demo / example output

### Human readability
- Output each diagram in its **own separate markdown code block** in the response.
  Blank lines between diagrams are stripped by the renderer; separator lines are ugly.
  A new ``` fence between each diagram is the only reliable visual break.

### PDF / printable output
- **Default to portrait page orientation** when generating PDFs of tabs or full
  sets. Only use landscape when the content genuinely cannot be made to fit
  portrait, or when the user explicitly asks for landscape.
- Label the instrument ("Guitar" / "Bass") clearly at the top of each page.
- `examples/french_sixth_pdfs.py` is the reference generator: portrait, one page
  per scale, full sets laid out two diagrams per row, with DejaVu Sans Mono for
  the monospace grid (it carries the ♭/♯/→ glyphs that the PDF core fonts lack).

### Finger-reach cap
- `MAX_FINGER_STEP` (in `src/fretboard.py`) is the **global hard cap** on the
  largest semitone gap between two adjacent fingered notes on one string.
  Default: **3 semitones (minor 3rd)**.
- **Major-3rd exception**: a scale that contains no minor 3rd *anywhere* (no two
  of its tones are 3 semitones apart — e.g. the whole-tone scale, all-even
  intervals) has no m3 grouping to reach for, so its smallest "wide" 2-note
  option is a major 3rd. For such scales the cap is raised one semitone to a
  **major 3rd (4)**. `effective_finger_step(scale_name)` returns the per-scale cap
  (4 for whole-tone, 3 for everything else, since every other scale in `SCALES`
  has a minor 3rd somewhere). The generators compute it and pass it to the
  pickers as `cap=`.
- Hard-capped in `pick_pair` and `pick_triple` — any caller-passed
  `max_stretch` or `max_step` above `cap` is silently clamped to it.
  This applies uniformly: scales (all 6 two-note variants), 3NPS, arpeggios.
- Arpeggios default to `degrees=(1, 3, 5, 7)` (the diatonic 7th chord).
  Adding the 7th brings in a m2 or M2 around the 7-1 boundary in most
  chord types, so 2-note-per-string pairs within m3 are usually available
  even when the bare triad is augmented (e.g. E enigmatic 1-3-5 = E aug,
  but 1-3-5-7 = E aug-maj7 has D#-E m2 and C-D# m3).
- When no chord-tone pair fits within m3 on a given string, the arpeggio
  falls back to a single chord tone closest to the target.

### Open-string drone counts as the root
- A non-capo'd, non-muted string drones its open pitch. If that open pitch
  equals the scale root, `require_root_on_low_e` is already satisfied — the
  generator does NOT then drag a body note up to a higher octave of the root.
  This matters for E-rooted scales on the low E string especially.

### Capo bar blocks all strings
- The highest spider-capo bar physically occupies its fret across the whole neck.
  No body note may sit at or below that fret on **any** string, capo'd or not.
- The renderer enforces this visually: with a higher capo at fret M, the body's
  first column (after the prefix space) represents fret M+1, not fret 1. The
  space at body[0] is the bar itself.

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
- **Up to two distinct spider-capo frets per pattern.** A second spider capo is the
  preferred way to "remove" X strings: give those strings a drone at a different fret
  rather than leaving them silent. Three or more distinct capo frets is rejected by
  `_validate_capo_count` in `fretboard.py`.
- **Never capo all 6 strings at the same fret with a single capo** — that is just a
  transposition and should be expressed as the equivalent key with no capo. Rule: if
  one capo would go all the way across at fret N, transpose the root DOWN by N
  semitones and use no capo. Example: G altered + capo 1 all strings → F# (Gb) altered,
  no capo. Two capos at *different* frets covering all six strings is fine — not a
  transposition.
- **Rarely more than one `'X'` string per pattern**, but this is a guideline not a hard rule.
  `X` means "fretted normally, no open/capo drone shown on this string." Prefer using a
  second capo to provide a drone instead.
- Choose capo fret and which strings get it based on which drone tones are harmonically
  interesting (in-scale, dissonant, or a mix) — don't default to all-six every time.

### 3NPS scale-tone continuity
- `generate_3nps` defaults to `continuous=True`: each string starts on the
  **next scale tone** after the previous string's last note. This lays out
  18 consecutive scale tones evenly across the 6 strings — the classical
  3NPS shape — with no repeated pitches at string boundaries.
- Without continuity, the picker can pick a triple that starts on the same
  pitch class the previous string ended on (e.g. low E ending at fret 12 = E
  and A string starting at fret 7 = E — same note, redundant).
- The fallback chain: if no continuous triple is reachable on a string
  (e.g. the required first pitch class lies past `fret_max`), drop the
  continuity constraint, then the root-on-low-E constraint, then relax span.

### Cluster mode (capo-driven stacked-seconds drone chord)
- **Idea**: pick spider-capo positions so that the six open/capo drones land on
  six adjacent scale-tones (a "cluster of seconds" chord voicing) — the
  alternative to the 3rds-and-4ths voicings that natural tunings produce.
- **Hard fact (don't promise more than this delivers)**: with `max_capo=4` and
  any standard tuning, a strictly stepwise ascending run across all six
  strings is mathematically impossible. The natural open-string intervals
  (P4 / M3) total ≥ 24 semitones across the five string boundaries; capos
  add only 0..4 frets per string, so the capo budget cannot compress those
  intervals down to seconds across five jumps. The six drones can still form
  a **stacked-seconds chord** when strummed, but the strummed *order* will
  include some jumps wider than a second.
- `find_cluster_drones` brute-forces all `(max_capo+1)^6` capo combinations,
  filters to those with ≤ `max_distinct_capos` distinct nonzero frets and
  six distinct drone pcs that form a contiguous scale-tone block, and ranks:
  1. configs whose drone midi sequence strictly ascends across strings,
  2. then fewer distinct capo frets (1 > 2),
  3. then lower top capo fret (more playable).
- `generate_cluster` picks the best (or `choose=k`-th best) config. By
  default `body_notes_per_string=0` — the diagram is the capo config itself,
  with empty body. Setting it to `1` adds one in-scale fret per string just
  above each drone, picked above `body_fret_min` (which respects the highest
  capo bar) — useful as a scalar continuation when picking the strings.
- Works under `use_tuning('bass_6')` (BEADGC) too. Bass has uniform P4
  intervals so cluster solutions are still findable; capos required tend to
  be higher than on guitar.

### Arpeggio picker (pair-first, chord-forming, full scale)
- `generate_arpeggio` pulls from the **full scale** (not a fixed chord-tone
  set) so the picker has dense pair options near every position.
- On each string the picker considers every 2-note pair within `max_stretch`.
  For each pair it checks whether **drone + body notes** form a recognised
  triad or 7th chord (see chord naming below). Pairs are ranked by **middle
  -fret proximity to the target** so a pair that straddles the target wins.
- **drone→f1 constraint**: the lower body note must sit at least a m3 from
  the drone (allowed range: m3..♭6 = 3..8 semitones). This enforces actual
  arpeggio character rather than a chromatic cluster around the drone.
- **Variety bonus**: across the 6 strings of one arpeggio, the picker
  tracks which chord *types* (interval signatures) and *identities*
  (pitch-class sets) have already appeared, and subtracts a bonus from the
  score of unused options — so each string is nudged toward a fresh chord.
  The bonus is small enough that proximity still dominates for large
  jumps (won't drag a string halfway up the neck just for variety).
- Selection priority:
  1. The closest chord-forming pair within `2 * max_stretch` of the target.
  2. A non-chord pair within `max_stretch` of the target — but only if it
     is significantly closer (more than `max_stretch` better in middle-fret
     proximity) than the best chord-forming pair. This keeps the pattern
     compact when chord-forming options would force a big jump.
  3. A single chord tone when no pair at all fits.
- In a full set, both arps use the same picker and differ only in
  `start_fret` (`base` and `base + 5`) — no triad-vs-7th distinction.
- Result: most strings land on a recognised triad or 7th chord, the pattern
  stays compact across the neck, and per-line chord labels are meaningful.

### Chord naming (triads and 7th chords only)
`per_string_chord` recognises **triads and 7th chords only**, including their
dyad fragments when the quality is unambiguous. 6th chords, add chords,
slash chords, clusters etc. are NOT in the recognised set — they show as
`Drone? (degree-list)`.
- Dominant 7 is labelled `7`; major 7 is labelled `Δ7` (always distinguish).
- Dyads:
  - `(0, 4)` → `` (major, no 5)
  - `(0, 3)` → `m` (minor, no 5)
  - `(0, 6)` → `dim`
  - `(0, 8)` → `aug`
  - `(0, 7)` → `5` (power chord)
  - `(0, 2)` → `sus2`
  - `(0, 5)` → `sus4`
  - `(0, 11)` → `Δ7` (major 7 fragment)
  - `(0, 10)` → `7` (dominant 7 fragment)
- Triads (complete) — major, minor, dim, aug, sus2, sus4.
- 7th chords (complete OR with the 5 or 3 omitted) — `Δ7`, `7`, `m7`, `mΔ7`,
  `m7♭5`, `dim7`, `augΔ7`, `aug7`.
- Anything else (intervals not in `_CHORD_TYPE_NAMES`) → `Drone? (degrees)`.

### Full sets
- `generate_full_set(root, scale, ...)` returns three rows of diagrams: 3 two-note
  variations, 3 three-note (3NPS) positions ascending up the neck, and 2 arpeggios.
- The **root is forced onto the low E string** in every diagram of a full set
  (and is also available via `require_root_on_low_e=True` on the individual generators).
- Pass `second_capo_fret=N` to convert any `'X'` strings to a second spider capo at fret N.

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
