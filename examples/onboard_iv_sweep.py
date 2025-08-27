#!/usr/bin/env python3
"""
Example demonstrating miniSMU onboard I-V sweep functionality

This example shows how to use the built-in I-V sweep features of the miniSMU MS01
which requires firmware version 1.3.4 or later.

Features demonstrated:
- Simple I-V sweep with progress monitoring
- Advanced sweep configuration
- Data format comparison (CSV vs JSON)
- Multiple sweep configurations
- Error handling and sweep abort
"""

import time
import matplotlib.pyplot as plt
from minismu_py import SMU, ConnectionType

# Connection parameters - adjust as needed  
miniSMU_PORT = "COM41"  # Replace with your miniSMU's USB port

def simple_iv_sweep_example():
    """Basic I-V sweep example with progress monitoring"""
   
    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("=== Simple I-V Sweep Example ===\n")
        
        print(f"Device: {smu.get_identity()}")
        
        # Configure the SMU for voltage sourcing
        smu.set_mode(1, "FVMI")  # Force voltage, measure current
        
        # Perform a simple I-V sweep with progress monitoring
        print("\nRunning I-V sweep from -1V to +1V with 21 points...")
        
        # This will automatically configure, execute, and retrieve data
        result = smu.run_iv_sweep(
            channel=1,
            start_voltage=-1.0,
            end_voltage=1.0,
            points=21,
            dwell_ms=100,  # 100ms between points
            auto_enable=True,  # Automatically enable/disable output
            output_format="JSON",  # Get structured data
            monitor_progress=True  # Show progress updates
        )
        
        # Display results
        print(f"\nSweep completed! Collected {len(result.data)} data points")
        print(f"Sweep configuration:")
        print(f"  Start: {result.config.start_voltage}V")
        print(f"  End: {result.config.end_voltage}V") 
        print(f"  Points: {result.config.points}")
        print(f"  Dwell: {result.config.dwell_ms}ms")
        
        # Show first few data points
        print(f"\nFirst 3 data points:")
        for i, point in enumerate(result.data[:3]):
            print(f"  Point {i+1}: {point.voltage:.3f}V, {point.current*1e6:.1f}µA")

def advanced_iv_sweep_example():
    """Advanced I-V sweep configuration example"""    
    
    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("\n=== Advanced I-V Sweep Configuration ===\n")
        
        channel = 1
        
        # Step 1: Configure sweep parameters individually
        print("Configuring sweep parameters...")
        smu.set_sweep_start_voltage(channel, -0.5)
        smu.set_sweep_end_voltage(channel, 1.5)  
        smu.set_sweep_points(channel, 50)
        smu.set_sweep_dwell_time(channel, 75)
        smu.enable_sweep_auto_output(channel)
        smu.set_sweep_output_format(channel, "CSV")
        
        # Step 2: Check configuration
        auto_status = smu.get_sweep_auto_output_status(channel)
        output_format = smu.get_sweep_output_format(channel)
        print(f"Auto output control: {'Enabled' if auto_status else 'Disabled'}")
        print(f"Output format: {output_format}")
        
        # Step 3: Execute sweep
        print("\nExecuting sweep...")
        smu.execute_sweep(channel)
        
        # Step 4: Monitor progress manually
        print("Monitoring sweep progress...")
        while True:
            status = smu.get_sweep_status(channel)
            
            if status.status == "RUNNING":
                progress = (status.current_point / status.total_points) * 100
                elapsed_sec = status.elapsed_ms / 1000
                remaining_sec = status.estimated_remaining_ms / 1000
                print(f"  {progress:.1f}% complete ({status.current_point}/{status.total_points}) - "
                      f"Elapsed: {elapsed_sec:.1f}s, Remaining: ~{remaining_sec:.1f}s")
                time.sleep(1)
            elif status.status == "COMPLETED":
                print("  Sweep completed!")
                break
            elif status.status == "ABORTED":
                print("  Sweep was aborted!")
                return
            else:
                time.sleep(0.5)
        
        # Step 5: Retrieve data in CSV format
        data_points = smu.get_sweep_data_csv(channel)
        print(f"\nRetrieved {len(data_points)} data points in CSV format")
        
        # Display voltage range and current range
        voltages = [p.voltage for p in data_points]
        currents = [p.current for p in data_points]
        print(f"Voltage range: {min(voltages):.3f}V to {max(voltages):.3f}V")
        print(f"Current range: {min(currents)*1e6:.1f}µA to {max(currents)*1e6:.1f}µA")

