"""
Temperature Management System

Temperature control during cardiopulmonary bypass is critical for:
- Myocardial protection through hypothermia
- Reduced metabolic demand during circulatory arrest
- Safe rewarming without neurological injury

This module implements:
- Heat exchanger control
- Multi-point temperature monitoring
- Safe cooling and rewarming protocols
- Temperature gradient protection
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time


class TemperatureMode(Enum):
    """Operating modes for temperature management."""
    NORMOTHERMIC = auto()      # Maintain normal temperature (36-37°C)
    MILD_HYPOTHERMIA = auto()   # 32-34°C
    MODERATE_HYPOTHERMIA = auto()  # 28-32°C
    DEEP_HYPOTHERMIA = auto()   # 20-28°C
    PROFOUND_HYPOTHERMIA = auto()  # <20°C (for circulatory arrest)
    REWARMING = auto()          # Active rewarming phase


class TemperatureAlertLevel(Enum):
    """Alert levels for temperature abnormalities."""
    NORMAL = auto()
    WARNING = auto()
    CRITICAL = auto()
    EMERGENCY = auto()


@dataclass
class TemperatureReading:
    """Temperature reading from a monitoring point."""
    location: str
    value_celsius: float
    timestamp: float = field(default_factory=time.time)
    is_valid: bool = True

    def to_fahrenheit(self) -> float:
        """Convert to Fahrenheit."""
        return (self.value_celsius * 9/5) + 32


@dataclass
class TemperatureLimits:
    """Safety limits for temperature parameters."""
    # Absolute limits
    min_patient_temp_celsius: float = 15.0  # Minimum safe for deep hypothermia
    max_patient_temp_celsius: float = 38.5  # Maximum to avoid hyperthermia

    # Heat exchanger water limits
    min_water_temp_celsius: float = 4.0
    max_water_temp_celsius: float = 42.0

    # Gradient limits (to prevent tissue damage)
    max_blood_water_gradient_celsius: float = 10.0  # Blood to water
    max_arterial_venous_gradient_celsius: float = 10.0
    max_nasopharyngeal_rectal_gradient_celsius: float = 10.0

    # Rate limits
    max_cooling_rate_celsius_per_min: float = 1.0
    max_rewarming_rate_celsius_per_min: float = 0.5  # Slower to prevent injury


@dataclass
class TemperaturePoint:
    """Monitoring point for temperature measurement."""
    name: str
    location: str
    current_temp_celsius: float = 37.0
    is_active: bool = True
    sensor_type: str = "thermistor"
    last_update: float = field(default_factory=time.time)

    # Calibration
    offset_celsius: float = 0.0

    def update(self, raw_temp: float) -> float:
        """Update temperature reading with calibration."""
        self.current_temp_celsius = raw_temp + self.offset_celsius
        self.last_update = time.time()
        return self.current_temp_celsius

    def get_reading(self) -> TemperatureReading:
        """Get current reading as TemperatureReading object."""
        return TemperatureReading(
            location=self.location,
            value_celsius=self.current_temp_celsius,
            timestamp=self.last_update,
            is_valid=self.is_active
        )


class HeatExchanger:
    """
    Heat exchanger for blood temperature control.

    Uses water circulation to transfer heat to/from blood.
    Critical for cooling and rewarming during bypass.
    """

    def __init__(self, max_flow_l_min: float = 20.0):
        """Initialize heat exchanger."""
        self.is_active: bool = False
        self.max_flow_l_min = max_flow_l_min

        # Water circuit parameters
        self.water_flow_l_min: float = 0.0
        self.water_inlet_temp_celsius: float = 37.0
        self.water_outlet_temp_celsius: float = 37.0
        self.target_water_temp_celsius: float = 37.0

        # Blood side parameters
        self.blood_inlet_temp_celsius: float = 37.0
        self.blood_outlet_temp_celsius: float = 37.0

        # Performance metrics
        self.heat_transfer_efficiency: float = 0.95
        self.calculated_heat_transfer_watts: float = 0.0

        # Safety limits
        self.limits = TemperatureLimits()

        # Callbacks
        self._alert_callbacks: list[Callable[[TemperatureAlertLevel, str], None]] = []

    def register_alert_callback(
        self, callback: Callable[[TemperatureAlertLevel, str], None]
    ) -> None:
        """Register callback for temperature alerts."""
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, level: TemperatureAlertLevel, message: str) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            callback(level, message)

    def activate(self) -> bool:
        """Activate heat exchanger."""
        self.is_active = True
        return True

    def deactivate(self) -> None:
        """Deactivate heat exchanger."""
        self.is_active = False
        self.water_flow_l_min = 0.0

    def set_target_temperature(self, temp_celsius: float) -> bool:
        """
        Set target water temperature.

        Args:
            temp_celsius: Target temperature

        Returns:
            True if target is within safe limits
        """
        if (self.limits.min_water_temp_celsius <= temp_celsius <=
            self.limits.max_water_temp_celsius):
            self.target_water_temp_celsius = temp_celsius
            return True
        return False

    def set_water_flow(self, flow_l_min: float) -> bool:
        """Set water flow rate."""
        if 0 <= flow_l_min <= self.max_flow_l_min:
            self.water_flow_l_min = flow_l_min
            return True
        return False

    def update_readings(self,
                       water_inlet: float,
                       water_outlet: float,
                       blood_inlet: float,
                       blood_outlet: float) -> None:
        """Update all temperature readings."""
        self.water_inlet_temp_celsius = water_inlet
        self.water_outlet_temp_celsius = water_outlet
        self.blood_inlet_temp_celsius = blood_inlet
        self.blood_outlet_temp_celsius = blood_outlet

        # Calculate heat transfer
        self._calculate_heat_transfer()

        # Check safety gradients
        self._check_gradients()

    def _calculate_heat_transfer(self) -> None:
        """Calculate heat transfer rate."""
        if self.water_flow_l_min <= 0:
            self.calculated_heat_transfer_watts = 0.0
            return

        # Q = m * c * dT
        # Water specific heat: 4.186 kJ/(kg·K)
        # Convert L/min to kg/s (assuming water density ~1 kg/L)
        mass_flow_kg_s = self.water_flow_l_min / 60.0
        temp_diff = self.water_inlet_temp_celsius - self.water_outlet_temp_celsius
        self.calculated_heat_transfer_watts = mass_flow_kg_s * 4186 * temp_diff

    def _check_gradients(self) -> None:
        """Check temperature gradients for safety."""
        blood_water_gradient = abs(
            self.blood_inlet_temp_celsius - self.water_inlet_temp_celsius
        )

        if blood_water_gradient > self.limits.max_blood_water_gradient_celsius:
            self._trigger_alert(
                TemperatureAlertLevel.CRITICAL,
                f"Blood-water gradient too high: {blood_water_gradient:.1f}°C"
            )

    def get_blood_water_gradient(self) -> float:
        """Get current blood-water temperature gradient."""
        return abs(self.blood_inlet_temp_celsius - self.water_inlet_temp_celsius)

    def get_status(self) -> dict:
        """Get heat exchanger status."""
        return {
            "is_active": self.is_active,
            "water_flow_l_min": self.water_flow_l_min,
            "target_temp_celsius": self.target_water_temp_celsius,
            "water_inlet_celsius": self.water_inlet_temp_celsius,
            "water_outlet_celsius": self.water_outlet_temp_celsius,
            "blood_inlet_celsius": self.blood_inlet_temp_celsius,
            "blood_outlet_celsius": self.blood_outlet_temp_celsius,
            "blood_water_gradient_celsius": round(self.get_blood_water_gradient(), 1),
            "heat_transfer_watts": round(self.calculated_heat_transfer_watts, 1)
        }


class TemperatureController:
    """
    Comprehensive temperature management controller.

    Coordinates:
    - Multiple temperature monitoring points
    - Heat exchanger control
    - Cooling and rewarming protocols
    - Safety gradient monitoring
    """

    def __init__(self):
        """Initialize temperature controller."""
        self.mode = TemperatureMode.NORMOTHERMIC
        self.target_patient_temp_celsius: float = 37.0
        self.heat_exchanger = HeatExchanger()
        self.limits = TemperatureLimits()

        # Temperature monitoring points
        self.monitoring_points: dict[str, TemperaturePoint] = {}
        self._initialize_monitoring_points()

        # Timing
        self.cooling_start_time: float | None = None
        self.rewarming_start_time: float | None = None

        # History for rate calculation
        self.temperature_history: list[tuple[float, float]] = []  # (time, temp)
        self.max_history_size: int = 100

        # Callbacks
        self._alert_callbacks: list[Callable[[TemperatureAlertLevel, str], None]] = []

    def _initialize_monitoring_points(self) -> None:
        """Set up standard temperature monitoring points."""
        points = [
            ("arterial", "Arterial Line"),
            ("venous", "Venous Line"),
            ("nasopharyngeal", "Nasopharyngeal"),
            ("rectal", "Rectal/Core"),
            ("bladder", "Bladder"),
            ("myocardial", "Myocardial"),
            ("water_inlet", "Heat Exchanger Water Inlet"),
            ("water_outlet", "Heat Exchanger Water Outlet"),
        ]

        for name, location in points:
            self.monitoring_points[name] = TemperaturePoint(
                name=name,
                location=location
            )

    def register_alert_callback(
        self, callback: Callable[[TemperatureAlertLevel, str], None]
    ) -> None:
        """Register callback for temperature alerts."""
        self._alert_callbacks.append(callback)
        self.heat_exchanger.register_alert_callback(callback)

    def _trigger_alert(self, level: TemperatureAlertLevel, message: str) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            callback(level, message)

    def update_temperature(self, point_name: str, temp_celsius: float) -> bool:
        """
        Update a temperature monitoring point.

        Args:
            point_name: Name of monitoring point
            temp_celsius: Temperature reading

        Returns:
            True if update successful
        """
        if point_name not in self.monitoring_points:
            return False

        point = self.monitoring_points[point_name]
        point.update(temp_celsius)

        # Track arterial temperature for rate calculations
        if point_name == "arterial":
            self._record_temperature(temp_celsius)
            self._check_temperature_safety(temp_celsius)

        return True

    def _record_temperature(self, temp_celsius: float) -> None:
        """Record temperature for trend analysis."""
        self.temperature_history.append((time.time(), temp_celsius))

        # Limit history size
        if len(self.temperature_history) > self.max_history_size:
            self.temperature_history = self.temperature_history[-self.max_history_size:]

    def _check_temperature_safety(self, temp_celsius: float) -> None:
        """Check patient temperature against safety limits."""
        if temp_celsius > self.limits.max_patient_temp_celsius:
            self._trigger_alert(
                TemperatureAlertLevel.CRITICAL,
                f"Patient temperature too high: {temp_celsius:.1f}°C"
            )
        elif temp_celsius < self.limits.min_patient_temp_celsius:
            self._trigger_alert(
                TemperatureAlertLevel.CRITICAL,
                f"Patient temperature too low: {temp_celsius:.1f}°C"
            )

    def get_temperature_rate(self) -> float | None:
        """
        Calculate temperature change rate in °C/min.

        Returns:
            Rate of change or None if insufficient data
        """
        if len(self.temperature_history) < 2:
            return None

        # Use last 5 minutes of data
        cutoff_time = time.time() - 300  # 5 minutes
        recent = [(t, temp) for t, temp in self.temperature_history if t > cutoff_time]

        if len(recent) < 2:
            return None

        # Linear regression for rate
        time_start, temp_start = recent[0]
        time_end, temp_end = recent[-1]

        time_diff_min = (time_end - time_start) / 60.0
        if time_diff_min <= 0:
            return None

        return (temp_end - temp_start) / time_diff_min

    def start_cooling(self, target_temp_celsius: float) -> bool:
        """
        Initiate controlled cooling protocol.

        Args:
            target_temp_celsius: Target temperature

        Returns:
            True if cooling initiated successfully
        """
        if target_temp_celsius >= self.get_current_patient_temp():
            return False

        if target_temp_celsius < self.limits.min_patient_temp_celsius:
            self._trigger_alert(
                TemperatureAlertLevel.WARNING,
                f"Target {target_temp_celsius}°C below safe minimum"
            )
            return False

        self.target_patient_temp_celsius = target_temp_celsius
        self.cooling_start_time = time.time()

        # Determine mode based on target
        if target_temp_celsius >= 32:
            self.mode = TemperatureMode.MILD_HYPOTHERMIA
        elif target_temp_celsius >= 28:
            self.mode = TemperatureMode.MODERATE_HYPOTHERMIA
        elif target_temp_celsius >= 20:
            self.mode = TemperatureMode.DEEP_HYPOTHERMIA
        else:
            self.mode = TemperatureMode.PROFOUND_HYPOTHERMIA

        # Set heat exchanger for cooling
        self.heat_exchanger.activate()

        return True

    def start_rewarming(self, target_temp_celsius: float = 37.0) -> bool:
        """
        Initiate controlled rewarming protocol.

        Args:
            target_temp_celsius: Target temperature (default normothermic)

        Returns:
            True if rewarming initiated successfully
        """
        current_temp = self.get_current_patient_temp()

        if target_temp_celsius <= current_temp:
            return False

        if target_temp_celsius > self.limits.max_patient_temp_celsius:
            return False

        self.target_patient_temp_celsius = target_temp_celsius
        self.rewarming_start_time = time.time()
        self.mode = TemperatureMode.REWARMING

        # Set heat exchanger for warming
        self.heat_exchanger.activate()

        return True

    def adjust_heat_exchanger_for_rate(self) -> float:
        """
        Calculate and set optimal heat exchanger temperature for safe rate.

        Returns:
            Recommended water temperature
        """
        current_temp = self.get_current_patient_temp()
        current_rate = self.get_temperature_rate()

        if self.mode == TemperatureMode.REWARMING:
            max_rate = self.limits.max_rewarming_rate_celsius_per_min
            max_water_temp = min(
                current_temp + self.limits.max_blood_water_gradient_celsius,
                self.limits.max_water_temp_celsius
            )

            if current_rate is not None and current_rate > max_rate:
                # Reduce water temperature
                recommended = current_temp + (self.limits.max_blood_water_gradient_celsius * 0.5)
            else:
                recommended = max_water_temp

        else:  # Cooling
            max_rate = self.limits.max_cooling_rate_celsius_per_min
            min_water_temp = max(
                current_temp - self.limits.max_blood_water_gradient_celsius,
                self.limits.min_water_temp_celsius
            )

            if current_rate is not None and abs(current_rate) > max_rate:
                # Reduce gradient
                recommended = current_temp - (self.limits.max_blood_water_gradient_celsius * 0.5)
            else:
                recommended = min_water_temp

        self.heat_exchanger.set_target_temperature(recommended)
        return recommended

    def get_current_patient_temp(self) -> float:
        """
        Get best estimate of current patient core temperature.

        Prioritizes nasopharyngeal, then venous, then arterial.
        """
        priority_points = ["nasopharyngeal", "rectal", "venous", "arterial"]

        for point_name in priority_points:
            if point_name in self.monitoring_points:
                point = self.monitoring_points[point_name]
                if point.is_active:
                    return point.current_temp_celsius

        # Fallback to arterial line
        if "arterial" in self.monitoring_points:
            return self.monitoring_points["arterial"].current_temp_celsius

        return 37.0  # Default if no readings

    def check_gradients(self) -> dict[str, float]:
        """
        Check all critical temperature gradients.

        Returns:
            Dictionary of gradient values
        """
        gradients = {}

        # Arterial-venous gradient
        if "arterial" in self.monitoring_points and "venous" in self.monitoring_points:
            av_gradient = abs(
                self.monitoring_points["arterial"].current_temp_celsius -
                self.monitoring_points["venous"].current_temp_celsius
            )
            gradients["arterial_venous"] = av_gradient

            if av_gradient > self.limits.max_arterial_venous_gradient_celsius:
                self._trigger_alert(
                    TemperatureAlertLevel.WARNING,
                    f"Arterial-venous gradient high: {av_gradient:.1f}°C"
                )

        # Nasopharyngeal-rectal gradient
        if "nasopharyngeal" in self.monitoring_points and "rectal" in self.monitoring_points:
            nr_gradient = abs(
                self.monitoring_points["nasopharyngeal"].current_temp_celsius -
                self.monitoring_points["rectal"].current_temp_celsius
            )
            gradients["nasopharyngeal_rectal"] = nr_gradient

            if nr_gradient > self.limits.max_nasopharyngeal_rectal_gradient_celsius:
                self._trigger_alert(
                    TemperatureAlertLevel.WARNING,
                    f"NP-rectal gradient high: {nr_gradient:.1f}°C"
                )

        # Blood-water gradient
        gradients["blood_water"] = self.heat_exchanger.get_blood_water_gradient()

        return gradients

    def is_at_target(self, tolerance_celsius: float = 0.5) -> bool:
        """Check if patient is at target temperature."""
        current = self.get_current_patient_temp()
        return abs(current - self.target_patient_temp_celsius) <= tolerance_celsius

    def get_time_to_target_estimate(self) -> float | None:
        """
        Estimate time to reach target temperature in minutes.

        Returns:
            Estimated minutes or None if cannot estimate
        """
        rate = self.get_temperature_rate()
        if rate is None or abs(rate) < 0.01:
            return None

        current = self.get_current_patient_temp()
        temp_diff = self.target_patient_temp_celsius - current

        # Check if rate is in correct direction
        if (temp_diff > 0 and rate < 0) or (temp_diff < 0 and rate > 0):
            return None  # Moving wrong direction

        return abs(temp_diff / rate)

    def get_status(self) -> dict:
        """Get comprehensive temperature management status."""
        gradients = self.check_gradients()
        rate = self.get_temperature_rate()
        time_to_target = self.get_time_to_target_estimate()

        return {
            "mode": self.mode.name,
            "target_temp_celsius": self.target_patient_temp_celsius,
            "current_patient_temp_celsius": round(self.get_current_patient_temp(), 1),
            "is_at_target": self.is_at_target(),
            "rate_celsius_per_min": round(rate, 2) if rate else None,
            "estimated_time_to_target_min": round(time_to_target, 1) if time_to_target else None,
            "gradients": {k: round(v, 1) for k, v in gradients.items()},
            "heat_exchanger": self.heat_exchanger.get_status(),
            "monitoring_points": {
                name: {
                    "location": point.location,
                    "temp_celsius": round(point.current_temp_celsius, 1),
                    "is_active": point.is_active
                }
                for name, point in self.monitoring_points.items()
            }
        }
