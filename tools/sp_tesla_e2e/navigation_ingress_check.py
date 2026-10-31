#!/usr/bin/env python3
"""Failure cases: unclaimed/disabled owner, foreign/public/IPv6 peers,
oversize/flood input, arbitrary reply, close/rebind, capability absent.
Ownership must be rechecked without a grace period, including after blocking I/O.
Socket fixtures never use the live navigation port or user data.
"""
import importlib.util
import inspect
from pathlib import Path
import socket
import struct
import sys
from types import ModuleType
from unittest.mock import patch


class Transport:
  def __init__(self, interface_index):
    self.interface_index, self.closed, self.reads, self.sent = interface_index, False, 0, []
    self.on_read = lambda: None
    self.timeout = False

  def fileno(self):
    return -1 if self.closed else 123

  def close(self):
    self.closed = True

  def recvfrom(self, size):
    self.reads += 1
    self.on_read()
    if self.timeout:
      raise TimeoutError()
    return b'{}', ('192.168.2.3', 5555)

  def recvmsg(self, size, ancillary_size):
    body, address = self.recvfrom(size)
    info = struct.pack('=I4s4s', self.interface_index, bytes(4), bytes(4))
    return body, [(socket.IPPROTO_IP, 8, info)], 0, address

  def sendto(self, body, address):
    self.sent.append((body, address))


def revocation_checks(api):
  kwargs = {'interface_index': 7} if 'interface_index' in inspect.signature(api.NavigationIngress).parameters else {}
  acknowledgement = {'messageType': 'navassist_udp_ack', 'schemaVersion': 3, 'sessionId': 'fixture', 'sequence': 1}
  for operation in ('receive', 'ack', 'receive_completion', 'receive_timeout', 'fetch_completion'):
    if operation == 'fetch_completion' and not hasattr(api.NavigationIngress, 'fetch_https'):
      continue
    allowed, transport = [True], Transport(7)
    with patch.object(api.time, 'monotonic', return_value=100.):
      ingress = api.NavigationIngress('fixture', authorize=lambda allowed=allowed: allowed[0], transport=transport, **kwargs)
      store = ModuleType('openpilot.tesla.store')

      def revoke(*_args, allowed=allowed):
        allowed[0] = False
        return b'fixture'

      store._get = revoke
      if operation == 'ack':
        assert ingress.receive() == (b'{}', '192.168.2.3')
      if operation in ('receive', 'ack'):
        allowed[0] = False
      if operation.startswith('receive_'):
        transport.on_read = revoke
        transport.timeout = operation == 'receive_timeout'
      reads = transport.reads
      with patch.dict(sys.modules, {'openpilot.tesla.store': store}):
        try:
          if operation == 'fetch_completion':
            ingress.fetch_https('https://example.invalid/fixture')
          elif operation == 'ack':
            ingress.ack(acknowledgement)
          else:
            ingress.receive()
        except PermissionError:
          pass
        else:
          raise AssertionError(f'ownership revocation not enforced: {operation}')
      assert transport.closed and ingress.peer is None and not transport.sent, operation
      if operation == 'receive':
        assert transport.reads == reads, 'revoked owner reached socket receive'
  print('navigation revocation: immediate receive/ack and completion checks passed')


def main():
  root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
  spec = importlib.util.spec_from_file_location('nav_api', root / 'openpilot/tesla/navigation.py')
  api = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(api)
  revocation_checks(api)
  assert api.private_peer('192.168.1.2') and api.private_peer('10.0.0.2')
  assert not any(api.private_peer(x) for x in ('8.8.8.8', '127.0.0.1', '::1', '100.64.1.2'))
  allowed = [True]
  with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
    server.bind(('127.0.0.1', 0))
    server.settimeout(.1)
    port = server.getsockname()[1]
    ingress = api.NavigationIngress('fixture', authorize=lambda: allowed[0], transport=server)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
      client.settimeout(.1)
      client.sendto(b'{}', ('127.0.0.1', port))
      assert ingress.receive() is None  # loopback is not a production phone peer
    try:
      ingress.ack({'sessionId': 'x', 'sequence': 1})
      raise AssertionError('reply without peer')
    except PermissionError:
      pass
    allowed[0] = False
    try:
      ingress.receive()
      raise AssertionError('disabled owner')
    except PermissionError:
      pass
    assert server.fileno() == -1
  print('navigation ingress contract: passed')


if __name__ == '__main__':
  main()
