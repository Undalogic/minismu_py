#!/usr/bin/env python3
"""
Example demonstrating miniSMU 4-wire (Kelvin) measurement mode with I-V sweep

This example shows how to use 4-wire measurement mode to eliminate lead resistance
errors in high-current or low-resistance DUT measurements.

4-Wire Mode Operation:
- CH1 acts as the source/force channel (sources voltage/current)
- CH2 acts as the sense channel (high-impedance voltage measurement)
- Measurements return CH1 current + CH2 voltage (true DUT voltage)

Hardware Connection (Kelvin):
    CH1 BNC Center ----[Force]---->----+---- DUT+
                               |
    CH2 BNC Center ----[Sense]-------->+

    CH1 BNC Shield ----[Force]----<----+---- DUT-
                               |
    CH2 BNC Shield ----[Sense]-------->+

This eliminates voltage drop errors from test leads and contact resistance.

Requirements:
- miniSMU firmware with 4-wire mode support (v1.4.0+)
- Both channels available (CH2 will be used for sensing)
"""

import time
import csv
from minismu_py import SMU, ConnectionType, SMUException

# Connection parameters - adjust as needed
miniSMU_PORT = "COM41"  # Replace with your miniSMU's USB port


def fourwire_basic_measurement():
    """Basic 4-wire measurement example"""

    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("=== 4-Wire Basic Measurement Example ===\n")
        print(f"Device: {smu.get_identity()}")

        # Check initial 4-wire mode status
        print(f"4-wire mode initially: {'Enabled' if smu.get_fourwire_mode() else 'Disabled'}")

        try:
            # Enable 4-wire mode
            print("\nEnabling 4-wire measurement mode...")
            smu.enable_fourwire_mode()
            print(f"4-wire mode now: {'Enabled' if smu.get_fourwire_mode() else 'Disabled'}")

            # Configure CH1 for voltage sourcing
            smu.set_mode(1, "FVMI")  # Force voltage, measure current
            smu.set_voltage(1, 1.0)  # Set 1V

            # Enable output (this enables both CH1 and CH2 in 4-wire mode)
            print("\nEnabling output (both channels)...")
            smu.enable_channel(1)

            # Allow settling time
            time.sleep(0.5)

            # Measure - returns CH1 current + CH2 voltage (true DUT voltage)
            voltage, current = smu.measure_voltage_and_current(1)
            print(f"\n4-Wire Measurement Results:")
            print(f"  Voltage (from CH2 sense): {voltage:.6f} V")
            print(f"  Current (from CH1 force): {current*1e6:.3f} uA")

            if current != 0:
                resistance = voltage / current
                print(f"  Calculated resistance: {resistance:.3f} Ohms")

        finally:
            # Always clean up
            print("\nDisabling output...")
            smu.disable_channel(1)

            print("Disabling 4-wire mode...")
            smu.disable_fourwire_mode()
            print(f"4-wire mode: {'Enabled' if smu.get_fourwire_mode() else 'Disabled'}")


def fourwire_iv_sweep():
    """4-wire I-V sweep example with lead resistance compensation"""

    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("\n=== 4-Wire I-V Sweep Example ===\n")
        print(f"Device: {smu.get_identity()}")

        try:
            # Enable 4-wire mode first
            print("Enabling 4-wire mode...")
            smu.enable_fourwire_mode()

            # Configure CH1 for voltage sourcing
            smu.set_mode(1, "FVMI")

            # Perform sweep using onboard sweep function
            # In 4-wire mode, the sweep will use CH2 for voltage sensing
            print("\nRunning I-V sweep in 4-wire mode...")
            print("Sweep: 0V to 1V, 21 points, 100ms dwell\n")

            result = smu.run_iv_sweep(
                channel=1,
                start_voltage=0.0,
                end_voltage=1.0,
                points=21,
                dwell_ms=100,
                auto_enable=True,
                output_format="JSON",
                monitor_progress=True
            )

            # Display results
            print(f"\nSweep completed! {len(result.data)} data points collected")
            print("\nData (first 5 points):")
            print("  Voltage (V)  |  Current (uA)")
            print("  -------------|---------------")
            for point in result.data[:5]:
                print(f"  {point.voltage:12.6f} | {point.current*1e6:12.3f}")

            if len(result.data) > 5:
                print(f"  ... and {len(result.data) - 5} more points")

            # Save to CSV
            output_file = "fourwire_iv_sweep_results.csv"
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp_ms', 'voltage_V', 'current_A'])
                for point in result.data:
                    writer.writerow([point.timestamp, point.voltage, point.current])
            print(f"\nResults saved to {output_file}")

            return result

        finally:
            print("\nDisabling 4-wire mode...")
            smu.disable_fourwire_mode()


