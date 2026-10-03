import pytest
from minismu_py import SMU, ConnectionType, SMUException
from unittest.mock import Mock, patch

@pytest.fixture
def mock_serial():
    with patch('serial.Serial') as mock:
        # Configure mock to return specific responses
        mock_instance = Mock()
        mock_instance.readline.return_value = b"OK\n"
        mock.return_value = mock_instance
        yield mock_instance

def test_smu_initialization(mock_serial):
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    assert smu.connection_type == ConnectionType.USB

def test_get_identity(mock_serial):
    mock_serial.readline.return_value = b"Undalogic Inc,MS01-p9,12345,v1.0.0\n"
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    identity = smu.get_identity()
    assert "Undalogic" in identity

def test_measure_voltage_and_current(mock_serial):
    mock_serial.readline.return_value = b"3.301,-0.0015\n"
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    voltage, current = smu.measure_voltage_and_current(1)
    assert isinstance(voltage, float)
    assert isinstance(current, float)

def test_invalid_voltage_range(mock_serial):
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    with pytest.raises(ValueError):
        smu.set_voltage_range(1, "INVALID")

def test_device_error_raises(mock_serial):
    mock_serial.readline.return_value = b"ERROR: Invalid channel\n"
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    with pytest.raises(SMUException):
        smu.set_voltage(3, 1.0)

def test_stop_streaming_raises_if_data_never_stops(mock_serial):
    # e.g. the other channel is still streaming: the drain must give up
    mock_serial.read.return_value = b"2,100,1.0,0.0001\n"
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    smu._max_drain_time = 0.3
    with pytest.raises(SMUException, match="still sending data"):
        smu.stop_streaming(1)

def test_stop_streaming_flushes_partial_device_line(mock_serial):
    mock_serial.read.return_value = b""
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    smu.stop_streaming(1)
    writes = [c.args[0] for c in mock_serial.write.call_args_list]
    assert writes == [b"\n", b"SOUR1:DATA:STREAM OFF\n"]

def test_multiline_response_bounded_while_streaming(mock_serial):
    mock_serial.readline.return_value = b"1,100,1.0,0.0001\n"
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    smu._max_response_time = 0.3
    with pytest.raises(SMUException, match="still be streaming"):
        smu._send_command("SOUR1:SWEEP:DATA?")

def test_json_response_bounded_while_streaming(mock_serial):
    lines = iter([b'{"data": [\n'])
    mock_serial.readline.side_effect = lambda: next(lines, b"1,100,1.0,0.0001\n")
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    smu._max_response_time = 0.3
    with pytest.raises(SMUException, match="still be streaming"):
        smu._send_command("SOUR1:SWEEP:DATA:JSON?")
