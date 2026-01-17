# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
