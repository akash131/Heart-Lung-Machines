"""
Communication Protocols System

Integration with hospital information systems and external devices
requires standardized communication protocols.

This module implements:
- HL7 message generation and parsing
- Serial communication for device integration
- Network communication for EMR integration
- Data exchange formats
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Any
import time
import json
from datetime import datetime


class CommunicationProtocol(Enum):
    """Supported communication protocols."""
    HL7_V2 = auto()
    HL7_FHIR = auto()
    SERIAL = auto()
    TCP_IP = auto()
    MODBUS = auto()


class HL7MessageType(Enum):
    """HL7 v2.x message types."""
    ADT = "ADT"  # Admit/Discharge/Transfer
    ORU = "ORU"  # Observation Result
    ORM = "ORM"  # Order Message
    ACK = "ACK"  # Acknowledgment


class ConnectionStatus(Enum):
    """Connection status states."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()


@dataclass
class SerialConfig:
    """Serial port configuration."""
    port: str = "/dev/ttyUSB0"
    baud_rate: int = 9600
    data_bits: int = 8
    stop_bits: int = 1
    parity: str = "N"
    timeout_seconds: float = 1.0


@dataclass
class NetworkConfig:
    """Network configuration."""
    host: str = "localhost"
    port: int = 2575  # Standard HL7 port
    protocol: str = "TCP"
    timeout_seconds: float = 5.0
    use_mllp: bool = True  # Minimal Lower Layer Protocol for HL7


@dataclass
class HL7Segment:
    """An HL7 message segment."""
    segment_type: str
    fields: list[str]

    def to_string(self) -> str:
        """Convert segment to HL7 string format."""
        return f"{self.segment_type}|{'|'.join(self.fields)}"

    @classmethod
    def from_string(cls, segment_string: str) -> "HL7Segment":
        """Parse segment from HL7 string."""
        parts = segment_string.split("|")
        return cls(segment_type=parts[0], fields=parts[1:] if len(parts) > 1 else [])


