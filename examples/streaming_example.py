from minismu_py import SMU, ConnectionType, SMUException
import time
import csv
from typing import Optional
from tqdm import tqdm
import numpy as np
from datetime import datetime

class SMUStreamingManager:
    """Helper class to manage SMU streaming operations"""
    def __init__(self, connection_type: ConnectionType, **kwargs):
        self.connection_type = connection_type
        self.connection_params = kwargs
        self.smu: Optional[SMU] = None
    
    def connect(self) -> SMU:
        """Connect to SMU and verify connection"""
        try:
            self.smu = SMU(self.connection_type, **self.connection_params)
            identity = self.smu.get_identity()
            print(f"Connected to: {identity}")
            return self.smu
        except SMUException as e:
            print(f"Failed to connect to SMU: {e}")
            raise

def streaming_example(smu: SMU, channel: int = 1, duration: float = 10.0, 
                     sample_rate: float = 100.0, voltage: float = 3.3):
    """
    Demonstrate streaming functionality of the SMU
    
    Args:
        smu: SMU instance
        channel: Channel number (1 or 2)
        duration: Duration of streaming in seconds
        sample_rate: Sample rate in Hz
        voltage: Voltage to apply during streaming
    """
    try:
        # Configure channel
        smu.set_mode(channel, "FVMI")  # Force Voltage, Measure Current mode
        smu.set_voltage_range(channel, "AUTO")
        smu.enable_channel(channel)
        smu.set_voltage(channel, voltage)
        
        # Configure streaming
        smu.set_sample_rate(channel, sample_rate)
        
        # Set miniSMU's internal time for timestamping
        current_time = int(time.time() * 1000)  # Convert to milliseconds
        smu.set_time(current_time)
        
        # Calculate number of samples
        num_samples = int(duration * sample_rate)
        
        # Create progress bar
        pbar = tqdm(total=num_samples, desc="Streaming Data", unit="samples")
        
        # Prepare data storage
        timestamps = []
        voltages = []
        currents = []
        
        # Start streaming
        print("Starting streaming...")
        response = smu.start_streaming(channel)
        
        # Collect data
        while len(timestamps) < num_samples:
            try:
                # Read streaming data packet
                data_channel, t, v, i = smu.read_streaming_data()
                
                # Only process data from the requested channel
                if data_channel == channel:
                    timestamps.append(t)
                    voltages.append(v)
                    currents.append(i)
                    
                    # Update progress bar
                    pbar.update(1)
                    pbar.set_description(f"V={v:.3f}V, I={i*1e6:.1f}µA")
                
            except SMUException as e:
                print(f"\nError reading streaming data: {e}")
                break
        
        # Stop streaming
        print("Stopping streaming...")
        response = smu.stop_streaming(channel)
        # if response != "OK":
        #     raise SMUException(f"Unexpected response from stop_streaming: {response}")
            
        pbar.close()
        
        # Calculate statistics
        v_mean = np.mean(voltages)
        v_std = np.std(voltages)
        i_mean = np.mean(currents)
        i_std = np.std(currents)
        
        print("\nStreaming Statistics:")
        print(f"Voltage: {v_mean:.3f}V ± {v_std:.3f}V")
        print(f"Current: {i_mean*1e6:.1f}µA ± {i_std*1e6:.1f}µA")
        
        # Save data to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'streaming_data_{timestamp}.csv'
        
        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Channel', 'Timestamp (s)', 'Voltage (V)', 'Current (A)'])
            for t, v, i in zip(timestamps, voltages, currents):
                writer.writerow([channel, t, v, i])
        
        print(f"\nData saved to {filename}")
        return timestamps, voltages, currents
            
    finally:
        # Always disable channel after measurement
        smu.disable_channel(channel)
        smu.stop_streaming(channel)

def main():
    # Connection parameters
    miniSMU_PORT = "COM50"  # Replace with your miniSMU's USB port
    
    try:
        # Create USB manager and connect to SMU
        usb_manager = SMUStreamingManager(ConnectionType.USB, port=miniSMU_PORT)
        smu = usb_manager.connect()
        
        # Use context manager to ensure proper cleanup
        with smu:            
            print("\n--- Streaming Example ---")
            print("This example will:")
            print("1. Configure the SMU for streaming")
            print("2. Apply 0.5V to channel 1")
            print("3. Stream voltage and current data for 10 seconds")
            print("4. Save the data to a CSV file")
            print("5. Display basic statistics")
            
            # Perform streaming measurement
            timestamps, voltages, currents = streaming_example(
                smu, 
                channel=1,
                duration=10.0,  # 10 seconds of data
                sample_rate=100.0,  # 100 Hz sampling
                voltage=0.5  # Apply 0.5V
            )
                        
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