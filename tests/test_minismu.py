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

def test_invalid_voltage_range():
    smu = SMU(ConnectionType.USB, port="/dev/ttyACM0")
    with pytest.raises(ValueError):
        smu.set_voltage_range(1, "INVALID")
