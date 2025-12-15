"""
Cardiopulmonary Bypass Circuit Management

This module implements the core bypass circuit components including:
- Venous reservoir management
- Blood pump control (roller and centrifugal)
- Oxygenator monitoring
- Arterial filter management
- Flow rate control and monitoring
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time


class PumpType(Enum):
    """Types of blood pumps used in bypass circuits."""
    ROLLER = auto()      # Roller/peristaltic pump - positive displacement
    CENTRIFUGAL = auto() # Centrifugal pump - non-occlusive


class CircuitState(Enum):
    """Operational states of the bypass circuit."""
    OFF = auto()
    PRIMING = auto()      # Circuit being filled with priming solution
    STANDBY = auto()      # Ready but not pumping
    RUNNING = auto()      # Active bypass
    WEANING = auto()      # Gradual reduction before coming off bypass
    EMERGENCY_STOP = auto()


@dataclass
class FlowParameters:
    """Blood flow parameters for the circuit."""
    flow_rate_ml_min: float = 0.0        # Current flow rate
    target_flow_rate_ml_min: float = 0.0  # Target flow rate
    min_flow_rate_ml_min: float = 0.0     # Minimum safe flow
    max_flow_rate_ml_min: float = 7000.0  # Maximum flow capacity

    def validate(self) -> bool:
        """Validate flow parameters are within safe ranges."""
        return (0 <= self.flow_rate_ml_min <= self.max_flow_rate_ml_min and
                0 <= self.target_flow_rate_ml_min <= self.max_flow_rate_ml_min)


@dataclass
class PressureReadings:
    """Pressure readings from various circuit points."""
    arterial_line_mmhg: float = 0.0      # Pressure in arterial line
    venous_line_mmhg: float = 0.0        # Pressure in venous line
    pre_oxygenator_mmhg: float = 0.0     # Pressure before oxygenator
    post_oxygenator_mmhg: float = 0.0    # Pressure after oxygenator
    transmembrane_pressure_mmhg: float = 0.0  # Across oxygenator membrane

    # Safety thresholds
    max_arterial_pressure_mmhg: float = 350.0
    max_transmembrane_pressure_mmhg: float = 500.0

    def is_safe(self) -> bool:
        """Check if all pressures are within safe limits."""
        return (self.arterial_line_mmhg <= self.max_arterial_pressure_mmhg and
                self.transmembrane_pressure_mmhg <= self.max_transmembrane_pressure_mmhg)

    def calculate_transmembrane(self) -> float:
        """Calculate transmembrane pressure across oxygenator."""
        self.transmembrane_pressure_mmhg = (
            self.pre_oxygenator_mmhg - self.post_oxygenator_mmhg
        )
        return self.transmembrane_pressure_mmhg


@dataclass
class CircuitComponent:
    """Base class for circuit components."""
    name: str
    is_active: bool = False
    last_check_time: float = field(default_factory=time.time)
    error_state: bool = False
    error_message: str = ""

    def activate(self) -> bool:
        """Activate the component."""
        if not self.error_state:
            self.is_active = True
            return True
        return False

    def deactivate(self) -> None:
        """Deactivate the component."""
        self.is_active = False

    def set_error(self, message: str) -> None:
        """Set component to error state."""
        self.error_state = True
        self.error_message = message
        self.is_active = False

    def clear_error(self) -> None:
        """Clear error state."""
        self.error_state = False
        self.error_message = ""


@dataclass
class VenousReservoir(CircuitComponent):
    """
    Venous reservoir for collecting drained blood.

    Critical for maintaining circuit volume and preventing air entrainment.
    """
    capacity_ml: float = 4000.0
    current_level_ml: float = 0.0
    low_level_alarm_ml: float = 400.0
    critical_level_alarm_ml: float = 200.0

    def update_level(self, level_ml: float) -> None:
        """Update current reservoir level."""
        self.current_level_ml = max(0, min(level_ml, self.capacity_ml))
        self.last_check_time = time.time()

    def is_level_safe(self) -> bool:
        """Check if reservoir level is safe for operation."""
        return self.current_level_ml >= self.critical_level_alarm_ml

    def is_level_low(self) -> bool:
        """Check if reservoir level is low (warning)."""
        return self.current_level_ml < self.low_level_alarm_ml

    def get_fill_percentage(self) -> float:
        """Get reservoir fill level as percentage."""
        return (self.current_level_ml / self.capacity_ml) * 100


@dataclass
class BloodPump(CircuitComponent):
    """
    Blood pump for circulating blood through the bypass circuit.

    Supports both roller and centrifugal pump types with appropriate
    control characteristics.
    """
    pump_type: PumpType = PumpType.ROLLER
    rpm: float = 0.0
    max_rpm: float = 200.0  # Roller pump typical max
    flow_per_revolution_ml: float = 35.0  # For roller pump calibration
    occlusion_setting: float = 0.0  # For roller pump (0-100%)

    def __post_init__(self):
        """Adjust parameters based on pump type."""
        if self.pump_type == PumpType.CENTRIFUGAL:
            self.max_rpm = 5000.0
            self.flow_per_revolution_ml = 0.0  # Not applicable

    def set_rpm(self, rpm: float) -> bool:
        """Set pump RPM within safe limits."""
        if 0 <= rpm <= self.max_rpm:
            self.rpm = rpm
            return True
        return False

    def calculate_flow_rate(self) -> float:
        """
        Calculate theoretical flow rate based on RPM.

        For roller pumps: Flow = RPM * flow_per_revolution
        For centrifugal pumps: Flow is non-linear and depends on afterload
        """
        if not self.is_active:
            return 0.0

        if self.pump_type == PumpType.ROLLER:
            return self.rpm * self.flow_per_revolution_ml
        else:
            # Centrifugal pump - simplified model
            # Actual flow depends on pressure differential
            return self.rpm * 1.2  # Approximate ml/min

    def emergency_stop(self) -> None:
        """Immediately stop the pump."""
        self.rpm = 0.0
        self.is_active = False


@dataclass
class Oxygenator(CircuitComponent):
    """
    Membrane oxygenator for gas exchange.

    Monitors oxygen transfer efficiency and membrane integrity.
    """
    membrane_type: str = "hollow_fiber"
    surface_area_m2: float = 2.5
    max_blood_flow_ml_min: float = 7000.0

    # Gas parameters
    oxygen_flow_l_min: float = 0.0
    fio2_percent: float = 100.0  # Fraction of inspired oxygen
    sweep_gas_flow_l_min: float = 0.0

    # Efficiency monitoring
    oxygen_transfer_efficiency: float = 1.0
    co2_removal_efficiency: float = 1.0

    def set_gas_flow(self, o2_flow: float, sweep_flow: float) -> None:
        """Set oxygen and sweep gas flow rates."""
        self.oxygen_flow_l_min = max(0, o2_flow)
        self.sweep_gas_flow_l_min = max(0, sweep_flow)

    def set_fio2(self, fio2: float) -> bool:
        """Set FiO2 (21-100%)."""
        if 21 <= fio2 <= 100:
            self.fio2_percent = fio2
            return True
        return False

    def calculate_gas_blood_ratio(self, blood_flow_ml_min: float) -> float:
        """Calculate gas to blood flow ratio."""
        if blood_flow_ml_min <= 0:
            return 0.0
        # Convert blood flow to L/min for ratio
        blood_flow_l_min = blood_flow_ml_min / 1000.0
        total_gas_flow = self.oxygen_flow_l_min + self.sweep_gas_flow_l_min
        return total_gas_flow / blood_flow_l_min if blood_flow_l_min > 0 else 0.0

    def is_efficiency_acceptable(self) -> bool:
        """Check if oxygenator efficiency is acceptable."""
        return (self.oxygen_transfer_efficiency >= 0.8 and
                self.co2_removal_efficiency >= 0.8)


@dataclass
class ArterialFilter(CircuitComponent):
    """
    Arterial line filter for removing particulate matter and micro-emboli.
    """
    pore_size_microns: float = 40.0
    max_pressure_drop_mmhg: float = 50.0
    current_pressure_drop_mmhg: float = 0.0
    filter_saturation_percent: float = 0.0

    def update_pressure_drop(self, pre_pressure: float, post_pressure: float) -> None:
        """Update pressure drop across filter."""
        self.current_pressure_drop_mmhg = pre_pressure - post_pressure
        self.last_check_time = time.time()

    def is_filter_blocked(self) -> bool:
        """Check if filter is becoming blocked."""
        return self.current_pressure_drop_mmhg > self.max_pressure_drop_mmhg

    def estimate_saturation(self, bypass_time_minutes: float) -> float:
        """Estimate filter saturation based on bypass time."""
        # Simplified model - actual would use pressure trends
        self.filter_saturation_percent = min(100, bypass_time_minutes * 0.2)
        return self.filter_saturation_percent


class BypassCircuit:
    """
    Complete cardiopulmonary bypass circuit manager.

    Coordinates all circuit components and monitors overall circuit health.
    """

    def __init__(self, pump_type: PumpType = PumpType.ROLLER):
        """Initialize bypass circuit with specified pump type."""
        self.state = CircuitState.OFF
        self.start_time: float | None = None
        self.bypass_time_minutes: float = 0.0

        # Initialize components
        self.venous_reservoir = VenousReservoir(name="venous_reservoir")
        self.blood_pump = BloodPump(name="main_pump", pump_type=pump_type)
        self.oxygenator = Oxygenator(name="oxygenator")
        self.arterial_filter = ArterialFilter(name="arterial_filter")

        # Flow and pressure monitoring
        self.flow_params = FlowParameters()
        self.pressures = PressureReadings()

        # Callbacks for alarms
        self._alarm_callbacks: list[Callable[[str, str], None]] = []

        # Priming volume tracking
        self.priming_volume_ml: float = 0.0
        self.is_primed: bool = False

    def register_alarm_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for alarm notifications."""
        self._alarm_callbacks.append(callback)

    def _trigger_alarm(self, level: str, message: str) -> None:
        """Trigger alarm callbacks."""
        for callback in self._alarm_callbacks:
            callback(level, message)

    def start_priming(self, priming_volume_ml: float = 1800.0) -> bool:
        """
        Start circuit priming procedure.

        Args:
            priming_volume_ml: Volume of priming solution (typically 1500-2000ml)

        Returns:
            True if priming started successfully
        """
        if self.state != CircuitState.OFF:
            return False

        self.state = CircuitState.PRIMING
        self.priming_volume_ml = priming_volume_ml
        self.venous_reservoir.update_level(priming_volume_ml)
        self.venous_reservoir.activate()

        return True

    def complete_priming(self) -> bool:
        """Mark priming as complete and transition to standby."""
        if self.state != CircuitState.PRIMING:
            return False

        # Verify minimum priming achieved
        if self.venous_reservoir.current_level_ml < 1000:
            self._trigger_alarm("warning", "Insufficient priming volume")
            return False

        self.is_primed = True
        self.state = CircuitState.STANDBY
        return True

    def start_bypass(self, target_flow_ml_min: float) -> bool:
        """
        Initiate cardiopulmonary bypass.

        Args:
            target_flow_ml_min: Target blood flow rate

        Returns:
            True if bypass started successfully
        """
        if self.state != CircuitState.STANDBY:
            self._trigger_alarm("error", "Cannot start bypass - not in standby")
            return False

        if not self.is_primed:
            self._trigger_alarm("error", "Circuit not primed")
            return False

        if not self.venous_reservoir.is_level_safe():
            self._trigger_alarm("error", "Reservoir level too low")
            return False

        # Activate all components
        self.blood_pump.activate()
        self.oxygenator.activate()
        self.arterial_filter.activate()

        # Set target flow
        self.flow_params.target_flow_rate_ml_min = target_flow_ml_min

        # Start timing
        self.state = CircuitState.RUNNING
        self.start_time = time.time()

        return True

    def update_flow_rate(self, new_flow_ml_min: float) -> bool:
        """
        Update blood flow rate.

        Args:
            new_flow_ml_min: New target flow rate

        Returns:
            True if flow rate updated successfully
        """
        if self.state != CircuitState.RUNNING:
            return False

        if not self.flow_params.min_flow_rate_ml_min <= new_flow_ml_min <= self.flow_params.max_flow_rate_ml_min:
            self._trigger_alarm("warning", f"Flow rate {new_flow_ml_min} out of range")
            return False

        self.flow_params.target_flow_rate_ml_min = new_flow_ml_min

        # Calculate required pump RPM
        if self.blood_pump.pump_type == PumpType.ROLLER:
            required_rpm = new_flow_ml_min / self.blood_pump.flow_per_revolution_ml
            self.blood_pump.set_rpm(required_rpm)
        else:
            # Centrifugal - requires feedback control
            estimated_rpm = new_flow_ml_min / 1.2
            self.blood_pump.set_rpm(estimated_rpm)

        return True

    def start_weaning(self) -> bool:
        """Begin weaning process to come off bypass."""
        if self.state != CircuitState.RUNNING:
            return False

        self.state = CircuitState.WEANING
        return True

    def stop_bypass(self) -> bool:
        """Stop bypass and return circuit to standby."""
        if self.state not in (CircuitState.RUNNING, CircuitState.WEANING):
            return False

        # Gradually reduce flow (in practice, this would be stepped)
        self.blood_pump.set_rpm(0)
        self.blood_pump.deactivate()

        self.state = CircuitState.STANDBY
        self.flow_params.flow_rate_ml_min = 0

        return True

    def emergency_stop(self) -> None:
        """Emergency stop - immediately halt all flow."""
        self.blood_pump.emergency_stop()
        self.state = CircuitState.EMERGENCY_STOP
        self.flow_params.flow_rate_ml_min = 0
        self._trigger_alarm("critical", "EMERGENCY STOP ACTIVATED")

    def update_readings(self,
                       reservoir_level_ml: float,
                       actual_flow_ml_min: float,
                       arterial_pressure: float,
                       venous_pressure: float,
                       pre_oxy_pressure: float,
                       post_oxy_pressure: float) -> None:
        """
        Update all sensor readings.

        This method should be called regularly with current sensor values.
        """
        # Update reservoir
        self.venous_reservoir.update_level(reservoir_level_ml)

        # Update flow
        self.flow_params.flow_rate_ml_min = actual_flow_ml_min

        # Update pressures
        self.pressures.arterial_line_mmhg = arterial_pressure
        self.pressures.venous_line_mmhg = venous_pressure
        self.pressures.pre_oxygenator_mmhg = pre_oxy_pressure
        self.pressures.post_oxygenator_mmhg = post_oxy_pressure
        self.pressures.calculate_transmembrane()

        # Update filter pressure drop
        self.arterial_filter.update_pressure_drop(post_oxy_pressure, arterial_pressure)

        # Update bypass time
        if self.start_time and self.state == CircuitState.RUNNING:
            self.bypass_time_minutes = (time.time() - self.start_time) / 60.0

        # Check for alarm conditions
        self._check_alarm_conditions()

    def _check_alarm_conditions(self) -> None:
        """Check for conditions requiring alarms."""
        # Reservoir level checks
        if not self.venous_reservoir.is_level_safe():
            self._trigger_alarm("critical", "CRITICAL: Reservoir level critical")
        elif self.venous_reservoir.is_level_low():
            self._trigger_alarm("warning", "Reservoir level low")

        # Pressure checks
        if not self.pressures.is_safe():
            if self.pressures.arterial_line_mmhg > self.pressures.max_arterial_pressure_mmhg:
                self._trigger_alarm("critical", "Arterial line pressure too high")
            if self.pressures.transmembrane_pressure_mmhg > self.pressures.max_transmembrane_pressure_mmhg:
                self._trigger_alarm("critical", "Transmembrane pressure too high - possible oxygenator failure")

        # Filter check
        if self.arterial_filter.is_filter_blocked():
            self._trigger_alarm("warning", "Arterial filter pressure drop elevated")

        # Oxygenator efficiency
        if self.oxygenator.is_active and not self.oxygenator.is_efficiency_acceptable():
            self._trigger_alarm("warning", "Oxygenator efficiency degraded")

    def get_status(self) -> dict:
        """Get comprehensive circuit status."""
        return {
            "state": self.state.name,
            "bypass_time_minutes": round(self.bypass_time_minutes, 1),
            "is_primed": self.is_primed,
            "reservoir": {
                "level_ml": self.venous_reservoir.current_level_ml,
                "fill_percent": round(self.venous_reservoir.get_fill_percentage(), 1),
                "is_safe": self.venous_reservoir.is_level_safe()
            },
            "flow": {
                "current_ml_min": self.flow_params.flow_rate_ml_min,
                "target_ml_min": self.flow_params.target_flow_rate_ml_min,
                "pump_rpm": self.blood_pump.rpm,
                "pump_type": self.blood_pump.pump_type.name
            },
            "pressures": {
                "arterial_mmhg": self.pressures.arterial_line_mmhg,
                "venous_mmhg": self.pressures.venous_line_mmhg,
                "transmembrane_mmhg": self.pressures.transmembrane_pressure_mmhg
            },
            "oxygenator": {
                "active": self.oxygenator.is_active,
                "fio2_percent": self.oxygenator.fio2_percent,
                "o2_transfer_efficiency": self.oxygenator.oxygen_transfer_efficiency
            },
            "filter": {
                "pressure_drop_mmhg": self.arterial_filter.current_pressure_drop_mmhg,
                "is_blocked": self.arterial_filter.is_filter_blocked()
            }
        }
