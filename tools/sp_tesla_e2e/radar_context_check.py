#!/usr/bin/env python3
"""Failure cases: no source context, undeclared reads, callback failure escapes
the guard, or a faulted source is revived instead of using the original receiver.
Exercises the actual guard implementation with synthetic inputs and no sockets.
"""
import ast
from pathlib import Path
import sys


def main():
  root = Path(__file__).resolve().parents[2]
  sys.path.insert(0, str(root))
  from openpilot.tesla.card_context import CardSubscriptions, METADATA
  from types import SimpleNamespace
  faults = []
  ns = {'time': SimpleNamespace(monotonic_ns=lambda: 10),
        'record_fault': lambda *args: faults.append(args)}
  path = root / 'openpilot/tesla/plugins/__init__.py'
  tree = ast.parse(path.read_text())
  definitions = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
                 and n.name in ('_GuardedRadar', '_call')]
  exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), 'exec'), ns)
  class Source:
    plugin_name = 'fixture'
    calls = 0
    fail = False

    def radar_context(self, context, now):
      assert set(context.valid) == {'deviceMotion'} and now == 10
      if self.fail:
        raise ValueError('context failure')
      self.calls += 1

    def update(self, frames):
      return 'plugin'
  class SM(dict):
    def __init__(self, names):
      super().__init__((name, object()) for name in names)
      for name in METADATA:
        setattr(self, name, dict.fromkeys(names, True))

    def update(self, timeout):
      assert timeout == 0
  source = Source()
  guard = ns['_GuardedRadar'](source, SimpleNamespace(update=lambda frames: 'original'), ('deviceMotion',))
  guard._context = CardSubscriptions(SM)
  assert guard.update([]) == 'plugin' and source.calls == 1
  source.fail = True
  assert guard.update([]) == 'original' and len(faults) == 1
  source.fail = False
  assert guard.update([]) == 'original' and source.calls == 1
  print('radar context guard: passed')


if __name__ == '__main__':
  main()
