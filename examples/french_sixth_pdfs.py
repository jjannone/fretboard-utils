"""Generate one-page PDFs of full practice sets for the no-X French-sixth tuning.

Tuning: capo 1 on A,G (->A#,G#); capo 3 on B (->D).  Open E, D, e.
Drones spell the French sixth {E, G#, A#, D} = E7b5 / A#7b5, which sits inside
five different scales.  Each scale gets a full set (3 two-note variants, 3 three
-note positions, 2 arpeggios) laid out on a single landscape page.

Run:  python3 examples/french_sixth_pdfs.py [output_dir]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fpdf import FPDF

from fretboard import (
    generate_full_set, render_full_set, capo_summary,
    scale_spelling, scale_degree_labels,
)

FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'

TUNING = {'A': 1, 'G': 1, 'B': 3}
ROOT = 'E'

# scale_key -> (display title, one-line character note)
SCALES = {
    'whole_tone':      ('Whole Tone',
                        'Symmetric, no leading tone; drones are 4 of the 6 whole-tone pitches.'),
    'half_whole_dim':  ('Half-Whole Diminished',
                        'Octatonic dominant (H-W); drones outline the E7b5 backbone.'),
    'lydian_dominant': ('Lydian Dominant',
                        'Acoustic scale - bright dominant with #4; drones = 1 3 #4 b7.'),
    'altered':         ('Altered',
                        'Super-Locrian (7th mode of F melodic minor); every tension altered.'),
    'enigmatic':       ("Enigmatic",
                        "Verdi's scale - b2 over a whole-tone top; exotic and unresolved."),
}


def build_pdf(scale_key, title, note, out_dir):
    fs = generate_full_set(ROOT, scale_key, string_configs=TUNING)
    grid = render_full_set(fs)

    spelling = ' '.join(scale_spelling(ROOT, scale_key))
    degrees = ' '.join(scale_degree_labels(scale_key))
    capos = capo_summary(TUNING)

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.add_font('DejaVuMono', '', FONT_PATH)
    pdf.add_font('DejaVuMono', 'B', FONT_BOLD)
    pdf.add_page()
    pdf.set_margins(12, 10, 12)

    pdf.set_xy(12, 10)
    pdf.set_font('DejaVuMono', 'B', 19)
    pdf.cell(0, 9, f'French-Sixth Tuning  -  {ROOT} {title}', new_x='LMARGIN', new_y='NEXT')

    pdf.set_font('DejaVuMono', '', 11)
    pdf.cell(0, 5.6, f'Scale:  {spelling}   ({degrees})', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5.6, f'Tuning: {capos}   -   no muted strings', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5.6, 'Drones spell the French sixth {E, G#, A#, D} = E7b5 / A#7b5', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5.6, note, new_x='LMARGIN', new_y='NEXT')

    pdf.ln(3)
    grid_size = 11.0
    line_h = 4.9
    pdf.set_font('DejaVuMono', '', grid_size)
    for line in grid.splitlines():
        pdf.cell(0, line_h, line, new_x='LMARGIN', new_y='NEXT')

    pdf.ln(2)
    pdf.set_font('DejaVuMono', '', 8.5)
    pdf.cell(0, 4, 'Rows: top = two-note-per-string (tight / wide / alternating); '
                   'middle = three-note-per-string (ascending positions); '
                   'bottom = arpeggios (low / high).', new_x='LMARGIN', new_y='NEXT')

    out_path = os.path.join(out_dir, f'french_sixth_{scale_key}.pdf')
    pdf.output(out_path)
    return out_path


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'pdf')
    os.makedirs(out_dir, exist_ok=True)
    for key, (title, note) in SCALES.items():
        path = build_pdf(key, title, note, out_dir)
        print('wrote', path)


if __name__ == '__main__':
    main()