class HL7MessageBuilder:
    """Builder for HL7 v2.x messages."""

    def __init__(self):
        self.segments: list[HL7Segment] = []
        self.field_separator = "|"
        self.component_separator = "^"
        self.repetition_separator = "~"
        self.escape_character = "\\"
        self.subcomponent_separator = "&"

    def add_msh_segment(self,
                        sending_app: str,
                        sending_facility: str,
                        receiving_app: str,
                        receiving_facility: str,
                        message_type: HL7MessageType,
                        message_control_id: str) -> "HL7MessageBuilder":
        """Add MSH (Message Header) segment."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        encoding_chars = f"{self.component_separator}{self.repetition_separator}{self.escape_character}{self.subcomponent_separator}"

        fields = [
            encoding_chars,
            sending_app,
            sending_facility,
            receiving_app,
            receiving_facility,
            timestamp,
            "",  # Security
            f"{message_type.value}^R01",  # Message Type
            message_control_id,
            "P",  # Processing ID (Production)
            "2.5.1"  # Version ID
        ]

        self.segments.append(HL7Segment("MSH", fields))
        return self

    def add_pid_segment(self,
                        patient_id: str,
                        patient_name: str,
                        dob: str = "",
                        sex: str = "",
                        mrn: str = "") -> "HL7MessageBuilder":
        """Add PID (Patient Identification) segment."""
        fields = [
            "1",  # Set ID
            patient_id,  # Patient ID (External)
            mrn,  # Patient ID (Internal)
            "",  # Alt Patient ID
            patient_name,  # Patient Name
            "",  # Mother's Maiden Name
            dob,  # Date of Birth
            sex,  # Sex
        ]
        self.segments.append(HL7Segment("PID", fields))
        return self

    def add_obr_segment(self,
                        order_id: str,
                        procedure_code: str,
                        procedure_name: str) -> "HL7MessageBuilder":
        """Add OBR (Observation Request) segment."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        fields = [
            "1",  # Set ID
            order_id,  # Placer Order Number
            order_id,  # Filler Order Number
            f"{procedure_code}^{procedure_name}",  # Universal Service ID
            "",  # Priority
            timestamp,  # Requested Date/Time
            timestamp,  # Observation Date/Time
        ]
        self.segments.append(HL7Segment("OBR", fields))
        return self

    def add_obx_segment(self,
                        set_id: int,
                        value_type: str,
                        observation_id: str,
                        observation_name: str,
                        value: str,
                        units: str,
                        reference_range: str = "",
                        abnormal_flag: str = "") -> "HL7MessageBuilder":
        """Add OBX (Observation/Result) segment."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        fields = [
            str(set_id),  # Set ID
            value_type,  # Value Type (NM=Numeric, ST=String, etc.)
            f"{observation_id}^{observation_name}",  # Observation Identifier
            "",  # Observation Sub-ID
            value,  # Observation Value
            units,  # Units
            reference_range,  # Reference Range
            abnormal_flag,  # Abnormal Flags
            "",  # Probability
            "",  # Nature of Abnormal Test
            "F",  # Observation Result Status (F=Final)
            "",  # Date Last Observed Normal
            "",  # User Defined Access Checks
            timestamp,  # Date/Time of Observation
        ]
        self.segments.append(HL7Segment("OBX", fields))
        return self

    def build(self) -> str:
        """Build the complete HL7 message."""
        message = "\r".join(seg.to_string() for seg in self.segments)
        return message + "\r"

    def build_mllp(self) -> bytes:
        """Build message with MLLP framing."""
        message = self.build()
        # MLLP: <VT>message<FS><CR>
        return b"\x0b" + message.encode("utf-8") + b"\x1c\r"


class HL7MessageParser:
    """Parser for HL7 v2.x messages."""

    def __init__(self):
        self.field_separator = "|"
        self.component_separator = "^"

    def parse(self, message: str) -> dict:
        """
        Parse an HL7 message.

        Args:
            message: Raw HL7 message string

        Returns:
            Parsed message as dictionary
        """
        result = {
            "segments": [],
            "message_type": None,
            "patient_id": None,
            "observations": []
        }

        # Split into segments
        segments = message.strip().split("\r")

        for seg_str in segments:
            if not seg_str:
                continue

            segment = HL7Segment.from_string(seg_str)
            result["segments"].append({
                "type": segment.segment_type,
                "fields": segment.fields
            })

            # Extract key information
            if segment.segment_type == "MSH" and len(segment.fields) > 7:
                result["message_type"] = segment.fields[7].split("^")[0]

            elif segment.segment_type == "PID" and len(segment.fields) > 1:
                result["patient_id"] = segment.fields[1]

            elif segment.segment_type == "OBX" and len(segment.fields) > 4:
                obs_id = segment.fields[2].split("^")
                result["observations"].append({
                    "id": obs_id[0] if obs_id else "",
                    "name": obs_id[1] if len(obs_id) > 1 else "",
                    "value": segment.fields[4],
                    "units": segment.fields[5] if len(segment.fields) > 5 else ""
                })

        return result


class SerialConnection:
    """Serial port connection handler."""

    def __init__(self, config: SerialConfig):
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.is_open: bool = False
        self._receive_buffer: bytes = b""

        # Callbacks
        self._data_callbacks: list[Callable[[bytes], None]] = []

    def register_data_callback(self, callback: Callable[[bytes], None]) -> None:
        """Register callback for received data."""
        self._data_callbacks.append(callback)

    def connect(self) -> bool:
        """
        Open serial connection.

        In real implementation, would use pyserial.
        """
        self.status = ConnectionStatus.CONNECTING
        # Simulated connection
        self.is_open = True
        self.status = ConnectionStatus.CONNECTED
        return True

    def disconnect(self) -> None:
        """Close serial connection."""
        self.is_open = False
        self.status = ConnectionStatus.DISCONNECTED

    def send(self, data: bytes) -> bool:
        """
        Send data over serial connection.

        Args:
            data: Data to send

        Returns:
            True if sent successfully
        """
        if not self.is_open:
            return False
        # In real implementation, would write to serial port
        return True

    def receive(self) -> bytes | None:
        """
        Receive data from serial connection.

        Returns:
            Received data or None
        """
        if not self.is_open:
            return None
        # In real implementation, would read from serial port
        return None

    def get_status(self) -> dict:
        """Get connection status."""
        return {
            "port": self.config.port,
            "baud_rate": self.config.baud_rate,
            "status": self.status.name,
            "is_open": self.is_open
        }


class NetworkConnection:
    """Network connection handler for HL7 and other protocols."""

    def __init__(self, config: NetworkConfig):
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.is_connected: bool = False
        self.last_message_time: float = 0.0
        self.messages_sent: int = 0
        self.messages_received: int = 0

        # Callbacks
        self._message_callbacks: list[Callable[[str], None]] = []

    def register_message_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback for received messages."""
        self._message_callbacks.append(callback)

    def connect(self) -> bool:
        """
        Establish network connection.

        In real implementation, would create socket connection.
        """
        self.status = ConnectionStatus.CONNECTING
        # Simulated connection
        self.is_connected = True
        self.status = ConnectionStatus.CONNECTED
        return True

    def disconnect(self) -> None:
        """Close network connection."""
        self.is_connected = False
        self.status = ConnectionStatus.DISCONNECTED

    def send_message(self, message: str) -> bool:
        """
        Send message over network.

        Args:
            message: Message to send

        Returns:
            True if sent successfully
        """
        if not self.is_connected:
            return False

        # In real implementation, would send over socket
        if self.config.use_mllp:
            # Add MLLP framing
            pass

        self.messages_sent += 1
        self.last_message_time = time.time()
        return True

    def send_hl7_message(self, builder: HL7MessageBuilder) -> bool:
        """Send an HL7 message."""
        if self.config.use_mllp:
            # Would send MLLP-framed message
            pass
        else:
            message = builder.build()
            return self.send_message(message)
        return True

    def get_status(self) -> dict:
        """Get connection status."""
        return {
            "host": self.config.host,
            "port": self.config.port,
            "protocol": self.config.protocol,
            "status": self.status.name,
            "is_connected": self.is_connected,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received
        }


