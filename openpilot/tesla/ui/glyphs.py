"""Bounded extra glyphs for enabled plugin-provided display labels."""


def extra_glyphs():
  from openpilot.common.params import Params
  from openpilot.tesla.plugins import active, record_fault
  chars = set()
  for plugin in active(Params()):
    if 'ui.glyphs' not in plugin.CLAIMS:
      continue
    try:
      text = plugin.ui_glyphs()
      if not isinstance(text, str) or len(text) > 16384:
        raise ValueError('invalid glyph data')
      addition = {c for c in text if c.isprintable() and ord(c) < 65536}
      if len(chars | addition) > 4096:
        raise ValueError('glyph budget exceeded')
      chars.update(addition)
    except Exception:
      record_fault(plugin.NAME, 'ui_glyphs', ValueError('glyph provider failed'))
  return chars
