"""Pydantic v2 models matching contracts/event.schema.json (schema_version 1.0)."""
import json
from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SensorId = Literal["ssh-decoy-01", "web-decoy-01"]
EventType = Literal[
    "connection_open", "auth_failure", "auth_success", "command_input",
    "connection_close", "http_request", "synthetic_file_access", "blocked_request",
]

MAX_ATTR_KEYS = 32
MAX_ATTR_BYTES = 16 * 1024


class Attributes(BaseModel):
    # additionalProperties is true in the schema; extras are kept but bounded below.
    model_config = ConfigDict(extra="allow")

    username: Optional[str] = Field(None, max_length=128)
    password_sha256: Optional[str] = Field(None, max_length=128)
    client_version: Optional[str] = Field(None, max_length=256)
    command: Optional[str] = Field(None, max_length=4096)
    method: Optional[str] = Field(None, max_length=32)
    path: Optional[str] = Field(None, max_length=4096)
    query_redacted: Optional[str] = Field(None, max_length=4096)
    user_agent: Optional[str] = Field(None, max_length=512)
    status_code: Optional[int] = None
    response_class: Optional[Literal["normal", "fake_error", "fake_data", "blocked"]] = None
    honeytoken_id: Optional[str] = Field(None, max_length=128)
    asset_id: Optional[str] = Field(None, max_length=128)
    size_bytes: Optional[int] = None
    sha256: Optional[str] = Field(None, max_length=128)
    outcome: Optional[Literal["served", "denied", "not_found"]] = None
    block_action_id: Optional[str] = Field(None, max_length=128)

    @model_validator(mode="after")
    def _bounded_and_no_raw_secrets(self) -> "Attributes":
        data = self.model_dump(exclude_none=True)
        # Raw passwords must never reach storage: only password_sha256 is allowed.
        for key in data:
            k = key.lower()
            if k != "password_sha256" and ("pass" in k or "secret" in k):
                raise ValueError(f"attribute '{key}' looks like a raw secret; send a hash only")
        if len(data) > MAX_ATTR_KEYS:
            raise ValueError(f"more than {MAX_ATTR_KEYS} attributes")
        if len(json.dumps(data, default=str)) > MAX_ATTR_BYTES:
            raise ValueError("attributes too large")
        return self


class IngestEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    source_record_id: str = Field(min_length=1, max_length=128)
    sensor_id: SensorId
    event_type: EventType
    occurred_at: datetime
    src_ip: str
    src_port: Optional[int] = Field(None, ge=0, le=65535)
    session_id: Optional[str] = Field(None, max_length=128)
    lab_run_id: str = Field(min_length=1, max_length=128)
    capture_mode: Literal["live", "replay"]
    attributes: Attributes = Field(default_factory=Attributes)

    @field_validator("src_ip")
    @classmethod
    def _ipv4(cls, v: str) -> str:
        try:
            return str(IPv4Address(v))
        except ValueError:
            raise ValueError("not an ipv4") from None

    @field_validator("occurred_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must include a timezone (use UTC)")
        return v.astimezone(timezone.utc)


def to_rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reason_for(exc: Any) -> str:
    """Short 'field: message' string from a pydantic ValidationError."""
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err["loc"]) or "event"
    msg = err["msg"].removeprefix("Value error, ")
    return f"{loc}: {msg}"
