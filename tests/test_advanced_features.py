"""Tests for advanced heart-lung machine features."""

import pytest
import time

from hlm.cardioplegia import (
    CardioplegiaDeliverySystem,
    CardioplegiaType,
    DeliveryRoute,
    CardioplegiaTemperature,
    DeliveryPhase,
    BloodCardioplegiaMixer,
)
from hlm.blood_gas import (
    BloodGasMonitor,
    BloodGasReading,
    BloodGasCalculator,
    PerfusionTargets,
)
from hlm.ultrafiltration import (
    HemoconcentratorSystem,
    UltrafiltrationMode,
)
from hlm.suction import (
    SuctionController,
    SuctionType,
    VentMode,
)
from hlm.anticoagulation import (
    AnticoagulationMonitor,
    ACTMethod,
    CoagulationStatus,
)
from hlm.data_logging import (
    DataLogger,
    DataCategory,
    EventSeverity,
)
from hlm.protocols import (
    GoalDirectedPerfusion,
    StandardAdultProtocol,
    GoalStatus,
    RecommendationPriority,
)


class TestCardioplegiaSystem:
    """Tests for cardioplegia delivery system."""

    def test_initialization(self):
        system = CardioplegiaDeliverySystem()
        assert system.is_active is False
        assert system.is_delivering is False

    def test_configure(self):
        system = CardioplegiaDeliverySystem()
        system.configure(
            cardioplegia_type=CardioplegiaType.BLOOD_4_1,
            delivery_route=DeliveryRoute.ANTEGRADE,
            temperature_mode=CardioplegiaTemperature.COLD,
            blood_ratio=4.0
        )
        assert system.cardioplegia_type == CardioplegiaType.BLOOD_4_1
        assert system.delivery_route == DeliveryRoute.ANTEGRADE

    def test_start_delivery(self):
        system = CardioplegiaDeliverySystem()
        system.activate()
        assert system.start_delivery(200, DeliveryPhase.INDUCTION) is True
        assert system.is_delivering is True

    def test_stop_delivery_records_dose(self):
        system = CardioplegiaDeliverySystem()
        system.activate()
        system.start_delivery(200, DeliveryPhase.INDUCTION)
        system.current_dose_volume_ml = 300
        dose = system.stop_delivery()
        assert dose is not None
        assert len(system.doses) == 1

    def test_needs_redose(self):
        system = CardioplegiaDeliverySystem()
        system.last_dose_time = time.time() - 1300  # 21+ minutes ago
        assert system.needs_redose() is True

    def test_mixer_ratio(self):
        mixer = BloodCardioplegiaMixer()
        mixer.set_ratio(4.0)
        mixer.set_total_flow(250)
        # 4:1 ratio means blood is 4/5, crystalloid is 1/5
        assert mixer.blood_flow_ml_min == pytest.approx(200, rel=0.01)
        assert mixer.crystalloid_flow_ml_min == pytest.approx(50, rel=0.01)


class TestBloodGasMonitor:
    """Tests for blood gas monitoring."""

    def test_initialization(self):
        monitor = BloodGasMonitor()
        assert monitor.is_active is False
        assert monitor.arterial is None

    def test_oxygen_content_calculation(self):
        # CaO2 = (1.34 × Hb × SaO2) + (0.003 × PaO2)
        cao2 = BloodGasCalculator.calculate_oxygen_content(
            po2_mmhg=200,
            so2_percent=99,
            hemoglobin_g_dl=10
        )
        # 1.34 * 10 * 0.99 + 0.003 * 200 = 13.266 + 0.6 = 13.866
        assert cao2 == pytest.approx(13.866, rel=0.01)

    def test_oxygen_delivery_calculation(self):
        do2 = BloodGasCalculator.calculate_oxygen_delivery(
            oxygen_content_ml_dl=15.0,
            flow_rate_ml_min=4000
        )
        # DO2 = 15 * 4 * 10 = 600 ml/min
        assert do2 == pytest.approx(600, rel=0.01)

    def test_update_arterial(self):
        monitor = BloodGasMonitor()
        monitor.activate()
        reading = BloodGasReading(
            po2_mmhg=200,
            so2_percent=99,
            hemoglobin_g_dl=10,
            ph=7.40,
            pco2_mmhg=40
        )
        monitor.set_flow_rate(4000)
        monitor.update_arterial(reading)
        assert monitor.arterial is not None
        assert monitor.oxygen_content.cao2_ml_dl > 0

    def test_perfusion_targets(self):
        targets = PerfusionTargets()
        assert targets.min_do2_ml_min_m2 == 270
        assert targets.target_svo2_percent == 75


