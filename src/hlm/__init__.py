"""
Heart-Lung Machine (Cardiopulmonary Bypass) System

This package provides a comprehensive, vendor-parity implementation of a
heart-lung machine control system with:

Core Systems:
- Cardiopulmonary bypass circuit management
- Bubble detection and removal
- Temperature management
- Safety monitoring and alarms

Advanced Features:
- Cardioplegia delivery system
- Blood gas and perfusion monitoring
- Hemoconcentrator/ultrafiltration
- Suction and vent management
- Anticoagulation (ACT) monitoring
- Data logging and trending
- Goal-directed perfusion protocols
- User interface and display
- HL7/serial communication
- Calibration and maintenance
- Configuration and audit trails
"""

# Core systems
from hlm.bypass_circuit import BypassCircuit, CircuitComponent, PumpType
from hlm.bubble_detection import BubbleDetector, BubbleRemovalSystem
from hlm.temperature import TemperatureController, HeatExchanger
from hlm.safety import SafetyMonitor, SafetyInterlock, AlarmLevel, Alarm
from hlm.controller import HeartLungMachineController

# Advanced systems
from hlm.cardioplegia import CardioplegiaDeliverySystem, CardioplegiaType, DeliveryRoute
from hlm.blood_gas import BloodGasMonitor, BloodGasReading, PerfusionParameters
from hlm.ultrafiltration import HemoconcentratorSystem, UltrafiltrationMode
from hlm.suction import SuctionController, SuctionType
from hlm.anticoagulation import AnticoagulationMonitor, ACTReading
from hlm.data_logging import DataLogger, EventRecord
from hlm.protocols import GoalDirectedPerfusion, StandardAdultProtocol, Protocol
from hlm.display import DisplayManager, DisplayMode
from hlm.communication import CommunicationManager, HL7MessageBuilder
from hlm.maintenance import MaintenanceSystem, CalibrationManager, MaintenanceManager
from hlm.configuration import ConfigurationSystem, UserRole, AuditTrail

__version__ = "2.0.0"
__all__ = [
    # Core
    "BypassCircuit",
    "CircuitComponent",
    "PumpType",
    "BubbleDetector",
    "BubbleRemovalSystem",
    "TemperatureController",
    "HeatExchanger",
    "SafetyMonitor",
    "SafetyInterlock",
    "AlarmLevel",
    "Alarm",
    "HeartLungMachineController",
    # Cardioplegia
    "CardioplegiaDeliverySystem",
    "CardioplegiaType",
    "DeliveryRoute",
    # Blood Gas
    "BloodGasMonitor",
    "BloodGasReading",
    "PerfusionParameters",
    # Ultrafiltration
    "HemoconcentratorSystem",
    "UltrafiltrationMode",
    # Suction
    "SuctionController",
    "SuctionType",
    # Anticoagulation
    "AnticoagulationMonitor",
    "ACTReading",
    # Data Logging
    "DataLogger",
    "EventRecord",
    # Protocols
    "GoalDirectedPerfusion",
    "StandardAdultProtocol",
    "Protocol",
    # Display
    "DisplayManager",
    "DisplayMode",
    # Communication
    "CommunicationManager",
    "HL7MessageBuilder",
    # Maintenance
    "MaintenanceSystem",
    "CalibrationManager",
    "MaintenanceManager",
    # Configuration
    "ConfigurationSystem",
    "UserRole",
    "AuditTrail",
]
