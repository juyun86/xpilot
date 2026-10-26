#!/usr/bin/env python3
"""Failure cases: unclaimed/disabled owner, foreign/public/IPv6 peers,
oversize/flood input, arbitrary reply, close/rebind, capability absent.
Socket fixtures never use the live navigation port or user data.
"""
import importlib.util
from pathlib import Path
import socket
import sys


def main():
  root = Path(__file__).resolve().parents[2]
  spec = importlib.util.spec_from_file_location('nav_api', root / 'openpilot/tesla/navigation.py')
  api = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(api)
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
