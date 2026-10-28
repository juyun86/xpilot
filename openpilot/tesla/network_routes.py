"""Root-owned routing resources for the fixed reviewed IPv4 VPN profile."""
import ipaddress
import json
import os
from pathlib import Path
import pwd
import socket

from openpilot.tesla.network import CONTROL, DEV, MARK, OWNER, ROOT, TABLE, UID, lease, owner, require_owner, run

IPT = 'iptables-legacy'
CHAINS = (('mangle', 'C3MH_MARK', 'OUTPUT'), ('nat', 'C3MH_OUTDNS', 'OUTPUT'), ('filter', 'C3MH_INPUT', 'INPUT'))


def remember(key, value):
  state = owner()
  if state is None:
    raise PermissionError('Missing VPN ownership record')
  state[key] = value
  pending = OWNER.with_suffix('.pending')
  pending.write_text(json.dumps(state))
  os.replace(pending, OWNER)


def hotspot():
  data = json.loads(run('ip', '-j', '-4', 'addr', 'show', 'dev', 'wlan0').stdout)
  for dev in data:
    for address in dev.get('addr_info', []):
      if address.get('local') == '192.168.43.1':
        return str(ipaddress.ip_network(f"{address['local']}/{address['prefixlen']}", strict=False))
  return None


def reserve(provider):
  previous = owner()
  if previous is not None:
    require_owner(previous, provider)
    if previous['lease'] != lease():
      raise PermissionError('Previous VPN generation must be cleaned first')
    return
  # Refuse collisions before changing anything; never adopt an existing interface.
  if run('ip', 'link', 'show', DEV, check=False).returncode == 0:
    raise RuntimeError('VPN interface already exists')
  if run('ip', 'route', 'show', 'table', TABLE, check=False).stdout.strip():
    raise RuntimeError('VPN routing table already exists')
  rules = json.loads(run('ip', '-j', 'rule').stdout)
  if any(r.get('priority') in (17880, 17890) or str(r.get('table')) == TABLE for r in rules):
    raise RuntimeError('VPN routing policy already exists')
  for table, chain in [('nat', 'C3MH_DNS'), *[(t, c) for t, c, _ in CHAINS]]:
    if run(IPT, '-t', table, '-S', chain, check=False).returncode == 0:
      raise RuntimeError('VPN firewall chain already exists')
  try:
    pwd.getpwuid(UID)
  except KeyError:
    pass
  else:
    raise RuntimeError('VPN runtime UID is assigned')
  for entry in Path('/proc').iterdir():
    try:
      if (entry.name.isdigit() and entry.stat().st_uid == UID
          and (entry / 'stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'):
        raise RuntimeError('VPN runtime UID already has a process')
    except FileNotFoundError:
      pass
  for port in (17890, 17891, 17893):
    for kind in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
      with socket.socket(socket.AF_INET, kind) as probe:
        # Closed Go listeners can leave TIME_WAIT. This still rejects listeners,
        # while allowing immediate managed restart after a verified core stop.
        if kind == socket.SOCK_STREAM:
          probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('0.0.0.0', port))
  CONTROL.mkdir(mode=0o700, parents=True, exist_ok=True)
  previous_forward = Path('/proc/sys/net/ipv4/ip_forward').read_text().strip()
  state = {'provider': provider, 'lease': lease(), 'previous_forward': previous_forward,
           'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'chains': [], 'rules': [], 'hooks': []}
  pending = OWNER.with_suffix('.pending')
  pending.write_text(json.dumps(state))
  pending.chmod(0o600)
  os.replace(pending, OWNER)


def prepare(provider):
  reserve(provider)
  if owner().get('interface'):
    return
  run('ip', 'tuntap', 'add', 'dev', DEV, 'mode', 'tun', 'user', str(UID))
  remember('interface', True)
  run('ip', 'addr', 'replace', '198.18.0.1/30', 'dev', DEV)
  run('ip', 'link', 'set', DEV, 'up')
  Path('/proc/sys/net/ipv4/ip_forward').write_text('1')


def hotspot_rules(network):
  if not network:
    return []
  return [('-t', 'nat', 'PREROUTING', '-i', 'wlan0', '-j', 'C3MH_DNS'),
          ('-t', 'filter', 'FORWARD', '-i', 'wlan0', '-o', DEV, '-j', 'ACCEPT'),
          ('-t', 'filter', 'FORWARD', '-i', DEV, '-o', 'wlan0', '-j', 'ACCEPT')]


def enable(provider):
  state = owner()
  require_owner(state, provider)
  if state.get('enabled'):
    return
  network = hotspot()
  remember('hotspot', network)
  if network:
    run('ip', 'route', 'replace', network, 'dev', 'wlan0', 'table', TABLE)
    remember('hotspot_route', True)
    run('ip', 'rule', 'add', 'priority', '17890', 'iif', 'wlan0', 'lookup', TABLE)
    remember('rules', ['hotspot'])
  run('ip', 'route', 'replace', 'default', 'dev', DEV, 'table', TABLE)
  remember('default_route', True)
  for table, chain in [('nat', 'C3MH_DNS'), *[(t, c) for t, c, _ in CHAINS]]:
    run(IPT, '-t', table, '-N', chain)
    remember('chains', owner()['chains'] + [[table, chain]])
  for protocol in ('udp', 'tcp'):
    run(IPT, '-t', 'nat', '-A', 'C3MH_DNS', '-p', protocol, '--dport', '53', '-j', 'REDIRECT', '--to-ports', '17893')
  for rule in hotspot_rules(network):
    run(IPT, *rule[:2], '-I', *rule[2:])
    remember('hooks', owner()['hooks'] + [list(rule)])
  for chain, table in (('C3MH_MARK', 'mangle'), ('C3MH_OUTDNS', 'nat')):
    run(IPT, '-t', table, '-A', chain, '-m', 'owner', '--uid-owner', str(UID), '-j', 'RETURN')
  for subnet in ('127.0.0.0/8', '192.168.0.0/16', '10.0.0.0/8', '172.16.0.0/12', '169.254.0.0/16',
                 '198.18.0.0/15', '224.0.0.0/4', '255.255.255.255/32'):
    run(IPT, '-t', 'mangle', '-A', 'C3MH_MARK', '-d', subnet, '-j', 'RETURN')
  run(IPT, '-t', 'mangle', '-A', 'C3MH_MARK', '-j', 'MARK', '--set-mark', MARK)
  for protocol in ('udp', 'tcp'):
    run(IPT, '-t', 'nat', '-A', 'C3MH_OUTDNS', '-p', protocol, '--dport', '53', '-j', 'REDIRECT', '--to-ports', '17893')
  for interface in (('lo', 'wlan0') if network else ('lo',)):
    run(IPT, '-t', 'filter', '-A', 'C3MH_INPUT', '-i', interface, '-j', 'RETURN')
  for protocol in ('udp', 'tcp'):
    run(IPT, '-t', 'filter', '-A', 'C3MH_INPUT', '-p', protocol, '--dport', '17893', '-j', 'REJECT')
  for table, chain, parent in CHAINS:
    run(IPT, '-t', table, '-I', parent, '-j', chain)
    remember('hooks', owner()['hooks'] + [['-t', table, parent, '-j', chain]])
  run('ip', 'rule', 'add', 'priority', '17880', 'fwmark', MARK + '/0xffff', 'lookup', TABLE)
  remember('rules', owner()['rules'] + ['mark'])
  (ROOT / 'gateway_enabled').write_text('1')
  remember('enabled', True)


def disable(provider):
  state = owner()
  if state is None:
    return  # No ownership record means no right to remove resources.
  require_owner(state, provider)
  if 'mark' in state['rules']:
    run('ip', 'rule', 'del', 'priority', '17880', 'fwmark', MARK + '/0xffff', 'lookup', TABLE, check=False)
  if 'hotspot' in state['rules']:
    run('ip', 'rule', 'del', 'priority', '17890', 'iif', 'wlan0', 'lookup', TABLE, check=False)
  for rule in reversed(state['hooks']):
    run(IPT, *rule[:2], '-D', *rule[2:], check=False)
  for table, chain in reversed(state['chains']):
    run(IPT, '-t', table, '-F', chain, check=False)
    run(IPT, '-t', table, '-X', chain, check=False)
  if state.get('default_route'):
    run('ip', 'route', 'del', 'default', 'dev', DEV, 'table', TABLE, check=False)
  if state.get('hotspot_route'):
    run('ip', 'route', 'del', state['hotspot'], 'dev', 'wlan0', 'table', TABLE, check=False)
  if state.get('interface'):
    run('ip', 'link', 'del', DEV, check=False)
  Path('/proc/sys/net/ipv4/ip_forward').write_text(state['previous_forward'])
  (ROOT / 'gateway_enabled').unlink(missing_ok=True)
  OWNER.unlink()
