"""
Configuration and Audit System

Configuration management and audit trails are essential for:
- Regulatory compliance (FDA 21 CFR Part 11, IEC 62304)
- Quality assurance
- Incident investigation
- System customization

This module implements:
- System configuration management
- User/role management
- Audit trail logging
- Configuration validation
- Version control
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable
import time
import json
import hashlib
from datetime import datetime


class UserRole(Enum):
    """User roles with different permission levels."""
    VIEWER = auto()          # View only
    OPERATOR = auto()        # Normal operation
    PERFUSIONIST = auto()    # Full clinical use
    SUPERVISOR = auto()      # Supervise and approve
    TECHNICIAN = auto()      # Maintenance and calibration
    ADMINISTRATOR = auto()   # Full system access


class AuditEventType(Enum):
    """Types of auditable events."""
    LOGIN = auto()
    LOGOUT = auto()
    CONFIG_CHANGE = auto()
    PARAMETER_CHANGE = auto()
    ALARM_ACKNOWLEDGE = auto()
    PROCEDURE_START = auto()
    PROCEDURE_END = auto()
    CALIBRATION = auto()
    MAINTENANCE = auto()
    ERROR = auto()
    SECURITY = auto()


class ConfigCategory(Enum):
    """Categories of configuration settings."""
    SYSTEM = auto()
    ALARM = auto()
    DISPLAY = auto()
    COMMUNICATION = auto()
    PROTOCOL = auto()
    SAFETY = auto()
    USER = auto()


@dataclass
class User:
    """System user."""
    user_id: str
    username: str
    role: UserRole
    full_name: str = ""
    email: str = ""
    department: str = ""
    is_active: bool = True
    password_hash: str = ""
    last_login: float | None = None
    created_at: float = field(default_factory=time.time)
    created_by: str = ""

    def check_password(self, password: str) -> bool:
        """Verify password."""
        hashed = hashlib.sha256(password.encode()).hexdigest()
        return hashed == self.password_hash

    def set_password(self, password: str) -> None:
        """Set password (stores hash only)."""
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()

    def has_permission(self, required_role: UserRole) -> bool:
        """Check if user has required permission level."""
        role_hierarchy = {
            UserRole.VIEWER: 1,
            UserRole.OPERATOR: 2,
            UserRole.PERFUSIONIST: 3,
            UserRole.SUPERVISOR: 4,
            UserRole.TECHNICIAN: 4,
            UserRole.ADMINISTRATOR: 5
        }
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(required_role, 5)


@dataclass
class AuditEntry:
    """An audit trail entry."""
    entry_id: str
    timestamp: float = field(default_factory=time.time)
    event_type: AuditEventType = AuditEventType.CONFIG_CHANGE
    user_id: str = ""
    username: str = ""
    description: str = ""
    old_value: str = ""
    new_value: str = ""
    ip_address: str = ""
    session_id: str = ""
    procedure_id: str = ""
    is_successful: bool = True
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "event_type": self.event_type.name,
            "user_id": self.user_id,
            "username": self.username,
            "description": self.description,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "is_successful": self.is_successful,
            "details": self.details
        }


@dataclass
class ConfigSetting:
    """A configuration setting."""
    key: str
    value: Any
    category: ConfigCategory
    description: str = ""
    unit: str = ""
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list | None = None
    requires_restart: bool = False
    requires_admin: bool = False
    is_read_only: bool = False
    last_modified: float = field(default_factory=time.time)
    modified_by: str = ""

    def validate(self, new_value: Any) -> tuple[bool, str]:
        """
        Validate a new value for this setting.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.is_read_only:
            return (False, "Setting is read-only")

        if self.allowed_values and new_value not in self.allowed_values:
            return (False, f"Value must be one of: {self.allowed_values}")

        if self.min_value is not None and new_value < self.min_value:
            return (False, f"Value must be >= {self.min_value}")

        if self.max_value is not None and new_value > self.max_value:
            return (False, f"Value must be <= {self.max_value}")

        return (True, "")


