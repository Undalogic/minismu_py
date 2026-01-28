"""
Example: Manual Current Range Control

This example demonstrates how to disable automatic current range switching
and manually select a specific current measurement range. This is useful when:
- You need consistent range for comparative measurements
- You want to optimise resolution for a known current level
- You need to avoid range switching transients during measurements

Available current ranges:
    Range 0: +/- 1 uA
    Range 1: +/- 25 uA
    Range 2: +/- 650 uA
    Range 3: +/- 15 mA
    Range 4: +/- 180 mA
"""

from minismu_py import SMU, ConnectionType, CURRENT_RANGE_LIMITS
import time


def format_current_limit(limit_amps):
    """Format a current limit value for display."""
    if limit_amps < 1e-3:
        return f"{limit_amps * 1e6:.0f} uA"
    else:
        return f"{limit_amps * 1e3:.0f} mA"


def print_range_info():
    """Print all available current ranges."""
    print("Available current ranges:")
    for idx, limit in CURRENT_RANGE_LIMITS.items():
        print(f"  Range {idx}: +/- {format_current_limit(limit)}")
    print()


def example_manual_range_selection(smu):
    """Demonstrate manual range selection by index."""
    print("=" * 50)
    print("Example 1: Manual Range Selection by Index")
    print("=" * 50)

    # Disable autoranging first
    print("Disabling autoranging on channel 1...")
    smu.set_autorange(1, False)

    # Set to range 2 (650 uA) for precise low-current measurements
    selected_range = 2
    range_limit = smu.get_current_range_limit(selected_range)
    print(f"Setting current range to {selected_range} (+/- {format_current_limit(range_limit)})...")
    smu.set_current_range(1, selected_range)

    # Take a measurement
    smu.set_voltage(1, 1.0)
    time.sleep(0.1)
    voltage, current = smu.measure_voltage_and_current(1)
    print(f"Measurement: {voltage:.4f} V, {current * 1e6:.3f} uA")
    print()


def example_range_by_current_limit(smu):
    """Demonstrate automatic range selection based on expected current."""
    print("=" * 50)
    print("Example 2: Range Selection by Expected Current")
    print("=" * 50)

    # Scenario: We expect currents up to 10 mA
    expected_max_current = 10e-3  # 10 mA
    print(f"Expected maximum current: {format_current_limit(expected_max_current)}")

    # This will automatically:
    # 1. Disable autoranging
    # 2. Select the smallest range that fits (range 3: 15 mA)
    # 3. Return the selected range index
    selected_range = smu.set_current_range_by_limit(1, expected_max_current)
    range_limit = smu.get_current_range_limit(selected_range)
    print(f"Selected range: {selected_range} (limit: +/- {format_current_limit(range_limit)})")

    # Another scenario: measuring microamp-level currents
    print()
    expected_max_current = 20e-6  # 20 uA
    print(f"Expected maximum current: {format_current_limit(expected_max_current)}")

    selected_range = smu.set_current_range_by_limit(1, expected_max_current)
    range_limit = smu.get_current_range_limit(selected_range)
    print(f"Selected range: {selected_range} (limit: +/- {format_current_limit(range_limit)})")
    print()


def example_restore_autorange(smu):
    """Demonstrate re-enabling autoranging."""
    print("=" * 50)
    print("Example 3: Re-enabling Autoranging")
    print("=" * 50)

    print("Re-enabling autoranging on channel 1...")
    smu.set_autorange(1, True)
    print("Autoranging is now enabled - the miniSMU will automatically")
    print("select the optimal range based on measured current.")
    print()


def main():
    print_range_info()

    # Create SMU instance with USB connection
    # Change the port to match your system (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux)
    with SMU(ConnectionType.USB, port="COM4") as smu:
        print(f"Connected to: {smu.get_identity()}")
        print()

        # Configure channel 1 for voltage sourcing
        smu.set_mode(1, "FVMI")
        smu.set_voltage_range(1, "AUTO")
        smu.enable_channel(1)

        try:
            # Run examples
            example_manual_range_selection(smu)
            example_range_by_current_limit(smu)
            example_restore_autorange(smu)

        finally:
            # Clean up: disable channel and restore autoranging
            smu.set_voltage(1, 0)
            smu.disable_channel(1)
            smu.set_autorange(1, True)
            print("Cleanup complete.")


if __name__ == "__main__":
    main()
