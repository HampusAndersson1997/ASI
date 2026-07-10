# AGENTS.md

## Scope and precedence

This file governs the entire repository. A deeper `AGENTS.md` may refine instructions for its subtree, but may not weaken root safety, evidence, secret, held-out, replay, or capability-claim requirements.

Apply instructions in this order:

1. Platform and system safety requirements
2. Explicit user instructions
3. Nearest applicable `AGENTS.md`
4. This root file
5. Task specifications, schemas, policies, and execution plans
6. Current code, tests, and repository conventions
7. General engineering defaults

When instructions conflict, follow the higher-precedence rule. Do not guess. Stop before unsafe, destructive, irreversible, or externally consequential action and report the exact conflict.

## Fresh-session discovery

Before modifying files in a fresh session:

1. Read this file and all deeper applicable `AGENTS.md` files.
2. Inspect `git status`; preserve user changes.
3. Read the nearest README, task spec, policy, schema, tests, and entry points.
4. Discover actual Python, Node, Docker, benchmark, evaluator, replay, and environment commands from repository files.
5. Identify the authoritative implementation, evaluator, baseline, development set, held-out boundary, expected artifacts, and safety boundary.
6. Define a verifiable target before coding.

For non-trivial work, record:

```text
Goal:
Observed baseline:
Applicable instructions:
Authoritative implementation:
Evaluator:
Development data:
Held-out data:
Expected files:
Verification commands:
Pass condition:
Non-goals:
Safety boundaries:
Rollback:
```

Do not assume a path, dependency, service, model, dataset, command, or capability exists because documentation mentions it.

## Missing-skill fallback

Search applicable `skills/`, documentation, scripts, and deeper instructions before using a specialized workflow.

When the required skill is absent:

1. Do not invent repository-specific behavior.
2. Use the smallest safe generic workflow.
3. Prefer read-only inspection and dry runs.
4. Define explicit inputs, outputs, invariants, limits, and stop conditions.
5. Reuse existing schemas and utilities.
6. Mark repository assumptions `UNVERIFIED`.
7. Do not add a reusable abstraction unless the task requires it.
8. Report the missing skill when it limits confidence.

A missing skill never permits skipping validation or safety controls.

## Mission and claim boundary

This repository is an evidence-driven ARC/ASI research and engineering workbench.

```text
Goal -> Memory -> Plan -> Execute -> Evaluate -> Verify -> Compress -> Improve
```

The objective is verified capability compounding through reproducible artifacts, fixed evaluators, held-out tests, and bounded experiments.

`ASI`, `AGI`, `intelligence`, `reasoning`, `autonomy`, and `world model` are project or research labels, not achievement claims.

Never claim that this repository, an agent, or a model has achieved AGI, ASI, general intelligence, autonomous self-improvement, self-awareness, broad understanding, or production safety.

Claims must remain narrow and evidence-scoped:

```text
The candidate improved exact-grid accuracy from X to Y on benchmark B,
using evaluator V, environment E, dataset hash H, and seed S.
```

## Evidence law

```text
No claim without evidence.
No action without traceability.
No improvement without a fixed evaluator.
No success from training or development performance alone.
No hidden-answer leakage.
No hallucinated completion.
```

A meaningful completed change requires:

1. **Artifact** — code, test, schema, benchmark result, replay, report, or decision record.
2. **Verifier** — test, evaluator, invariant check, replay, or explicit review gate.
3. **Recorded result** — enough evidence to reproduce or audit the conclusion.

Classify statements as:

- `OBSERVED` — directly read or measured
- `INFERRED` — derived from observations
- `HYPOTHESIS` — plausible but untested
- `DECISION` — selected action and rationale
- `UNVERIFIED` — requires evidence

Never store inference, generated output, model self-report, or hypothesis as observed fact.

## Secrets and private data

Never read, print, summarize, transmit, commit, or log:

- `.env` or `.env.*`
- credentials, API keys, tokens, cookies, private keys, or certificates
- service-role keys
- unnecessary personal data
- private datasets or model weights outside approved scope
- secrets embedded in shell history, process arguments, Docker layers, or artifacts

Use `.env.example`, mocks, fixtures, schemas, and secret-name placeholders. If a task requires a secret, use an approved injection mechanism without inspecting the value.

Never weaken ignore rules, redaction, credential scanning, or secret boundaries to obtain a pass.

## Live-service boundary

Assume external services are live and consequential unless proven to be disposable local fixtures.

Without explicit authorization, do not:

- contact hosted databases or paid APIs
- send email or messages
- mutate cloud resources
- deploy
- change accounts, permissions, DNS, tunnels, or infrastructure
- upload data or download models/datasets
- start externally reachable servers
- write to production or shared environments

