# ARC-40D controller contract

Standalone. This note restates what `arc40d_core.py` implements. It is not
a second specification, and it does not depend on any other protocol. If it
disagrees with the module, the module wins.

## What one run is

`run_controller_call` executes exactly one provider call and returns one
`CallRecord`.

- `turn_index` is always `0`.
- A valid `CONTINUE` (`NEXT_PROMPT`) does not execute the next prompt.
- A valid `STOP` (`CHAIN_COMPLETE`) also ends the run.
- Either valid decision sets `run_end` to `DECISION_RECORDED`.
- Any other technical outcome sets `run_end` to `ABORTED`.
- `estimated_cost_usd` is always `None`. Cost belongs outside this module.

## Fail closed, before the provider

`validate_manifest` runs before `call_model`. It rejects the run when any
of these differ from the frozen manifest:

- condition is unknown, or the system-prompt SHA-256 does not match
- packet id is unknown, or the packet-text SHA-256 does not match
- `parser_version`, `runner_version`, `lockfile_hash`, or `price_table_hash`
- live `model_specs_hash`, or the runtime fingerprint's `model_specs_hash`
- installed SDK versions versus `manifest.sdk_versions`

The supplied `ModelSpec` must be the same object stored under
`model_specs[spec.family]`. After the call, `result.requested_model` must
equal `spec.model_id`.

## Terminal line

Exactly one nonblank line:

```text
NEXT_PROMPT: <one complete pasteable next prompt>
```

or:

```text
CHAIN_COMPLETE: <concise stopping reason>
```

Rejected: extra nonblank lines, a malformed line, an empty payload, or a
payload that itself contains `NEXT_PROMPT:` or `CHAIN_COMPLETE:`.

## Status precedence

Visible text is not scored if the call already failed technically:

1. `result.error` → `PROVIDER_ERROR`
2. `result.refusal` → `REFUSAL`
3. `result.truncated` → `TRUNCATED`
4. parser failure → `INVALID_OUTPUT`
5. otherwise → `SUCCESS`, and `decision` is `CONTINUE` or `STOP`

A truncated, refused, or failed response is not a valid controller
decision even if its text looks like a terminal marker.

## What this module does not do

- It does not call a provider. The caller supplies `call_model`.
- It does not chain prompts.
- It does not price a call.
- It does not define how `manifest_sha256` is computed. The field is stored
  on the manifest; this module does not re-hash the manifest object.
