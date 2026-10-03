# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2026-10-03

### Fixed

- **Streaming can no longer hang the connection indefinitely**
  ([#5](https://github.com/Undalogic/minismu_py/issues/5)). The read loops
  used by `stop_streaming()` and for multi-line/JSON responses (sweep data)
  only timed out after a quiet gap, so a device that kept streaming blocked
  them forever. They now have an absolute time limit: `stop_streaming()`
  raises `SMUException` if data is still arriving after 2 s (typically
  because the other channel is still streaming - stop it too), and sweep data
  reads raise after 30 s.
- **`stop_streaming()` now works on a stream left running by a previous
  session.** The device keeps a partially received command line across USB
  sessions, so `STREAM OFF` could be appended to stray bytes and ignored.
  `stop_streaming()` now sends a blank line first to flush it. Verified on
  hardware (fw v1.4.6).

## [0.4.0] - 2026-07-06

### Fixed

- **Network (TCP) responses are now read reliably.** Previously a single
  `recv(1024)` was used per command, so responses larger than 1024 bytes or
  split across TCP segments were truncated - onboard sweep data retrieval and
  `wifi_scan()` were effectively broken over network connections. Responses
  are now buffered and reassembled line-by-line, with the same chunked-JSON
  handling as USB.
- **CSV sweep data retrieval now returns all points.** The response reader
  returned only the first line of multi-line CSV sweep data, so
  `run_iv_sweep(..., output_format="CSV")` and `get_sweep_data_csv()`
  silently returned a single data point. Verified on hardware (fw v1.5.0).
- **Streaming no longer desynchronises the connection.** `stop_streaming()`
  now drains in-flight streamed data, so commands issued after stopping a
  stream see clean responses instead of stale data packets. Opening a USB
  connection also discards any stale buffered data from a previous session.
- **Streaming data parsing supports firmware v1.5.0+ packets**, which append
  extra fields (e.g. active current range) after channel/timestamp/voltage/
  current.
- `run_iv_sweep()` completion polling no longer races the sweep start (an
  early `IDLE` status was previously treated as completion) and can no longer
  loop forever - it times out with an `SMUException` if the sweep doesn't
  complete within the expected duration plus 30 seconds. `ABORTED` now raises
  consistently in both the monitored and unmonitored paths.
- Fixed a serial timeout leak in the chunked-response reader that could
  permanently reduce the port timeout from 1 s to 0.1 s after a read error.
- Network connection attempts now time out after 5 seconds instead of
  hanging for the OS default.
- `reset()` no longer expects a response; the device reboots and
  re-enumerates, so the old behaviour raised a spurious error.

### Changed

- **Device-reported errors now raise `SMUException`.** Non-query commands
  are acknowledged with `OK`; any other response (e.g.
  `Invalid channel number`) raises. Previously errors for setter commands
  (including protection limits) were silently discarded.
- Malformed responses to measurement and status queries now raise
  `SMUException` instead of leaking bare `ValueError` from float parsing.
- `set_wifi_credentials()` raises `ValueError` if the SSID or password
  contains double quotes or newlines, which would break command framing.

### Known issues

- Firmware v1.5.0 and earlier truncate responses larger than ~5.7 kB over
  TCP: the device stops transmitting after exactly 5744 bytes (the TCP send
  buffer size), regardless of how quickly the client reads. Over network
  connections this limits sweeps to roughly 95 points in JSON format and
  ~175 points in CSV format. This is a firmware-side bug; the library now
  detects the truncation (including the case where a sheared CSV line still
  parses as a plausible value) and raises a descriptive `SMUException`
  instead of returning incomplete data. USB is unaffected.
- Firmware v1.5.0 reports WiFi status as `{"status": "Connected", ...}`
  with no RSSI field; `get_wifi_status()` now understands this shape
  (previously it always reported `connected=False`), and `rssi` is 0 when
  the firmware doesn't provide it. Verified against v1.4.6 as well, which
  uses the same schema.
- Firmware v1.4.6 does not validate channel numbers (it acknowledges e.g.
  `SOUR9:VOLT` with `OK`), so invalid-channel mistakes only raise on
  v1.5.0+, where the firmware reports them.

## [0.3.0] - 2025-11-26

### Added

- **4-Wire (Kelvin) Measurement Mode** - New methods for high-accuracy measurements that eliminate lead resistance errors:
  - `enable_fourwire_mode()` - Enable 4-wire mode (CH2 becomes high-impedance sense channel)
  - `disable_fourwire_mode()` - Disable 4-wire mode and restore independent channel operation
  - `get_fourwire_mode()` - Query current 4-wire mode status (returns `bool`)
- New example `examples/fourwire_iv_sweep.py` demonstrating 4-wire measurement techniques

### Notes

4-wire mode operation:
- CH1 acts as the source/force channel
- CH2 acts as the sense channel (FIMV mode @ 0A, high impedance)
- Measurements on CH1 return CH1 current + CH2 voltage (true DUT voltage)
- Cannot enable while streaming or sweep is active
- CH2 commands are blocked while 4-wire mode is active
- `OUTP1 ON/OFF` controls both channels together in 4-wire mode

## [0.2.0] - 2025-10-15

### Added

- **Onboard I-V Sweep Support** - Complete implementation for firmware v1.3.4+:
  - `configure_iv_sweep()` - Configure all sweep parameters at once
  - `set_sweep_start_voltage()` / `set_sweep_end_voltage()` - Individual voltage setters
  - `set_sweep_points()` - Set number of measurement points (1-1000)
  - `set_sweep_dwell_time()` - Set dwell time between points (0-10000ms)
  - `enable_sweep_auto_output()` / `disable_sweep_auto_output()` - Auto output control
  - `get_sweep_auto_output_status()` - Query auto output setting
  - `set_sweep_output_format()` / `get_sweep_output_format()` - CSV or JSON format
  - `execute_sweep()` / `abort_sweep()` - Control sweep execution
  - `get_sweep_status()` - Get sweep progress information
  - `get_sweep_data_raw()` / `get_sweep_data_csv()` / `get_sweep_data_json()` - Data retrieval
  - `run_iv_sweep()` - High-level method for complete sweep operation with progress monitoring
- New data classes: `SweepStatus`, `SweepConfig`, `SweepDataPoint`, `SweepResult`
- New example `examples/onboard_iv_sweep.py` with comprehensive sweep demonstrations
- Improved USB response handling for large JSON data with chunk validation

### Changed

- Enhanced `_read_usb_response()` with robust UTF-8 error handling
- Added JSON completion detection and automatic cleaning for corrupted responses

## [0.1.0] - 2025-09-01

### Added

- Initial release
- USB and Network (TCP) connection support
- Channel control methods (`enable_channel`, `disable_channel`, `set_mode`)
- Source configuration (`set_voltage`, `set_current`, `set_voltage_range`)
- Protection settings (`set_current_protection`, `set_voltage_protection`)
- Measurement methods (`measure_voltage`, `measure_current`, `measure_voltage_and_current`)
- Data streaming support (`start_streaming`, `stop_streaming`, `read_streaming_data`)
- System configuration (`set_led_brightness`, `get_temperatures`, `set_time`)
- WiFi configuration (`wifi_scan`, `get_wifi_status`, `set_wifi_credentials`, etc.)
- Context manager support for automatic connection cleanup
- `SMUException` for error handling
- `WifiStatus` data class for WiFi status information
- Basic examples: `basic_usage.py`, `streaming_example.py`, `usb_iv_sweep.py`
