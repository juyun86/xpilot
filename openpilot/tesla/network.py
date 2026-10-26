"""Bounded IPv4 VPN API for reviewed plugins. Claims are not an OS sandbox."""
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path('/data/mihomo')
CONTROL = Path('/data/xpilot_network')
OWNER = CONTROL / 'vpn-owner.json'
DEV, TABLE, MARK, UID = 'c3mh0', '17890', '17890', 61400
ACTIONS = frozenset(('prepare', 'startcore', 'stopcore', 'enable', 'disable'))


def checked_action(provider, action):
  if not isinstance(provider, str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}', provider):
    raise ValueError('Invalid network provider')
  if action not in ACTIONS:
    raise ValueError('Unsupported network action')


def require_owner(owner, provider):
  if not isinstance(owner, dict) or owner.get('provider') != provider:
    raise PermissionError('Network resources belong to another provider')


def parked():
  if Path('/data/params/d/IsOffroad').read_text().strip() != '1':
    raise PermissionError('Park before changing the VPN')
  engaged = Path('/data/params/d/IsEngaged')
  if engaged.exists() and engaged.read_text().strip() == '1':
    raise PermissionError('Disengage before changing the VPN')


def owner():
  try:
    state = json.loads(OWNER.read_text())
    if state.get('boot_id') != Path('/proc/sys/kernel/random/boot_id').read_text().strip():
      OWNER.unlink()  # Kernel resources do not survive reboot; never adopt new ones.
      return None
    return state
  except FileNotFoundError:
    return None


def authorized(provider):
  """Check installed manifest/enable state without importing downloaded code."""
  candidates = []
  for path in Path('/data/xpilot_plugins').glob('*/plugin.json'):
    try:
      data = json.loads(path.read_text())
      if data.get('id') != path.parent.name or 'role:network.vpn' not in data.get('claims', []):
        continue
      key = data.get('enable_param')
      if not isinstance(key, str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]*', key):
        continue
      value = Path('/data/xpilot_plugins/.params') / key
      default = data.get('params', {}).get(key, {}).get('default', '0')
      enabled = value.read_text().strip() if value.is_file() else str(default)
      if enabled in ('1', 'true', 'True'):
        candidates.append((int(data.get('priority', 100)), data['id']))
    except (ValueError, OSError, TypeError):
      continue
  if not candidates or min(candidates)[1] != provider:
    raise PermissionError('Network provider is not the enabled role owner')


def run(*args, check=True):
  return subprocess.run(list(args), capture_output=True, text=True, check=check, timeout=8)


def ticks(pid):
  return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def lease():
  return json.loads((ROOT / 'network-lease.json').read_text())


def valid_lease(provider, state=None):
  try:
    state = lease() if state is None else state
    pid = int(state['pid'])
    command = Path(f'/proc/{pid}/cmdline').read_bytes()
    return (Path(f'/proc/{pid}').stat().st_uid == 1000 and ticks(pid) == state['start']
            and f'xpilot_ext.{provider}.service'.encode() in command)
  except (OSError, ValueError, KeyError):
    return False


class NetworkVPN:
  """Fixed profile: no shell, command text, executable path or routing arguments."""
  def __init__(self, provider):
    checked_action(provider, 'prepare')
    self.provider = provider

  def request(self, action):
    checked_action(self.provider, action)
    if action in ('prepare', 'startcore', 'enable'):
      authorized(self.provider)
      parked()
    helper = Path(__file__).resolve().with_name('network_gateway.py')
    result = subprocess.run(['sudo', '-n', '/usr/bin/python3', str(helper), self.provider, action],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
      raise RuntimeError('Host VPN operation failed: ' + action)
    return json.loads(result.stdout)
