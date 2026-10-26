"""Language plugin contract: disabled/fault fallback, placeholders and glyphs.

Failure modes: applying a disabled language, executing a non-owner, malformed
catalog crashing startup, wrong format fields, missing Chinese glyphs, and
measuring English before drawing Chinese. Run before and after implementation.
"""
import inspect
from openpilot.tesla.plugin import Plugin
from openpilot.tesla import manifest

assert hasattr(Plugin, 'ui_language'), 'missing language-pack extension hook'
assert 'ui_language' in manifest.HOST_CAPS['hooks']
from openpilot.tesla.ui.localization import configure
assert 'plugins' in inspect.signature(configure).parameters
print('language extension contract available')
