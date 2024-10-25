# SMU Interface

Python interface library for Undalogic SMU devices. Supports both USB and network connections for controlling and measuring with SMU devices.

## Installation

```bash
pip install smu-interface
```

## Quick Start

```python
from smu_interface import SMU, ConnectionType

# Connect to SMU via USB
smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")

# Basic device operations
print(smu.get_identity())

# Configure channel 1
smu.set_mode(1, "FVMI")  # Set to FVMI mode
smu.enable_channel(1)
smu.set_voltage(1, 3.3)  # Set to 3.3V

# Take measurements
voltage, current = smu.measure_voltage_and_current(1)
print(f"Voltage: {voltage}V, Current: {current}A")

# Close connection
smu.close()
```

## Features

- USB and network connection support
- Comprehensive measurement and source control
- Data streaming capabilities
- System configuration
- WiFi configuration and management
- Type hints for better IDE support
- Context manager support

## Documentation

For full documentation, visit [docs link].

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
