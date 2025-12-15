"""Tests for the main HeartLungMachineController."""

import pytest
from hlm.controller import (
    HeartLungMachineController,
    MachineState,
    PatientParameters,
)
from hlm.bypass_circuit import PumpType


class TestPatientParameters:
    """Tests for PatientParameters."""

    def test_calculate_bsa(self):
        params = PatientParameters(weight_kg=70, height_cm=170)
        bsa = params.calculate_bsa()
        # DuBois formula: 0.007184 * 70^0.425 * 170^0.725 ≈ 1.8
        assert 1.7 < bsa < 1.9

    def test_calculate_target_flow(self):
        params = PatientParameters(
            weight_kg=70,
            height_cm=170,
            target_flow_index_l_min_m2=2.4
        )
        flow = params.calculate_target_flow()
        # BSA ~1.8, flow index 2.4, so ~4320 ml/min
        assert 4000 < flow < 5000


class TestHeartLungMachineController:
    """Tests for HeartLungMachineController."""

    def test_initialization(self):
        controller = HeartLungMachineController()
        assert controller.state == MachineState.OFF
        assert controller.bypass_circuit is not None
        assert controller.bubble_system is not None
        assert controller.temperature_controller is not None
        assert controller.safety_monitor is not None

    def test_power_on(self):
        controller = HeartLungMachineController()
        assert controller.power_on() is True
        assert controller.state == MachineState.READY
        assert controller.safety_monitor.is_active is True

    def test_power_on_already_on(self):
        controller = HeartLungMachineController()
        controller.power_on()
        assert controller.power_on() is False

    def test_power_off(self):
        controller = HeartLungMachineController()
        controller.power_on()
        assert controller.power_off() is True
        assert controller.state == MachineState.OFF

    def test_power_off_during_bypass_fails(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass()
        assert controller.power_off() is False

    def test_set_patient_parameters(self):
        controller = HeartLungMachineController()
        controller.set_patient_parameters(
            weight_kg=80,
            height_cm=180,
            hematocrit_percent=40
        )
        assert controller.patient_params.weight_kg == 80
        assert controller.patient_params.height_cm == 180
        assert controller.patient_params.hematocrit_percent == 40

    def test_start_priming(self):
        controller = HeartLungMachineController()
        controller.power_on()
        assert controller.start_priming(1800) is True
        assert controller.state == MachineState.PRIMING
        assert controller.bubble_system.is_active is True

    def test_start_priming_wrong_state(self):
        controller = HeartLungMachineController()
        assert controller.start_priming() is False

    def test_complete_priming(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        assert controller.complete_priming() is True
        assert controller.state == MachineState.STANDBY

    def test_start_bypass(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        assert controller.start_bypass(4000) is True
        assert controller.state == MachineState.ON_BYPASS

    def test_start_bypass_auto_flow(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.set_patient_parameters(70, 170)
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass()  # No flow specified
        # Should use calculated flow
        assert controller.bypass_circuit.flow_params.target_flow_rate_ml_min > 0

    def test_start_bypass_wrong_state(self):
        controller = HeartLungMachineController()
        controller.power_on()
        assert controller.start_bypass(4000) is False

    def test_adjust_flow(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(3000)
        assert controller.adjust_flow(4000) is True

    def test_adjust_flow_wrong_state(self):
        controller = HeartLungMachineController()
        controller.power_on()
        assert controller.adjust_flow(4000) is False

    def test_start_cooling(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)
        assert controller.start_cooling(28.0) is True

    def test_start_cooling_wrong_state(self):
        controller = HeartLungMachineController()
        controller.power_on()
        assert controller.start_cooling(28.0) is False

    def test_start_rewarming(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)
        # Set hypothermic temperature first
        controller.temperature_controller.update_temperature("arterial", 28.0)
        assert controller.start_rewarming(37.0) is True

    def test_start_weaning(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)
        assert controller.start_weaning() is True
        assert controller.state == MachineState.WEANING

    def test_stop_bypass(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)
        assert controller.stop_bypass() is True
        assert controller.state == MachineState.STANDBY

    def test_emergency_stop(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)
        controller.emergency_stop()
        assert controller.state == MachineState.EMERGENCY

    def test_recover_from_emergency(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)
        controller.emergency_stop()

        # Clear critical alarms
        for alarm in controller.safety_monitor.get_critical_alarms():
            alarm.resolve()
        controller.safety_monitor.clear_resolved_alarms()

        assert controller.recover_from_emergency() is True
        assert controller.state == MachineState.STANDBY

    def test_recover_from_emergency_with_alarms_fails(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)
        controller.emergency_stop()
        # Critical alarms still active
        assert controller.recover_from_emergency() is False

    def test_update_sensors(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)

        controller.update_sensors(
            reservoir_level_ml=2000,
            flow_ml_min=4000,
            arterial_pressure=200,
            venous_pressure=-20,
            pre_oxy_pressure=180,
            post_oxy_pressure=160,
            bubble_readings={"arterial_line": 1.0},
            temperature_readings={"arterial": 37.0}
        )

        # Check that values propagated
        assert controller.bypass_circuit.flow_params.flow_rate_ml_min == 4000
        assert controller.bypass_circuit.venous_reservoir.current_level_ml == 2000

    def test_acknowledge_alarm(self):
        controller = HeartLungMachineController()
        controller.power_on()
        alarm = controller.safety_monitor.create_alarm(
            level=controller.safety_monitor.safety_limits["Blood Flow"].category,
            category=controller.safety_monitor.safety_limits["Blood Flow"].category,
            message="Test alarm"
        )
        assert controller.acknowledge_alarm(alarm.alarm_id, "user123") is True

    def test_get_bypass_time(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)

        # Time should be >= 0
        assert controller.get_bypass_time() >= 0

    def test_get_status(self):
        controller = HeartLungMachineController()
        controller.power_on()
        status = controller.get_status()

        assert "machine_state" in status
        assert "bypass_circuit" in status
        assert "bubble_system" in status
        assert "temperature" in status
        assert "safety" in status
        assert "patient" in status

    def test_get_event_log(self):
        controller = HeartLungMachineController()
        controller.power_on()

        log = controller.get_event_log()
        assert len(log) > 0
        assert any("POWER_ON" in event["type"] for event in log)

    def test_generate_procedure_report(self):
        controller = HeartLungMachineController()
        controller.power_on()
        controller.set_patient_parameters(70, 170)
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)
        controller.stop_bypass()

        report = controller.generate_procedure_report()

        assert "total_bypass_time_minutes" in report
        assert "patient_parameters" in report
        assert "pump_type" in report
        assert "alarm_summary" in report

    def test_status_callback(self):
        controller = HeartLungMachineController()
        statuses = []

        def callback(status):
            statuses.append(status)

        controller.register_status_callback(callback)
        controller.power_on()
        controller.start_priming()
        controller.complete_priming()
        controller.start_bypass(4000)

        controller.update_sensors(
            reservoir_level_ml=2000,
            flow_ml_min=4000,
            arterial_pressure=200,
            venous_pressure=-20,
            pre_oxy_pressure=180,
            post_oxy_pressure=160
        )

        assert len(statuses) > 0

    def test_centrifugal_pump(self):
        controller = HeartLungMachineController(pump_type=PumpType.CENTRIFUGAL)
        assert controller.pump_type == PumpType.CENTRIFUGAL
        assert controller.bypass_circuit.blood_pump.pump_type == PumpType.CENTRIFUGAL


class TestFullWorkflow:
    """Integration tests for complete bypass workflow."""

    def test_complete_bypass_procedure(self):
        """Test a complete bypass procedure workflow."""
        controller = HeartLungMachineController()

        # 1. Power on
        assert controller.power_on() is True
        assert controller.state == MachineState.READY

        # 2. Set patient data
        controller.set_patient_parameters(70, 170, 35)

        # 3. Prime circuit
        assert controller.start_priming(1800) is True
        assert controller.state == MachineState.PRIMING
        assert controller.complete_priming() is True
        assert controller.state == MachineState.STANDBY

        # 4. Start bypass
        assert controller.start_bypass() is True
        assert controller.state == MachineState.ON_BYPASS

        # 5. Cooling phase
        controller.temperature_controller.update_temperature("arterial", 37.0)
        assert controller.start_cooling(28.0) is True

        # 6. Update sensors during bypass
        controller.update_sensors(
            reservoir_level_ml=2000,
            flow_ml_min=4200,
            arterial_pressure=220,
            venous_pressure=-15,
            pre_oxy_pressure=200,
            post_oxy_pressure=180,
            temperature_readings={"arterial": 32.0}
        )

        # 7. Rewarming phase
        controller.temperature_controller.update_temperature("arterial", 28.0)
        assert controller.start_rewarming(37.0) is True

        # 8. Weaning
        assert controller.start_weaning() is True
        assert controller.state == MachineState.WEANING

        # 9. Stop bypass
        assert controller.stop_bypass() is True
        assert controller.state == MachineState.STANDBY

        # 10. Power off
        assert controller.power_off() is True
        assert controller.state == MachineState.OFF

        # Verify procedure report
        report = controller.generate_procedure_report()
        assert report["total_bypass_time_minutes"] >= 0
        assert len(controller.event_log) > 5
