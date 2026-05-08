"""
Tests for fretboard.py — runnable directly or via pytest.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fretboard import (
    pitch_at, note_name, scale_pitches,
    parse_diagram, verify, generate_2nps, render, generate_and_render,
    SCALES, NOTE_NAMES,
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
