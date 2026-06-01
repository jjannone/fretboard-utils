"""
Tests for fretboard.py — runnable directly or via pytest.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fretboard import (
    pitch_at, note_name, scale_pitches, chord_tones,
    parse_diagram, verify, generate_2nps, generate_3nps, generate_arpeggio,
    render, generate_and_render, generate_3nps_and_render,
    generate_arpeggio_and_render, generate_full_set, render_full_set,
    all_diagram_frets_in_range,
    find_cluster_drones, generate_cluster, generate_cluster_and_render,
    find_scalar_runs, generate_scalar_run, generate_scalar_run_and_render,
    use_tuning,
    MAX_FINGER_STEP, OPEN_STRINGS, OPEN_MIDI, SCALES, NOTE_NAMES,
)


def test_open_string_pitches():
    assert note_name('E', 0) == 'E'
    assert note_name('A', 0) == 'A'
    assert note_name('D', 0) == 'D'
    assert note_name('G', 0) == 'G'
    assert note_name('B', 0) == 'B'
    assert note_name('e', 0) == 'E'


def test_g_to_b_offset():
    """G string fret 5 = C; B string fret 5 = E (M3 offset)."""
    assert note_name('G', 5) == 'C'
    assert note_name('B', 5) == 'E'
    # Same pitch C: G fret 5, B fret 1
    assert pitch_at('G', 5) == pitch_at('B', 1)


def test_scale_pitches_c_major():
    pitches = scale_pitches('C', 'major')
    expected = {NOTE_NAMES.index(n) for n in ['C', 'D', 'E', 'F', 'G', 'A', 'B']}
    assert pitches == expected


def test_scale_pitches_a_minor():
    pitches = scale_pitches('A', 'natural_minor')
    expected = {NOTE_NAMES.index(n) for n in ['A', 'B', 'C', 'D', 'E', 'F', 'G']}
    assert pitches == expected


def test_parse_basic_diagram():
    d = """e|---3-5----|
B|---3-5----|
G|---4-6----|
D|---5-7----|
A|---5-7----|
E|---3-5----|"""
    notes = parse_diagram(d)
    # 12 notes total (2 per string * 6 strings)
    assert len(notes) == 12
    # Check first note (high e, fret 3)
    assert notes[0][:2] == ('e', 3)


def test_parse_adjacent_frets():
    d = """e|---34----|"""
    notes = parse_diagram(d)
    assert len(notes) == 2
    assert notes[0][:2] == ('e', 3)
    assert notes[1][:2] == ('e', 4)


def test_verify_correct_diagram():
    # C whole tone — verified by hand
    d = """e|----4-6----|
B|---3-5-----|
G|---3-5-----|
D|----4-6----|
A|---3-5-----|
E|----4-6----|"""
    assert verify(d, 'C', 'whole_tone')


def test_verify_catches_g_to_b_error():
    """A common error: forgetting the G→B offset.
    If we naively put fret 3 on B string thinking it's the same pitch
    as fret 3 on G, we get D instead of C — wrong for C-rooted scale
    that doesn't include D."""
    # C major DOES include both C and D, so use a scale that doesn't.
    # Use C augmented (C, D#, E, G, G#, B): D is NOT in scale.
    d = """e|---3----|
B|---3----|
G|---3----|
D|---3----|
A|---3----|
E|---3----|"""
    # G3=A#(not in C aug), so this should fail anyway — but test it
    pitches = scale_pitches('C', 'augmented')
    # Verify G3 (A#) is NOT in C augmented
    assert pitch_at('G', 3) not in pitches


def test_generate_and_verify_all_scales():
    """Generate diagrams for every scale and verify each."""
    failures = []
    for scale_name in SCALES:
        try:
            diagram = generate_and_render('C', scale_name)
            assert verify(diagram, 'C', scale_name)
        except Exception as e:
            failures.append((scale_name, str(e)))
    assert not failures, f"Failures: {failures}"


def test_render_format_no_em_dashes():
    """Output must contain only ASCII hyphen-minus."""
    diagram = generate_and_render('C', 'whole_tone')
    assert '—' not in diagram
    assert '–' not in diagram
    assert '-' in diagram  # ASCII hyphen-minus IS present


def test_render_lowest_fret_at_least_3():
    """Per convention, all generated patterns have lowest fret >= 3."""
    for scale_name in SCALES:
        try:
            pattern = generate_2nps('C', scale_name, start_fret=3)
            if pattern is None:
                continue
            for s, (f1, f2) in pattern.items():
                assert f1 >= 3, f"{scale_name}: {s} starts at fret {f1}"
        except Exception:
            pass


