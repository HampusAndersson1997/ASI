# Memory Protocol

Date: 2026-05-23

Purpose:

```text
Prevent hallucinated claims from becoming working memory.
```

Rule:

```text
Memory stores evidence state, not belief.
```

## Evidence Classes

### Fact

Definition:

```text
Observed claim with source, timestamp, and verifier.
```

Required fields:

```text
id:
status: fact
claim:
source:
observed_at:
verifier:
scope:
expires:
```

Use as premise:

```text
yes, inside scope and before expiry
```

### Inference

Definition:

```text
Claim derived from facts by an explicit rule.
```

Required fields:

```text
id:
status: inference
claim:
premises:
rule:
confidence:
observed_at:
verifier:
```

Use as premise:

```text
only when premises remain valid and confidence threshold is met
```

### Hypothesis

Definition:

```text
Plausible claim without enough evidence.
```

Required fields:

```text
id:
status: hypothesis
claim:
why_possible:
test:
stop_condition:
```

Use as premise:

```text
no
```

### Unknown

Definition:

```text
Claim not checked or not checkable yet.
```

Required fields:

```text
id:
status: unknown
claim:
missing_evidence:
next_check:
```

Use as premise:

```text
no
```

### Refuted

Definition:

```text
Claim contradicted by evidence.
```

Required fields:

```text
id:
status: refuted
claim:
counterevidence:
observed_at:
verifier:
```

Use as premise:

```text
no, except as negative evidence
```

## Storage Rules

1. No source, no fact.
2. No verifier, no fact.
3. No timestamp, no fact.
4. No scope, no fact.
5. No test, no hypothesis.
6. Conflicting facts require quarantine until resolved.
7. Expired facts demote to `unknown` until rechecked.
8. Summaries inherit weakest source status.
9. User preference can be a fact about preference, not a fact about reality.
10. Current external state must be reverified before use.

## Compact Record Format

Use one record per atomic claim:

```text
[id] status | claim | source | verifier | time | scope | expires
```

Example:

```text
M001 fact | ASI == Build ASI Workbench == NoteItHub goal 115 | C:\Users\J\Sandbox\asi_kernel\goals\pursuit_goals.md | Select-String readback | 2026-05-23 | local ASI goal mapping | until NoteItHub state changes
```

## Quarantine

Put weak or conflicting memory here:

```text
C:\Users\J\Sandbox\asi_kernel\memory\quarantine\
```

A quarantined claim can leave quarantine only after:

```text
source + verifier + timestamp + scope
```

## Retrieval Test 001

Question:

```text
Can system recover canonical ASI goal mapping with evidence?
```

Expected answer:

```text
ASI == Build ASI Workbench == NoteItHub goal 115
```

Observed evidence:

```text
C:\Users\J\Sandbox\asi_kernel\goals\pursuit_goals.md records the canonical mapping and prior verified NoteItHub lookup.
```

Verifier:

```text
Select-String readback on 2026-05-23 found:
- Canonical goal
- ASI == Build ASI Workbench == NoteItHub goal 115
- Verified NoteItHub lookup returned goal 115 with seven tasks and no duplicate creation
```

Live NoteItHub recheck:

```text
blocked: Monthly credit limit reached. Upgrade your plan for more credits.
```

Result:

```text
pass for local retrieval; live external verification blocked
```

Memory record:

```text
M001 fact | ASI == Build ASI Workbench == NoteItHub goal 115 | C:\Users\J\Sandbox\asi_kernel\goals\pursuit_goals.md | Select-String readback | 2026-05-23 | local ASI goal mapping | until NoteItHub state changes
```

## Update Discipline

Before using memory:

```text
retrieve -> check status -> check expiry -> verify if needed -> act
```

After action:

```text
record command/tool -> record observation -> classify claim -> store or quarantine
```

Forbidden:

```text
Unverified claim -> fact
Inference -> fact
Hypothesis -> action premise
Summary without source -> memory
```
