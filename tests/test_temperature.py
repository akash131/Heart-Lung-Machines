"""Tests for the temperature management module."""

import pytest
import time
from hlm.temperature import (
    TemperatureController,
    HeatExchanger,
    TemperatureMode,
    TemperaturePoint,
    TemperatureReading,
    TemperatureLimits,
)


class TestTemperatureReading:
    """Tests for TemperatureReading."""

    def test_to_fahrenheit(self):
        reading = TemperatureReading(location="test", value_celsius=37.0)
        assert reading.to_fahrenheit() == pytest.approx(98.6, rel=0.01)

    def test_to_fahrenheit_freezing(self):
        reading = TemperatureReading(location="test", value_celsius=0.0)
        assert reading.to_fahrenheit() == 32.0


class TestTemperaturePoint:
    """Tests for TemperaturePoint."""

    def test_update(self):
        point = TemperaturePoint(name="test", location="Test Location")
        result = point.update(36.5)
        assert result == 36.5
        assert point.current_temp_celsius == 36.5

    def test_update_with_offset(self):
        point = TemperaturePoint(name="test", location="Test", offset_celsius=0.5)
        result = point.update(36.0)
        assert result == 36.5  # Raw + offset

    def test_get_reading(self):
        point = TemperaturePoint(name="test", location="Test Location")
        point.update(37.0)
        reading = point.get_reading()
        assert reading.value_celsius == 37.0
        assert reading.location == "Test Location"
        assert reading.is_valid is True


class TestHeatExchanger:
    """Tests for HeatExchanger."""

    def test_activate_deactivate(self):
        hx = HeatExchanger()
        hx.activate()
        assert hx.is_active is True
        hx.deactivate()
        assert hx.is_active is False
        assert hx.water_flow_l_min == 0.0

    def test_set_target_temperature_valid(self):
        hx = HeatExchanger()
        assert hx.set_target_temperature(30.0) is True
        assert hx.target_water_temp_celsius == 30.0

    def test_set_target_temperature_too_low(self):
        hx = HeatExchanger()
        assert hx.set_target_temperature(2.0) is False  # Below min

    def test_set_target_temperature_too_high(self):
        hx = HeatExchanger()
        assert hx.set_target_temperature(50.0) is False  # Above max

    def test_set_water_flow_valid(self):
        hx = HeatExchanger()
        assert hx.set_water_flow(10.0) is True
        assert hx.water_flow_l_min == 10.0

    def test_set_water_flow_exceeds_max(self):
        hx = HeatExchanger()
        assert hx.set_water_flow(25.0) is False  # Above 20 L/min max

    def test_update_readings(self):
        hx = HeatExchanger()
        hx.update_readings(
            water_inlet=10.0,
            water_outlet=15.0,
            blood_inlet=20.0,
            blood_outlet=18.0
        )
        assert hx.water_inlet_temp_celsius == 10.0
        assert hx.water_outlet_temp_celsius == 15.0
        assert hx.blood_inlet_temp_celsius == 20.0
        assert hx.blood_outlet_temp_celsius == 18.0

    def test_get_blood_water_gradient(self):
        hx = HeatExchanger()
        hx.blood_inlet_temp_celsius = 35.0
        hx.water_inlet_temp_celsius = 30.0
        assert hx.get_blood_water_gradient() == 5.0

    def test_gradient_alert(self):
        hx = HeatExchanger()
        alerts = []

        def callback(level, message):
            alerts.append((level, message))

        hx.register_alert_callback(callback)
        hx.update_readings(
            water_inlet=20.0,
            water_outlet=25.0,
            blood_inlet=35.0,  # 15°C gradient - exceeds limit
            blood_outlet=33.0
        )

        assert len(alerts) > 0
        assert any("gradient" in msg.lower() for _, msg in alerts)

    def test_get_status(self):
        hx = HeatExchanger()
        status = hx.get_status()
        assert "is_active" in status
        assert "water_flow_l_min" in status
        assert "blood_water_gradient_celsius" in status


