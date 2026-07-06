import serial
import socket
import time
import json
import re
from enum import Enum
from typing import Optional, Tuple, Union, List
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

# Current range limits in amperes (absolute value)
# Range index -> max current magnitude
CURRENT_RANGE_LIMITS = {
    0: 1e-6,      # Range 0: ± 1 µA
    1: 25e-6,     # Range 1: ± 25 µA
    2: 650e-6,    # Range 2: ± 650 µA
    3: 15e-3,     # Range 3: ± 15 mA
    4: 180e-3,    # Range 4: ± 180 mA
}

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

        # Detected firmware version from *IDN?, or None if we couldn't parse it.
        self.firmware_version: Optional[Tuple[int, int, int]] = None
        # What to append to a TCP command before sending. Firmware 1.4.6 added
        # strict LF-delimited command parsing; older firmware tolerated either,
        # so we keep "" for pre-1.4.6 to match the historical wire shape and
        # only opt into "\n" once we've confirmed the device understands it.
        self._tcp_command_suffix = "\n"
        # Receive buffer for line-based TCP reads. TCP is a byte stream, so
        # responses can arrive fragmented or coalesced; leftover bytes from
        # one recv() are kept here for the next read.
        self._tcp_buffer = b""
        # How long to wait for the first line of a command response
        self._response_timeout = 1.0

        if connection_type == ConnectionType.USB:
            try:
                self._connection = serial.Serial(port, 115200, timeout=1)
                # Discard stale data a previous session may have left behind
                self._connection.reset_input_buffer()
            except serial.SerialException as e:
                raise SMUException(f"Failed to open USB connection: {e}")
        else:
            try:
                self._connection = socket.create_connection((host, tcp_port), timeout=5.0)
                self._connection.settimeout(1.0)
            except socket.error as e:
                raise SMUException(f"Failed to open network connection: {e}")

            # Probe firmware version. Use "\n" for the probe itself: pre-1.4.6
            # firmware tolerates it (strips trailing whitespace), 1.4.6+
            # requires it - so "\n" works against any version we care about.
            self._detect_firmware_version_over_tcp()

    @staticmethod
    def _parse_firmware_version(idn: str) -> Optional[Tuple[int, int, int]]:
        """Extract (major, minor, patch) from an *IDN? response, or None."""
        if not idn:
            return None
        m = re.search(r'v(\d+)\.(\d+)\.(\d+)', idn)
        if not m:
            return None
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def _detect_firmware_version_over_tcp(self) -> None:
        """Probe *IDN?, parse the version, and pick the TCP command suffix.

        On any failure we keep the default suffix ("\n"), which is the safer
        bet for unknown firmware - 1.4.6+ requires it, older firmware
        tolerates it.
        """
        try:
            self._connection.sendall(b"*IDN?\n")
            idn = self._tcp_readline(self._response_timeout)
        except socket.error:
            return

        version = self._parse_firmware_version(idn)
        if version is None:
            return

        self.firmware_version = version
        if version < (1, 4, 6):
            self._tcp_command_suffix = ""

    def _send_command(self, command: str) -> str:
        """
        Send command and get response

        Args:
            command: Command string to send

        Returns:
            Response from device

        Raises:
            SMUException: On a communication failure, or if the device
                reports an error for the command
        """
        self._write_command(command)
        try:
            response = self._read_response(command)
        except (serial.SerialException, socket.error) as e:
            raise SMUException(f"Communication error: {e}")

        if command.endswith("?"):
            # Query: data response expected; explicit errors are prefixed
            if response.startswith("ERROR"):
                raise SMUException(f"Device error for '{command}': {response}")
            return response

        # Non-query commands are acknowledged with "OK"; anything else is an
        # error report (e.g. "Invalid channel number", "ERROR: ...")
        if response != "OK":
            raise SMUException(f"Device error for '{command}': {response!r}")

        return response

    def _write_command(self, command: str):
        """Send a command without reading a response."""
        try:
            if self.connection_type == ConnectionType.USB:
                self._connection.write(f"{command}\n".encode())
            else:
                self._connection.sendall(f"{command}{self._tcp_command_suffix}".encode())
        except (serial.SerialException, socket.error) as e:
            raise SMUException(f"Communication error: {e}")

    def _readline(self, timeout: float, partial_ok: bool = True) -> str:
        """Read one newline-terminated line, decoded and stripped.

        Returns "" if no line arrived within the timeout.

        Args:
            timeout: Max quiet time (no bytes arriving) to wait for
            partial_ok: On timeout with an incomplete line buffered, whether
                to return the partial line (True) or keep it buffered for the
                next read (False). Only meaningful for TCP; pyserial's
                readline always returns partial data on timeout.
        """
        if self.connection_type == ConnectionType.USB:
            return self._usb_readline(timeout)
        return self._tcp_readline(timeout, partial_ok)

    def _usb_readline(self, timeout: float) -> str:
        original_timeout = self._connection.timeout
        try:
            self._connection.timeout = timeout
            raw = self._connection.readline()
        finally:
            self._connection.timeout = original_timeout
        return raw.decode('utf-8', errors='replace').strip()

    def _tcp_readline(self, timeout: float, partial_ok: bool = True) -> str:
        """Read one LF-terminated line from the socket.

        Buffers raw bytes across recv() calls so that fragmented or
        coalesced responses are reassembled correctly. The timeout counts
        quiet time: it restarts whenever bytes arrive, so a line delivered
        across several slow segments is not sheared mid-line.

        If the link goes quiet with an incomplete line buffered, the partial
        data is returned when partial_ok is True (compat fallback for
        firmware that doesn't newline-terminate a response), otherwise it
        stays buffered for the next read and "" is returned.
        """
        deadline = time.monotonic() + timeout
        while b"\n" not in self._tcp_buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                # Link went quiet without a complete line
                if partial_ok and self._tcp_buffer:
                    line = self._tcp_buffer.decode('utf-8', errors='replace').strip()
                    self._tcp_buffer = b""
                    return line
                return ""
            self._connection.settimeout(remaining)
            try:
                chunk = self._connection.recv(4096)
            except socket.timeout:
                continue  # deadline check above handles the fallback
            if not chunk:
                # Connection closed - return any remaining buffered data
                line = self._tcp_buffer.decode('utf-8', errors='replace').strip()
                self._tcp_buffer = b""
                return line
            self._tcp_buffer += chunk
            deadline = time.monotonic() + timeout  # data arrived; restart quiet timer
        line, _, self._tcp_buffer = self._tcp_buffer.partition(b"\n")
        return line.decode('utf-8', errors='replace').strip()

    def _flush_partial_line(self) -> str:
        """Return and clear any buffered partial line (TCP only)."""
        if self.connection_type == ConnectionType.USB:
            return ""
        line = self._tcp_buffer.decode('utf-8', errors='replace').strip()
        self._tcp_buffer = b""
        return line

    def _read_response(self, command: str) -> str:
        """
        Read a complete response for the given command

        Args:
            command: Original command sent (used to detect expected response type)

        Returns:
            Complete response from device
        """
        initial_response = self._readline(self._response_timeout)

        # JSON responses (sweep data, WiFi status/scan) may span multiple chunks
        if initial_response.startswith('{') or initial_response.startswith('['):
            return self._read_json_response(initial_response)

        # CSV sweep data spans multiple lines; read until the link goes quiet
        if initial_response and command.upper().endswith("SWEEP:DATA?"):
            return self._read_multiline_response(initial_response)

        return initial_response

    def _read_multiline_response(self, first_line: str) -> str:
        """Accumulate a multi-line response until no new lines arrive."""
        lines = [first_line]
        quiet_reads = 0
        while quiet_reads < 3:  # ~600ms of silence ends the response
            line = self._readline(0.2, partial_ok=False)
            if line:
                lines.append(line)
                quiet_reads = 0
            else:
                quiet_reads += 1
        # Device stopped mid-line? Surface the partial data rather than drop it
        tail = self._flush_partial_line()
        if tail:
            lines.append(tail)
        return '\n'.join(lines)

    def _read_json_response(self, initial_response: str) -> str:
        """
        Accumulate a possibly-chunked JSON response until it parses

        Args:
            initial_response: First line of the response (starts with '{' or '[')

        Returns:
            Complete response from device
        """
        response_buffer = [initial_response]
        timeout_count = 0
        max_timeout_iterations = 10  # Max quiet reads before giving up

        # Quick check: if it looks like complete JSON, try parsing it
        if self._is_likely_complete_json(initial_response):
            try:
                json.loads(initial_response)
                return initial_response  # Successfully parsed, it's complete
            except json.JSONDecodeError:
                pass  # Not complete yet, continue reading

        # Read additional chunks until we have complete JSON or timeout
        while timeout_count < max_timeout_iterations:
            chunk = self._readline(0.1, partial_ok=False)
            if not chunk:
                timeout_count += 1
                continue

            # Only append non-empty, valid chunks
            if self._is_valid_chunk(chunk):
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

        # Timed out - final attempt to validate and clean what we have,
        # including any unterminated trailing data still buffered
        tail = self._flush_partial_line()
        if tail:
            response_buffer.append(tail)
        final_response = ''.join(response_buffer)
        try:
            json.loads(final_response)
            return final_response
        except json.JSONDecodeError:
            try:
                cleaned_response = self._clean_json_response(final_response)
                json.loads(cleaned_response)  # Validate cleaned version
                return cleaned_response
            except json.JSONDecodeError:
                # JSON is incomplete or severely corrupted
                # Return as-is to maintain compatibility
                return final_response

    def _drain_input(self):
        """Discard buffered and in-flight data until the link goes quiet.

        Used to resynchronise the request/response pairing after operations
        that leave unsolicited data in flight (e.g. stopping a stream).
        """
        if self.connection_type == ConnectionType.USB:
            original_timeout = self._connection.timeout
            try:
                self._connection.timeout = 0.2
                while self._connection.read(4096):
                    pass
            finally:
                self._connection.timeout = original_timeout
            self._connection.reset_input_buffer()
        else:
            self._tcp_buffer = b""
            self._connection.settimeout(0.2)
            try:
                while self._connection.recv(4096):
                    pass
            except socket.timeout:
                pass
    
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
        """Reset the device

        The device reboots and (over USB) re-enumerates, so this connection
        is no longer valid afterwards; create a new SMU instance to continue.
        """
        self._write_command("*RST")

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
        try:
            return float(response)
        except ValueError:
            raise SMUException(f"Unexpected response to MEAS{channel}:VOLT?: {response!r}")

    def measure_current(self, channel: int) -> float:
        """
        Measure current on specified channel
        
        Args:
            channel: Channel number (1 or 2)
            
        Returns:
            Measured current in amperes
        """
        response = self._send_command(f"MEAS{channel}:CURR?")
        try:
            return float(response)
        except ValueError:
            raise SMUException(f"Unexpected response to MEAS{channel}:CURR?: {response!r}")
    
    def measure_voltage_and_current(self, channel: int) -> Tuple[float, float]:
        """
        Measure both voltage and current on specified channel
        
        Args:
            channel: Channel number (1 or 2)
            
        Returns:
            Tuple of (voltage, current)
        """
        response = self._send_command(f"MEAS{channel}:VOLT:CURR?")
        try:
            voltage, current = map(float, response.split(','))
        except ValueError:
            raise SMUException(f"Unexpected response to MEAS{channel}:VOLT:CURR?: {response!r}")
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

    # Current Range Methods
    def set_autorange(self, channel: int, enabled: bool):
        """
        Enable or disable automatic current range switching

        By default, the miniSMU automatically switches current range to the most
        appropriate range for the measured current. Disabling autorange allows
        manual control of the current range using set_current_range().

        Args:
            channel: Channel number (1 or 2)
            enabled: True to enable autoranging, False to disable
        """
        if enabled:
            self._send_command(f"CH{channel}:AUTORANGE:ENA")
        else:
            self._send_command(f"CH{channel}:AUTORANGE:DIS")

    def set_current_range(self, channel: int, range_index: int):
        """
        Manually set the current measurement range

        Note: Autoranging must be disabled first using set_autorange(channel, False)
        for this setting to take effect.

        Available ranges:
            0: ± 1 µA
            1: ± 25 µA
            2: ± 650 µA
            3: ± 15 mA
            4: ± 180 mA

        Args:
            channel: Channel number (1 or 2)
            range_index: Range index (0-4)

        Raises:
            ValueError: If range_index is not between 0 and 4
        """
        if not 0 <= range_index <= 4:
            raise ValueError("Range index must be between 0 and 4")
        self._send_command(f"CH{channel}:IRANGE {range_index}")

    def set_current_range_by_limit(self, channel: int, max_current: float,
                                    disable_autorange: bool = True) -> int:
        """
        Set the current range based on the maximum expected current

        Automatically selects the smallest range that can accommodate the specified
        maximum current, providing the best resolution for that current level.

        Available ranges:
            0: ± 1 µA
            1: ± 25 µA
            2: ± 650 µA
            3: ± 15 mA
            4: ± 180 mA

        Args:
            channel: Channel number (1 or 2)
            max_current: Maximum expected current magnitude in amperes (absolute value)
            disable_autorange: If True, automatically disables autoranging before
                              setting the range (default: True)

        Returns:
            The selected range index (0-4)

        Raises:
            ValueError: If max_current exceeds the maximum range (180 mA)

        Example:
            # For measurements up to 10 mA, this will select range 3 (± 15 mA)
            selected = smu.set_current_range_by_limit(1, 0.010)
            print(f"Selected range: {selected}")  # Prints: Selected range: 3

            # For measurements up to 500 µA, this will select range 2 (± 650 µA)
            selected = smu.set_current_range_by_limit(1, 500e-6)
        """
        max_current = abs(max_current)

        # Find the smallest range that can accommodate the current
        selected_range = None
        for range_index in sorted(CURRENT_RANGE_LIMITS.keys()):
            if max_current <= CURRENT_RANGE_LIMITS[range_index]:
                selected_range = range_index
                break

        if selected_range is None:
            raise ValueError(
                f"max_current ({max_current} A) exceeds maximum range limit "
                f"({CURRENT_RANGE_LIMITS[4]} A = 180 mA)"
            )

        if disable_autorange:
            self.set_autorange(channel, False)

        self.set_current_range(channel, selected_range)
        return selected_range

    def get_current_range_limit(self, range_index: int) -> float:
        """
        Get the current limit for a specific range index

        Args:
            range_index: Range index (0-4)

        Returns:
            Maximum current magnitude in amperes for the specified range

        Raises:
            ValueError: If range_index is not between 0 and 4
        """
        if range_index not in CURRENT_RANGE_LIMITS:
            raise ValueError("Range index must be between 0 and 4")
        return CURRENT_RANGE_LIMITS[range_index]

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
        """Stop data streaming for specified channel

        Streamed data packets still in flight (including any interleaved with
        the command acknowledgment) are discarded, so that subsequent commands
        see clean responses. The acknowledgment itself is not validated, since
        it cannot be distinguished from in-flight data packets.
        """
        self._write_command(f"SOUR{channel}:DATA:STREAM OFF")
        self._drain_input()

    def read_streaming_data(self) -> Tuple[int, float, float, float]:
        """
        Read a single data packet from the streaming buffer

        Returns:
            Tuple of (channel, timestamp, voltage, current) from the streaming data
        """
        if self.connection_type == ConnectionType.USB:
            # Read the data packet. Firmware v1.5.0+ appends extra fields
            # (e.g. the active current range) after the first four; ignore them.
            data = self._connection.readline().decode('utf-8', errors='replace').strip()
            parts = data.split(',')
            try:
                if len(parts) < 4:
                    raise ValueError
                channel, timestamp, voltage, current = parts[:4]
                return int(channel), float(timestamp), float(voltage), float(current)
            except ValueError:
                raise SMUException(f"Failed to parse streaming data: {data!r}")
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
        try:
            return int(response)
        except ValueError:
            raise SMUException(f"Unexpected response to SYST:LED?: {response!r}")

    def get_temperatures(self) -> Tuple[float, float, float]:
        """
        Get system temperatures
        
        Returns:
            Tuple of (adc_temp, channel1_temp, channel2_temp)
        """
        response = self._send_command("SYST:TEMP?")
        try:
            adc_temp, ch1_temp, ch2_temp = map(float, response.split(','))
        except ValueError:
            raise SMUException(f"Unexpected response to SYST:TEMP?: {response!r}")
        return adc_temp, ch1_temp, ch2_temp

    def set_time(self, timestamp: int):
        """
        Set the device's internal clock using a Unix timestamp in milliseconds

        Args:
            timestamp: Unix timestamp in milliseconds
        """
        self._send_command(f"SYST:TIME {timestamp}")

    # 4-Wire (Kelvin) Measurement Mode Methods
    def enable_fourwire_mode(self):
        """
        Enable 4-wire (Kelvin) measurement mode

        In 4-wire mode:
        - CH1 acts as the source/force channel (FVMI mode)
        - CH2 acts as the sense channel (FIMV mode @ 0A, high impedance)
        - Measurements on CH1 return CH1 current + CH2 voltage (true DUT voltage)
        - This eliminates lead resistance errors in high-current applications

        Note:
        - Cannot enable while streaming or sweep is active
        - CH2 commands are blocked while 4-wire mode is active
        - OUTP1 ON/OFF controls both channels together

        Raises:
            SMUException: If 4-wire mode cannot be enabled (streaming/sweep active)
        """
        self._send_command("SYST:4WIR ENA")

    def disable_fourwire_mode(self):
        """
        Disable 4-wire measurement mode and restore independent channel operation

        After disabling:
        - CH2 returns to its previous state
        - Both channels can be controlled independently
        - Measurements return values from the measured channel only
        """
        self._send_command("SYST:4WIR DIS")

    def get_fourwire_mode(self) -> bool:
        """
        Query 4-wire measurement mode status

        Returns:
            True if 4-wire mode is enabled, False otherwise
        """
        response = self._send_command("SYST:4WIR?")
        return response.strip() == "1"

    # WiFi Configuration Methods
    def wifi_scan(self) -> list:
        """
        Scan for available WiFi networks
        
        Returns:
            List of available networks
        """
        response = self._send_command("SYST:WIFI:SCAN?")
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise SMUException(f"Malformed WiFi scan response: {e}")

    def get_wifi_status(self) -> WifiStatus:
        """
        Get current WiFi status
        
        Returns:
            WifiStatus object with connection details
        """
        response = self._send_command("SYST:WIFI?")
        try:
            status_dict = json.loads(response)
        except json.JSONDecodeError as e:
            raise SMUException(f"Malformed WiFi status response: {e}")
        # Firmware v1.5.0 reports {"status": "Connected", ...} rather than a
        # boolean "connected" field; accept either shape
        if 'connected' in status_dict:
            connected = bool(status_dict['connected'])
        else:
            connected = status_dict.get('status', '') == 'Connected'
        return WifiStatus(
            connected=connected,
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

        Raises:
            ValueError: If the SSID or password contains characters that would
                break the command framing (double quotes or newlines)
        """
        for name, value in (("SSID", ssid), ("password", password)):
            if any(c in value for c in ('"', '\n', '\r')):
                raise ValueError(f"WiFi {name} must not contain double quotes or newlines")
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
            raise SMUException(f"Invalid sweep status response: {response!r}")

        try:
            return SweepStatus(
                status=parts[0],
                current_point=int(parts[1]),
                total_points=int(parts[2]),
                elapsed_ms=int(parts[3]),
                estimated_remaining_ms=int(parts[4])
            )
        except ValueError:
            raise SMUException(f"Invalid sweep status response: {response!r}")

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
                    try:
                        data_points.append(SweepDataPoint(
                            timestamp=int(float(parts[0])),
                            voltage=float(parts[1]),
                            current=float(parts[2])
                        ))
                    except ValueError:
                        raise SMUException(
                            f"Malformed CSV sweep data line "
                            f"(response may be truncated): {line!r}")

        # Verify completeness: a truncated response can still parse cleanly
        # (e.g. sheared mid-line at a spot that yields a plausible number)
        status = self.get_sweep_status(channel)
        if status.status == "COMPLETED" and len(data_points) != status.total_points:
            message = (f"CSV sweep data is incomplete: got {len(data_points)} of "
                       f"{status.total_points} points")
            if self.connection_type == ConnectionType.NETWORK:
                message += (". Firmware v1.5.0 and earlier truncate responses "
                            "larger than ~5.7 kB over TCP (~175 CSV points); "
                            "use fewer points or a USB connection")
            raise SMUException(message)

        return data_points

    def get_sweep_data_json(self, channel: int) -> SweepResult:
        """
        Get sweep data in JSON format parsed into SweepResult object

        Note: firmware v1.5.0 and earlier truncate responses larger than
        ~5.7 kB over network connections (roughly 95 sweep points in JSON
        format, ~175 in CSV). For larger sweeps, use a USB connection.

        Returns:
            SweepResult object with configuration and data

        Raises:
            SMUException: If the sweep data is truncated or malformed
        """
        # Ensure JSON format is set
        self.set_sweep_output_format(channel, "JSON")

        # Get raw data
        raw_data = self.get_sweep_data_raw(channel)

        # Parse JSON data
        try:
            json_data = json.loads(raw_data)
        except json.JSONDecodeError as e:
            message = (f"Sweep data JSON is truncated or malformed "
                       f"(received {len(raw_data)} chars): {e}")
            if self.connection_type == ConnectionType.NETWORK:
                message += (". Firmware v1.5.0 and earlier truncate responses "
                            "larger than ~5.7 kB over TCP (~95 JSON points); "
                            "use CSV format (fits ~175 points), fewer points, "
                            "or a USB connection")
            raise SMUException(message)
        
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
            output_format: Output format ("CSV" or "JSON"). Note: firmware
                v1.5.0 and earlier truncate responses larger than ~5.7 kB over
                network connections (roughly 95 points in JSON format, ~175 in
                CSV); use USB for larger sweeps.
            monitor_progress: Print progress updates during sweep

        Returns:
            List[SweepDataPoint] for CSV format or SweepResult for JSON format

        Raises:
            SMUException: If the sweep is aborted or doesn't complete within
                the expected duration plus a 30 second margin
        """
        # Configure sweep
        self.configure_iv_sweep(channel, start_voltage, end_voltage, points,
                               dwell_ms, auto_enable, output_format)

        # Execute sweep
        self.execute_sweep(channel)

        if monitor_progress:
            print(f"Starting I-V sweep: {start_voltage}V to {end_voltage}V, {points} points")

        # Wait for completion. IDLE is ambiguous: the firmware reports it both
        # before the sweep has started and after it has finished, so only treat
        # it as completion once we've seen the sweep run (or waited longer than
        # the sweep could possibly take to start and finish).
        expected_duration_s = (points * dwell_ms) / 1000.0
        start_time = time.monotonic()
        deadline = start_time + expected_duration_s + 30.0
        seen_running = False

        while True:
            status = self.get_sweep_status(channel)

            if status.status == "RUNNING":
                seen_running = True
                if monitor_progress:
                    if status.total_points > 0:
                        progress = (status.current_point / status.total_points) * 100
                        remaining_sec = status.estimated_remaining_ms / 1000
                        print(f"Progress: {progress:.1f}% ({status.current_point}/{status.total_points}), "
                              f"~{remaining_sec:.1f}s remaining")
                    time.sleep(1)
                else:
                    time.sleep(0.2)
            elif status.status == "COMPLETED":
                if monitor_progress:
                    print("Sweep completed successfully!")
                break
            elif status.status == "ABORTED":
                raise SMUException("Sweep was aborted")
            elif status.status == "IDLE" and (
                    seen_running or
                    time.monotonic() - start_time > max(2.0, expected_duration_s)):
                break
            else:
                # Not started yet or unknown status - wait and check again
                time.sleep(0.2)

            if time.monotonic() > deadline:
                raise SMUException(
                    f"Timed out waiting for sweep completion "
                    f"(last status: {status.status})")

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