def fourwire_manual_sweep():
    """Manual point-by-point sweep in 4-wire mode for maximum control"""

    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("\n=== 4-Wire Manual Sweep Example ===\n")
        print(f"Device: {smu.get_identity()}")

        results = []

        try:
            # Enable 4-wire mode
            print("Enabling 4-wire mode...")
            smu.enable_fourwire_mode()

            # Configure CH1
            smu.set_mode(1, "FVMI")
            smu.set_voltage(1, 0.0)  # Start at 0V
            smu.enable_channel(1)

            # Define sweep parameters
            start_v = -0.5
            end_v = 0.5
            num_points = 11
            step_v = (end_v - start_v) / (num_points - 1)
            dwell_s = 0.1  # 100ms settling time

            print(f"\nManual sweep: {start_v}V to {end_v}V, {num_points} points")
            print("\nMeasuring...")

            for i in range(num_points):
                voltage_setpoint = start_v + i * step_v

                # Set voltage
                smu.set_voltage(1, voltage_setpoint)

                # Wait for settling
                time.sleep(dwell_s)

                # Measure (4-wire: CH1 current + CH2 voltage)
                voltage, current = smu.measure_voltage_and_current(1)

                results.append({
                    'setpoint': voltage_setpoint,
                    'voltage': voltage,
                    'current': current
                })

                print(f"  Point {i+1:2d}/{num_points}: Set={voltage_setpoint:+.3f}V, "
                      f"Meas={voltage:+.6f}V, I={current*1e6:+.3f}uA")

            print(f"\nSweep complete! {len(results)} points collected")

            # Calculate and display any voltage error (setpoint vs measured)
            print("\nVoltage accuracy analysis:")
            errors = [abs(r['setpoint'] - r['voltage']) * 1000 for r in results]  # mV
            print(f"  Max error: {max(errors):.3f} mV")
            print(f"  Avg error: {sum(errors)/len(errors):.3f} mV")

            return results

        finally:
            smu.disable_channel(1)
            smu.disable_fourwire_mode()


