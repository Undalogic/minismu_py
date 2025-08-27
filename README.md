# miniSMU Python Library

A comprehensive Python library for controlling the miniSMU MS01 Source Measure Unit (SMU) from Undalogic. This library provides both USB and WiFi connectivity options with support for advanced features including onboard I-V sweeps, protection settings, and high-precision measurements.

## Features

- **Dual Connectivity**: USB (CDC) and WiFi (TCP) connections
- **Complete SMU Control**: Voltage/current sourcing, measurement, and channel management
- **Advanced Measurement Features**: Configurable oversampling ratio (OSR) for precision control
- **Safety Protection**: Current and voltage protection limits
- **Onboard I-V Sweeps**: Hardware-accelerated sweeps with progress monitoring (firmware v1.3.4+)
- **WiFi Management**: Network configuration, scanning, and auto-connect settings
- **Data Streaming**: Real-time continuous measurements
- **Robust Communication**: Handles chunked USB data and corruption gracefully

## Installation

### From Source
```bash
git clone https://github.com/Undalogic/minismu_py.git
cd minismu_py
pip install -e .
```

### Dependencies
- `pyserial` - For USB communication
- `tqdm` - For progress bars (optional, used in examples)
- `matplotlib` - For plotting (optional, used in plotting examples)

## Quick Start

### Basic Usage (USB Connection)
```python
from minismu_py import SMU, ConnectionType

# Connect to miniSMU via USB
with SMU(ConnectionType.USB, port="COM3") as smu:  # Adjust port for your system
    print(f"Connected to: {smu.get_identity()}")
    
    # Configure channel 1 for voltage sourcing
    smu.set_mode(1, "FVMI")  # Force Voltage, Measure Current
    smu.set_voltage(1, 1.2)  # Set 1.2V output
    smu.enable_channel(1)
    
    # Take measurements
    voltage, current = smu.measure_voltage_and_current(1)
    print(f"Measured: {voltage:.3f}V, {current*1000:.3f}mA")
    
    smu.disable_channel(1)
```

### Basic Usage (WiFi Connection)
```python
from minismu_py import SMU, ConnectionType

# Connect to miniSMU via WiFi
with SMU(ConnectionType.NETWORK, host="192.168.1.106") as smu:
    # Same usage as USB connection
    print(f"Connected to: {smu.get_identity()}")
```

## Core Functionality

### Connection Management

#### USB Connection
```python
# Windows
smu = SMU(ConnectionType.USB, port="COM3")

# Linux/macOS
smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
```

#### Network Connection
```python
smu = SMU(ConnectionType.NETWORK, host="192.168.1.106", tcp_port=3333)
```

### Channel Configuration

#### Operating Modes
```python
smu.set_mode(1, "FVMI")  # Force Voltage, Measure Current
smu.set_mode(1, "FIMV")  # Force Current, Measure Voltage
```

#### Output Control
```python
smu.set_voltage(1, 3.3)      # Set 3.3V on channel 1
smu.set_current(1, 0.01)     # Set 10mA on channel 1
smu.enable_channel(1)        # Enable output
smu.disable_channel(1)       # Disable output
```

#### Protection Limits
```python
smu.set_current_protection(1, 0.1)    # 100mA current limit in FVMI mode
smu.set_voltage_protection(1, 5.0)    # 5V voltage limit in FIMV
```

### Measurements

#### Single Measurements
```python
voltage = smu.measure_voltage(1)
current = smu.measure_current(1)
voltage, current = smu.measure_voltage_and_current(1)
```

#### Precision Control
```python
# Set oversampling ratio (0-15, represents approx. 2^OSR samples)
smu.set_oversampling_ratio(1, 12)
```

### Data Streaming
```python
smu.set_sample_rate(1, 1000)      # 1000 Hz sampling
smu.start_streaming(1)

# Read streaming data
for _ in range(100):
    channel, timestamp, voltage, current = smu.read_streaming_data()
    print(f"CH{channel}: {voltage:.3f}V, {current*1000:.3f}mA @ {timestamp}")

smu.stop_streaming(1)
```

## Advanced Features

### Onboard I-V Sweeps (Firmware v1.3.4+)

