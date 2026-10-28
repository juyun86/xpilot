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
  """Resolve valid manifests and all exclusive claims, without importing plugin code.

  A manifest whose code cannot load can only make this check more restrictive;
  the separately verified service lease ensures the requested worker is running.
  """
  from openpilot.tesla import manifest as mf
  builtin, _ = mf.load_all(mf.PLUGINS_DIR)
  installed, _ = mf.load_all(mf.INSTALL_DIR)
  taken_ids = {m.id for m in builtin}
  taken_keys = mf.compiled_param_keys()
  specs = set()
  accepted = list(builtin)
  for m in installed:
    if m.id in taken_ids or set(m.params) & (taken_keys | specs):
      continue
    accepted.append(m)
    specs.update(m.params)
  enabled = set()
  valid = []
  for m in accepted:
    ok, _ = mf.compatible(m, mf.HOST_CAPS)
    if not ok:
      continue
    valid.append(m)
    key = m.enable_param
    if key is None:
      enabled.add(m.id)
      continue
    path = (mf.INSTALL_DIR / '.params' if m in installed else Path('/data/params/d')) / key
    default = m.params.get(key, {}).get('default', '0') if m in installed else '0'
    try:
      value = path.read_text().strip()
    except FileNotFoundError:
      value = str(default)
    if value in ('1', 'true', 'True'):
      enabled.add(m.id)
  active, _ = mf.resolve([(m.id, m.priority, m.claims) for m in valid], enabled)
  if not any(m.id == provider and m.id in active and 'role:network.vpn' in m.claims for m in valid):
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
