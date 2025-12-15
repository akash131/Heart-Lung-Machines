"""
Anticoagulation Monitoring System

Proper anticoagulation is essential during cardiopulmonary bypass to prevent
thrombosis while avoiding excessive bleeding.

This module implements:
- ACT (Activated Clotting Time) monitoring
- Heparin dosing calculations
- Protamine dosing calculations
- Heparin concentration monitoring (HMS)
- Coagulation status tracking
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time


class AnticoagulantType(Enum):
    """Types of anticoagulants used."""
    HEPARIN = auto()
    BIVALIRUDIN = auto()
    ARGATROBAN = auto()


class CoagulationStatus(Enum):
    """Overall coagulation status."""
    UNKNOWN = auto()
    INADEQUATE = auto()    # ACT too low - needs more heparin
    THERAPEUTIC = auto()    # ACT in target range
    EXCESSIVE = auto()      # ACT too high
    NEUTRALIZED = auto()    # Post-protamine


class ACTMethod(Enum):
    """ACT measurement methods."""
    HEMOCHRON = auto()
    HEPCON = auto()
    I_STAT = auto()
    MANUAL = auto()


@dataclass
class ACTReading:
    """A single ACT measurement."""
    timestamp: float = field(default_factory=time.time)
    value_seconds: float = 0.0
    method: ACTMethod = ACTMethod.HEMOCHRON
    sample_type: str = "arterial"
    is_baseline: bool = False
    notes: str = ""

    def is_therapeutic(self, target_min: float = 480.0) -> bool:
        """Check if ACT is therapeutic."""
        return self.value_seconds >= target_min


@dataclass
class HeparinDose:
    """Record of a heparin dose."""
    timestamp: float = field(default_factory=time.time)
    dose_units: float = 0.0
    concentration_units_ml: float = 1000.0
    volume_ml: float = 0.0
    route: str = "IV"
    indication: str = ""


@dataclass
class ProtamineDose:
    """Record of a protamine dose."""
    timestamp: float = field(default_factory=time.time)
    dose_mg: float = 0.0
    rate_mg_min: float = 0.0
    infusion_duration_min: float = 0.0
    heparin_reversed_units: float = 0.0


@dataclass
class AnticoagulationTargets:
    """Target ranges for anticoagulation."""
    # ACT targets
    baseline_act_seconds: float = 120.0
    min_bypass_act_seconds: float = 480.0
    target_bypass_act_seconds: float = 500.0

    # Heparin parameters
    initial_heparin_units_kg: float = 400.0  # Initial bolus
    supplemental_heparin_units: float = 5000.0  # Supplemental doses
    max_heparin_dose_units: float = 50000.0

    # Protamine parameters
    protamine_ratio: float = 1.0  # mg protamine per 100 units heparin
    max_protamine_rate_mg_min: float = 5.0
    protamine_test_dose_mg: float = 10.0


@dataclass
class HeparinManagementSystem:
    """
    Heparin Management System (HMS) for heparin concentration monitoring.

    Uses heparin-protamine titration to estimate circulating heparin.
    """
    is_available: bool = False
    heparin_concentration_units_ml: float = 0.0
    calculated_whole_blood_heparin_units: float = 0.0

    # Sensitivity
    patient_heparin_sensitivity: float = 1.0  # ACT response per unit/kg

    def calculate_sensitivity(self,
                               baseline_act: float,
                               post_heparin_act: float,
                               heparin_dose_units_kg: float) -> float:
        """Calculate patient's heparin sensitivity."""
        if heparin_dose_units_kg <= 0:
            return 1.0

        act_increase = post_heparin_act - baseline_act
        self.patient_heparin_sensitivity = act_increase / heparin_dose_units_kg
        return self.patient_heparin_sensitivity