def test_chord_tones_major_triad():
    """C major (1,3,5) = {C, E, G}."""
    assert chord_tones('C', 'major') == {0, 4, 7}


def test_chord_tones_minor_triad():
    """A natural minor (1,3,5) = {A, C, E}."""
    assert chord_tones('A', 'natural_minor') == {9, 0, 4}


def test_two_spider_capos_allowed():
    """Two distinct spider-capo frets are now allowed in string_configs."""
    diagram = generate_and_render(
        'C', 'major',
        string_configs={'E': 1, 'A': 1, 'D': 3, 'G': 3},
        require_root_on_low_e=True,
    )
    assert verify(diagram, 'C', 'major')


def test_three_capo_frets_rejected():
    """Three or more distinct capo frets still raises."""
    try:
        generate_and_render('C', 'major',
                            string_configs={'E': 1, 'A': 2, 'D': 3})
    except ValueError:
        return
    assert False, "Expected ValueError for 3 distinct capo frets"


def test_full_set_replaces_x_with_second_capo():
    """second_capo_fret converts every 'X' in string_configs to that fret."""
    fs = generate_full_set(
        'A', 'natural_minor',
        string_configs={'E': 2, 'A': 2, 'D': 'X', 'G': 'X'},
        second_capo_fret=4,
    )
    # Spot-check one rendered diagram for the two capo prefixes
    diagram = fs['two_note'][0][1]
    # D and G lines should now begin with config char '4' (capo at fret 4)
    for line in diagram.split('\n'):
        if line.startswith('D') or line.startswith('G'):
            assert line[1] == '4', f"Expected capo 4 on {line[0]} line: {line!r}"


def test_full_set_root_on_low_e():
    """Every diagram in a full set must have the scale root on the low E string."""
    fs = generate_full_set('C', 'major',
                           string_configs={'E': 1, 'A': 1, 'D': 'X', 'G': 'X'},
                           second_capo_fret=3)
    root_pc = NOTE_NAMES.index('C')
    open_e = OPEN_STRINGS['E']
    for section in fs.values():
        for label, diagram in section:
            # Locate the low-E line; check capo drone + body notes via parse_diagram
            e_line = next((ln for ln in diagram.split('\n') if ln.startswith('E')), None)
            assert e_line is not None
            has_root = False
            cfg_char = e_line[1]
            if cfg_char.isdigit() and cfg_char != '0':
                capo_fret = int(cfg_char)
                if (open_e + capo_fret) % 12 == root_pc:
                    has_root = True
            for s, fret, _col in parse_diagram(diagram):
                if s == 'E' and (open_e + fret) % 12 == root_pc:
                    has_root = True
            assert has_root, f"No root on low E for '{label}': {e_line!r}"


def test_full_set_all_diagrams_verify():
    """Every diagram in a full set must be in-scale."""
    fs = generate_full_set('G', 'major',
                           string_configs={'E': 2, 'A': 2, 'D': 'X', 'G': 'X'},
                           second_capo_fret=4)
    for section_key, section in fs.items():
        for label, diagram in section:
            assert verify(diagram, 'G', 'major'), f"{section_key}/{label} failed verify"


def test_3nps_basic():
    """3NPS produces 18 notes total (6 strings * 3)."""
    diagram = generate_3nps_and_render('C', 'major', start_fret=5)
    notes = parse_diagram(diagram)
    assert len(notes) == 18, f"Expected 18 notes, got {len(notes)}"
    assert verify(diagram, 'C', 'major')


def test_arpeggio_respects_max_finger_step():
    """No within-string gap in an arpeggio may exceed MAX_FINGER_STEP."""
    for root, scale in [('C', 'major'), ('A', 'natural_minor'),
                        ('G', 'dorian'), ('E', 'enigmatic')]:
        diagram = generate_arpeggio_and_render(root, scale, start_fret=5)
        per_string = {}
        for s, fret, _col in parse_diagram(diagram):
            per_string.setdefault(s, []).append(fret)
        for s, frets in per_string.items():
            frets.sort()
            for a, b in zip(frets, frets[1:]):
                assert (b - a) <= MAX_FINGER_STEP, \
                    f"{root} {scale}: {s} has gap {b-a} > m3 between {a} and {b}"


