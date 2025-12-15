"""
Suction and Vent Management System

Management of surgical field blood salvage and cardiac venting is critical
for maintaining adequate venous return and minimizing blood loss.

This module implements:
- Cardiotomy suction control
- Left heart vent management
- Aortic root vent/suction
- Cell saver interface
- Suction-induced hemolysis monitoring
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time


class SuctionType(Enum):
    """Types of suction in the bypass circuit."""
    CARDIOTOMY = auto()       # Surgical field suction
    LV_VENT = auto()          # Left ventricular vent
    LA_VENT = auto()          # Left atrial vent
    PA_VENT = auto()          # Pulmonary artery vent
    AORTIC_ROOT = auto()      # Aortic root suction
    CELL_SAVER = auto()       # Cell salvage suction


class VentMode(Enum):
    """Operating modes for vents."""
    OFF = auto()
    GRAVITY = auto()          # Passive gravity drainage
    ACTIVE_SUCTION = auto()   # Active suction
    INTERMITTENT = auto()     # Intermittent cycling


@dataclass
class SuctionLimits:
    """Safety limits for suction systems."""
    max_cardiotomy_vacuum_mmhg: float = -150.0
    max_vent_vacuum_mmhg: float = -100.0
    max_suction_flow_ml_min: float = 1000.0
    min_vacuum_for_flow_mmhg: float = -20.0
    hemolysis_warning_threshold: float = 50.0  # mg/dL free Hb


@dataclass
class SuctionChannel:
    """A single suction/vent channel."""
    name: str
    suction_type: SuctionType
    is_active: bool = False
    mode: VentMode = VentMode.OFF

    # Vacuum control
    target_vacuum_mmhg: float = -80.0
    actual_vacuum_mmhg: float = 0.0
    max_vacuum_mmhg: float = -150.0

    # Flow tracking
    flow_rate_ml_min: float = 0.0
    total_volume_ml: float = 0.0

    # Occlusion detection
    is_occluded: bool = False
    occlusion_alarm: bool = False

    def set_vacuum(self, vacuum_mmhg: float) -> bool:
        """Set target vacuum level."""
        if vacuum_mmhg > 0:
            return False
        if vacuum_mmhg < self.max_vacuum_mmhg:
            return False
        self.target_vacuum_mmhg = vacuum_mmhg
        return True

    def start(self, mode: VentMode = VentMode.ACTIVE_SUCTION) -> None:
        """Start suction."""
        self.is_active = True
        self.mode = mode

    def stop(self) -> None:
        """Stop suction."""
        self.is_active = False
        self.mode = VentMode.OFF
        self.flow_rate_ml_min = 0.0

    def update(self, vacuum_mmhg: float, flow_ml_min: float) -> None:
        """Update readings."""
        self.actual_vacuum_mmhg = vacuum_mmhg
        self.flow_rate_ml_min = flow_ml_min

        # Check for occlusion (high vacuum, low flow)
        if self.is_active:
            if vacuum_mmhg < -100 and flow_ml_min < 10:
                self.is_occluded = True
            else:
                self.is_occluded = False


@dataclass
class CardiotomyReservoir:
    """
    Cardiotomy reservoir for collecting suctioned blood.

    Includes defoaming and filtering before return to main circuit.
    """
    capacity_ml: float = 3000.0
    current_level_ml: float = 0.0
    low_level_alarm_ml: float = 100.0
    high_level_alarm_ml: float = 2500.0

    # Defoaming status
    defoamer_active: bool = True
    filter_pore_size_microns: float = 40.0

    # Blood quality
    estimated_hemolysis_mg_dl: float = 0.0

    def update_level(self, level_ml: float) -> None:
        """Update reservoir level."""
        self.current_level_ml = max(0, min(level_ml, self.capacity_ml))

    def is_level_low(self) -> bool:
        """Check if level is low."""
        return self.current_level_ml < self.low_level_alarm_ml

    def is_level_high(self) -> bool:
        """Check if level is high."""
        return self.current_level_ml > self.high_level_alarm_ml

    def get_fill_percentage(self) -> float:
        """Get fill level as percentage."""
        return (self.current_level_ml / self.capacity_ml) * 100.0


class SuctionController:
    """
    Central controller for all suction and vent channels.
    """

    def __init__(self):
        """Initialize suction controller."""
        self.is_active: bool = False

        # Suction channels
        self.channels: dict[str, SuctionChannel] = {}
        self._initialize_channels()

        # Cardiotomy reservoir
        self.cardiotomy_reservoir = CardiotomyReservoir()

        # Totals
        self.total_suctioned_ml: float = 0.0
        self.total_returned_ml: float = 0.0

        # Safety
        self.limits = SuctionLimits()

        # Hemolysis monitoring
        self.free_hemoglobin_mg_dl: float = 0.0
        self.hemolysis_warning: bool = False

        # Callbacks
        self._alarm_callbacks: list[Callable[[str, str], None]] = []

    def _initialize_channels(self) -> None:
        """Set up standard suction channels."""
        channels = [
            ("cardiotomy_1", SuctionType.CARDIOTOMY, -80.0, -150.0),
            ("cardiotomy_2", SuctionType.CARDIOTOMY, -80.0, -150.0),
            ("lv_vent", SuctionType.LV_VENT, -60.0, -100.0),
            ("la_vent", SuctionType.LA_VENT, -60.0, -100.0),
            ("aortic_root", SuctionType.AORTIC_ROOT, -40.0, -80.0),
            ("cell_saver", SuctionType.CELL_SAVER, -100.0, -200.0),
        ]

        for name, suction_type, target_vac, max_vac in channels:
            self.channels[name] = SuctionChannel(
                name=name,
                suction_type=suction_type,
                target_vacuum_mmhg=target_vac,
                max_vacuum_mmhg=max_vac
            )

    def register_alarm_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register alarm callback."""
        self._alarm_callbacks.append(callback)

    def _trigger_alarm(self, level: str, message: str) -> None:
        """Trigger alarm callbacks."""
        for callback in self._alarm_callbacks:
            callback(level, message)

    def activate(self) -> None:
        """Activate suction system."""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate suction system."""
        # Stop all channels
        for channel in self.channels.values():
            channel.stop()
        self.is_active = False

    def start_channel(self, channel_name: str,
                      mode: VentMode = VentMode.ACTIVE_SUCTION,
                      vacuum_mmhg: float | None = None) -> bool:
        """
        Start a suction channel.

        Args:
            channel_name: Name of channel to start
            mode: Operating mode
            vacuum_mmhg: Target vacuum (optional)

        Returns:
            True if started successfully
        """
        if channel_name not in self.channels:
            return False

        channel = self.channels[channel_name]

        if vacuum_mmhg is not None:
            if not channel.set_vacuum(vacuum_mmhg):
                return False

        channel.start(mode)
        return True

    def stop_channel(self, channel_name: str) -> bool:
        """Stop a suction channel."""
        if channel_name not in self.channels:
            return False

        self.channels[channel_name].stop()
        return True

    def set_channel_vacuum(self, channel_name: str, vacuum_mmhg: float) -> bool:
        """Set vacuum level for a channel."""
        if channel_name not in self.channels:
            return False

        return self.channels[channel_name].set_vacuum(vacuum_mmhg)

    def update_channel(self, channel_name: str,
                       vacuum_mmhg: float,
                       flow_ml_min: float) -> None:
        """Update a channel's readings."""
        if channel_name not in self.channels:
            return

        channel = self.channels[channel_name]
        channel.update(vacuum_mmhg, flow_ml_min)

        # Accumulate volume
        if channel.is_active and flow_ml_min > 0:
            # Approximate volume (assuming 1 second updates)
            volume = flow_ml_min / 60.0
            channel.total_volume_ml += volume
            self.total_suctioned_ml += volume

            # Add to cardiotomy reservoir if not cell saver
            if channel.suction_type != SuctionType.CELL_SAVER:
                self.cardiotomy_reservoir.update_level(
                    self.cardiotomy_reservoir.current_level_ml + volume
                )

        # Check for alarms
        self._check_channel_alarms(channel)

    def _check_channel_alarms(self, channel: SuctionChannel) -> None:
        """Check channel for alarm conditions."""
        if not channel.is_active:
            return

        # Occlusion alarm
        if channel.is_occluded:
            self._trigger_alarm("warning",
                f"Suction occlusion detected: {channel.name}")

        # Over-vacuum alarm
        if channel.actual_vacuum_mmhg < channel.max_vacuum_mmhg:
            self._trigger_alarm("warning",
                f"Excessive vacuum on {channel.name}: {channel.actual_vacuum_mmhg} mmHg")

    def update_reservoir_level(self, level_ml: float) -> None:
        """Update cardiotomy reservoir level."""
        self.cardiotomy_reservoir.update_level(level_ml)

        # Check alarms
        if self.cardiotomy_reservoir.is_level_high():
            self._trigger_alarm("warning",
                f"Cardiotomy reservoir high: {level_ml:.0f} ml")
        elif self.cardiotomy_reservoir.is_level_low():
            self._trigger_alarm("info", "Cardiotomy reservoir low")

    def update_hemolysis(self, free_hb_mg_dl: float) -> None:
        """Update free hemoglobin level for hemolysis monitoring."""
        self.free_hemoglobin_mg_dl = free_hb_mg_dl

        if free_hb_mg_dl > self.limits.hemolysis_warning_threshold:
            self.hemolysis_warning = True
            self._trigger_alarm("warning",
                f"Elevated hemolysis: {free_hb_mg_dl:.0f} mg/dL free Hb")
        else:
            self.hemolysis_warning = False

    def return_cardiotomy_blood(self, volume_ml: float) -> None:
        """Record blood returned from cardiotomy to main circuit."""
        self.total_returned_ml += volume_ml
        current = self.cardiotomy_reservoir.current_level_ml
        self.cardiotomy_reservoir.update_level(current - volume_ml)

    def get_active_channels(self) -> list[str]:
        """Get list of active channel names."""
        return [name for name, ch in self.channels.items() if ch.is_active]

    def get_total_flow(self) -> float:
        """Get total flow from all active channels."""
        return sum(ch.flow_rate_ml_min for ch in self.channels.values() if ch.is_active)

    def get_status(self) -> dict:
        """Get comprehensive suction system status."""
        return {
            "is_active": self.is_active,
            "channels": {
                name: {
                    "type": ch.suction_type.name,
                    "active": ch.is_active,
                    "mode": ch.mode.name,
                    "vacuum_mmhg": round(ch.actual_vacuum_mmhg, 1),
                    "target_vacuum_mmhg": round(ch.target_vacuum_mmhg, 1),
                    "flow_ml_min": round(ch.flow_rate_ml_min, 1),
                    "total_volume_ml": round(ch.total_volume_ml, 1),
                    "is_occluded": ch.is_occluded
                }
                for name, ch in self.channels.items()
            },
            "cardiotomy_reservoir": {
                "level_ml": round(self.cardiotomy_reservoir.current_level_ml, 1),
                "fill_percent": round(self.cardiotomy_reservoir.get_fill_percentage(), 1),
                "is_high": self.cardiotomy_reservoir.is_level_high(),
                "is_low": self.cardiotomy_reservoir.is_level_low()
            },
            "totals": {
                "suctioned_ml": round(self.total_suctioned_ml, 1),
                "returned_ml": round(self.total_returned_ml, 1),
                "total_flow_ml_min": round(self.get_total_flow(), 1)
            },
            "hemolysis": {
                "free_hb_mg_dl": round(self.free_hemoglobin_mg_dl, 1),
                "warning": self.hemolysis_warning
            }
        }
