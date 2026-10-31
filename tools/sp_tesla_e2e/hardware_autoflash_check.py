"""Firmware policy regression, without USB I/O or starting a flash subprocess.

Failure cases:
- Runtime/ROM USB IDs with an unknown product trigger automatic flashing.
- An onroad/offroad transition or repeated detection retries the flash.
- Disconnect or an unrelated USB device retains stale firmware state.
"""

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
usb_path = root / "openpilot/common/hardware/usb.py"
usb_tree = ast.parse(usb_path.read_text())
names = {"CHESTNUT_FW_VERSION", "CHESTNUT_USB_IDS", "CHESTNUT_ROM_USB_IDS", "CHESTNUT_USB_PRODUCT"}
usb_nodes = [
  node for node in usb_tree.body
  if (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names for target in node.targets))
  or (isinstance(node, ast.FunctionDef) and node.name == "is_chestnut_usb_id")
]
env = {}
exec(compile(ast.Module(body=usb_nodes, type_ignores=[]), str(usb_path), "exec"), env)
started = []


class FakeThread:
  def __init__(self, target, daemon):
    self.target = target

  def start(self):
    self.target()

  def is_alive(self):
    return False


env.update(threading=SimpleNamespace(Thread=FakeThread), time=SimpleNamespace(monotonic=lambda: 100.0),
           cloudlog=SimpleNamespace(warning=lambda message: None))
path = root / "openpilot/system/hardware/hardwared.py"
tree = ast.parse(path.read_text())
node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Chestnut")
exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), env)
cases = [([], "absent"), ([{"vendorId": 0x1234, "productId": 1, "product": "unknown"}], "unrelated")]
for vendor, product in env["CHESTNUT_USB_IDS"] + env["CHESTNUT_ROM_USB_IDS"]:
  for name in (env["CHESTNUT_USB_PRODUCT"], "custom ed4e39b7-CLEAN", ""):
    cases.append(([{"vendorId": vendor, "productId": product, "product": name}], f"{vendor:04x}:{product:04x}/{name}"))

failures = []
for devices, name in cases:
  monitor = env["Chestnut"]()
  monitor.flash = lambda name=name: started.append(name)
  for offroad in (True, False, True):
    monitor.update(offroad, devices)
  if monitor.attempts or monitor.thread is not None or monitor.flashing or monitor.failed:
    failures.append(name)
  monitor.flashed = True
  monitor.update(True, [])
  assert not monitor.flashed and not monitor.mismatch, f"disconnect reset failed: {name}"

assert not failures and not started, f"automatic flash permitted: {failures}; flash calls: {started}"
print(f"PASS: {len(cases)} USB inventories, repeated offroad/onroad transitions, disconnect reset; no flash")
