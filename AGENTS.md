# miniSMU Python Library - AI Context

This file provides context for AI assistants to help write scripts using the miniSMU Python library.

## What is miniSMU?

miniSMU is a compact, dual-channel Source Measure Unit (SMU) for photovoltaic characterization and general electronics testing. It can:
- Force voltage and measure current (FVMI mode)
- Force current and measure voltage (FIMV mode)
- Perform hardware-accelerated I-V sweeps
- Stream real-time measurement data
- Connect via USB or WiFi

## Installation

```bash
pip install minismu-py
```

## Quick Start Template

```python
from minismu_py import SMU, ConnectionType

# USB connection (most common)
with SMU(ConnectionType.USB, port="COM3") as smu:  # Windows
# with SMU(ConnectionType.USB, port="/dev/ttyACM0") as smu:  # Linux/Mac

    print(smu.get_identity())

    # Configure channel 1: Force Voltage, Measure Current
    smu.set_mode(1, "FVMI")
    smu.set_voltage(1, 1.0)  # Set 1V
    smu.set_current_protection(1, 0.1)  # 100mA limit

    smu.enable_channel(1)
    voltage, current = smu.measure_voltage_and_current(1)
    print(f"V: {voltage:.4f} V, I: {current*1e6:.2f} µA")
    smu.disable_channel(1)
```

## Core API Reference

### Connection

```python
from minismu_py import SMU, ConnectionType

# USB connection
smu = SMU(ConnectionType.USB, port="COM3")

# WiFi connection
smu = SMU(ConnectionType.NETWORK, host="192.168.1.100", tcp_port=3333)

# Always use context manager for automatic cleanup
with SMU(ConnectionType.USB, port="COM3") as smu:
    # your code here
```

### Channel Configuration

```python
# Set operating mode
smu.set_mode(channel, "FVMI")  # Force Voltage, Measure Current (most common)
smu.set_mode(channel, "FIMV")  # Force Current, Measure Voltage

# Set output values
smu.set_voltage(channel, voltage_in_volts)  # e.g., 1.5 for 1.5V
smu.set_current(channel, current_in_amps)   # e.g., 0.001 for 1mA

# Enable/disable output
smu.enable_channel(channel)   # channel is 1 or 2
smu.disable_channel(channel)
```

### Measurements

```python
# Single measurements
voltage = smu.measure_voltage(channel)
current = smu.measure_current(channel)

# Combined measurement (more efficient)
voltage, current = smu.measure_voltage_and_current(channel)

# Set measurement precision (0-15, higher = more averaging)
smu.set_oversampling_ratio(channel, 10)  # ~2^10 = 1024 samples averaged
```

### Protection Limits

```python
# Set protection limits (prevents damage to DUT)
smu.set_current_protection(channel, current_in_amps)  # e.g., 0.1 for 100mA
smu.set_voltage_protection(channel, voltage_in_volts)  # e.g., 5.0 for 5V
```

### Current Range Control

miniSMU has 5 current ranges for optimal precision:

| Range | Limit | Best For |
|-------|-------|----------|
| 0 | ±1 µA | Picoamp/nanoamp measurements |
| 1 | ±25 µA | Microamp measurements |
| 2 | ±650 µA | Sub-milliamp precision |
| 3 | ±15 mA | General milliamp work |
| 4 | ±180 mA | High current measurements |

```python
# Auto-range (default) - automatically selects best range
smu.set_autorange(channel, True)

# Manual range selection for consistent measurements
smu.set_autorange(channel, False)
smu.set_current_range(channel, 2)  # Lock to range 2 (±650µA)

# Or set range by expected current
smu.set_current_range_by_limit(channel, 0.0005)  # Auto-select for 500µA max
```

### Hardware I-V Sweeps (Recommended)

Hardware sweeps are faster and more consistent than software loops. Requires firmware v1.3.4+.

```python
from minismu_py import SMU, ConnectionType

with SMU(ConnectionType.USB, port="COM3") as smu:
    # Run a complete I-V sweep
    result = smu.run_iv_sweep(
        channel=1,
        start_voltage=-1.0,    # Start at -1V
        end_voltage=1.0,       # End at +1V
        points=101,            # 101 measurement points
        dwell_ms=50,           # 50ms per point
        monitor_progress=True  # Show progress
    )

    # Access the data
    for point in result.data:
        print(f"{point.voltage:.3f} V, {point.current*1e6:.2f} µA")

    # Or access as lists
    voltages = [p.voltage for p in result.data]
    currents = [p.current for p in result.data]
```

### 4-Wire (Kelvin) Measurements

For accurate low-resistance measurements. Requires firmware v1.4.3+. Uses CH1 for current forcing and CH2 for voltage sensing.

```python
smu.enable_fourwire_mode()

# Now CH1 forces current, CH2 measures voltage (for Kelvin sensing)
smu.set_mode(1, "FIMV")
smu.set_current(1, 0.001)  # Force 1mA
smu.enable_channel(1)

# measure_voltage_and_current returns (CH2 voltage, CH1 current) in 4-wire mode
voltage, current = smu.measure_voltage_and_current(1)
resistance = voltage / current
print(f"Resistance: {resistance:.4f} Ω")

smu.disable_fourwire_mode()  # Restore independent channels
```

### Data Streaming

For real-time continuous monitoring:

