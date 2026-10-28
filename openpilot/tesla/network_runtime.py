"""Core and independent crash cleanup for host-owned VPN resources."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

from openpilot.tesla.network import ROOT, UID, lease, owner, parked, require_owner, ticks, valid_lease
from openpilot.tesla.network_routes import disable


def core_pids():
  result = []
  for entry in Path('/proc').iterdir():
    if not entry.name.isdigit():
      continue
    try:
      if entry.stat().st_uid == UID and (entry / 'cmdline').read_bytes().split(b'\0')[0] == str(ROOT / 'mihomo').encode():
        result.append(int(entry.name))
    except (OSError, ValueError):
      pass
  return result


def startcore(provider):
  state = owner()
  require_owner(state, provider)
  if not valid_lease(provider, state['lease']) or core_pids():
    raise RuntimeError('VPN daemon is unavailable or core already exists')
  runtime = ROOT / 'runtime'
  runtime.mkdir(exist_ok=True)
  runtime.chmod(0o700)
  os.chown(runtime, UID, UID)
  ROOT.chmod(0o711)
  target = runtime / 'config.yaml'
  shutil.copyfile(ROOT / 'config.yaml', target)
  target.chmod(0o600)
  os.chown(target, UID, UID)
  def demote():
    os.setgroups([])
    os.setgid(UID)
    os.setuid(UID)
  logpath = ROOT / 'core.log'
  logpath.touch(exist_ok=True)
  logpath.chmod(0o600)
  with logpath.open('ab') as log:
    process = subprocess.Popen([str(ROOT / 'mihomo'), '-d', str(runtime), '-f', str(target)],
                               stdout=log, stderr=log, start_new_session=True, preexec_fn=demote,
                               env={'PATH': '/usr/bin:/bin', 'HOME': str(runtime), 'USER': 'xpilot-vpn'})
  pidfile = ROOT / 'pid'
  pidfile.write_text(str(process.pid))
  pidfile.chmod(0o600)
  os.chown(pidfile, 1000, 1000)
  deadline = time.monotonic() + 5
  while time.monotonic() < deadline:
    if process.poll() is not None:
      raise RuntimeError('VPN core exited')
    if process.pid in core_pids():
      helper = Path(__file__).resolve().with_name('network_gateway.py')
      with (ROOT / 'watch.log').open('ab') as log:
        watcher = subprocess.Popen(['/usr/bin/python3', str(helper), provider, 'watch',
                                    str(process.pid), ticks(process.pid)], stdout=log, stderr=log, start_new_session=True)
      (ROOT / 'watch.log').chmod(0o600)
      (ROOT / 'network-watch.pid').write_text(str(watcher.pid))
      return
    time.sleep(.05)
  raise RuntimeError('VPN core launch timed out')


def stop_watch():
  path = ROOT / 'network-watch.pid'
  try:
    pid = int(path.read_text())
    command = Path(f'/proc/{pid}/cmdline').read_bytes()
    if Path(f'/proc/{pid}').stat().st_uid == 0 and b'network_gateway.py' in command and b'watch' in command:
      os.kill(pid, signal.SIGTERM)
      deadline = time.monotonic() + 2
      while Path(f'/proc/{pid}').exists() and time.monotonic() < deadline:
        time.sleep(.05)
      if Path(f'/proc/{pid}').exists():
        os.kill(pid, signal.SIGKILL)
  except (OSError, ValueError):
    pass
  path.unlink(missing_ok=True)


def stopcore(provider):
  if owner() is None:
    return
  require_owner(owner(), provider)
  stop_watch()
  targets = core_pids()
  for pid in targets:
    try:
      os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
      pass
  deadline = time.monotonic() + 4
  while time.monotonic() < deadline and set(targets) & set(core_pids()):
    time.sleep(.1)
  for pid in set(targets) & set(core_pids()):
    try:
      os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
      pass
  deadline = time.monotonic() + 1
  while time.monotonic() < deadline and set(targets) & set(core_pids()):
    time.sleep(.05)
  if set(targets) & set(core_pids()):
    raise RuntimeError('VPN core did not stop')
  (ROOT / 'pid').unlink(missing_ok=True)


def parking_allowed():
  try:
    parked()
    return True
  except (OSError, PermissionError):
    return False


def watch(provider, core_pid, started):
  import fcntl
  from openpilot.tesla.network import CONTROL
  expected = owner()
  require_owner(expected, provider)
  stopped = False
  def explicit_stop(*_):
    nonlocal stopped
    stopped = True
  signal.signal(signal.SIGTERM, explicit_stop)
  signal.signal(signal.SIGINT, explicit_stop)
  def same_core():
    try:
      return core_pid in core_pids() and ticks(core_pid) == started
    except OSError:
      return False
  while not stopped and same_core() and valid_lease(provider, expected['lease']) and parking_allowed():
    time.sleep(.5)
  if stopped:
    return
  with (CONTROL / 'lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    current = owner()
    if current is None or current.get('lease') != expected['lease']:
      return  # Never clean a replacement generation.
    if same_core():
      os.kill(core_pid, signal.SIGTERM)
      deadline = time.monotonic() + 1
      while same_core() and time.monotonic() < deadline:
        time.sleep(.05)
      if same_core():
        os.kill(core_pid, signal.SIGKILL)
    disable(provider)
    (ROOT / 'pid').unlink(missing_ok=True)
