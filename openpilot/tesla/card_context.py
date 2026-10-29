"""Nonblocking, declared-service snapshots for card plugin hooks."""
from types import MappingProxyType

METADATA = ('seen', 'alive', 'valid', 'updated', 'logMonoTime', 'recv_time')


class CardContext:
  __slots__ = ('_data', '_metadata')

  def __init__(self, sm, names):
    object.__setattr__(self, '_data', MappingProxyType({name: sm[name] for name in names}))
    object.__setattr__(self, '_metadata', MappingProxyType({
      key: MappingProxyType({name: getattr(sm, key)[name] for name in names}) for key in METADATA
    }))

  def __getitem__(self, name):
    return self._data[name]

  def __getattr__(self, name):
    try:
      return self._metadata[name]
    except KeyError as exc:
      raise AttributeError(name) from exc

  def __setattr__(self, name, value):
    raise AttributeError('card context is read-only')


class CardSubscriptions:
  def __init__(self, factory=None):
    self._factory = factory
    self._sm = None
    self._names = frozenset()

  def poll(self, subscriptions):
    if not subscriptions:
      return {}
    names = frozenset(name for declared in subscriptions.values() for name in declared)
    if not names:
      return {name: CardContext(None, ()) for name in subscriptions}
    if self._sm is None:
      factory = self._factory
      if factory is None:
        from openpilot.cereal import messaging
        factory = messaging.SubMaster
      self._sm = factory(sorted(names))
      self._names = names
    if not names <= self._names:
      raise ValueError('card subscriptions are frozen at startup')
    self._sm.update(0)
    return {owner: CardContext(self._sm, declared) for owner, declared in subscriptions.items()}
