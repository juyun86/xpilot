#!/usr/bin/env python3
"""Failures: arbitrary addresses/buses/options, mismatched binary shape, unknown
rule types advertised as supported. No hardware or CAN transmission.
"""
import importlib.util
from pathlib import Path
import struct


def main():
  root = Path(__file__).resolve().parents[2]
  spec = importlib.util.spec_from_file_location('rules', root / 'openpilot/tesla/panda_rules.py')
  rules = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(rules)
  for address in (0x300, 0x301):
    declaration = {'type': 'sensor_motion.v1', 'tx_address': address, 'tx_bus': 1}
    actual = rules.encode_rule(declaration)
    assert len(actual) == 84 and actual[2:4] == bytes([2, 0])
    assert struct.unpack_from('<II4BII2BHII', actual, 4) == (
      address, 0x60A, 1, 1, 2, 4, 200_000, 40_000, 2, 0, 25, 0, 1_000_000)
    assert actual[36:] == bytes(48)
    for change in ({'tx_address': 0x302}, {'tx_address': 0x2B9}, {'tx_bus': 0},
                   {'tx_bus': True}, {'min_interval_us': 1}, {'type': 'sensor_motion.v2'}):
      try:
        rules.encode_rule(declaration | change)
        raise AssertionError(f'unsafe declaration accepted: {change}')
      except ValueError:
        pass
  print('sensor motion encoder contract: passed')


if __name__ == '__main__':
  main()
