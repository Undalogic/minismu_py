#!/usr/bin/env python3
"""
Example demonstrating advanced miniSMU features including:
- OSR (Oversampling Ratio) configuration
- Current and voltage protection settings
- WiFi auto-connect configuration
"""

from minismu_py import SMU, ConnectionType

def demonstrate_advanced_features():
    """Demonstrate the newly implemented advanced features"""
    
    # Connection parameters - adjust as needed
    miniSMU_PORT = "COM41"  # Replace with your miniSMU's USB port
    
    # Connect to SMU
    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        
        print("=== Advanced miniSMU Features Demo ===\n")
        
        # Get device info
        print(f"Device ID: {smu.get_identity()}")
        
        # 1. Configure measurement precision with OSR
        print("\n1. Configuring measurement precision...")
        
        # Set high precision for channel 1 (OSR = 12)
        smu.set_oversampling_ratio(1, 12)
        print("   Channel 1: High precision (OSR=12)")
        
        # Set medium precision for channel 2 (OSR = 8)
        smu.set_oversampling_ratio(2, 8)
        print("   Channel 2: Medium precision (OSR=8)")
        
        # 2. Configure safety protection limits
        print("\n2. Setting up protection limits...")
        
        # Set current protection to 50mA for channel 1
        smu.set_current_protection(1, 0.05)  # 50mA
        print("   Channel 1: Current protection set to 50mA")
        
        # Set voltage protection to 3.3V for channel 1
        smu.set_voltage_protection(1, 3.3)  # 3.3V
        print("   Channel 1: Voltage protection set to 3.3V")
        
        # Configure channel 2 for higher limits
        smu.set_current_protection(2, 0.1)   # 100mA
        smu.set_voltage_protection(2, 5.0)   # 5V
        print("   Channel 2: Current protection set to 100mA, voltage to 5V")
        
        # 3. Configure WiFi settings
        print("\n3. Configuring WiFi settings...")
        
        try:
            # Check current WiFi status
            wifi_status = smu.get_wifi_status()
            print(f"   WiFi connected: {wifi_status.connected}")
            if wifi_status.connected:
                print(f"   SSID: {wifi_status.ssid}")
                print(f"   IP: {wifi_status.ip_address}")
                print(f"   Signal strength: {wifi_status.rssi} dBm")
            
            # Check auto-connect status
            auto_connect = smu.get_wifi_autoconnect_status()
            print(f"   Auto-connect enabled: {auto_connect}")
            
            # Enable auto-connect for convenience
            smu.enable_wifi_autoconnect()
            print("   Auto-connect enabled for future connections")
            
        except Exception as e:
            print(f"   WiFi configuration error: {e}")
        
        # 4. Demonstrate a complete measurement setup
        print("\n4. Complete measurement setup example...")
        
        # Configure channel 1 for precision voltage sourcing
        smu.set_mode(1, "FVMI")  # Force voltage, measure current
        smu.set_voltage(1, 1.2)  # Set 1.2V output
        smu.enable_channel(1)
        print("   Channel 1: Configured for 1.2V precision sourcing")
        
        # Take a high-precision measurement
        voltage, current = smu.measure_voltage_and_current(1)
        print(f"   Measured: {voltage:.6f}V, {current*1000:.3f}mA")
        
        # Configure channel 2 for current sourcing  
        smu.set_mode(2, "FIMV")  # Force current, measure voltage
        smu.set_current(2, 0.01)  # Set 10mA output
        smu.enable_channel(2)
        print("   Channel 2: Configured for 10mA current sourcing")
        
        # Take measurement on channel 2
        voltage, current = smu.measure_voltage_and_current(2)
        print(f"   Measured: {voltage:.3f}V, {current*1000:.3f}mA")
        
        # 5. Safety demonstration
        print("\n5. Safety features active:")
        print("   - Current limited to 50mA (CH1) and 100mA (CH2)")
        print("   - Voltage limited to 3.3V (CH1) and 5V (CH2)")
        print("   - High precision measurements enabled")
        
        # Clean up
        smu.disable_channel(1)
        smu.disable_channel(2)
        print("\n✓ Demo completed successfully!")

if __name__ == "__main__":
    try:
        demonstrate_advanced_features()
    except Exception as e:
        print(f"Demo failed: {e}")
        print("\nNote: Make sure your miniSMU device is connected and accessible.")
        print("You may need to adjust the connection parameters in the script.")
        print("Current settings: COM50 for USB connection")