class DeviceInterface:
    """
    Interface for external device communication.

    Handles communication with inline monitors, analyzers, etc.
    """

    def __init__(self, device_name: str, serial_config: SerialConfig | None = None):
        self.device_name = device_name
        self.serial_config = serial_config or SerialConfig()
        self.connection = SerialConnection(self.serial_config)
        self.is_active: bool = False

        # Data parsing
        self.last_data: dict = {}
        self.last_update: float = 0.0

        # Device-specific protocol handlers
        self._protocol_handlers: dict[str, Callable[[bytes], dict]] = {}

    def register_protocol_handler(self,
                                    device_type: str,
                                    handler: Callable[[bytes], dict]) -> None:
        """Register a protocol handler for a device type."""
        self._protocol_handlers[device_type] = handler

    def connect(self) -> bool:
        """Connect to device."""
        if self.connection.connect():
            self.is_active = True
            return True
        return False

    def disconnect(self) -> None:
        """Disconnect from device."""
        self.connection.disconnect()
        self.is_active = False

    def request_data(self) -> bool:
        """Request data from device."""
        if not self.is_active:
            return False
        # Send device-specific request command
        return self.connection.send(b"REQUEST\r\n")

    def process_data(self, data: bytes, device_type: str = "generic") -> dict:
        """
        Process received data.

        Args:
            data: Raw data from device
            device_type: Type of device for protocol selection

        Returns:
            Parsed data dictionary
        """
        if device_type in self._protocol_handlers:
            self.last_data = self._protocol_handlers[device_type](data)
        else:
            # Generic parsing
            self.last_data = self._generic_parse(data)

        self.last_update = time.time()
        return self.last_data

    def _generic_parse(self, data: bytes) -> dict:
        """Generic data parsing."""
        try:
            # Try JSON
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Return as raw string
            return {"raw": data.decode("utf-8", errors="ignore")}

    def get_status(self) -> dict:
        """Get device interface status."""
        return {
            "device_name": self.device_name,
            "is_active": self.is_active,
            "connection": self.connection.get_status(),
            "last_update": self.last_update,
            "has_data": bool(self.last_data)
        }


