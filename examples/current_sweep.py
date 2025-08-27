from minismu_py import SMU, ConnectionType, SMUException
import time
import csv
import argparse
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

def current_sweep_example(smu: SMU, currents: list, channel: int = 1):
    """Perform a current sweep and measure voltage"""
    try:
        # Configure channel
        smu.set_mode(channel, "FIMV")  # Force Current, Measure Voltage mode
        # smu.set_current_range(channel, "AUTO")
        smu.enable_channel(channel)
        
        results = []
        
        # Create progress bar
        pbar = tqdm(currents, desc="Current Sweep", unit="pts", unit_scale=False)
        for current in pbar:
            smu.set_current(channel, current)
            time.sleep(0.2)  # Allow settling time
            v, i = smu.measure_voltage_and_current(channel)
            results.append({
                'target_current': current,
                'measured_current': i,
                'measured_voltage': v
            })
            # Update progress bar description with current measurements
            pbar.set_description(f"I={i*1e3:.1f}mA, V={v:.3f}V")
        
        return results
            
    finally:
        # Always disable channel after measurement
        smu.disable_channel(channel)


def load_currents_from_csv(filename: str) -> list:
    """Load current values from CSV file"""
    currents = []
    try:
        with open(filename, 'r', newline='') as f:
            reader = csv.reader(f)
            # Skip header if present
            first_row = next(reader, None)
            if first_row:
                try:
                    # Try to parse first row as float
                    currents.append(float(first_row[0]))
                except ValueError:
                    # First row is header, skip it
                    pass
                
                # Read remaining rows
                for row in reader:
                    if row:  # Skip empty rows
                        currents.append(float(row[0]))
        
        print(f"Loaded {len(currents)} current setpoints from {filename}")
        return currents
    except FileNotFoundError:
        print(f"Error: CSV file '{filename}' not found")
        raise
    except ValueError as e:
        print(f"Error parsing CSV file: {e}")
        raise


def generate_linear_currents(start: float, stop: float, step: float) -> list:
    """Generate linearly spaced current values"""
    num_steps = int((stop - start) / step) + 1
    return [start + i * step for i in range(num_steps)]


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Perform current sweep with miniSMU')
    parser.add_argument('--port', '-p', type=str, default='COM50', 
                        help='COM port for miniSMU connection (default: COM50)')
    parser.add_argument('--csv', type=str,
                        help='CSV file containing current setpoints (A). Overrides linear sweep parameters.')
    parser.add_argument('--start', '-s', type=float, default=-0.010,
                        help='Start current in Amps (default: -0.010 A = -10mA)')
    parser.add_argument('--stop', '-e', type=float, default=0.010,
                        help='Stop current in Amps (default: 0.010 A = 10mA)')
    parser.add_argument('--step', '-t', type=float, default=0.001,
                        help='Step current in Amps (default: 0.001 A = 1mA)')
    parser.add_argument('--channel', '-c', type=int, default=1,
                        help='SMU channel to use (default: 1)')
    parser.add_argument('--output', '-o', type=str, default='current_sweep_results.csv',
                        help='Output CSV filename (default: current_sweep_results.csv)')
    
    args = parser.parse_args()
    
    # Determine current setpoints
    if args.csv:
        print(f"Loading current setpoints from CSV: {args.csv}")
        currents = load_currents_from_csv(args.csv)
    else:
        print(f"Generating linear current sweep:")
        print(f"  Start: {args.start*1000:.1f} mA")
        print(f"  Stop: {args.stop*1000:.1f} mA") 
        print(f"  Step: {args.step*1000:.1f} mA")
        currents = generate_linear_currents(args.start, args.stop, args.step)
    
    # Display sweep parameters
    print(f"\nCurrent Sweep Parameters:")
    print(f"  Port: {args.port}")
    print(f"  Number of setpoints: {len(currents)}")
    print(f"  Current range: {min(currents)*1000:.1f} to {max(currents)*1000:.1f} mA")
    print(f"  Channel: {args.channel}")
    print(f"  Output: {args.output}")
    
    try:
        # Create USB manager and connect to SMU
        usb_manager = SMUUSBManager(args.port)
        smu = usb_manager.connect()
        
        # Use context manager to ensure proper cleanup
        with smu:            
            print("\n--- Current Sweep Example (USB) ---")
            sweep_results = current_sweep_example(smu, currents, args.channel)
            
            # Save sweep results to CSV file
            with open(args.output, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['target_current', 'measured_current', 'measured_voltage'])
                writer.writeheader()
                writer.writerows(sweep_results)
            print(f"\nResults saved to {args.output}")
                        
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