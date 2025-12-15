"""
Safety Monitoring and Alarm System

Patient safety is paramount during cardiopulmonary bypass. This module implements:
- Comprehensive alarm management
- Multiple safety parameter monitoring
- Alarm escalation protocols
- Event logging for post-operative review
- Emergency response coordination
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time


class AlarmLevel(Enum):
    """Alarm severity levels following IEC 60601-1-8 standard."""
    INFO = auto()       # Informational - no action required
    LOW = auto()        # Low priority - awareness needed
    MEDIUM = auto()     # Medium priority - attention required
    HIGH = auto()       # High priority - immediate attention
    CRITICAL = auto()   # Critical - immediate action required


class AlarmCategory(Enum):
    """Categories of alarms for filtering and prioritization."""
    FLOW = auto()           # Blood flow related
    PRESSURE = auto()       # Pressure related
    TEMPERATURE = auto()    # Temperature related
    BUBBLE = auto()         # Air detection related
    LEVEL = auto()          # Reservoir level related
    OXYGENATION = auto()    # Gas exchange related
    EQUIPMENT = auto()      # Equipment malfunction
    POWER = auto()          # Power related
    SYSTEM = auto()         # System errors


class AlarmState(Enum):
    """States an alarm can be in."""
    ACTIVE = auto()         # Alarm condition present
    ACKNOWLEDGED = auto()   # User acknowledged, condition still present
    SILENCED = auto()       # Temporarily silenced
    RESOLVED = auto()       # Condition resolved
    ESCALATED = auto()      # Escalated to higher level


@dataclass
class Alarm:
    """Represents a single alarm instance."""
    alarm_id: str
    level: AlarmLevel
    category: AlarmCategory
    message: str
    timestamp: float = field(default_factory=time.time)
    state: AlarmState = AlarmState.ACTIVE
    source: str = ""
    parameter_value: float | None = None
    threshold_value: float | None = None

    # Acknowledgment tracking
    acknowledged_by: str | None = None
    acknowledged_at: float | None = None

    # Silence tracking
    silence_duration_seconds: float = 0.0
    silence_start_time: float | None = None

    # Escalation tracking
    escalation_count: int = 0
    original_level: AlarmLevel | None = None

    def acknowledge(self, user_id: str) -> None:
        """Acknowledge the alarm."""
        self.state = AlarmState.ACKNOWLEDGED
        self.acknowledged_by = user_id
        self.acknowledged_at = time.time()

    def silence(self, duration_seconds: float = 120.0) -> None:
        """Temporarily silence the alarm."""
        if self.level != AlarmLevel.CRITICAL:  # Critical alarms cannot be silenced
            self.state = AlarmState.SILENCED
            self.silence_duration_seconds = duration_seconds
            self.silence_start_time = time.time()

    def is_silence_expired(self) -> bool:
        """Check if silence period has expired."""
        if self.silence_start_time is None:
            return True
        elapsed = time.time() - self.silence_start_time
        return elapsed >= self.silence_duration_seconds

    def resolve(self) -> None:
        """Mark alarm as resolved."""
        self.state = AlarmState.RESOLVED

    def escalate(self) -> None:
        """Escalate alarm to next level."""
        if self.original_level is None:
            self.original_level = self.level

        level_order = [AlarmLevel.INFO, AlarmLevel.LOW, AlarmLevel.MEDIUM,
                      AlarmLevel.HIGH, AlarmLevel.CRITICAL]
        current_index = level_order.index(self.level)

        if current_index < len(level_order) - 1:
            self.level = level_order[current_index + 1]
            self.state = AlarmState.ESCALATED
            self.escalation_count += 1

    def get_age_seconds(self) -> float:
        """Get alarm age in seconds."""
        return time.time() - self.timestamp

    def to_dict(self) -> dict:
        """Convert alarm to dictionary."""
        return {
            "alarm_id": self.alarm_id,
            "level": self.level.name,
            "category": self.category.name,
            "message": self.message,
            "timestamp": self.timestamp,
            "state": self.state.name,
            "source": self.source,
            "parameter_value": self.parameter_value,
            "threshold_value": self.threshold_value,
            "age_seconds": round(self.get_age_seconds(), 1)
        }


@dataclass
class SafetyLimit:
    """Defines a safety parameter limit."""
    name: str
    category: AlarmCategory
    low_warning: float | None = None
    low_critical: float | None = None
    high_warning: float | None = None
    high_critical: float | None = None
    unit: str = ""

    def check_value(self, value: float) -> tuple[AlarmLevel | None, str]:
        """
        Check value against limits.

        Returns:
            Tuple of (AlarmLevel, message) or (None, "") if within limits
        """
        if self.low_critical is not None and value < self.low_critical:
            return (AlarmLevel.CRITICAL,
                    f"{self.name} critically low: {value}{self.unit}")

        if self.high_critical is not None and value > self.high_critical:
            return (AlarmLevel.CRITICAL,
                    f"{self.name} critically high: {value}{self.unit}")

        if self.low_warning is not None and value < self.low_warning:
            return (AlarmLevel.HIGH,
                    f"{self.name} low: {value}{self.unit}")

        if self.high_warning is not None and value > self.high_warning:
            return (AlarmLevel.HIGH,
                    f"{self.name} high: {value}{self.unit}")

        return (None, "")


class SafetyMonitor:
    """
    Central safety monitoring and alarm management system.

    Coordinates all safety monitoring, alarm generation, and response.
    """

    def __init__(self):
        """Initialize safety monitor."""
        self.is_active: bool = False
        self.alarms: dict[str, Alarm] = {}
        self.alarm_history: list[Alarm] = []
        self.safety_limits: dict[str, SafetyLimit] = {}

        # Alarm ID counter
        self._alarm_counter: int = 0

        # Callbacks
        self._alarm_callbacks: list[Callable[[Alarm], None]] = []
        self._emergency_callback: Callable[[], None] | None = None

        # Configuration
        self.escalation_time_seconds: float = 60.0  # Time before escalation
        self.max_silence_duration_seconds: float = 120.0  # Max silence time
        self.enable_audio: bool = True

        # Initialize standard safety limits
        self._initialize_safety_limits()

    def _initialize_safety_limits(self) -> None:
        """Set up standard safety limits for bypass."""
        limits = [
            # Flow limits
            SafetyLimit(
                name="Blood Flow",
                category=AlarmCategory.FLOW,
                low_warning=1500,
                low_critical=1000,
                high_warning=6000,
                high_critical=7000,
                unit=" ml/min"
            ),
            # Pressure limits
            SafetyLimit(
                name="Arterial Line Pressure",
                category=AlarmCategory.PRESSURE,
                high_warning=300,
                high_critical=350,
                unit=" mmHg"
            ),
            SafetyLimit(
                name="Venous Line Pressure",
                category=AlarmCategory.PRESSURE,
                low_critical=-100,
                high_warning=20,
                high_critical=50,
                unit=" mmHg"
            ),
            SafetyLimit(
                name="Transmembrane Pressure",
                category=AlarmCategory.PRESSURE,
                high_warning=400,
                high_critical=500,
                unit=" mmHg"
            ),
            # Level limits
            SafetyLimit(
                name="Reservoir Level",
                category=AlarmCategory.LEVEL,
                low_warning=400,
                low_critical=200,
                unit=" ml"
            ),
            # Temperature limits
            SafetyLimit(
                name="Arterial Temperature",
                category=AlarmCategory.TEMPERATURE,
                low_warning=28,
                low_critical=15,
                high_warning=37.5,
                high_critical=38.5,
                unit="°C"
            ),
            SafetyLimit(
                name="Blood-Water Gradient",
                category=AlarmCategory.TEMPERATURE,
                high_warning=8,
                high_critical=10,
                unit="°C"
            ),
        ]

        for limit in limits:
            self.safety_limits[limit.name] = limit

    def register_alarm_callback(self, callback: Callable[[Alarm], None]) -> None:
        """Register callback for new alarms."""
        self._alarm_callbacks.append(callback)

    def register_emergency_callback(self, callback: Callable[[], None]) -> None:
        """Register callback for emergency stop."""
        self._emergency_callback = callback

    def _generate_alarm_id(self) -> str:
        """Generate unique alarm ID."""
        self._alarm_counter += 1
        return f"ALM-{int(time.time())}-{self._alarm_counter:04d}"

    def activate(self) -> None:
        """Activate safety monitoring."""
        self.is_active = True

    def deactivate(self) -> None:
        """Deactivate safety monitoring."""
        self.is_active = False

    def check_parameter(self, limit_name: str, value: float) -> Alarm | None:
        """
        Check a parameter against its safety limits.

        Args:
            limit_name: Name of the safety limit to check
            value: Current parameter value

        Returns:
            Alarm if limit exceeded, None otherwise
        """
        if not self.is_active:
            return None

        if limit_name not in self.safety_limits:
            return None

        limit = self.safety_limits[limit_name]
        level, message = limit.check_value(value)

        if level is None:
            # Check if existing alarm for this parameter should be resolved
            self._resolve_alarms_for_parameter(limit_name)
            return None

        # Check if alarm already exists
        existing = self._find_active_alarm_for_parameter(limit_name)
        if existing:
            # Update existing alarm if level changed
            if existing.level != level:
                existing.level = level
                existing.message = message
                existing.parameter_value = value
            return existing

        # Create new alarm
        alarm = self._create_alarm(
            level=level,
            category=limit.category,
            message=message,
            source=limit_name,
            parameter_value=value,
            threshold_value=limit.high_critical or limit.low_critical
        )

        return alarm

    def _create_alarm(self,
                     level: AlarmLevel,
                     category: AlarmCategory,
                     message: str,
                     source: str = "",
                     parameter_value: float | None = None,
                     threshold_value: float | None = None) -> Alarm:
        """Create and register a new alarm."""
        alarm = Alarm(
            alarm_id=self._generate_alarm_id(),
            level=level,
            category=category,
            message=message,
            source=source,
            parameter_value=parameter_value,
            threshold_value=threshold_value
        )

        self.alarms[alarm.alarm_id] = alarm

        # Trigger callbacks
        for callback in self._alarm_callbacks:
            callback(alarm)

        # Trigger emergency if critical
        if level == AlarmLevel.CRITICAL and self._emergency_callback:
            self._emergency_callback()

        return alarm

    def create_alarm(self,
                    level: AlarmLevel,
                    category: AlarmCategory,
                    message: str,
                    source: str = "") -> Alarm:
        """Public method to create an alarm."""
        return self._create_alarm(level, category, message, source)

    def _find_active_alarm_for_parameter(self, source: str) -> Alarm | None:
        """Find an active alarm for a specific parameter."""
        for alarm in self.alarms.values():
            if (alarm.source == source and
                alarm.state in (AlarmState.ACTIVE, AlarmState.ACKNOWLEDGED,
                               AlarmState.SILENCED, AlarmState.ESCALATED)):
                return alarm
        return None

    def _resolve_alarms_for_parameter(self, source: str) -> None:
        """Resolve all alarms for a parameter."""
        for alarm in self.alarms.values():
            if alarm.source == source and alarm.state != AlarmState.RESOLVED:
                alarm.resolve()
                self.alarm_history.append(alarm)

    def acknowledge_alarm(self, alarm_id: str, user_id: str) -> bool:
        """
        Acknowledge an alarm.

        Args:
            alarm_id: ID of alarm to acknowledge
            user_id: ID of user acknowledging

        Returns:
            True if acknowledged successfully
        """
        if alarm_id in self.alarms:
            self.alarms[alarm_id].acknowledge(user_id)
            return True
        return False

    def silence_alarm(self, alarm_id: str, duration_seconds: float = 120.0) -> bool:
        """
        Silence an alarm temporarily.

        Args:
            alarm_id: ID of alarm to silence
            duration_seconds: Duration to silence

        Returns:
            True if silenced successfully
        """
        if alarm_id not in self.alarms:
            return False

        alarm = self.alarms[alarm_id]

        # Cannot silence critical alarms
        if alarm.level == AlarmLevel.CRITICAL:
            return False

        # Enforce max silence duration
        duration = min(duration_seconds, self.max_silence_duration_seconds)
        alarm.silence(duration)
        return True

    def update_escalations(self) -> list[Alarm]:
        """
        Check and process alarm escalations.

        Returns:
            List of escalated alarms
        """
        escalated = []

        for alarm in self.alarms.values():
            if alarm.state == AlarmState.ACTIVE:
                if alarm.get_age_seconds() >= self.escalation_time_seconds:
                    alarm.escalate()
                    escalated.append(alarm)

            elif alarm.state == AlarmState.SILENCED:
                if alarm.is_silence_expired():
                    alarm.state = AlarmState.ACTIVE

        return escalated

    def get_active_alarms(self) -> list[Alarm]:
        """Get all active (non-resolved) alarms."""
        return [
            alarm for alarm in self.alarms.values()
            if alarm.state != AlarmState.RESOLVED
        ]

    def get_critical_alarms(self) -> list[Alarm]:
        """Get all critical alarms."""
        return [
            alarm for alarm in self.alarms.values()
            if alarm.level == AlarmLevel.CRITICAL and alarm.state != AlarmState.RESOLVED
        ]

    def get_alarms_by_category(self, category: AlarmCategory) -> list[Alarm]:
        """Get alarms filtered by category."""
        return [
            alarm for alarm in self.alarms.values()
            if alarm.category == category and alarm.state != AlarmState.RESOLVED
        ]

    def clear_resolved_alarms(self) -> int:
        """
        Move resolved alarms to history and clear from active.

        Returns:
            Number of alarms cleared
        """
        resolved_ids = [
            alarm_id for alarm_id, alarm in self.alarms.items()
            if alarm.state == AlarmState.RESOLVED
        ]

        for alarm_id in resolved_ids:
            alarm = self.alarms.pop(alarm_id)
            self.alarm_history.append(alarm)

        return len(resolved_ids)

    def get_alarm_summary(self) -> dict:
        """Get summary of current alarm state."""
        active_alarms = self.get_active_alarms()

        by_level = {level.name: 0 for level in AlarmLevel}
        by_category = {cat.name: 0 for cat in AlarmCategory}
        by_state = {state.name: 0 for state in AlarmState}

        for alarm in active_alarms:
            by_level[alarm.level.name] += 1
            by_category[alarm.category.name] += 1
            by_state[alarm.state.name] += 1

        return {
            "total_active": len(active_alarms),
            "critical_count": by_level.get(AlarmLevel.CRITICAL.name, 0),
            "high_count": by_level.get(AlarmLevel.HIGH.name, 0),
            "by_level": by_level,
            "by_category": by_category,
            "by_state": by_state,
            "history_count": len(self.alarm_history)
        }

    def get_status(self) -> dict:
        """Get comprehensive safety monitor status."""
        summary = self.get_alarm_summary()
        active_alarms = self.get_active_alarms()

        return {
            "is_active": self.is_active,
            "summary": summary,
            "active_alarms": [alarm.to_dict() for alarm in active_alarms],
            "critical_alarms": [
                alarm.to_dict() for alarm in self.get_critical_alarms()
            ],
            "enable_audio": self.enable_audio
        }


class SafetyInterlock:
    """
    Safety interlock system for preventing unsafe operations.

    Provides hardware-level safety checks that must pass before
    certain operations can proceed.
    """

    def __init__(self, safety_monitor: SafetyMonitor):
        """Initialize safety interlock."""
        self.safety_monitor = safety_monitor
        self.interlocks_enabled: bool = True

        # Interlock conditions
        self.conditions: dict[str, Callable[[], bool]] = {}
        self._initialize_interlocks()

    def _initialize_interlocks(self) -> None:
        """Set up standard safety interlocks."""
        # These would typically check hardware signals
        self.conditions["no_critical_alarms"] = (
            lambda: len(self.safety_monitor.get_critical_alarms()) == 0
        )

    def add_interlock(self, name: str, condition: Callable[[], bool]) -> None:
        """Add a custom interlock condition."""
        self.conditions[name] = condition

    def check_interlock(self, name: str) -> bool:
        """Check a specific interlock."""
        if not self.interlocks_enabled:
            return True

        if name in self.conditions:
            return self.conditions[name]()
        return True

    def check_all_interlocks(self) -> tuple[bool, list[str]]:
        """
        Check all interlocks.

        Returns:
            Tuple of (all_passed, list of failed interlock names)
        """
        if not self.interlocks_enabled:
            return (True, [])

        failed = []
        for name, condition in self.conditions.items():
            if not condition():
                failed.append(name)

        return (len(failed) == 0, failed)

    def can_start_bypass(self) -> tuple[bool, list[str]]:
        """Check if bypass can be safely started."""
        return self.check_all_interlocks()

    def can_increase_flow(self) -> bool:
        """Check if flow can be safely increased."""
        return self.check_interlock("no_critical_alarms")

    def override_interlocks(self, user_id: str, reason: str) -> None:
        """
        Override interlocks (for emergency use only).

        This would typically require special authorization and be logged.
        """
        self.interlocks_enabled = False
        # Log the override
        self.safety_monitor.create_alarm(
            level=AlarmLevel.HIGH,
            category=AlarmCategory.SYSTEM,
            message=f"Safety interlocks overridden by {user_id}: {reason}",
            source="interlock_system"
        )

    def restore_interlocks(self) -> None:
        """Re-enable interlocks after override."""
        self.interlocks_enabled = True
