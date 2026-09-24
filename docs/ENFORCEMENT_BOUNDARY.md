# Enforcement boundary

Reviewed against commit `5a6a524`. Rechecked against the pinned file
`arc40d_core.py` (`ARC40D_CORE_v1.0-rc1`, SHA-256
`5212f2817f145997db35ca8e3852682c091572b9106ce0c3786e8598134b95e0`).

The frozen module was not changed. No model benchmark was run. The probes
below use a mock adapter.

The supplied conformance suite is 9 tests, and those 9 passed. They do not
cover the gaps in this note. rc1 stays a release candidate until the
boundary below is either accepted as outside the core or moved into a new
version.

## What “validated” means in rc1

The core checks that several supplied declarations agree. Some of those
declarations are measured from bytes or from the installed environment.
Others are accepted from the caller or the adapter.

Measured before the adapter is invoked:

- SHA-256 of the system-prompt string passed into `run_controller_call`
- SHA-256 of the packet-text string passed into `run_controller_call`
- SHA-256 of the `ModelSpec` mapping passed as `model_specs`
- equality of that concrete `ModelSpec` with `model_specs[spec.family]`
- versions reported by `importlib.metadata` for the package names listed in
  `manifest.sdk_versions`

Accepted as agreement between values the caller or adapter supplied:

- `manifest_sha256` (stored, never recomputed)
- `parser_version`, `runner_version`, `lockfile_hash`, `price_table_hash`
- `result.provider`
- `result.attempts` and `result.attempt_log`
- temperature, token limit, reasoning effort, timeout, and API mode actually
  used by the adapter
- the bytes the adapter submits to a provider

That distinction is the limit on calling this runner reproducible or
fail-closed. It fails closed when a measured value disagrees with the
manifest. It does not fail closed on a declaration it never measures.

## Confirmed gaps

These behaviors are in the pinned core.

| Finding | What was rechecked | Implication |
|---|---|---|
| Manifest contents are mutable. | Replacing `manifest.instruction_hashes["DIRECT_POLICY"]` let a different prompt run. `manifest_sha256` stayed the same. | `frozen=True` blocks replacing the field. It does not block editing the dictionary. |
| Provider identity is unchecked. | An adapter returning `provider="wrong-provider"` was `SUCCESS` when `requested_model` matched `spec.model_id`. | A reported provider mismatch is accepted. |
| Runtime versions are compared, not established. | The same invented parser and runner strings on both the manifest and the runtime passed `validate_manifest`. | The check is agreement between supplied strings. It does not compare them with `PARSER_VERSION` or `RUNNER_VERSION`. |
| Exceptions escape without a record. | An adapter raising `TimeoutError` produced no `CallRecord`. | Scoring stops. Structured failure accounting needs an outer harness. |
| Attempt metadata is unvalidated. | `attempts=0` and an empty attempt log, with a valid terminal line, was `SUCCESS`. | A successful record can carry contradictory execution metadata. |
| The adapter is not bound to `ModelSpec`. | `call_model` receives only the message list. | Hashing `ModelSpec` fixes the declared configuration. It does not prove the adapter used it. |
| `request_sha256` is pre-adapter. | The adapter changed the system message after receipt. The record stayed `SUCCESS` and kept the hash of the original messages. | The core hashes the messages it hands over. It does not hash the request a provider received, and it does not include provider-specific settings. |
| A missing package matches `""`. | `get_live_sdk_versions` returns `""` for a package that is not installed. A manifest that expected `""` passed. | Absence and a declared empty version are the same string. Production validation should distinguish them. |

`manifest_sha256`, `lockfile_hash`, and `price_table_hash` are caller-supplied.
The core already does not recompute `manifest_sha256`. That is an external
responsibility, not a hidden defect: the caller needs a defined hash scope
and a verification step outside this module.

## What did hold

- Exactly one call to `call_model` per `run_controller_call`. Multiple
  physical attempts can still happen inside that adapter. The attempt fields
  exist for that, and rc1 does not check them.
- `CONTINUE` and `STOP` both finish the controller run. `NEXT_PROMPT` is not
  executed.
- `PROVIDER_ERROR`, `REFUSAL`, and `TRUNCATED` outrank valid-looking terminal
  text.
- Extra nonblank lines and nested terminal markers are rejected.
- A prompt or packet hash mismatch raises before the adapter is called.
- `requested_model` must equal `spec.model_id`.

`SUCCESS` means the normalized response passed the technical flags and the
terminal-format check. It does not mean continuing or stopping was the right
decision. That requires cases, expected outcomes, and scoring outside this
module.

`CallRecord` does not store the response text, the next prompt, or the
stopping reason. `response_text_sha256` and `response_record_sha256` support
verification only if that evidence is kept elsewhere. The record alone cannot
be used to review the proposed next step.

## What not to change in place

Do not edit the pinned module to close these gaps.

Immutable manifest contents, a provider-identity check, a comparison against
the executing module’s version constants, and a required failure record are
candidates for core guarantees. They are not guarantees of rc1.

A transport-request contract, or a defined manifest-hash procedure, is an
architectural change. Under the freeze rule that is a new version and a new
module hash.

Until that version exists, treat rc1 as: one controller decision, with
fail-closed checks on the bytes and declarations this function actually
receives, assuming a trusted caller and a trusted adapter.
