from minismu_py import SMU, ConnectionType
import time

def main():
    # Create SMU instance with USB connection
    with SMU(ConnectionType.USB, port="COM50") as smu:
        # Print device information
        print("Device Info:", smu.get_identity())
        
        # Configure channel 1
        smu.set_mode(1, "FVMI")
        smu.set_voltage_range(1, "AUTO")
        smu.enable_channel(1)
        
        # Set voltage on channel 1 to 0.5V
        smu_channel = 1
        set_voltage = 0.5
        smu.set_voltage(smu_channel, set_voltage)
        time.sleep(0.1)  # Allow settling time
        
        # Take measurements
        voltage, current = smu.measure_voltage_and_current(1)
        print(f"Voltage: {voltage:.6f}V")
        print(f"Current: {current:.6f}A")

        # Disable channel 1
        smu.disable_channel(1)
        
        # Temperature monitoring
        adc_temp, ch1_temp, ch2_temp = smu.get_temperatures()
        print(f"Temperatures:")
        print(f"  ADC: {adc_temp:.1f}°C")
        print(f"  Channel 1: {ch1_temp:.1f}°C")
        print(f"  Channel 2: {ch2_temp:.1f}°C")

if __name__ == "__main__":
    main()
