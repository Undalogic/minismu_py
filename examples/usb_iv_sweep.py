from minismu_py import SMU, ConnectionType, SMUException
import time
import csv
from typing import Optional
from tqdm import tqdm

class SMUUSBManager:
    """Helper class to manage USB connection to SMU"""
    def __init__(self, port: str = "/dev/ttyACM0"):
        self.port = port
        self.smu: Optional[SMU] = None
    
    def connect(self) -> SMU:
        """Connect to SMU and verify connection"""
        try:
            self.smu = SMU(ConnectionType.USB, port=self.port)
            identity = self.smu.get_identity()
            print(f"Connected to: {identity}")
            return self.smu
        except SMUException as e:
            print(f"Failed to connect to SMU: {e}")
            raise

def voltage_sweep_example(smu: SMU, channel: int = 1):
    """Perform a voltage sweep and measure current"""
    try:
        # Configure channel
        smu.set_mode(channel, "FVMI")  # Force Voltage, Measure Current mode
        smu.set_voltage_range(channel, "AUTO")
        smu.enable_channel(channel)
        
        # Perform voltage sweep from -1V to 0.7V
        voltages = [v/100 for v in range(-100, 70, 2)]  # -1V to 0.7V in 20mV steps
        results = []
        
        # Create progress bar
        pbar = tqdm(voltages, desc="Voltage Sweep", unit="pts", unit_scale=False)
        for voltage in pbar:
            smu.set_voltage(channel, voltage)
            time.sleep(0.2)  # Allow settling time
            v, i = smu.measure_voltage_and_current(channel)
            results.append({
                'target_voltage': voltage,
                'measured_voltage': v,
                'measured_current': i
            })
            # Update progress bar description with current measurements
            pbar.set_description(f"V={v:.3f}V, I={i*1e6:.1f}µA")
        
        return results
            
    finally:
        # Always disable channel after measurement
        smu.disable_channel(channel)


def main():
    # Connection parameters
    miniSMU_PORT = "COM41"  # Replace with your miniSMU's USB port
    
    try:
        # Create USB manager and connect to SMU
        usb_manager = SMUUSBManager(miniSMU_PORT)
        smu = usb_manager.connect()
        
        # Use context manager to ensure proper cleanup
        with smu:            
            print("\n--- Voltage Sweep Example (USB) ---")
            sweep_results = voltage_sweep_example(smu, channel=1)
            
            # Save sweep results to CSV file
            with open('voltage_sweep_results_usb.csv', 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['target_voltage', 'measured_voltage', 'measured_current'])
                writer.writeheader()
                writer.writerows(sweep_results)
            print("\nResults saved to voltage_sweep_results_usb.csv")
                        
    except SMUException as e:
        print(f"SMU Error: {e}")
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        print("\nExample completed")

if __name__ == "__main__":
    main() 