The miniSMU can perform I-V sweeps directly on the device, reducing communication overhead and providing more consistent timing.

#### Simple I-V Sweep
```python
# Perform complete I-V sweep with progress monitoring
result = smu.run_iv_sweep(
    channel=1,
    start_voltage=-1.0,
    end_voltage=1.0,
    points=21,
    dwell_ms=100,
    monitor_progress=True
)

# Access results
for point in result.data:
    print(f"{point.voltage:.3f}V -> {point.current*1e6:.1f}µA")
```

#### Advanced Sweep Configuration
```python
# Configure sweep parameters individually
smu.set_sweep_start_voltage(1, -0.5)
smu.set_sweep_end_voltage(1, 1.5)
smu.set_sweep_points(1, 100)
smu.set_sweep_dwell_time(1, 50)  # 50ms between points
smu.enable_sweep_auto_output(1)  # Auto enable/disable channel
smu.set_sweep_output_format(1, "JSON")  # CSV or JSON format

# Execute and monitor
smu.execute_sweep(1)

while True:
    status = smu.get_sweep_status(1)
    if status.status == "COMPLETED":
        break
    print(f"Progress: {status.current_point}/{status.total_points}")
    time.sleep(1)

# Get results
data = smu.get_sweep_data_json(1)  # Returns SweepResult object
```

#### Sweep Data Formats

**JSON Format** (includes metadata):
```python
result = smu.get_sweep_data_json(1)
print(f"Config: {result.config.start_voltage}V to {result.config.end_voltage}V")
for point in result.data:
    print(f"{point.voltage:.3f}V, {point.current*1e6:.1f}µA")
```

**CSV Format** (simple data points):
```python
data_points = smu.get_sweep_data_csv(1)
for point in data_points:
    print(f"{point.voltage:.3f}V, {point.current*1e6:.1f}µA")
```

### WiFi Management

#### Network Configuration
```python
# Scan for networks
networks = smu.wifi_scan()
for network in networks:
    print(f"SSID: {network['ssid']}, Signal: {network['rssi']} dBm")

# Configure credentials
smu.set_wifi_credentials("MyNetwork", "MyPassword")
smu.enable_wifi()

# Auto-connect settings
smu.enable_wifi_autoconnect()
auto_enabled = smu.get_wifi_autoconnect_status()
```

#### WiFi Status
```python
status = smu.get_wifi_status()
print(f"Connected: {status.connected}")
if status.connected:
    print(f"SSID: {status.ssid}")
    print(f"IP: {status.ip_address}")
    print(f"Signal: {status.rssi} dBm")
```

### System Information
```python
# Device identification
print(smu.get_identity())

# Temperature monitoring
adc_temp, ch1_temp, ch2_temp = smu.get_temperatures()
print(f"Temperatures: ADC={adc_temp}°C, CH1={ch1_temp}°C, CH2={ch2_temp}°C")

# Time synchronization
import time
smu.set_time(int(time.time() * 1000))  # Unix timestamp in milliseconds
```

## Examples

The `examples/` directory contains comprehensive examples demonstrating various features:

### Basic Examples
- **`basic_usage.py`** - Simple voltage setting and measurement
- **`streaming_example.py`** - Real-time data streaming
- **`current_sweep.py`** - Manual current sweep implementation

### I-V Sweep Examples
- **`usb_iv_sweep.py`** - Manual I-V sweep over USB with progress bars
- **`wifi_iv_sweep.py`** - Manual I-V sweep over WiFi
- **`onboard_iv_sweep.py`** - Hardware-accelerated onboard I-V sweeps
  - Simple sweep with progress monitoring
  - Advanced configuration examples
  - Data format comparison (CSV vs JSON)
  - Sweep abort demonstration
  - I-V curve plotting with matplotlib

### Advanced Examples
- **`advanced_features.py`** - Comprehensive feature demonstration
  - OSR (oversampling) configuration
  - Protection limit settings
  - WiFi management
  - Complete measurement workflows

### Running Examples

1. **Adjust connection parameters** in the example files:
   ```python
   miniSMU_PORT = "COM3"  # Change to your USB port
   # or
   miniSMU_IP = "192.168.1.106"  # Change to your device IP
   ```

