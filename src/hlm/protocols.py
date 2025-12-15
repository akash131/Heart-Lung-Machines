"""
Automated Protocols and Goal-Directed Perfusion System

Standardized protocols and automated assistance for perfusion management
improve patient outcomes and reduce variability.

This module implements:
- Pre-defined perfusion protocols
- Goal-directed perfusion automation
- Decision support algorithms
- Protocol compliance monitoring
- Automated recommendations
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Any
import time


class ProtocolType(Enum):
    """Types of perfusion protocols."""
    STANDARD_ADULT = auto()
    PEDIATRIC = auto()
    DEEP_HYPOTHERMIC = auto()
    MINIMIZED_CIRCUIT = auto()
    BLOODLESS = auto()
    CUSTOM = auto()


class GoalCategory(Enum):
    """Categories of perfusion goals."""
    OXYGEN_DELIVERY = auto()
    HEMODYNAMICS = auto()
    TEMPERATURE = auto()
    COAGULATION = auto()
    METABOLIC = auto()
    FLUID_BALANCE = auto()


class GoalStatus(Enum):
    """Status of a goal."""
    NOT_APPLICABLE = auto()
    MET = auto()
    NEAR_TARGET = auto()
    NOT_MET = auto()
    CRITICAL = auto()


class RecommendationPriority(Enum):
    """Priority levels for recommendations."""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    URGENT = auto()


@dataclass
class PerfusionGoal:
    """A single perfusion goal with targets and status."""
    name: str
    category: GoalCategory
    target_value: float
    current_value: float = 0.0
    unit: str = ""

    # Tolerance
    tolerance_percent: float = 10.0
    critical_low: float | None = None
    critical_high: float | None = None

    # Status
    status: GoalStatus = GoalStatus.NOT_APPLICABLE
    last_updated: float = field(default_factory=time.time)

    def update_value(self, value: float) -> GoalStatus:
        """Update current value and recalculate status."""
        self.current_value = value
        self.last_updated = time.time()
        self.status = self._calculate_status()
        return self.status

    def _calculate_status(self) -> GoalStatus:
        """Calculate goal status based on current value."""
        # Check critical bounds
        if self.critical_low is not None and self.current_value < self.critical_low:
            return GoalStatus.CRITICAL
        if self.critical_high is not None and self.current_value > self.critical_high:
            return GoalStatus.CRITICAL

        # Calculate deviation from target
        if self.target_value == 0:
            return GoalStatus.MET if self.current_value == 0 else GoalStatus.NOT_MET

        deviation_percent = abs(
            (self.current_value - self.target_value) / self.target_value * 100
        )

        if deviation_percent <= self.tolerance_percent:
            return GoalStatus.MET
        elif deviation_percent <= self.tolerance_percent * 2:
            return GoalStatus.NEAR_TARGET
        else:
            return GoalStatus.NOT_MET


@dataclass
class Recommendation:
    """A recommendation from the decision support system."""
    id: str
    priority: RecommendationPriority
    category: GoalCategory
    message: str
    rationale: str
    suggested_action: str
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False
    implemented: bool = False
    dismissed: bool = False


@dataclass
class ProtocolStep:
    """A step in a protocol."""
    step_number: int
    name: str
    description: str
    required: bool = True
    completed: bool = False
    completed_time: float | None = None
    completed_by: str = ""
    notes: str = ""

    # Validation
    validation_function: Callable[[], bool] | None = None


@dataclass
class ProtocolPhaseDefinition:
    """Definition of a protocol phase."""
    name: str
    description: str
    goals: list[str]  # Goal names
    steps: list[ProtocolStep]
    duration_estimate_min: float | None = None


class Protocol:
    """
    A complete perfusion protocol.

    Defines goals, phases, and steps for standardized perfusion.
    """

    def __init__(self,
                 name: str,
                 protocol_type: ProtocolType,
                 description: str = ""):
        self.name = name
        self.protocol_type = protocol_type
        self.description = description

        # Goals
        self.goals: dict[str, PerfusionGoal] = {}

        # Phases
        self.phases: list[ProtocolPhaseDefinition] = []
        self.current_phase_index: int = 0

        # Status
        self.is_active: bool = False
        self.start_time: float | None = None
        self.end_time: float | None = None

        # Compliance tracking
        self.compliance_checks: list[dict] = []

    def add_goal(self, goal: PerfusionGoal) -> None:
        """Add a goal to the protocol."""
        self.goals[goal.name] = goal

    def add_phase(self, phase: ProtocolPhaseDefinition) -> None:
        """Add a phase to the protocol."""
        self.phases.append(phase)

    def activate(self) -> None:
        """Activate the protocol."""
        self.is_active = True
        self.start_time = time.time()

    def deactivate(self) -> None:
        """Deactivate the protocol."""
        self.is_active = False
        self.end_time = time.time()

    def advance_phase(self) -> bool:
        """Advance to the next phase."""
        if self.current_phase_index < len(self.phases) - 1:
            self.current_phase_index += 1
            return True
        return False

    def get_current_phase(self) -> ProtocolPhaseDefinition | None:
        """Get the current phase."""
        if 0 <= self.current_phase_index < len(self.phases):
            return self.phases[self.current_phase_index]
        return None

    def update_goal(self, goal_name: str, value: float) -> GoalStatus | None:
        """Update a goal value."""
        if goal_name in self.goals:
            return self.goals[goal_name].update_value(value)
        return None

    def get_unmet_goals(self) -> list[PerfusionGoal]:
        """Get list of goals not currently met."""
        return [
            g for g in self.goals.values()
            if g.status in (GoalStatus.NOT_MET, GoalStatus.CRITICAL)
        ]

    def calculate_compliance(self) -> float:
        """Calculate overall protocol compliance percentage."""
        if not self.goals:
            return 100.0

        met_count = sum(
            1 for g in self.goals.values()
            if g.status in (GoalStatus.MET, GoalStatus.NEAR_TARGET)
        )
        return (met_count / len(self.goals)) * 100


class StandardAdultProtocol(Protocol):
    """Standard adult cardiopulmonary bypass protocol."""

    def __init__(self):
        super().__init__(
            name="Standard Adult CPB",
            protocol_type=ProtocolType.STANDARD_ADULT,
            description="Standard protocol for adult cardiac surgery"
        )
        self._initialize_goals()
        self._initialize_phases()

    def _initialize_goals(self) -> None:
        """Initialize standard goals."""
        goals = [
            PerfusionGoal(
                name="cardiac_index",
                category=GoalCategory.OXYGEN_DELIVERY,
                target_value=2.4,
                unit="L/min/m²",
                tolerance_percent=15,
                critical_low=1.8
            ),
            PerfusionGoal(
                name="do2_index",
                category=GoalCategory.OXYGEN_DELIVERY,
                target_value=300,
                unit="ml/min/m²",
                tolerance_percent=10,
                critical_low=270
            ),
            PerfusionGoal(
                name="svo2",
                category=GoalCategory.OXYGEN_DELIVERY,
                target_value=75,
                unit="%",
                tolerance_percent=10,
                critical_low=65
            ),
            PerfusionGoal(
                name="map",
                category=GoalCategory.HEMODYNAMICS,
                target_value=65,
                unit="mmHg",
                tolerance_percent=20,
                critical_low=50,
                critical_high=90
            ),
            PerfusionGoal(
                name="act",
                category=GoalCategory.COAGULATION,
                target_value=480,
                unit="seconds",
                tolerance_percent=0,
                critical_low=400
            ),
            PerfusionGoal(
                name="hemoglobin",
                category=GoalCategory.METABOLIC,
                target_value=8.0,
                unit="g/dL",
                tolerance_percent=25,
                critical_low=7.0
            ),
            PerfusionGoal(
                name="lactate",
                category=GoalCategory.METABOLIC,
                target_value=2.0,
                unit="mmol/L",
                tolerance_percent=50,
                critical_high=4.0
            ),
            PerfusionGoal(
                name="temperature",
                category=GoalCategory.TEMPERATURE,
                target_value=34.0,
                unit="°C",
                tolerance_percent=10,
                critical_low=20,
                critical_high=38
            ),
        ]

        for goal in goals:
            self.add_goal(goal)

    def _initialize_phases(self) -> None:
        """Initialize protocol phases."""
        phases = [
            ProtocolPhaseDefinition(
                name="Pre-Bypass",
                description="Preparation before initiating bypass",
                goals=["act"],
                steps=[
                    ProtocolStep(1, "Circuit priming", "Prime circuit with crystalloid"),
                    ProtocolStep(2, "Heparinization", "Administer heparin and verify ACT"),
                    ProtocolStep(3, "Cannulation", "Verify cannula placement"),
                ]
            ),
            ProtocolPhaseDefinition(
                name="Initiation",
                description="Starting cardiopulmonary bypass",
                goals=["cardiac_index", "do2_index"],
                steps=[
                    ProtocolStep(1, "Start bypass", "Begin arterial flow"),
                    ProtocolStep(2, "Achieve target flow", "Reach calculated flow rate"),
                    ProtocolStep(3, "Verify perfusion", "Confirm adequate SvO2"),
                ]
            ),
            ProtocolPhaseDefinition(
                name="Maintenance",
                description="Stable bypass period",
                goals=["cardiac_index", "do2_index", "svo2", "map", "hemoglobin", "lactate"],
                steps=[
                    ProtocolStep(1, "Monitor perfusion", "Maintain goal-directed targets"),
                    ProtocolStep(2, "Temperature management", "Control cooling/rewarming"),
                    ProtocolStep(3, "Blood management", "Optimize hemoglobin"),
                ]
            ),
            ProtocolPhaseDefinition(
                name="Weaning",
                description="Coming off bypass",
                goals=["temperature", "map"],
                steps=[
                    ProtocolStep(1, "Rewarm", "Achieve normothermia"),
                    ProtocolStep(2, "Reduce support", "Gradually decrease flow"),
                    ProtocolStep(3, "Separate", "Discontinue bypass"),
                ]
            ),
            ProtocolPhaseDefinition(
                name="Post-Bypass",
                description="After separation from bypass",
                goals=["act"],
                steps=[
                    ProtocolStep(1, "Protamine", "Reverse heparinization"),
                    ProtocolStep(2, "Verify hemostasis", "Confirm ACT normalization"),
                ]
            ),
        ]

        for phase in phases:
            self.add_phase(phase)


class GoalDirectedPerfusion:
    """
    Goal-directed perfusion automation system.

    Provides real-time recommendations based on current state
    relative to protocol goals.
    """

    def __init__(self):
        """Initialize goal-directed perfusion system."""
        self.is_active: bool = False
        self.protocol: Protocol | None = None

        # Recommendations
        self.active_recommendations: list[Recommendation] = []
        self.recommendation_history: list[Recommendation] = []
        self._recommendation_counter: int = 0

        # Decision rules
        self.rules: list[Callable[[dict], Recommendation | None]] = []
        self._initialize_rules()

        # Current state
        self.current_state: dict = {}

        # Callbacks
        self._recommendation_callbacks: list[Callable[[Recommendation], None]] = []

    def register_recommendation_callback(
        self, callback: Callable[[Recommendation], None]
    ) -> None:
        """Register callback for new recommendations."""
        self._recommendation_callbacks.append(callback)

    def _initialize_rules(self) -> None:
        """Initialize decision support rules."""

        def low_do2_rule(state: dict) -> Recommendation | None:
            do2 = state.get("do2_index", 0)
            if do2 < 270:
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.URGENT,
                    category=GoalCategory.OXYGEN_DELIVERY,
                    message=f"DO2 index critical: {do2:.0f} ml/min/m²",
                    rationale="DO2 < 270 ml/min/m² is associated with increased morbidity",
                    suggested_action="Increase pump flow or consider transfusion if Hb low"
                )
            elif do2 < 300:
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.HIGH,
                    category=GoalCategory.OXYGEN_DELIVERY,
                    message=f"DO2 index below target: {do2:.0f} ml/min/m²",
                    rationale="Target DO2 > 300 ml/min/m² for optimal outcomes",
                    suggested_action="Consider increasing flow rate"
                )
            return None

        def low_svo2_rule(state: dict) -> Recommendation | None:
            svo2 = state.get("svo2", 0)
            if svo2 < 65:
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.URGENT,
                    category=GoalCategory.OXYGEN_DELIVERY,
                    message=f"SvO2 critical: {svo2:.0f}%",
                    rationale="SvO2 < 65% indicates inadequate oxygen delivery",
                    suggested_action="Increase flow, check hemoglobin, reduce O2 demand"
                )
            elif svo2 < 70:
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.HIGH,
                    category=GoalCategory.OXYGEN_DELIVERY,
                    message=f"SvO2 below target: {svo2:.0f}%",
                    rationale="Target SvO2 > 70-75% during bypass",
                    suggested_action="Optimize oxygen delivery"
                )
            return None

        def low_act_rule(state: dict) -> Recommendation | None:
            act = state.get("act", 0)
            if act < 400 and state.get("on_bypass", False):
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.URGENT,
                    category=GoalCategory.COAGULATION,
                    message=f"ACT critically low: {act:.0f} seconds",
                    rationale="ACT < 400s during bypass risks clot formation",
                    suggested_action="Administer supplemental heparin immediately"
                )
            elif act < 480 and state.get("on_bypass", False):
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.HIGH,
                    category=GoalCategory.COAGULATION,
                    message=f"ACT below target: {act:.0f} seconds",
                    rationale="Target ACT > 480s during bypass",
                    suggested_action="Consider supplemental heparin"
                )
            return None

        def low_hemoglobin_rule(state: dict) -> Recommendation | None:
            hb = state.get("hemoglobin", 0)
            if hb < 7.0:
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.URGENT,
                    category=GoalCategory.METABOLIC,
                    message=f"Hemoglobin critical: {hb:.1f} g/dL",
                    rationale="Hb < 7 g/dL compromises oxygen delivery",
                    suggested_action="Transfuse packed red blood cells"
                )
            elif hb < 8.0 and state.get("do2_index", 300) < 300:
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.HIGH,
                    category=GoalCategory.METABOLIC,
                    message=f"Hemoglobin low with inadequate DO2: {hb:.1f} g/dL",
                    rationale="Low Hb contributing to inadequate oxygen delivery",
                    suggested_action="Consider transfusion or hemoconcentration"
                )
            return None

        def high_lactate_rule(state: dict) -> Recommendation | None:
            lactate = state.get("lactate", 0)
            if lactate > 4.0:
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.URGENT,
                    category=GoalCategory.METABOLIC,
                    message=f"Lactate critically elevated: {lactate:.1f} mmol/L",
                    rationale="Lactate > 4 indicates tissue hypoperfusion",
                    suggested_action="Increase flow, check DO2, consider vasodilator"
                )
            elif lactate > 3.0:
                return Recommendation(
                    id=self._generate_recommendation_id(),
                    priority=RecommendationPriority.HIGH,
                    category=GoalCategory.METABOLIC,
                    message=f"Lactate elevated: {lactate:.1f} mmol/L",
                    rationale="Rising lactate may indicate inadequate perfusion",
                    suggested_action="Optimize oxygen delivery and monitor trend"
                )
            return None

        self.rules = [
            low_do2_rule,
            low_svo2_rule,
            low_act_rule,
            low_hemoglobin_rule,
            high_lactate_rule,
        ]

    def _generate_recommendation_id(self) -> str:
        """Generate unique recommendation ID."""
        self._recommendation_counter += 1
        return f"REC-{int(time.time())}-{self._recommendation_counter:04d}"

    def activate(self, protocol: Protocol | None = None) -> None:
        """Activate goal-directed perfusion."""
        self.is_active = True
        self.protocol = protocol or StandardAdultProtocol()
        self.protocol.activate()

    def deactivate(self) -> None:
        """Deactivate goal-directed perfusion."""
        self.is_active = False
        if self.protocol:
            self.protocol.deactivate()

    def update_state(self, **kwargs) -> list[Recommendation]:
        """
        Update current state and generate recommendations.

        Args:
            **kwargs: Current parameter values

        Returns:
            List of new recommendations
        """
        self.current_state.update(kwargs)
        new_recommendations = []

        if not self.is_active:
            return new_recommendations

        # Update protocol goals
        if self.protocol:
            for key, value in kwargs.items():
                self.protocol.update_goal(key, value)

        # Run decision rules
        for rule in self.rules:
            rec = rule(self.current_state)
            if rec:
                # Check if similar recommendation already active
                existing = [r for r in self.active_recommendations
                           if r.category == rec.category and not r.acknowledged]
                if not existing:
                    self.active_recommendations.append(rec)
                    new_recommendations.append(rec)

                    # Notify callbacks
                    for callback in self._recommendation_callbacks:
                        callback(rec)

        return new_recommendations

    def acknowledge_recommendation(self, rec_id: str, user_id: str = "") -> bool:
        """Acknowledge a recommendation."""
        for rec in self.active_recommendations:
            if rec.id == rec_id:
                rec.acknowledged = True
                return True
        return False

    def implement_recommendation(self, rec_id: str, user_id: str = "") -> bool:
        """Mark a recommendation as implemented."""
        for rec in self.active_recommendations:
            if rec.id == rec_id:
                rec.implemented = True
                self.recommendation_history.append(rec)
                self.active_recommendations.remove(rec)
                return True
        return False

    def dismiss_recommendation(self, rec_id: str, user_id: str = "") -> bool:
        """Dismiss a recommendation."""
        for rec in self.active_recommendations:
            if rec.id == rec_id:
                rec.dismissed = True
                self.recommendation_history.append(rec)
                self.active_recommendations.remove(rec)
                return True
        return False

    def get_unmet_goals(self) -> list[PerfusionGoal]:
        """Get list of unmet goals."""
        if self.protocol:
            return self.protocol.get_unmet_goals()
        return []

    def get_compliance_score(self) -> float:
        """Get current protocol compliance score."""
        if self.protocol:
            return self.protocol.calculate_compliance()
        return 0.0

    def get_status(self) -> dict:
        """Get goal-directed perfusion status."""
        return {
            "is_active": self.is_active,
            "protocol": self.protocol.name if self.protocol else None,
            "current_phase": (
                self.protocol.get_current_phase().name
                if self.protocol and self.protocol.get_current_phase()
                else None
            ),
            "compliance_score": round(self.get_compliance_score(), 1),
            "goals": {
                name: {
                    "target": goal.target_value,
                    "current": round(goal.current_value, 2),
                    "status": goal.status.name,
                    "unit": goal.unit
                }
                for name, goal in (self.protocol.goals.items() if self.protocol else {})
            },
            "unmet_goals_count": len(self.get_unmet_goals()),
            "active_recommendations": len(self.active_recommendations),
            "recommendations": [
                {
                    "id": r.id,
                    "priority": r.priority.name,
                    "category": r.category.name,
                    "message": r.message,
                    "suggested_action": r.suggested_action
                }
                for r in self.active_recommendations
            ]
        }
