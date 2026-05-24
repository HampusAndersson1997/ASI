# Codex CLI Tool

## Purpose

Use Codex CLI as a bounded sub-agent/tool for the measured ASI Kernel harness. This skill does not indicate actual AGI or ASI capability.

## Use When

- Inspect repo.
- Generate small files.
- Repair tests.
- Refactor limited scope.
- Write docs.

## Do Not Use When

- The task requires secrets.
- The task writes outside the sandbox.
- The task is broad, such as "improve everything".
- The task recursively invokes Codex without a depth limit.

## Procedure

1. Define a narrow task.
2. Define expected output files.
3. Define validation commands.
4. Run the wrapper.
5. Inspect output.
6. Run tests.
7. Log result.
8. Accept, revise, or roll back.
