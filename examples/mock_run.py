"""Credential-free rc1 calls.

Not part of the pinned module. Shows one accepted stop and one truncated
response that must not be scored as a stop.
"""

from __future__ import annotations

from arc40d_core import (
    PARSER_VERSION,
    RUNNER_VERSION,
    ExperimentManifest,
    ModelResult,
    ModelSpec,
    RuntimeFingerprint,
    hash_model_specs,
    run_controller_call,
    sha256_hex,
)

SYSTEM_PROMPT = "Decide whether to continue or stop. Reply with one terminal line."
PACKET_TEXT = "Case packet: the draft claims the measurement was replicated."
CONDITION = "DIRECT_POLICY"
PACKET_ID = "PKT-1"


def sha(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


def build():
    spec = ModelSpec(
        family="mock",
        provider="mock",
        model_id="mock-model",
        api_mode="responses",
        max_output_tokens=256,
        temperature=0.0,
        reasoning_effort=None,
        timeout_seconds=30,
        sdk_version="",
    )
    model_specs = {spec.family: spec}
    specs_hash = hash_model_specs(model_specs)
    manifest = ExperimentManifest(
        experiment_id="arc40d-mock",
        # Stored only. rc1 does not recompute this.
        manifest_sha256="0" * 64,
        instruction_hashes={CONDITION: sha(SYSTEM_PROMPT)},
        model_specs_hash=specs_hash,
        parser_version=PARSER_VERSION,
        runner_version=RUNNER_VERSION,
        case_packet_hashes={PACKET_ID: sha(PACKET_TEXT)},
        sdk_versions={},
        lockfile_hash="lock",
        price_table_hash="price",
    )
    runtime = RuntimeFingerprint(
        model_specs_hash=specs_hash,
        parser_version=PARSER_VERSION,
        runner_version=RUNNER_VERSION,
        lockfile_hash="lock",
        price_table_hash="price",
    )
    return spec, model_specs, manifest, runtime


def show(label: str, call_model) -> None:
    spec, model_specs, manifest, runtime = build()
    record = run_controller_call(
        manifest=manifest,
        runtime=runtime,
        case_id_internal="case-1",
        packet_id=PACKET_ID,
        packet_text=PACKET_TEXT,
        condition=CONDITION,
        system_prompt=SYSTEM_PROMPT,
        spec=spec,
        model_specs=model_specs,
        call_model=call_model,
    )
    print(
        f"{label}: status={record.call_status} "
        f"decision={record.decision} run_end={record.run_end}"
    )


def successful_stop(_messages):
    spec, _, _, _ = build()
    return ModelResult(
        text="CHAIN_COMPLETE: the packet already contains the replicate",
        provider=spec.provider,
        requested_model=spec.model_id,
    )


def truncated_stop(_messages):
    """Same visible marker. The adapter reports that generation was cut off."""
    spec, _, _, _ = build()
    return ModelResult(
        text="CHAIN_COMPLETE: the packet already contains the replicate",
        provider=spec.provider,
        requested_model=spec.model_id,
        truncated=True,
        finish_status="length",
    )


def main() -> None:
    show("stop", successful_stop)
    show("truncated", truncated_stop)


if __name__ == "__main__":
    main()
