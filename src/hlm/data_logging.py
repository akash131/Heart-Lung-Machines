"""
Data Logging and Trending System

Comprehensive data recording is essential for:
- Real-time monitoring and display
- Post-operative analysis
- Quality improvement
- Regulatory compliance
- Legal documentation

This module implements:
- High-frequency parameter logging
- Event recording
- Trend analysis
- Report generation
- Data export capabilities
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable
import time
import json
import csv
from io import StringIO
from datetime import datetime


class DataCategory(Enum):
    """Categories of logged data."""
    FLOW = auto()
    PRESSURE = auto()
    TEMPERATURE = auto()
    BLOOD_GAS = auto()
    COAGULATION = auto()
    SAFETY = auto()
    EVENT = auto()
    MEDICATION = auto()
    EQUIPMENT = auto()


class EventSeverity(Enum):
    """Severity levels for logged events."""
    INFO = auto()
    WARNING = auto()
    ALARM = auto()
    CRITICAL = auto()
    ACTION = auto()


class TrendDirection(Enum):
    """Direction of parameter trend."""
    INCREASING = auto()
    DECREASING = auto()
    STABLE = auto()
    UNKNOWN = auto()


@dataclass
class DataPoint:
    """A single data point with metadata."""
    timestamp: float
    parameter_name: str
    value: float
    unit: str
    category: DataCategory
    source: str = ""
    is_valid: bool = True
    quality_flag: str = ""


@dataclass
class EventRecord:
    """Record of an event during the procedure."""
    timestamp: float
    event_type: str
    severity: EventSeverity
    description: str
    category: DataCategory
    source: str = ""
    user_id: str = ""
    data: dict = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_by: str = ""
    acknowledged_at: float | None = None


@dataclass
class TrendAnalysis:
    """Analysis of a parameter trend."""
    parameter_name: str
    direction: TrendDirection
    rate_per_minute: float
    current_value: float
    min_value: float
    max_value: float
    mean_value: float
    std_deviation: float
    analysis_period_minutes: float
    data_points: int


@dataclass
class ProcedurePhase:
    """A phase within the procedure."""
    name: str
    start_time: float
    end_time: float | None = None
    notes: str = ""


class DataBuffer:
    """
    Circular buffer for high-frequency data storage.

    Efficient storage for time-series data with automatic cleanup.
    """

    def __init__(self, max_size: int = 10000, retention_hours: float = 24.0):
        self.max_size = max_size
        self.retention_hours = retention_hours
        self.data: list[DataPoint] = []

    def add(self, point: DataPoint) -> None:
        """Add a data point to the buffer."""
        self.data.append(point)

        # Trim if over max size
        if len(self.data) > self.max_size:
            self.data = self.data[-self.max_size:]

    def get_range(self, start_time: float, end_time: float) -> list[DataPoint]:
        """Get data points within a time range."""
        return [p for p in self.data if start_time <= p.timestamp <= end_time]

    def get_recent(self, seconds: float) -> list[DataPoint]:
        """Get data points from the last N seconds."""
        cutoff = time.time() - seconds
        return [p for p in self.data if p.timestamp >= cutoff]

    def get_by_parameter(self, parameter_name: str) -> list[DataPoint]:
        """Get all data points for a specific parameter."""
        return [p for p in self.data if p.parameter_name == parameter_name]

    def cleanup_old_data(self) -> int:
        """Remove data older than retention period."""
        cutoff = time.time() - (self.retention_hours * 3600)
        original_count = len(self.data)
        self.data = [p for p in self.data if p.timestamp >= cutoff]
        return original_count - len(self.data)

    def get_statistics(self, parameter_name: str,
                       seconds: float = 300) -> dict | None:
        """Calculate statistics for a parameter over a time period."""
        points = [p for p in self.get_recent(seconds)
                  if p.parameter_name == parameter_name and p.is_valid]

        if not points:
            return None

        values = [p.value for p in points]
        n = len(values)

        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n if n > 1 else 0
        std_dev = variance ** 0.5

        return {
            "count": n,
            "min": min(values),
            "max": max(values),
            "mean": mean,
            "std_dev": std_dev,
            "first_value": values[0],
            "last_value": values[-1],
            "trend": "increasing" if values[-1] > values[0] else "decreasing" if values[-1] < values[0] else "stable"
        }


class DataLogger:
    """
    Central data logging system for the heart-lung machine.

    Coordinates all data recording, storage, and retrieval.
    """

    def __init__(self):
        """Initialize data logger."""
        self.is_recording: bool = False
        self.procedure_id: str = ""
        self.procedure_start_time: float | None = None
        self.procedure_end_time: float | None = None

        # Data storage
        self.data_buffer = DataBuffer()
        self.events: list[EventRecord] = []
        self.phases: list[ProcedurePhase] = []

        # Patient information
        self.patient_id: str = ""
        self.patient_name: str = ""
        self.mrn: str = ""

        # Procedure information
        self.procedure_type: str = ""
        self.surgeon: str = ""
        self.perfusionist: str = ""
        self.anesthesiologist: str = ""

        # Logging intervals
        self.high_frequency_interval_sec: float = 1.0
        self.standard_interval_sec: float = 5.0
        self.low_frequency_interval_sec: float = 60.0

        # Parameter definitions
        self.parameter_definitions: dict[str, dict] = {}
        self._initialize_parameter_definitions()

        # Callbacks
        self._event_callbacks: list[Callable[[EventRecord], None]] = []

    def _initialize_parameter_definitions(self) -> None:
        """Define standard parameters with metadata."""
        self.parameter_definitions = {
            "arterial_flow": {
                "unit": "ml/min",
                "category": DataCategory.FLOW,
                "min_normal": 2000,
                "max_normal": 6000,
                "critical_low": 1000,
                "critical_high": 7000
            },
            "arterial_pressure": {
                "unit": "mmHg",
                "category": DataCategory.PRESSURE,
                "min_normal": 150,
                "max_normal": 300,
                "critical_low": 100,
                "critical_high": 350
            },
            "venous_pressure": {
                "unit": "mmHg",
                "category": DataCategory.PRESSURE,
                "min_normal": -30,
                "max_normal": 20,
                "critical_low": -100,
                "critical_high": 50
            },
            "arterial_temperature": {
                "unit": "°C",
                "category": DataCategory.TEMPERATURE,
                "min_normal": 28,
                "max_normal": 37,
                "critical_low": 15,
                "critical_high": 39
            },
            "venous_saturation": {
                "unit": "%",
                "category": DataCategory.BLOOD_GAS,
                "min_normal": 65,
                "max_normal": 85,
                "critical_low": 55,
                "critical_high": 95
            },
            "reservoir_level": {
                "unit": "ml",
                "category": DataCategory.EQUIPMENT,
                "min_normal": 500,
                "max_normal": 3000,
                "critical_low": 200,
                "critical_high": 3500
            },
            "pump_rpm": {
                "unit": "rpm",
                "category": DataCategory.EQUIPMENT,
                "min_normal": 0,
                "max_normal": 200,
                "critical_low": 0,
                "critical_high": 250
            },
            "act": {
                "unit": "seconds",
                "category": DataCategory.COAGULATION,
                "min_normal": 480,
                "max_normal": 999,
                "critical_low": 400,
                "critical_high": None
            },
            "hemoglobin": {
                "unit": "g/dL",
                "category": DataCategory.BLOOD_GAS,
                "min_normal": 7,
                "max_normal": 12,
                "critical_low": 6,
                "critical_high": 15
            },
            "lactate": {
                "unit": "mmol/L",
                "category": DataCategory.BLOOD_GAS,
                "min_normal": 0,
                "max_normal": 2,
                "critical_low": None,
                "critical_high": 4
            }
        }

    def register_event_callback(self, callback: Callable[[EventRecord], None]) -> None:
        """Register callback for new events."""
        self._event_callbacks.append(callback)

    def start_recording(self, procedure_id: str | None = None) -> str:
        """
        Start recording a new procedure.

        Args:
            procedure_id: Optional procedure ID (auto-generated if not provided)

        Returns:
            Procedure ID
        """
        if procedure_id is None:
            procedure_id = f"PROC-{int(time.time())}"

        self.procedure_id = procedure_id
        self.procedure_start_time = time.time()
        self.is_recording = True

        self.log_event(
            event_type="PROCEDURE_START",
            severity=EventSeverity.INFO,
            description="Procedure recording started",
            category=DataCategory.EVENT
        )

        return procedure_id

    def stop_recording(self) -> None:
        """Stop recording the current procedure."""
        self.procedure_end_time = time.time()
        self.is_recording = False

        self.log_event(
            event_type="PROCEDURE_END",
            severity=EventSeverity.INFO,
            description="Procedure recording stopped",
            category=DataCategory.EVENT
        )

    def log_data(self,
                 parameter_name: str,
                 value: float,
                 source: str = "",
                 is_valid: bool = True) -> DataPoint | None:
        """
        Log a data point.

        Args:
            parameter_name: Name of the parameter
            value: Parameter value
            source: Data source identifier
            is_valid: Whether the data is valid

        Returns:
            Logged data point or None if not recording
        """
        if not self.is_recording:
            return None

        # Get parameter metadata
        param_def = self.parameter_definitions.get(parameter_name, {})
        unit = param_def.get("unit", "")
        category = param_def.get("category", DataCategory.EQUIPMENT)

        # Check for quality flags
        quality_flag = ""
        if param_def:
            critical_low = param_def.get("critical_low")
            critical_high = param_def.get("critical_high")
            if critical_low is not None and value < critical_low:
                quality_flag = "CRITICAL_LOW"
            elif critical_high is not None and value > critical_high:
                quality_flag = "CRITICAL_HIGH"

        point = DataPoint(
            timestamp=time.time(),
            parameter_name=parameter_name,
            value=value,
            unit=unit,
            category=category,
            source=source,
            is_valid=is_valid,
            quality_flag=quality_flag
        )

        self.data_buffer.add(point)
        return point

    def log_event(self,
                  event_type: str,
                  severity: EventSeverity,
                  description: str,
                  category: DataCategory,
                  source: str = "",
                  user_id: str = "",
                  data: dict | None = None) -> EventRecord:
        """
        Log an event.

        Args:
            event_type: Type of event
            severity: Event severity
            description: Event description
            category: Event category
            source: Event source
            user_id: User who triggered event
            data: Additional event data

        Returns:
            Logged event record
        """
        event = EventRecord(
            timestamp=time.time(),
            event_type=event_type,
            severity=severity,
            description=description,
            category=category,
            source=source,
            user_id=user_id,
            data=data or {}
        )

        self.events.append(event)

        # Notify callbacks
        for callback in self._event_callbacks:
            callback(event)

        return event

    def start_phase(self, phase_name: str, notes: str = "") -> ProcedurePhase:
        """
        Start a new procedure phase.

        Args:
            phase_name: Name of the phase
            notes: Additional notes

        Returns:
            Phase record
        """
        # End current phase if any
        if self.phases and self.phases[-1].end_time is None:
            self.phases[-1].end_time = time.time()

        phase = ProcedurePhase(
            name=phase_name,
            start_time=time.time(),
            notes=notes
        )
        self.phases.append(phase)

        self.log_event(
            event_type="PHASE_START",
            severity=EventSeverity.INFO,
            description=f"Started phase: {phase_name}",
            category=DataCategory.EVENT,
            data={"phase_name": phase_name, "notes": notes}
        )

        return phase

    def end_phase(self, notes: str = "") -> None:
        """End the current phase."""
        if self.phases and self.phases[-1].end_time is None:
            self.phases[-1].end_time = time.time()
            if notes:
                self.phases[-1].notes += f" {notes}"

            self.log_event(
                event_type="PHASE_END",
                severity=EventSeverity.INFO,
                description=f"Ended phase: {self.phases[-1].name}",
                category=DataCategory.EVENT
            )

    def analyze_trend(self,
                      parameter_name: str,
                      analysis_minutes: float = 10.0) -> TrendAnalysis | None:
        """
        Analyze trend for a parameter.

        Args:
            parameter_name: Parameter to analyze
            analysis_minutes: Time period for analysis

        Returns:
            Trend analysis or None if insufficient data
        """
        stats = self.data_buffer.get_statistics(parameter_name, analysis_minutes * 60)

        if stats is None or stats["count"] < 2:
            return None

        # Calculate rate of change
        time_span_min = analysis_minutes
        value_change = stats["last_value"] - stats["first_value"]
        rate = value_change / time_span_min if time_span_min > 0 else 0

        # Determine direction
        if abs(rate) < 0.01 * stats["mean"]:  # Less than 1% change
            direction = TrendDirection.STABLE
        elif rate > 0:
            direction = TrendDirection.INCREASING
        else:
            direction = TrendDirection.DECREASING

        return TrendAnalysis(
            parameter_name=parameter_name,
            direction=direction,
            rate_per_minute=rate,
            current_value=stats["last_value"],
            min_value=stats["min"],
            max_value=stats["max"],
            mean_value=stats["mean"],
            std_deviation=stats["std_dev"],
            analysis_period_minutes=analysis_minutes,
            data_points=stats["count"]
        )

    def get_procedure_duration(self) -> float:
        """Get procedure duration in minutes."""
        if self.procedure_start_time is None:
            return 0.0

        end = self.procedure_end_time or time.time()
        return (end - self.procedure_start_time) / 60.0

    def export_to_csv(self,
                      parameters: list[str] | None = None,
                      start_time: float | None = None,
                      end_time: float | None = None) -> str:
        """
        Export data to CSV format.

        Args:
            parameters: List of parameters to export (None for all)
            start_time: Start time filter
            end_time: End time filter

        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["timestamp", "datetime", "parameter", "value", "unit", "quality"])

        # Filter data
        start = start_time or self.procedure_start_time or 0
        end = end_time or time.time()
        data = self.data_buffer.get_range(start, end)

        if parameters:
            data = [p for p in data if p.parameter_name in parameters]

        # Write data
        for point in sorted(data, key=lambda x: x.timestamp):
            dt = datetime.fromtimestamp(point.timestamp).isoformat()
            writer.writerow([
                point.timestamp,
                dt,
                point.parameter_name,
                round(point.value, 2),
                point.unit,
                point.quality_flag
            ])

        return output.getvalue()

    def export_events_to_json(self) -> str:
        """Export events to JSON format."""
        events_data = []
        for event in self.events:
            events_data.append({
                "timestamp": event.timestamp,
                "datetime": datetime.fromtimestamp(event.timestamp).isoformat(),
                "type": event.event_type,
                "severity": event.severity.name,
                "description": event.description,
                "category": event.category.name,
                "source": event.source,
                "user_id": event.user_id,
                "data": event.data
            })

        return json.dumps(events_data, indent=2)

    def generate_summary_report(self) -> dict:
        """Generate a summary report of the procedure."""
        duration = self.get_procedure_duration()

        # Analyze key parameters
        parameter_summaries = {}
        for param_name in self.parameter_definitions:
            stats = self.data_buffer.get_statistics(param_name, duration * 60)
            if stats:
                parameter_summaries[param_name] = {
                    "min": round(stats["min"], 2),
                    "max": round(stats["max"], 2),
                    "mean": round(stats["mean"], 2),
                    "data_points": stats["count"]
                }

        # Event summary
        events_by_severity = {}
        for severity in EventSeverity:
            count = len([e for e in self.events if e.severity == severity])
            if count > 0:
                events_by_severity[severity.name] = count

        return {
            "procedure_id": self.procedure_id,
            "patient_id": self.patient_id,
            "mrn": self.mrn,
            "procedure_type": self.procedure_type,
            "team": {
                "surgeon": self.surgeon,
                "perfusionist": self.perfusionist,
                "anesthesiologist": self.anesthesiologist
            },
            "timing": {
                "start_time": (
                    datetime.fromtimestamp(self.procedure_start_time).isoformat()
                    if self.procedure_start_time else None
                ),
                "end_time": (
                    datetime.fromtimestamp(self.procedure_end_time).isoformat()
                    if self.procedure_end_time else None
                ),
                "duration_minutes": round(duration, 1)
            },
            "phases": [
                {
                    "name": p.name,
                    "duration_minutes": round((
                        (p.end_time or time.time()) - p.start_time
                    ) / 60, 1),
                    "notes": p.notes
                }
                for p in self.phases
            ],
            "parameters": parameter_summaries,
            "events": {
                "total": len(self.events),
                "by_severity": events_by_severity
            },
            "data_points_recorded": len(self.data_buffer.data)
        }

    def get_status(self) -> dict:
        """Get current logger status."""
        return {
            "is_recording": self.is_recording,
            "procedure_id": self.procedure_id,
            "duration_minutes": round(self.get_procedure_duration(), 1),
            "current_phase": self.phases[-1].name if self.phases else None,
            "data_points": len(self.data_buffer.data),
            "events_recorded": len(self.events),
            "phases_recorded": len(self.phases)
        }