class AuditTrail:
    """
    Audit trail management system.

    Provides tamper-evident logging of all system activities.
    """

    def __init__(self):
        """Initialize audit trail."""
        self.entries: list[AuditEntry] = []
        self._entry_counter: int = 0
        self._last_hash: str = ""

    def _generate_entry_id(self) -> str:
        """Generate unique entry ID."""
        self._entry_counter += 1
        return f"AUD-{int(time.time())}-{self._entry_counter:06d}"

    def _calculate_hash(self, entry: AuditEntry) -> str:
        """Calculate hash for entry integrity."""
        data = f"{entry.entry_id}{entry.timestamp}{entry.event_type.name}"
        data += f"{entry.user_id}{entry.description}{self._last_hash}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def log(self,
            event_type: AuditEventType,
            description: str,
            user_id: str = "",
            username: str = "",
            old_value: str = "",
            new_value: str = "",
            details: dict | None = None,
            is_successful: bool = True) -> AuditEntry:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            description: Event description
            user_id: User who triggered event
            username: Username
            old_value: Previous value (for changes)
            new_value: New value (for changes)
            details: Additional details
            is_successful: Whether event was successful

        Returns:
            Created audit entry
        """
        entry = AuditEntry(
            entry_id=self._generate_entry_id(),
            event_type=event_type,
            user_id=user_id,
            username=username,
            description=description,
            old_value=old_value,
            new_value=new_value,
            is_successful=is_successful,
            details=details or {}
        )

        # Add integrity hash
        entry.details["integrity_hash"] = self._calculate_hash(entry)
        self._last_hash = entry.details["integrity_hash"]

        self.entries.append(entry)
        return entry

    def get_entries(self,
                    start_time: float | None = None,
                    end_time: float | None = None,
                    event_type: AuditEventType | None = None,
                    user_id: str | None = None) -> list[AuditEntry]:
        """
        Get audit entries with filters.

        Args:
            start_time: Start of time range
            end_time: End of time range
            event_type: Filter by event type
            user_id: Filter by user

        Returns:
            Filtered list of entries
        """
        filtered = self.entries

        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]

        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]

        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]

        if user_id:
            filtered = [e for e in filtered if e.user_id == user_id]

        return filtered

    def export_to_json(self) -> str:
        """Export audit trail to JSON."""
        return json.dumps([e.to_dict() for e in self.entries], indent=2)

    def verify_integrity(self) -> tuple[bool, list[str]]:
        """
        Verify audit trail integrity.

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []
        prev_hash = ""

        for entry in self.entries:
            # Recalculate hash
            self._last_hash = prev_hash
            expected_hash = self._calculate_hash(entry)
            actual_hash = entry.details.get("integrity_hash", "")

            if expected_hash != actual_hash:
                issues.append(f"Integrity violation at entry {entry.entry_id}")

            prev_hash = actual_hash

        return (len(issues) == 0, issues)


