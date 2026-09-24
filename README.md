# ARC40D-CORE

![Version: v1.0-rc1](https://img.shields.io/badge/version-v1.0--rc1-2563EB)
![Status: frozen](https://img.shields.io/badge/status-FROZEN-B45309)
![Scope: standalone](https://img.shields.io/badge/scope-standalone-374151)
![Decisions: one](https://img.shields.io/badge/controller-single%20decision-0F766E)
[![License: MIT](https://img.shields.io/badge/license-MIT-6B7280)](LICENSE)

> **One decision. Do not score a cut-off reply as a stop.**

You are comparing how models decide whether to keep investigating or stop.
A reply can be cut off after it has already produced a valid-looking stop
marker. Scoring that marker as an intentional decision distorts the
experiment.

ARC40D-CORE keeps that from happening inside one controller call. It
separates a reported technical failure from a valid terminal decision, and
it checks that the prompt and case you pass in match the experiment you
declared. It does not run the next prompt. It does not decide whether
stopping was the right scientific call.

It is standalone. Nothing outside this repository is required to read,
hash, or test the core.

rc1 checks agreement among values it is given. It catches a **reported**
`requested_model` that does not match the declared model id. It cannot
independently detect a model that was swapped silently: if the adapter
reports the expected id, the core accepts it. The adapter's transport
request is not proven here. See
[`docs/ENFORCEMENT_BOUNDARY.md`](docs/ENFORCEMENT_BOUNDARY.md).

## Try it without credentials

[`examples/mock_run.py`](examples/mock_run.py) builds a manifest, calls the
controller twice, and prints the decision and status. One adapter returns a
finished stop. The other returns the same text and reports that generation
was cut off.

```bash
PYTHONPATH=. python3 examples/mock_run.py
```

```text
stop: status=SUCCESS decision=STOP run_end=DECISION_RECORDED
truncated: status=TRUNCATED decision=None run_end=ABORTED
```

The truncated call is not a stop. The visible `CHAIN_COMPLETE` line is
ignored because the adapter set `truncated=True`.

The script constructs the manifest from the prompt and packet bytes, then
inspects the record:

```python
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
# record.call_status, record.decision, record.run_end
```

`manifest_sha256` in that example is a stored placeholder. rc1 does not
recompute it.

## What a real adapter must do

`call_model` receives only the messages. The core does not apply
`ModelSpec` and does not keep the response text.

A real adapter has to:

- Apply the declared settings itself: model id, provider, API mode,
  temperature, max output tokens, reasoning effort, and timeout.
- Report technical failure on the result: `truncated`, `refusal`, or
  `error`. A valid-looking marker must not be left unmarked when the
  generation did not finish.
- Report `requested_model` as the id that was actually requested. rc1
  rejects a reported mismatch. It cannot see a silent substitution.
- Keep the submitted request and the response text outside the record.
  The record stores hashes, not the next prompt or the stopping reason.

Until you write that adapter, a run only checks that the prompt, case, and
declared settings agree, and that the returned text is one valid terminal
line or a reported technical failure. It is not proof of what a provider
received. The mock script never calls a model. No provider adapter ships
in this repository.

The published example does not call a model. This repository is release
candidate 1. The module hash below is the pin.

## Freeze pin

| Object | SHA-256 |
|---|---|
| [`arc40d_core.py`](arc40d_core.py) | `5212f2817f145997db35ca8e3852682c091572b9106ce0c3786e8598134b95e0` |

Verify the raw file, not a re-saved copy:

```bash
sha256sum arc40d_core.py
```

```powershell
Get-FileHash .\arc40d_core.py -Algorithm SHA256
```

The published file is 26657 bytes and has no trailing newline. See
[`release/HASHES.md`](release/HASHES.md).

## What a run records

| Outcome | `call_status` | `run_end` |
|---|---|---|
| One valid terminal line | `SUCCESS` | `DECISION_RECORDED` |
| Provider error, refusal, truncation, or bad output | not `SUCCESS` | `ABORTED` |
| Manifest, model-spec, requested-model, or listed-SDK mismatch | no record | exception before or after the call |
| Adapter exception (`TimeoutError` and anything else `call_model` raises) | no record | the exception propagates |

A valid line is exactly one of:

```text
NEXT_PROMPT: <one complete pasteable next prompt>
CHAIN_COMPLETE: <concise stopping reason>
```

`NEXT_PROMPT` is recorded as `CONTINUE`. `CHAIN_COMPLETE` is recorded as
`STOP`. Both end the controller run. Technical failure outranks text that
merely looks like a marker.

`estimated_cost_usd` stays unset. Pricing is outside this module.

## Layout

| Path | Role |
|---|---|
| [`arc40d_core.py`](arc40d_core.py) | Frozen module. Hash this. Do not restyle it. |
| [`examples/mock_run.py`](examples/mock_run.py) | Runnable manifest, mock adapter, and both outcomes. Not part of the pin. |
| [`conftest.py`](conftest.py) | Fixtures the in-module conformance tests require. Not part of the pin. |
| [`docs/CONTROLLER.md`](docs/CONTROLLER.md) | Restatement of the controller contract. |
| [`docs/ENFORCEMENT_BOUNDARY.md`](docs/ENFORCEMENT_BOUNDARY.md) | What rc1 actually checks, and which limits are still open. |
| [`release/HASHES.md`](release/HASHES.md) | SHA-256 pin and byte count. |
| [`LICENSE`](LICENSE) | MIT |

## Run the conformance suite

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The tests live inside the frozen module. Pytest is pointed at
`arc40d_core.py`. Fixtures supply a manifest whose instruction hash is
SHA-256 of `p` and whose packet hash is SHA-256 of `t`, matching the
strings those tests pass in. `sdk_versions` is empty so the suite does
not depend on installed provider packages.

## Changing the pinned file

Change `arc40d_core.py` only to fix a failing conformance test, or to fix
code that breaks a promise that file already makes. Either fix needs a new
SHA-256, published in place of the pin above.

Leave the file alone for renaming, formatting, or a new capability. Binding
the declared model settings to the request a provider actually receives is
a new version, not an edit of this one.

If this README and `arc40d_core.py` disagree, the module wins. Open
questions about that file are in
[`docs/ENFORCEMENT_BOUNDARY.md`](docs/ENFORCEMENT_BOUNDARY.md).

## What a successful record means

`SUCCESS` means the adapter returned one well-formed terminal line and did
not report a technical failure. It does not mean continuing or stopping was
the right decision. The record does not store the next prompt or the
stopping reason. Keep the response text yourself.

## License

[MIT License](LICENSE).
