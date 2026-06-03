"""Render the three E harmonic minor scalar-run flavors stacked top-to-bottom
as one PNG. Each flavor: title, treble_8 staff with the six ascending notes,
subtitle (sequence + step pattern), then the ASCII tab. Staff notation is
engraved via LilyPond.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import fretboard as fb

_PC_TO_LY = {0: 'c', 1: 'cis', 2: 'd', 3: 'dis', 4: 'e', 5: 'f',
             6: 'fis', 7: 'g', 8: 'gis', 9: 'a', 10: 'ais', 11: 'b'}


def midi_to_ly(midi):
    """LilyPond absolute pitch from MIDI (c' = middle C = MIDI 60)."""
    pc = midi % 12
    octave = midi // 12 - 1
    name = _PC_TO_LY[pc]
    if octave >= 3:
        return name + "'" * (octave - 3)
    return name + "," * (3 - octave)


def render_staff_png(seq, out_no_ext):
    notes = ' '.join(midi_to_ly(m) + '1' for m in seq)
    ly = rf"""\version "2.24.0"
\paper {{
  paper-width = 7\in
  paper-height = 1.4\in
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
    {notes}
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
        capture_output=True, text=True
    )
    if res.returncode != 0:
        print(res.stderr[-1500:])
        raise RuntimeError("LilyPond failed")
    return out_no_ext + '.png'


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else '/tmp/harm_minor'
    os.makedirs(out_dir, exist_ok=True)

    flavors = [
        ('Strict 2nds — span 10, 2 drones',
         dict(allow_one_minor_third=False, max_body_span=12)),
        ('One m3 allowed (default) — span 3, 4 drones',
         dict()),
        ('One wild jump allowed — span 0, 5 drones',
         dict(allow_one_wild_jump=True)),
    ]

    items = []
    for i, (title, kwargs) in enumerate(flavors):
        c = fb.find_scalar_runs('E', 'harmonic_minor', **kwargs)[0]
        d = fb.generate_scalar_run_and_render('E', 'harmonic_minor', **kwargs)
        dec = fb.decorate(d, 'E', 'harmonic_minor', c['string_configs'])
        seq = c['sequence_midi']
        steps = ', '.join(str(seq[j + 1] - seq[j]) for j in range(5))
        notes_str = ' '.join(fb.NOTE_NAMES[m % 12] for m in seq)
        sub = f"sequence: {notes_str}    steps: [{steps}]"
        staff_png = render_staff_png(seq, os.path.join(out_dir, f'flavor_{i}'))
        items.append((title, sub, dec, staff_png))

    from PIL import Image, ImageDraw, ImageFont
    f_title = ImageFont.truetype(
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
    f_sub = ImageFont.truetype(
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
    f_tab = ImageFont.truetype(
        '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 16)

    # Pre-measure each block
    blocks = []
    dummy = Image.new('RGB', (10, 10))
    dd = ImageDraw.Draw(dummy)
    for title, sub, dec, staff_png in items:
        staff = Image.open(staff_png)
        bbox = staff.convert('L').point(lambda x: 0 if x > 240 else 255).getbbox()
        if bbox:
            staff = staff.crop(bbox)
        sw, sh = staff.size
        tab_lines = dec.split('\n')
        tab_h = len(tab_lines) * (f_tab.size + 6)
        tab_w = max(dd.textlength(ln, font=f_tab) for ln in tab_lines)
        block_w = int(max(sw, tab_w, dd.textlength(title, font=f_title))) + 40
        block_h = f_title.size + 12 + sh + 8 + f_sub.size + 12 + tab_h + 24
        blocks.append((title, sub, tab_lines, staff, sw, sh, int(tab_w),
                       tab_h, block_w, block_h))

    out_w = max(b[8] for b in blocks)
    out_h = sum(b[9] for b in blocks) + 20
    final = Image.new('RGB', (out_w, out_h), 'white')
    draw = ImageDraw.Draw(final)

    y = 10
    for (title, sub, tab_lines, staff, sw, sh, tw, th,
         block_w, block_h) in blocks:
        # Title (left-aligned)
        draw.text((20, y), title, font=f_title, fill='black')
        y += f_title.size + 12
        # Staff (left-aligned)
        final.paste(staff, (20, y))
        y += sh + 8
        # Subtitle
        draw.text((20, y), sub, font=f_sub, fill='#555')
        y += f_sub.size + 12
        # Tab block
        for ln in tab_lines:
            draw.text((40, y), ln, font=f_tab, fill='black')
            y += f_tab.size + 6
        y += 24

    out_path = os.path.join(out_dir, 'harm_minor_3way.png')
    final.save(out_path)
    print(f"wrote {out_path}  ({out_w}x{out_h})")


if __name__ == '__main__':
    main()
