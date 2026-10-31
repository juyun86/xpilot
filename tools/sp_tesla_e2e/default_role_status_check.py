"""Default role providers are standby when replaced; genuine conflicts and faults remain visible."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / 'openpilot/tesla/ui/offroad.py'
fn = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name == 'plugin_status')
env = {'mf': SimpleNamespace(INSTALL_DIR=Path('/nonexistent-plugin-store')),
       'store': SimpleNamespace(plugin_state=lambda *args: 'installed'), 'tr': lambda text: text}
exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), env)
status = env['plugin_status']
default = SimpleNamespace(NAME='default', ENABLE_PARAM=None, CLAIMS=['role:perception.model'])
manual = SimpleNamespace(NAME='manual', ENABLE_PARAM='ExtManual', CLAIMS=['role:perception.model'])
mixed = SimpleNamespace(NAME='mixed', ENABLE_PARAM=None, CLAIMS=['role:perception.model', 'can.tx:0x1:0'])
assert status(default, {}, {'default':'replacement'}) == 'inactive'
assert status(default, {'default':'failure'}, {'default':'replacement'}) == 'fault'
assert status(manual, {}, {'manual':'other'}) == 'conflict'
assert status(mixed, {}, {'mixed':'other'}) == 'conflict'
assert status(default, {}, {}) == ''
print('PASS default inactive, actual conflict, fault priority, active default')