class UserManager:
    """
    User and session management.
    """

    def __init__(self, audit_trail: AuditTrail):
        """Initialize user manager."""
        self.users: dict[str, User] = {}
        self.active_sessions: dict[str, dict] = {}
        self.audit_trail = audit_trail

        # Create default admin user
        self._create_default_admin()

    def _create_default_admin(self) -> None:
        """Create default administrator account."""
        admin = User(
            user_id="admin",
            username="admin",
            role=UserRole.ADMINISTRATOR,
            full_name="System Administrator"
        )
        admin.set_password("admin")  # Should be changed on first login
        self.users["admin"] = admin

    def create_user(self,
                    username: str,
                    password: str,
                    role: UserRole,
                    full_name: str = "",
                    created_by: str = "") -> User:
        """
        Create a new user.

        Args:
            username: Username
            password: Initial password
            role: User role
            full_name: Full name
            created_by: Admin who created the user

        Returns:
            Created user
        """
        user_id = f"USR-{int(time.time())}"
        user = User(
            user_id=user_id,
            username=username,
            role=role,
            full_name=full_name,
            created_by=created_by
        )
        user.set_password(password)

        self.users[user_id] = user

        self.audit_trail.log(
            event_type=AuditEventType.SECURITY,
            description=f"User created: {username}",
            user_id=created_by,
            new_value=f"role={role.name}"
        )

        return user

    def authenticate(self,
                     username: str,
                     password: str) -> tuple[bool, User | None, str]:
        """
        Authenticate a user.

        Args:
            username: Username
            password: Password

        Returns:
            Tuple of (success, user, session_id)
        """
        # Find user
        user = None
        for u in self.users.values():
            if u.username == username:
                user = u
                break

        if user is None:
            self.audit_trail.log(
                event_type=AuditEventType.LOGIN,
                description=f"Login failed: user not found",
                username=username,
                is_successful=False
            )
            return (False, None, "")

        if not user.is_active:
            self.audit_trail.log(
                event_type=AuditEventType.LOGIN,
                description=f"Login failed: user inactive",
                user_id=user.user_id,
                username=username,
                is_successful=False
            )
            return (False, None, "")

        if not user.check_password(password):
            self.audit_trail.log(
                event_type=AuditEventType.LOGIN,
                description=f"Login failed: invalid password",
                user_id=user.user_id,
                username=username,
                is_successful=False
            )
            return (False, None, "")

        # Create session
        session_id = f"SES-{int(time.time())}-{user.user_id}"
        self.active_sessions[session_id] = {
            "user_id": user.user_id,
            "username": username,
            "role": user.role,
            "login_time": time.time()
        }

        user.last_login = time.time()

        self.audit_trail.log(
            event_type=AuditEventType.LOGIN,
            description=f"User logged in",
            user_id=user.user_id,
            username=username,
            details={"session_id": session_id}
        )

        return (True, user, session_id)

    def logout(self, session_id: str) -> bool:
        """Log out a session."""
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions.pop(session_id)

        self.audit_trail.log(
            event_type=AuditEventType.LOGOUT,
            description=f"User logged out",
            user_id=session["user_id"],
            username=session["username"],
            details={"session_id": session_id}
        )

        return True

    def get_session_user(self, session_id: str) -> User | None:
        """Get user for a session."""
        if session_id not in self.active_sessions:
            return None

        user_id = self.active_sessions[session_id]["user_id"]
        return self.users.get(user_id)


