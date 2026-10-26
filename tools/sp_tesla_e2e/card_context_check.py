#!/usr/bin/env python3
"""Failures: undeclared reads, mutable metadata, blocking polls, no-op hooks
opening sockets, stale input hidden by caching, and dead plugins retaining access.
Synthetic SubMaster only; no vehicle sockets or Params.
"""
import importlib.util
from pathlib import Path


def main():
  path = Path(__file__).resolve().parents[2] / 'openpilot/tesla/card_context.py'
  spec = importlib.util.spec_from_file_location('card_context', path)
  api = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(api)

  class SM(dict):
    def __init__(self, names):
      super().__init__((name, object()) for name in names)
      for key in api.METADATA:
        setattr(self, key, dict.fromkeys(names, 1))
      self.calls = []

    def update(self, timeout):
      self.calls.append(timeout)

  created = []
  def factory(names):
    sm = SM(names)
    created.append(sm)
    return sm

  bus = api.CardSubscriptions(factory)
  assert bus.poll({}) == {} and not created
  first = bus.poll({'radar': ('deviceMotion', 'extrinsicsCalibration'), 'other': ('deviceMotion',)})
  assert len(created) == 1 and created[0].calls == [0]
  assert set(first['other'].seen) == {'deviceMotion'}
  try:
    first['other']['extrinsicsCalibration']
    raise AssertionError('undeclared read')
  except KeyError:
    pass
  try:
    first['radar'].valid['deviceMotion'] = False
    raise AssertionError('mutable metadata')
  except TypeError:
    pass
  created[0].valid['deviceMotion'] = False
  created[0].logMonoTime['deviceMotion'] = 17
  second = bus.poll({'radar': ('deviceMotion', 'extrinsicsCalibration')})
  assert first['radar'].valid['deviceMotion'] == 1
  assert second['radar'].valid['deviceMotion'] is False
  assert second['radar'].logMonoTime['deviceMotion'] == 17
  assert 'other' not in second and created[0].calls == [0, 0]
  assert bus.poll({}) == {} and created[0].calls == [0, 0]
  try:
    bus.poll({'new': ('undeclared_after_start',)})
    raise AssertionError('subscription changed after startup')
  except ValueError:
    pass
  print('card context contract: passed')


if __name__ == '__main__':
  main()