```python
smu.set_sample_rate(1, 100)  # 100 Hz sampling
smu.set_mode(1, "FVMI")
smu.set_voltage(1, 1.0)
smu.enable_channel(1)
smu.start_streaming(1)

try:
    while True:
        channel, timestamp, voltage, current = smu.read_streaming_data()
        print(f"t={timestamp}ms: {voltage:.4f}V, {current*1e6:.2f}µA")
except KeyboardInterrupt:
    pass

smu.stop_streaming(1)
smu.disable_channel(1)
```

### WiFi Configuration

```python
# Scan for networks
networks = smu.wifi_scan()
for net in networks:
    print(net)

# Configure and connect
smu.set_wifi_credentials("MyNetwork", "password123")
smu.enable_wifi()
smu.enable_wifi_autoconnect()

# Check status
status = smu.get_wifi_status()
print(f"Connected: {status.connected}, IP: {status.ip_address}")
```

### System Functions

```python
smu.get_identity()          # Device identification string
smu.reset()                 # Reset device
smu.set_led_brightness(50)  # LED brightness 0-100%
smu.get_temperatures()      # Returns (adc_temp, ch1_temp, ch2_temp) in °C
```

## Common Use Cases

### Solar Cell I-V Characterization

```python
from minismu_py import SMU, ConnectionType
import matplotlib.pyplot as plt

with SMU(ConnectionType.USB, port="COM3") as smu:
    # Configure for solar cell measurement
    smu.set_mode(1, "FVMI")
    smu.set_current_protection(1, 0.1)  # 100mA limit
    smu.set_oversampling_ratio(1, 8)    # Good precision

    # Sweep from reverse bias through forward bias
    result = smu.run_iv_sweep(
        channel=1,
        start_voltage=-0.2,  # Slight reverse bias
        end_voltage=0.8,     # Past Voc
        points=101,
        dwell_ms=100
    )

    voltages = [p.voltage for p in result.data]
    currents = [p.current * 1000 for p in result.data]  # Convert to mA

    plt.plot(voltages, currents)
    plt.xlabel("Voltage (V)")
    plt.ylabel("Current (mA)")
    plt.title("Solar Cell I-V Curve")
    plt.grid(True)
    plt.show()
```

### LED Characterization

```python
from minismu_py import SMU, ConnectionType

with SMU(ConnectionType.USB, port="COM3") as smu:
    smu.set_mode(1, "FVMI")
    smu.set_current_protection(1, 0.02)  # 20mA limit for LED

    result = smu.run_iv_sweep(
        channel=1,
        start_voltage=0,
        end_voltage=3.5,  # Typical for white/blue LEDs
        points=71,
        dwell_ms=50
    )

    # Find turn-on voltage (where current exceeds 1mA)
    for point in result.data:
        if point.current > 0.001:
            print(f"LED turn-on voltage: ~{point.voltage:.2f} V")
            break
```

### Resistance Measurement

```python
from minismu_py import SMU, ConnectionType

with SMU(ConnectionType.USB, port="COM3") as smu:
    smu.set_mode(1, "FIMV")  # Force current, measure voltage
    smu.set_current(1, 0.001)  # Force 1mA
    smu.set_voltage_protection(1, 10)  # 10V limit

    smu.enable_channel(1)
    voltage, current = smu.measure_voltage_and_current(1)
    resistance = voltage / current
    print(f"Resistance: {resistance:.2f} Ω")
    smu.disable_channel(1)
```

### Time-Series Monitoring

```python
from minismu_py import SMU, ConnectionType
import time

with SMU(ConnectionType.USB, port="COM3") as smu:
    smu.set_mode(1, "FVMI")
    smu.set_voltage(1, 1.0)
    smu.enable_channel(1)

    data = []
    start_time = time.time()

    for _ in range(100):  # 100 measurements
        v, i = smu.measure_voltage_and_current(1)
        t = time.time() - start_time
        data.append((t, v, i))
        time.sleep(0.1)  # 10 Hz sampling

    smu.disable_channel(1)

    # Process data...
```

## Important Notes

1. **Always use context managers** (`with` statement) to ensure proper cleanup
2. **Set protection limits** before enabling channels to protect your device under test
3. **Disable channels** when not measuring to avoid heating/damage
4. **Channel numbers are 1 and 2**, not 0 and 1
5. **Current values are in Amps** - use `* 1e3` for mA, `* 1e6` for µA
6. **Voltage values are in Volts**
7. **Hardware sweeps require firmware v1.3.4+** - check with `smu.get_identity()`
8. **4-wire mode requires firmware v1.4.3+**

## Firmware Updates

If you need newer features, firmware updates are available at:
https://www.undalogic.com/minismu/firmware-update

## Data Classes Reference

```python
from minismu_py import (
    SMU,
    ConnectionType,      # USB or NETWORK
    SMUException,        # Custom exception for errors
    WifiStatus,          # WiFi connection info
    SweepStatus,         # Sweep progress info
    SweepConfig,         # Sweep configuration
    SweepDataPoint,      # Individual measurement (timestamp, voltage, current)
    SweepResult,         # Complete sweep results
    CURRENT_RANGE_LIMITS # Dict of range limits: {0: 1e-6, 1: 25e-6, ...}
)
```

## Troubleshooting

- **Connection errors**: Check the correct COM port (Windows) or /dev/ttyACM* (Linux)
- **Timeout errors**: Increase timeout or check device responsiveness
- **Unexpected currents**: Verify current range and protection settings
- **WiFi issues**: Ensure device is in range and credentials are correct
