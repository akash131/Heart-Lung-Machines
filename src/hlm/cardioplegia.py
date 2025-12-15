"""
Cardioplegia Delivery System

Cardioplegia is a critical component for myocardial protection during cardiac surgery.
This module implements:
- Multiple cardioplegia delivery modes (antegrade, retrograde, combined)
- Temperature-controlled delivery (cold, tepid, warm)
- Ratio control for blood cardioplegia
- Dose tracking and timing
- Pressure monitoring for safe delivery
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time


class CardioplegiaType(Enum):
    """Types of cardioplegia solutions."""
    CRYSTALLOID = auto()      # Pure crystalloid solution
    BLOOD_4_1 = auto()        # 4:1 blood to crystalloid ratio
    BLOOD_8_1 = auto()        # 8:1 blood to crystalloid ratio
    BLOOD_MICROPLEGIA = auto() # High ratio blood cardioplegia
    DEL_NIDO = auto()         # Del Nido single-dose solution
    CUSTODIOL = auto()        # HTK solution (Custodiol)


class DeliveryRoute(Enum):
    """Routes for cardioplegia delivery."""
    ANTEGRADE = auto()        # Via aortic root
    RETROGRADE = auto()       # Via coronary sinus
    COMBINED = auto()         # Both routes
    DIRECT_OSTIAL = auto()    # Direct coronary ostial cannulation


class CardioplegiaTemperature(Enum):
    """Temperature categories for cardioplegia."""
    COLD = auto()             # 4-8°C
    TEPID = auto()            # 20-25°C
    WARM = auto()             # 35-37°C


class DeliveryPhase(Enum):
    """Phases of cardioplegia delivery."""
    INDUCTION = auto()        # Initial arrest dose
    MAINTENANCE = auto()      # Repeat doses
    HOT_SHOT = auto()         # Terminal warm dose before reperfusion
    CONTINUOUS = auto()       # Continuous delivery


@dataclass
class CardioplegiaDose:
    """Record of a cardioplegia dose."""
    dose_number: int
    timestamp: float
    phase: DeliveryPhase
    route: DeliveryRoute
    volume_ml: float
    duration_seconds: float
    temperature_celsius: float
    flow_rate_ml_min: float
    pressure_mmhg: float
    cardioplegia_type: CardioplegiaType
    potassium_meq_l: float = 20.0


@dataclass
class CardioplegiaLimits:
    """Safety limits for cardioplegia delivery."""
    # Pressure limits
    max_antegrade_pressure_mmhg: float = 150.0
    max_retrograde_pressure_mmhg: float = 40.0  # Lower for coronary sinus

    # Flow limits
    max_antegrade_flow_ml_min: float = 350.0
    max_retrograde_flow_ml_min: float = 250.0

    # Temperature limits
    min_cold_temp_celsius: float = 4.0
    max_cold_temp_celsius: float = 10.0
    min_tepid_temp_celsius: float = 18.0
    max_tepid_temp_celsius: float = 28.0
    min_warm_temp_celsius: float = 34.0
    max_warm_temp_celsius: float = 37.5

    # Timing limits
    max_interval_minutes: float = 20.0  # Max time between doses
    min_induction_volume_ml: float = 500.0


@dataclass
class CardioplegiaPump:
    """Cardioplegia delivery pump."""
    name: str
    is_active: bool = False
    rpm: float = 0.0
    max_rpm: float = 500.0
    flow_rate_ml_min: float = 0.0
    occlusion_percent: float = 100.0
    tubing_size_inch: float = 0.25

    def set_flow_rate(self, flow_ml_min: float) -> bool:
        """Set target flow rate."""
        if 0 <= flow_ml_min <= 500:
            self.flow_rate_ml_min = flow_ml_min
            # Calculate RPM based on tubing size
            self.rpm = flow_ml_min / (self.tubing_size_inch * 50)
            return True
        return False

    def start(self) -> None:
        """Start the pump."""
        self.is_active = True

    def stop(self) -> None:
        """Stop the pump."""
        self.is_active = False
        self.flow_rate_ml_min = 0.0
        self.rpm = 0.0


@dataclass
class CardioplegiaHeatExchanger:
    """Heat exchanger for cardioplegia temperature control."""
    is_active: bool = False
    target_temp_celsius: float = 8.0
    actual_temp_celsius: float = 20.0
    water_temp_celsius: float = 4.0

    def set_target_temperature(self, temp: float, mode: CardioplegiaTemperature) -> bool:
        """Set target temperature based on mode."""
        if mode == CardioplegiaTemperature.COLD:
            if 4.0 <= temp <= 10.0:
                self.target_temp_celsius = temp
                self.water_temp_celsius = max(2.0, temp - 4.0)
                return True
        elif mode == CardioplegiaTemperature.TEPID:
            if 18.0 <= temp <= 28.0:
                self.target_temp_celsius = temp
                self.water_temp_celsius = temp - 2.0
                return True
        elif mode == CardioplegiaTemperature.WARM:
            if 34.0 <= temp <= 37.5:
                self.target_temp_celsius = temp
                self.water_temp_celsius = temp + 1.0
                return True
        return False

    def update_actual_temp(self, temp: float) -> None:
        """Update measured temperature."""
        self.actual_temp_celsius = temp


class BloodCardioplegiaMixer:
    """
    Mixer for blood cardioplegia.

    Mixes oxygenated blood with crystalloid cardioplegia
    at specified ratios.
    """

    def __init__(self):
        self.is_active: bool = False
        self.blood_flow_ml_min: float = 0.0
        self.crystalloid_flow_ml_min: float = 0.0
        self.target_ratio: float = 4.0  # Blood:crystalloid ratio
        self.actual_ratio: float = 0.0
        self.potassium_concentration_meq_l: float = 20.0

        # Pumps
        self.blood_pump = CardioplegiaPump(name="blood_pump")
        self.crystalloid_pump = CardioplegiaPump(name="crystalloid_pump")

    def set_ratio(self, ratio: float) -> bool:
        """Set blood to crystalloid ratio."""
        if 1.0 <= ratio <= 20.0:
            self.target_ratio = ratio
            return True
        return False

    def set_total_flow(self, total_flow_ml_min: float) -> None:
        """Set total output flow and calculate component flows."""
        # Calculate flows based on ratio
        # ratio = blood / crystalloid
        # total = blood + crystalloid
        # blood = total * ratio / (ratio + 1)
        self.blood_flow_ml_min = total_flow_ml_min * self.target_ratio / (self.target_ratio + 1)
        self.crystalloid_flow_ml_min = total_flow_ml_min / (self.target_ratio + 1)

        self.blood_pump.set_flow_rate(self.blood_flow_ml_min)
        self.crystalloid_pump.set_flow_rate(self.crystalloid_flow_ml_min)

    def calculate_actual_ratio(self) -> float:
        """Calculate actual ratio from measured flows."""
        if self.crystalloid_flow_ml_min > 0:
            self.actual_ratio = self.blood_flow_ml_min / self.crystalloid_flow_ml_min
        else:
            self.actual_ratio = 0.0
        return self.actual_ratio

    def calculate_final_potassium(self,
                                   crystalloid_k_meq_l: float,
                                   blood_k_meq_l: float = 4.5) -> float:
        """Calculate final potassium concentration in mixture."""
        if self.target_ratio <= 0:
            return crystalloid_k_meq_l

        # Weighted average based on volumes
        total = self.target_ratio + 1
        final_k = (blood_k_meq_l * self.target_ratio + crystalloid_k_meq_l) / total
        self.potassium_concentration_meq_l = final_k
        return final_k

    def start(self) -> None:
        """Start both pumps."""
        self.is_active = True
        self.blood_pump.start()
        self.crystalloid_pump.start()

    def stop(self) -> None:
        """Stop both pumps."""
        self.is_active = False
        self.blood_pump.stop()
        self.crystalloid_pump.stop()


class CardioplegiaDeliverySystem:
    """
    Complete cardioplegia delivery system.

    Coordinates pumps, heat exchanger, mixing, and monitoring
    for safe and effective cardioplegia delivery.
    """

    def __init__(self):
        """Initialize cardioplegia system."""
        self.is_active: bool = False
        self.is_delivering: bool = False

        # Configuration
        self.cardioplegia_type = CardioplegiaType.BLOOD_4_1
        self.delivery_route = DeliveryRoute.ANTEGRADE
        self.temperature_mode = CardioplegiaTemperature.COLD
        self.current_phase = DeliveryPhase.INDUCTION

        # Components
        self.mixer = BloodCardioplegiaMixer()
        self.heat_exchanger = CardioplegiaHeatExchanger()
        self.main_pump = CardioplegiaPump(name="main_delivery_pump")

        # Monitoring
        self.delivery_pressure_mmhg: float = 0.0
        self.delivery_temperature_celsius: float = 20.0
        self.actual_flow_ml_min: float = 0.0

        # Dose tracking
        self.doses: list[CardioplegiaDose] = []
        self.total_volume_delivered_ml: float = 0.0
        self.current_dose_volume_ml: float = 0.0
        self.dose_start_time: float | None = None
        self.last_dose_time: float | None = None

        # Arrest timing
        self.arrest_time: float | None = None
        self.cross_clamp_time: float | None = None

        # Safety
        self.limits = CardioplegiaLimits()

        # Callbacks
        self._alarm_callbacks: list[Callable[[str, str], None]] = []

    def register_alarm_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register alarm callback."""
        self._alarm_callbacks.append(callback)

    def _trigger_alarm(self, level: str, message: str) -> None:
        """Trigger alarm callbacks."""
        for callback in self._alarm_callbacks:
            callback(level, message)

    def configure(self,
                  cardioplegia_type: CardioplegiaType,
                  delivery_route: DeliveryRoute,
                  temperature_mode: CardioplegiaTemperature,
                  blood_ratio: float = 4.0) -> None:
        """Configure cardioplegia delivery parameters."""
        self.cardioplegia_type = cardioplegia_type
        self.delivery_route = delivery_route
        self.temperature_mode = temperature_mode

        # Configure mixer if blood cardioplegia
        if cardioplegia_type in (CardioplegiaType.BLOOD_4_1,
                                  CardioplegiaType.BLOOD_8_1,
                                  CardioplegiaType.BLOOD_MICROPLEGIA):
            self.mixer.set_ratio(blood_ratio)

        # Set temperature target
        temp_targets = {
            CardioplegiaTemperature.COLD: 8.0,
            CardioplegiaTemperature.TEPID: 22.0,
            CardioplegiaTemperature.WARM: 37.0
        }
        self.heat_exchanger.set_target_temperature(
            temp_targets[temperature_mode],
            temperature_mode
        )

    def activate(self) -> None:
        """Activate cardioplegia system."""
        self.is_active = True
        self.heat_exchanger.is_active = True

    def deactivate(self) -> None:
        """Deactivate cardioplegia system."""
        self.stop_delivery()
        self.is_active = False
        self.heat_exchanger.is_active = False

    def start_delivery(self,
                       flow_rate_ml_min: float,
                       phase: DeliveryPhase = DeliveryPhase.MAINTENANCE) -> bool:
        """
        Start cardioplegia delivery.

        Args:
            flow_rate_ml_min: Target flow rate
            phase: Delivery phase

        Returns:
            True if delivery started successfully
        """
        if not self.is_active:
            return False

        # Check pressure limits based on route
        max_pressure = (self.limits.max_retrograde_pressure_mmhg
                       if self.delivery_route == DeliveryRoute.RETROGRADE
                       else self.limits.max_antegrade_pressure_mmhg)

        if self.delivery_pressure_mmhg > max_pressure:
            self._trigger_alarm("warning",
                f"Cardioplegia pressure too high: {self.delivery_pressure_mmhg} mmHg")
            return False

        self.current_phase = phase
        self.is_delivering = True
        self.dose_start_time = time.time()
        self.current_dose_volume_ml = 0.0

        # Configure flow
        if self.cardioplegia_type in (CardioplegiaType.BLOOD_4_1,
                                       CardioplegiaType.BLOOD_8_1,
                                       CardioplegiaType.BLOOD_MICROPLEGIA):
            self.mixer.set_total_flow(flow_rate_ml_min)
            self.mixer.start()
        else:
            self.main_pump.set_flow_rate(flow_rate_ml_min)
            self.main_pump.start()

        return True

    def stop_delivery(self) -> CardioplegiaDose | None:
        """
        Stop cardioplegia delivery and record dose.

        Returns:
            Recorded dose or None
        """
        if not self.is_delivering:
            return None

        self.is_delivering = False
        self.mixer.stop()
        self.main_pump.stop()

        # Record dose
        if self.dose_start_time is not None:
            duration = time.time() - self.dose_start_time
            dose = CardioplegiaDose(
                dose_number=len(self.doses) + 1,
                timestamp=self.dose_start_time,
                phase=self.current_phase,
                route=self.delivery_route,
                volume_ml=self.current_dose_volume_ml,
                duration_seconds=duration,
                temperature_celsius=self.delivery_temperature_celsius,
                flow_rate_ml_min=self.actual_flow_ml_min,
                pressure_mmhg=self.delivery_pressure_mmhg,
                cardioplegia_type=self.cardioplegia_type,
                potassium_meq_l=self.mixer.potassium_concentration_meq_l
            )
            self.doses.append(dose)
            self.total_volume_delivered_ml += self.current_dose_volume_ml
            self.last_dose_time = time.time()

            return dose

        return None

    def record_cardiac_arrest(self) -> None:
        """Record time of cardiac arrest."""
        self.arrest_time = time.time()

    def record_cross_clamp(self) -> None:
        """Record aortic cross-clamp time."""
        self.cross_clamp_time = time.time()

    def get_cross_clamp_duration(self) -> float | None:
        """Get cross-clamp duration in minutes."""
        if self.cross_clamp_time is None:
            return None
        return (time.time() - self.cross_clamp_time) / 60.0

    def get_time_since_last_dose(self) -> float | None:
        """Get time since last cardioplegia dose in minutes."""
        if self.last_dose_time is None:
            return None
        return (time.time() - self.last_dose_time) / 60.0

    def needs_redose(self) -> bool:
        """Check if cardioplegia redose is needed."""
        time_since = self.get_time_since_last_dose()
        if time_since is None:
            return False
        return time_since >= self.limits.max_interval_minutes

    def update_readings(self,
                       pressure_mmhg: float,
                       temperature_celsius: float,
                       flow_ml_min: float) -> None:
        """Update sensor readings."""
        self.delivery_pressure_mmhg = pressure_mmhg
        self.delivery_temperature_celsius = temperature_celsius
        self.actual_flow_ml_min = flow_ml_min
        self.heat_exchanger.update_actual_temp(temperature_celsius)

        # Accumulate volume if delivering
        if self.is_delivering:
            # Approximate volume from flow (called periodically)
            self.current_dose_volume_ml += flow_ml_min / 60.0  # Assumes 1 second update

        # Check for alarms
        self._check_alarms()

    def _check_alarms(self) -> None:
        """Check for alarm conditions."""
        # Pressure alarms
        max_pressure = (self.limits.max_retrograde_pressure_mmhg
                       if self.delivery_route == DeliveryRoute.RETROGRADE
                       else self.limits.max_antegrade_pressure_mmhg)

        if self.is_delivering and self.delivery_pressure_mmhg > max_pressure:
            self._trigger_alarm("critical",
                f"Cardioplegia pressure exceeded: {self.delivery_pressure_mmhg:.0f} mmHg")

        # Temperature alarms
        if self.is_delivering:
            if self.temperature_mode == CardioplegiaTemperature.COLD:
                if self.delivery_temperature_celsius > self.limits.max_cold_temp_celsius:
                    self._trigger_alarm("warning",
                        f"Cardioplegia too warm: {self.delivery_temperature_celsius:.1f}°C")

        # Redose reminder
        if self.needs_redose():
            self._trigger_alarm("warning",
                f"Cardioplegia redose needed - {self.get_time_since_last_dose():.1f} min since last dose")

    def calculate_total_potassium_delivered(self) -> float:
        """Calculate total potassium delivered in mEq."""
        total_meq = 0.0
        for dose in self.doses:
            # mEq = concentration (mEq/L) * volume (L)
            total_meq += dose.potassium_meq_l * (dose.volume_ml / 1000.0)
        return total_meq

    def get_status(self) -> dict:
        """Get cardioplegia system status."""
        return {
            "is_active": self.is_active,
            "is_delivering": self.is_delivering,
            "cardioplegia_type": self.cardioplegia_type.name,
            "delivery_route": self.delivery_route.name,
            "temperature_mode": self.temperature_mode.name,
            "current_phase": self.current_phase.name,
            "delivery": {
                "pressure_mmhg": round(self.delivery_pressure_mmhg, 1),
                "temperature_celsius": round(self.delivery_temperature_celsius, 1),
                "flow_ml_min": round(self.actual_flow_ml_min, 1),
                "current_dose_volume_ml": round(self.current_dose_volume_ml, 1)
            },
            "totals": {
                "doses_given": len(self.doses),
                "total_volume_ml": round(self.total_volume_delivered_ml, 1),
                "total_potassium_meq": round(self.calculate_total_potassium_delivered(), 2)
            },
            "timing": {
                "cross_clamp_duration_min": (
                    round(self.get_cross_clamp_duration(), 1)
                    if self.get_cross_clamp_duration() else None
                ),
                "time_since_last_dose_min": (
                    round(self.get_time_since_last_dose(), 1)
                    if self.get_time_since_last_dose() else None
                ),
                "needs_redose": self.needs_redose()
            },
            "mixer": {
                "blood_ratio": self.mixer.target_ratio,
                "blood_flow_ml_min": round(self.mixer.blood_flow_ml_min, 1),
                "crystalloid_flow_ml_min": round(self.mixer.crystalloid_flow_ml_min, 1),
                "final_potassium_meq_l": round(self.mixer.potassium_concentration_meq_l, 1)
            }
        }

    def get_dose_history(self) -> list[dict]:
        """Get history of all cardioplegia doses."""
        return [
            {
                "dose_number": d.dose_number,
                "phase": d.phase.name,
                "route": d.route.name,
                "volume_ml": round(d.volume_ml, 1),
                "duration_seconds": round(d.duration_seconds, 1),
                "temperature_celsius": round(d.temperature_celsius, 1),
                "flow_rate_ml_min": round(d.flow_rate_ml_min, 1),
                "pressure_mmhg": round(d.pressure_mmhg, 1),
                "potassium_meq_l": round(d.potassium_meq_l, 1)
            }
            for d in self.doses
        ]
