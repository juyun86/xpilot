"""Failure cases before changes: legacy enable lost, explicit disable ignored,
malformed catalog applied, inactive owner invoked, and English dynamic labels.
Uses synthetic params and a plugin class loaded from the actual reviewed source.
"""
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from openpilot.tesla import plugin_params, plugins
from openpilot.tesla.ui.localization import configure

with tempfile.TemporaryDirectory() as directory:
  directory = Path(directory)
  with patch.object(plugin_params.mf, 'INSTALL_DIR', directory):
    old = directory / '.params/OldLocale'
    old.parent.mkdir()
    old.write_text('1')
    view = plugin_params.ParamsView(None, {'ExtLocale': {'type': 'BOOL', 'default': '0', 'aliases': ['OldLocale']}})
    assert view.get_bool('ExtLocale'), 'legacy enable value lost'
    view.put_bool('ExtLocale', False)
    assert not view.get_bool('ExtLocale'), 'legacy value overrode explicit disable'
    assert old.read_text() == '1', 'rollback value destroyed'

package = ROOT.parent / 'xpilot-plugins/plugins/chinese_ui'
spec = importlib.util.spec_from_file_location('contract_locale', package / 'plugin.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
locale = module.ChineseUI
locale.NAME, locale.CLAIMS = 'contract_locale', ('role:ui.language',)
faults = []
def language():
  return SimpleNamespace(_language='en', _translations={})
with patch.object(plugins, 'resolve', return_value=({'contract_locale'}, {})), \
     patch.object(plugins, 'record_fault', side_effect=lambda *args: faults.append(args)):
  output = language()
  configure(output, None, [locale])
  assert output._language == 'zh-CHS' and output._translations['Not set']
  with patch.object(locale, 'ui_language', return_value={'code': 'zh-CHS', 'font': package / 'NotoSansCJKsc-Regular.otf',
                                                      'translations': {'Count {n}': '错误 {other}'}}):
    output = language()
    configure(output, None, [locale])
    assert output._language == 'en' and not output._translations and faults
with patch.object(plugins, 'resolve', return_value=(set(), {})), patch.object(locale, 'ui_language') as method:
  configure(language(), None, [locale])
  method.assert_not_called()
print('language alias, disable, malformed fallback and inactive owner verified')