Prefer unit tests, mocks, temporary local databases, recorded fixtures, dry runs, and read-only checks.

When live access is authorized, identify the service and environment, distinguish reads from writes, minimize scope, set timeouts and bounded retries, capture non-secret evidence, define rollback, and never broaden authorization.

A mocked or local pass is not proof of live integration success.

## Docker boundary

Treat Docker as privileged execution affecting filesystems, networks, images, and persistence.

Before Docker execution, inspect the Dockerfile, Compose file, entrypoint, mounts, network, ports, secrets, capabilities, and runtime user.

Without explicit authorization, do not run builds, pulls, containers, Compose stacks, privileged mode, Docker socket mounts, host networking, broad host mounts, public ports, persistent volumes, root containers where avoidable, or cleanup commands.

When authorized:

- pin versions or digests where practical
- use read-only mounts
- set CPU, memory, process, and time limits
- disable network when unnecessary
- avoid persistence
- record exact commands and resource IDs
- clean up only resources created by the task

## Unsafe execution boundary

Generated, downloaded, untrusted, or model-proposed code is data until inspected and validated.

Forbidden by default:

- arbitrary shell strings
- `eval`, `exec`, or untrusted dynamic imports
- shell interpolation of model output
- unsanitized command construction
- unbounded subprocesses or recursive agent spawning
- destructive filesystem commands
- privilege escalation or disabled security controls
- writes outside the repository or task-owned temporary directories

Subprocesses must use argument arrays, explicit executables, fixed working directories, allowlisted environments, timeouts, bounded output, checked return codes, safe logging, path/flag validation, and child termination on timeout.

## Architecture invariants

### Python ownership

Python is the default owner of:

- ARC environments, tasks, transitions, and replay
- scientific and benchmark logic
- evaluators and scoring
- experiment orchestration
- dataset validation
- world-model research logic
- evidence and artifact generation

Keep domain logic importable and testable. CLI entry points must be thin wrappers. Do not hide core semantics in notebooks, shell scripts, dashboards, or generated files. Make randomness explicit through seeds or injected RNGs.

### Node/TypeScript ownership

Node/TypeScript is the default owner of:

- MCP, HTTP, and process-boundary adapters
- transport validation
- interface schemas
- bounded command dispatch
- service lifecycle code

Node must not duplicate Python ARC transitions, evaluator, scoring, replay, or world-model semantics. Cross-language behavior must use a versioned validated contract.

At process boundaries, validate input and output, preserve structured errors, enforce time and size limits, and never infer semantic success from process exit alone.

### Cross-language contract

Each Python/Node boundary must define:

```text
schema_version
request_id
operation
inputs
limits
result
error
evidence
```

Breaking schema changes require a version change and compatibility tests. Exactly one component owns semantics; the other transports or adapts them.

### World-model separation

The authoritative environment determines actual state transitions.

A world model may predict next state, rank actions, estimate uncertainty, propose abstractions, or generate hypotheses. It must not redefine what happened.

Keep separate:

1. `observation`
2. `belief_state`
3. `predicted_transition`
4. `executed_action`
5. `observed_transition`
6. `evaluation`

Never overwrite observations with predictions. Train or update world models from recorded transitions, not hidden evaluator answers. World-model claims require held-out predictive evaluation against an explicit baseline.

### State and transition invariants

State must be schema-versioned, serializable, canonically encodable or hashable, independent of memory addresses, explicit about task/episode/step/environment version, and free of hidden mutable global state.

Transitions must not mutate input state unless explicitly documented and tested. Record seed, RNG source, environment version, configuration, action order, and relevant dependency versions for nondeterminism.

## Evaluator-first experiments

Define the evaluator before optimizing the candidate.

Before an experiment:

1. State the hypothesis.
2. Freeze target behavior.
3. Identify the baseline.
4. Define metrics and failure conditions.
5. Define development data.
6. Seal held-out data.
7. Record evaluator version and configuration.
8. Set budget and stop conditions.
9. Define allowed result labels.

Candidate generation and evaluation must be independent. Evaluator failure is experiment failure, not candidate success.

Changing evaluator, parser, prompt set, scoring rule, timeout, environment, decoder, or action semantics is an instrument change. Version it, re-evaluate baseline and candidate under the same instrument, preserve old results, and do not call instrument-only score movement model improvement.

## Held-out and regression protocol

Development and held-out data must be separated.

Held-out data must not be copied into training, included in examples, used for architecture selection, repeatedly debugged against, exposed to proposal agents, or used to tune prompts, thresholds, seeds, or stopping rules.

