# Card context API

Purpose: allow installed plugins to consume existing messages such as motion and
calibration without modifying SP card subscriptions for each radar model.

Declare `requires.hooks: ["card_context"]` and a class-level `SERVICES` tuple of
existing service names. Discovery rejects unknown service names. Only enabled,
claim-winning, successfully constructed plugins that override `card_context`
contribute subscriptions. Services are frozen for the drive; restart applies
enable/disable, removal or upgrade. A no-op hook creates no subscriptions.

`card_context(context, now_ns)` runs immediately before that plugin's
`control_sends(CS, CC, now_ns)`. One shared SubMaster polls with timeout zero per
control cycle. Each plugin receives only its declared services. Payloads are
SubMaster's capnp readers; metadata mappings `seen`, `alive`, `valid`, `updated`,
`logMonoTime`, `recv_time` are immutable snapshots. The timestamp argument is the
same monotonic nanoseconds passed to control_sends. Original message timestamps
and health are never replaced with polling time. Plugins must check freshness,
finiteness and message-specific health; stale or unseen input grants no action.

A hook exception drops that plugin before sending anything from its control
hook, using existing fault recording. A shared subscription/poll failure drops
only context consumers; unrelated plugins continue. Dropped consumers no longer
receive callbacks. When none remain, polling stops. Sockets belong to card and
are reclaimed when that process exits; no files, parameters, private state or
extra processes are created. An old retained view is not refreshed in place.

The API grants read access, not CAN permission or an operating-system sandbox.
All generated frames still need exact can.tx claims, Panda rules and existing
core-alive gates. No vehicle port, safety mode or rule ABI is changed here.
In particular, this API alone does not enable ARS408 motion transmission.

Validation: `tools/sp_tesla_e2e/card_context_check.py` uses synthetic snapshots
for restricted reads, immutable metadata, original time/validity, nonblocking
polling, frozen subscriptions and dropped consumers. It is not firmware or road
validation. Cross-process/device acceptance remains separately required.

## Radar receiver context

A provider returned by radar_interface may implement
`radar_context(context, now_ns)` and declare `requires.hooks: ["radar_context"]`.
The guard calls it immediately before that provider's update, using only its
owning Plugin.SERVICES and the same immutable snapshot format. It has a separate
nonblocking subscription so it does not depend on card controller construction
or control_sends running. Source context failures are recorded, latch the source
off and use the original receiver, just like source update failures. Existing
providers without the callback are unchanged. This lets a receiver mark missing
motion as temporarily unavailable rather than publishing valid-looking targets.
`radar_context_check.py` exercises the actual guard with synthetic inputs.