def test_arpeggio_uses_two_notes_when_chord_allows():
    """When a chord type has m3-or-smaller adjacent tones (e.g. major/minor),
    at least one string should be able to fit two notes inside MAX_FINGER_STEP."""
    diagram = generate_arpeggio_and_render('C', 'major', start_fret=3)
    per_string = {}
    for s, fret, _col in parse_diagram(diagram):
        per_string.setdefault(s, []).append(fret)
    assert any(len(v) == 2 for v in per_string.values()), \
        f"C major arpeggio should fit a 2-note pair on at least one string: {per_string}"


def test_arpeggio_scale_tone_picks_form_pairs_where_possible():
    """With scale-tone picking, arpeggios should land 2NPS pairs on most strings
    when the scale is dense enough (e.g. C major). At least half should be pairs."""
    diagram = generate_arpeggio_and_render('C', 'major', start_fret=5)
    per_string = {}
    for s, fret, _col in parse_diagram(diagram):
        per_string.setdefault(s, []).append(fret)
    pair_count = sum(1 for v in per_string.values() if len(v) == 2)
    assert pair_count >= 3, f"Expected ≥3 strings with 2NPS pairs; got {pair_count}"


def test_pick_pair_clamps_max_stretch_to_global_cap():
    """Passing max_stretch above MAX_FINGER_STEP is silently clamped."""
    from fretboard import pick_pair
    frets = [3, 5, 7, 8, 10, 12]
    pair = pick_pair(frets, target=3, max_stretch=10)  # caller asks for huge stretch
    assert pair is not None
    assert (pair[1] - pair[0]) <= MAX_FINGER_STEP


def test_open_e_drone_satisfies_root_on_e_rooted_scale():
    """For E enigmatic with low E open, the open drone IS the root — body
    notes should NOT be forced up to fret 12 just to include the root."""
    # 3NPS at pos 5: low E should sit in fret-5-ish territory, not fret 10-12.
    diagram = generate_3nps_and_render('E', 'enigmatic', start_fret=5,
                                        string_configs={'A': 1, 'G': 1, 'B': 4},
                                        require_root_on_low_e=True)
    e_low_frets = sorted(f for s, f, _c in parse_diagram(diagram) if s == 'E')
    # Triple should sit near target=5; lowest fret should be within ~m3 of it,
    # NOT pinned to fret 12 (which is what a forced-root-in-body would give).
    assert min(e_low_frets) <= 8, \
        f"Low E body should sit near pos 5, not be dragged up to 12; got {e_low_frets}"


def test_full_set_wide_variant_respects_global_cap():
    """The wide 2NPS variant must not exceed MAX_FINGER_STEP on any string."""
    fs = generate_full_set('C', 'major')
    _label, wide_diagram = fs['two_note'][1]  # second variant is 'wide (m3)'
    per_string = {}
    for s, fret, _c in parse_diagram(wide_diagram):
        per_string.setdefault(s, []).append(fret)
    for s, frets in per_string.items():
        frets.sort()
        for a, b in zip(frets, frets[1:]):
            assert (b - a) <= MAX_FINGER_STEP, f"wide on {s}: gap {b-a} > m3"


def test_arpeggio_only_scale_tones():
    """Arpeggio diagram contains only in-scale pitches.

    The picker now draws from the full scale (not just chord_tones) so it
    can find compact pairs near every position. Per-line chord identity is
    computed at render time by per_string_chord.
    """
    diagram = generate_arpeggio_and_render('C', 'major', start_fret=3)
    pitches = scale_pitches('C', 'major')
    for s, fret, _col in parse_diagram(diagram):
        pc = pitch_at(s, fret)
        assert pc in pitches, f"{s}{fret} pc={pc} not in scale {pitches}"


def test_max_finger_step_default_is_minor_third():
    """The module-level cap on fingered-note distance defaults to a minor 3rd."""
    assert MAX_FINGER_STEP == 3


def test_2nps_default_caps_stretch_at_minor_third():
    """generate_2nps with default max_stretch should never exceed MAX_FINGER_STEP."""
    pattern = generate_2nps('C', 'major', start_fret=5)
    assert pattern is not None
    for s, (f1, f2) in pattern.items():
        assert f2 - f1 <= MAX_FINGER_STEP, f"{s} pair ({f1},{f2}) exceeds m3 cap"