```text
train/develop -> evaluate on development -> freeze candidate
-> one bounded held-out evaluation -> record result
```

After held-out failure, develop from development examples, synthetic examples, non-answer-revealing failure categories, or a new future held-out set.

Every improvement claim must record baseline ID, candidate ID, development-data hash, held-out identifier/hash, evaluator version, environment version, model revision where relevant, seed, decoding settings, raw artifacts, aggregate metrics, and regression results.

Regression suites must include prior solved cases, known failures, schema checks, and safety invariants. Development improvement with held-out or regression degradation is not a pass.

## ARC action validation

Validate every ARC action against the authoritative current state before execution.

Each action record must contain or reference:

```text
episode_id
task_id
environment_version
step_index
action_schema_version
action_type
action_parameters
pre_state_hash
available_actions_hash or action_space_version
seed or deterministic context
```

Validation must check schema version, required fields, exact types, action membership, parameter ranges, grid/coordinate bounds, coordinate convention, current availability, episode/step consistency, pre-state hash, and terminal-state restrictions.

Reject invalid actions before mutation. Never silently clip, coerce, default, reinterpret coordinates, substitute another action, or count rejection as a transition.

After execution, record:

```text
executed_action
post_state_hash
observation_hash
reward_or_score_delta
terminal
success
error
deterministic_sequence_id or timestamp
```

An action is executed exactly once only when the authoritative environment returns a transition record.

## ARC replay

Every scored interactive ARC episode must be replayable from an immutable trace containing task/environment version, initial-state hash, seed/configuration, ordered validated actions, per-step pre/post hashes, observation hashes, reward/score deltas, terminal/success flags, evaluator version, and trace schema version.

Replay must:

1. Initialize the same task/environment version.
2. Verify initial-state hash.
3. Revalidate each action.
4. Apply actions in exact order.
5. Compare every pre-state, post-state, observation, reward, and terminal field.
6. Stop at first divergence and record mismatching step/fields.
7. Verify final state and evaluator result.

Matching only the final state is insufficient.

Replay labels:

- `PASS` — every required step and final check matches
- `FAIL` — deterministic divergence or invalid trace
- `INCONCLUSIVE` — exact replay impossible because required state, seed, version, or context is missing
- `NOT_RUN` — replay not executed

Do not report interactive ARC results as verified unless replay is `PASS`.

## Minimal engineering workflow

Before coding:

- inspect instructions and working tree
- identify authoritative code and evaluator
- reproduce baseline
- define the smallest passing change
- identify safety and held-out boundaries

During coding:

- touch only required files
- match existing style
- avoid unrelated formatting/refactors
- add no speculative features
- add no unnecessary abstraction
- remove only code made obsolete by this change
- preserve user changes
- keep generated files generated
- keep runtime artifacts out of source directories

Bug fixes require a reproducing failing test, minimum fix, passing targeted test, relevant regressions, and diff inspection.

Refactors require before/after behavior checks using the same tests.

Performance or capability changes require a baseline, frozen evaluator/inputs, controlled variable change, identical rerun conditions, raw and aggregate comparison, held-out checks, regressions, and narrow conclusions.

## Repository commands

Commands are current known entry points, not substitutes for discovery. Run only commands relevant to the changed subtree.

### ASI kernel tests

