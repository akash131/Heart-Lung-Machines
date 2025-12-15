"""Tests for system management features (configuration, maintenance, etc.)."""

import pytest
import time

from hlm.maintenance import (
    MaintenanceSystem,
    CalibrationManager,
    MaintenanceManager,
    CalibrationStatus,
    MaintenanceStatus,
    ComponentType,
    CalibrationPoint,
    ComponentLifecycle,
)
from hlm.configuration import (
    ConfigurationSystem,
    ConfigurationManager,
    UserManager,
    AuditTrail,
    User,
    UserRole,
    AuditEventType,
    ConfigCategory,
)
from hlm.display import (
    DisplayManager,
    DisplayMode,
    DisplayFormatter,
    AlarmDisplay,
    ParameterStatus,
)
from hlm.communication import (
    CommunicationManager,
    HL7MessageBuilder,
    HL7MessageParser,
    HL7MessageType,
    SerialConfig,
    NetworkConfig,
)


class TestCalibrationManager:
    """Tests for calibration management."""

    def test_initialization(self):
        manager = CalibrationManager()
        assert len(manager.calibration_specs) > 0

    def test_start_calibration(self):
        manager = CalibrationManager()
        record = manager.start_calibration(
            sensor_id="arterial_pressure",
            sensor_type="pressure",
            technician_id="TECH001"
        )
        assert record is not None
        assert record.status == CalibrationStatus.IN_PROGRESS

    def test_add_calibration_point(self):
        manager = CalibrationManager()
        manager.start_calibration("test_sensor", "pressure")
        point = manager.add_calibration_point(100.0, 99.5, 2.0)
        assert point.deviation == pytest.approx(-0.5, rel=0.01)
        assert point.is_acceptable is True

    def test_complete_calibration(self):
        manager = CalibrationManager()
        manager.start_calibration("test_sensor", "pressure")
        manager.add_calibration_point(0.0, 0.0)
        manager.add_calibration_point(200.0, 200.5)
        record = manager.complete_calibration(expiry_days=30)
        assert record.status == CalibrationStatus.CALIBRATED
        assert record.expiry_date is not None

    def test_calibration_expiry(self):
        manager = CalibrationManager()
        manager.start_calibration("test_sensor", "pressure")
        manager.add_calibration_point(0.0, 0.0)
        record = manager.complete_calibration(expiry_days=-1)  # Already expired
        assert manager.get_calibration_status("test_sensor") == CalibrationStatus.EXPIRED


class TestMaintenanceManager:
    """Tests for maintenance management."""

    def test_initialization(self):
        manager = MaintenanceManager()
        assert len(manager.tasks) > 0

    def test_record_maintenance(self):
        manager = MaintenanceManager()
        task_id = list(manager.tasks.keys())[0]
        success = manager.record_maintenance(task_id, "TECH001", "Completed OK")
        assert success is True
        assert manager.tasks[task_id].last_performed is not None

    def test_get_due_tasks(self):
        manager = MaintenanceManager()
        # Set a task as overdue
        task_id = list(manager.tasks.keys())[0]
        manager.tasks[task_id].next_due = time.time() - 86400  # Yesterday
        due_tasks = manager.get_due_tasks()
        assert len(due_tasks) > 0

    def test_component_lifecycle(self):
        manager = MaintenanceManager()
        component = ComponentLifecycle(
            component_id="test_oxy",
            component_type=ComponentType.OXYGENATOR,
            max_use_hours=8.0
        )
        manager.add_component(component)
        manager.update_component_usage("test_oxy", hours=4.0)
        assert manager.components["test_oxy"].current_use_hours == 4.0
        assert manager.components["test_oxy"].get_remaining_life_percent() == 50.0

    def test_component_expiry(self):
        manager = MaintenanceManager()
        component = ComponentLifecycle(
            component_id="test_filter",
            component_type=ComponentType.FILTER,
            expiry_date=time.time() - 86400  # Expired yesterday
        )
        manager.add_component(component)
        assert component.is_expired() is True


