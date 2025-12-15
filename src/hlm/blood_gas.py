"""
Blood Gas and Perfusion Monitoring System

Real-time monitoring of blood gases and perfusion parameters is essential
for optimal patient management during cardiopulmonary bypass.

This module implements:
- Arterial and venous blood gas monitoring
- Oxygen delivery (DO2) and consumption (VO2) calculations
- Lactate trending
- Continuous inline monitoring support
- Goal-directed perfusion parameters
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time
import math


class BloodGasType(Enum):
    """Type of blood gas sample."""
    ARTERIAL = auto()        # Arterial (post-oxygenator)
    VENOUS = auto()          # Mixed venous (pre-oxygenator)
    CARDIOPLEGIA = auto()    # Cardioplegia effluent


class SampleSource(Enum):
    """Source of blood gas measurement."""
    INLINE_CONTINUOUS = auto()  # CDI or similar inline monitor
    POINT_OF_CARE = auto()      # POC analyzer (iSTAT, etc.)
    LABORATORY = auto()          # Central lab
    MANUAL_ENTRY = auto()        # Manually entered values


@dataclass
class BloodGasReading:
    """A single blood gas reading."""
    timestamp: float = field(default_factory=time.time)
    gas_type: BloodGasType = BloodGasType.ARTERIAL
    source: SampleSource = SampleSource.INLINE_CONTINUOUS

    # Oxygenation
    po2_mmhg: float = 0.0           # Partial pressure of oxygen
    pco2_mmhg: float = 0.0          # Partial pressure of CO2
    so2_percent: float = 0.0        # Oxygen saturation
    fio2_percent: float = 100.0     # Fraction of inspired O2

    # Acid-base
    ph: float = 7.40
    hco3_meq_l: float = 24.0        # Bicarbonate
    base_excess_meq_l: float = 0.0  # Base excess

    # Electrolytes
    potassium_meq_l: float = 4.0
    sodium_meq_l: float = 140.0
    calcium_ionized_mmol_l: float = 1.2
    glucose_mg_dl: float = 100.0

    # Hemoglobin
    hemoglobin_g_dl: float = 12.0
    hematocrit_percent: float = 36.0

    # Metabolic
    lactate_mmol_l: float = 1.0

    def is_valid(self) -> bool:
        """Check if reading values are physiologically plausible."""
        return (
            0 < self.po2_mmhg < 800 and
            10 < self.pco2_mmhg < 150 and
            0 < self.so2_percent <= 100 and
            6.5 < self.ph < 8.0 and
            0 < self.hemoglobin_g_dl < 25
        )


@dataclass
class OxygenContent:
    """Calculated oxygen content."""
    cao2_ml_dl: float = 0.0  # Arterial O2 content
    cvo2_ml_dl: float = 0.0  # Venous O2 content
    avdo2_ml_dl: float = 0.0  # A-V O2 difference


@dataclass
class PerfusionParameters:
    """Calculated perfusion parameters."""
    # Oxygen delivery and consumption
    do2_ml_min_m2: float = 0.0      # O2 delivery indexed to BSA
    vo2_ml_min_m2: float = 0.0      # O2 consumption indexed to BSA
    do2_ml_min: float = 0.0         # Absolute O2 delivery
    vo2_ml_min: float = 0.0         # Absolute O2 consumption

    # Extraction and utilization
    o2_extraction_ratio: float = 0.0  # VO2/DO2
    venous_saturation_percent: float = 0.0

    # Flow indices
    cardiac_index_l_min_m2: float = 0.0
    flow_rate_ml_min: float = 0.0

    # Metabolic indicators
    lactate_mmol_l: float = 0.0
    base_excess_meq_l: float = 0.0


@dataclass
class PerfusionTargets:
    """Target ranges for goal-directed perfusion."""
    # Oxygen delivery targets
    min_do2_ml_min_m2: float = 270.0  # Critical DO2 threshold
    target_do2_ml_min_m2: float = 300.0
    optimal_do2_ml_min_m2: float = 400.0

    # Venous saturation targets
    min_svo2_percent: float = 65.0
    target_svo2_percent: float = 75.0

    # Blood gas targets
    target_ph_min: float = 7.35
    target_ph_max: float = 7.45
    target_pco2_min_mmhg: float = 35.0
    target_pco2_max_mmhg: float = 45.0
    target_po2_min_mmhg: float = 150.0
    target_po2_max_mmhg: float = 300.0

    # Metabolic targets
    max_lactate_mmol_l: float = 3.0
    min_base_excess_meq_l: float = -4.0

    # Hemoglobin targets
    min_hemoglobin_g_dl: float = 7.0
    target_hemoglobin_g_dl: float = 8.0

    # Electrolyte targets
    target_potassium_min_meq_l: float = 3.5
    target_potassium_max_meq_l: float = 5.0
    target_calcium_min_mmol_l: float = 1.0
    target_calcium_max_mmol_l: float = 1.3
    target_glucose_min_mg_dl: float = 80.0
    target_glucose_max_mg_dl: float = 180.0


class BloodGasCalculator:
    """
    Calculator for derived blood gas and perfusion parameters.
    """

    @staticmethod
    def calculate_oxygen_content(
        po2_mmhg: float,
        so2_percent: float,
        hemoglobin_g_dl: float
    ) -> float:
        """
        Calculate oxygen content using the oxygen content equation.

        CaO2 = (1.34 × Hb × SaO2) + (0.003 × PaO2)

        Args:
            po2_mmhg: Partial pressure of oxygen
            so2_percent: Oxygen saturation (0-100)
            hemoglobin_g_dl: Hemoglobin concentration

        Returns:
            Oxygen content in ml O2/dL blood
        """
        # Bound saturation
        so2_fraction = min(1.0, max(0.0, so2_percent / 100.0))

        # Bound contribution: Hb-bound oxygen
        bound_o2 = 1.34 * hemoglobin_g_dl * so2_fraction

        # Dissolved contribution: dissolved oxygen in plasma
        dissolved_o2 = 0.003 * po2_mmhg

        return bound_o2 + dissolved_o2

    @staticmethod
    def calculate_oxygen_delivery(
        oxygen_content_ml_dl: float,
        flow_rate_ml_min: float
    ) -> float:
        """
        Calculate oxygen delivery.

        DO2 = CaO2 × Q × 10

        Args:
            oxygen_content_ml_dl: Arterial oxygen content
            flow_rate_ml_min: Blood flow rate

        Returns:
            Oxygen delivery in ml O2/min
        """
        # Convert flow to L/min for calculation
        flow_l_min = flow_rate_ml_min / 1000.0
        return oxygen_content_ml_dl * flow_l_min * 10.0

    @staticmethod
    def calculate_oxygen_consumption(
        cao2_ml_dl: float,
        cvo2_ml_dl: float,
        flow_rate_ml_min: float
    ) -> float:
        """
        Calculate oxygen consumption using Fick principle.

        VO2 = (CaO2 - CvO2) × Q × 10

        Args:
            cao2_ml_dl: Arterial oxygen content
            cvo2_ml_dl: Venous oxygen content
            flow_rate_ml_min: Blood flow rate

        Returns:
            Oxygen consumption in ml O2/min
        """
        flow_l_min = flow_rate_ml_min / 1000.0
        avdo2 = cao2_ml_dl - cvo2_ml_dl
        return avdo2 * flow_l_min * 10.0

    @staticmethod
    def calculate_extraction_ratio(vo2: float, do2: float) -> float:
        """Calculate oxygen extraction ratio."""
        if do2 <= 0:
            return 0.0
        return min(1.0, vo2 / do2)

    @staticmethod
    def index_to_bsa(value: float, bsa_m2: float) -> float:
        """Index a value to body surface area."""
        if bsa_m2 <= 0:
            return 0.0
        return value / bsa_m2

    @staticmethod
    def calculate_p50(po2_mmhg: float, so2_percent: float) -> float:
        """
        Estimate P50 (PO2 at 50% saturation) from a single point.

        Uses Hill equation approximation.
        """
        if so2_percent <= 0 or so2_percent >= 100:
            return 26.6  # Normal P50

        so2_fraction = so2_percent / 100.0
        n = 2.7  # Hill coefficient

        try:
            p50 = po2_mmhg * ((1 - so2_fraction) / so2_fraction) ** (1/n)
            return max(15.0, min(40.0, p50))  # Physiological bounds
        except (ValueError, ZeroDivisionError):
            return 26.6


class InlineSensorInterface:
    """
    Interface for inline blood gas monitoring systems.

    Supports continuous monitoring devices like CDI 500, Terumo CDI,
    and similar inline blood parameter monitoring systems.
    """

    def __init__(self, device_name: str = "Inline Monitor"):
        self.device_name = device_name
        self.is_connected: bool = False
        self.is_calibrated: bool = False
        self.last_calibration_time: float | None = None

        # Sensor status
        self.arterial_sensor_active: bool = False
        self.venous_sensor_active: bool = False

        # Current readings
        self.arterial_reading: BloodGasReading | None = None
        self.venous_reading: BloodGasReading | None = None

        # Update interval
        self.update_interval_seconds: float = 5.0
        self.last_update_time: float = 0.0

    def connect(self) -> bool:
        """Connect to inline monitor."""
        self.is_connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from inline monitor."""
        self.is_connected = False

    def calibrate(self) -> bool:
        """Perform sensor calibration."""
        if not self.is_connected:
            return False
        self.is_calibrated = True
        self.last_calibration_time = time.time()
        return True

    def needs_calibration(self, max_hours: float = 8.0) -> bool:
        """Check if calibration is needed."""
        if not self.is_calibrated or self.last_calibration_time is None:
            return True
        hours_since_cal = (time.time() - self.last_calibration_time) / 3600.0
        return hours_since_cal >= max_hours

    def update_arterial(self, reading: BloodGasReading) -> None:
        """Update arterial reading from sensor."""
        reading.gas_type = BloodGasType.ARTERIAL
        reading.source = SampleSource.INLINE_CONTINUOUS
        self.arterial_reading = reading
        self.arterial_sensor_active = True
        self.last_update_time = time.time()

    def update_venous(self, reading: BloodGasReading) -> None:
        """Update venous reading from sensor."""
        reading.gas_type = BloodGasType.VENOUS
        reading.source = SampleSource.INLINE_CONTINUOUS
        self.venous_reading = reading
        self.venous_sensor_active = True
        self.last_update_time = time.time()


