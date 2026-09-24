# ARC40D-CORE

![Version: v1.0-rc1](https://img.shields.io/badge/version-v1.0--rc1-2563EB)
![Status: frozen](https://img.shields.io/badge/status-FROZEN-B45309)
![Decisions: one](https://img.shields.io/badge/controller-single%20decision-0F766E)
[![License: MIT](https://img.shields.io/badge/license-MIT-6B7280)](LICENSE)

> **One decision. Hash the request. Fail closed.**

ARC40D-CORE is the controller-only runner for an ARC-40D experiment.
It validates a frozen manifest, makes exactly one model call, and records
either a terminal decision or an abort. It does not execute `NEXT_PROMPT`.

The current object is **frozen at release candidate 1**. The module hash
below is the pin. This repository does not report an executed benchmark.

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
| Manifest, SDK, model-spec, or requested-model mismatch | no record | exception before or after the call |

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
| [`conftest.py`](conftest.py) | Fixtures the in-module conformance tests require. Not part of the pin. |
| [`docs/CONTROLLER.md`](docs/CONTROLLER.md) | Restatement of the controller contract. |
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

## Freeze rule

After the module SHA-256 above:

Permitted changes to `arc40d_core.py`:

- fix a conformance-test failure
- fix a newly discovered hash-changing defect that breaks a claimed invariant

Not sufficient:

- naming preference
- stylistic cleanup
- refactoring without a demonstrated defect
- convenience features
- architectural experimentation

Any intentional architectural change requires a new version and a new hash.

## Claim boundary

This repository publishes the controller core and its fail-closed checks.
It does not establish that a model followed the instruction, that a
benchmark was executed, or that a research claim was confirmed.

## License

[MIT License](LICENSE).
