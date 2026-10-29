"""Sensor motion failures, specified before implementation.

S1 malformed fixed profile or address grants arbitrary TX.
S2 absent/stale/wrong-bus/wrong-DLC/wrong-ID-type radar RX grants TX.
S3 direction/reserved bits/speed/yaw limits are not enforced.
S4 rate, expiry, timer wrap or rejected frames corrupt budgets.
S5 noOutput, relay malfunction, disabled vehicle bus or CLEAR retains permission.
Disengaged sensor input is intentional; it cannot authorize vehicle controls.
"""
import struct
import unittest

from opendbc.safety.tests.xpilot_rules_helpers import configure, control, harness, packet, table, upload


def motion_rule(address):
  rule = bytearray(84)
  struct.pack_into('<HBBII4BII2BHII', rule, 0, 84, 2, 0, address, 0x60A,
                   1, 1, 2, 4, 200_000, 40_000, 2, 0, 25, 0, 1_000_000)
  return bytes(rule)


class TestSensorMotion(unittest.TestCase):
  def setUp(self):
    self.s = harness()
    self.s.set_timer(0)
    configure(self.s, (motion_rule(0x300), motion_rule(0x301)))
    self.s.set_controls_allowed(False)

  def rx(self, at=0, bus=1, data=bytes(4)):
    self.s.set_timer(at)
    self.s.safety_rx_hook(packet(0x60A, data, bus))

  def tx(self, address, value, at=0, bus=1):
    self.s.set_timer(at)
    return bool(self.s.safety_tx_hook(packet(address, value.to_bytes(2, 'big'), bus)))

  def test_fixed_profile_rejects_every_mutated_byte(self):
    for i in range(84):
      self.s.set_safety_hooks(19, 0)
      mutated = bytearray(motion_rule(0x300))
      mutated[i] ^= 2 if i == 4 else 1
      with self.subTest(offset=i):
        self.assertNotEqual(upload(self.s, table((mutated,)))[3], 0)

  def test_no_input_wrong_bus_length_and_expiry(self):
    self.assertFalse(self.tx(0x300, 0))
    self.rx(bus=0)
    self.assertFalse(self.tx(0x300, 0))
    self.rx(data=bytes(8))
    self.assertFalse(self.tx(0x300, 0))
    self.rx()
    self.assertFalse(self.tx(0x300, 0, bus=0))
    self.assertTrue(self.tx(0x300, 0))
    self.assertFalse(self.tx(0x300, 0, at=39_999))
    self.assertTrue(self.tx(0x300, 0, at=40_000))
    self.assertTrue(self.tx(0x300, 0, at=200_000))
    self.assertFalse(self.tx(0x301, 32768, at=200_001))

  def test_payloads_exhaustive(self):
    # Independent DBC oracle over all payloads, refresh RX and interval each time.
    for address in (0x300, 0x301):
      for value in range(65536):
        now = value * 50_000
        self.rx(at=now)
        speed, direction = value & 0x1FFF, value >> 14
        expected = ((not value & 0x2000) and direction <= 2 and speed <= 4250 and
                    ((direction == 0) == (speed == 0))) if address == 0x300 else 22768 <= value <= 42768
        self.assertEqual(self.tx(address, value, at=now), expected, (address, value))

  def test_clear_relay_mode_and_bus_gates(self):
    self.rx()
    self.s.set_relay_malfunction(True)
    self.assertFalse(self.tx(0x300, 0))
    self.s.set_relay_malfunction(False)
    self.assertTrue(self.tx(0x300, 0))
    control(self.s, 0xA4)
    self.assertFalse(self.tx(0x301, 32768))
    configure(self.s, (motion_rule(0x300),), vehicle=False)
    self.rx()
    self.assertFalse(self.tx(0x300, 0))
    configure(self.s, (motion_rule(0x300),))
    self.s.set_safety_hooks(19, 0)
    self.rx()
    self.assertFalse(self.tx(0x300, 0))

  def test_id_type_length_budget_and_wrap(self):
    source = packet(0x60A, bytes(4))
    source.extended = True
    self.s.safety_rx_hook(source)
    self.assertFalse(self.tx(0x300, 0))
    self.rx()
    send = packet(0x300, bytes(2))
    send.extended = True
    self.assertFalse(self.s.safety_tx_hook(send))
    self.assertFalse(self.s.safety_tx_hook(packet(0x300, bytes(3))))
    for i in range(25):
      self.rx(i * 40_000)
      self.assertTrue(self.tx(0x300, 0, i * 40_000))
    self.assertFalse(self.tx(0x300, 0, 999_999))
    self.rx(1_000_000)
    self.assertTrue(self.tx(0x300, 0, 1_000_000))
    configure(self.s, (motion_rule(0x300),))
    start = 0xFFFF0000
    self.rx(start)
    self.assertTrue(self.tx(0x300, 0, start))
    self.assertTrue(self.tx(0x300, 0, (start + 200_000) & 0xFFFFFFFF))
    self.s.set_timer((start + 1_000_000) & 0xFFFFFFFF)
    self.s.safety_tick()
    self.assertFalse(self.tx(0x300, 0, start + 100))



if __name__ == '__main__':
  unittest.main()