class BloodGasMonitor:
    """
    Comprehensive blood gas and perfusion monitoring system.

    Integrates multiple data sources and calculates derived parameters
    for goal-directed perfusion management.
    """

    def __init__(self):
        """Initialize blood gas monitor."""
        self.is_active: bool = False

        # Inline sensor interface
        self.inline_sensor = InlineSensorInterface()

        # Current readings
        self.arterial: BloodGasReading | None = None
        self.venous: BloodGasReading | None = None

        # Calculated parameters
        self.oxygen_content = OxygenContent()
        self.perfusion = PerfusionParameters()
        self.targets = PerfusionTargets()

        # Patient data
        self.bsa_m2: float = 1.8
        self.flow_rate_ml_min: float = 0.0
        self.temperature_celsius: float = 37.0

        # History for trending
        self.arterial_history: list[BloodGasReading] = []
        self.venous_history: list[BloodGasReading] = []
        self.perfusion_history: list[tuple[float, PerfusionParameters]] = []

        # Callbacks
        self._alert_callbacks: list[Callable[[str, str], None]] = []

        # Calculator
        self.calculator = BloodGasCalculator()

    def register_alert_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register alert callback."""
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, level: str, message: str) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            callback(level, message)

    def activate(self) -> None:
        """Activate monitoring."""
        self.is_active = True
        self.inline_sensor.connect()

    def deactivate(self) -> None:
        """Deactivate monitoring."""
        self.is_active = False
        self.inline_sensor.disconnect()

    def set_patient_data(self, bsa_m2: float, temperature_celsius: float = 37.0) -> None:
        """Set patient data for calculations."""
        self.bsa_m2 = bsa_m2
        self.temperature_celsius = temperature_celsius

    def set_flow_rate(self, flow_ml_min: float) -> None:
        """Update current flow rate for calculations."""
        self.flow_rate_ml_min = flow_ml_min
        self._calculate_perfusion_parameters()

    def update_arterial(self, reading: BloodGasReading) -> None:
        """
        Update arterial blood gas reading.

        Args:
            reading: Blood gas reading
        """
        reading.gas_type = BloodGasType.ARTERIAL
        self.arterial = reading
        self.arterial_history.append(reading)

        # Limit history size
        if len(self.arterial_history) > 1000:
            self.arterial_history = self.arterial_history[-500:]

        self._calculate_perfusion_parameters()
        self._check_arterial_alerts()

    def update_venous(self, reading: BloodGasReading) -> None:
        """
        Update venous blood gas reading.

        Args:
            reading: Blood gas reading
        """
        reading.gas_type = BloodGasType.VENOUS
        self.venous = reading
        self.venous_history.append(reading)

        # Limit history size
        if len(self.venous_history) > 1000:
            self.venous_history = self.venous_history[-500:]

        self._calculate_perfusion_parameters()
        self._check_venous_alerts()

    def _calculate_perfusion_parameters(self) -> None:
        """Calculate all derived perfusion parameters."""
        if self.arterial is None:
            return

        # Calculate arterial oxygen content
        self.oxygen_content.cao2_ml_dl = self.calculator.calculate_oxygen_content(
            self.arterial.po2_mmhg,
            self.arterial.so2_percent,
            self.arterial.hemoglobin_g_dl
        )

        # Calculate venous oxygen content if available
        if self.venous is not None:
            self.oxygen_content.cvo2_ml_dl = self.calculator.calculate_oxygen_content(
                self.venous.po2_mmhg,
                self.venous.so2_percent,
                self.venous.hemoglobin_g_dl
            )
            self.oxygen_content.avdo2_ml_dl = (
                self.oxygen_content.cao2_ml_dl - self.oxygen_content.cvo2_ml_dl
            )

            # Venous saturation
            self.perfusion.venous_saturation_percent = self.venous.so2_percent

        # Calculate oxygen delivery
        self.perfusion.do2_ml_min = self.calculator.calculate_oxygen_delivery(
            self.oxygen_content.cao2_ml_dl,
            self.flow_rate_ml_min
        )
        self.perfusion.do2_ml_min_m2 = self.calculator.index_to_bsa(
            self.perfusion.do2_ml_min,
            self.bsa_m2
        )

        # Calculate oxygen consumption if venous data available
        if self.venous is not None:
            self.perfusion.vo2_ml_min = self.calculator.calculate_oxygen_consumption(
                self.oxygen_content.cao2_ml_dl,
                self.oxygen_content.cvo2_ml_dl,
                self.flow_rate_ml_min
            )
            self.perfusion.vo2_ml_min_m2 = self.calculator.index_to_bsa(
                self.perfusion.vo2_ml_min,
                self.bsa_m2
            )

            # Extraction ratio
            self.perfusion.o2_extraction_ratio = self.calculator.calculate_extraction_ratio(
                self.perfusion.vo2_ml_min,
                self.perfusion.do2_ml_min
            )

        # Flow indices
        self.perfusion.flow_rate_ml_min = self.flow_rate_ml_min
        self.perfusion.cardiac_index_l_min_m2 = (
            (self.flow_rate_ml_min / 1000.0) / self.bsa_m2 if self.bsa_m2 > 0 else 0
        )

        # Metabolic parameters from arterial reading
        self.perfusion.lactate_mmol_l = self.arterial.lactate_mmol_l
        self.perfusion.base_excess_meq_l = self.arterial.base_excess_meq_l

        # Record history
        self.perfusion_history.append((time.time(), PerfusionParameters(
            do2_ml_min_m2=self.perfusion.do2_ml_min_m2,
            vo2_ml_min_m2=self.perfusion.vo2_ml_min_m2,
            do2_ml_min=self.perfusion.do2_ml_min,
            vo2_ml_min=self.perfusion.vo2_ml_min,
            o2_extraction_ratio=self.perfusion.o2_extraction_ratio,
            venous_saturation_percent=self.perfusion.venous_saturation_percent,
            cardiac_index_l_min_m2=self.perfusion.cardiac_index_l_min_m2,
            flow_rate_ml_min=self.perfusion.flow_rate_ml_min,
            lactate_mmol_l=self.perfusion.lactate_mmol_l,
            base_excess_meq_l=self.perfusion.base_excess_meq_l
        )))

        # Limit history
        if len(self.perfusion_history) > 1000:
            self.perfusion_history = self.perfusion_history[-500:]

    def _check_arterial_alerts(self) -> None:
        """Check arterial values against targets and alert."""
        if self.arterial is None:
            return

        # pH alerts
        if self.arterial.ph < self.targets.target_ph_min:
            self._trigger_alert("warning", f"Arterial pH low: {self.arterial.ph:.2f}")
        elif self.arterial.ph > self.targets.target_ph_max:
            self._trigger_alert("warning", f"Arterial pH high: {self.arterial.ph:.2f}")

        # PCO2 alerts
        if self.arterial.pco2_mmhg < self.targets.target_pco2_min_mmhg:
            self._trigger_alert("info", f"Arterial PCO2 low: {self.arterial.pco2_mmhg:.0f} mmHg")
        elif self.arterial.pco2_mmhg > self.targets.target_pco2_max_mmhg:
            self._trigger_alert("warning", f"Arterial PCO2 high: {self.arterial.pco2_mmhg:.0f} mmHg")

        # PO2 alerts
        if self.arterial.po2_mmhg < self.targets.target_po2_min_mmhg:
            self._trigger_alert("warning", f"Arterial PO2 low: {self.arterial.po2_mmhg:.0f} mmHg")

        # Hemoglobin alerts
        if self.arterial.hemoglobin_g_dl < self.targets.min_hemoglobin_g_dl:
            self._trigger_alert("critical", f"Hemoglobin critical: {self.arterial.hemoglobin_g_dl:.1f} g/dL")
        elif self.arterial.hemoglobin_g_dl < self.targets.target_hemoglobin_g_dl:
            self._trigger_alert("warning", f"Hemoglobin low: {self.arterial.hemoglobin_g_dl:.1f} g/dL")

        # Potassium alerts
        if self.arterial.potassium_meq_l < self.targets.target_potassium_min_meq_l:
            self._trigger_alert("warning", f"Potassium low: {self.arterial.potassium_meq_l:.1f} mEq/L")
        elif self.arterial.potassium_meq_l > self.targets.target_potassium_max_meq_l:
            self._trigger_alert("critical", f"Potassium high: {self.arterial.potassium_meq_l:.1f} mEq/L")

        # Lactate alerts
        if self.arterial.lactate_mmol_l > self.targets.max_lactate_mmol_l:
            self._trigger_alert("warning", f"Lactate elevated: {self.arterial.lactate_mmol_l:.1f} mmol/L")

        # Glucose alerts
        if self.arterial.glucose_mg_dl < self.targets.target_glucose_min_mg_dl:
            self._trigger_alert("warning", f"Glucose low: {self.arterial.glucose_mg_dl:.0f} mg/dL")
        elif self.arterial.glucose_mg_dl > self.targets.target_glucose_max_mg_dl:
            self._trigger_alert("warning", f"Glucose high: {self.arterial.glucose_mg_dl:.0f} mg/dL")

    def _check_venous_alerts(self) -> None:
        """Check venous values and perfusion parameters."""
        # SvO2 alerts
        if self.perfusion.venous_saturation_percent < self.targets.min_svo2_percent:
            self._trigger_alert("critical",
                f"SvO2 critical: {self.perfusion.venous_saturation_percent:.0f}%")
        elif self.perfusion.venous_saturation_percent < self.targets.target_svo2_percent:
            self._trigger_alert("warning",
                f"SvO2 low: {self.perfusion.venous_saturation_percent:.0f}%")

        # DO2 alerts
        if self.perfusion.do2_ml_min_m2 < self.targets.min_do2_ml_min_m2:
            self._trigger_alert("critical",
                f"DO2 critical: {self.perfusion.do2_ml_min_m2:.0f} ml/min/m²")
        elif self.perfusion.do2_ml_min_m2 < self.targets.target_do2_ml_min_m2:
            self._trigger_alert("warning",
                f"DO2 below target: {self.perfusion.do2_ml_min_m2:.0f} ml/min/m²")

        # High extraction ratio
        if self.perfusion.o2_extraction_ratio > 0.35:
            self._trigger_alert("warning",
                f"O2 extraction high: {self.perfusion.o2_extraction_ratio:.0%}")

    def is_do2_adequate(self) -> bool:
        """Check if oxygen delivery is adequate."""
        return self.perfusion.do2_ml_min_m2 >= self.targets.target_do2_ml_min_m2

    def is_svo2_adequate(self) -> bool:
        """Check if venous saturation is adequate."""
        return self.perfusion.venous_saturation_percent >= self.targets.target_svo2_percent

    def get_recommended_flow_for_do2(self, target_do2_ml_min_m2: float) -> float:
        """
        Calculate flow rate needed to achieve target DO2.

        Args:
            target_do2_ml_min_m2: Target indexed DO2

        Returns:
            Required flow rate in ml/min
        """
        if self.oxygen_content.cao2_ml_dl <= 0:
            return 0.0

        # DO2 = CaO2 × Q × 10 / BSA
        # Q = DO2 × BSA / (CaO2 × 10)
        target_do2_ml_min = target_do2_ml_min_m2 * self.bsa_m2
        required_flow_l_min = target_do2_ml_min / (self.oxygen_content.cao2_ml_dl * 10.0)
        return required_flow_l_min * 1000.0

    def get_lactate_trend(self, minutes: float = 60.0) -> str:
        """
        Get lactate trend over specified period.

        Returns:
            'increasing', 'decreasing', 'stable', or 'unknown'
        """
        cutoff = time.time() - (minutes * 60)
        recent = [r for r in self.arterial_history if r.timestamp > cutoff]

        if len(recent) < 2:
            return "unknown"

        first_half = recent[:len(recent)//2]
        second_half = recent[len(recent)//2:]

        avg_first = sum(r.lactate_mmol_l for r in first_half) / len(first_half)
        avg_second = sum(r.lactate_mmol_l for r in second_half) / len(second_half)

        diff = avg_second - avg_first
        if diff > 0.3:
            return "increasing"
        elif diff < -0.3:
            return "decreasing"
        else:
            return "stable"

    def get_status(self) -> dict:
        """Get comprehensive blood gas status."""
        return {
            "is_active": self.is_active,
            "inline_sensor": {
                "connected": self.inline_sensor.is_connected,
                "calibrated": self.inline_sensor.is_calibrated,
                "needs_calibration": self.inline_sensor.needs_calibration()
            },
            "arterial": {
                "available": self.arterial is not None,
                "ph": round(self.arterial.ph, 2) if self.arterial else None,
                "pco2_mmhg": round(self.arterial.pco2_mmhg, 1) if self.arterial else None,
                "po2_mmhg": round(self.arterial.po2_mmhg, 1) if self.arterial else None,
                "so2_percent": round(self.arterial.so2_percent, 1) if self.arterial else None,
                "hemoglobin_g_dl": round(self.arterial.hemoglobin_g_dl, 1) if self.arterial else None,
                "potassium_meq_l": round(self.arterial.potassium_meq_l, 1) if self.arterial else None,
                "lactate_mmol_l": round(self.arterial.lactate_mmol_l, 2) if self.arterial else None,
                "glucose_mg_dl": round(self.arterial.glucose_mg_dl, 0) if self.arterial else None
            },
            "venous": {
                "available": self.venous is not None,
                "po2_mmhg": round(self.venous.po2_mmhg, 1) if self.venous else None,
                "so2_percent": round(self.venous.so2_percent, 1) if self.venous else None
            },
            "oxygen_content": {
                "cao2_ml_dl": round(self.oxygen_content.cao2_ml_dl, 1),
                "cvo2_ml_dl": round(self.oxygen_content.cvo2_ml_dl, 1),
                "avdo2_ml_dl": round(self.oxygen_content.avdo2_ml_dl, 1)
            },
            "perfusion": {
                "do2_ml_min_m2": round(self.perfusion.do2_ml_min_m2, 0),
                "vo2_ml_min_m2": round(self.perfusion.vo2_ml_min_m2, 0),
                "o2_extraction_ratio": round(self.perfusion.o2_extraction_ratio, 2),
                "svo2_percent": round(self.perfusion.venous_saturation_percent, 1),
                "cardiac_index_l_min_m2": round(self.perfusion.cardiac_index_l_min_m2, 2),
                "is_do2_adequate": self.is_do2_adequate(),
                "is_svo2_adequate": self.is_svo2_adequate()
            },
            "trends": {
                "lactate_trend": self.get_lactate_trend()
            }
        }
