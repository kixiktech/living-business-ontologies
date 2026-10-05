import re
from lbo import palette


def test_every_color_is_six_digit_lowercase_hex():
    for hexes in (palette.ROLE.values(), palette.TINT.values(), palette.LAYER.values(),
                  [palette.INK, palette.GREY, palette.FAINT, palette.PAPER]):
        for h in hexes:
            assert re.fullmatch(r'#[0-9a-f]{6}', h), h


def test_all_contains_every_named_color():
    named = set(palette.ROLE.values()) | set(palette.TINT.values()) | set(palette.LAYER.values())
    named |= {palette.INK, palette.GREY, palette.FAINT, palette.PAPER}
    assert named == set(palette.ALL)


def test_roles_and_tints_share_keys():
    assert set(palette.ROLE) == set(palette.TINT) == {
        'agent', 'owner', 'tool', 'monitor', 'reflect', 'pass', 'fail'}


def test_layers_are_the_four_ontology_layers():
    assert list(palette.LAYER) == ['core', 'extension', 'meaning', 'control']


def test_pygments_style_uses_only_palette_colors():
    style = palette.pygments_style()
    for token, spec in style.styles.items():
        for h in re.findall(r'#[0-9a-fA-F]{6}', spec):
            assert h.lower() in palette.ALL, (token, h)


def test_pygments_css_is_scoped_to_listings():
    css = palette.pygments_css()
    assert '.listing .k ' in css or '.listing .k{' in css.replace(' ', '')


def test_pygments_css_uses_only_palette_colors():
    css = palette.pygments_css()

    def _expand(m: re.Match) -> str:
        h = m.group(0)
        if len(h) == 4:
            h = '#' + ''.join(c * 2 for c in h[1:])
        return h.lower()

    expanded = re.sub(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?', _expand, css)
    for h in re.findall(r'#[0-9a-fA-F]{6}', expanded):
        assert h in palette.ALL, h
