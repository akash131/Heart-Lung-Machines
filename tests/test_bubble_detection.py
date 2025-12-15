"""Tests for the bubble detection and removal module."""

import pytest
from hlm.bubble_detection import (
    BubbleDetector,
    BubbleRemovalSystem,
    BubbleSize,
    BubbleAlertLevel,
    DetectorLocation,
    UltrasonicSensor,
    BubbleTrap,
    BubbleEvent,
)


class TestUltrasonicSensor:
    """Tests for UltrasonicSensor."""

    def test_no_bubble_detection(self):
        sensor = UltrasonicSensor(location=DetectorLocation.ARTERIAL_LINE)
        result = sensor.update_reading(1.0)  # Perfect signal
        assert result is None

    def test_micro_bubble_detection(self):
        sensor = UltrasonicSensor(location=DetectorLocation.ARTERIAL_LINE)
        result = sensor.update_reading(0.95)  # Slight attenuation
        assert result == BubbleSize.MICRO

    def test_small_bubble_detection(self):
        sensor = UltrasonicSensor(location=DetectorLocation.ARTERIAL_LINE)
        result = sensor.update_reading(0.80)
        assert result == BubbleSize.SMALL

    def test_medium_bubble_detection(self):
        sensor = UltrasonicSensor(location=DetectorLocation.ARTERIAL_LINE)
        result = sensor.update_reading(0.50)
        assert result == BubbleSize.MEDIUM

    def test_large_bubble_detection(self):
        sensor = UltrasonicSensor(location=DetectorLocation.ARTERIAL_LINE)
        result = sensor.update_reading(0.20)
        assert result == BubbleSize.LARGE

    def test_massive_air_detection(self):
        sensor = UltrasonicSensor(location=DetectorLocation.ARTERIAL_LINE)
        result = sensor.update_reading(0.05)
        assert result == BubbleSize.MASSIVE

    def test_estimate_volume(self):
        sensor = UltrasonicSensor(location=DetectorLocation.ARTERIAL_LINE)
        assert sensor.estimate_volume(BubbleSize.MICRO) == 0.5
        assert sensor.estimate_volume(BubbleSize.SMALL) == 5.0
        assert sensor.estimate_volume(BubbleSize.LARGE) == 200.0

    def test_calibration(self):
        sensor = UltrasonicSensor(location=DetectorLocation.ARTERIAL_LINE)
        sensor.calibrate(blood_baseline=0.95, air_baseline=0.0)
        assert sensor.calibration_factor == pytest.approx(1.0 / 0.95, rel=0.01)


class TestBubbleTrap:
    """Tests for BubbleTrap."""

    def test_accumulate_air(self):
        trap = BubbleTrap(name="test")
        trap.accumulate_air(1000)  # 1000 ul = 1 ml
        assert trap.accumulated_air_ml == 1.0

    def test_needs_purge(self):
        trap = BubbleTrap(name="test", purge_threshold_ml=5.0)
        trap.accumulated_air_ml = 3.0
        assert trap.needs_purge() is False
        trap.accumulated_air_ml = 6.0
        assert trap.needs_purge() is True

    def test_purge(self):
        trap = BubbleTrap(name="test")
        trap.accumulated_air_ml = 10.0
        purged = trap.purge()
        assert purged == 10.0
        assert trap.accumulated_air_ml == 0.0

    def test_get_fill_percentage(self):
        trap = BubbleTrap(name="test", trap_volume_ml=100)
        trap.accumulated_air_ml = 25
        assert trap.get_fill_percentage() == 25.0


