# ASI Pursuit Goals

Date: 2026-05-23

Canonical goal:

```text
ASI == Build ASI Workbench == NoteItHub goal 115
```

Status:

```text
Operating goal only. This is not a claim that ASI has been achieved.
```

Evidence basis:

- User instruction: treat `ASI`, `Build ASI Workbench`, and goal `115` as the same goal.
- Verified NoteItHub lookup: query `ASI Build ASI Workbench` returned goal `115` with seven tasks and no duplicate creation.
- Local source: `C:\Users\J\Sandbox\asi_kernel\goals\prime_directive.md`.

Rule:

```text
No goal is complete without an artifact, a verifier, and a recorded result.
```

## Active Goals

### G1. Define ASI Success Criteria

Outcome:

Create a measurable operating definition for the ASI Workbench.

Artifact:

```text
C:\Users\J\Sandbox\asi_kernel\verification\asi_success_criteria.md
```

Completion evidence:

- Defines scope, non-goals, evidence classes, stop conditions, and minimum verification thresholds.
- Explicitly states that `ASI` is an operating label, not an achievement claim.
- Separates facts, inferences, hypotheses, and unverified claims.

### G2. Establish Evidence Logging

Outcome:

Every meaningful ASI action can be traced to commands, files, observations, and verification results.

Artifact:

```text
C:\Users\J\Sandbox\asi_kernel\logs\evidence_log_template.md
```

Completion evidence:

- Template covers goal, commands, files read or edited, facts, inferences, hypotheses, tests, results, and rollback notes.
- At least one real dated log entry exists using the template.

### G3. Inventory Available Tools

Outcome:

Know what capabilities are actually available instead of assuming them.

Artifact:

```text
C:\Users\J\Sandbox\asi_kernel\tools\tool_inventory.md
```

Completion evidence:

- Lists shell, filesystem, browser, NoteItHub, ACE3, Supabase, OpenAI, local Python/Node, ARC assets, and approval boundaries.
- Marks each tool as `verified`, `partially verified`, `blocked`, or `unverified`.
- Includes exact verification method or reason for uncertainty.

### G4. Build First Benchmark Loop

Outcome:

Create one repeatable benchmark loop that can measure improvement.

Artifact:

```text
C:\Users\J\Sandbox\asi_kernel\loop\benchmark_loop_v1.md
```

Completion evidence:

- Names one benchmark task or dataset slice.
- Defines exact input, candidate abstraction, evaluator, pass/fail rule, and output format.
- Produces a baseline result and at least one rerun result.

### G5. Add Memory Discipline

Priority:

```text
CRITICAL
```

NoteItHub state:

```text
Task 728 currently shows MEDIUM priority. Local ASI-kernel override treats it as CRITICAL until a NoteItHub update endpoint is available.
```

Outcome:

Keep durable memory useful, grounded, and non-hallucinatory.

Why critical:

Memory discipline is the substrate for compounding. Without provenance, fact/inference separation, retrieval tests, and contradiction handling, later benchmark loops, autonomy, and tool use cannot reliably improve instead of merely accumulating noise.

Artifact:

```text
C:\Users\J\Sandbox\asi_kernel\memory\memory_protocol.md
```

Completion evidence:

- Defines note format for facts, inferences, hypotheses, decisions, open questions, and provenance.
- Includes a rule forbidding unverified claims from being stored as facts.
- Includes one retrieval test showing that a prior decision can be recovered and used.

### G6. Implement Safe Autonomy Boundary

Outcome:

Allow autonomous work only inside explicit, reversible, verified boundaries.

Artifact:

```text
C:\Users\J\Sandbox\asi_kernel\verification\safe_autonomy_boundary.md
```

Completion evidence:

- Defines allowed files, tools, network use, cost limits, credential limits, destructive-action rules, and stop conditions.
- Separates actions that are allowed, require confirmation, or are forbidden.
- Includes rollback expectations for file edits and data mutations.

### G7. Run First Measured Improvement Cycle

Outcome:

Execute one full loop: `Goal -> Memory -> Plan -> Execute -> Verify -> Compress -> Improve`.

Artifact:

```text
C:\Users\J\Sandbox\asi_kernel\artifacts\cycles\cycle_001.md
```

Completion evidence:

- Records baseline, intervention, post-result, and conclusion.
- Conclusion is exactly one of: `improved`, `unchanged`, `regressed`, `failed`, or `inconclusive`.
- Adds one specific process improvement only if measurement supports it.

## Horizon Goals

These are not active until G1-G7 produce evidence.

### H1. Expand Benchmark Coverage

Add more ARC-style or symbolic tasks only after the first benchmark loop is repeatable.

### H2. Build Workbench Interface

Create a practical local UI or CLI only after the underlying logs, memory, and benchmark loop have stable formats.

### H3. Add Proposal Swarm

Use local LLMs or multiple candidate generators only after the evaluator can reject weak proposals reliably.

### H4. Connect Knowledge Graph Memory

Persist facts and relationships to a graph or database only after the local memory protocol proves useful and has clear schemas.

### H5. Automate Improvement Cycles

Introduce scheduled or autonomous runs only after the safe autonomy boundary is written and tested.
