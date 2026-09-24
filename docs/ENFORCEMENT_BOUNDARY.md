# Enforcement boundary

Reviewed against commit `5a6a524`. Rechecked against the pinned file
`arc40d_core.py` (`ARC40D_CORE_v1.0-rc1`, SHA-256
`5212f2817f145997db35ca8e3852682c091572b9106ce0c3786e8598134b95e0`).

The pinned bytes stay. This note states what those bytes do. It does not
withdraw a claim that is still written in the module. Describing a narrower
scope does not turn a broken claim into a future feature.

The supplied conformance suite is 9 tests, and those 9 passed. They do not
cover the gaps below. No model benchmark was run. The probes use a mock
adapter.

rc1, under this note, checks that supplied configuration values agree and
records a syntactically valid controller decision. That scope assumes a
trusted caller and a trusted adapter. It is useful and testable. The
implementation limits below are still in the file.

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

That distinction is what rc1 establishes in practice. It is not a rewrite of
the claims in the pinned module. Those claims are classified below.

## Confirmed gaps

These behaviors are in the pinned core. The class of each one is in the
classification section, not in this table.

| Finding | What was rechecked | Implication |
|---|---|---|
| Manifest contents are mutable. | Replacing `manifest.instruction_hashes["DIRECT_POLICY"]` let a different prompt run. `manifest_sha256` stayed the same. | `frozen=True` stops field reassignment. It does not make the dictionaries deeply immutable. The open question is the module's frozen-manifest promise, not the decorator by itself. |
| Provider identity is unchecked. | An adapter returning `provider="wrong-provider"` was `SUCCESS` when `requested_model` matched `spec.model_id`. | A reported provider mismatch is accepted. |
| Runtime versions are compared, not established. | The same invented parser and runner strings on both the manifest and the runtime passed `validate_manifest`. | The check is agreement between supplied strings. It does not compare them with `PARSER_VERSION` or `RUNNER_VERSION`. |
| Exceptions escape without a record. | An adapter raising `TimeoutError` produced no `CallRecord`. | Scoring stops. Structured failure accounting needs an outer harness. |
| Attempt metadata is unvalidated. | `attempts=0` and an empty attempt log, with a valid terminal line, was `SUCCESS`. | A successful record can carry contradictory execution metadata. |
| The adapter is not bound to `ModelSpec`. | `call_model` receives only the message list. | Hashing `ModelSpec` fixes the declared configuration. It does not prove the adapter used it. |
| `request_sha256` is pre-adapter. | The adapter changed the system message after receipt. The record stayed `SUCCESS` and kept the hash of the original messages. | The core hashes the messages it hands over. It does not hash the request a provider received, and it does not include provider-specific settings. |
| A missing package matches `""`. | `get_live_sdk_versions` returns `""` when a package is not installed. A manifest that expected `""` passed. | The gap is only that case. A manifest that expects a real version already fails when the package is absent. |

`manifest_sha256` is the clearest external responsibility. The field is
stored, the runner never recomputes it, and this repository already said so.
`lockfile_hash` and `price_table_hash` are likewise caller-supplied strings.
A defined manifest-hash scope would still be a new version. It is not an
undisclosed hole in rc1.

## Freeze rule

The module permits a change for a conformance-test failure, or for a
hash-changing defect that breaks a claimed invariant. Any other architectural
change needs a new version.

Two different situations:

| Situation | What the rule allows |
|---|---|
| An existing claim is violated | A defect fix is permitted. The module hash changes and must be recorded again. |
| A responsibility that was outside the core becomes a core guarantee | A versioned contract change. Not an rc1 patch. |

Writing this note is the first kind of documentation. It is not the second
kind of permission. Narrower wording here does not reclassify a violation of
a claim that remains in `arc40d_core.py`.

## Classification

| Finding | Claim already in the pinned module | Class |
|---|---|---|
| Manifest dicts can be edited in place. | The runner says it validates a frozen manifest. `dataclass(frozen=True)` only stops assignment to the field. Deep immutability is not what the decorator guarantees. | Possible defect fix, if the claim is the frozen-manifest promise. Not a defect in the decorator. Not repaired in these bytes. |
| An absent package satisfies expected version `""`. | "Exact SDK environment." A missing package becomes `""`. | Possible defect fix for that one match. If the manifest expects a real version, a missing package already fails. Not repaired in these bytes. |
| Parser and runner strings are not read from this module. | The runner comment says validate actual runtime. The signature takes a caller-built `RuntimeFingerprint`. Only SDK versions are read from the environment. | Unresolved. Do not file it as a new-version feature only because this note calls the check an agreement. |
| `result.provider` is not compared with `spec.provider`. | `requested_model` is the named source of truth, and a conformance test covers that mismatch. `validate_manifest` also says "any configuration mismatch." | Not explicitly guaranteed at the core boundary. The broader sentence leaves interpretive tension. Not conclusively outside every existing claim. |
| An adapter exception produces no `CallRecord`. | Pre-call mismatches raise, and the suite expects those raises. The same "any configuration mismatch" sentence does not say every failure becomes a record. | Not explicitly guaranteed at the core boundary. Not conclusively settled as a non-guarantee. |
| `attempts=0` with an empty log can still be `SUCCESS`. | `SUCCESS` is defined as the technical flags plus one valid terminal line. No separate attempt-consistency rule is stated. | Not explicitly guaranteed at the core boundary. |
| `call_model` is not given `ModelSpec`, and `request_sha256` is the message list from before the adapter runs. | Execution controls must be bound into `model_specs_hash`. The hash is of the mapping supplied to the run. The "exact provider request" constructed here is the message list. | Versioned contract change. This is the v1.1 priority below. |
| `manifest_sha256` is stored and never recomputed. | Already documented. The field is stored. No code claims to calculate it. | External responsibility. Clearer than the open cases above. A defined hash scheme is still a new version. |

## v1.1 priority

The strongest v1.1 objective is to bind the declared model configuration to
the request the adapter actually submits. That connects configuration
provenance to actual execution.

rc1 hashes the `ModelSpec` it was given, then hands the adapter only
messages. Temperature, token limit, reasoning effort, timeout, API mode, and
any later mutation of those messages are outside the hash. Closing that gap
is a new contract, not an in-place reading of rc1. The questions above stay
recorded on the pinned candidate.

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

## What this note does not do

It does not patch `arc40d_core.py`. The pin remains
`5212f2817f145997db35ca8e3852682c091572b9106ce0c3786e8598134b95e0`.

It does not forbid a later fix, under the freeze rule, for a claim the
pinned file already makes and does not keep. That fix would replace the pin.

It does not decide provider identity, attempt-log consistency, or exception
accounting. Those are not explicitly guaranteed at the core boundary.
"Any configuration mismatch" still leaves interpretive tension, so this note
does not close them as non-guarantees.

The manifest self-hash is different. Omission of a recomputed
`manifest_sha256` is already documented, and it stays an external
responsibility.

Shallow freezing and the `""` SDK match stay possible defect fixes on the
grounds above. rc1 remains pinned with those questions recorded.
