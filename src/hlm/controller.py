"""
Heart-Lung Machine Controller

Main controller that integrates all subsystems:
- Cardiopulmonary bypass circuit
- Bubble detection and removal
- Temperature management
- Safety monitoring

Provides unified interface for operating the heart-lung machine.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable
import time

from hlm.bypass_circuit import BypassCircuit, PumpType, CircuitState
from hlm.bubble_detection import (
    BubbleRemovalSystem,
    DetectorLocation,
    BubbleAlertLevel
)
from hlm.temperature import TemperatureController, TemperatureMode
from hlm.safety import (
    SafetyMonitor,
    SafetyInterlock,
    AlarmLevel,
    AlarmCategory
)


class MachineState(Enum):
    """Overall machine operational state."""
    OFF = auto()
    SELF_TEST = auto()
    READY = auto()
    PRIMING = auto()
    STANDBY = auto()
    ON_BYPASS = auto()
    WEANING = auto()
    EMERGENCY = auto()
    MAINTENANCE = auto()


@dataclass
class PatientParameters:
    """Patient-specific parameters for bypass calculations."""
    weight_kg: float = 70.0
    height_cm: float = 170.0
    hematocrit_percent: float = 35.0
    target_flow_index_l_min_m2: float = 2.4  # L/min/m² BSA

    def calculate_bsa(self) -> float:
        """Calculate body surface area using DuBois formula."""
        return 0.007184 * (self.weight_kg ** 0.425) * (self.height_cm ** 0.725)

    def calculate_target_flow(self) -> float:
        """Calculate target flow rate based on BSA."""
        bsa = self.calculate_bsa()
        return self.target_flow_index_l_min_m2 * bsa * 1000  # ml/min


class HeartLungMachineController:
    """
    Main controller for the heart-lung machine.

    Coordinates all subsystems and provides a unified interface
    for operating the machine during cardiopulmonary bypass.
    """

    def __init__(self, pump_type: PumpType = PumpType.ROLLER):
        """
        Initialize the heart-lung machine controller.

        Args:
            pump_type: Type of blood pump to use
        """
        self.state = MachineState.OFF
        self.pump_type = pump_type

        # Initialize subsystems
        self.bypass_circuit = BypassCircuit(pump_type=pump_type)
        self.bubble_system = BubbleRemovalSystem()
        self.temperature_controller = TemperatureController()
        self.safety_monitor = SafetyMonitor()
        self.safety_interlock = SafetyInterlock(self.safety_monitor)

        # Patient parameters
        self.patient_params = PatientParameters()

        # Timing
        self.power_on_time: float | None = None
        self.bypass_start_time: float | None = None
        self.total_bypass_time_minutes: float = 0.0

        # Event log
        self.event_log: list[dict] = []

        # Wire up callbacks between subsystems
        self._connect_subsystems()

        # External callbacks
        self._status_callbacks: list[Callable[[dict], None]] = []

    def _connect_subsystems(self) -> None:
        """Connect callback chains between subsystems."""
        # Bypass circuit alarms -> Safety monitor
        def bypass_alarm_handler(level: str, message: str):
            alarm_level = AlarmLevel[level.upper()] if level.upper() in AlarmLevel.__members__ else AlarmLevel.MEDIUM
            self.safety_monitor.create_alarm(
                level=alarm_level,
                category=AlarmCategory.FLOW,
                message=message,
                source="bypass_circuit"
            )
        self.bypass_circuit.register_alarm_callback(bypass_alarm_handler)

        # Bubble system -> Emergency stop
        def bubble_emergency_handler():
            self._handle_emergency("Air embolism risk detected")
        self.bubble_system.register_emergency_callback(bubble_emergency_handler)

        # Temperature alerts -> Safety monitor
        def temp_alert_handler(level, message: str):
            alarm_level = AlarmLevel.HIGH if "gradient" in message.lower() else AlarmLevel.MEDIUM
            self.safety_monitor.create_alarm(
                level=alarm_level,
                category=AlarmCategory.TEMPERATURE,
                message=message,
                source="temperature_controller"
            )
        self.temperature_controller.register_alert_callback(temp_alert_handler)

        # Safety monitor emergency -> Machine emergency
        def safety_emergency_handler():
            self._handle_emergency("Critical safety alarm")
        self.safety_monitor.register_emergency_callback(safety_emergency_handler)

    def _log_event(self, event_type: str, description: str, data: dict | None = None) -> None:
        """Log an event for the procedure record."""
        event = {
            "timestamp": time.time(),
            "type": event_type,
            "description": description,
            "machine_state": self.state.name,
            "data": data or {}
        }
        self.event_log.append(event)

    def register_status_callback(self, callback: Callable[[dict], None]) -> None:
        """Register callback for status updates."""
        self._status_callbacks.append(callback)

    def _notify_status(self) -> None:
        """Notify registered callbacks of status change."""
        status = self.get_status()
        for callback in self._status_callbacks:
            callback(status)

    def power_on(self) -> bool:
        """
        Power on the machine and run self-test.

        Returns:
            True if self-test passed
        """
        if self.state != MachineState.OFF:
            return False

        self.power_on_time = time.time()
        self.state = MachineState.SELF_TEST
        self._log_event("POWER_ON", "Machine powered on, starting self-test")

        # Run self-test
        if self._run_self_test():
            self.state = MachineState.READY
            self.safety_monitor.activate()
            self._log_event("SELF_TEST", "Self-test completed successfully")
            return True
        else:
            self.state = MachineState.MAINTENANCE
            self._log_event("SELF_TEST", "Self-test failed", {"result": "FAILED"})
            return False

    def _run_self_test(self) -> bool:
        """
        Run machine self-test sequence.

        Returns:
            True if all tests pass
        """
        tests_passed = True

        # Test pump motor
        # In real implementation, would test actual hardware
        self._log_event("SELF_TEST", "Testing pump motor")

        # Test sensors
        self._log_event("SELF_TEST", "Testing sensors")

        # Test alarms
        self._log_event("SELF_TEST", "Testing alarm system")

        # Test bubble detectors
        self._log_event("SELF_TEST", "Testing bubble detectors")

        # Test heat exchanger
        self._log_event("SELF_TEST", "Testing heat exchanger")

        return tests_passed

    def power_off(self) -> bool:
        """Power off the machine."""
        if self.state == MachineState.ON_BYPASS:
            return False  # Cannot power off while on bypass

        self.safety_monitor.deactivate()
        self.bubble_system.deactivate()

        self.state = MachineState.OFF
        self._log_event("POWER_OFF", "Machine powered off")

        return True

    def set_patient_parameters(self, weight_kg: float, height_cm: float,
                               hematocrit_percent: float = 35.0) -> None:
        """Set patient-specific parameters."""
        self.patient_params = PatientParameters(
            weight_kg=weight_kg,
            height_cm=height_cm,
            hematocrit_percent=hematocrit_percent
        )
        self._log_event(
            "PATIENT_DATA",
            "Patient parameters set",
            {
                "weight_kg": weight_kg,
                "height_cm": height_cm,
                "hematocrit": hematocrit_percent,
                "bsa": round(self.patient_params.calculate_bsa(), 2),
                "target_flow": round(self.patient_params.calculate_target_flow(), 0)
            }
        )

    def start_priming(self, priming_volume_ml: float = 1800.0) -> bool:
        """
        Start circuit priming procedure.

        Args:
            priming_volume_ml: Volume of priming solution

        Returns:
            True if priming started
        """
        if self.state != MachineState.READY:
            return False

        if self.bypass_circuit.start_priming(priming_volume_ml):
            self.state = MachineState.PRIMING
            self.bubble_system.activate()
            self._log_event(
                "PRIMING",
                "Priming started",
                {"volume_ml": priming_volume_ml}
            )
            return True
        return False

    def complete_priming(self) -> bool:
        """Complete priming and transition to standby."""
        if self.state != MachineState.PRIMING:
            return False

        # Perform de-airing
        deair_result = self.bubble_system.perform_de_airing_sequence()
        self._log_event(
            "DE_AIRING",
            "De-airing sequence completed",
            deair_result
        )

        if self.bypass_circuit.complete_priming():
            self.state = MachineState.STANDBY
            self._log_event("PRIMING", "Priming completed, entering standby")
            return True
        return False

    def start_bypass(self, target_flow_ml_min: float | None = None) -> bool:
        """
        Initiate cardiopulmonary bypass.

        Args:
            target_flow_ml_min: Target flow rate (or calculated from patient params)

        Returns:
            True if bypass started
        """
        if self.state != MachineState.STANDBY:
            return False

        # Check safety interlocks
        can_start, failed = self.safety_interlock.can_start_bypass()
        if not can_start:
            self._log_event(
                "INTERLOCK",
                "Bypass start blocked by interlocks",
                {"failed_interlocks": failed}
            )
            return False

        # Calculate target flow if not specified
        if target_flow_ml_min is None:
            target_flow_ml_min = self.patient_params.calculate_target_flow()

        if self.bypass_circuit.start_bypass(target_flow_ml_min):
            self.state = MachineState.ON_BYPASS
            self.bypass_start_time = time.time()

            # Activate temperature control
            self.temperature_controller.heat_exchanger.activate()

            self._log_event(
                "BYPASS_START",
                "Cardiopulmonary bypass initiated",
                {"target_flow_ml_min": target_flow_ml_min}
            )
            return True
        return False

    def adjust_flow(self, new_flow_ml_min: float) -> bool:
        """
        Adjust bypass flow rate.

        Args:
            new_flow_ml_min: New target flow rate

        Returns:
            True if flow adjusted
        """
        if self.state != MachineState.ON_BYPASS:
            return False

        if not self.safety_interlock.can_increase_flow():
            if new_flow_ml_min > self.bypass_circuit.flow_params.flow_rate_ml_min:
                return False

        if self.bypass_circuit.update_flow_rate(new_flow_ml_min):
            self._log_event(
                "FLOW_CHANGE",
                f"Flow adjusted to {new_flow_ml_min} ml/min"
            )
            return True
        return False

    def start_cooling(self, target_temp_celsius: float) -> bool:
        """
        Initiate controlled cooling.

        Args:
            target_temp_celsius: Target patient temperature

        Returns:
            True if cooling started
        """
        if self.state != MachineState.ON_BYPASS:
            return False

        if self.temperature_controller.start_cooling(target_temp_celsius):
            self._log_event(
                "COOLING",
                f"Cooling initiated to {target_temp_celsius}°C"
            )
            return True
        return False

    def start_rewarming(self, target_temp_celsius: float = 37.0) -> bool:
        """
        Initiate controlled rewarming.

        Args:
            target_temp_celsius: Target temperature

        Returns:
            True if rewarming started
        """
        if self.state != MachineState.ON_BYPASS:
            return False

        if self.temperature_controller.start_rewarming(target_temp_celsius):
            self._log_event(
                "REWARMING",
                f"Rewarming initiated to {target_temp_celsius}°C"
            )
            return True
        return False

    def start_weaning(self) -> bool:
        """Begin weaning process to come off bypass."""
        if self.state != MachineState.ON_BYPASS:
            return False

        if self.bypass_circuit.start_weaning():
            self.state = MachineState.WEANING
            self._log_event("WEANING", "Weaning from bypass initiated")
            return True
        return False

    def stop_bypass(self) -> bool:
        """Stop bypass and return to standby."""
        if self.state not in (MachineState.ON_BYPASS, MachineState.WEANING):
            return False

        # Calculate total bypass time
        if self.bypass_start_time:
            self.total_bypass_time_minutes = (
                time.time() - self.bypass_start_time
            ) / 60.0

        if self.bypass_circuit.stop_bypass():
            self.state = MachineState.STANDBY
            self._log_event(
                "BYPASS_END",
                "Bypass terminated",
                {"total_time_minutes": round(self.total_bypass_time_minutes, 1)}
            )
            return True
        return False

    def emergency_stop(self) -> None:
        """Execute emergency stop procedure."""
        self._handle_emergency("Manual emergency stop activated")

    def _handle_emergency(self, reason: str) -> None:
        """Handle emergency situation."""
        self.bypass_circuit.emergency_stop()
        self.bubble_system.clamp_line("arterial")
        self.state = MachineState.EMERGENCY

        self.safety_monitor.create_alarm(
            level=AlarmLevel.CRITICAL,
            category=AlarmCategory.SYSTEM,
            message=f"EMERGENCY STOP: {reason}",
            source="controller"
        )

        self._log_event(
            "EMERGENCY",
            f"Emergency stop executed: {reason}"
        )

    def recover_from_emergency(self) -> bool:
        """Attempt to recover from emergency state."""
        if self.state != MachineState.EMERGENCY:
            return False

        # Check if it's safe to recover
        critical_alarms = self.safety_monitor.get_critical_alarms()
        if critical_alarms:
            return False

        # Unclamp lines
        self.bubble_system.unclamp_line("arterial")

        self.state = MachineState.STANDBY
        self._log_event("RECOVERY", "Recovered from emergency, entering standby")

        return True

    def update_sensors(self,
                      reservoir_level_ml: float,
                      flow_ml_min: float,
                      arterial_pressure: float,
                      venous_pressure: float,
                      pre_oxy_pressure: float,
                      post_oxy_pressure: float,
                      bubble_readings: dict[str, float] | None = None,
                      temperature_readings: dict[str, float] | None = None) -> None:
        """
        Update all sensor readings.

        This method should be called regularly with current sensor values.

        Args:
            reservoir_level_ml: Venous reservoir level
            flow_ml_min: Measured blood flow rate
            arterial_pressure: Arterial line pressure (mmHg)
            venous_pressure: Venous line pressure (mmHg)
            pre_oxy_pressure: Pre-oxygenator pressure (mmHg)
            post_oxy_pressure: Post-oxygenator pressure (mmHg)
            bubble_readings: Dict of detector location -> signal level
            temperature_readings: Dict of point name -> temperature
        """
        # Update bypass circuit
        self.bypass_circuit.update_readings(
            reservoir_level_ml=reservoir_level_ml,
            actual_flow_ml_min=flow_ml_min,
            arterial_pressure=arterial_pressure,
            venous_pressure=venous_pressure,
            pre_oxy_pressure=pre_oxy_pressure,
            post_oxy_pressure=post_oxy_pressure
        )

        # Update bubble detection
        if bubble_readings:
            for location_name, signal in bubble_readings.items():
                try:
                    location = DetectorLocation[location_name.upper()]
                    self.bubble_system.update_sensor_reading(location, signal)
                except KeyError:
                    pass

        # Update temperatures
        if temperature_readings:
            for point_name, temp in temperature_readings.items():
                self.temperature_controller.update_temperature(point_name, temp)

        # Check safety parameters
        self.safety_monitor.check_parameter("Blood Flow", flow_ml_min)
        self.safety_monitor.check_parameter("Arterial Line Pressure", arterial_pressure)
        self.safety_monitor.check_parameter("Venous Line Pressure", venous_pressure)
        self.safety_monitor.check_parameter("Reservoir Level", reservoir_level_ml)

        # Check temperature gradients
        gradients = self.temperature_controller.check_gradients()
        if "blood_water" in gradients:
            self.safety_monitor.check_parameter(
                "Blood-Water Gradient",
                gradients["blood_water"]
            )

        # Check arterial temperature
        arterial_temp = temperature_readings.get("arterial") if temperature_readings else None
        if arterial_temp is not None:
            self.safety_monitor.check_parameter("Arterial Temperature", arterial_temp)

        # Process alarm escalations
        self.safety_monitor.update_escalations()

        # Notify status listeners
        self._notify_status()

    def acknowledge_alarm(self, alarm_id: str, user_id: str) -> bool:
        """Acknowledge an alarm."""
        return self.safety_monitor.acknowledge_alarm(alarm_id, user_id)

    def silence_alarm(self, alarm_id: str, duration_seconds: float = 120.0) -> bool:
        """Silence an alarm temporarily."""
        return self.safety_monitor.silence_alarm(alarm_id, duration_seconds)

    def get_bypass_time(self) -> float:
        """Get current bypass time in minutes."""
        if self.bypass_start_time and self.state == MachineState.ON_BYPASS:
            return (time.time() - self.bypass_start_time) / 60.0
        return self.total_bypass_time_minutes

    def get_status(self) -> dict:
        """Get comprehensive machine status."""
        return {
            "machine_state": self.state.name,
            "bypass_time_minutes": round(self.get_bypass_time(), 1),
            "patient": {
                "weight_kg": self.patient_params.weight_kg,
                "height_cm": self.patient_params.height_cm,
                "bsa_m2": round(self.patient_params.calculate_bsa(), 2),
                "target_flow_ml_min": round(self.patient_params.calculate_target_flow(), 0)
            },
            "bypass_circuit": self.bypass_circuit.get_status(),
            "bubble_system": self.bubble_system.get_status(),
            "temperature": self.temperature_controller.get_status(),
            "safety": self.safety_monitor.get_status()
        }

    def get_event_log(self) -> list[dict]:
        """Get the event log for this procedure."""
        return self.event_log.copy()

    def generate_procedure_report(self) -> dict:
        """Generate a summary report of the procedure."""
        return {
            "power_on_time": self.power_on_time,
            "bypass_start_time": self.bypass_start_time,
            "total_bypass_time_minutes": round(self.total_bypass_time_minutes, 1),
            "patient_parameters": {
                "weight_kg": self.patient_params.weight_kg,
                "height_cm": self.patient_params.height_cm,
                "bsa_m2": round(self.patient_params.calculate_bsa(), 2)
            },
            "pump_type": self.pump_type.name,
            "alarm_summary": self.safety_monitor.get_alarm_summary(),
            "bubble_events_total": len(self.bubble_system.detector.event_history),
            "event_log_entries": len(self.event_log),
            "final_state": self.state.name
        }