class TestHemoconcentrator:
    """Tests for hemoconcentrator/ultrafiltration system."""

    def test_initialization(self):
        system = HemoconcentratorSystem()
        assert system.is_active is False
        assert system.mode == UltrafiltrationMode.OFF

    def test_prime_filter(self):
        system = HemoconcentratorSystem()
        assert system.prime_filter() is True
        assert system.filter_in_use is True

    def test_start_ultrafiltration(self):
        system = HemoconcentratorSystem()
        system.prime_filter()
        assert system.start_ultrafiltration(
            mode=UltrafiltrationMode.CUF,
            rate_ml_hr=500,
            blood_flow_ml_min=200
        ) is True
        assert system.is_active is True
        assert system.mode == UltrafiltrationMode.CUF

    def test_calculate_expected_hematocrit(self):
        system = HemoconcentratorSystem()
        # Start with 25% Hct, 5000ml blood volume, remove 1000ml
        # RBC volume = 0.25 * 5000 = 1250ml
        # New blood volume = 4000ml
        # New Hct = 1250/4000 = 31.25%
        expected = system.calculate_expected_hematocrit(25.0, 5000, 1000)
        assert expected == pytest.approx(31.25, rel=0.01)

    def test_zbuf_mode(self):
        system = HemoconcentratorSystem()
        system.prime_filter()
        system.start_ultrafiltration(
            mode=UltrafiltrationMode.ZBUF,
            rate_ml_hr=500,
            blood_flow_ml_min=200
        )
        assert system.replacement_controller.target_rate_ml_hr == 500


class TestSuctionController:
    """Tests for suction and vent management."""

    def test_initialization(self):
        controller = SuctionController()
        assert len(controller.channels) > 0
        assert "cardiotomy_1" in controller.channels

    def test_start_channel(self):
        controller = SuctionController()
        controller.activate()
        assert controller.start_channel("cardiotomy_1") is True
        assert controller.channels["cardiotomy_1"].is_active is True

    def test_set_vacuum(self):
        controller = SuctionController()
        assert controller.set_channel_vacuum("cardiotomy_1", -100) is True
        assert controller.channels["cardiotomy_1"].target_vacuum_mmhg == -100

    def test_clamp_detection(self):
        controller = SuctionController()
        controller.activate()
        controller.start_channel("cardiotomy_1")
        # High vacuum, low flow = occluded
        controller.update_channel("cardiotomy_1", -150, 5)
        assert controller.channels["cardiotomy_1"].is_occluded is True

    def test_cardiotomy_reservoir(self):
        controller = SuctionController()
        controller.update_reservoir_level(2000)
        assert controller.cardiotomy_reservoir.current_level_ml == 2000
        assert controller.cardiotomy_reservoir.is_level_high() is False


class TestAnticoagulationMonitor:
    """Tests for anticoagulation monitoring."""

    def test_initialization(self):
        monitor = AnticoagulationMonitor()
        assert monitor.status == CoagulationStatus.UNKNOWN

    def test_record_baseline(self):
        monitor = AnticoagulationMonitor()
        monitor.record_baseline_act(120)
        assert monitor.baseline_act == 120

    def test_record_act(self):
        monitor = AnticoagulationMonitor()
        monitor.activate()
        reading = monitor.record_act(520)
        assert reading.value_seconds == 520
        assert monitor.current_act == 520

    def test_calculate_initial_heparin(self):
        monitor = AnticoagulationMonitor()
        monitor.set_patient_weight(70)
        dose = monitor.calculate_initial_heparin_dose()
        # 70 kg * 400 U/kg = 28000 U
        assert dose == 28000

    def test_calculate_protamine(self):
        monitor = AnticoagulationMonitor()
        monitor.set_patient_weight(70)
        monitor.record_heparin_dose(30000)
        dose = monitor.calculate_protamine_dose()
        assert dose > 0

    def test_status_therapeutic(self):
        monitor = AnticoagulationMonitor()
        monitor.heparinization_time = time.time()
        monitor.record_act(520)
        assert monitor.status == CoagulationStatus.THERAPEUTIC


class TestDataLogger:
    """Tests for data logging system."""

    def test_initialization(self):
        logger = DataLogger()
        assert logger.is_recording is False

    def test_start_recording(self):
        logger = DataLogger()
        proc_id = logger.start_recording()
        assert logger.is_recording is True
        assert proc_id.startswith("PROC-")

    def test_log_data(self):
        logger = DataLogger()
        logger.start_recording()
        point = logger.log_data("arterial_flow", 4000)
        assert point is not None
        assert point.value == 4000

    def test_log_event(self):
        logger = DataLogger()
        logger.start_recording()
        event = logger.log_event(
            event_type="TEST",
            severity=EventSeverity.INFO,
            description="Test event",
            category=DataCategory.EVENT
        )
        assert event is not None
        assert len(logger.events) == 2  # Including PROCEDURE_START

    def test_phases(self):
        logger = DataLogger()
        logger.start_recording()
        phase = logger.start_phase("Bypass")
        assert phase.name == "Bypass"
        assert len(logger.phases) == 1

    def test_export_csv(self):
        logger = DataLogger()
        logger.start_recording()
        logger.log_data("arterial_flow", 4000)
        logger.log_data("arterial_flow", 4100)
        csv = logger.export_to_csv()
        assert "arterial_flow" in csv