2. **Run examples**:
   ```bash
   python examples/basic_usage.py
   python examples/onboard_iv_sweep.py
   python examples/advanced_features.py
   ```

## Data Classes

The library provides structured data classes for complex operations:

### Sweep Operations
```python
from minismu_py import SweepStatus, SweepConfig, SweepDataPoint, SweepResult

# Sweep status monitoring
status = smu.get_sweep_status(1)
print(f"Status: {status.status}")
print(f"Progress: {status.current_point}/{status.total_points}")
print(f"Elapsed: {status.elapsed_ms}ms")

# Sweep results
result = smu.get_sweep_data_json(1)
print(f"Configuration: {result.config}")
print(f"Data points: {len(result.data)}")
```

### WiFi Status
```python
from minismu_py import WifiStatus

status = smu.get_wifi_status()
print(f"Connected: {status.connected}")
print(f"Network: {status.ssid}")
print(f"IP: {status.ip_address}")
print(f"Signal: {status.rssi} dBm")
```

## Error Handling

The library includes comprehensive error handling:

```python
from minismu_py import SMUException

try:
    with SMU(ConnectionType.USB, port="COM3") as smu:
        # Your code here
        pass
except SMUException as e:
    print(f"SMU Error: {e}")
except Exception as e:
    print(f"General Error: {e}")
```

### Common Issues and Solutions

#### Connection Issues
- **USB**: Verify the correct COM port/device path
- **WiFi**: Ensure device is on the same network and reachable
- **Permissions**: On Linux, you may need to add your user to the `dialout` group

#### Firmware Compatibility
- **Onboard I-V Sweeps**: Requires firmware v1.3.4 or later
- **Feature Support**: Older firmware may not support all features

#### Communication Issues
The library automatically handles:
- Chunked USB data transmission
- UTF-8 encoding errors
- JSON corruption in responses
- Network timeouts and reconnection

## API Reference

### Core Classes

#### SMU
The main interface class for miniSMU control.

**Constructor:**
```python
SMU(connection_type, port="/dev/ttyACM0", host="192.168.1.1", tcp_port=3333)
```

**Key Methods:**
- `get_identity()` - Device identification
- `set_mode(channel, mode)` - Configure channel mode
- `set_voltage(channel, voltage)` - Set output voltage
- `set_current(channel, current)` - Set output current
- `measure_voltage_and_current(channel)` - Take measurements
- `enable_channel(channel)` / `disable_channel(channel)` - Output control

### Protection and Precision
- `set_current_protection(channel, limit)` - Current protection limit
- `set_voltage_protection(channel, limit)` - Voltage protection limit
- `set_oversampling_ratio(channel, osr)` - Measurement precision (0-15)

### I-V Sweep Methods
- `run_iv_sweep()` - Complete sweep operation
- `configure_iv_sweep()` - Setup sweep parameters
- `execute_sweep(channel)` - Start sweep execution
- `get_sweep_status(channel)` - Monitor progress
- `get_sweep_data_json(channel)` - Get structured results
- `abort_sweep(channel)` - Stop running sweep

### WiFi Methods
- `wifi_scan()` - Scan for networks
- `set_wifi_credentials(ssid, password)` - Configure network
- `get_wifi_status()` - Connection status
- `enable_wifi_autoconnect()` - Auto-connect control

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

### Development Setup
```bash
git clone https://github.com/Undalogic/minismu_py.git
cd minismu_py
pip install -e .[dev]  # Install with development dependencies
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Documentation**: This README and inline code documentation
- **Examples**: Comprehensive examples in the `examples/` directory
- **Issues**: Report bugs and request features via GitHub Issues
- **Website**: [www.undalogic.com](http://www.undalogic.com)

## Changelog

### v0.2.0
- Added onboard I-V sweep functionality (firmware v1.3.4+)
- Implemented OSR (oversampling ratio) control for precision measurements
- Added current and voltage protection settings
- Enhanced WiFi management with auto-connect features
- Improved USB communication with chunked data and corruption handling
- Added comprehensive examples and documentation

### v0.1.0
- Initial release with basic SMU control
- USB and WiFi connectivity
- Basic measurement and sourcing functions
- Data streaming support
- WiFi configuration