class AnticoagulationMonitor:
    """
    Comprehensive anticoagulation monitoring and management system.
    """

    def __init__(self):
        """Initialize anticoagulation monitor."""
        self.is_active: bool = False
        self.status = CoagulationStatus.UNKNOWN

        # Current anticoagulant
        self.anticoagulant = AnticoagulantType.HEPARIN
        self.targets = AnticoagulationTargets()

        # Patient parameters
        self.patient_weight_kg: float = 70.0
        self.estimated_blood_volume_ml: float = 5000.0

        # ACT tracking
        self.act_readings: list[ACTReading] = []
        self.baseline_act: float | None = None
        self.current_act: float | None = None
        self.last_act_time: float | None = None

        # Heparin tracking
        self.heparin_doses: list[HeparinDose] = []
        self.total_heparin_units: float = 0.0
        self.heparin_on_board_units: float = 0.0

        # Protamine tracking
        self.protamine_doses: list[ProtamineDose] = []
        self.total_protamine_mg: float = 0.0
        self.protamine_infusion_active: bool = False

        # HMS
        self.hms = HeparinManagementSystem()

        # Timing
        self.bypass_start_time: float | None = None
        self.heparinization_time: float | None = None
        self.neutralization_time: float | None = None

        # Callbacks
        self._alarm_callbacks: list[Callable[[str, str], None]] = []

    def register_alarm_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register alarm callback."""
        self._alarm_callbacks.append(callback)

    def _trigger_alarm(self, level: str, message: str) -> None:
        """Trigger alarm callbacks."""
        for callback in self._alarm_callbacks:
            callback(level, message)

    def set_patient_weight(self, weight_kg: float) -> None:
        """Set patient weight for dose calculations."""
        self.patient_weight_kg = weight_kg
        self.estimated_blood_volume_ml = weight_kg * 70  # 70 ml/kg estimate

    def activate(self) -> None:
        """Activate anticoagulation monitoring."""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate monitoring."""
        self.is_active = False

    def record_baseline_act(self, act_seconds: float,
                            method: ACTMethod = ACTMethod.HEMOCHRON) -> None:
        """Record baseline ACT before heparinization."""
        reading = ACTReading(
            value_seconds=act_seconds,
            method=method,
            is_baseline=True,
            notes="Pre-heparin baseline"
        )
        self.act_readings.append(reading)
        self.baseline_act = act_seconds
        self.targets.baseline_act_seconds = act_seconds

    def record_act(self, act_seconds: float,
                   method: ACTMethod = ACTMethod.HEMOCHRON,
                   notes: str = "") -> ACTReading:
        """
        Record an ACT measurement.

        Args:
            act_seconds: ACT value in seconds
            method: Measurement method
            notes: Additional notes

        Returns:
            The recorded reading
        """
        reading = ACTReading(
            value_seconds=act_seconds,
            method=method,
            notes=notes
        )
        self.act_readings.append(reading)
        self.current_act = act_seconds
        self.last_act_time = time.time()

        # Update status
        self._update_status()

        # Check for alarms
        self._check_act_alarms()

        return reading

    def _update_status(self) -> None:
        """Update coagulation status based on current ACT."""
        if self.current_act is None:
            self.status = CoagulationStatus.UNKNOWN
            return

        if self.neutralization_time is not None:
            # Post-protamine
            if self.current_act <= self.targets.baseline_act_seconds * 1.2:
                self.status = CoagulationStatus.NEUTRALIZED
            else:
                self.status = CoagulationStatus.INADEQUATE
        elif self.heparinization_time is not None:
            # On bypass
            if self.current_act >= self.targets.min_bypass_act_seconds:
                self.status = CoagulationStatus.THERAPEUTIC
            else:
                self.status = CoagulationStatus.INADEQUATE
        else:
            self.status = CoagulationStatus.UNKNOWN

    def _check_act_alarms(self) -> None:
        """Check ACT values for alarm conditions."""
        if self.current_act is None:
            return

        if self.bypass_start_time is not None and self.neutralization_time is None:
            # On bypass - check if therapeutic
            if self.current_act < self.targets.min_bypass_act_seconds:
                self._trigger_alarm("critical",
                    f"ACT below target: {self.current_act:.0f}s (target ≥{self.targets.min_bypass_act_seconds}s)")
            elif self.current_act < self.targets.min_bypass_act_seconds + 20:
                self._trigger_alarm("warning",
                    f"ACT approaching threshold: {self.current_act:.0f}s")

    def calculate_initial_heparin_dose(self) -> float:
        """
        Calculate initial heparin dose for bypass.

        Returns:
            Recommended dose in units
        """
        return self.patient_weight_kg * self.targets.initial_heparin_units_kg

    def calculate_supplemental_heparin(self) -> float:
        """
        Calculate supplemental heparin dose if ACT is low.

        Uses ACT-based dosing or HMS if available.
        """
        if self.current_act is None:
            return self.targets.supplemental_heparin_units

        if self.hms.is_available and self.hms.patient_heparin_sensitivity > 0:
            # HMS-based calculation
            target_increase = self.targets.target_bypass_act_seconds - self.current_act
            dose_per_kg = target_increase / self.hms.patient_heparin_sensitivity
            return dose_per_kg * self.patient_weight_kg
        else:
            # Standard supplemental dose
            return self.targets.supplemental_heparin_units

    def record_heparin_dose(self, dose_units: float,
                           indication: str = "supplemental") -> HeparinDose:
        """
        Record a heparin dose.

        Args:
            dose_units: Dose in units
            indication: Reason for dose

        Returns:
            Recorded dose
        """
        dose = HeparinDose(
            dose_units=dose_units,
            volume_ml=dose_units / 1000.0,  # Assuming 1000 U/ml
            indication=indication
        )
        self.heparin_doses.append(dose)
        self.total_heparin_units += dose_units
        self.heparin_on_board_units += dose_units

        # Mark heparinization time if first dose
        if self.heparinization_time is None:
            self.heparinization_time = time.time()

        # Update HMS sensitivity if baseline available
        if len(self.heparin_doses) == 1 and self.baseline_act is not None:
            # Will be updated when post-heparin ACT is recorded
            pass

        return dose

    def calculate_protamine_dose(self, target_reversal_percent: float = 100.0) -> float:
        """
        Calculate protamine dose for heparin reversal.

        Args:
            target_reversal_percent: Percentage of heparin to reverse

        Returns:
            Protamine dose in mg
        """
        # Account for heparin metabolism (half-life ~90 min)
        if self.heparinization_time is not None:
            elapsed_hours = (time.time() - self.heparinization_time) / 3600.0
            half_lives = elapsed_hours / 1.5  # 90 min half-life
            metabolized_fraction = 1 - (0.5 ** half_lives)
            remaining_heparin = self.total_heparin_units * (1 - metabolized_fraction)
        else:
            remaining_heparin = self.total_heparin_units

        # Add circuit heparin estimate
        circuit_heparin = 5000  # Typical priming heparin
        total_to_reverse = remaining_heparin + circuit_heparin

        # Apply target percentage
        heparin_to_reverse = total_to_reverse * (target_reversal_percent / 100.0)

        # Calculate protamine (1 mg per 100 units, adjusted by ratio)
        protamine_mg = (heparin_to_reverse / 100.0) * self.targets.protamine_ratio

        return protamine_mg

    def record_protamine_dose(self, dose_mg: float,
                              infusion_duration_min: float = 10.0) -> ProtamineDose:
        """
        Record a protamine dose.

        Args:
            dose_mg: Dose in milligrams
            infusion_duration_min: Duration of infusion

        Returns:
            Recorded dose
        """
        rate = dose_mg / infusion_duration_min if infusion_duration_min > 0 else 0

        dose = ProtamineDose(
            dose_mg=dose_mg,
            rate_mg_min=rate,
            infusion_duration_min=infusion_duration_min,
            heparin_reversed_units=dose_mg * 100 / self.targets.protamine_ratio
        )
        self.protamine_doses.append(dose)
        self.total_protamine_mg += dose_mg

        # Mark neutralization time
        if self.neutralization_time is None:
            self.neutralization_time = time.time()

        # Update heparin on board
        self.heparin_on_board_units -= dose.heparin_reversed_units
        self.heparin_on_board_units = max(0, self.heparin_on_board_units)

        return dose

    def get_time_since_last_act(self) -> float | None:
        """Get time since last ACT in minutes."""
        if self.last_act_time is None:
            return None
        return (time.time() - self.last_act_time) / 60.0

    def needs_act_check(self, interval_minutes: float = 30.0) -> bool:
        """Check if ACT recheck is needed."""
        time_since = self.get_time_since_last_act()
        if time_since is None:
            return True
        return time_since >= interval_minutes

    def get_heparin_infusion_rate(self, target_concentration_u_ml: float = 3.0) -> float:
        """
        Calculate heparin infusion rate for maintaining concentration.

        Args:
            target_concentration_u_ml: Target heparin concentration

        Returns:
            Infusion rate in units/hour
        """
        # Based on clearance (approximately 1.5 ml/kg/min for heparin)
        clearance_ml_hr = self.patient_weight_kg * 1.5 * 60
        return target_concentration_u_ml * clearance_ml_hr

    def estimate_heparin_level(self) -> float:
        """
        Estimate current circulating heparin level.

        Returns:
            Estimated heparin in units/ml
        """
        if self.total_heparin_units == 0:
            return 0.0

        # Simple pharmacokinetic model
        if self.heparinization_time is not None:
            elapsed_hours = (time.time() - self.heparinization_time) / 3600.0
            half_life_hours = 1.5
            remaining_fraction = 0.5 ** (elapsed_hours / half_life_hours)
            remaining_units = self.total_heparin_units * remaining_fraction

            # Account for protamine reversal
            reversed_units = self.total_protamine_mg * 100 / self.targets.protamine_ratio
            remaining_units -= reversed_units
            remaining_units = max(0, remaining_units)

            return remaining_units / self.estimated_blood_volume_ml

        return self.total_heparin_units / self.estimated_blood_volume_ml

    def get_status(self) -> dict:
        """Get comprehensive anticoagulation status."""
        return {
            "is_active": self.is_active,
            "status": self.status.name,
            "anticoagulant": self.anticoagulant.name,
            "act": {
                "baseline_seconds": self.baseline_act,
                "current_seconds": self.current_act,
                "target_min_seconds": self.targets.min_bypass_act_seconds,
                "is_therapeutic": (
                    self.current_act >= self.targets.min_bypass_act_seconds
                    if self.current_act else False
                ),
                "time_since_last_min": (
                    round(self.get_time_since_last_act(), 1)
                    if self.get_time_since_last_act() else None
                ),
                "needs_recheck": self.needs_act_check(),
                "total_readings": len(self.act_readings)
            },
            "heparin": {
                "total_units": round(self.total_heparin_units, 0),
                "estimated_on_board_units": round(self.heparin_on_board_units, 0),
                "estimated_level_u_ml": round(self.estimate_heparin_level(), 2),
                "doses_given": len(self.heparin_doses)
            },
            "protamine": {
                "total_mg": round(self.total_protamine_mg, 1),
                "doses_given": len(self.protamine_doses),
                "infusion_active": self.protamine_infusion_active
            },
            "hms": {
                "available": self.hms.is_available,
                "sensitivity": round(self.hms.patient_heparin_sensitivity, 2)
            },
            "recommendations": {
                "initial_heparin_dose": round(self.calculate_initial_heparin_dose(), 0),
                "supplemental_dose": round(self.calculate_supplemental_heparin(), 0),
                "protamine_dose": round(self.calculate_protamine_dose(), 1)
            }
        }

    def get_dose_history(self) -> dict:
        """Get history of all anticoagulation doses."""
        return {
            "heparin": [
                {
                    "timestamp": d.timestamp,
                    "dose_units": d.dose_units,
                    "indication": d.indication
                }
                for d in self.heparin_doses
            ],
            "protamine": [
                {
                    "timestamp": d.timestamp,
                    "dose_mg": d.dose_mg,
                    "duration_min": d.infusion_duration_min
                }
                for d in self.protamine_doses
            ],
            "act_readings": [
                {
                    "timestamp": r.timestamp,
                    "value_seconds": r.value_seconds,
                    "method": r.method.name,
                    "is_baseline": r.is_baseline
                }
                for r in self.act_readings
            ]
        }