class CommunicationManager:
    """
    Central communication manager.

    Coordinates all external communications including
    EMR integration, device interfaces, and data export.
    """

    def __init__(self):
        """Initialize communication manager."""
        self.is_active: bool = False

        # HL7 configuration
        self.hl7_config = NetworkConfig()
        self.hl7_connection: NetworkConnection | None = None
        self.hl7_parser = HL7MessageParser()

        # Device interfaces
        self.devices: dict[str, DeviceInterface] = {}

        # Message queue
        self.outbound_queue: list[str] = []
        self.inbound_queue: list[str] = []

        # Statistics
        self.total_messages_sent: int = 0
        self.total_messages_received: int = 0
        self.last_activity: float = 0.0

        # Callbacks
        self._observation_callbacks: list[Callable[[dict], None]] = []

    def register_observation_callback(
        self, callback: Callable[[dict], None]
    ) -> None:
        """Register callback for received observations."""
        self._observation_callbacks.append(callback)

    def activate(self) -> None:
        """Activate communication manager."""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate communication manager."""
        self.is_active = False
        if self.hl7_connection:
            self.hl7_connection.disconnect()
        for device in self.devices.values():
            device.disconnect()

    def connect_hl7(self, config: NetworkConfig | None = None) -> bool:
        """
        Establish HL7 connection.

        Args:
            config: Network configuration (uses default if not provided)

        Returns:
            True if connected successfully
        """
        if config:
            self.hl7_config = config

        self.hl7_connection = NetworkConnection(self.hl7_config)
        return self.hl7_connection.connect()

    def add_device(self, name: str, config: SerialConfig) -> DeviceInterface:
        """
        Add a device interface.

        Args:
            name: Device name
            config: Serial configuration

        Returns:
            Device interface
        """
        device = DeviceInterface(name, config)
        self.devices[name] = device
        return device

    def send_observations(self,
                          patient_id: str,
                          observations: list[dict]) -> bool:
        """
        Send observations via HL7.

        Args:
            patient_id: Patient identifier
            observations: List of observation dictionaries

        Returns:
            True if sent successfully
        """
        if not self.hl7_connection or not self.hl7_connection.is_connected:
            return False

        builder = HL7MessageBuilder()
        builder.add_msh_segment(
            sending_app="HLM_SYSTEM",
            sending_facility="PERFUSION",
            receiving_app="EMR",
            receiving_facility="HOSPITAL",
            message_type=HL7MessageType.ORU,
            message_control_id=f"MSG{int(time.time())}"
        )
        builder.add_pid_segment(patient_id=patient_id, patient_name="")
        builder.add_obr_segment(
            order_id=f"ORD{int(time.time())}",
            procedure_code="CPB",
            procedure_name="Cardiopulmonary Bypass"
        )

        for i, obs in enumerate(observations, 1):
            builder.add_obx_segment(
                set_id=i,
                value_type="NM",
                observation_id=obs.get("id", ""),
                observation_name=obs.get("name", ""),
                value=str(obs.get("value", "")),
                units=obs.get("units", ""),
                reference_range=obs.get("reference_range", ""),
                abnormal_flag=obs.get("abnormal_flag", "")
            )

        success = self.hl7_connection.send_hl7_message(builder)
        if success:
            self.total_messages_sent += 1
            self.last_activity = time.time()

        return success

    def get_status(self) -> dict:
        """Get communication manager status."""
        return {
            "is_active": self.is_active,
            "hl7": {
                "connected": (
                    self.hl7_connection.is_connected
                    if self.hl7_connection else False
                ),
                "config": {
                    "host": self.hl7_config.host,
                    "port": self.hl7_config.port
                }
            },
            "devices": {
                name: device.get_status()
                for name, device in self.devices.items()
            },
            "statistics": {
                "messages_sent": self.total_messages_sent,
                "messages_received": self.total_messages_received,
                "last_activity": self.last_activity
            }
        }
