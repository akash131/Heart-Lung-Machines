"""
Calibration and Maintenance System

Regular calibration and maintenance are essential for medical device
accuracy and patient safety.

This module implements:
- Sensor calibration management
- Preventive maintenance tracking
- Component lifecycle management
- Calibration verification
- Maintenance scheduling
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable
import time
from datetime import datetime, timedelta


class CalibrationStatus(Enum):
    """Calibration status states."""
    NOT_CALIBRATED = auto()
    CALIBRATED = auto()
    EXPIRED = auto()
    FAILED = auto()
    IN_PROGRESS = auto()


class MaintenanceStatus(Enum):
    """Maintenance status states."""
    OK = auto()
    DUE_SOON = auto()
    OVERDUE = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()


class ComponentType(Enum):
    """Types of components requiring maintenance."""
    PUMP_HEAD = auto()
    OXYGENATOR = auto()
    HEAT_EXCHANGER = auto()
    PRESSURE_SENSOR = auto()
    FLOW_SENSOR = auto()
    TEMPERATURE_SENSOR = auto()
    BUBBLE_DETECTOR = auto()
    LEVEL_SENSOR = auto()
    TUBING_SET = auto()
    FILTER = auto()


@dataclass
class CalibrationPoint:
    """A single calibration point."""
    reference_value: float
    measured_value: float
    deviation: float = 0.0
    is_acceptable: bool = True

    def calculate_deviation(self) -> float:
        """Calculate deviation from reference."""
        if self.reference_value != 0:
            self.deviation = ((self.measured_value - self.reference_value) /
                             self.reference_value * 100)
        else:
            self.deviation = self.measured_value
        return self.deviation


@dataclass
class CalibrationRecord:
    """Record of a calibration event."""
    sensor_id: str
    sensor_type: str
    timestamp: float = field(default_factory=time.time)
    technician_id: str = ""
    status: CalibrationStatus = CalibrationStatus.CALIBRATED
    calibration_points: list[CalibrationPoint] = field(default_factory=list)
    offset_applied: float = 0.0
    gain_applied: float = 1.0
    expiry_date: float | None = None
    notes: str = ""
    certificate_number: str = ""

    def is_expired(self) -> bool:
        """Check if calibration has expired."""
        if self.expiry_date is None:
            return False
        return time.time() > self.expiry_date


@dataclass
class MaintenanceTask:
    """A maintenance task."""
    task_id: str
    component_type: ComponentType
    component_id: str
    description: str
    interval_days: int
    last_performed: float | None = None
    next_due: float | None = None
    status: MaintenanceStatus = MaintenanceStatus.OK
    performed_by: str = ""
    notes: str = ""
    is_critical: bool = False

    def calculate_next_due(self) -> float:
        """Calculate next due date."""
        if self.last_performed:
            self.next_due = self.last_performed + (self.interval_days * 86400)
        return self.next_due or 0

    def is_overdue(self) -> bool:
        """Check if maintenance is overdue."""
        if self.next_due is None:
            return False
        return time.time() > self.next_due

    def is_due_soon(self, days: int = 7) -> bool:
        """Check if maintenance is due within specified days."""
        if self.next_due is None:
            return False
        threshold = time.time() + (days * 86400)
        return self.next_due <= threshold


@dataclass
class ComponentLifecycle:
    """Lifecycle tracking for a component."""
    component_id: str
    component_type: ComponentType
    serial_number: str = ""
    lot_number: str = ""
    install_date: float | None = None
    expiry_date: float | None = None
    max_use_hours: float | None = None
    current_use_hours: float = 0.0
    max_procedures: int | None = None
    current_procedures: int = 0
    is_single_use: bool = False
    status: str = "active"

    def is_expired(self) -> bool:
        """Check if component has expired."""
        if self.expiry_date and time.time() > self.expiry_date:
            return True
        if self.max_use_hours and self.current_use_hours > self.max_use_hours:
            return True
        if self.max_procedures and self.current_procedures >= self.max_procedures:
            return True
        return False

    def get_remaining_life_percent(self) -> float:
        """Get remaining component life as percentage."""
        if self.max_use_hours and self.max_use_hours > 0:
            return max(0, (1 - self.current_use_hours / self.max_use_hours) * 100)
        if self.max_procedures and self.max_procedures > 0:
            return max(0, (1 - self.current_procedures / self.max_procedures) * 100)
        return 100.0


@dataclass
class SensorCalibrationSpec:
    """Specification for sensor calibration."""
    sensor_type: str
    calibration_points: list[float]  # Reference values
    tolerance_percent: float
    calibration_interval_days: int
    requires_two_point: bool = True
    zero_point: float = 0.0
    span_point: float = 100.0


class CalibrationManager:
    """
    Manages sensor calibration processes.
    """

    def __init__(self):
        """Initialize calibration manager."""
        self.calibration_specs: dict[str, SensorCalibrationSpec] = {}
        self.calibration_records: dict[str, list[CalibrationRecord]] = {}
        self.current_calibration: CalibrationRecord | None = None

        self._initialize_specs()

    def _initialize_specs(self) -> None:
        """Initialize calibration specifications."""
        self.calibration_specs = {
            "pressure_arterial": SensorCalibrationSpec(
                sensor_type="pressure",
                calibration_points=[0.0, 200.0, 400.0],
                tolerance_percent=2.0,
                calibration_interval_days=30,
                zero_point=0.0,
                span_point=400.0
            ),
            "pressure_venous": SensorCalibrationSpec(
                sensor_type="pressure",
                calibration_points=[-50.0, 0.0, 50.0],
                tolerance_percent=2.0,
                calibration_interval_days=30,
                zero_point=0.0,
                span_point=50.0
            ),
            "flow": SensorCalibrationSpec(
                sensor_type="flow",
                calibration_points=[0.0, 2500.0, 5000.0],
                tolerance_percent=3.0,
                calibration_interval_days=90,
                zero_point=0.0,
                span_point=5000.0
            ),
            "temperature": SensorCalibrationSpec(
                sensor_type="temperature",
                calibration_points=[25.0, 37.0],
                tolerance_percent=0.5,
                calibration_interval_days=180,
                zero_point=25.0,
                span_point=37.0
            ),
            "level": SensorCalibrationSpec(
                sensor_type="level",
                calibration_points=[0.0, 2000.0, 4000.0],
                tolerance_percent=5.0,
                calibration_interval_days=30,
                zero_point=0.0,
                span_point=4000.0
            ),
        }

    def start_calibration(self,
                          sensor_id: str,
                          sensor_type: str,
                          technician_id: str = "") -> CalibrationRecord:
        """
        Start a calibration procedure.

        Args:
            sensor_id: Sensor identifier
            sensor_type: Type of sensor
            technician_id: Technician performing calibration

        Returns:
            New calibration record
        """
        self.current_calibration = CalibrationRecord(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            technician_id=technician_id,
            status=CalibrationStatus.IN_PROGRESS
        )
        return self.current_calibration

    def add_calibration_point(self,
                               reference_value: float,
                               measured_value: float,
                               tolerance_percent: float = 2.0) -> CalibrationPoint:
        """
        Add a calibration point to current calibration.

        Args:
            reference_value: Known reference value
            measured_value: Measured value
            tolerance_percent: Acceptable tolerance

        Returns:
            Calibration point
        """
        if self.current_calibration is None:
            raise ValueError("No calibration in progress")

        point = CalibrationPoint(
            reference_value=reference_value,
            measured_value=measured_value
        )
        point.calculate_deviation()
        point.is_acceptable = abs(point.deviation) <= tolerance_percent

        self.current_calibration.calibration_points.append(point)
        return point

    def complete_calibration(self,
                              expiry_days: int = 30,
                              offset: float = 0.0,
                              gain: float = 1.0) -> CalibrationRecord:
        """
        Complete the current calibration.

        Args:
            expiry_days: Days until calibration expires
            offset: Offset to apply
            gain: Gain to apply

        Returns:
            Completed calibration record
        """
        if self.current_calibration is None:
            raise ValueError("No calibration in progress")

        # Check if all points are acceptable
        all_acceptable = all(
            p.is_acceptable for p in self.current_calibration.calibration_points
        )

        self.current_calibration.status = (
            CalibrationStatus.CALIBRATED if all_acceptable
            else CalibrationStatus.FAILED
        )
        self.current_calibration.offset_applied = offset
        self.current_calibration.gain_applied = gain
        self.current_calibration.expiry_date = time.time() + (expiry_days * 86400)

        # Store record
        sensor_id = self.current_calibration.sensor_id
        if sensor_id not in self.calibration_records:
            self.calibration_records[sensor_id] = []
        self.calibration_records[sensor_id].append(self.current_calibration)

        record = self.current_calibration
        self.current_calibration = None
        return record

    def get_calibration_status(self, sensor_id: str) -> CalibrationStatus:
        """Get current calibration status for a sensor."""
        if sensor_id not in self.calibration_records:
            return CalibrationStatus.NOT_CALIBRATED

        records = self.calibration_records[sensor_id]
        if not records:
            return CalibrationStatus.NOT_CALIBRATED

        latest = records[-1]
        if latest.is_expired():
            return CalibrationStatus.EXPIRED
        return latest.status

    def get_expiring_calibrations(self, days: int = 7) -> list[str]:
        """Get sensors with calibrations expiring soon."""
        expiring = []
        threshold = time.time() + (days * 86400)

        for sensor_id, records in self.calibration_records.items():
            if records:
                latest = records[-1]
                if latest.expiry_date and latest.expiry_date <= threshold:
                    expiring.append(sensor_id)

        return expiring


class MaintenanceManager:
    """
    Manages preventive maintenance scheduling and tracking.
    """

    def __init__(self):
        """Initialize maintenance manager."""
        self.tasks: dict[str, MaintenanceTask] = {}
        self.components: dict[str, ComponentLifecycle] = {}
        self.maintenance_history: list[dict] = []

        self._initialize_standard_tasks()

    def _initialize_standard_tasks(self) -> None:
        """Initialize standard maintenance tasks."""
        standard_tasks = [
            MaintenanceTask(
                task_id="PM001",
                component_type=ComponentType.PUMP_HEAD,
                component_id="main_pump",
                description="Inspect roller pump head for wear",
                interval_days=30,
                is_critical=True
            ),
            MaintenanceTask(
                task_id="PM002",
                component_type=ComponentType.PRESSURE_SENSOR,
                component_id="arterial_pressure",
                description="Calibrate arterial pressure transducer",
                interval_days=30,
                is_critical=True
            ),
            MaintenanceTask(
                task_id="PM003",
                component_type=ComponentType.FLOW_SENSOR,
                component_id="arterial_flow",
                description="Calibrate flow sensor",
                interval_days=90,
                is_critical=True
            ),
            MaintenanceTask(
                task_id="PM004",
                component_type=ComponentType.TEMPERATURE_SENSOR,
                component_id="arterial_temp",
                description="Calibrate temperature sensors",
                interval_days=180,
                is_critical=False
            ),
            MaintenanceTask(
                task_id="PM005",
                component_type=ComponentType.BUBBLE_DETECTOR,
                component_id="arterial_bubble",
                description="Test bubble detector sensitivity",
                interval_days=30,
                is_critical=True
            ),
            MaintenanceTask(
                task_id="PM006",
                component_type=ComponentType.HEAT_EXCHANGER,
                component_id="heater_cooler",
                description="Clean and inspect heat exchanger",
                interval_days=7,
                is_critical=True
            ),
        ]

        for task in standard_tasks:
            self.tasks[task.task_id] = task

    def add_task(self, task: MaintenanceTask) -> None:
        """Add a maintenance task."""
        self.tasks[task.task_id] = task

    def record_maintenance(self,
                           task_id: str,
                           performed_by: str,
                           notes: str = "") -> bool:
        """
        Record completion of a maintenance task.

        Args:
            task_id: Task identifier
            performed_by: Person who performed maintenance
            notes: Additional notes

        Returns:
            True if recorded successfully
        """
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        task.last_performed = time.time()
        task.performed_by = performed_by
        task.notes = notes
        task.calculate_next_due()
        task.status = MaintenanceStatus.COMPLETED

        # Record in history
        self.maintenance_history.append({
            "task_id": task_id,
            "component_id": task.component_id,
            "description": task.description,
            "performed_at": task.last_performed,
            "performed_by": performed_by,
            "notes": notes
        })

        return True

    def get_due_tasks(self, include_overdue: bool = True) -> list[MaintenanceTask]:
        """Get tasks that are due or overdue."""
        due_tasks = []
        for task in self.tasks.values():
            if task.is_overdue():
                task.status = MaintenanceStatus.OVERDUE
                if include_overdue:
                    due_tasks.append(task)
            elif task.is_due_soon():
                task.status = MaintenanceStatus.DUE_SOON
                due_tasks.append(task)
            else:
                task.status = MaintenanceStatus.OK

        return due_tasks

    def get_critical_overdue(self) -> list[MaintenanceTask]:
        """Get critical tasks that are overdue."""
        return [
            task for task in self.tasks.values()
            if task.is_overdue() and task.is_critical
        ]

    def add_component(self, component: ComponentLifecycle) -> None:
        """Add a component for lifecycle tracking."""
        self.components[component.component_id] = component

    def update_component_usage(self,
                                component_id: str,
                                hours: float = 0,
                                procedures: int = 0) -> None:
        """Update component usage metrics."""
        if component_id in self.components:
            comp = self.components[component_id]
            comp.current_use_hours += hours
            comp.current_procedures += procedures

    def get_expiring_components(self, days: int = 30) -> list[ComponentLifecycle]:
        """Get components expiring within specified days."""
        expiring = []
        threshold = time.time() + (days * 86400)

        for comp in self.components.values():
            if comp.expiry_date and comp.expiry_date <= threshold:
                expiring.append(comp)
            elif comp.get_remaining_life_percent() < 20:
                expiring.append(comp)

        return expiring

    def get_status(self) -> dict:
        """Get maintenance system status."""
        due_tasks = self.get_due_tasks()
        critical_overdue = self.get_critical_overdue()
        expiring_components = self.get_expiring_components()

        return {
            "total_tasks": len(self.tasks),
            "due_tasks": len(due_tasks),
            "critical_overdue": len(critical_overdue),
            "tracked_components": len(self.components),
            "expiring_components": len(expiring_components),
            "maintenance_history_count": len(self.maintenance_history),
            "tasks": {
                task_id: {
                    "description": task.description,
                    "status": task.status.name,
                    "is_critical": task.is_critical,
                    "next_due": (
                        datetime.fromtimestamp(task.next_due).isoformat()
                        if task.next_due else None
                    )
                }
                for task_id, task in self.tasks.items()
            }
        }


class MaintenanceSystem:
    """
    Combined calibration and maintenance system.
    """

    def __init__(self):
        """Initialize maintenance system."""
        self.calibration_manager = CalibrationManager()
        self.maintenance_manager = MaintenanceManager()

        # Callbacks
        self._alert_callbacks: list[Callable[[str, str], None]] = []

    def register_alert_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register alert callback."""
        self._alert_callbacks.append(callback)

    def _trigger_alert(self, level: str, message: str) -> None:
        """Trigger alert callbacks."""
        for callback in self._alert_callbacks:
            callback(level, message)

    def check_system_readiness(self) -> tuple[bool, list[str]]:
        """
        Check if system is ready for use.

        Returns:
            Tuple of (is_ready, list of issues)
        """
        issues = []

        # Check critical calibrations
        for sensor_id, spec in self.calibration_manager.calibration_specs.items():
            status = self.calibration_manager.get_calibration_status(sensor_id)
            if status == CalibrationStatus.EXPIRED:
                issues.append(f"Calibration expired: {sensor_id}")
            elif status == CalibrationStatus.NOT_CALIBRATED:
                issues.append(f"Not calibrated: {sensor_id}")
            elif status == CalibrationStatus.FAILED:
                issues.append(f"Calibration failed: {sensor_id}")

        # Check critical maintenance
        critical_overdue = self.maintenance_manager.get_critical_overdue()
        for task in critical_overdue:
            issues.append(f"Critical maintenance overdue: {task.description}")

        # Check expiring components
        expired = [
            c for c in self.maintenance_manager.components.values()
            if c.is_expired()
        ]
        for comp in expired:
            issues.append(f"Component expired: {comp.component_id}")

        is_ready = len(issues) == 0
        return (is_ready, issues)

    def perform_daily_check(self) -> dict:
        """
        Perform daily maintenance check.

        Returns:
            Check results
        """
        results = {
            "timestamp": time.time(),
            "is_ready": True,
            "issues": [],
            "warnings": [],
            "due_tasks": [],
            "expiring_calibrations": [],
            "expiring_components": []
        }

        # System readiness
        is_ready, issues = self.check_system_readiness()
        results["is_ready"] = is_ready
        results["issues"] = issues

        # Due tasks
        due_tasks = self.maintenance_manager.get_due_tasks()
        results["due_tasks"] = [t.description for t in due_tasks]

        # Expiring calibrations
        expiring_cal = self.calibration_manager.get_expiring_calibrations(days=7)
        results["expiring_calibrations"] = expiring_cal

        # Expiring components
        expiring_comp = self.maintenance_manager.get_expiring_components(days=30)
        results["expiring_components"] = [c.component_id for c in expiring_comp]

        # Generate alerts
        if not is_ready:
            self._trigger_alert("critical", "System not ready for clinical use")

        for task in due_tasks:
            if task.is_overdue():
                self._trigger_alert("warning", f"Maintenance overdue: {task.description}")

        return results

    def get_status(self) -> dict:
        """Get combined maintenance system status."""
        is_ready, issues = self.check_system_readiness()

        return {
            "is_ready": is_ready,
            "issues": issues,
            "calibration": {
                "specs_defined": len(self.calibration_manager.calibration_specs),
                "sensors_calibrated": len(self.calibration_manager.calibration_records),
                "expiring_soon": len(
                    self.calibration_manager.get_expiring_calibrations(days=7)
                )
            },
            "maintenance": self.maintenance_manager.get_status()
        }
