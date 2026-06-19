"""Render the three single-capo "idea" diagrams as one stacked PNG:
each idea gets a treble_8 staff with the strummed drone chord (whole notes),
the ASCII tab showing capo placement and the resulting drones, and a label
naming the implied scale.

Run: python3 examples/single_capo_ideas.py [output_dir]
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import fretboard as fb

_PC_TO_LY = {0: 'c', 1: 'cis', 2: 'd', 3: 'dis', 4: 'e', 5: 'f',
             6: 'fis', 7: 'g', 8: 'gis', 9: 'a', 10: 'ais', 11: 'b'}


def midi_to_ly(midi):
    pc = midi % 12
    octave = midi // 12 - 1
    name = _PC_TO_LY[pc]
    if octave >= 3:
        return name + "'" * (octave - 3)
    return name + "," * (3 - octave)


def render_staff_png(chord_midis, melody_midis, out_no_ext):
    """Render a treble_8 staff with one stacked chord (whole notes) then a few
    'missing scale tone' notes after it as half-note suggestions for melody."""
    chord = ' '.join(midi_to_ly(m) for m in sorted(chord_midis))
    melody_seq = ' '.join(midi_to_ly(m) + '2' for m in melody_midis)
    ly = rf"""\version "2.24.0"
\paper {{
  paper-width = 8\in
  paper-height = 1.6\in
  top-margin = 0.05\in
  bottom-margin = 0.05\in
  left-margin = 0.2\in
  right-margin = 0.2\in
  tagline = ##f
}}
\score {{
  \new Staff \with {{
    \override TimeSignature.stencil = ##f
    \override BarLine.stencil = ##f
  }} {{
    \clef "treble_8"
    \cadenzaOn
    <{chord}>1
    \bar "|"
    {melody_seq}
  }}
  \layout {{ indent = 0  ragged-right = ##t }}
}}
"""
    ly_path = out_no_ext + '.ly'
    with open(ly_path, 'w') as f:
        f.write(ly)
    res = subprocess.run(
        ['lilypond', '--png', '-dresolution=200',
         '-o', out_no_ext, ly_path],
        capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stderr[-1500:])
        raise RuntimeError("LilyPond failed")
    return out_no_ext + '.png'


# Each idea: (title, capo_fret, capo_positions, midi_per_string, scale_root, scale_name, comment)
# midi_per_string is the actual sounding MIDI at each string position 0..5 (low to high).
OPEN_MIDI = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4


def build_midis(capo_fret, capo_positions):
    return [OPEN_MIDI[i] + (capo_fret if i in capo_positions else 0) for i in range(6)]


def ascii_drone_tab(capo_fret, capo_positions, root, scale_name, label):
    cfg = {i: capo_fret for i in capo_positions}
    diagram = fb.render({i: () for i in range(6)},
                        label=label, width=18,
                        string_configs=cfg)
    return fb.decorate(diagram, root, scale_name, cfg)


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else '/tmp/single_capo_ideas'
    os.makedirs(out_dir, exist_ok=True)

    ideas = [
        # (title, capo_fret, set-of-positions, root, scale, melody-tone hints)
        ('Idea 1 — capo 3 on D, G  →  F Persian / E exotic',
         3, {2, 3}, 'F', 'persian',
         "Drones F A A♯ B E; missing scale tones to target: G♭, D♭, C♯"),
        ('Idea 2 — capo 2 on E, A, D, B  →  D major / E kumoi voicing',
         2, {0, 1, 2, 4}, 'D', 'major',
         "Drones F♯ B E G C♯ E; an Em6/9 / DΔ7 sound. Root (D) and 5 (A) absent — floats."),
        ('Idea 3 — capo 1 on D, G  →  E Double Harmonic (Byzantine)',
         1, {2, 3}, 'E', 'double_harmonic',
         "Drones E A D♯ G♯ B E; covers 1 3 4 5 7. Missing scale tones: F (♭2), C (♭6)."),
    ]

    items = []
    for i, (title, fret, caps, root, scale, sub) in enumerate(ideas):
        midis = build_midis(fret, caps)
        # melody hints = scale tones NOT in the drone chord
        scale_pcs = fb.scale_pitches(root, scale)
        drone_pcs = {m % 12 for m in midis}
        missing_pcs = sorted(scale_pcs - drone_pcs)
        # render those at a comfortable octave (around middle C / above)
        melody = [60 + p if p < 8 else 48 + p for p in missing_pcs]
        # bump to put around C5 if too low
        melody = sorted(set(melody))
        staff_png = render_staff_png(midis, melody, os.path.join(out_dir, f'idea_{i}'))
        tab = ascii_drone_tab(fret, caps, root, scale, f'{root} {scale}')
        items.append((title, sub, tab, staff_png))

    from PIL import Image, ImageDraw, ImageFont
    f_title = ImageFont.truetype(
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    f_sub = ImageFont.truetype(
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
    f_tab = ImageFont.truetype(
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 16)

    blocks = []
    dummy = Image.new('RGB', (10, 10))
    dd = ImageDraw.Draw(dummy)
    for title, sub, tab, staff_png in items:
        staff = Image.open(staff_png)
        bbox = staff.convert('L').point(lambda x: 0 if x > 240 else 255).getbbox()
        if bbox:
            staff = staff.crop(bbox)
        sw, sh = staff.size
        tab_lines = tab.split('\n')
        tab_h = len(tab_lines) * (f_tab.size + 6)
        tab_w = max(dd.textlength(ln, font=f_tab) for ln in tab_lines)
        block_w = int(max(sw, tab_w, dd.textlength(title, font=f_title))) + 40
        block_h = f_title.size + 12 + sh + 8 + f_sub.size + 12 + tab_h + 24
        blocks.append((title, sub, tab_lines, staff, sw, sh, tab_h, block_w, block_h))

    out_w = max(b[7] for b in blocks)
    out_h = sum(b[8] for b in blocks) + 20
    final = Image.new('RGB', (out_w, out_h), 'white')
    draw = ImageDraw.Draw(final)

    y = 10
    for title, sub, tab_lines, staff, sw, sh, th, bw, bh in blocks:
        draw.text((20, y), title, font=f_title, fill='black')
        y += f_title.size + 12
        final.paste(staff, (20, y))
        y += sh + 8
        draw.text((20, y), sub, font=f_sub, fill='#555')
        y += f_sub.size + 12
        for ln in tab_lines:
            draw.text((40, y), ln, font=f_tab, fill='black')
            y += f_tab.size + 6
        y += 24

    out_path = os.path.join(out_dir, 'single_capo_ideas.png')
    final.save(out_path)
    print(f"wrote {out_path}  ({out_w}x{out_h})")


if __name__ == '__main__':
    main()
