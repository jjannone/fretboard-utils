"""Generate portrait full-set PDFs for the French-sixth tuning, guitar and bass.

Two multi-page PDFs (one per instrument), one page per scale, bundled into a zip:

  guitar (EADGBe): capo 1 on A,G; capo 3 on B  -> drones E,A#,F#?...  no:
      open E, D, e; A#,G# at capo 1; D at capo 3  => French sixth {E,G#,A#,D}, no X.
  bass (BEADGC):   capo 1 on A,G; capo 3 on low B; C muted
      => same French sixth {E,G#,A#,D}, with the high C string muted (X).

Each page shows a full set: six 2-note-per-string variants (tight, wide,
alternating, descending, climbing, fast climbing), three 3NPS positions, and two
arpeggios -- laid out two diagrams per row in portrait.

Run:  python3 examples/french_sixth_pdfs.py [output_dir]
"""
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fpdf import FPDF

from fretboard import (
    generate_full_set, use_tuning, decorate, capo_summary,
    scale_spelling, scale_degree_labels,
)

MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
MONO_B = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
SANS = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
SANS_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

ROOT = 'E'
BODY_WIDTH = 14  # min body columns; render auto-expands for wide (fast-climb) shapes

SCALES = {
    'whole_tone':      ('Whole Tone',
                        'Symmetric, no leading tone; the wide variant uses M3 (no m3 exists).'),
    'half_whole_dim':  ('Half-Whole Diminished',
                        'Octatonic dominant (H-W); drones outline the E7b5 backbone.'),
    'lydian_dominant': ('Lydian Dominant',
                        'Acoustic scale - bright dominant with #4; drones = 1 3 #4 b7.'),
    'altered':         ('Altered',
                        'Super-Locrian (7th mode of F melodic minor); every tension altered.'),
    'enigmatic':       ("Enigmatic",
                        "Verdi's scale - b2 over a whole-tone top; exotic and unresolved."),
}

INSTRUMENTS = {
    'guitar': {'tuning': 'guitar', 'cfg': {'A': 1, 'G': 1, 'B': 3},
               'drone_note': 'Drones spell the French sixth {E, G#, A#, D} = E7b5 / A#7b5 (no muted string)'},
    'bass':   {'tuning': 'bass_6', 'cfg': {'B': 3, 'A': 1, 'G': 1, 'C': 'X'},
               'drone_note': 'Drones spell the French sixth {E, G#, A#, D}; high C string muted (X)'},
}


def _cell(caption, decorated):
    """One diagram cell: a caption line above the six string lines."""
    return [caption] + decorated.split('\n')


def _join_row(cells, gap=4):
    """Lay out cells side by side, padding to equal height/width."""
    height = max(len(c) for c in cells)
    widths = [max((len(ln) for ln in c), default=0) for c in cells]
    padded = [c + [''] * (height - len(c)) for c in cells]
    rows = []
    for i in range(height):
        rows.append((' ' * gap).join(p[i].ljust(w) for p, w in zip(padded, widths)))
    return rows


def _rows_of_two(items):
    """Group (caption, diagram) items into rows of two cells, return text lines."""
    cells = [_cell(lbl, d) for lbl, d in items]
    out = []
    for i in range(0, len(cells), 2):
        out += _join_row(cells[i:i + 2])
        out.append('')  # gap between rows
    return out


def grid_text(fs, scale):
    """Full monospace grid for one scale's full set (two diagrams per row)."""
    dec = lambda d, wc: decorate(d, ROOT, scale, fs.string_configs, with_chords=wc)
    lines = []
    lines.append('2-note-per-string:')
    lines += _rows_of_two([(lbl, dec(d, False)) for lbl, d in fs['two_note']])
    lines.append('3-note-per-string:')
    lines += _rows_of_two([(lbl, dec(d, False)) for lbl, d in fs['three_note']])
    lines.append('Arpeggios:')
    lines += _rows_of_two([(lbl, dec(d, True)) for lbl, d in fs['arpeggio']])
    return [ln for ln in lines]


def add_page(pdf, instrument, scale_key, title, note, drone_note, cfg):
    fs = generate_full_set(ROOT, scale_key, string_configs=cfg, width=BODY_WIDTH)
    grid = grid_text(fs, scale_key)

    spelling = ' '.join(scale_spelling(ROOT, scale_key))
    degrees = ' '.join(scale_degree_labels(scale_key))
    capos = capo_summary(cfg)

    pdf.add_page()  # A4 portrait
    left, top = 12, 12
    usable_w_mm = 210 - 2 * left

    # ---- header (proportional font) ----
    pdf.set_xy(left, top)
    pdf.set_font('Sans', 'B', 22)
    pdf.cell(0, 10, instrument.upper(), new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Sans', 'B', 14)
    pdf.cell(0, 7, f'{ROOT} {title}', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Sans', '', 9.5)
    pdf.cell(0, 5, f'Scale:  {spelling}   ({degrees})', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, f'Tuning: {capos}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, drone_note, new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, note, new_x='LMARGIN', new_y='NEXT')

    grid_top = pdf.get_y() + 3
    avail_h_mm = 297 - grid_top - 8

    # ---- auto-fit the monospace grid to the remaining space ----
    cols = max(len(ln) for ln in grid)
    rows = len(grid)
    mm_per_pt = 0.3528
    w_limit = usable_w_mm / (cols * 0.602 * mm_per_pt)
    h_limit = avail_h_mm / (rows * 1.18 * mm_per_pt)
    fs_pt = min(w_limit, h_limit, 10.5)
    line_h = fs_pt * 1.18 * mm_per_pt

    pdf.set_xy(left, grid_top)
    pdf.set_font('Mono', '', fs_pt)
    for ln in grid:
        pdf.set_x(left)
        pdf.cell(0, line_h, ln, new_x='LMARGIN', new_y='NEXT')


def build_instrument_pdf(instrument, out_dir):
    spec = INSTRUMENTS[instrument]
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.add_font('Mono', '', MONO)
    pdf.add_font('Mono', 'B', MONO_B)
    pdf.add_font('Sans', '', SANS)
    pdf.add_font('Sans', 'B', SANS_B)
    with use_tuning(spec['tuning']):
        for scale_key, (title, note) in SCALES.items():
            add_page(pdf, instrument, scale_key, title, note, spec['drone_note'], spec['cfg'])
    out_path = os.path.join(out_dir, f'french_sixth_{instrument}.pdf')
    pdf.output(out_path)
    return out_path


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'pdf')
    os.makedirs(out_dir, exist_ok=True)
    paths = [build_instrument_pdf(name, out_dir) for name in INSTRUMENTS]
    zip_path = os.path.join(out_dir, 'french_sixth_tabs.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p, os.path.basename(p))
    for p in paths:
        print('wrote', p)
    print('wrote', zip_path)


if __name__ == '__main__':
    main()
