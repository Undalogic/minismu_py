import serial
import socket
import time
import json
from enum import Enum
from typing import Optional, Tuple, Dict, Union, List
from dataclasses import dataclass

@dataclass
class WifiStatus:
    connected: bool
    ssid: str
    ip_address: str
    rssi: int

@dataclass
class SweepStatus:
    status: str
    current_point: int
    total_points: int
    elapsed_ms: int
    estimated_remaining_ms: int

@dataclass
class SweepConfig:
    channel: int
    start_voltage: float
    end_voltage: float
    points: int
    dwell_ms: int
    auto_enable: bool

@dataclass
class SweepDataPoint:
    timestamp: int
    voltage: float
    current: float

@dataclass
class SweepResult:
    config: SweepConfig
    data: List[SweepDataPoint]

class ConnectionType(Enum):
    USB = "usb"
    NETWORK = "network"

class SMUException(Exception):
    """Custom exception for SMU-related errors"""
    pass

class SMU:
    """Interface for the SMU device supporting both USB and network connections"""
    
    def __init__(self, connection_type: ConnectionType, port: str = "/dev/ttyACM0", 
                 host: str = "192.168.1.1", tcp_port: int = 3333):
        """
        Initialize SMU connection
        
        Args:
            connection_type: Type of connection (USB or Network)
            port: Serial port for USB connection
            host: IP address for network connection
            tcp_port: TCP port for network connection
        """
        self.connection_type = connection_type
        self._connection = None
        
        if connection_type == ConnectionType.USB:
            try:
                self._connection = serial.Serial(port, 115200, timeout=1)
            except serial.SerialException as e:
                raise SMUException(f"Failed to open USB connection: {e}")
        else:
            try:
                self._connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._connection.connect((host, tcp_port))
                self._connection.settimeout(1.0)
            except socket.error as e:
                raise SMUException(f"Failed to open network connection: {e}")

    def _send_command(self, command: str) -> str:
        """
        Send command and get response
        
        Args:
            command: Command string to send
            
        Returns:
            Response from device
        """
        try:
            if self.connection_type == ConnectionType.USB:
                self._connection.write(f"{command}\n".encode())
                response = self._read_usb_response(command)
            else:
                self._connection.send(f"{command}".encode())
                response = self._connection.recv(1024).decode().strip()
            
            # Check if response is an acknowledgment
            if response == "OK":
                return response
                
            # For query commands (ending with ?), return the raw response
            if command.endswith("?"):
                return response
                
            # For other commands, return the response
            return response
            
        except (serial.SerialException, socket.error) as e:
            raise SMUException(f"Communication error: {e}")

    def _read_usb_response(self, command: str) -> str:
        """
        Read USB response with support for chunked JSON data
        
        Args:
            command: Original command sent (used to detect expected response type)
            
        Returns:
            Complete response from device
        """
        response_buffer = []
        timeout_count = 0
        max_timeout_iterations = 10  # Max iterations before giving up
        
        # First, try to read the initial response with robust decoding
        try:
            initial_response = self._connection.readline().decode('utf-8', errors='replace').strip()
        except UnicodeDecodeError:
            # Fallback for severely corrupted data
            raw_data = self._connection.readline()
            initial_response = raw_data.decode('utf-8', errors='ignore').strip()
        
        # If it's a simple response (not JSON), return immediately
        if not initial_response.startswith('{') and not initial_response.startswith('['):
            return initial_response
        
        # This looks like JSON - we might need to read more chunks
        response_buffer.append(initial_response)
        
        # Try to parse as JSON to see if it's complete
        current_response = ''.join(response_buffer)
        
        # Quick check: if it looks like complete JSON, try parsing it
        if self._is_likely_complete_json(current_response):
            try:
                json.loads(current_response)
                return current_response  # Successfully parsed, it's complete
            except json.JSONDecodeError:
                pass  # Not complete yet, continue reading
        
        # Read additional chunks until we have complete JSON or timeout
        while timeout_count < max_timeout_iterations:
            try:
                # Set a shorter timeout for additional chunks
                original_timeout = self._connection.timeout
                self._connection.timeout = 0.1  # 100ms timeout for chunk reading
                
                # Read chunk with robust decoding
                try:
                    chunk = self._connection.readline().decode('utf-8', errors='replace').strip()
                except UnicodeDecodeError:
                    # Fallback for severely corrupted chunks
                    raw_chunk = self._connection.readline()
                    chunk = raw_chunk.decode('utf-8', errors='ignore').strip()
                
                # Restore original timeout
                self._connection.timeout = original_timeout
                
                if chunk:
                    # Only append non-empty, valid chunks
                    if chunk.strip() and self._is_valid_chunk(chunk):
                        response_buffer.append(chunk)
                    timeout_count = 0  # Reset timeout counter since we got data
                    
                    # Try to parse the accumulated response
                    current_response = ''.join(response_buffer)
                    try:
                        json.loads(current_response)
                        return current_response  # Successfully parsed complete JSON
                    except json.JSONDecodeError:
                        # Try cleaning the JSON in case of corruption
                        try:
                            cleaned_response = self._clean_json_response(current_response)
                            json.loads(cleaned_response)
                            return cleaned_response  # Successfully parsed cleaned JSON
                        except json.JSONDecodeError:
                            continue  # Not complete yet, keep reading
                else:
                    timeout_count += 1
                    
            except serial.SerialTimeoutException:
                timeout_count += 1
                continue
        
        # If we get here, either we have a complete response or we timed out
        final_response = ''.join(response_buffer)
        
        # Final attempt to validate and clean JSON
        if final_response.startswith('{') or final_response.startswith('['):
            try:
                json.loads(final_response)
                return final_response
            except json.JSONDecodeError:
                # Try cleaning the JSON for known corruption issues
                try:
                    cleaned_response = self._clean_json_response(final_response)
                    json.loads(cleaned_response)  # Validate cleaned version
                    return cleaned_response
                except json.JSONDecodeError:
                    # JSON is incomplete or severely corrupted
                    # Return as-is to maintain compatibility
                    pass
        
        return final_response
    
    def _is_likely_complete_json(self, text: str) -> bool:
        """
        Quick heuristic to check if JSON looks complete
        
        Args:
            text: Text to check
            
        Returns:
            True if JSON appears complete
        """
        if not text:
            return False
            
        text = text.strip()
        
        # Check for matching braces/brackets
        if text.startswith('{'):
            open_braces = text.count('{')
            close_braces = text.count('}')
            return open_braces == close_braces and close_braces > 0
        elif text.startswith('['):
            open_brackets = text.count('[')
            close_brackets = text.count(']')
            return open_brackets == close_brackets and close_brackets > 0
        
        return True  # Not JSON, assume complete
    
    def _is_valid_chunk(self, chunk: str) -> bool:
        """
        Validate if a chunk contains reasonable text data
        
        Args:
            chunk: Text chunk to validate
            
        Returns:
            True if chunk seems valid
        """
        if not chunk:
            return False
            
        # Check for excessive control characters or replacement characters
        control_char_count = sum(1 for c in chunk if ord(c) < 32 and c not in '\t\n\r')
        replacement_char_count = chunk.count('\ufffd')  # Unicode replacement character
        
        # If more than 20% of characters are problematic, reject the chunk
        total_chars = len(chunk)
        if total_chars > 0:
            problem_ratio = (control_char_count + replacement_char_count) / total_chars
            if problem_ratio > 0.2:
                return False
        
        return True
    
    def _clean_json_response(self, json_str: str) -> str:
        """
        Clean corrupted JSON response, specifically handling WiFi status issues
        
        Args:
            json_str: Raw JSON string that may contain corrupted data
            
        Returns:
            Cleaned JSON string
        """
        import re
        
        # Replace corrupted IP addresses with placeholder
        # Pattern matches corrupted Unicode sequences in IP field
        ip_pattern = r'"ip":\s*"[^"]*[\u0000-\u001f\u007f-\u009f][^"]*"'
        json_str = re.sub(ip_pattern, '"ip": "0.0.0.0"', json_str)
        
        # Replace corrupted gateway addresses
        gateway_pattern = r'"gateway":\s*"[^"]*[\u0000-\u001f\u007f-\u009f][^"]*"'
        json_str = re.sub(gateway_pattern, '"gateway": "0.0.0.0"', json_str)
        
        # Replace other corrupted string fields with empty strings
        for field in ['subnet', 'ssid']:
            field_pattern = f'"{field}":\\s*"[^"]*[\\u0000-\\u001f\\u007f-\\u009f][^"]*"'
            json_str = re.sub(field_pattern, f'"{field}": ""', json_str)
        
        return json_str

    def get_identity(self) -> str:
        """Get device identification"""
        return self._send_command("*IDN?")

    def reset(self):
        """Reset the device"""
        self._send_command("*RST")

    # Source and Measurement Methods
    def set_voltage(self, channel: int, voltage: float):
        """
        Set voltage for specified channel
        
        Args:
            channel: Channel number (1 or 2)
            voltage: Voltage value in volts
        """
        self._send_command(f"SOUR{channel}:VOLT {voltage}")

    def set_current(self, channel: int, current: float):
        """
        Set current for specified channel
        
        Args:
            channel: Channel number (1 or 2)
            current: Current value in amperes
        """
        self._send_command(f"SOUR{channel}:CURR {current}")

    def set_current_protection(self, channel: int, current_limit: float):
        """
        Set current protection limit for specified channel
        
        Args:
            channel: Channel number (1 or 2)
            current_limit: Current protection limit in amperes
        """
        self._send_command(f"SOUR{channel}:CURR:PROT {current_limit}")

    def set_voltage_protection(self, channel: int, voltage_limit: float):
        """
        Set voltage protection limit for specified channel
        
        Args:
            channel: Channel number (1 or 2)
            voltage_limit: Voltage protection limit in volts
        """
        self._send_command(f"SOUR{channel}:VOLT:PROT {voltage_limit}")

    def measure_voltage(self, channel: int) -> float:
        """
        Measure voltage on specified channel
        
        Args:
            channel: Channel number (1 or 2)
            
        Returns:
            Measured voltage in volts
        """
        response = self._send_command(f"MEAS{channel}:VOLT?")
        return float(response)

    def measure_current(self, channel: int) -> float:
        """
        Measure current on specified channel
        
        Args:
            channel: Channel number (1 or 2)
            
        Returns:
            Measured current in amperes
        """
        response = self._send_command(f"MEAS{channel}:CURR?")
        return float(response)
    
    def measure_voltage_and_current(self, channel: int) -> Tuple[float, float]:
        """
        Measure both voltage and current on specified channel
        
        Args:
            channel: Channel number (1 or 2)
            
        Returns:
            Tuple of (voltage, current)
        """
        response = self._send_command(f"MEAS{channel}:VOLT:CURR?")
        voltage, current = map(float, response.split(','))
        return voltage, current

    def set_oversampling_ratio(self, channel: int, osr: int):
        """
        Set measurement oversampling ratio for specified channel
        
        Args:
            channel: Channel number (1 or 2)
            osr: Oversampling ratio (0-15, represents 2^osr)
        """
        if not 0 <= osr <= 15:
            raise ValueError("OSR must be between 0 and 15")
        self._send_command(f"MEAS{channel}:OSR {osr}")

    # Channel Configuration Methods
    def enable_channel(self, channel: int):
        """Enable specified channel"""
        self._send_command(f"OUTP{channel} ON")

    def disable_channel(self, channel: int):
        """Disable specified channel"""
        self._send_command(f"OUTP{channel} OFF")

    def set_voltage_range(self, channel: int, range_type: str):
        """
        Set voltage range for channel
        
        Args:
            channel: Channel number (1 or 2)
            range_type: 'AUTO', 'LOW', or 'HIGH'
        """
        if range_type not in ['AUTO', 'LOW', 'HIGH']:
            raise ValueError("Range type must be 'AUTO', 'LOW', or 'HIGH'")
        self._send_command(f"SOUR{channel}:VOLT:RANGE {range_type}")

    def set_mode(self, channel: int, mode: str):
        """
        Set channel mode (FIMV or FVMI)
        
        Args:
            channel: Channel number (1 or 2)
            mode: 'FIMV' or 'FVMI'
        """
        if mode not in ['FIMV', 'FVMI']:
            raise ValueError("Mode must be 'FIMV' or 'FVMI'")
        self._send_command(f"SOUR{channel}:{mode} ENA")

    # Data Streaming Methods
    def start_streaming(self, channel: int):
        """Start data streaming for specified channel"""
        self._send_command(f"SOUR{channel}:DATA:STREAM ON")

    def stop_streaming(self, channel: int):
        """Stop data streaming for specified channel"""
        self._send_command(f"SOUR{channel}:DATA:STREAM OFF")

    def read_streaming_data(self) -> Tuple[int, float, float, float]:
        """
        Read a single data packet from the streaming buffer
        
        Returns:
            Tuple of (channel, timestamp, voltage, current) from the streaming data
        """
        if self.connection_type == ConnectionType.USB:
            # Read the data packet
            data = self._connection.readline().decode().strip()
            try:
                channel, timestamp, voltage, current = data.split(',')
                return int(channel), float(timestamp), float(voltage), float(current)
            except ValueError as e:
                raise SMUException(f"Failed to parse streaming data: {data}")
        else:
            raise SMUException("Streaming is only supported over USB connection")

    def set_sample_rate(self, channel: int, rate: float):
        """
        Set sample rate for specified channel
        
        Args:
            channel: Channel number (1 or 2)
            rate: Sample rate in Hz
        """
        self._send_command(f"SOUR{channel}:DATA:SRATE {rate}")

    # System Configuration Methods
    def set_led_brightness(self, brightness: int):
        """
        Set LED brightness (0-100)
        
        Args:
            brightness: Brightness percentage (0-100)
        """
        if not 0 <= brightness <= 100:
            raise ValueError("Brightness must be between 0 and 100")
        self._send_command(f"SYST:LED {brightness}")

    def get_led_brightness(self) -> int:
        """Get current LED brightness"""
        response = self._send_command("SYST:LED?")
        return int(response)

    def get_temperatures(self) -> Tuple[float, float, float]:
        """
        Get system temperatures
        
        Returns:
            Tuple of (adc_temp, channel1_temp, channel2_temp)
        """
        response = self._send_command("SYST:TEMP?")
        return tuple(map(float, response.split(',')))

    def set_time(self, timestamp: int):
        """
        Set the device's internal clock using a Unix timestamp in milliseconds
        
        Args:
            timestamp: Unix timestamp in milliseconds
        """
        self._send_command(f"SYST:TIME {timestamp}")

    # WiFi Configuration Methods
    def wifi_scan(self) -> list:
        """
        Scan for available WiFi networks
        
        Returns:
            List of available networks
        """
        response = self._send_command("SYST:WIFI:SCAN?")
        return json.loads(response)

    def get_wifi_status(self) -> WifiStatus:
        """
        Get current WiFi status
        
        Returns:
            WifiStatus object with connection details
        """
        response = self._send_command("SYST:WIFI?")
        status_dict = json.loads(response)
        return WifiStatus(
            connected=status_dict.get('connected', False),
            ssid=status_dict.get('ssid', ''),
            ip_address=status_dict.get('ip', ''),
            rssi=status_dict.get('rssi', 0)
        )

    def set_wifi_credentials(self, ssid: str, password: str):
        """
        Set WiFi credentials
        
        Args:
            ssid: Network SSID
            password: Network password
        """
        self._send_command(f'SYST:WIFI:SSID "{ssid}"')
        self._send_command(f'SYST:WIFI:PASS "{password}"')

    def enable_wifi(self):
        """Enable WiFi"""
        self._send_command("SYST:WIFI ENA")

    def disable_wifi(self):
        """Disable WiFi"""
        self._send_command("SYST:WIFI DIS")

    def enable_wifi_autoconnect(self):
        """Enable WiFi auto-connect"""
        self._send_command("SYST:WIFI:AUTO ENA")

    def disable_wifi_autoconnect(self):
        """Disable WiFi auto-connect"""
        self._send_command("SYST:WIFI:AUTO DIS")

    def get_wifi_autoconnect_status(self) -> bool:
        """
        Get WiFi auto-connect status
        
        Returns:
            True if auto-connect is enabled, False otherwise
        """
        response = self._send_command("SYST:WIFI:AUTO?")
        return response == "1"

    def get_wifi_ssid(self) -> str:
        """
        Get current WiFi SSID
        
        Returns:
            Current WiFi SSID
        """
        return self._send_command("SYST:WIFI:SSID?")

    # I-V Sweep Methods
    def configure_iv_sweep(self, channel: int, start_voltage: float, end_voltage: float, 
                          points: int, dwell_ms: int, auto_enable: bool = True, 
                          output_format: str = "CSV"):
        """
        Configure I-V sweep parameters for specified channel
        
        Args:
            channel: Channel number (1 or 2)
            start_voltage: Starting voltage in volts
            end_voltage: Ending voltage in volts
            points: Number of measurement points (max 1000)
            dwell_ms: Dwell time between measurements in milliseconds (max 10000)
            auto_enable: Enable automatic output control during sweep
            output_format: Output format ("CSV" or "JSON")
        """
        if not 1 <= points <= 1000:
            raise ValueError("Points must be between 1 and 1000")
        if not 0 <= dwell_ms <= 10000:
            raise ValueError("Dwell time must be between 0 and 10000 milliseconds")
        if output_format not in ["CSV", "JSON"]:
            raise ValueError("Output format must be 'CSV' or 'JSON'")
        
        # Configure sweep parameters
        self._send_command(f"SOUR{channel}:SWEEP:VOLT:START {start_voltage}")
        self._send_command(f"SOUR{channel}:SWEEP:VOLT:END {end_voltage}")
        self._send_command(f"SOUR{channel}:SWEEP:POINTS {points}")
        self._send_command(f"SOUR{channel}:SWEEP:DWELL {dwell_ms}")
        
        # Configure auto enable/disable
        if auto_enable:
            self._send_command(f"SOUR{channel}:SWEEP:AUTO:ENA")
        else:
            self._send_command(f"SOUR{channel}:SWEEP:AUTO:DIS")
        
        # Set output format
        self._send_command(f"SOUR{channel}:SWEEP:FORMAT {output_format}")

    def set_sweep_start_voltage(self, channel: int, voltage: float):
        """Set sweep start voltage"""
        self._send_command(f"SOUR{channel}:SWEEP:VOLT:START {voltage}")

    def set_sweep_end_voltage(self, channel: int, voltage: float):
        """Set sweep end voltage"""
        self._send_command(f"SOUR{channel}:SWEEP:VOLT:END {voltage}")

    def set_sweep_points(self, channel: int, points: int):
        """Set number of sweep points (max 1000)"""
        if not 1 <= points <= 1000:
            raise ValueError("Points must be between 1 and 1000")
        self._send_command(f"SOUR{channel}:SWEEP:POINTS {points}")

    def set_sweep_dwell_time(self, channel: int, dwell_ms: int):
        """Set dwell time between measurements (max 10000ms)"""
        if not 0 <= dwell_ms <= 10000:
            raise ValueError("Dwell time must be between 0 and 10000 milliseconds")
        self._send_command(f"SOUR{channel}:SWEEP:DWELL {dwell_ms}")

    def enable_sweep_auto_output(self, channel: int):
        """Enable automatic output control during sweep"""
        self._send_command(f"SOUR{channel}:SWEEP:AUTO:ENA")

    def disable_sweep_auto_output(self, channel: int):
        """Disable automatic output control during sweep"""
        self._send_command(f"SOUR{channel}:SWEEP:AUTO:DIS")

    def get_sweep_auto_output_status(self, channel: int) -> bool:
        """Get sweep auto output control status"""
        response = self._send_command(f"SOUR{channel}:SWEEP:AUTO?")
        return response == "1"

    def set_sweep_output_format(self, channel: int, output_format: str):
        """Set sweep output format ('CSV' or 'JSON')"""
        if output_format not in ["CSV", "JSON"]:
            raise ValueError("Output format must be 'CSV' or 'JSON'")
        self._send_command(f"SOUR{channel}:SWEEP:FORMAT {output_format}")

    def get_sweep_output_format(self, channel: int) -> str:
        """Get current sweep output format"""
        response = self._send_command(f"SOUR{channel}:SWEEP:FORMAT?")
        return response.strip('"')

    def execute_sweep(self, channel: int):
        """Execute the configured I-V sweep"""
        self._send_command(f"SOUR{channel}:SWEEP:EXECUTE")

    def abort_sweep(self, channel: int):
        """Abort running I-V sweep"""
        self._send_command(f"SOUR{channel}:SWEEP:ABORT")

    def get_sweep_status(self, channel: int) -> SweepStatus:
        """
        Get sweep status and progress information
        
        Returns:
            SweepStatus object with current status details
        """
        response = self._send_command(f"SOUR{channel}:SWEEP:STATUS?")
        parts = response.split(',')
        if len(parts) != 5:
            raise SMUException(f"Invalid sweep status response: {response}")
        
        return SweepStatus(
            status=parts[0],
            current_point=int(parts[1]),
            total_points=int(parts[2]),
            elapsed_ms=int(parts[3]),
            estimated_remaining_ms=int(parts[4])
        )

    def get_sweep_data_raw(self, channel: int) -> str:
        """Get raw sweep data in configured format"""
        return self._send_command(f"SOUR{channel}:SWEEP:DATA?")

    def get_sweep_data_csv(self, channel: int) -> List[SweepDataPoint]:
        """
        Get sweep data in CSV format parsed into SweepDataPoint objects
        
        Returns:
            List of SweepDataPoint objects
        """
        # Ensure CSV format is set
        self.set_sweep_output_format(channel, "CSV")
        
        # Get raw data
        raw_data = self.get_sweep_data_raw(channel)
        
        # Parse CSV data
        data_points = []
        for line in raw_data.strip().split('\n'):
            if line.strip():
                parts = line.split(',')
                if len(parts) >= 3:
                    data_points.append(SweepDataPoint(
                        timestamp=int(float(parts[0])),
                        voltage=float(parts[1]),
                        current=float(parts[2])
                    ))
        
        return data_points

    def get_sweep_data_json(self, channel: int) -> SweepResult:
        """
        Get sweep data in JSON format parsed into SweepResult object
        
        Returns:
            SweepResult object with configuration and data
        """
        # Ensure JSON format is set
        self.set_sweep_output_format(channel, "JSON")
        
        # Get raw data
        raw_data = self.get_sweep_data_raw(channel)
        
        # Parse JSON data
        json_data = json.loads(raw_data)
        
        # Create config object
        config_data = json_data['sweep_config']
        config = SweepConfig(
            channel=config_data['channel'],
            start_voltage=config_data['start_voltage'],
            end_voltage=config_data['end_voltage'],
            points=config_data['points'],
            dwell_ms=config_data['dwell_ms'],
            auto_enable=config_data['auto_enable']
        )
        
        # Create data points
        data_points = []
        for point in json_data['data']:
            data_points.append(SweepDataPoint(
                timestamp=int(point['t']),
                voltage=float(point['v']),
                current=float(point['i'])
            ))
        
        return SweepResult(config=config, data=data_points)

    def run_iv_sweep(self, channel: int, start_voltage: float, end_voltage: float,
                    points: int, dwell_ms: int = 50, auto_enable: bool = True,
                    output_format: str = "JSON", monitor_progress: bool = False) -> Union[List[SweepDataPoint], SweepResult]:
        """
        Complete I-V sweep operation: configure, execute, and retrieve data
        
        Args:
            channel: Channel number (1 or 2)
            start_voltage: Starting voltage in volts
            end_voltage: Ending voltage in volts  
            points: Number of measurement points (max 1000)
            dwell_ms: Dwell time between measurements in milliseconds
            auto_enable: Enable automatic output control during sweep
            output_format: Output format ("CSV" or "JSON")
            monitor_progress: Print progress updates during sweep
            
        Returns:
            List[SweepDataPoint] for CSV format or SweepResult for JSON format
        """
        # Configure sweep
        self.configure_iv_sweep(channel, start_voltage, end_voltage, points, 
                               dwell_ms, auto_enable, output_format)
        
        # Execute sweep
        self.execute_sweep(channel)
        
        # Monitor progress if requested
        if monitor_progress:
            print(f"Starting I-V sweep: {start_voltage}V to {end_voltage}V, {points} points")
            
            while True:
                status = self.get_sweep_status(channel)
                
                if status.status == "RUNNING":
                    progress = (status.current_point / status.total_points) * 100
                    remaining_sec = status.estimated_remaining_ms / 1000
                    print(f"Progress: {progress:.1f}% ({status.current_point}/{status.total_points}), "
                          f"~{remaining_sec:.1f}s remaining")
                    time.sleep(1)
                elif status.status == "COMPLETED":
                    print("Sweep completed successfully!")
                    break
                elif status.status == "ABORTED":
                    raise SMUException("Sweep was aborted")
                else:
                    # For other statuses, wait and check again
                    time.sleep(0.5)
        else:
            # Wait for completion without monitoring
            while True:
                status = self.get_sweep_status(channel)
                if status.status in ["COMPLETED", "ABORTED", "IDLE"]:
                    break
                time.sleep(0.5)
        
        # Retrieve and return data
        if output_format == "CSV":
            return self.get_sweep_data_csv(channel)
        else:
            return self.get_sweep_data_json(channel)

    def close(self):
        """Close the connection"""
        if self._connection:
            self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()