def compare_2wire_vs_4wire():
    """Compare 2-wire and 4-wire measurements to show lead compensation"""

    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("\n=== 2-Wire vs 4-Wire Comparison ===\n")
        print(f"Device: {smu.get_identity()}")
        print("\nThis example compares measurements with and without 4-wire mode.")
        print("With significant lead resistance, 4-wire should show more accurate DUT voltage.\n")

        test_voltage = 1.0
        results_2wire = []
        results_4wire = []

        # Configure CH1
        smu.set_mode(1, "FVMI")
        smu.set_voltage(1, test_voltage)

        # --- 2-Wire Measurement ---
        print(f"2-Wire measurement at {test_voltage}V setpoint:")
        smu.enable_channel(1)
        time.sleep(0.5)

        for i in range(5):
            v, i_meas = smu.measure_voltage_and_current(1)
            results_2wire.append((v, i_meas))
            time.sleep(0.1)

        smu.disable_channel(1)

        avg_v_2wire = sum(r[0] for r in results_2wire) / len(results_2wire)
        avg_i_2wire = sum(r[1] for r in results_2wire) / len(results_2wire)
        print(f"  Avg Voltage: {avg_v_2wire:.6f} V")
        print(f"  Avg Current: {avg_i_2wire*1e6:.3f} uA")

        # --- 4-Wire Measurement ---
        print(f"\n4-Wire measurement at {test_voltage}V setpoint:")

        try:
            smu.enable_fourwire_mode()
            smu.set_voltage(1, test_voltage)
            smu.enable_channel(1)
            time.sleep(0.5)

            for i in range(5):
                v, i_meas = smu.measure_voltage_and_current(1)
                results_4wire.append((v, i_meas))
                time.sleep(0.1)

            avg_v_4wire = sum(r[0] for r in results_4wire) / len(results_4wire)
            avg_i_4wire = sum(r[1] for r in results_4wire) / len(results_4wire)
            print(f"  Avg Voltage: {avg_v_4wire:.6f} V")
            print(f"  Avg Current: {avg_i_4wire*1e6:.3f} uA")

        finally:
            smu.disable_channel(1)
            smu.disable_fourwire_mode()

        # --- Comparison ---
        print("\n--- Comparison ---")
        voltage_diff = (avg_v_4wire - avg_v_2wire) * 1000  # mV
        print(f"Voltage difference (4W - 2W): {voltage_diff:+.3f} mV")

        if avg_i_2wire != 0 and avg_i_4wire != 0:
            r_2wire = avg_v_2wire / avg_i_2wire
            r_4wire = avg_v_4wire / avg_i_4wire
            print(f"Calculated R (2-wire): {r_2wire:.3f} Ohms")
            print(f"Calculated R (4-wire): {r_4wire:.3f} Ohms")
            print(f"Lead resistance estimate: {abs(r_2wire - r_4wire):.3f} Ohms")


def error_handling_example():
    """Demonstrate 4-wire mode error handling"""

    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("\n=== 4-Wire Error Handling Example ===\n")

        # Example 1: Try to enable during streaming (should fail)
        print("Test 1: Enable 4-wire while streaming (should fail)")
        try:
            smu.start_streaming(1)
            time.sleep(0.1)
            smu.enable_fourwire_mode()
            print("  Unexpected: Should have raised an exception")
        except SMUException as e:
            print(f"  Expected error: {e}")
        finally:
            smu.stop_streaming(1)

        # Example 2: Query mode when not enabled
        print("\nTest 2: Query 4-wire status")
        status = smu.get_fourwire_mode()
        print(f"  4-wire mode enabled: {status}")

        # Example 3: Enable and disable correctly
        print("\nTest 3: Normal enable/disable cycle")
        try:
            smu.enable_fourwire_mode()
            print(f"  After enable: {smu.get_fourwire_mode()}")
            smu.disable_fourwire_mode()
            print(f"  After disable: {smu.get_fourwire_mode()}")
        except SMUException as e:
            print(f"  Error: {e}")

        print("\nError handling tests complete!")


def main():
    """Run all 4-wire measurement examples"""

    print("=" * 60)
    print("miniSMU 4-Wire (Kelvin) Measurement Examples")
    print("=" * 60)
    print("\nNote: Ensure CH2 sense leads are connected to the DUT")
    print("for accurate 4-wire measurements.\n")

    try:
        # Run examples
        fourwire_basic_measurement()
        fourwire_iv_sweep()
        fourwire_manual_sweep()
        compare_2wire_vs_4wire()
        error_handling_example()

        print("\n" + "=" * 60)
        print("All 4-wire examples completed successfully!")
        print("=" * 60)

    except SMUException as e:
        print(f"\nSMU Error: {e}")
        print("\nTroubleshooting:")
        print("- Ensure miniSMU firmware supports 4-wire mode")
        print("- Check that no streaming or sweep is active before enabling")
        print("- Verify USB connection and port settings")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
