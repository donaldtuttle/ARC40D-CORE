"""
ARC40D_CORE_v1.0-rc1

Controller-only. Single-decision. Fail-closed invariants.

FROZEN CORE RULE:
Hash this module. After freeze, change only in response to:
    1. a conformance-test failure, or
    2. a hash-changing defect that breaks a claimed invariant.

No architectural changes after freeze without creating a new version.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import (
    Literal,
    Optional,
    List,
    Dict,
    Any,
    Callable,
    Tuple,
)
import hashlib
import json
import re
import secrets
import time
import uuid

from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError


# =============================================================================
# Version
# =============================================================================

VERSION = "ARC40D_CORE_v1.0-rc1"
PARSER_VERSION = "arc40d-parser-v1"
RUNNER_VERSION = "arc40d-controller-v1"


# =============================================================================
# Status axes
# =============================================================================

Decision = Literal[
    "CONTINUE",
    "STOP",
]

CallStatus = Literal[
    "SUCCESS",
    "INVALID_OUTPUT",
    "TRUNCATED",
    "REFUSAL",
    "PROVIDER_ERROR",
]

RunEnd = Literal[
    "DECISION_RECORDED",
    "ABORTED",
]


# =============================================================================
# Canonical serialization / hashing
# =============================================================================

def canonical_json_bytes(obj: Any) -> bytes:
    """
    Return one canonical JSON byte representation for all experiment hashes.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# =============================================================================
# Frozen provider-attempt record
# =============================================================================

@dataclass(frozen=True)
class AttemptRecord:
    attempt_index: int
    started_at_utc: str
    completed_at_utc: str
    latency_seconds: float
    success: bool

    http_status: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    provider_request_id: Optional[str] = None


# =============================================================================
# Provider-normalized usage
# =============================================================================

@dataclass(frozen=True)
class NormalizedUsage:
    """
    Provider-agnostic token accounting.

    input_tokens:
        Total reported input/prompt tokens.

    cached_input_tokens:
        Input tokens reported as cache hits, where exposed.

    visible_output_tokens:
        User-visible generated output tokens where distinguishable.

    reasoning_tokens:
        Hidden/reasoning/thinking tokens where exposed.

    billed_output_tokens:
        Tokens billed by the provider at the output rate.

    provider_total_tokens:
        Provider-reported total token count where exposed.
    """

    input_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    visible_output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    billed_output_tokens: Optional[int] = None
    provider_total_tokens: Optional[int] = None


# =============================================================================
# Full frozen model configuration
# =============================================================================

@dataclass(frozen=True)
class ModelSpec:
    """
    Every execution control capable of changing model behavior must be bound
    into model_specs_hash.
    """

    family: str
    provider: str
    model_id: str
    api_mode: str
    max_output_tokens: int
    temperature: Optional[float]
    reasoning_effort: Optional[str]
    timeout_seconds: int
    sdk_version: str


def hash_model_specs(specs: Dict[str, ModelSpec]) -> str:
    """
    Hash the complete model configuration mapping actually supplied to the run.
    """
    payload = {
        key: asdict(spec)
        for key, spec in sorted(specs.items())
    }
    return sha256_hex(canonical_json_bytes(payload))


# =============================================================================
# Immutable canonical call record
# =============================================================================

@dataclass(frozen=True)
class CallRecord:
    experiment_id: str
    manifest_sha256: str

    run_id: str
    blind_id: str
    replicate_id: str

    case_id_internal: str
    packet_id: str
    condition: str

    model_family: str
    requested_model: str
    resolved_model: Optional[str]

    # Always zero for ARC-40D.
    turn_index: int

    call_status: CallStatus
    decision: Optional[Decision]
    parser_error: Optional[str]

    provider_request_id: Optional[str]
    provider_response_id: Optional[str]
    finish_status: Optional[str]

    usage: NormalizedUsage

    attempts: int
    attempt_log: Tuple[AttemptRecord, ...]

    wall_latency_seconds: float
    estimated_cost_usd: Optional[float]

    request_sha256: str
    response_text_sha256: str
    response_record_sha256: str

    started_at_utc: str
    completed_at_utc: str

    run_end: RunEnd
    core_version: str = VERSION


# =============================================================================
# Experiment manifest
# =============================================================================

