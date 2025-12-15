"""
Bubble Detection and Removal System

Air embolism is one of the most serious complications during cardiopulmonary
bypass. This module implements:
- Ultrasonic bubble detection at multiple circuit points
- Automatic bubble removal activation
- Air accumulation monitoring
- Emergency response protocols
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time


class BubbleSize(Enum):
    """Classification of bubble sizes."""
    MICRO = auto()      # < 40 microns - usually filtered
    SMALL = auto()      # 40-200 microns
    MEDIUM = auto()     # 200-500 microns
    LARGE = auto()      # > 500 microns - dangerous
    MASSIVE = auto()    # Gross air - critical emergency


class DetectorLocation(Enum):
    """Locations for bubble detectors in the circuit."""
    VENOUS_LINE = auto()        # Venous return line
    PRE_OXYGENATOR = auto()     # Before oxygenator
    POST_OXYGENATOR = auto()    # After oxygenator
    ARTERIAL_LINE = auto()      # Final check before patient
    CARDIOPLEGIA_LINE = auto()  # Cardioplegia delivery


class BubbleAlertLevel(Enum):
    """Alert levels for bubble detection."""
    NONE = auto()
    INFO = auto()       # Micro bubbles detected - monitoring
    WARNING = auto()    # Small bubbles - removal active
    CRITICAL = auto()   # Medium/large bubbles - consider stopping
    EMERGENCY = auto()  # Massive air - emergency stop required


@dataclass
class BubbleEvent:
    """Record of a bubble detection event."""
    timestamp: float
    location: DetectorLocation
    size: BubbleSize
    estimated_volume_ul: float  # Microliters
    alert_level: BubbleAlertLevel
    was_removed: bool = False


@dataclass
class UltrasonicSensor:
    """
    Ultrasonic bubble detector sensor.

    Uses ultrasound transmission to detect air bubbles in the blood line.
    Air has different acoustic impedance than blood, causing signal attenuation.
    """
    location: DetectorLocation
    sensitivity_threshold: float = 0.95  # Signal threshold for detection
    is_active: bool = True
    last_reading: float = 1.0  # 1.0 = no bubbles, 0.0 = complete air
    calibration_factor: float = 1.0

    # Detection thresholds (signal attenuation levels)
    micro_bubble_threshold: float = 0.98
    small_bubble_threshold: float = 0.90
    medium_bubble_threshold: float = 0.70
    large_bubble_threshold: float = 0.40
    massive_air_threshold: float = 0.10

    def update_reading(self, signal_level: float) -> BubbleSize | None:
        """
        Update sensor reading and classify bubble size.

        Args:
            signal_level: Normalized signal level (0.0-1.0)

        Returns:
            BubbleSize if bubble detected, None otherwise
        """
        self.last_reading = signal_level * self.calibration_factor

        if self.last_reading < self.massive_air_threshold:
            return BubbleSize.MASSIVE
        elif self.last_reading < self.large_bubble_threshold:
            return BubbleSize.LARGE
        elif self.last_reading < self.medium_bubble_threshold:
            return BubbleSize.MEDIUM
        elif self.last_reading < self.small_bubble_threshold:
            return BubbleSize.SMALL
        elif self.last_reading < self.micro_bubble_threshold:
            return BubbleSize.MICRO
        return None

    def estimate_volume(self, bubble_size: BubbleSize) -> float:
        """
        Estimate bubble volume in microliters based on size classification.

        Returns:
            Estimated volume in microliters
        """
        volume_estimates = {
            BubbleSize.MICRO: 0.5,
            BubbleSize.SMALL: 5.0,
            BubbleSize.MEDIUM: 50.0,
            BubbleSize.LARGE: 200.0,
            BubbleSize.MASSIVE: 1000.0
        }
        return volume_estimates.get(bubble_size, 0.0)

    def calibrate(self, blood_baseline: float, air_baseline: float) -> None:
        """
        Calibrate sensor with known blood and air readings.

        Args:
            blood_baseline: Signal level with blood (should be ~1.0)
            air_baseline: Signal level with air (should be ~0.0)
        """
        if blood_baseline > air_baseline:
            self.calibration_factor = 1.0 / blood_baseline


@dataclass
class BubbleTrap:
    """
    Bubble trap/removal device.

    Physical device that uses buoyancy to separate air from blood.
    """
    name: str
    is_active: bool = True
    trap_volume_ml: float = 50.0  # Volume capacity
    accumulated_air_ml: float = 0.0
    purge_threshold_ml: float = 30.0  # Threshold for purge warning
    last_purge_time: float = field(default_factory=time.time)

    def accumulate_air(self, volume_ul: float) -> None:
        """Add detected air volume to trap accumulator."""
        self.accumulated_air_ml += volume_ul / 1000.0  # Convert ul to ml

    def needs_purge(self) -> bool:
        """Check if trap needs to be purged."""
        return self.accumulated_air_ml >= self.purge_threshold_ml

    def purge(self) -> float:
        """
        Purge accumulated air from trap.

        Returns:
            Volume of air purged in ml
        """
        purged_volume = self.accumulated_air_ml
        self.accumulated_air_ml = 0.0
        self.last_purge_time = time.time()
        return purged_volume

    def get_fill_percentage(self) -> float:
        """Get trap fill level as percentage."""
        return (self.accumulated_air_ml / self.trap_volume_ml) * 100


class BubbleDetector:
    """
    Multi-point bubble detection system.

    Monitors multiple locations in the circuit for air bubbles
    and classifies severity of detections.
    """

    def __init__(self):
        """Initialize bubble detection system."""
        self.sensors: dict[DetectorLocation, UltrasonicSensor] = {}
        self.event_history: list[BubbleEvent] = []
        self.is_monitoring: bool = False
        self.total_detected_volume_ul: float = 0.0

        # Callbacks
        self._alert_callbacks: list[Callable[[BubbleAlertLevel, str], None]] = []

        # Initialize sensors at standard locations
        self._initialize_sensors()

    def _initialize_sensors(self) -> None:
        """Set up sensors at standard monitoring points."""
        for location in DetectorLocation:
            self.sensors[location] = UltrasonicSensor(location=location)

    def register_alert_callback(
        self, callback: Callable[[BubbleAlertLevel, str], None]
    ) -> None:
        """Register callback for bubble alerts."""
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, level: BubbleAlertLevel, message: str) -> None:
        """Trigger all registered alert callbacks."""
        for callback in self._alert_callbacks:
            callback(level, message)

    def start_monitoring(self) -> None:
        """Start bubble monitoring."""
        self.is_monitoring = True
        for sensor in self.sensors.values():
            sensor.is_active = True

    def stop_monitoring(self) -> None:
        """Stop bubble monitoring."""
        self.is_monitoring = False

    def update_sensor(
        self, location: DetectorLocation, signal_level: float
    ) -> BubbleEvent | None:
        """
        Update a specific sensor with new reading.

        Args:
            location: Sensor location
            signal_level: Current signal level (0.0-1.0)

        Returns:
            BubbleEvent if bubble detected, None otherwise
        """
        if not self.is_monitoring or location not in self.sensors:
            return None

        sensor = self.sensors[location]
        bubble_size = sensor.update_reading(signal_level)

        if bubble_size is None:
            return None

        # Create bubble event
        volume = sensor.estimate_volume(bubble_size)
        alert_level = self._classify_alert_level(bubble_size, location)

        event = BubbleEvent(
            timestamp=time.time(),
            location=location,
            size=bubble_size,
            estimated_volume_ul=volume,
            alert_level=alert_level
        )

        # Record event
        self.event_history.append(event)
        self.total_detected_volume_ul += volume

        # Trigger appropriate alert
        self._handle_detection(event)

        return event

    def _classify_alert_level(
        self, size: BubbleSize, location: DetectorLocation
    ) -> BubbleAlertLevel:
        """
        Classify alert level based on bubble size and location.

        Arterial line detections are more critical as they're closest to patient.
        """
        # Base level from size
        size_levels = {
            BubbleSize.MICRO: BubbleAlertLevel.INFO,
            BubbleSize.SMALL: BubbleAlertLevel.WARNING,
            BubbleSize.MEDIUM: BubbleAlertLevel.CRITICAL,
            BubbleSize.LARGE: BubbleAlertLevel.EMERGENCY,
            BubbleSize.MASSIVE: BubbleAlertLevel.EMERGENCY
        }
        base_level = size_levels.get(size, BubbleAlertLevel.INFO)

        # Escalate if in arterial line (closest to patient)
        if location == DetectorLocation.ARTERIAL_LINE:
            if base_level == BubbleAlertLevel.INFO:
                return BubbleAlertLevel.WARNING
            elif base_level == BubbleAlertLevel.WARNING:
                return BubbleAlertLevel.CRITICAL

        return base_level

    def _handle_detection(self, event: BubbleEvent) -> None:
        """Handle bubble detection event with appropriate response."""
        location_name = event.location.name.replace("_", " ").title()
        size_name = event.size.name.lower()

        if event.alert_level == BubbleAlertLevel.EMERGENCY:
            message = (
                f"EMERGENCY: {size_name} air detected in {location_name}! "
                f"Volume: {event.estimated_volume_ul:.1f}ul"
            )
            self._trigger_alert(BubbleAlertLevel.EMERGENCY, message)

        elif event.alert_level == BubbleAlertLevel.CRITICAL:
            message = (
                f"CRITICAL: {size_name} bubble in {location_name}. "
                f"Volume: {event.estimated_volume_ul:.1f}ul"
            )
            self._trigger_alert(BubbleAlertLevel.CRITICAL, message)

        elif event.alert_level == BubbleAlertLevel.WARNING:
            message = f"Warning: {size_name} bubble detected in {location_name}"
            self._trigger_alert(BubbleAlertLevel.WARNING, message)

        elif event.alert_level == BubbleAlertLevel.INFO:
            message = f"Info: Micro-bubbles detected in {location_name}"
            self._trigger_alert(BubbleAlertLevel.INFO, message)

    def get_recent_events(self, seconds: float = 60.0) -> list[BubbleEvent]:
        """Get bubble events from the last N seconds."""
        cutoff = time.time() - seconds
        return [e for e in self.event_history if e.timestamp > cutoff]

    def get_arterial_line_status(self) -> dict:
        """Get status of the critical arterial line sensor."""
        sensor = self.sensors.get(DetectorLocation.ARTERIAL_LINE)
        if not sensor:
            return {"error": "Sensor not found"}

        recent_events = [
            e for e in self.get_recent_events()
            if e.location == DetectorLocation.ARTERIAL_LINE
        ]

        return {
            "is_active": sensor.is_active,
            "last_reading": sensor.last_reading,
            "is_clear": sensor.last_reading >= sensor.micro_bubble_threshold,
            "recent_detections": len(recent_events)
        }

    def get_status(self) -> dict:
        """Get comprehensive bubble detection status."""
        return {
            "is_monitoring": self.is_monitoring,
            "total_detected_volume_ul": round(self.total_detected_volume_ul, 1),
            "total_events": len(self.event_history),
            "sensors": {
                loc.name: {
                    "active": sensor.is_active,
                    "last_reading": round(sensor.last_reading, 3),
                    "is_clear": sensor.last_reading >= sensor.micro_bubble_threshold
                }
                for loc, sensor in self.sensors.items()
            },
            "arterial_line": self.get_arterial_line_status()
        }


class BubbleRemovalSystem:
    """
    Integrated bubble removal system.

    Combines detection with active removal mechanisms including:
    - Venous reservoir de-airing
    - Bubble traps at key points
    - Automatic line clamping
    - Purge line management
    """

    def __init__(self):
        """Initialize bubble removal system."""
        self.detector = BubbleDetector()
        self.is_active: bool = False

        # Bubble traps
        self.traps: dict[str, BubbleTrap] = {
            "venous": BubbleTrap(name="venous_trap"),
            "arterial": BubbleTrap(name="arterial_trap", purge_threshold_ml=20.0),
            "cardioplegia": BubbleTrap(name="cardioplegia_trap", trap_volume_ml=30.0)
        }

        # Line clamp states
        self.line_clamps: dict[str, bool] = {
            "arterial": False,  # False = open, True = clamped
            "venous": False,
            "cardioplegia": False
        }

        # Auto-clamp settings
        self.auto_clamp_enabled: bool = True
        self.auto_clamp_threshold: BubbleAlertLevel = BubbleAlertLevel.CRITICAL

        # Callbacks
        self._emergency_callbacks: list[Callable[[], None]] = []

        # Register for bubble alerts
        self.detector.register_alert_callback(self._handle_bubble_alert)

    def register_emergency_callback(self, callback: Callable[[], None]) -> None:
        """Register callback for emergency stop trigger."""
        self._emergency_callbacks.append(callback)

    def _trigger_emergency(self) -> None:
        """Trigger emergency callbacks."""
        for callback in self._emergency_callbacks:
            callback()

    def activate(self) -> None:
        """Activate bubble removal system."""
        self.is_active = True
        self.detector.start_monitoring()

    def deactivate(self) -> None:
        """Deactivate bubble removal system."""
        self.is_active = False
        self.detector.stop_monitoring()

    def _handle_bubble_alert(
        self, level: BubbleAlertLevel, message: str
    ) -> None:
        """Handle bubble detection alerts from detector."""
        if not self.is_active:
            return

        # Auto-clamp on critical arterial line detection
        if (self.auto_clamp_enabled and
            level.value >= self.auto_clamp_threshold.value):
            # Check if this is arterial line
            recent = self.detector.get_recent_events(seconds=1.0)
            arterial_events = [
                e for e in recent
                if e.location == DetectorLocation.ARTERIAL_LINE
            ]
            if arterial_events:
                self.clamp_line("arterial")

        # Emergency stop on massive air
        if level == BubbleAlertLevel.EMERGENCY:
            self._trigger_emergency()

    def update_sensor_reading(
        self, location: DetectorLocation, signal_level: float
    ) -> BubbleEvent | None:
        """
        Update bubble sensor and handle any detected bubbles.

        Args:
            location: Sensor location
            signal_level: Current signal level

        Returns:
            BubbleEvent if bubble detected
        """
        event = self.detector.update_sensor(location, signal_level)

        if event and event.alert_level != BubbleAlertLevel.NONE:
            # Route air to appropriate trap
            self._route_to_trap(event)

        return event

    def _route_to_trap(self, event: BubbleEvent) -> None:
        """Route detected air to appropriate trap."""
        trap_mapping = {
            DetectorLocation.VENOUS_LINE: "venous",
            DetectorLocation.PRE_OXYGENATOR: "venous",
            DetectorLocation.POST_OXYGENATOR: "arterial",
            DetectorLocation.ARTERIAL_LINE: "arterial",
            DetectorLocation.CARDIOPLEGIA_LINE: "cardioplegia"
        }

        trap_name = trap_mapping.get(event.location)
        if trap_name and trap_name in self.traps:
            self.traps[trap_name].accumulate_air(event.estimated_volume_ul)
            event.was_removed = True

    def clamp_line(self, line: str) -> bool:
        """
        Clamp a specific line.

        Args:
            line: Line to clamp (arterial, venous, cardioplegia)

        Returns:
            True if clamp activated
        """
        if line in self.line_clamps:
            self.line_clamps[line] = True
            return True
        return False

    def unclamp_line(self, line: str) -> bool:
        """
        Release a line clamp.

        Args:
            line: Line to unclamp

        Returns:
            True if clamp released
        """
        if line in self.line_clamps:
            # Verify line is safe before unclamping
            self.line_clamps[line] = False
            return True
        return False

    def purge_trap(self, trap_name: str) -> float:
        """
        Purge a bubble trap.

        Args:
            trap_name: Name of trap to purge

        Returns:
            Volume purged in ml
        """
        if trap_name in self.traps:
            return self.traps[trap_name].purge()
        return 0.0

    def get_traps_needing_purge(self) -> list[str]:
        """Get list of traps that need purging."""
        return [name for name, trap in self.traps.items() if trap.needs_purge()]

    def perform_de_airing_sequence(self) -> dict:
        """
        Perform systematic de-airing of the circuit.

        Returns:
            Summary of de-airing results
        """
        results = {
            "traps_purged": [],
            "total_air_removed_ml": 0.0,
            "lines_status": {}
        }

        # Purge all traps
        for name, trap in self.traps.items():
            if trap.accumulated_air_ml > 0:
                volume = trap.purge()
                results["traps_purged"].append(name)
                results["total_air_removed_ml"] += volume

        # Check line status
        for line, clamped in self.line_clamps.items():
            results["lines_status"][line] = "clamped" if clamped else "open"

        return results

    def get_status(self) -> dict:
        """Get comprehensive bubble removal system status."""
        return {
            "is_active": self.is_active,
            "auto_clamp_enabled": self.auto_clamp_enabled,
            "detection": self.detector.get_status(),
            "traps": {
                name: {
                    "accumulated_air_ml": round(trap.accumulated_air_ml, 2),
                    "fill_percent": round(trap.get_fill_percentage(), 1),
                    "needs_purge": trap.needs_purge()
                }
                for name, trap in self.traps.items()
            },
            "line_clamps": self.line_clamps.copy(),
            "traps_needing_purge": self.get_traps_needing_purge()
        }