class TestBubbleDetector:
    """Tests for BubbleDetector."""

    def test_initialization(self):
        detector = BubbleDetector()
        assert len(detector.sensors) == len(DetectorLocation)
        assert detector.is_monitoring is False

    def test_start_stop_monitoring(self):
        detector = BubbleDetector()
        detector.start_monitoring()
        assert detector.is_monitoring is True
        detector.stop_monitoring()
        assert detector.is_monitoring is False

    def test_update_sensor_creates_event(self):
        detector = BubbleDetector()
        detector.start_monitoring()
        event = detector.update_sensor(DetectorLocation.ARTERIAL_LINE, 0.50)
        assert event is not None
        assert event.size == BubbleSize.MEDIUM
        assert event.location == DetectorLocation.ARTERIAL_LINE

    def test_update_sensor_no_event_when_clear(self):
        detector = BubbleDetector()
        detector.start_monitoring()
        event = detector.update_sensor(DetectorLocation.ARTERIAL_LINE, 1.0)
        assert event is None

    def test_update_sensor_not_monitoring(self):
        detector = BubbleDetector()
        event = detector.update_sensor(DetectorLocation.ARTERIAL_LINE, 0.50)
        assert event is None

    def test_alert_escalation_arterial(self):
        detector = BubbleDetector()
        detector.start_monitoring()
        # Small bubble in arterial line should be escalated
        event = detector.update_sensor(DetectorLocation.ARTERIAL_LINE, 0.85)
        assert event.alert_level == BubbleAlertLevel.CRITICAL  # Escalated from WARNING

    def test_alert_callback(self):
        detector = BubbleDetector()
        alerts = []

        def callback(level, message):
            alerts.append((level, message))

        detector.register_alert_callback(callback)
        detector.start_monitoring()
        detector.update_sensor(DetectorLocation.ARTERIAL_LINE, 0.50)

        assert len(alerts) > 0

    def test_get_recent_events(self):
        detector = BubbleDetector()
        detector.start_monitoring()
        detector.update_sensor(DetectorLocation.VENOUS_LINE, 0.80)
        detector.update_sensor(DetectorLocation.ARTERIAL_LINE, 0.90)

        events = detector.get_recent_events(seconds=60)
        assert len(events) == 2

    def test_get_arterial_line_status(self):
        detector = BubbleDetector()
        detector.start_monitoring()
        status = detector.get_arterial_line_status()
        assert "is_active" in status
        assert "is_clear" in status

    def test_get_status(self):
        detector = BubbleDetector()
        status = detector.get_status()
        assert "is_monitoring" in status
        assert "sensors" in status
        assert "arterial_line" in status


class TestBubbleRemovalSystem:
    """Tests for BubbleRemovalSystem."""

    def test_initialization(self):
        system = BubbleRemovalSystem()
        assert system.is_active is False
        assert len(system.traps) == 3
        assert "venous" in system.traps
        assert "arterial" in system.traps

    def test_activate_deactivate(self):
        system = BubbleRemovalSystem()
        system.activate()
        assert system.is_active is True
        assert system.detector.is_monitoring is True
        system.deactivate()
        assert system.is_active is False

    def test_update_sensor_routes_to_trap(self):
        system = BubbleRemovalSystem()
        system.activate()
        event = system.update_sensor_reading(DetectorLocation.ARTERIAL_LINE, 0.80)
        assert event is not None
        assert event.was_removed is True
        assert system.traps["arterial"].accumulated_air_ml > 0

    def test_clamp_unclamp_line(self):
        system = BubbleRemovalSystem()
        assert system.line_clamps["arterial"] is False
        assert system.clamp_line("arterial") is True
        assert system.line_clamps["arterial"] is True
        assert system.unclamp_line("arterial") is True
        assert system.line_clamps["arterial"] is False

    def test_clamp_invalid_line(self):
        system = BubbleRemovalSystem()
        assert system.clamp_line("invalid") is False

    def test_purge_trap(self):
        system = BubbleRemovalSystem()
        system.traps["arterial"].accumulated_air_ml = 5.0
        purged = system.purge_trap("arterial")
        assert purged == 5.0
        assert system.traps["arterial"].accumulated_air_ml == 0.0

    def test_get_traps_needing_purge(self):
        system = BubbleRemovalSystem()
        system.traps["arterial"].accumulated_air_ml = 25.0  # Above 20ml threshold
        system.traps["venous"].accumulated_air_ml = 5.0  # Below threshold
        needing_purge = system.get_traps_needing_purge()
        assert "arterial" in needing_purge
        assert "venous" not in needing_purge

    def test_de_airing_sequence(self):
        system = BubbleRemovalSystem()
        system.traps["arterial"].accumulated_air_ml = 10.0
        system.traps["venous"].accumulated_air_ml = 5.0

        results = system.perform_de_airing_sequence()

        assert results["total_air_removed_ml"] == 15.0
        assert "arterial" in results["traps_purged"]
        assert "venous" in results["traps_purged"]

    def test_auto_clamp_on_critical(self):
        system = BubbleRemovalSystem()
        system.activate()
        system.auto_clamp_enabled = True
        system.auto_clamp_threshold = BubbleAlertLevel.CRITICAL

        # Trigger critical bubble in arterial line
        system.update_sensor_reading(DetectorLocation.ARTERIAL_LINE, 0.50)

        # Auto-clamp should have activated
        assert system.line_clamps["arterial"] is True

    def test_emergency_callback(self):
        system = BubbleRemovalSystem()
        emergency_triggered = []

        def emergency_callback():
            emergency_triggered.append(True)

        system.register_emergency_callback(emergency_callback)
        system.activate()

        # Trigger massive air (emergency)
        system.update_sensor_reading(DetectorLocation.ARTERIAL_LINE, 0.05)

        assert len(emergency_triggered) > 0

    def test_get_status(self):
        system = BubbleRemovalSystem()
        status = system.get_status()
        assert "is_active" in status
        assert "detection" in status
        assert "traps" in status
        assert "line_clamps" in status