@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    manifest_sha256: str

    # condition -> exact system-prompt SHA-256
    instruction_hashes: Dict[str, str]

    # Complete frozen ModelSpec mapping SHA-256
    model_specs_hash: str

    parser_version: str
    runner_version: str

    # opaque packet_id -> exact packet-text SHA-256
    case_packet_hashes: Dict[str, str]

    # exact installed package versions
    sdk_versions: Dict[str, str]

    lockfile_hash: str
    price_table_hash: str


@dataclass(frozen=True)
class RuntimeFingerprint:
    model_specs_hash: str
    parser_version: str
    runner_version: str
    lockfile_hash: str
    price_table_hash: str


# =============================================================================
# Live environment inspection
# =============================================================================

def get_live_sdk_versions(packages: List[str]) -> Dict[str, str]:
    """
    Read the installed package versions from the live Python environment.
    """
    out: Dict[str, str] = {}

    for package in packages:
        try:
            out[package] = version(package)
        except PackageNotFoundError:
            out[package] = ""

    return out


# =============================================================================
# Manifest validation
# =============================================================================

def validate_manifest(
    *,
    manifest: ExperimentManifest,
    runtime: RuntimeFingerprint,
    condition: str,
    system_prompt: str,
    packet_id: str,
    packet_text: str,
    live_sdk_versions: Dict[str, str],
    live_model_specs_hash: str,
) -> None:
    """
    Fail closed on any configuration mismatch.

    This function must run before every provider invocation.
    """

    # ---------------------------------------------------------------------
    # Instruction identity
    # ---------------------------------------------------------------------

    instruction_sha = sha256_hex(system_prompt.encode("utf-8"))

    expected_instruction_sha = manifest.instruction_hashes.get(condition)

    if expected_instruction_sha is None:
        raise RuntimeError(
            f"unknown condition: {condition}"
        )

    if instruction_sha != expected_instruction_sha:
        raise RuntimeError(
            f"instruction hash mismatch for {condition}"
        )

    # ---------------------------------------------------------------------
    # Frozen packet identity
    # ---------------------------------------------------------------------

    packet_sha = sha256_hex(packet_text.encode("utf-8"))

    expected_packet_sha = manifest.case_packet_hashes.get(packet_id)

    if expected_packet_sha is None:
        raise RuntimeError(
            f"unknown packet_id: {packet_id}"
        )

    if packet_sha != expected_packet_sha:
        raise RuntimeError(
            f"packet hash mismatch for {packet_id}"
        )

    # ---------------------------------------------------------------------
    # Runtime fingerprint
    # ---------------------------------------------------------------------

    for field_name in (
        "parser_version",
        "runner_version",
        "lockfile_hash",
        "price_table_hash",
    ):
        actual = getattr(runtime, field_name)
        expected = getattr(manifest, field_name)

        if actual != expected:
            raise RuntimeError(
                f"{field_name} mismatch: "
                f"{actual!r} != {expected!r}"
            )

    # ---------------------------------------------------------------------
    # Complete model-spec binding
    # ---------------------------------------------------------------------

    if live_model_specs_hash != manifest.model_specs_hash:
        raise RuntimeError(
            "model_specs_hash mismatch: "
            f"live={live_model_specs_hash} "
            f"expected={manifest.model_specs_hash}"
        )

    if runtime.model_specs_hash != manifest.model_specs_hash:
        raise RuntimeError(
            "runtime fingerprint model_specs_hash mismatch"
        )

    # ---------------------------------------------------------------------
    # Exact SDK environment
    # ---------------------------------------------------------------------

    if live_sdk_versions != manifest.sdk_versions:
        raise RuntimeError(
            "SDK environment mismatch:\n"
            f"live={live_sdk_versions}\n"
            f"expected={manifest.sdk_versions}"
        )


# =============================================================================
# Strict ARC-40D terminal parser
# =============================================================================

_TERMINAL_RE = re.compile(
    r"^(NEXT_PROMPT|CHAIN_COMPLETE):\s*(.+)$"
)


@dataclass(frozen=True)
class ParsedTerminal:
    valid: bool
    decision: Optional[Decision] = None

    next_prompt: Optional[str] = None
    stop_reason: Optional[str] = None

    error: Optional[str] = None


