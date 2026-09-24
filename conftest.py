"""Pytest fixtures for the frozen ARC-40D conformance suite.

These fixtures live outside arc40d_core.py on purpose. The core module is
hash-pinned. Do not move fixture construction into that file.
"""

from __future__ import annotations

import pytest

from arc40d_core import (
    PARSER_VERSION,
    RUNNER_VERSION,
    ExperimentManifest,
    ModelSpec,
    RuntimeFingerprint,
    hash_model_specs,
    sha256_hex,
)

# The suite calls validate_manifest with these exact strings.
SYSTEM_PROMPT = "p"
PACKET_TEXT = "t"
CONDITION = "DIRECT_POLICY"
PACKET_ID = "PKT"


def _sha(text: str) -> str:
    return sha256_hex(text.encode("utf-8"))


@pytest.fixture
def spec() -> ModelSpec:
    return ModelSpec(
        family="test",
        provider="test",
        model_id="m",
        api_mode="responses",
        max_output_tokens=1024,
        temperature=0.0,
        reasoning_effort=None,
        timeout_seconds=60,
        sdk_version="",
    )


@pytest.fixture
def model_specs(spec: ModelSpec) -> dict[str, ModelSpec]:
    return {spec.family: spec}


@pytest.fixture
def runtime(model_specs: dict[str, ModelSpec]) -> RuntimeFingerprint:
    return RuntimeFingerprint(
        model_specs_hash=hash_model_specs(model_specs),
        parser_version=PARSER_VERSION,
        runner_version=RUNNER_VERSION,
        lockfile_hash="lock",
        price_table_hash="price",
    )


@pytest.fixture
def manifest(
    runtime: RuntimeFingerprint,
) -> ExperimentManifest:
    # manifest_sha256 is not recomputed by the core. The suite does not
    # check it. This placeholder is not a self-hash of the manifest.
    return ExperimentManifest(
        experiment_id="arc40d-fixture",
        manifest_sha256="0" * 64,
        instruction_hashes={CONDITION: _sha(SYSTEM_PROMPT)},
        model_specs_hash=runtime.model_specs_hash,
        parser_version=PARSER_VERSION,
        runner_version=RUNNER_VERSION,
        case_packet_hashes={PACKET_ID: _sha(PACKET_TEXT)},
        sdk_versions={},
        lockfile_hash=runtime.lockfile_hash,
        price_table_hash=runtime.price_table_hash,
    )
