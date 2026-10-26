# Sensor motion rule v1

## Reason and scope

ARS408 consumes vehicle speed and calibrated yaw even while driving control is
disengaged. These are sensor inputs, not steering, braking or engagement commands.
The existing template_clone.v1 requires equal RX/TX length and controls_allowed
except for explicit cancel values; it cannot express these two sensor frames.
This new closed wire profile extends the runtime engine without changing any
existing template rule, Tesla mode-owned address or G8 longitudinal owner gate.

The manifest declares two rules of the form
`{"type":"sensor_motion.v1","tx_address":768,"tx_bus":1}` (769 for yaw),
matching `can.tx:0x300:1` and `can.tx:0x301:1`, plus
`requires: {"rule_abi":1,"rule_types":["sensor_motion.v1"]}`. No other address,
bus or configurable property is accepted. Host capability checking rejects old
hosts. Old firmware rejects record type 2 at COMMIT, causing the existing loader
to clear/fault the feature; a manifest claim never grants firmware permission.

## Binary and firmware constraints

Table/upload ABI 1 is unchanged. Type 2 is an 84-byte record with no fields or
tuples. Layout uses the existing offsets: TX address 0x300/0x301, RX address
0x60A, both bus 1, TX length 2, RX length 4, TTL 200000 us, min interval 40000 us,
WINDOW session 2, count 25, idle 0, window 1000000 us. All other bytes are zero,
including predicate/copy masks, counters, checksums and reserved bytes. Firmware
compares the complete record to this fixed form; any other encoding is rejected.

- Require a real, fresh standard-ID 0x60A object-status frame on bus 1, DLC 4.
  Host calls cannot refresh that RX timestamp. This is sensor presence, not proof
  of road coverage or radar accuracy; plugin diagnostics still apply.
- Speed (0x300): big-endian 16 bits, direction bits 15..14 in {0,1,2}, reserved
  bit 13 zero, speed bits 12..0 at 0.02 m/s in 0..4250 (85 m/s). Direction zero
  iff speed zero; 1 forward and 2 reverse. Invalid values are rejected.
- Yaw (0x301): big-endian raw 22768..42768 inclusive, encoding -100..100 deg/s
  with 0.01 resolution and -327.68 offset.
- Require Tesla mode, vehicle bus and no relay malfunction. NoOutput/Silent,
  wrong DLC/bus/ID type, unclaimed/duplicate address and stale RX reject TX.
- Sensor input alone may pass while controls_allowed is false. It is **not** a
  budget exemption: interval, window count, reset, expiry and wrap handling all
  remain active. Vehicle control addresses retain their original checks.

The plugin produces at 20 Hz; the firmware's 25 Hz ceiling tolerates scheduling
and clock jitter. It consumes validated host card_context and rejects motion
older than 150 ms, calibration older than 2 s, invalid CAN speed and nonfinite
values. Host/card faults stop the plugin and request existing rule revocation.
No parameter, file, subprocess, configuration write or raw CAN socket is added.

## Lifecycle and validation

Existing offroad arming, CAPS-before-EP2, upload CRC/status, onroad fault latching,
CLEAR and safety-mode reset contracts apply unchanged. Disabling/uninstalling
requires the normal parked restart; the next setup omits its rules. No in-drive
rearming or unsupported-firmware fallback grants TX. Installing software does
not implicitly flash Panda or prove a compatible device runtime.

Tests were specified first: host fixed-record encoding and malformed manifest
rejection; C-engine exhaustive 16-bit payloads for both messages; bytewise profile
mutation; freshness, rate, wrap, bus/DLC/ID type, CLEAR and relay/mode gates.
Run the complete existing safety suite, host checks, MISRA and F4/H7/body builds.
Report compiled/tested commits separately from any device flash and road test.