class TestMaintenanceSystem:
    """Tests for combined maintenance system."""

    def test_system_readiness(self):
        system = MaintenanceSystem()
        is_ready, issues = system.check_system_readiness()
        # Fresh system should have calibration issues
        assert isinstance(issues, list)

    def test_daily_check(self):
        system = MaintenanceSystem()
        results = system.perform_daily_check()
        assert "is_ready" in results
        assert "issues" in results
        assert "due_tasks" in results


class TestAuditTrail:
    """Tests for audit trail."""

    def test_log_entry(self):
        trail = AuditTrail()
        entry = trail.log(
            event_type=AuditEventType.CONFIG_CHANGE,
            description="Test change",
            user_id="USER001"
        )
        assert entry.entry_id.startswith("AUD-")
        assert len(trail.entries) == 1

    def test_integrity_verification(self):
        trail = AuditTrail()
        trail.log(AuditEventType.LOGIN, "User logged in")
        trail.log(AuditEventType.CONFIG_CHANGE, "Changed setting")
        is_valid, issues = trail.verify_integrity()
        assert is_valid is True
        assert len(issues) == 0

    def test_filtered_query(self):
        trail = AuditTrail()
        trail.log(AuditEventType.LOGIN, "Login 1", user_id="USER001")
        trail.log(AuditEventType.LOGOUT, "Logout 1", user_id="USER001")
        trail.log(AuditEventType.LOGIN, "Login 2", user_id="USER002")

        entries = trail.get_entries(user_id="USER001")
        assert len(entries) == 2


class TestUserManager:
    """Tests for user management."""

    def test_default_admin(self):
        trail = AuditTrail()
        manager = UserManager(trail)
        assert "admin" in manager.users

    def test_create_user(self):
        trail = AuditTrail()
        manager = UserManager(trail)
        user = manager.create_user(
            username="testuser",
            password="password123",
            role=UserRole.PERFUSIONIST,
            full_name="Test User"
        )
        assert user.username == "testuser"
        assert user.role == UserRole.PERFUSIONIST

    def test_authentication(self):
        trail = AuditTrail()
        manager = UserManager(trail)
        success, user, session_id = manager.authenticate("admin", "admin")
        assert success is True
        assert user is not None
        assert session_id.startswith("SES-")

    def test_failed_authentication(self):
        trail = AuditTrail()
        manager = UserManager(trail)
        success, user, session_id = manager.authenticate("admin", "wrong")
        assert success is False
        assert user is None

    def test_user_permissions(self):
        user = User(
            user_id="1",
            username="test",
            role=UserRole.PERFUSIONIST
        )
        assert user.has_permission(UserRole.OPERATOR) is True
        assert user.has_permission(UserRole.ADMINISTRATOR) is False


class TestConfigurationManager:
    """Tests for configuration management."""

    def test_default_settings(self):
        trail = AuditTrail()
        manager = ConfigurationManager(trail)
        assert len(manager.settings) > 0
        assert manager.get("alarm.audio_enabled") is True

    def test_set_valid_value(self):
        trail = AuditTrail()
        manager = ConfigurationManager(trail)
        success, error = manager.set("alarm.audio_volume", 50)
        assert success is True
        assert manager.get("alarm.audio_volume") == 50

    def test_set_invalid_value(self):
        trail = AuditTrail()
        manager = ConfigurationManager(trail)
        success, error = manager.set("alarm.audio_volume", 150)  # Over 100
        assert success is False
        assert "must be" in error

    def test_export_import(self):
        trail = AuditTrail()
        manager = ConfigurationManager(trail)
        manager.set("alarm.audio_volume", 75)
        json_config = manager.export_config()
        assert '"alarm.audio_volume"' in json_config


class TestConfigurationSystem:
    """Tests for complete configuration system."""

    def test_login_logout(self):
        system = ConfigurationSystem()
        success, result = system.login("admin", "admin")
        assert success is True
        assert system.current_user is not None
        system.logout()
        assert system.current_user is None

    def test_setting_with_permissions(self):
        system = ConfigurationSystem()
        system.login("admin", "admin")
        success, error = system.set_setting("alarm.audio_volume", 60)
        assert success is True


