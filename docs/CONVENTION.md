# Diagram Convention

This document is the canonical reference for the **fretboard-faithful ASCII
diagram** style used by this library.

## Structure

A diagram is **6 lines** representing the 6 strings of a guitar in standard
tuning, ordered with the **highest-pitched string on top**:

```
e|     <- high E (1st string)
B|
G|
D|
A|
E|     <- low E (6th string)
```

Each line is prefixed with the string letter followed by a pipe `|`, then a
sequence of dashes and digits, then a closing pipe `|`.

## Columns are frets

The horizontal position of a digit in the diagram corresponds to its **actual
fret position** on the neck. A `5` in column 5 means fret 5. This makes
diagrams a literal mini neck-map rather than abstract tab.

```
e|----4-6----|
       ^   ^
       |   fret 6
       fret 4
```

## Adjacent frets squeeze

When two consecutive frets are both played on the same string, they sit in
adjacent columns with no separator: `34`, `67`, `78`. This is the necessary
compromise for monospace text — otherwise consecutive frets would waste space.

```
B|---34---|     <- frets 3 and 4 on the B string
```

## Non-adjacent frets use dashes that reflect the gap

The number of dashes between two frets equals the number of skipped frets:

| Frets played | Gap (skipped) | Notation |
|--------------|---------------|----------|
| 5 and 7      | 1 fret (6)    | `5-7`    |
| 3 and 6      | 2 frets (4,5) | `3--6`   |
| 3 and 7      | 3 frets (4,5,6) | `3---7`  |

This keeps column position fret-accurate.

## ASCII only

Use only **plain ASCII hyphen-minus** (`-`, U+002D). Never em dash (`—`,
U+2014) or en dash (`–`, U+2013). Many text editors and chat clients
auto-substitute these and break the layout.

## Padding

Pad with extra dashes on the right so all lines end at the same column with
the closing `|` aligned vertically.

## Lowest fret ≥ 3

Patterns are transposed so the lowest fret is at least 3, avoiding open
strings entirely. This keeps the visual style consistent (every position is
fretted) and avoids the alignment break caused by open-string notation
(`e0...` is one character where `B|...` is two).

When transposing for this rule, the **shape is preserved** — the scale's
identity may change (different root) but the fingering pattern is the same.

## Two-digit frets

Frets 10 and above are rendered as a single digit equal to `fret % 10`:
fret 10 → `0`, 11 → `1`, 12 → `2`, 13 → `3`, and so on. The displayed digit
is cosmetic — **column position is authoritative for the actual fret**, so
a `0` in column 10 means fret 10, a `3` in column 13 means fret 13.

This works because the convention forbids open strings (lowest fret ≥ 3),
so a digit at columns 0–2 never appears and there's no collision with
single-digit frets 0–2.

```
G|----------90------|     <- frets 9 and 10 on G
e|------------23----|     <- frets 12 and 13 on e
```

## What this is NOT

This is **not standard guitar tablature**:

- There is **no rhythm** or time information
- Horizontal position does not indicate when notes are played
- It's a **scale/position diagram** showing which frets to play on which strings

## Example

C Hungarian Minor in 3rd position:

```
e|---34-------------|
B|---34-------------|
G|----45------------|
D|----45------------|
A|---3-5------------|
E|---34-------------|  C Hungarian Minor
```
