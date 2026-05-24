# ASI Kernel Checkpoint

Date: 2026-05-21
Project: ASI Kernel
Supabase project ID: ashjuqtkgsgeusvgozrw
Region: eu-west-1
Last verified project status: ACTIVE_HEALTHY

## Verified

- Supabase project exists and was verified ACTIVE_HEALTHY.
- Public tables verified earlier with RLS enabled: memories, claims, experiments, benchmarks, artifacts, agent_runs.
- Prime Directive saved to public.artifacts and public.memories.
- Prime Directive memory ID: 9c7f1be0-feb3-4620-9638-819a51d81c17.
- Local ASI Kernel memory saved and duplicate cleanup verified.
- Surviving local bootstrap memory ID: 8319257a-cf6c-4e4f-ae1b-fcbe0c840f2f.
- Local save_memory.py works with UTF-8 BOM-safe .env loading.
- save_memory.py dedupe verified locally by save_memory_skipped_duplicate against memory ID 8319257a-cf6c-4e4f-ae1b-fcbe0c840f2f.

## Known local path

C:\Users\J\Sandbox\asi_kernel

## Current tool state

- tools\python\save_memory.py: working, dedupe-capable, JSONL action logging.
- logs\agent_actions.jsonl: contains failure history, success inserts, and dedupe skip evidence.

## Next planned ARC work

- Create / verify arc_agi_2\object_extractor.py.
- Run python .\arc_agi_2\object_extractor.py --self-test.
- Only after self-test passes, save ARC object extractor memory.
- Then build object_stats_report.json.
- Then extract H-ARC error priors.
- Then build first symbolic DSL solver.

## Prime Directive

Goal -> Memory -> Plan -> Execute -> Verify -> Compress -> Improve

## Law

No claim without evidence.
No action without logging.
No improvement without measurement.
No hallucinated success.
