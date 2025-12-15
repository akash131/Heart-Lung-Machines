"""Tests for the safety monitoring and alarm module."""

import pytest
import time
from hlm.safety import (
    SafetyMonitor,
    SafetyInterlock,
    Alarm,
    AlarmLevel,
    AlarmCategory,
    AlarmState,
    SafetyLimit,
)


class TestAlarm:
    """Tests for Alarm class."""

    def test_creation(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test alarm"
        )
        assert alarm.state == AlarmState.ACTIVE
        assert alarm.level == AlarmLevel.HIGH

    def test_acknowledge(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test alarm"
        )
        alarm.acknowledge("user123")
        assert alarm.state == AlarmState.ACKNOWLEDGED
        assert alarm.acknowledged_by == "user123"
        assert alarm.acknowledged_at is not None

    def test_silence(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test alarm"
        )
        alarm.silence(60.0)
        assert alarm.state == AlarmState.SILENCED
        assert alarm.silence_duration_seconds == 60.0

    def test_silence_critical_not_allowed(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.CRITICAL,
            category=AlarmCategory.FLOW,
            message="Critical alarm"
        )
        alarm.silence(60.0)
        # Critical alarms cannot be silenced
        assert alarm.state == AlarmState.ACTIVE

    def test_resolve(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test alarm"
        )
        alarm.resolve()
        assert alarm.state == AlarmState.RESOLVED

    def test_escalate(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.MEDIUM,
            category=AlarmCategory.FLOW,
            message="Test alarm"
        )
        alarm.escalate()
        assert alarm.level == AlarmLevel.HIGH
        assert alarm.original_level == AlarmLevel.MEDIUM
        assert alarm.escalation_count == 1

    def test_escalate_to_critical(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test alarm"
        )
        alarm.escalate()
        assert alarm.level == AlarmLevel.CRITICAL

    def test_silence_expiry(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test alarm"
        )
        alarm.silence(0.001)  # Very short silence
        time.sleep(0.01)
        assert alarm.is_silence_expired() is True

    def test_get_age(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test alarm",
            timestamp=time.time() - 60  # 60 seconds ago
        )
        age = alarm.get_age_seconds()
        assert 59 <= age <= 61

    def test_to_dict(self):
        alarm = Alarm(
            alarm_id="ALM-001",
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test alarm"
        )
        d = alarm.to_dict()
        assert d["alarm_id"] == "ALM-001"
        assert d["level"] == "HIGH"
        assert d["category"] == "FLOW"


class TestSafetyLimit:
    """Tests for SafetyLimit class."""

    def test_check_value_normal(self):
        limit = SafetyLimit(
            name="Test",
            category=AlarmCategory.FLOW,
            low_warning=1000,
            low_critical=500,
            high_warning=5000,
            high_critical=6000,
            unit=" ml/min"
        )
        level, msg = limit.check_value(3000)
        assert level is None

    def test_check_value_low_warning(self):
        limit = SafetyLimit(
            name="Test",
            category=AlarmCategory.FLOW,
            low_warning=1000,
            low_critical=500
        )
        level, msg = limit.check_value(800)
        assert level == AlarmLevel.HIGH
        assert "low" in msg.lower()

    def test_check_value_low_critical(self):
        limit = SafetyLimit(
            name="Test",
            category=AlarmCategory.FLOW,
            low_critical=500
        )
        level, msg = limit.check_value(300)
        assert level == AlarmLevel.CRITICAL

    def test_check_value_high_warning(self):
        limit = SafetyLimit(
            name="Test",
            category=AlarmCategory.FLOW,
            high_warning=5000
        )
        level, msg = limit.check_value(5500)
        assert level == AlarmLevel.HIGH
        assert "high" in msg.lower()

    def test_check_value_high_critical(self):
        limit = SafetyLimit(
            name="Test",
            category=AlarmCategory.FLOW,
            high_critical=6000
        )
        level, msg = limit.check_value(6500)
        assert level == AlarmLevel.CRITICAL