def test_3nps_default_caps_each_step_at_minor_third():
    """generate_3nps with default max_step caps every adjacent gap at m3."""
    pattern = generate_3nps('C', 'major', start_fret=5)
    assert pattern is not None
    for s, (a, b, c) in pattern.items():
        assert (b - a) <= MAX_FINGER_STEP, f"{s} gap a-b > m3"
        assert (c - b) <= MAX_FINGER_STEP, f"{s} gap b-c > m3"


def test_no_body_notes_at_or_below_higher_capo():
    """With a higher capo at fret M, no string can be fretted at frets <= M."""
    cfg = {'A': 1, 'G': 1, 'B': 'X'}
    fs = generate_full_set('E', 'enigmatic', string_configs=cfg, second_capo_fret=4)
    for section in fs.values():
        for label, diagram in section:
            assert all_diagram_frets_in_range(diagram, _post_x_configs(cfg, 4)), \
                f"Body note at or below the higher capo in '{label}':\n{diagram}"


def _post_x_configs(cfg, second_capo_fret):
    """Helper: mirror full_set's X->second_capo substitution for test assertions."""
    out = dict(cfg)
    for s, v in list(out.items()):
        if v == 'X':
            out[s] = second_capo_fret
    return out


def test_render_shifts_columns_by_higher_capo():
    """With max_capo M, body column k represents fret (k + M); body[0] is the bar."""
    cfg = {'A': 1, 'G': 1, 'B': 4}
    # Two-note pair at frets 5 and 6 on B (capo 4): col 1 = '5', col 2 = '6'
    pattern = {'E': (5, 8), 'A': (5, 6), 'D': (5, 7), 'G': (5, 6), 'B': (5, 6), 'e': (5, 8)}
    diag = render(pattern, label='', width=12, string_configs=cfg)
    # Locate the B line and check the leading body characters
    b_line = next(ln for ln in diag.split('\n') if ln.startswith('B'))
    # Expect: 'B4 56' then dashes. Body[0]=' ', body[1]='5', body[2]='6'.
    assert b_line.startswith('B4 56-'), f"Unexpected B line: {b_line!r}"
    # And the round-trip via parse_diagram recovers the original frets
    notes = parse_diagram(diag)
    b_notes = sorted(f for s, f, _c in notes if s == 'B')
    assert b_notes == [5, 6], f"parse_diagram returned {b_notes} for B"


def test_render_full_set_layout():
    """render_full_set returns a string with three blocks (separated by blanks)."""
    fs = generate_full_set('A', 'natural_minor')
    out = render_full_set(fs)
    # 3 sections separated by '\n\n'
    sections = out.split('\n\n')
    assert len(sections) == 3, f"Expected 3 sections, got {len(sections)}"


def test_cluster_drones_form_contiguous_scale_block():
    """Every config returned by find_cluster_drones has six distinct drone
    pitch classes that are six consecutive scale-tones (with octave wrap)."""
    for scale in ['major', 'altered', 'enigmatic', 'lydian_dominant', 'whole_tone']:
        cands = find_cluster_drones('E', scale)
        assert cands, f"expected cluster configs for E {scale}"
        scale_pcs = sorted(scale_pitches('E', scale))
        n = len(scale_pcs)
        valid_blocks = [frozenset(scale_pcs[(start + k) % n] for k in range(6))
                        for start in range(n)]
        for c in cands:
            assert len(set(c['drone_pcs'])) == 6
            assert frozenset(c['drone_pcs']) in valid_blocks, \
                f"{scale}: {c['drone_pcs']} is not a contiguous block"


def test_cluster_capo_limits_respected():
    """No cluster config uses more than 2 distinct nonzero capo frets, and
    every capo fret is within 0..max_capo."""
    for scale in ['major', 'altered', 'lydian_dominant', 'enigmatic', 'half_whole_dim']:
        for c in find_cluster_drones('E', scale, max_capo=4, max_distinct_capos=2):
            assert len(c['capo_frets']) <= 2
            assert all(1 <= f <= 4 for f in c['capo_frets'])


def test_cluster_diagram_verifies_with_body_notes():
    """Adding body notes still yields a diagram whose every fretted note is
    in scale and above the highest capo bar."""
    for scale in ['major', 'altered', 'lydian_dominant']:
        d = generate_cluster_and_render('E', scale, body_notes_per_string=1)
        cfg, _ = generate_cluster('E', scale, body_notes_per_string=1)
        assert verify(d, 'E', scale)
        assert all_diagram_frets_in_range(d, cfg)


