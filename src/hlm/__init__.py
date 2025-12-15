"""
Heart-Lung Machine (Cardiopulmonary Bypass) System

This package provides a comprehensive implementation of a heart-lung machine
control system with:
- Cardiopulmonary bypass circuit management
- Bubble detection and removal
- Temperature management
- Safety monitoring and alarms
"""

from hlm.bypass_circuit import BypassCircuit, CircuitComponent, PumpType
from hlm.bubble_detection import BubbleDetector, BubbleRemovalSystem
from hlm.temperature import TemperatureController, HeatExchanger
from hlm.safety import SafetyMonitor, AlarmLevel, Alarm
from hlm.controller import HeartLungMachineController

__version__ = "1.0.0"
__all__ = [
    "BypassCircuit",
    "CircuitComponent",
    "PumpType",
    "BubbleDetector",
    "BubbleRemovalSystem",
    "TemperatureController",
    "HeatExchanger",
    "SafetyMonitor",
    "AlarmLevel",
    "Alarm",
    "HeartLungMachineController",
]
