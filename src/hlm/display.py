"""
User Interface and Display System

The display system provides visual presentation of perfusion data
for the perfusionist and surgical team.

This module implements:
- Screen layout management
- Parameter display formatting
- Trend graph data preparation
- Alarm visualization
- Touch screen interface support
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Any
import time


class DisplayMode(Enum):
    """Display mode configurations."""
    STANDARD = auto()       # Standard bypass view
    COMPACT = auto()        # Compact view with essentials
    DETAILED = auto()       # Detailed view with all parameters
    TRENDING = auto()       # Focus on trends
    ALARM_FOCUS = auto()    # Alarm-centric view
    SETUP = auto()          # Setup/configuration view


class ParameterStatus(Enum):
    """Visual status for parameters."""
    NORMAL = auto()
    WARNING = auto()
    CRITICAL = auto()
    INACTIVE = auto()
    UPDATING = auto()


class AlarmIndicatorState(Enum):
    """State of alarm indicators."""
    OFF = auto()
    STEADY = auto()
    FLASHING_SLOW = auto()
    FLASHING_FAST = auto()


@dataclass
class DisplayColor:
    """RGB color definition."""
    r: int = 255
    g: int = 255
    b: int = 255

    def to_hex(self) -> str:
        """Convert to hex string."""
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"

    @classmethod
    def normal(cls) -> "DisplayColor":
        return cls(0, 255, 0)  # Green

    @classmethod
    def warning(cls) -> "DisplayColor":
        return cls(255, 255, 0)  # Yellow

    @classmethod
    def critical(cls) -> "DisplayColor":
        return cls(255, 0, 0)  # Red

    @classmethod
    def inactive(cls) -> "DisplayColor":
        return cls(128, 128, 128)  # Gray


@dataclass
class DisplayParameter:
    """A parameter formatted for display."""
    name: str
    value: str
    unit: str
    status: ParameterStatus = ParameterStatus.NORMAL
    color: DisplayColor = field(default_factory=DisplayColor.normal)
    is_editable: bool = False
    decimal_places: int = 1
    min_value: float | None = None
    max_value: float | None = None
    trend_direction: str = ""  # "up", "down", "stable", ""

    def format_value(self, raw_value: float) -> str:
        """Format a raw value for display."""
        if self.decimal_places == 0:
            return f"{int(raw_value)}"
        return f"{raw_value:.{self.decimal_places}f}"


@dataclass
class TrendDataPoint:
    """Data point for trend display."""
    timestamp: float
    value: float
    is_valid: bool = True


@dataclass
class TrendConfig:
    """Configuration for trend display."""
    parameter_name: str
    time_window_minutes: float = 60.0
    y_min: float | None = None
    y_max: float | None = None
    show_target_line: bool = False
    target_value: float | None = None
    color: DisplayColor = field(default_factory=DisplayColor.normal)


@dataclass
class ScreenLayout:
    """Layout definition for a screen."""
    name: str
    mode: DisplayMode
    parameter_positions: dict[str, tuple[int, int]]  # name -> (x, y)
    trend_positions: dict[str, tuple[int, int, int, int]]  # name -> (x, y, w, h)
    alarm_bar_position: tuple[int, int, int, int] = (0, 0, 800, 50)
    status_bar_position: tuple[int, int, int, int] = (0, 550, 800, 50)


class DisplayFormatter:
    """Formats data for display presentation."""

    def __init__(self):
        self.parameter_configs: dict[str, dict] = {}
        self._initialize_configs()

    def _initialize_configs(self) -> None:
        """Initialize display configurations for standard parameters."""
        self.parameter_configs = {
            "arterial_flow": {
                "display_name": "ART FLOW",
                "unit": "ml/min",
                "decimals": 0,
                "normal_range": (2000, 6000),
                "warning_range": (1500, 6500),
                "critical_low": 1000,
                "critical_high": 7000
            },
            "pump_rpm": {
                "display_name": "PUMP",
                "unit": "rpm",
                "decimals": 0,
                "normal_range": (0, 200),
                "warning_range": (0, 220),
                "critical_high": 250
            },
            "arterial_pressure": {
                "display_name": "ART PRESS",
                "unit": "mmHg",
                "decimals": 0,
                "normal_range": (150, 300),
                "warning_range": (100, 350),
                "critical_low": 50,
                "critical_high": 400
            },
            "venous_pressure": {
                "display_name": "VEN PRESS",
                "unit": "mmHg",
                "decimals": 0,
                "normal_range": (-30, 20),
                "warning_range": (-50, 40),
                "critical_low": -100,
                "critical_high": 50
            },
            "reservoir_level": {
                "display_name": "LEVEL",
                "unit": "ml",
                "decimals": 0,
                "normal_range": (500, 3000),
                "warning_range": (300, 3500),
                "critical_low": 200
            },
            "arterial_temp": {
                "display_name": "ART TEMP",
                "unit": "°C",
                "decimals": 1,
                "normal_range": (28, 37),
                "warning_range": (20, 38),
                "critical_low": 15,
                "critical_high": 39
            },
            "venous_temp": {
                "display_name": "VEN TEMP",
                "unit": "°C",
                "decimals": 1,
                "normal_range": (28, 37),
                "warning_range": (20, 38)
            },
            "svo2": {
                "display_name": "SvO2",
                "unit": "%",
                "decimals": 0,
                "normal_range": (70, 85),
                "warning_range": (65, 90),
                "critical_low": 60
            },
            "hematocrit": {
                "display_name": "HCT",
                "unit": "%",
                "decimals": 0,
                "normal_range": (25, 35),
                "warning_range": (20, 40),
                "critical_low": 18
            },
            "act": {
                "display_name": "ACT",
                "unit": "sec",
                "decimals": 0,
                "normal_range": (480, 999),
                "warning_range": (450, 999),
                "critical_low": 400
            },
            "do2_index": {
                "display_name": "DO2i",
                "unit": "ml/min/m²",
                "decimals": 0,
                "normal_range": (300, 500),
                "warning_range": (280, 550),
                "critical_low": 270
            },
            "cardioplegia_pressure": {
                "display_name": "CP PRESS",
                "unit": "mmHg",
                "decimals": 0,
                "normal_range": (0, 120),
                "warning_range": (0, 140),
                "critical_high": 150
            },
            "cardioplegia_temp": {
                "display_name": "CP TEMP",
                "unit": "°C",
                "decimals": 1,
                "normal_range": (4, 10),
                "warning_range": (2, 15)
            }
        }

    def format_parameter(self,
                         param_name: str,
                         value: float,
                         previous_value: float | None = None) -> DisplayParameter:
        """
        Format a parameter for display.

        Args:
            param_name: Parameter name
            value: Current value
            previous_value: Previous value for trend

        Returns:
            Formatted display parameter
        """
        config = self.parameter_configs.get(param_name, {})

        display_name = config.get("display_name", param_name.upper())
        unit = config.get("unit", "")
        decimals = config.get("decimals", 1)

        # Determine status and color
        status, color = self._determine_status(value, config)

        # Determine trend
        trend = ""
        if previous_value is not None:
            diff = value - previous_value
            if abs(diff) > 0.01 * abs(value):  # 1% change threshold
                trend = "up" if diff > 0 else "down"
            else:
                trend = "stable"

        param = DisplayParameter(
            name=display_name,
            value=f"{value:.{decimals}f}" if decimals > 0 else f"{int(value)}",
            unit=unit,
            status=status,
            color=color,
            decimal_places=decimals,
            trend_direction=trend
        )

        return param

    def _determine_status(self,
                          value: float,
                          config: dict) -> tuple[ParameterStatus, DisplayColor]:
        """Determine status and color based on value and config."""
        critical_low = config.get("critical_low")
        critical_high = config.get("critical_high")
        warning_range = config.get("warning_range", (None, None))
        normal_range = config.get("normal_range", (None, None))

        # Check critical
        if critical_low is not None and value < critical_low:
            return ParameterStatus.CRITICAL, DisplayColor.critical()
        if critical_high is not None and value > critical_high:
            return ParameterStatus.CRITICAL, DisplayColor.critical()

        # Check warning
        if warning_range[0] is not None and value < warning_range[0]:
            return ParameterStatus.WARNING, DisplayColor.warning()
        if warning_range[1] is not None and value > warning_range[1]:
            return ParameterStatus.WARNING, DisplayColor.warning()

        # Check normal
        if normal_range[0] is not None and value < normal_range[0]:
            return ParameterStatus.WARNING, DisplayColor.warning()
        if normal_range[1] is not None and value > normal_range[1]:
            return ParameterStatus.WARNING, DisplayColor.warning()

        return ParameterStatus.NORMAL, DisplayColor.normal()


class AlarmDisplay:
    """Manages alarm display and indicators."""

    def __init__(self):
        self.active_alarms: list[dict] = []
        self.acknowledged_alarms: list[str] = []
        self.audio_enabled: bool = True
        self.audio_paused_until: float = 0.0

    def add_alarm(self, alarm_id: str, level: str, message: str) -> None:
        """Add an alarm to display."""
        self.active_alarms.append({
            "id": alarm_id,
            "level": level,
            "message": message,
            "timestamp": time.time(),
            "indicator_state": (
                AlarmIndicatorState.FLASHING_FAST
                if level == "CRITICAL"
                else AlarmIndicatorState.FLASHING_SLOW
            )
        })

    def remove_alarm(self, alarm_id: str) -> None:
        """Remove an alarm from display."""
        self.active_alarms = [a for a in self.active_alarms if a["id"] != alarm_id]

    def acknowledge_alarm(self, alarm_id: str) -> None:
        """Acknowledge an alarm (changes indicator state)."""
        for alarm in self.active_alarms:
            if alarm["id"] == alarm_id:
                alarm["indicator_state"] = AlarmIndicatorState.STEADY
                self.acknowledged_alarms.append(alarm_id)
                break

    def pause_audio(self, seconds: float = 120.0) -> None:
        """Pause alarm audio temporarily."""
        self.audio_paused_until = time.time() + seconds

    def is_audio_active(self) -> bool:
        """Check if audio should be active."""
        if not self.audio_enabled:
            return False
        if time.time() < self.audio_paused_until:
            return False
        # Check for unacknowledged alarms
        return any(a["id"] not in self.acknowledged_alarms for a in self.active_alarms)

    def get_highest_priority_alarm(self) -> dict | None:
        """Get the highest priority unacknowledged alarm."""
        unacked = [a for a in self.active_alarms
                   if a["id"] not in self.acknowledged_alarms]
        if not unacked:
            return None

        # Sort by level (CRITICAL > HIGH > etc.)
        level_priority = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        unacked.sort(key=lambda a: level_priority.get(a["level"], 5))
        return unacked[0]

    def get_display_data(self) -> dict:
        """Get alarm display data."""
        return {
            "active_count": len(self.active_alarms),
            "unacknowledged_count": len([
                a for a in self.active_alarms
                if a["id"] not in self.acknowledged_alarms
            ]),
            "audio_active": self.is_audio_active(),
            "highest_priority": self.get_highest_priority_alarm(),
            "alarms": [
                {
                    "id": a["id"],
                    "level": a["level"],
                    "message": a["message"],
                    "acknowledged": a["id"] in self.acknowledged_alarms,
                    "indicator_state": a["indicator_state"].name
                }
                for a in self.active_alarms
            ]
        }


class DisplayManager:
    """
    Central display management system.

    Coordinates all display elements and screen updates.
    """

    def __init__(self):
        """Initialize display manager."""
        self.is_active: bool = False
        self.current_mode = DisplayMode.STANDARD
        self.brightness: int = 100  # 0-100

        # Components
        self.formatter = DisplayFormatter()
        self.alarm_display = AlarmDisplay()

        # Current parameter values
        self.parameters: dict[str, DisplayParameter] = {}
        self.previous_values: dict[str, float] = {}

        # Trends
        self.trend_data: dict[str, list[TrendDataPoint]] = {}
        self.trend_configs: dict[str, TrendConfig] = {}

        # Screen layouts
        self.layouts: dict[DisplayMode, ScreenLayout] = {}
        self._initialize_layouts()

        # Timing
        self.last_update: float = 0.0
        self.update_interval_ms: int = 100  # 10 Hz update rate

        # Touch input callbacks
        self._touch_callbacks: dict[str, Callable] = {}

    def _initialize_layouts(self) -> None:
        """Initialize screen layouts."""
        # Standard layout
        self.layouts[DisplayMode.STANDARD] = ScreenLayout(
            name="Standard",
            mode=DisplayMode.STANDARD,
            parameter_positions={
                "arterial_flow": (50, 100),
                "pump_rpm": (50, 150),
                "arterial_pressure": (50, 200),
                "venous_pressure": (50, 250),
                "reservoir_level": (50, 300),
                "arterial_temp": (250, 100),
                "venous_temp": (250, 150),
                "svo2": (250, 200),
                "hematocrit": (250, 250),
                "act": (250, 300),
                "do2_index": (450, 100),
                "cardioplegia_pressure": (450, 200),
                "cardioplegia_temp": (450, 250),
            },
            trend_positions={
                "arterial_flow": (550, 100, 200, 100),
                "svo2": (550, 220, 200, 100),
                "arterial_temp": (550, 340, 200, 100),
            }
        )

        # Compact layout
        self.layouts[DisplayMode.COMPACT] = ScreenLayout(
            name="Compact",
            mode=DisplayMode.COMPACT,
            parameter_positions={
                "arterial_flow": (50, 100),
                "arterial_pressure": (50, 150),
                "reservoir_level": (50, 200),
                "arterial_temp": (200, 100),
                "svo2": (200, 150),
                "act": (200, 200),
            },
            trend_positions={}
        )

    def activate(self) -> None:
        """Activate display system."""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate display system."""
        self.is_active = False

    def set_mode(self, mode: DisplayMode) -> None:
        """Set display mode."""
        self.current_mode = mode

    def set_brightness(self, brightness: int) -> None:
        """Set display brightness (0-100)."""
        self.brightness = max(0, min(100, brightness))

    def update_parameter(self, param_name: str, value: float) -> DisplayParameter:
        """
        Update a parameter value.

        Args:
            param_name: Parameter name
            value: New value

        Returns:
            Formatted display parameter
        """
        previous = self.previous_values.get(param_name)
        self.previous_values[param_name] = value

        display_param = self.formatter.format_parameter(param_name, value, previous)
        self.parameters[param_name] = display_param

        # Add to trend data
        if param_name not in self.trend_data:
            self.trend_data[param_name] = []

        self.trend_data[param_name].append(TrendDataPoint(
            timestamp=time.time(),
            value=value
        ))

        # Limit trend data to 24 hours
        cutoff = time.time() - 86400
        self.trend_data[param_name] = [
            p for p in self.trend_data[param_name]
            if p.timestamp > cutoff
        ]

        self.last_update = time.time()
        return display_param

    def add_alarm(self, alarm_id: str, level: str, message: str) -> None:
        """Add alarm to display."""
        self.alarm_display.add_alarm(alarm_id, level, message)

    def remove_alarm(self, alarm_id: str) -> None:
        """Remove alarm from display."""
        self.alarm_display.remove_alarm(alarm_id)

    def acknowledge_alarm(self, alarm_id: str) -> None:
        """Acknowledge an alarm."""
        self.alarm_display.acknowledge_alarm(alarm_id)

    def get_trend_data(self,
                       param_name: str,
                       minutes: float = 60.0) -> list[dict]:
        """
        Get trend data for a parameter.

        Args:
            param_name: Parameter name
            minutes: Time window in minutes

        Returns:
            List of data points
        """
        if param_name not in self.trend_data:
            return []

        cutoff = time.time() - (minutes * 60)
        points = [
            {"time": p.timestamp, "value": p.value}
            for p in self.trend_data[param_name]
            if p.timestamp > cutoff
        ]
        return points

    def register_touch_callback(self,
                                 region_name: str,
                                 callback: Callable) -> None:
        """Register callback for touch region."""
        self._touch_callbacks[region_name] = callback

    def handle_touch(self, x: int, y: int) -> str | None:
        """
        Handle touch input.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Region name that was touched, if any
        """
        # Check alarm bar
        layout = self.layouts.get(self.current_mode)
        if layout:
            ax, ay, aw, ah = layout.alarm_bar_position
            if ax <= x <= ax + aw and ay <= y <= ay + ah:
                if "alarm_bar" in self._touch_callbacks:
                    self._touch_callbacks["alarm_bar"]()
                return "alarm_bar"

        return None

    def get_screen_data(self) -> dict:
        """Get complete screen data for rendering."""
        layout = self.layouts.get(self.current_mode)

        return {
            "mode": self.current_mode.name,
            "brightness": self.brightness,
            "layout": layout.name if layout else None,
            "parameters": {
                name: {
                    "name": p.name,
                    "value": p.value,
                    "unit": p.unit,
                    "status": p.status.name,
                    "color": p.color.to_hex(),
                    "trend": p.trend_direction,
                    "position": (
                        layout.parameter_positions.get(name)
                        if layout else None
                    )
                }
                for name, p in self.parameters.items()
            },
            "alarms": self.alarm_display.get_display_data(),
            "last_update": self.last_update
        }

    def get_status(self) -> dict:
        """Get display system status."""
        return {
            "is_active": self.is_active,
            "mode": self.current_mode.name,
            "brightness": self.brightness,
            "parameters_displayed": len(self.parameters),
            "trends_tracked": len(self.trend_data),
            "active_alarms": len(self.alarm_display.active_alarms),
            "update_rate_hz": 1000 / self.update_interval_ms
        }