def format_comparison_example():
    """Compare CSV vs JSON output formats"""
    
    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("\n=== Output Format Comparison ===\n")
        
        channel = 1
        
        # Configure a small sweep for comparison
        smu.configure_iv_sweep(
            channel=channel,
            start_voltage=0.0,
            end_voltage=1.0,
            points=5,  # Small number for clear comparison
            dwell_ms=50,
            auto_enable=True,
            output_format="CSV"
        )
        
        # Run sweep
        print("Running sweep for format comparison...")
        smu.execute_sweep(channel)
        
        # Wait for completion
        while True:
            status = smu.get_sweep_status(channel)
            if status.status in ["COMPLETED", "ABORTED"]:
                break
            time.sleep(0.1)
        
        if status.status == "COMPLETED":
            # Get raw data in both formats
            print("\n--- Raw CSV Format ---")
            csv_raw = smu.get_sweep_data_raw(channel)
            print(csv_raw[:200] + "..." if len(csv_raw) > 200 else csv_raw)
            
            # Switch to JSON and get raw data
            smu.set_sweep_output_format(channel, "JSON")
            print("\n--- Raw JSON Format ---")
            json_raw = smu.get_sweep_data_raw(channel)
            print(json_raw[:300] + "..." if len(json_raw) > 300 else json_raw)
            
            # Get parsed data
            csv_data = smu.get_sweep_data_csv(channel)
            json_data = smu.get_sweep_data_json(channel)
            
            print(f"\n--- Parsed Data Comparison ---")
            print(f"CSV format returned {len(csv_data)} data points")
            print(f"JSON format returned {len(json_data.data)} data points with config metadata")
            print(f"JSON config: {json_data.config.start_voltage}V to {json_data.config.end_voltage}V")

def sweep_abort_example():
    """Demonstrate sweep abort functionality"""
      
    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("\n=== Sweep Abort Example ===\n")
        
        channel = 1
        
        # Configure a longer sweep so we have time to abort it
        print("Configuring long sweep (10 seconds) for abort demonstration...")
        smu.configure_iv_sweep(
            channel=channel,
            start_voltage=-1.0,
            end_voltage=1.0,
            points=100,
            dwell_ms=100,  # 10 seconds total
            auto_enable=True
        )
        
        # Start sweep
        print("Starting sweep...")
        smu.execute_sweep(channel)
        
        # Let it run for a few seconds
        print("Letting sweep run for 3 seconds...")
        time.sleep(3)
        
        # Check status
        status = smu.get_sweep_status(channel)
        print(f"Current status: {status.status}, point {status.current_point}/{status.total_points}")
        
        # Abort the sweep
        print("Aborting sweep...")
        smu.abort_sweep(channel)
        
        # Check final status
        time.sleep(0.5)
        final_status = smu.get_sweep_status(channel)
        print(f"Final status: {final_status.status}")
        print(f"Sweep stopped at point {final_status.current_point} of {final_status.total_points}")

def plot_iv_curve_example():
    """Run sweep and plot the I-V curve"""
        
    with SMU(ConnectionType.USB, port=miniSMU_PORT) as smu:
        print("\n=== I-V Curve Plotting Example ===\n")
        
        # Run a sweep suitable for plotting
        print("Running sweep for I-V curve...")
        result = smu.run_iv_sweep(
            channel=1,
            start_voltage=-1.0,
            end_voltage=1.0,
            points=41,
            dwell_ms=50,
            output_format="JSON",
            monitor_progress=False
        )
        
        # Extract data for plotting
        voltages = [p.voltage for p in result.data]
        currents = [p.current * 1e6 for p in result.data]  # Convert to µA
        
        # Create plot
        plt.figure(figsize=(10, 6))
        plt.plot(voltages, currents, 'b.-', linewidth=2, markersize=4)
        plt.xlabel('Voltage (V)')
        plt.ylabel('Current (µA)')
        plt.title('miniSMU I-V Sweep Results')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        # Save plot
        plt.savefig('iv_sweep_results.png', dpi=150, bbox_inches='tight')
        print(f"I-V curve plotted and saved as 'iv_sweep_results.png'")
        print(f"Data points: {len(result.data)}")
        print(f"Voltage range: {min(voltages):.3f}V to {max(voltages):.3f}V")
        print(f"Current range: {min(currents):.1f}µA to {max(currents):.1f}µA")

def main():
    """Run all I-V sweep examples"""
    
    try:
        print("miniSMU Onboard I-V Sweep Examples")
        print("==================================")
        print("Note: These examples require firmware v1.3.4 or later\n")
        
        # Run examples
        simple_iv_sweep_example()
        advanced_iv_sweep_example()
        format_comparison_example()
        sweep_abort_example()
        
        # Only try plotting if matplotlib is available
        try:
            plot_iv_curve_example()
        except ImportError:
            print("\nSkipping plot example (matplotlib not available)")
            
        print("\n✓ All I-V sweep examples completed!")
        
    except Exception as e:
        print(f"Example failed: {e}")
        print("\nTroubleshooting:")
        print("- Ensure your miniSMU device is connected")
        print("- Verify firmware version is 1.3.4 or later")
        print("- Check connection parameters in the script (currently set to COM41)")
        print("- Make sure no other software is using the device")

if __name__ == "__main__":
    main()