def parse_arc40d_terminal(text: str) -> ParsedTerminal:
    """
    ARC-40D controller-only output contract:

        Exactly one nonblank line.

        NEXT_PROMPT: <one complete pasteable next prompt>

    or:

        CHAIN_COMPLETE: <concise stopping reason>

    Any additional prose, duplicate terminal marker, nested marker, or empty
    payload is invalid.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if len(lines) != 1:
        return ParsedTerminal(
            valid=False,
            error=f"expected_one_nonblank_line_got_{len(lines)}",
        )

    match = _TERMINAL_RE.fullmatch(lines[0])

    if not match:
        return ParsedTerminal(
            valid=False,
            error="malformed_terminal",
        )

    marker, payload = match.groups()
    payload = payload.strip()

    if not payload:
        return ParsedTerminal(
            valid=False,
            error="empty_payload",
        )

    # Prevent one line from containing two controller decisions.
    if (
        "NEXT_PROMPT:" in payload
        or "CHAIN_COMPLETE:" in payload
    ):
        return ParsedTerminal(
            valid=False,
            error="nested_terminal_marker",
        )

    if marker == "NEXT_PROMPT":
        return ParsedTerminal(
            valid=True,
            decision="CONTINUE",
            next_prompt=payload,
        )

    return ParsedTerminal(
        valid=True,
        decision="STOP",
        stop_reason=payload,
    )


# =============================================================================
# Provider adapter result contract
# =============================================================================

@dataclass
class ModelResult:
    text: str
    provider: str
    requested_model: str

    resolved_model: Optional[str] = None

    finish_status: Optional[str] = None
    provider_request_id: Optional[str] = None
    provider_response_id: Optional[str] = None

    usage: NormalizedUsage = field(
        default_factory=NormalizedUsage
    )

    attempts: int = 1
    attempt_log: List[AttemptRecord] = field(
        default_factory=list
    )

    wall_latency_seconds: float = 0.0

    refusal: bool = False
    truncated: bool = False

    error: Optional[str] = None


# =============================================================================
# Technical-status precedence
# =============================================================================

@dataclass(frozen=True)
class EvaluatedCall:
    status: CallStatus
    parsed: Optional[ParsedTerminal] = None
    error: Optional[str] = None


def evaluate_call(result: ModelResult) -> EvaluatedCall:
    """
    Technical outcomes always outrank apparent terminal text.

    A truncated/refused/failed response cannot be scored as a valid controller
    decision merely because its visible text contains a valid-looking marker.
    """

    if result.error:
        return EvaluatedCall(
            status="PROVIDER_ERROR",
            error=result.error,
        )

    if result.refusal:
        return EvaluatedCall(
            status="REFUSAL",
            error="provider_or_model_refusal",
        )

    if result.truncated:
        return EvaluatedCall(
            status="TRUNCATED",
            error="generation_truncated",
        )

    parsed = parse_arc40d_terminal(result.text)

    if not parsed.valid:
        return EvaluatedCall(
            status="INVALID_OUTPUT",
            parsed=parsed,
            error=parsed.error,
        )

    return EvaluatedCall(
        status="SUCCESS",
        parsed=parsed,
    )


# =============================================================================
# ARC-40D controller-only runner
# =============================================================================

def run_controller_call(
    *,
    manifest: ExperimentManifest,
    runtime: RuntimeFingerprint,

    case_id_internal: str,
    packet_id: str,
    packet_text: str,

    condition: str,
    system_prompt: str,

    spec: ModelSpec,
    model_specs: Dict[str, ModelSpec],

    call_model: Callable[
        [List[dict]],
        ModelResult,
    ],

    replicate_id: str = "0",
) -> CallRecord:
    """
    Execute exactly one ARC-40D controller decision.

    ARC-40D does not execute NEXT_PROMPT.
    Both CONTINUE and STOP complete the benchmark run once a valid decision
    has been recorded.
    """

    # ---------------------------------------------------------------------
    # Validate actual runtime against frozen manifest
    # ---------------------------------------------------------------------

    live_sdk_versions = get_live_sdk_versions(
        list(manifest.sdk_versions.keys())
    )

    live_model_specs_hash = hash_model_specs(
        model_specs
    )

    validate_manifest(
        manifest=manifest,
        runtime=runtime,
        condition=condition,
        system_prompt=system_prompt,
        packet_id=packet_id,
        packet_text=packet_text,
        live_sdk_versions=live_sdk_versions,
        live_model_specs_hash=live_model_specs_hash,
    )

    # ---------------------------------------------------------------------
    # Bind concrete spec to exact frozen mapping
    # ---------------------------------------------------------------------

    if model_specs.get(spec.family) != spec:
        raise RuntimeError(
            "supplied ModelSpec is not the ModelSpec "
            "present in the frozen model_specs mapping"
        )

    # ---------------------------------------------------------------------
    # Allocate run/blind identities
    # ---------------------------------------------------------------------

    run_id = uuid.uuid4().hex
    blind_id = secrets.token_hex(12)

    # ---------------------------------------------------------------------
    # Construct exact provider request
    # ---------------------------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": packet_text,
        },
    ]

    request_sha256 = sha256_hex(
        canonical_json_bytes(messages)
    )

    # ---------------------------------------------------------------------
    # Logical provider call
    # ---------------------------------------------------------------------

    started_at_utc = datetime.now(
        timezone.utc
    ).isoformat()

    start_clock = time.perf_counter()

    result = call_model(messages)

    wall_latency_seconds = (
        time.perf_counter() - start_clock
    )

    completed_at_utc = datetime.now(
        timezone.utc
    ).isoformat()

    # ---------------------------------------------------------------------
    # Enforce requested-model source of truth
    # ---------------------------------------------------------------------

    if result.requested_model != spec.model_id:
        raise RuntimeError(
            "provider returned unexpected requested_model: "
            f"{result.requested_model!r} "
            f"!= {spec.model_id!r}"
        )

    # ---------------------------------------------------------------------
    # Response hashes
    # ---------------------------------------------------------------------

    response_text_sha256 = sha256_hex(
        result.text.encode("utf-8")
    )

    response_payload = {
        "text": result.text,
        "provider": result.provider,
        "requested_model": result.requested_model,
        "resolved_model": result.resolved_model,
        "finish_status": result.finish_status,
        "provider_request_id": result.provider_request_id,
        "provider_response_id": result.provider_response_id,
        "usage": asdict(result.usage),
        "attempts": result.attempts,
        "attempt_log": [
            asdict(attempt)
            for attempt in result.attempt_log
        ],
        "wall_latency_seconds": wall_latency_seconds,
        "refusal": result.refusal,
        "truncated": result.truncated,
        "error": result.error,
    }

    response_record_sha256 = sha256_hex(
        canonical_json_bytes(response_payload)
    )

    # ---------------------------------------------------------------------
    # Evaluate controller output
    # ---------------------------------------------------------------------

    evaluated = evaluate_call(result)

    decision: Optional[Decision] = None

    if (
        evaluated.parsed is not None
        and evaluated.parsed.valid
    ):
        decision = evaluated.parsed.decision

    run_end: RunEnd = (
        "DECISION_RECORDED"
        if evaluated.status == "SUCCESS"
        else "ABORTED"
    )

    # ---------------------------------------------------------------------
    # Cost deliberately remains unset in controller core.
    # Cost normalization belongs to frozen provider/price-layer code.
    # ---------------------------------------------------------------------

    estimated_cost_usd = None

    # ---------------------------------------------------------------------
    # Seal canonical CallRecord
    # ---------------------------------------------------------------------

    return CallRecord(
        experiment_id=manifest.experiment_id,
        manifest_sha256=manifest.manifest_sha256,

        run_id=run_id,
        blind_id=blind_id,
        replicate_id=replicate_id,

        case_id_internal=case_id_internal,
        packet_id=packet_id,
        condition=condition,

        model_family=spec.family,
        requested_model=spec.model_id,
        resolved_model=result.resolved_model,

        turn_index=0,

        call_status=evaluated.status,
        decision=decision,
        parser_error=evaluated.error,

        provider_request_id=result.provider_request_id,
        provider_response_id=result.provider_response_id,
        finish_status=result.finish_status,

        usage=result.usage,

        attempts=result.attempts,
        attempt_log=tuple(result.attempt_log),

        wall_latency_seconds=wall_latency_seconds,
        estimated_cost_usd=estimated_cost_usd,

        request_sha256=request_sha256,
        response_text_sha256=response_text_sha256,
        response_record_sha256=response_record_sha256,

        started_at_utc=started_at_utc,
        completed_at_utc=completed_at_utc,

        run_end=run_end,
        core_version=VERSION,
    )


# =============================================================================
# Minimal fail-closed conformance suite
# =============================================================================

# Run with pytest after supplying fixtures for:
#   manifest
#   runtime
#   model_specs
#   spec


def test_nested_marker_rejected():
    parsed = parse_arc40d_terminal(
        "NEXT_PROMPT: test CHAIN_COMPLETE: done"
    )

    assert not parsed.valid
    assert parsed.error == "nested_terminal_marker"


def test_multi_line_rejected():
    parsed = parse_arc40d_terminal(
        "prose\nNEXT_PROMPT: x"
    )

    assert not parsed.valid
    assert (
        "expected_one_nonblank_line"
        in parsed.error
    )


def test_technical_precedence():
    result = ModelResult(
        text="CHAIN_COMPLETE: ok",
        provider="test",
        requested_model="m",
        truncated=True,
    )

    evaluated = evaluate_call(result)

    assert evaluated.status == "TRUNCATED"


def test_attempt_record_frozen():
    from dataclasses import FrozenInstanceError
    import pytest

    attempt = AttemptRecord(
        attempt_index=1,
        started_at_utc="t0",
        completed_at_utc="t1",
        latency_seconds=0.1,
        success=True,
    )

    with pytest.raises(FrozenInstanceError):
        attempt.success = False  # type: ignore[misc]


def test_unknown_condition_fails(
    manifest,
    runtime,
    model_specs,
):
    import pytest

    live_sdks = dict(
        manifest.sdk_versions
    )

    with pytest.raises(
        RuntimeError,
        match="unknown condition",
    ):
        validate_manifest(
            manifest=manifest,
            runtime=runtime,
            condition="NO_SUCH_CONDITION",
            system_prompt="p",
            packet_id="PKT",
            packet_text="t",
            live_sdk_versions=live_sdks,
            live_model_specs_hash=hash_model_specs(
                model_specs
            ),
        )


def test_unknown_packet_fails(
    manifest,
    runtime,
    model_specs,
):
    import pytest

    live_sdks = dict(
        manifest.sdk_versions
    )

    with pytest.raises(
        RuntimeError,
        match="unknown packet_id",
    ):
        validate_manifest(
            manifest=manifest,
            runtime=runtime,
            condition="DIRECT_POLICY",
            system_prompt="p",
            packet_id="BAD_PKT",
            packet_text="t",
            live_sdk_versions=live_sdks,
            live_model_specs_hash=hash_model_specs(
                model_specs
            ),
        )


def test_runtime_fingerprint_mismatch_fails(
    manifest,
    runtime,
    model_specs,
):
    import pytest

    bad_runtime = RuntimeFingerprint(
        model_specs_hash=runtime.model_specs_hash,
        parser_version="WRONG",
        runner_version=runtime.runner_version,
        lockfile_hash=runtime.lockfile_hash,
        price_table_hash=runtime.price_table_hash,
    )

    with pytest.raises(
        RuntimeError,
        match="parser_version mismatch",
    ):
        validate_manifest(
            manifest=manifest,
            runtime=bad_runtime,
            condition="DIRECT_POLICY",
            system_prompt="p",
            packet_id="PKT",
            packet_text="t",
            live_sdk_versions=dict(
                manifest.sdk_versions
            ),
            live_model_specs_hash=hash_model_specs(
                model_specs
            ),
        )


def test_model_specs_hash_mismatch_fails(
    manifest,
    runtime,
):
    import pytest

    with pytest.raises(
        RuntimeError,
        match="model_specs_hash mismatch",
    ):
        validate_manifest(
            manifest=manifest,
            runtime=runtime,
            condition="DIRECT_POLICY",
            system_prompt="p",
            packet_id="PKT",
            packet_text="t",
            live_sdk_versions=dict(
                manifest.sdk_versions
            ),
            live_model_specs_hash="0" * 64,
        )


def test_requested_model_mismatch_aborts(
    manifest,
    runtime,
    model_specs,
    spec,
):
    import pytest

    def bad_adapter(_messages):
        return ModelResult(
            text="CHAIN_COMPLETE: x",
            provider="test",
            requested_model="WRONG_ID",
        )

    with pytest.raises(
        RuntimeError,
        match="unexpected requested_model",
    ):
        run_controller_call(
            manifest=manifest,
            runtime=runtime,

            case_id_internal="c1",
            packet_id="PKT",
            packet_text="t",

            condition="DIRECT_POLICY",
            system_prompt="p",

            spec=spec,
            model_specs=model_specs,

            call_model=bad_adapter,
        )


# =============================================================================
# Freeze statement
# =============================================================================

"""
ARC40D_CORE_v1.0-rc1 is frozen.

After establishing the module SHA-256:

Permitted changes:
    - fix a conformance-test failure
    - fix a newly discovered hash-changing defect that breaks a claimed
      invariant

Not sufficient grounds for change:
    - naming preference
    - stylistic cleanup
    - refactoring without demonstrated defect
    - additional convenience features
    - architectural experimentation

Any intentional architectural change requires a new version.
"""