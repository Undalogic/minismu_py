# miniSMU Python Interface

Python interface library for Undalogic miniSMU devices. Supports both USB and network connections for controlling and measuring with miniSMU devices.

## Installation

```bash
pip install minismu_py
```

## Quick Start

```python
from smu_interface import SMU, ConnectionType

# Connect to SMU via USB
smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")

# Basic device operations
print(smu.get_identity())

# Configure channel 1
channel = 1
smu.set_mode(channel, "FVMI")  # Set to FVMI (Force Voltage, Measure Current) mode
smu.enable_channel(channel)
smu.set_voltage(channel, 3.3)  # Set to 3.3V

# Take measurements
voltage, current = smu.measure_voltage_and_current(channel) 
print(f"Voltage: {voltage}V, Current: {current}A")

# Close connection
smu.close()
```

## Examples

The library includes several example scripts demonstrating different use cases:

### Basic Usage (`examples/basic_usage.py`)
- Basic device connection and configuration
- Simple voltage and current measurements
- Temperature monitoring
- Channel enable/disable operations

### USB IV Sweep (`examples/usb_iv_sweep.py`)
- Performs a voltage sweep from -1V to 0.7V
- Measures current at each voltage point
- Saves results to CSV file
- Includes progress bar for monitoring
- Proper error handling and cleanup

### WiFi IV Sweep (`examples/wifi_iv_sweep.py`)
- Similar functionality to USB IV sweep but over network connection
- Demonstrates network-based device control
- Includes connection management and error handling

### Streaming Example (`examples/streaming_example.py`)
- Demonstrates high-speed data streaming capabilities
- Configurable sample rate and duration
- Real-time progress monitoring with voltage and current display
- Automatic data collection and CSV export
- Statistical analysis of collected data
- Device time synchronization for accurate timestamps
- Proper resource cleanup and error handling

## Available Functions

### Connection Management
- `SMU(connection_type, port, host, tcp_port)` - Initialize SMU connection
- `close()` - Close the connection
- `get_identity()` - Get device identification
- `reset()` - Reset the device

### Source and Measurement
- `set_voltage(channel, voltage)` - Set voltage for specified channel
- `set_current(channel, current)` - Set current for specified channel
- `measure_voltage(channel)` - Measure voltage on specified channel
- `measure_current(channel)` - Measure current on specified channel
- `measure_voltage_and_current(channel)` - Measure both voltage and current

### Channel Configuration
- `enable_channel(channel)` - Enable specified channel
- `disable_channel(channel)` - Disable specified channel
- `set_voltage_range(channel, range_type)` - Set voltage range (AUTO/LOW/HIGH)
- `set_mode(channel, mode)` - Set channel mode (FIMV/FVMI)

### Data Streaming
- `start_streaming(channel)` - Start data streaming
- `stop_streaming(channel)` - Stop data streaming
- `set_sample_rate(channel, rate)` - Set sample rate in Hz
- `read_streaming_data()` - Read streaming data packet (channel, timestamp, voltage, current)

### System Configuration
- `set_led_brightness(brightness)` - Set LED brightness (0-100)
- `get_led_brightness()` - Get current LED brightness
- `get_temperatures()` - Get system temperatures (ADC, Channel 1, Channel 2)
- `set_time(timestamp)` - Set device's internal clock (Unix timestamp in milliseconds)

### WiFi Configuration
- `wifi_scan()` - Scan for available WiFi networks
- `get_wifi_status()` - Get current WiFi status
- `set_wifi_credentials(ssid, password)` - Set WiFi credentials
- `enable_wifi()` - Enable WiFi
- `disable_wifi()` - Disable WiFi

## Features

- USB and network connection support
- Comprehensive measurement and source control
- Data streaming capabilities with synchronized timestamps
- System configuration
- Temperature monitoring
- WiFi configuration and management
- Context manager support for proper resource cleanup
- Progress tracking for long operations
- CSV export for measurement data

## Error Handling

The library includes proper error handling through the `SMUException` class. All operations that communicate with the device may raise this exception if there are connection or communication issues.

## Requirements

- Python 3.6 or higher
- `pyserial` for USB connections
- `tqdm` for progress bars (optional, used in examples)