class TestTemperatureController:
    """Tests for TemperatureController."""

    def test_initialization(self):
        tc = TemperatureController()
        assert tc.mode == TemperatureMode.NORMOTHERMIC
        assert tc.target_patient_temp_celsius == 37.0
        assert len(tc.monitoring_points) > 0

    def test_update_temperature(self):
        tc = TemperatureController()
        assert tc.update_temperature("arterial", 36.5) is True
        assert tc.monitoring_points["arterial"].current_temp_celsius == 36.5

    def test_update_temperature_invalid_point(self):
        tc = TemperatureController()
        assert tc.update_temperature("invalid_point", 36.5) is False

    def test_get_current_patient_temp(self):
        tc = TemperatureController()
        tc.update_temperature("nasopharyngeal", 36.0)
        tc.update_temperature("arterial", 37.0)
        # Should prefer nasopharyngeal
        assert tc.get_current_patient_temp() == 36.0

    def test_start_cooling(self):
        tc = TemperatureController()
        tc.update_temperature("arterial", 37.0)
        assert tc.start_cooling(28.0) is True
        assert tc.mode == TemperatureMode.MODERATE_HYPOTHERMIA
        assert tc.target_patient_temp_celsius == 28.0
        assert tc.heat_exchanger.is_active is True

    def test_start_cooling_invalid_target(self):
        tc = TemperatureController()
        tc.update_temperature("arterial", 37.0)
        # Can't cool to warmer temperature
        assert tc.start_cooling(38.0) is False
        # Can't cool below safe minimum
        assert tc.start_cooling(10.0) is False

    def test_start_rewarming(self):
        tc = TemperatureController()
        # Update nasopharyngeal (prioritized by get_current_patient_temp)
        tc.update_temperature("nasopharyngeal", 28.0)  # Hypothermic
        tc.update_temperature("arterial", 28.0)  # Hypothermic
        assert tc.start_rewarming(37.0) is True
        assert tc.mode == TemperatureMode.REWARMING
        assert tc.target_patient_temp_celsius == 37.0

    def test_start_rewarming_invalid_target(self):
        tc = TemperatureController()
        tc.update_temperature("arterial", 37.0)
        # Can't rewarm to cooler temperature
        assert tc.start_rewarming(35.0) is False
        # Can't rewarm above safe max
        assert tc.start_rewarming(40.0) is False

    def test_is_at_target(self):
        tc = TemperatureController()
        tc.target_patient_temp_celsius = 37.0
        # Update nasopharyngeal (prioritized by get_current_patient_temp)
        tc.update_temperature("nasopharyngeal", 37.2)
        assert tc.is_at_target(tolerance_celsius=0.5) is True
        tc.update_temperature("nasopharyngeal", 35.0)
        assert tc.is_at_target(tolerance_celsius=0.5) is False

    def test_check_gradients(self):
        tc = TemperatureController()
        tc.update_temperature("arterial", 35.0)
        tc.update_temperature("venous", 33.0)
        tc.update_temperature("nasopharyngeal", 34.0)
        tc.update_temperature("rectal", 35.5)

        gradients = tc.check_gradients()

        assert "arterial_venous" in gradients
        assert gradients["arterial_venous"] == 2.0

    def test_gradient_alert(self):
        tc = TemperatureController()
        alerts = []

        def callback(level, message):
            alerts.append((level, message))

        tc.register_alert_callback(callback)
        tc.update_temperature("arterial", 35.0)
        tc.update_temperature("venous", 22.0)  # 13°C gradient - exceeds limit

        tc.check_gradients()

        assert len(alerts) > 0
        assert any("gradient" in msg.lower() for _, msg in alerts)

    def test_temperature_rate_calculation(self):
        tc = TemperatureController()

        # Record several temperatures over time
        tc.temperature_history = [
            (time.time() - 120, 37.0),
            (time.time() - 60, 36.0),
            (time.time(), 35.0),
        ]

        rate = tc.get_temperature_rate()
        assert rate is not None
        assert rate < 0  # Cooling

    def test_cooling_mode_classification(self):
        tc = TemperatureController()
        tc.update_temperature("arterial", 37.0)

        tc.start_cooling(33.0)
        assert tc.mode == TemperatureMode.MILD_HYPOTHERMIA

        tc.start_cooling(30.0)
        assert tc.mode == TemperatureMode.MODERATE_HYPOTHERMIA

        tc.start_cooling(25.0)
        assert tc.mode == TemperatureMode.DEEP_HYPOTHERMIA

        tc.start_cooling(18.0)
        assert tc.mode == TemperatureMode.PROFOUND_HYPOTHERMIA

    def test_get_status(self):
        tc = TemperatureController()
        status = tc.get_status()

        assert "mode" in status
        assert "target_temp_celsius" in status
        assert "current_patient_temp_celsius" in status
        assert "heat_exchanger" in status
        assert "monitoring_points" in status
        assert "gradients" in status
