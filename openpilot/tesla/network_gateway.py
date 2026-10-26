"""Fixed root entrypoint; never imports or executes downloaded plugin code."""
import fcntl
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from openpilot.tesla.network import CONTROL, authorized, checked_action, parked, valid_lease
from openpilot.tesla import network_routes as routes, network_runtime as runtime


def main():
  os.umask(0o077)
  if os.geteuid() != 0 or not Path('/AGNOS').is_file():
    raise PermissionError('AGNOS root entrypoint required')
  provider, action = sys.argv[1:3]
  if action == 'watch':
    checked_action(provider, 'prepare')
    runtime.watch(provider, int(sys.argv[3]), sys.argv[4])
    return
  checked_action(provider, action)
  CONTROL.mkdir(mode=0o700, parents=True, exist_ok=True)
  if CONTROL.is_symlink() or CONTROL.stat().st_uid != 0:
    raise PermissionError('Invalid host control directory')
  with (CONTROL / 'lock').open('a') as lock:
    deadline = time.monotonic() + 10
    while True:
      try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        break
      except BlockingIOError:
        if time.monotonic() >= deadline:
          raise TimeoutError('Network operation busy')
        time.sleep(.05)
    if action in ('prepare', 'startcore', 'enable'):
      authorized(provider)
      parked()  # Recheck after acquiring the lock, not only at request time.
      if not valid_lease(provider):
        raise PermissionError('VPN service lease is unavailable')
    handlers = {'prepare': routes.prepare, 'enable': routes.enable, 'disable': routes.disable,
                'startcore': runtime.startcore, 'stopcore': runtime.stopcore}
    if action == 'disable':
      runtime.stopcore(provider)
    handlers[action](provider)
  print(json.dumps({'ok': True}))


if __name__ == '__main__':
  try:
    main()
  except Exception:
    print(json.dumps({'error': 'Host VPN operation failed'}))
    sys.exit(1)