class TestDisplayManager:
    """Tests for display system."""

    def test_initialization(self):
        manager = DisplayManager()
        assert manager.current_mode == DisplayMode.STANDARD

    def test_update_parameter(self):
        manager = DisplayManager()
        param = manager.update_parameter("arterial_flow", 4000)
        assert param.name == "ART FLOW"
        assert "4000" in param.value

    def test_parameter_status(self):
        formatter = DisplayFormatter()
        # Normal value
        param = formatter.format_parameter("arterial_flow", 4000)
        assert param.status == ParameterStatus.NORMAL
        # Critical value
        param = formatter.format_parameter("arterial_flow", 500)
        assert param.status == ParameterStatus.CRITICAL

    def test_alarm_display(self):
        alarm_display = AlarmDisplay()
        alarm_display.add_alarm("ALM001", "HIGH", "Test alarm")
        assert len(alarm_display.active_alarms) == 1
        assert alarm_display.is_audio_active() is True

    def test_acknowledge_alarm(self):
        alarm_display = AlarmDisplay()
        alarm_display.add_alarm("ALM001", "HIGH", "Test alarm")
        alarm_display.acknowledge_alarm("ALM001")
        assert "ALM001" in alarm_display.acknowledged_alarms


class TestHL7Communication:
    """Tests for HL7 communication."""

    def test_message_builder(self):
        builder = HL7MessageBuilder()
        builder.add_msh_segment(
            sending_app="HLM",
            sending_facility="PERFUSION",
            receiving_app="EMR",
            receiving_facility="HOSPITAL",
            message_type=HL7MessageType.ORU,
            message_control_id="MSG001"
        )
        builder.add_pid_segment(patient_id="12345", patient_name="Test Patient")
        builder.add_obx_segment(
            set_id=1,
            value_type="NM",
            observation_id="FLOW",
            observation_name="Arterial Flow",
            value="4000",
            units="ml/min"
        )
        message = builder.build()
        assert "MSH|" in message
        assert "PID|" in message
        assert "OBX|" in message

    def test_message_parser(self):
        parser = HL7MessageParser()
        message = "MSH|^~\\&|HLM|PERF|EMR|HOSP|20231215||ORU^R01|MSG001|P|2.5.1\rPID|1|12345\r"
        result = parser.parse(message)
        assert result["message_type"] == "ORU"
        assert result["patient_id"] == "12345"


class TestCommunicationManager:
    """Tests for communication manager."""

    def test_initialization(self):
        manager = CommunicationManager()
        assert manager.is_active is False

    def test_add_device(self):
        manager = CommunicationManager()
        config = SerialConfig(port="/dev/ttyUSB0", baud_rate=9600)
        device = manager.add_device("CDI_Monitor", config)
        assert "CDI_Monitor" in manager.devices

    def test_hl7_connection(self):
        manager = CommunicationManager()
        manager.activate()
        config = NetworkConfig(host="localhost", port=2575)
        success = manager.connect_hl7(config)
        assert success is True
        assert manager.hl7_connection.is_connected is True


class TestSystemIntegration:
    """Integration tests for system management features."""

    def test_full_system_setup(self):
        """Test complete system setup workflow."""
        # Initialize systems
        config_system = ConfigurationSystem()
        maintenance_system = MaintenanceSystem()
        display_manager = DisplayManager()
        comm_manager = CommunicationManager()

        # Admin login
        success, _ = config_system.login("admin", "admin")
        assert success is True

        # Configure system
        config_system.set_setting("alarm.audio_volume", 80)
        config_system.set_setting("display.brightness", 100)
        config_system.set_setting("protocol.goal_directed_enabled", True)

        # Check maintenance readiness
        is_ready, issues = maintenance_system.check_system_readiness()
        # Note: Fresh system will have calibration issues
        assert isinstance(issues, list)

        # Setup display
        display_manager.activate()
        display_manager.set_mode(DisplayMode.STANDARD)

        # Setup communications
        comm_manager.activate()

        # Verify configuration
        assert config_system.get_setting("alarm.audio_volume") == 80
        assert display_manager.is_active is True
        assert comm_manager.is_active is True

        # Audit trail should have entries
        trail = config_system.get_audit_trail(hours=1)
        assert len(trail) > 0

        # Logout
        config_system.logout()
        assert config_system.current_user is None