class ConfigurationManager:
    """
    System configuration management.
    """

    def __init__(self, audit_trail: AuditTrail):
        """Initialize configuration manager."""
        self.settings: dict[str, ConfigSetting] = {}
        self.audit_trail = audit_trail

        # Version tracking
        self.config_version: int = 1
        self.last_modified: float = time.time()

        # Initialize default settings
        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Initialize default configuration settings."""
        defaults = [
            # System settings
            ConfigSetting(
                key="system.language",
                value="en",
                category=ConfigCategory.SYSTEM,
                description="System language",
                allowed_values=["en", "es", "fr", "de", "zh", "ja"]
            ),
            ConfigSetting(
                key="system.date_format",
                value="YYYY-MM-DD",
                category=ConfigCategory.SYSTEM,
                description="Date format",
                allowed_values=["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"]
            ),
            ConfigSetting(
                key="system.time_format",
                value="24h",
                category=ConfigCategory.SYSTEM,
                description="Time format",
                allowed_values=["24h", "12h"]
            ),
            ConfigSetting(
                key="system.temperature_unit",
                value="celsius",
                category=ConfigCategory.SYSTEM,
                description="Temperature unit",
                allowed_values=["celsius", "fahrenheit"]
            ),

            # Alarm settings
            ConfigSetting(
                key="alarm.audio_enabled",
                value=True,
                category=ConfigCategory.ALARM,
                description="Enable alarm audio"
            ),
            ConfigSetting(
                key="alarm.audio_volume",
                value=80,
                category=ConfigCategory.ALARM,
                description="Alarm audio volume",
                unit="%",
                min_value=0,
                max_value=100
            ),
            ConfigSetting(
                key="alarm.silence_duration",
                value=120,
                category=ConfigCategory.ALARM,
                description="Alarm silence duration",
                unit="seconds",
                min_value=30,
                max_value=300
            ),
            ConfigSetting(
                key="alarm.escalation_time",
                value=60,
                category=ConfigCategory.ALARM,
                description="Time before alarm escalation",
                unit="seconds",
                min_value=30,
                max_value=300
            ),

            # Safety settings
            ConfigSetting(
                key="safety.min_flow_rate",
                value=1000,
                category=ConfigCategory.SAFETY,
                description="Minimum safe flow rate",
                unit="ml/min",
                min_value=0,
                max_value=3000,
                requires_admin=True
            ),
            ConfigSetting(
                key="safety.max_arterial_pressure",
                value=350,
                category=ConfigCategory.SAFETY,
                description="Maximum arterial pressure alarm",
                unit="mmHg",
                min_value=200,
                max_value=500,
                requires_admin=True
            ),
            ConfigSetting(
                key="safety.min_reservoir_level",
                value=200,
                category=ConfigCategory.SAFETY,
                description="Minimum reservoir level alarm",
                unit="ml",
                min_value=100,
                max_value=500,
                requires_admin=True
            ),
            ConfigSetting(
                key="safety.min_act",
                value=480,
                category=ConfigCategory.SAFETY,
                description="Minimum ACT for bypass",
                unit="seconds",
                min_value=400,
                max_value=600,
                requires_admin=True
            ),

            # Display settings
            ConfigSetting(
                key="display.brightness",
                value=100,
                category=ConfigCategory.DISPLAY,
                description="Display brightness",
                unit="%",
                min_value=20,
                max_value=100
            ),
            ConfigSetting(
                key="display.trend_window",
                value=60,
                category=ConfigCategory.DISPLAY,
                description="Trend display window",
                unit="minutes",
                min_value=15,
                max_value=240
            ),
            ConfigSetting(
                key="display.auto_dimming",
                value=False,
                category=ConfigCategory.DISPLAY,
                description="Enable auto-dimming"
            ),

            # Communication settings
            ConfigSetting(
                key="communication.hl7_enabled",
                value=False,
                category=ConfigCategory.COMMUNICATION,
                description="Enable HL7 interface"
            ),
            ConfigSetting(
                key="communication.hl7_host",
                value="localhost",
                category=ConfigCategory.COMMUNICATION,
                description="HL7 server host"
            ),
            ConfigSetting(
                key="communication.hl7_port",
                value=2575,
                category=ConfigCategory.COMMUNICATION,
                description="HL7 server port",
                min_value=1,
                max_value=65535
            ),

            # Protocol settings
            ConfigSetting(
                key="protocol.default_protocol",
                value="standard_adult",
                category=ConfigCategory.PROTOCOL,
                description="Default perfusion protocol",
                allowed_values=["standard_adult", "pediatric", "deep_hypothermic", "minimized"]
            ),
            ConfigSetting(
                key="protocol.goal_directed_enabled",
                value=True,
                category=ConfigCategory.PROTOCOL,
                description="Enable goal-directed perfusion"
            ),
        ]

        for setting in defaults:
            self.settings[setting.key] = setting

    def get(self, key: str) -> Any:
        """Get a configuration value."""
        if key in self.settings:
            return self.settings[key].value
        return None

    def set(self,
            key: str,
            value: Any,
            user_id: str = "",
            username: str = "") -> tuple[bool, str]:
        """
        Set a configuration value.

        Args:
            key: Setting key
            value: New value
            user_id: User making change
            username: Username

        Returns:
            Tuple of (success, error_message)
        """
        if key not in self.settings:
            return (False, f"Unknown setting: {key}")

        setting = self.settings[key]

        # Validate
        is_valid, error = setting.validate(value)
        if not is_valid:
            return (False, error)

        # Store old value for audit
        old_value = setting.value

        # Update
        setting.value = value
        setting.last_modified = time.time()
        setting.modified_by = user_id
        self.config_version += 1
        self.last_modified = time.time()

        # Audit
        self.audit_trail.log(
            event_type=AuditEventType.CONFIG_CHANGE,
            description=f"Configuration changed: {key}",
            user_id=user_id,
            username=username,
            old_value=str(old_value),
            new_value=str(value)
        )

        return (True, "")

    def get_by_category(self, category: ConfigCategory) -> dict[str, ConfigSetting]:
        """Get all settings in a category."""
        return {
            key: setting for key, setting in self.settings.items()
            if setting.category == category
        }

    def export_config(self) -> str:
        """Export configuration to JSON."""
        config = {
            "version": self.config_version,
            "exported_at": datetime.now().isoformat(),
            "settings": {
                key: {
                    "value": setting.value,
                    "category": setting.category.name,
                    "description": setting.description
                }
                for key, setting in self.settings.items()
            }
        }
        return json.dumps(config, indent=2)

    def import_config(self,
                      config_json: str,
                      user_id: str = "") -> tuple[bool, list[str]]:
        """
        Import configuration from JSON.

        Args:
            config_json: Configuration JSON
            user_id: User importing config

        Returns:
            Tuple of (success, list of errors)
        """
        errors = []

        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as e:
            return (False, [f"Invalid JSON: {e}"])

        settings = config.get("settings", {})
        for key, data in settings.items():
            if key in self.settings:
                success, error = self.set(key, data.get("value"), user_id)
                if not success:
                    errors.append(f"{key}: {error}")

        return (len(errors) == 0, errors)

    def get_status(self) -> dict:
        """Get configuration status."""
        return {
            "version": self.config_version,
            "last_modified": datetime.fromtimestamp(self.last_modified).isoformat(),
            "total_settings": len(self.settings),
            "categories": {
                cat.name: len(self.get_by_category(cat))
                for cat in ConfigCategory
            }
        }


class ConfigurationSystem:
    """
    Complete configuration and audit system.
    """

    def __init__(self):
        """Initialize configuration system."""
        self.audit_trail = AuditTrail()
        self.user_manager = UserManager(self.audit_trail)
        self.config_manager = ConfigurationManager(self.audit_trail)

        # Current session
        self.current_session_id: str | None = None
        self.current_user: User | None = None

    def login(self, username: str, password: str) -> tuple[bool, str]:
        """
        Log in a user.

        Returns:
            Tuple of (success, error_or_session_id)
        """
        success, user, session_id = self.user_manager.authenticate(username, password)

        if success:
            self.current_session_id = session_id
            self.current_user = user
            return (True, session_id)
        else:
            return (False, "Authentication failed")

    def logout(self) -> bool:
        """Log out current user."""
        if self.current_session_id:
            self.user_manager.logout(self.current_session_id)
            self.current_session_id = None
            self.current_user = None
            return True
        return False

    def get_setting(self, key: str) -> Any:
        """Get a configuration setting."""
        return self.config_manager.get(key)

    def set_setting(self, key: str, value: Any) -> tuple[bool, str]:
        """Set a configuration setting."""
        if self.current_user is None:
            return (False, "Not logged in")

        setting = self.config_manager.settings.get(key)
        if setting and setting.requires_admin:
            if not self.current_user.has_permission(UserRole.ADMINISTRATOR):
                return (False, "Administrator permission required")

        return self.config_manager.set(
            key, value,
            user_id=self.current_user.user_id if self.current_user else "",
            username=self.current_user.username if self.current_user else ""
        )

    def get_audit_trail(self,
                        hours: float = 24.0,
                        event_type: AuditEventType | None = None) -> list[dict]:
        """Get recent audit entries."""
        start_time = time.time() - (hours * 3600)
        entries = self.audit_trail.get_entries(
            start_time=start_time,
            event_type=event_type
        )
        return [e.to_dict() for e in entries]

    def verify_audit_integrity(self) -> tuple[bool, list[str]]:
        """Verify audit trail integrity."""
        return self.audit_trail.verify_integrity()

    def get_status(self) -> dict:
        """Get configuration system status."""
        return {
            "is_logged_in": self.current_user is not None,
            "current_user": (
                {
                    "username": self.current_user.username,
                    "role": self.current_user.role.name,
                    "full_name": self.current_user.full_name
                }
                if self.current_user else None
            ),
            "configuration": self.config_manager.get_status(),
            "audit": {
                "total_entries": len(self.audit_trail.entries),
                "integrity_valid": self.audit_trail.verify_integrity()[0]
            },
            "users": {
                "total": len(self.user_manager.users),
                "active_sessions": len(self.user_manager.active_sessions)
            }
        }