From `asi_kernel/`:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q
```

Fallback:

```powershell
python -B -m pytest -p no:cacheprovider -q
```

Targeted wrapper tests:

```powershell
python -m pytest tests\test_codex_cli_wrapper.py tests\test_codex_phase2.py -q
```

Unit tests must not read `.env`, use network, call live services, invoke real Codex delegation, require local model weights, or leave persistent output outside test-owned paths.

### ARC smoke benchmark

From `asi_kernel/`:

```powershell
.\.venv\Scripts\python.exe benchmarks\arc_agi_2\run_solver.py --suite smoke
.\.venv\Scripts\python.exe benchmarks\arc_agi_2\score.py --latest
```

Runner exit is not a passing score; the scorer is separate.

### Dashboard

```powershell
.\.venv\Scripts\python.exe dashboards\progress_report.py
```

A dashboard summarizes evidence; it does not create or override raw evidence.

### Bounded Codex dry run

```powershell
.\.venv\Scripts\python.exe tools\codex_cli\run_codex_exec.py --task tools\codex_cli\codex_task_template.json --dry-run
```

Do not run real delegated execution during unit tests.

### Local LLM tests

From the Arch WSL `local_llm/` environment:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Training, bootstrap, model download, and full inference require explicit authorization.

### Node/TypeScript MCP checks

From repository root:

```powershell
npm --prefix chatgpt-arch-mcp run typecheck
npm --prefix chatgpt-arch-mcp run build
```

The current `npm test` script states that tests do not exist. Do not count it as behavioral verification.

## Bounded autonomy

Autonomous work requires one objective, allowlisted paths/tools, fixed budget, timeout, maximum cycles, evaluator, stop conditions, reversible output, and human-review boundary.

Default autonomous output is a proposal or patch artifact, not an automatically applied change.

Stop when budget/cycles expire, evaluator cannot run, evidence conflicts, failures repeat without new evidence, policy blocks the next action, held-out data would be exposed, metric changes would replace behavior improvement, or rollback is unavailable.

Do not turn a bounded task into open-ended research.

## Self-modification boundary

Changes to agent instructions, prompts, evaluators, safety policies, tool allowlists, command validators, memory rules, benchmark definitions, autonomy limits, patch application, or agent launchers are self-modification-sensitive.

They require explicit task authorization, rationale, tests, before/after comparison, regressions, and human review before activation.

An agent must not relax its constraints, expand permissions, increase budget, hide evidence, or alter evaluators to obtain a pass. Self-modification never auto-approves itself.

## Subagent contract

Every subagent task must define:

```text
Objective:
Allowed paths:
Forbidden paths:
Allowed tools:
Inputs:
Expected artifact:
Evaluator:
Verification commands:
Budget:
Timeout:
Maximum cycles:
Stop conditions:
Required report:
```

Subagents must read instructions, stay in scope, preserve user changes, return evidence rather than confidence, distinguish observations from inference, report commands and tests not run, and avoid commits, pushes, deployments, and live writes unless authorized.

The parent agent must review every changed file, validate claims, independently check verifiers, resolve conflicts, and reject unsupported conclusions.

Do not combine subagent answers by confidence, eloquence, or majority vote. Use an independent evaluator. Proposal agents must not receive hidden answers.

## Git boundaries

Unless explicitly requested, do not commit, branch, push, open/merge PRs, rewrite history, change repository settings, delete untracked files, or discard user changes.

Before completion, inspect the diff, map every changed line to the task, remove only task-created temporary changes, and disclose unrelated pre-existing changes without modifying them.

## Completion evidence

Every task must use exactly one result:

- `PASS`
- `FAIL`
- `INCONCLUSIVE`
- `NOT_RUN`

Use `PASS` only when required behavior exists, required tests/evaluators ran, pass conditions and regressions succeed, safety and held-out rules were followed, ARC replay passes when applicable, evidence exists, and no unrelated changes are known.

Use `FAIL` when a required verifier fails, an invariant is violated, replay diverges, held-out/regression criteria fail, or requested behavior is absent.

Use `INCONCLUSIVE` when evidence is insufficient/contradictory, the evaluator is invalid or incompatible, required versions/seeds/state/artifacts are missing, nondeterminism prevents comparison, only development evidence exists for a held-out claim, or a live integration was not exercised.

Use `NOT_RUN` when the relevant verifier was not executed. State why. Inspection or confidence cannot convert `NOT_RUN` into `PASS`.

## Final adherence verification

Before final response:

1. Re-read root and applicable deeper `AGENTS.md` files.
2. Inspect final diff.
3. Confirm every changed file is in scope.
4. Confirm no user changes were discarded.
5. Confirm no secrets were read or emitted.
6. Confirm no unauthorized live-service, Docker, network, or unsafe execution occurred.
7. Confirm evaluator and held-out boundaries.
8. Confirm ARC action and replay requirements when applicable.
9. Run required verifiers or report `NOT_RUN`.
10. Confirm claims are no broader than evidence.
11. Report exact commands and outcomes.

If adherence cannot be verified, the result cannot be `PASS`.

## Final report

```text
STATUS: DONE | BLOCKED | NEEDS_VERIFICATION | FAILED
RESULT: PASS | FAIL | INCONCLUSIVE | NOT_RUN

Goal:
- <verifiable target>

Scope:
- <paths and applicable instructions>

Changed:
- <path>: <direct reason>

Verification:
- `<exact command>` -> PASS | FAIL | NOT_RUN

Evaluation:
- baseline:
- candidate:
- evaluator version:
- development data:
- held-out data:
- regression:
- replay:

Evidence:
- <artifact paths, hashes, run IDs, or observations>

Safety:
- secrets:
- live services:
- Docker:
- unsafe execution:

Limitations:
- <remaining uncertainty or "None known">

Next required action:
- <one action or "None">
```

Keep reports factual and compact. Confidence is not evidence.