class TestGoalDirectedPerfusion:
    """Tests for goal-directed perfusion system."""

    def test_initialization(self):
        gdp = GoalDirectedPerfusion()
        assert gdp.is_active is False

    def test_activate_with_protocol(self):
        gdp = GoalDirectedPerfusion()
        gdp.activate()
        assert gdp.is_active is True
        assert gdp.protocol is not None

    def test_update_state_generates_recommendations(self):
        gdp = GoalDirectedPerfusion()
        gdp.activate()
        # Set critical values
        recs = gdp.update_state(
            do2_index=250,  # Below critical threshold
            svo2=60,  # Critical
            on_bypass=True
        )
        assert len(recs) > 0
        assert any(r.priority == RecommendationPriority.URGENT for r in recs)

    def test_goal_status(self):
        gdp = GoalDirectedPerfusion()
        gdp.activate()
        gdp.update_state(do2_index=350)
        assert gdp.protocol.goals["do2_index"].status == GoalStatus.MET

    def test_compliance_score(self):
        gdp = GoalDirectedPerfusion()
        gdp.activate()
        # Update all goals to target values
        gdp.update_state(
            cardiac_index=2.4,
            do2_index=300,
            svo2=75,
            map=65,
            act=500,
            hemoglobin=8.0,
            lactate=1.5,
            temperature=34.0
        )
        score = gdp.get_compliance_score()
        assert score >= 80.0  # Most goals should be met


class TestStandardProtocol:
    """Tests for standard adult protocol."""

    def test_initialization(self):
        protocol = StandardAdultProtocol()
        assert protocol.name == "Standard Adult CPB"
        assert len(protocol.goals) > 0
        assert len(protocol.phases) > 0

    def test_phases(self):
        protocol = StandardAdultProtocol()
        phase_names = [p.name for p in protocol.phases]
        assert "Pre-Bypass" in phase_names
        assert "Maintenance" in phase_names
        assert "Weaning" in phase_names

    def test_goal_update(self):
        protocol = StandardAdultProtocol()
        protocol.activate()
        status = protocol.update_goal("do2_index", 350)
        assert status == GoalStatus.MET

    def test_unmet_goals(self):
        protocol = StandardAdultProtocol()
        protocol.activate()
        protocol.update_goal("do2_index", 200)  # Below critical
        unmet = protocol.get_unmet_goals()
        assert len(unmet) > 0
        assert any(g.name == "do2_index" for g in unmet)


class TestIntegration:
    """Integration tests for advanced features."""

    def test_complete_bypass_with_advanced_features(self):
        """Test integration of advanced features in a bypass scenario."""
        # Initialize systems
        blood_gas = BloodGasMonitor()
        anticoag = AnticoagulationMonitor()
        cardioplegia = CardioplegiaDeliverySystem()
        uf = HemoconcentratorSystem()
        suction = SuctionController()
        logger = DataLogger()
        gdp = GoalDirectedPerfusion()

        # Setup
        blood_gas.activate()
        blood_gas.set_patient_data(bsa_m2=1.8)
        anticoag.set_patient_weight(70)
        anticoag.activate()
        cardioplegia.activate()
        uf.prime_filter()
        suction.activate()
        logger.start_recording()
        gdp.activate()

        # Pre-bypass
        logger.start_phase("Pre-Bypass")
        anticoag.record_baseline_act(120)
        anticoag.record_heparin_dose(28000)
        anticoag.record_act(520)
        assert anticoag.status == CoagulationStatus.THERAPEUTIC

        # On bypass
        logger.start_phase("Bypass")
        blood_gas.set_flow_rate(4000)
        blood_gas.update_arterial(BloodGasReading(
            po2_mmhg=200,
            so2_percent=99,
            hemoglobin_g_dl=9,
            ph=7.40,
            pco2_mmhg=40,
            lactate_mmol_l=1.5
        ))
        blood_gas.update_venous(BloodGasReading(
            po2_mmhg=40,
            so2_percent=70
        ))

        # Log data
        logger.log_data("arterial_flow", 4000)
        logger.log_data("svo2", 70)

        # Goal-directed update
        gdp.update_state(
            cardiac_index=blood_gas.perfusion.cardiac_index_l_min_m2,
            do2_index=blood_gas.perfusion.do2_ml_min_m2,
            svo2=70,
            hemoglobin=9,
            lactate=1.5,
            on_bypass=True
        )

        # Cardioplegia
        cardioplegia.configure(
            CardioplegiaType.BLOOD_4_1,
            DeliveryRoute.ANTEGRADE,
            CardioplegiaTemperature.COLD
        )
        cardioplegia.start_delivery(200, DeliveryPhase.INDUCTION)
        cardioplegia.current_dose_volume_ml = 500
        cardioplegia.stop_delivery()
        assert len(cardioplegia.doses) == 1

        # Ultrafiltration
        uf.start_ultrafiltration(UltrafiltrationMode.CUF, 500, 200)
        uf.update_readings(150, 100, 500, 28)

        # Suction
        suction.start_channel("cardiotomy_1")
        suction.update_channel("cardiotomy_1", -80, 100)

        # Verify logging
        logger.end_phase()
        assert len(logger.events) > 0
        assert logger.data_buffer.get_statistics("arterial_flow") is not None

        # Generate report
        report = logger.generate_summary_report()
        assert report["timing"]["duration_minutes"] >= 0
