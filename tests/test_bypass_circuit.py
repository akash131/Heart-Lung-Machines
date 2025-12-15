"""Tests for the bypass circuit module."""

import pytest
from hlm.bypass_circuit import (
    BypassCircuit,
    PumpType,
    CircuitState,
    FlowParameters,
    PressureReadings,
    VenousReservoir,
    BloodPump,
    Oxygenator,
    ArterialFilter,
)


class TestFlowParameters:
    """Tests for FlowParameters dataclass."""

    def test_default_values(self):
        params = FlowParameters()
        assert params.flow_rate_ml_min == 0.0
        assert params.target_flow_rate_ml_min == 0.0
        assert params.max_flow_rate_ml_min == 7000.0

    def test_validate_within_range(self):
        params = FlowParameters(flow_rate_ml_min=3000, target_flow_rate_ml_min=4000)
        assert params.validate() is True

    def test_validate_exceeds_max(self):
        params = FlowParameters(flow_rate_ml_min=8000)
        assert params.validate() is False

    def test_validate_negative(self):
        params = FlowParameters(flow_rate_ml_min=-100)
        assert params.validate() is False


class TestPressureReadings:
    """Tests for PressureReadings dataclass."""

    def test_is_safe_within_limits(self):
        pressures = PressureReadings(
            arterial_line_mmhg=250,
            transmembrane_pressure_mmhg=300
        )
        assert pressures.is_safe() is True

    def test_is_safe_high_arterial(self):
        pressures = PressureReadings(arterial_line_mmhg=400)
        assert pressures.is_safe() is False

    def test_is_safe_high_transmembrane(self):
        pressures = PressureReadings(transmembrane_pressure_mmhg=600)
        assert pressures.is_safe() is False

    def test_calculate_transmembrane(self):
        pressures = PressureReadings(
            pre_oxygenator_mmhg=200,
            post_oxygenator_mmhg=150
        )
        result = pressures.calculate_transmembrane()
        assert result == 50
        assert pressures.transmembrane_pressure_mmhg == 50


class TestVenousReservoir:
    """Tests for VenousReservoir component."""

    def test_update_level(self):
        reservoir = VenousReservoir(name="test")
        reservoir.update_level(2000)
        assert reservoir.current_level_ml == 2000

    def test_update_level_clamps_to_capacity(self):
        reservoir = VenousReservoir(name="test", capacity_ml=3000)
        reservoir.update_level(5000)
        assert reservoir.current_level_ml == 3000

    def test_update_level_clamps_negative(self):
        reservoir = VenousReservoir(name="test")
        reservoir.update_level(-100)
        assert reservoir.current_level_ml == 0

    def test_is_level_safe(self):
        reservoir = VenousReservoir(name="test", critical_level_alarm_ml=200)
        reservoir.update_level(300)
        assert reservoir.is_level_safe() is True
        reservoir.update_level(100)
        assert reservoir.is_level_safe() is False

    def test_is_level_low(self):
        reservoir = VenousReservoir(name="test", low_level_alarm_ml=400)
        reservoir.update_level(500)
        assert reservoir.is_level_low() is False
        reservoir.update_level(300)
        assert reservoir.is_level_low() is True

    def test_get_fill_percentage(self):
        reservoir = VenousReservoir(name="test", capacity_ml=1000)
        reservoir.update_level(250)
        assert reservoir.get_fill_percentage() == 25.0


class TestBloodPump:
    """Tests for BloodPump component."""

    def test_roller_pump_defaults(self):
        pump = BloodPump(name="test", pump_type=PumpType.ROLLER)
        assert pump.max_rpm == 200.0
        assert pump.flow_per_revolution_ml == 35.0

    def test_centrifugal_pump_defaults(self):
        pump = BloodPump(name="test", pump_type=PumpType.CENTRIFUGAL)
        assert pump.max_rpm == 5000.0

    def test_set_rpm_valid(self):
        pump = BloodPump(name="test", pump_type=PumpType.ROLLER)
        assert pump.set_rpm(100) is True
        assert pump.rpm == 100

    def test_set_rpm_exceeds_max(self):
        pump = BloodPump(name="test", pump_type=PumpType.ROLLER)
        assert pump.set_rpm(300) is False

    def test_calculate_flow_rate_roller(self):
        pump = BloodPump(name="test", pump_type=PumpType.ROLLER)
        pump.is_active = True
        pump.set_rpm(100)
        flow = pump.calculate_flow_rate()
        assert flow == 100 * 35.0  # rpm * flow_per_revolution

    def test_calculate_flow_rate_inactive(self):
        pump = BloodPump(name="test")
        pump.set_rpm(100)
        assert pump.calculate_flow_rate() == 0.0

    def test_emergency_stop(self):
        pump = BloodPump(name="test")
        pump.is_active = True
        pump.set_rpm(100)
        pump.emergency_stop()
        assert pump.rpm == 0.0
        assert pump.is_active is False