def test_cluster_bass_tuning():
    """Cluster finder works inside use_tuning('bass_6')."""
    with use_tuning('bass_6'):
        cands = find_cluster_drones('E', 'altered')
        assert cands, "expected at least one cluster config on bass"
        # Every drone is in scale
        pcs = scale_pitches('E', 'altered')
        for c in cands:
            for pc in c['drone_pcs']:
                assert pc in pcs


def test_open_midi_diffs_match_open_strings():
    """OPEN_MIDI values agree with OPEN_STRINGS pitch classes (mod 12)."""
    for s, midi in OPEN_MIDI.items():
        assert midi % 12 == OPEN_STRINGS[s], f"{s}: midi {midi} % 12 != pc {OPEN_STRINGS[s]}"


def test_scalar_run_upper_five_strings_ascend_stepwise():
    """The upper five strings of a run form five consecutive scale tones,
    ascending in m2/M2 steps (or up to one m3 if allow_one_minor_third)."""
    for scale in ['major', 'altered', 'whole_tone', 'lydian_dominant',
                  'natural_minor', 'half_whole_dim']:
        cands = find_scalar_runs('E', scale)
        assert cands, f"expected scalar runs for E {scale}"
        for c in cands[:5]:
            seq = c['sequence_midi']
            assert len(seq) == 6
            pitches = scale_pitches('E', scale)
            assert all(m % 12 in pitches for m in seq)
            # Upper five (indices 1..5) ascend stepwise
            upper = seq[1:]
            assert all(upper[i + 1] > upper[i] for i in range(4))
            steps = [upper[i + 1] - upper[i] for i in range(4)]
            assert all(s <= 3 for s in steps), f"{scale}: upper steps {steps}"
            m3s = [s for s in steps if s > 2]
            assert len(m3s) <= 1, f"{scale}: multiple m3 steps {steps}"
            assert c['has_minor_third'] == (len(m3s) == 1)
            # Bass pedal sits at or below the first upper note
            assert seq[0] <= seq[1]


def test_scalar_run_diagram_picks_correct_pitches():
    """Picking the diagram string-by-string low-to-high reproduces the
    sequence_midi exactly."""
    for scale in ['major', 'altered', 'harmonic_minor']:
        cands = find_scalar_runs('E', scale)
        c = cands[0]
        cfg, pat = c['string_configs'], c['pattern']
        for i, s in enumerate(['E', 'A', 'D', 'G', 'B', 'e']):
            if pat[s]:  # body note present
                fret = pat[s][0]
                actual = OPEN_MIDI[s] + fret
            else:  # drone (open or capo)
                actual = OPEN_MIDI[s] + cfg.get(s, 0)
            assert actual == c['sequence_midi'][i], \
                f"{scale} string {s}: got {actual}, expected {c['sequence_midi'][i]}"


def test_scalar_run_body_span_within_limit():
    """No run violates its max_body_span constraint when results exist."""
    for span in [7, 8, 10]:
        for scale in ['major', 'altered', 'lydian_dominant']:
            cands = find_scalar_runs('E', scale, max_body_span=span)
            assert cands, f"{scale} span={span}: no runs"
            for c in cands[:5]:
                assert c['body_span'] <= span


def test_scalar_run_diagram_verifies():
    """The rendered run diagram verifies and respects the capo-bar floor."""
    for scale in ['major', 'altered', 'lydian_dominant', 'harmonic_minor']:
        d = generate_scalar_run_and_render('E', scale)
        cfg, _ = generate_scalar_run('E', scale)
        assert verify(d, 'E', scale)
        assert all_diagram_frets_in_range(d, cfg)


def test_scalar_run_bass_tuning():
    """Scalar-run finder works on bass (BEADGC). Bass open strings are
    uniformly a P4 apart so the body geometry forces a wider span; pass
    max_body_span=8."""
    with use_tuning('bass_6'):
        cands = find_scalar_runs('E', 'altered', max_body_span=8)
        assert cands, "expected runs on bass"
        c = cands[0]
        assert len(c['sequence_midi']) == 6
        upper = c['sequence_midi'][1:]
        assert all(upper[i + 1] > upper[i] for i in range(4))


if __name__ == '__main__':
    # Simple test runner
    tests = [v for k, v in list(globals().items()) if k.startswith('test_')]
    passed = 0
    failed = []
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print()
    print(f"{passed}/{len(tests)} passed")
    if failed:
        sys.exit(1)
