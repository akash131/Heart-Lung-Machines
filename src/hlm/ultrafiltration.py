"""
Hemoconcentrator and Ultrafiltration System

Ultrafiltration is used during cardiopulmonary bypass to:
- Remove excess fluid and reduce hemodilution
- Concentrate red blood cells and increase hematocrit
- Remove inflammatory mediators
- Correct electrolyte imbalances

This module implements:
- Conventional ultrafiltration (CUF) during bypass
- Modified ultrafiltration (MUF) after bypass
- Zero-balance ultrafiltration (ZBUF)
- Dialysis/hemofiltration capabilities
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time


class UltrafiltrationMode(Enum):
    """Modes of ultrafiltration operation."""
    OFF = auto()
    CUF = auto()           # Conventional UF - during bypass
    MUF = auto()           # Modified UF - post-bypass
    ZBUF = auto()          # Zero-balance UF - with replacement
    DIALYSIS = auto()      # Dialysis mode with dialysate


class FilterType(Enum):
    """Types of hemoconcentrator filters."""
    POLYSULFONE = auto()
    POLYETHERSULFONE = auto()
    AN69 = auto()          # Acrylonitrile
    PMMA = auto()          # Polymethylmethacrylate


@dataclass
class FilterSpecifications:
    """Specifications for a hemoconcentrator filter."""
    filter_type: FilterType = FilterType.POLYSULFONE
    surface_area_m2: float = 0.7
    max_blood_flow_ml_min: float = 500.0
    max_tmp_mmhg: float = 500.0  # Maximum transmembrane pressure
    priming_volume_ml: float = 35.0
    molecular_weight_cutoff_daltons: int = 65000
    max_ultrafiltrate_rate_ml_hr: float = 2000.0


@dataclass
class UltrafiltrationSession:
    """Record of an ultrafiltration session."""
    start_time: float
    end_time: float | None = None
    mode: UltrafiltrationMode = UltrafiltrationMode.CUF
    total_ultrafiltrate_ml: float = 0.0
    total_replacement_ml: float = 0.0
    net_fluid_removal_ml: float = 0.0
    average_rate_ml_hr: float = 0.0
    starting_hematocrit: float = 0.0
    ending_hematocrit: float = 0.0


@dataclass
class UltrafiltrationLimits:
    """Safety limits for ultrafiltration."""
    max_tmp_mmhg: float = 400.0           # Max transmembrane pressure
    max_uf_rate_ml_hr: float = 1500.0     # Max ultrafiltrate rate
    min_blood_flow_ml_min: float = 100.0  # Min blood flow through filter
    max_blood_flow_ml_min: float = 500.0  # Max blood flow through filter
    max_net_removal_ml: float = 3000.0    # Max total fluid removal
    target_hematocrit_max: float = 35.0   # Don't over-concentrate


class UltrafiltrationPump:
    """Pump for controlling ultrafiltrate removal."""

    def __init__(self):
        self.is_active: bool = False
        self.rpm: float = 0.0
        self.max_rpm: float = 300.0
        self.target_rate_ml_hr: float = 0.0
        self.actual_rate_ml_hr: float = 0.0

    def set_rate(self, rate_ml_hr: float) -> bool:
        """Set ultrafiltration rate."""
        if 0 <= rate_ml_hr <= 2000:
            self.target_rate_ml_hr = rate_ml_hr
            self.rpm = rate_ml_hr / 10.0  # Approximate
            return True
        return False

    def start(self) -> None:
        """Start the pump."""
        self.is_active = True

    def stop(self) -> None:
        """Stop the pump."""
        self.is_active = False
        self.actual_rate_ml_hr = 0.0

    def update_actual_rate(self, rate_ml_hr: float) -> None:
        """Update actual measured rate."""
        self.actual_rate_ml_hr = rate_ml_hr


class ReplacementFluidController:
    """Controller for replacement fluid in ZBUF mode."""

    def __init__(self):
        self.is_active: bool = False
        self.target_rate_ml_hr: float = 0.0
        self.actual_rate_ml_hr: float = 0.0
        self.total_delivered_ml: float = 0.0

        # Fluid composition tracking
        self.fluid_type: str = "balanced_crystalloid"
        self.potassium_meq_l: float = 4.0
        self.sodium_meq_l: float = 140.0

    def set_rate(self, rate_ml_hr: float) -> None:
        """Set replacement fluid rate."""
        self.target_rate_ml_hr = rate_ml_hr

    def start(self) -> None:
        """Start replacement fluid."""
        self.is_active = True

    def stop(self) -> None:
        """Stop replacement fluid."""
        self.is_active = False

    def update_volume(self, volume_ml: float) -> None:
        """Update total volume delivered."""
        self.total_delivered_ml += volume_ml


class HemoconcentratorSystem:
    """
    Complete hemoconcentrator/ultrafiltration system.

    Provides comprehensive ultrafiltration capabilities including
    CUF, MUF, ZBUF, and dialysis modes.
    """

    def __init__(self):
        """Initialize hemoconcentrator system."""
        self.is_active: bool = False
        self.mode = UltrafiltrationMode.OFF

        # Filter
        self.filter_specs = FilterSpecifications()
        self.filter_in_use: bool = False
        self.filter_use_time_minutes: float = 0.0

        # Pumps and controllers
        self.uf_pump = UltrafiltrationPump()
        self.replacement_controller = ReplacementFluidController()

        # Monitoring
        self.blood_flow_ml_min: float = 0.0
        self.inlet_pressure_mmhg: float = 0.0
        self.outlet_pressure_mmhg: float = 0.0
        self.transmembrane_pressure_mmhg: float = 0.0
        self.ultrafiltrate_rate_ml_hr: float = 0.0

        # Totals
        self.total_ultrafiltrate_ml: float = 0.0
        self.total_replacement_ml: float = 0.0
        self.net_fluid_removal_ml: float = 0.0

        # Sessions
        self.sessions: list[UltrafiltrationSession] = []
        self.current_session: UltrafiltrationSession | None = None

        # Safety
        self.limits = UltrafiltrationLimits()

        # Timing
        self.start_time: float | None = None
        self.last_update_time: float = time.time()

        # Hematocrit tracking
        self.current_hematocrit: float = 0.0
        self.target_hematocrit: float = 30.0

        # Callbacks
        self._alarm_callbacks: list[Callable[[str, str], None]] = []

    def register_alarm_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register alarm callback."""
        self._alarm_callbacks.append(callback)

    def _trigger_alarm(self, level: str, message: str) -> None:
        """Trigger alarm callbacks."""
        for callback in self._alarm_callbacks:
            callback(level, message)

    def prime_filter(self) -> bool:
        """Prime the hemoconcentrator filter."""
        if self.filter_in_use:
            return False

        # In real system, would run priming sequence
        self.filter_in_use = True
        return True

    def start_ultrafiltration(self,
                              mode: UltrafiltrationMode,
                              rate_ml_hr: float,
                              blood_flow_ml_min: float = 200.0) -> bool:
        """
        Start ultrafiltration.

        Args:
            mode: UF mode to use
            rate_ml_hr: Target ultrafiltrate rate
            blood_flow_ml_min: Blood flow through filter

        Returns:
            True if started successfully
        """
        if not self.filter_in_use:
            self._trigger_alarm("warning", "Filter not primed")
            return False

        if rate_ml_hr > self.limits.max_uf_rate_ml_hr:
            self._trigger_alarm("warning", f"Rate {rate_ml_hr} exceeds max {self.limits.max_uf_rate_ml_hr}")
            return False

        if blood_flow_ml_min < self.limits.min_blood_flow_ml_min:
            self._trigger_alarm("warning", "Blood flow too low for UF")
            return False

        self.mode = mode
        self.is_active = True
        self.blood_flow_ml_min = blood_flow_ml_min
        self.start_time = time.time()

        # Set pump rate
        self.uf_pump.set_rate(rate_ml_hr)
        self.uf_pump.start()

        # Start replacement if ZBUF
        if mode == UltrafiltrationMode.ZBUF:
            self.replacement_controller.set_rate(rate_ml_hr)  # Match UF rate
            self.replacement_controller.start()

        # Start session
        self.current_session = UltrafiltrationSession(
            start_time=time.time(),
            mode=mode,
            starting_hematocrit=self.current_hematocrit
        )

        return True

    def stop_ultrafiltration(self) -> UltrafiltrationSession | None:
        """
        Stop ultrafiltration.

        Returns:
            Completed session record
        """
        if not self.is_active:
            return None

        self.is_active = False
        self.uf_pump.stop()
        self.replacement_controller.stop()

        # Complete session
        session = None
        if self.current_session is not None:
            self.current_session.end_time = time.time()
            self.current_session.total_ultrafiltrate_ml = self.total_ultrafiltrate_ml
            self.current_session.total_replacement_ml = self.total_replacement_ml
            self.current_session.net_fluid_removal_ml = self.net_fluid_removal_ml
            self.current_session.ending_hematocrit = self.current_hematocrit

            # Calculate average rate
            duration_hr = (self.current_session.end_time - self.current_session.start_time) / 3600.0
            if duration_hr > 0:
                self.current_session.average_rate_ml_hr = (
                    self.current_session.total_ultrafiltrate_ml / duration_hr
                )

            session = self.current_session
            self.sessions.append(session)
            self.current_session = None

        self.mode = UltrafiltrationMode.OFF
        return session

    def set_rate(self, rate_ml_hr: float) -> bool:
        """Adjust ultrafiltration rate."""
        if not self.is_active:
            return False

        if rate_ml_hr > self.limits.max_uf_rate_ml_hr:
            return False

        self.uf_pump.set_rate(rate_ml_hr)

        # Adjust replacement for ZBUF
        if self.mode == UltrafiltrationMode.ZBUF:
            self.replacement_controller.set_rate(rate_ml_hr)

        return True

    def set_blood_flow(self, flow_ml_min: float) -> bool:
        """Set blood flow through filter."""
        if flow_ml_min < self.limits.min_blood_flow_ml_min:
            return False
        if flow_ml_min > self.limits.max_blood_flow_ml_min:
            return False

        self.blood_flow_ml_min = flow_ml_min
        return True

    def update_readings(self,
                       inlet_pressure: float,
                       outlet_pressure: float,
                       uf_rate: float,
                       hematocrit: float | None = None) -> None:
        """
        Update sensor readings.

        Args:
            inlet_pressure: Filter inlet pressure (mmHg)
            outlet_pressure: Filter outlet pressure (mmHg)
            uf_rate: Measured ultrafiltrate rate (ml/hr)
            hematocrit: Current hematocrit if available
        """
        now = time.time()
        elapsed_hr = (now - self.last_update_time) / 3600.0
        self.last_update_time = now

        # Update pressures
        self.inlet_pressure_mmhg = inlet_pressure
        self.outlet_pressure_mmhg = outlet_pressure

        # Calculate TMP (simplified - actual would include UF pressure)
        self.transmembrane_pressure_mmhg = (
            (inlet_pressure + outlet_pressure) / 2.0
        )

        # Update rate
        self.ultrafiltrate_rate_ml_hr = uf_rate
        self.uf_pump.update_actual_rate(uf_rate)

        # Accumulate volumes
        if self.is_active and elapsed_hr > 0:
            uf_volume = uf_rate * elapsed_hr
            self.total_ultrafiltrate_ml += uf_volume

            if self.mode == UltrafiltrationMode.ZBUF:
                replacement_volume = self.replacement_controller.target_rate_ml_hr * elapsed_hr
                self.total_replacement_ml += replacement_volume
                self.replacement_controller.update_volume(replacement_volume)

            self.net_fluid_removal_ml = self.total_ultrafiltrate_ml - self.total_replacement_ml

            # Update filter use time
            self.filter_use_time_minutes += (elapsed_hr * 60)

        # Update hematocrit
        if hematocrit is not None:
            self.current_hematocrit = hematocrit

        # Check alarms
        self._check_alarms()

    def _check_alarms(self) -> None:
        """Check for alarm conditions."""
        # TMP alarm
        if self.transmembrane_pressure_mmhg > self.limits.max_tmp_mmhg:
            self._trigger_alarm("critical",
                f"TMP exceeded: {self.transmembrane_pressure_mmhg:.0f} mmHg")

        # Max removal alarm
        if self.net_fluid_removal_ml > self.limits.max_net_removal_ml:
            self._trigger_alarm("warning",
                f"Net fluid removal {self.net_fluid_removal_ml:.0f} ml exceeds limit")

        # Over-concentration alarm
        if self.current_hematocrit > self.limits.target_hematocrit_max:
            self._trigger_alarm("warning",
                f"Hematocrit {self.current_hematocrit:.1f}% exceeds target")

        # Low blood flow alarm
        if self.is_active and self.blood_flow_ml_min < self.limits.min_blood_flow_ml_min:
            self._trigger_alarm("warning",
                f"Blood flow low: {self.blood_flow_ml_min:.0f} ml/min")

    def calculate_expected_hematocrit(self,
                                       initial_hct: float,
                                       blood_volume_ml: float,
                                       fluid_removal_ml: float) -> float:
        """
        Calculate expected hematocrit after fluid removal.

        Args:
            initial_hct: Starting hematocrit (%)
            blood_volume_ml: Estimated blood volume
            fluid_removal_ml: Volume to be removed

        Returns:
            Expected hematocrit after removal
        """
        if blood_volume_ml <= fluid_removal_ml:
            return initial_hct

        # RBC volume stays constant, plasma volume decreases
        rbc_volume = (initial_hct / 100.0) * blood_volume_ml
        new_blood_volume = blood_volume_ml - fluid_removal_ml
        new_hct = (rbc_volume / new_blood_volume) * 100.0

        return min(new_hct, 50.0)  # Cap at physiological limit

    def calculate_fluid_removal_for_target_hct(self,
                                                current_hct: float,
                                                target_hct: float,
                                                blood_volume_ml: float) -> float:
        """
        Calculate fluid removal needed to reach target hematocrit.

        Args:
            current_hct: Current hematocrit (%)
            target_hct: Target hematocrit (%)
            blood_volume_ml: Estimated blood volume

        Returns:
            Volume to remove in ml
        """
        if target_hct <= current_hct:
            return 0.0

        # RBC volume = Hct × Blood volume
        # New blood volume = RBC volume / target Hct
        rbc_volume = (current_hct / 100.0) * blood_volume_ml
        target_blood_volume = rbc_volume / (target_hct / 100.0)

        return max(0.0, blood_volume_ml - target_blood_volume)

    def estimate_time_to_target(self,
                                 target_removal_ml: float,
                                 rate_ml_hr: float) -> float:
        """
        Estimate time to achieve target fluid removal.

        Args:
            target_removal_ml: Target fluid removal
            rate_ml_hr: Ultrafiltration rate

        Returns:
            Time in minutes
        """
        if rate_ml_hr <= 0:
            return float('inf')

        remaining_ml = target_removal_ml - self.net_fluid_removal_ml
        if remaining_ml <= 0:
            return 0.0

        return (remaining_ml / rate_ml_hr) * 60.0

    def get_filter_life_remaining(self) -> float:
        """
        Estimate remaining filter life as percentage.

        Based on TMP trends and use time.
        """
        # Simple model based on use time (actual would use TMP trends)
        max_use_minutes = 480.0  # 8 hours typical max
        used_fraction = self.filter_use_time_minutes / max_use_minutes

        # Factor in TMP
        tmp_factor = self.transmembrane_pressure_mmhg / self.limits.max_tmp_mmhg

        life_remaining = max(0.0, (1.0 - max(used_fraction, tmp_factor)) * 100.0)
        return life_remaining

    def get_status(self) -> dict:
        """Get comprehensive system status."""
        return {
            "is_active": self.is_active,
            "mode": self.mode.name,
            "filter": {
                "in_use": self.filter_in_use,
                "type": self.filter_specs.filter_type.name,
                "surface_area_m2": self.filter_specs.surface_area_m2,
                "use_time_minutes": round(self.filter_use_time_minutes, 1),
                "life_remaining_percent": round(self.get_filter_life_remaining(), 1)
            },
            "pressures": {
                "inlet_mmhg": round(self.inlet_pressure_mmhg, 1),
                "outlet_mmhg": round(self.outlet_pressure_mmhg, 1),
                "tmp_mmhg": round(self.transmembrane_pressure_mmhg, 1)
            },
            "flows": {
                "blood_ml_min": round(self.blood_flow_ml_min, 1),
                "uf_rate_ml_hr": round(self.ultrafiltrate_rate_ml_hr, 1),
                "target_rate_ml_hr": round(self.uf_pump.target_rate_ml_hr, 1),
                "replacement_rate_ml_hr": round(self.replacement_controller.target_rate_ml_hr, 1)
            },
            "volumes": {
                "total_ultrafiltrate_ml": round(self.total_ultrafiltrate_ml, 1),
                "total_replacement_ml": round(self.total_replacement_ml, 1),
                "net_removal_ml": round(self.net_fluid_removal_ml, 1)
            },
            "hematocrit": {
                "current_percent": round(self.current_hematocrit, 1),
                "target_percent": round(self.target_hematocrit, 1)
            },
            "sessions": {
                "count": len(self.sessions),
                "current_active": self.current_session is not None
            }
        }

    def get_session_history(self) -> list[dict]:
        """Get history of ultrafiltration sessions."""
        return [
            {
                "mode": s.mode.name,
                "duration_minutes": (
                    round((s.end_time - s.start_time) / 60.0, 1)
                    if s.end_time else None
                ),
                "total_uf_ml": round(s.total_ultrafiltrate_ml, 1),
                "net_removal_ml": round(s.net_fluid_removal_ml, 1),
                "average_rate_ml_hr": round(s.average_rate_ml_hr, 1),
                "hct_change": round(s.ending_hematocrit - s.starting_hematocrit, 1)
            }
            for s in self.sessions
        ]