class TestOxygenator:
    """Tests for Oxygenator component."""

    def test_set_gas_flow(self):
        oxy = Oxygenator(name="test")
        oxy.set_gas_flow(2.0, 3.0)
        assert oxy.oxygen_flow_l_min == 2.0
        assert oxy.sweep_gas_flow_l_min == 3.0

    def test_set_fio2_valid(self):
        oxy = Oxygenator(name="test")
        assert oxy.set_fio2(50) is True
        assert oxy.fio2_percent == 50

    def test_set_fio2_invalid(self):
        oxy = Oxygenator(name="test")
        assert oxy.set_fio2(10) is False  # Below 21%
        assert oxy.set_fio2(110) is False  # Above 100%

    def test_calculate_gas_blood_ratio(self):
        oxy = Oxygenator(name="test")
        oxy.oxygen_flow_l_min = 2.0
        oxy.sweep_gas_flow_l_min = 3.0
        ratio = oxy.calculate_gas_blood_ratio(5000)  # 5 L/min blood flow
        assert ratio == 1.0  # 5 L gas / 5 L blood

    def test_is_efficiency_acceptable(self):
        oxy = Oxygenator(name="test")
        assert oxy.is_efficiency_acceptable() is True
        oxy.oxygen_transfer_efficiency = 0.5
        assert oxy.is_efficiency_acceptable() is False


class TestArterialFilter:
    """Tests for ArterialFilter component."""

    def test_update_pressure_drop(self):
        filt = ArterialFilter(name="test")
        filt.update_pressure_drop(100, 80)
        assert filt.current_pressure_drop_mmhg == 20

    def test_is_filter_blocked(self):
        filt = ArterialFilter(name="test", max_pressure_drop_mmhg=50)
        filt.current_pressure_drop_mmhg = 30
        assert filt.is_filter_blocked() is False
        filt.current_pressure_drop_mmhg = 60
        assert filt.is_filter_blocked() is True


class TestBypassCircuit:
    """Tests for the main BypassCircuit class."""

    def test_initial_state(self):
        circuit = BypassCircuit()
        assert circuit.state == CircuitState.OFF
        assert circuit.is_primed is False

    def test_start_priming(self):
        circuit = BypassCircuit()
        assert circuit.start_priming(1800) is True
        assert circuit.state == CircuitState.PRIMING
        assert circuit.priming_volume_ml == 1800
        assert circuit.venous_reservoir.current_level_ml == 1800

    def test_start_priming_wrong_state(self):
        circuit = BypassCircuit()
        circuit.state = CircuitState.RUNNING
        assert circuit.start_priming() is False

    def test_complete_priming(self):
        circuit = BypassCircuit()
        circuit.start_priming(1500)
        assert circuit.complete_priming() is True
        assert circuit.state == CircuitState.STANDBY
        assert circuit.is_primed is True

    def test_complete_priming_insufficient_volume(self):
        circuit = BypassCircuit()
        circuit.start_priming(500)  # Too low
        circuit.venous_reservoir.update_level(500)
        assert circuit.complete_priming() is False

    def test_start_bypass(self):
        circuit = BypassCircuit()
        circuit.start_priming(1800)
        circuit.complete_priming()
        assert circuit.start_bypass(4000) is True
        assert circuit.state == CircuitState.RUNNING
        assert circuit.flow_params.target_flow_rate_ml_min == 4000

    def test_start_bypass_not_primed(self):
        circuit = BypassCircuit()
        circuit.state = CircuitState.STANDBY
        assert circuit.start_bypass(4000) is False

    def test_update_flow_rate(self):
        circuit = BypassCircuit()
        circuit.start_priming()
        circuit.complete_priming()
        circuit.start_bypass(3000)
        assert circuit.update_flow_rate(4000) is True
        assert circuit.flow_params.target_flow_rate_ml_min == 4000

    def test_start_weaning(self):
        circuit = BypassCircuit()
        circuit.start_priming()
        circuit.complete_priming()
        circuit.start_bypass(4000)
        assert circuit.start_weaning() is True
        assert circuit.state == CircuitState.WEANING

    def test_stop_bypass(self):
        circuit = BypassCircuit()
        circuit.start_priming()
        circuit.complete_priming()
        circuit.start_bypass(4000)
        assert circuit.stop_bypass() is True
        assert circuit.state == CircuitState.STANDBY

    def test_emergency_stop(self):
        circuit = BypassCircuit()
        circuit.start_priming()
        circuit.complete_priming()
        circuit.start_bypass(4000)
        circuit.emergency_stop()
        assert circuit.state == CircuitState.EMERGENCY_STOP
        assert circuit.blood_pump.rpm == 0

    def test_get_status(self):
        circuit = BypassCircuit()
        status = circuit.get_status()
        assert "state" in status
        assert "reservoir" in status
        assert "flow" in status
        assert "pressures" in status
        assert "oxygenator" in status
        assert "filter" in status

    def test_alarm_callback(self):
        circuit = BypassCircuit()
        alarms = []

        def callback(level, message):
            alarms.append((level, message))

        circuit.register_alarm_callback(callback)
        circuit.start_priming()
        circuit.complete_priming()
        circuit.start_bypass(4000)

        # Trigger low reservoir alarm
        circuit.update_readings(
            reservoir_level_ml=100,  # Critical level
            actual_flow_ml_min=4000,
            arterial_pressure=200,
            venous_pressure=-20,
            pre_oxy_pressure=180,
            post_oxy_pressure=160
        )

        assert len(alarms) > 0
        assert any("reservoir" in msg.lower() for _, msg in alarms)