class TestSafetyMonitor:
    """Tests for SafetyMonitor class."""

    def test_initialization(self):
        monitor = SafetyMonitor()
        assert monitor.is_active is False
        assert len(monitor.safety_limits) > 0

    def test_activate_deactivate(self):
        monitor = SafetyMonitor()
        monitor.activate()
        assert monitor.is_active is True
        monitor.deactivate()
        assert monitor.is_active is False

    def test_check_parameter_normal(self):
        monitor = SafetyMonitor()
        monitor.activate()
        alarm = monitor.check_parameter("Blood Flow", 4000)
        assert alarm is None

    def test_check_parameter_alarm(self):
        monitor = SafetyMonitor()
        monitor.activate()
        alarm = monitor.check_parameter("Blood Flow", 500)  # Very low
        assert alarm is not None
        assert alarm.level == AlarmLevel.CRITICAL

    def test_check_parameter_not_active(self):
        monitor = SafetyMonitor()
        alarm = monitor.check_parameter("Blood Flow", 500)
        assert alarm is None  # Not monitoring when inactive

    def test_create_alarm(self):
        monitor = SafetyMonitor()
        monitor.activate()
        alarm = monitor.create_alarm(
            level=AlarmLevel.HIGH,
            category=AlarmCategory.EQUIPMENT,
            message="Equipment fault",
            source="pump"
        )
        assert alarm.alarm_id.startswith("ALM-")
        assert alarm in monitor.alarms.values()

    def test_alarm_callback(self):
        monitor = SafetyMonitor()
        monitor.activate()
        alarms_received = []

        def callback(alarm):
            alarms_received.append(alarm)

        monitor.register_alarm_callback(callback)
        monitor.create_alarm(
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test"
        )

        assert len(alarms_received) == 1

    def test_emergency_callback(self):
        monitor = SafetyMonitor()
        monitor.activate()
        emergency_triggered = []

        def callback():
            emergency_triggered.append(True)

        monitor.register_emergency_callback(callback)
        monitor.create_alarm(
            level=AlarmLevel.CRITICAL,
            category=AlarmCategory.FLOW,
            message="Critical"
        )

        assert len(emergency_triggered) == 1

    def test_acknowledge_alarm(self):
        monitor = SafetyMonitor()
        monitor.activate()
        alarm = monitor.create_alarm(
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test"
        )
        assert monitor.acknowledge_alarm(alarm.alarm_id, "user123") is True
        assert alarm.state == AlarmState.ACKNOWLEDGED

    def test_silence_alarm(self):
        monitor = SafetyMonitor()
        monitor.activate()
        alarm = monitor.create_alarm(
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test"
        )
        assert monitor.silence_alarm(alarm.alarm_id, 60.0) is True
        assert alarm.state == AlarmState.SILENCED

    def test_silence_critical_alarm_fails(self):
        monitor = SafetyMonitor()
        monitor.activate()
        alarm = monitor.create_alarm(
            level=AlarmLevel.CRITICAL,
            category=AlarmCategory.FLOW,
            message="Critical"
        )
        assert monitor.silence_alarm(alarm.alarm_id, 60.0) is False

    def test_get_active_alarms(self):
        monitor = SafetyMonitor()
        monitor.activate()

        alarm1 = monitor.create_alarm(
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Alarm 1"
        )
        alarm2 = monitor.create_alarm(
            level=AlarmLevel.MEDIUM,
            category=AlarmCategory.PRESSURE,
            message="Alarm 2"
        )
        alarm2.resolve()

        active = monitor.get_active_alarms()
        assert len(active) == 1
        assert alarm1 in active

    def test_get_critical_alarms(self):
        monitor = SafetyMonitor()
        monitor.activate()

        monitor.create_alarm(
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="High alarm"
        )
        critical = monitor.create_alarm(
            level=AlarmLevel.CRITICAL,
            category=AlarmCategory.FLOW,
            message="Critical alarm"
        )

        criticals = monitor.get_critical_alarms()
        assert len(criticals) == 1
        assert critical in criticals

    def test_clear_resolved_alarms(self):
        monitor = SafetyMonitor()
        monitor.activate()

        alarm = monitor.create_alarm(
            level=AlarmLevel.HIGH,
            category=AlarmCategory.FLOW,
            message="Test"
        )
        alarm.resolve()

        cleared = monitor.clear_resolved_alarms()
        assert cleared == 1
        assert alarm.alarm_id not in monitor.alarms
        assert alarm in monitor.alarm_history

    def test_get_alarm_summary(self):
        monitor = SafetyMonitor()
        monitor.activate()

        monitor.create_alarm(level=AlarmLevel.HIGH, category=AlarmCategory.FLOW, message="1")
        monitor.create_alarm(level=AlarmLevel.HIGH, category=AlarmCategory.FLOW, message="2")
        monitor.create_alarm(level=AlarmLevel.CRITICAL, category=AlarmCategory.PRESSURE, message="3")

        summary = monitor.get_alarm_summary()
        assert summary["total_active"] == 3
        assert summary["critical_count"] == 1
        assert summary["high_count"] == 2


