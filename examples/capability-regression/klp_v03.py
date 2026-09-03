"""Validation and identity helpers for the KLP Core v0.3 records."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from typing import Any


PROTOCOL_VERSION = "klp-core/v0.3"
_DIGEST_PREFIX = "sha256:"


class ContractError(ValueError):
    """Raised when a KLP v0.3 record is invalid or mismatched."""


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def digest(value: object) -> str:
    return _DIGEST_PREFIX + hashlib.sha256(canonical_json(value)).hexdigest()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{label} must be an object")
    return value


def _required(mapping: dict[str, Any], key: str, label: str) -> Any:
    if key not in mapping:
        raise ContractError(f"{label}.{key} is required")
    return mapping[key]


def _nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{label} must be a nonempty string")
    return value


def _string_list(value: object, label: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ContractError(f"{label} must be an array")
    if nonempty and not value:
        raise ContractError(f"{label} must not be empty")
    for index, item in enumerate(value):
        _nonempty_string(item, f"{label}[{index}]")
    return value


def _positive_revision(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ContractError(f"{label} must be a positive integer")
    return value


def _digest_string(value: object, label: str) -> str:
    text = _nonempty_string(value, label)
    if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", text) is None:
        raise ContractError(f"{label} must be a sha256 digest")
    return text


def _validate_capability(capability: object, index: int) -> dict[str, Any]:
    value = _mapping(capability, f"mission.critical_capabilities[{index}]")
    label = f"mission.critical_capabilities[{index}]"
    for key in (
        "capability_id",
        "required_behavior",
        "proof_method",
        "accepted_baseline_ref",
        "decision_provenance_requirement",
    ):
        _nonempty_string(_required(value, key, label), f"{label}.{key}")
    if _required(value, "severity", label) != "critical":
        raise ContractError(f"{label}.severity must be critical")
    _string_list(_required(value, "trigger_rules", label), f"{label}.trigger_rules")
    _string_list(_required(value, "positive_control", label), f"{label}.positive_control")
    _string_list(_required(value, "negative_control", label), f"{label}.negative_control")
    return value


def _validate_mission_body(body: object) -> dict[str, Any]:
    mission = _mapping(body, "mission")
    for key in (
        "product_outcome",
        "operator_revision_authority",
        "revision_reason",
    ):
        _nonempty_string(_required(mission, key, "mission"), f"mission.{key}")
    capabilities = _required(mission, "critical_capabilities", "mission")
    if not isinstance(capabilities, list) or not capabilities:
        raise ContractError("mission.critical_capabilities must be a nonempty array")
    capability_ids: set[str] = set()
    for index, capability in enumerate(capabilities):
        validated = _validate_capability(capability, index)
        capability_id = validated["capability_id"]
        if capability_id in capability_ids:
            raise ContractError(f"duplicate capability id: {capability_id}")
        capability_ids.add(capability_id)
    _string_list(
        _required(mission, "forbidden_regressions", "mission"),
        "mission.forbidden_regressions",
        nonempty=False,
    )
    return mission


def validate_mission_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    record = _mapping(snapshot, "Mission Contract")
    identity = _mapping(_required(record, "identity", "Mission Contract"), "identity")
    body = _validate_mission_body(_required(record, "mission", "Mission Contract"))
    if _required(identity, "protocol_version", "identity") != PROTOCOL_VERSION:
        raise ContractError("identity.protocol_version is not KLP Core v0.3")
    _nonempty_string(
        _required(identity, "mission_id", "identity"), "identity.mission_id"
    )
    revision = _positive_revision(
        _required(identity, "mission_revision", "identity"), "identity.mission_revision"
    )
    mission_hash = _digest_string(
        _required(identity, "mission_hash", "identity"), "identity.mission_hash"
    )
    parent = _required(identity, "parent_mission_hash", "identity")
    if parent is not None:
        _digest_string(parent, "identity.parent_mission_hash")
    _nonempty_string(
        _required(identity, "authority_ref", "identity"), "identity.authority_ref"
    )
    _nonempty_string(
        _required(identity, "created_at", "identity"), "identity.created_at"
    )
    if digest(body) != mission_hash:
        raise ContractError("mission hash does not match mission body")
    if revision == 1 and parent is not None:
        raise ContractError("first mission revision must not have a parent mission hash")
    if revision > 1 and parent is None:
        raise ContractError("revised mission must have a parent mission hash")
    return body


def _validate_task_snapshot(
    snapshot: dict[str, Any], *, verify_digest: bool
) -> dict[str, Any]:
    record = _mapping(snapshot, "Task Contract")
    identity = _mapping(_required(record, "identity", "Task Contract"), "identity")
    task = _mapping(_required(record, "task", "Task Contract"), "task")
    if _required(identity, "protocol_version", "identity") != PROTOCOL_VERSION:
        raise ContractError("identity.protocol_version is not KLP Core v0.3")
    _nonempty_string(
        _required(identity, "task_id", "identity"), "identity.task_id"
    )
    _positive_revision(
        _required(identity, "task_revision", "identity"), "identity.task_revision"
    )
    contract_hash = _digest_string(
        _required(identity, "contract_hash", "identity"), "identity.contract_hash"
    )
    _nonempty_string(
        _required(identity, "created_at", "identity"), "identity.created_at"
    )
    for key in ("task_id", "objective", "mission_id", "mission_hash"):
        _nonempty_string(_required(task, key, "task"), f"task.{key}")
    _positive_revision(
        _required(task, "mission_revision", "task"), "task.mission_revision"
    )
    _digest_string(_required(task, "mission_hash", "task"), "task.mission_hash")
    _string_list(
        _required(task, "affected_capabilities", "task"),
        "task.affected_capabilities",
        nonempty=False,
    )
    expected_delta = _required(task, "expected_capability_delta", "task")
    if expected_delta not in {"preserve", "improve"}:
        raise ContractError("task.expected_capability_delta must be preserve or improve")
    _string_list(
        _required(task, "required_capability_probes", "task"),
        "task.required_capability_probes",
    )
    _string_list(
        _required(task, "baseline_evidence_refs", "task"),
        "task.baseline_evidence_refs",
        nonempty=False,
    )
    _string_list(
        _required(task, "allowed_paths", "task"), "task.allowed_paths"
    )
    if task["task_id"] != identity["task_id"]:
        raise ContractError("task id does not match Task Contract identity")
    if verify_digest and digest(task) != contract_hash:
        raise ContractError("contract hash does not match task body")
    return task


def validate_task_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return _validate_task_snapshot(snapshot, verify_digest=True)


def matching_capability_ids(
    mission: dict[str, Any], changed_surfaces: list[str]
) -> set[str]:
    _validate_mission_body(mission)
    surfaces = _string_list(changed_surfaces, "changed_surfaces", nonempty=False)
    return {
        capability["capability_id"]
        for capability in mission["critical_capabilities"]
        if any(
            fnmatch.fnmatchcase(surface, rule)
            for surface in surfaces
            for rule in capability["trigger_rules"]
        )
    }


def validate_task_binding(
    mission_snapshot: dict[str, Any],
    task_snapshot: dict[str, Any],
    changed_surfaces: list[str],
) -> set[str]:
    mission = validate_mission_snapshot(mission_snapshot)
    identity = mission_snapshot["identity"]
    task_record = _mapping(task_snapshot, "Task Contract")
    task_body = _mapping(
        _required(task_record, "task", "Task Contract"), "task"
    )
    if _required(task_body, "mission_id", "task") != identity["mission_id"]:
        raise ContractError("task mission id does not match Mission Contract")
    if (
        _required(task_body, "mission_revision", "task")
        != identity["mission_revision"]
    ):
        raise ContractError("task mission revision does not match Mission Contract")
    if _required(task_body, "mission_hash", "task") != identity["mission_hash"]:
        raise ContractError("task mission hash does not match Mission Contract")

    task = _validate_task_snapshot(task_snapshot, verify_digest=False)
    triggered = matching_capability_ids(mission, changed_surfaces)
    capability_ids = {item["capability_id"] for item in mission["critical_capabilities"]}
    declared = set(task["affected_capabilities"])
    unknown = declared - capability_ids
    if unknown:
        raise ContractError(
            "task declares unknown capability: " + ", ".join(sorted(unknown))
        )
    omitted = triggered - declared
    if omitted:
        raise ContractError(
            "triggered capability not declared: " + ", ".join(sorted(omitted))
        )
    task_identity = task_snapshot["identity"]
    if digest(task) != task_identity["contract_hash"]:
        raise ContractError("contract hash does not match task body")
    return triggered


_TECHNICAL_FIELDS = (
    "fields_changed",
    "evidence_refs",
    "behavioral_impact",
    "architectural_impact",
    "testing_impact",
    "safety_impact",
    "compatibility_impact",
    "alternatives_considered",
    "rollback_implications",
    "duration",
)
_IMPACT_FIELDS = ("today", "after", "user_may_lose", "expected_benefit", "if_declined")


def validate_amendment_request(request: dict[str, Any]) -> None:
    record = _mapping(request, "Mission Amendment Request")
    if (
        _required(record, "protocol_version", "Mission Amendment Request")
        != PROTOCOL_VERSION
    ):
        raise ContractError(
            "Mission Amendment Request.protocol_version must be klp-core/v0.3"
        )
    technical = _mapping(
        _required(record, "technical_explanation", "Mission Amendment Request"),
        "technical_explanation",
    )
    if "operator_impact_statement" not in record:
        raise ContractError(
            "Mission Amendment Request requires a plain-English Operator Impact Statement"
        )
    impact = _mapping(record["operator_impact_statement"], "operator_impact_statement")
    for key in _TECHNICAL_FIELDS:
        value = _required(technical, key, "technical_explanation")
        if key.endswith("_refs") or key in {"fields_changed", "alternatives_considered"}:
            _string_list(value, f"technical_explanation.{key}")
        else:
            _nonempty_string(value, f"technical_explanation.{key}")
    for key in _IMPACT_FIELDS:
        _nonempty_string(
            _required(impact, key, "operator_impact_statement"),
            f"operator_impact_statement.{key}",
        )
    for key in ("request_id", "mission_id", "current_mission_hash", "requested_change"):
        value = _required(record, key, "Mission Amendment Request")
        if key == "requested_change":
            _nonempty_string(value, "Mission Amendment Request.requested_change")
        else:
            _nonempty_string(value, f"Mission Amendment Request.{key}")
    _digest_string(
        record["current_mission_hash"],
        "Mission Amendment Request.current_mission_hash",
    )


def build_authorized_mission_revision(
    current_snapshot: dict[str, Any],
    request: dict[str, Any],
    amended_mission: dict[str, Any],
    operator_authority_ref: str,
) -> dict[str, Any]:
    validate_mission_snapshot(current_snapshot)
    validate_amendment_request(request)
    current_identity = current_snapshot["identity"]
    authority_ref = _nonempty_string(
        operator_authority_ref, "operator_authority_ref"
    )
    if request["mission_id"] != current_identity["mission_id"]:
        raise ContractError(
            "amendment mission id does not match current Mission Contract"
        )
    if request["current_mission_hash"] != current_identity["mission_hash"]:
        raise ContractError(
            "amendment mission hash does not match current Mission Contract"
        )
    if not isinstance(amended_mission, dict):
        raise ContractError("amended_mission must be an object")
    body = _validate_mission_body(amended_mission)
    identity = {
        "protocol_version": PROTOCOL_VERSION,
        "mission_id": current_identity["mission_id"],
        "mission_revision": current_identity["mission_revision"] + 1,
        "mission_hash": digest(body),
        "parent_mission_hash": current_identity["mission_hash"],
        "authority_ref": authority_ref,
        "created_at": current_identity["created_at"],
    }
    return {"identity": identity, "mission": body}