class TestSafetyInterlock:
    """Tests for SafetyInterlock class."""

    def test_initialization(self):
        monitor = SafetyMonitor()
        interlock = SafetyInterlock(monitor)
        assert interlock.interlocks_enabled is True

    def test_check_interlock_passes(self):
        monitor = SafetyMonitor()
        monitor.activate()
        interlock = SafetyInterlock(monitor)
        assert interlock.check_interlock("no_critical_alarms") is True

    def test_check_interlock_fails(self):
        monitor = SafetyMonitor()
        monitor.activate()
        monitor.create_alarm(
            level=AlarmLevel.CRITICAL,
            category=AlarmCategory.FLOW,
            message="Critical"
        )
        interlock = SafetyInterlock(monitor)
        assert interlock.check_interlock("no_critical_alarms") is False

    def test_check_all_interlocks(self):
        monitor = SafetyMonitor()
        monitor.activate()
        interlock = SafetyInterlock(monitor)

        passed, failed = interlock.check_all_interlocks()
        assert passed is True
        assert len(failed) == 0

    def test_can_start_bypass(self):
        monitor = SafetyMonitor()
        monitor.activate()
        interlock = SafetyInterlock(monitor)

        can_start, failed = interlock.can_start_bypass()
        assert can_start is True

    def test_can_start_bypass_blocked(self):
        monitor = SafetyMonitor()
        monitor.activate()
        monitor.create_alarm(
            level=AlarmLevel.CRITICAL,
            category=AlarmCategory.FLOW,
            message="Critical"
        )
        interlock = SafetyInterlock(monitor)

        can_start, failed = interlock.can_start_bypass()
        assert can_start is False
        assert "no_critical_alarms" in failed

    def test_override_interlocks(self):
        monitor = SafetyMonitor()
        monitor.activate()
        monitor.create_alarm(
            level=AlarmLevel.CRITICAL,
            category=AlarmCategory.FLOW,
            message="Critical"
        )
        interlock = SafetyInterlock(monitor)

        # Before override
        assert interlock.check_interlock("no_critical_alarms") is False

        # Override
        interlock.override_interlocks("admin", "Emergency situation")
        assert interlock.interlocks_enabled is False
        assert interlock.check_interlock("no_critical_alarms") is True

    def test_restore_interlocks(self):
        monitor = SafetyMonitor()
        interlock = SafetyInterlock(monitor)
        interlock.override_interlocks("admin", "Test")
        interlock.restore_interlocks()
        assert interlock.interlocks_enabled is True

    def test_add_custom_interlock(self):
        monitor = SafetyMonitor()
        interlock = SafetyInterlock(monitor)

        test_condition = True
        interlock.add_interlock("custom_check", lambda: test_condition)
        assert interlock.check_interlock("custom_check") is True

        test_condition = False
        # Note: lambda captures variable reference, not value
        # This test shows interlock checking behavior
