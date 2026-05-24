from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from benchmark_proposals import FAILURE_TAXONOMY, compare, score_response
from common import extract_json_object, extract_json_object_with_reason, extract_single_json_object_with_reason, read_json, read_jsonl, write_json


REQUIRED_FIELDS = [
    "claim",
    "evidence",
    "proposal",
    "executable_abstraction",
    "verification_plan",
    "risk_boundary",
    "expected_result",
    "stop_condition",
]


def full_response(**overrides: str) -> str:
    payload = {
        "claim": "Measured claim only.",
        "evidence": "fact: local artifact exists.",
        "proposal": "Run the benchmark harness.",
        "executable_abstraction": "script: benchmark_proposals.py compare.",
        "verification_plan": "Run score and compare checks.",
        "risk_boundary": "Allowed local files only; stop on missing metadata.",
        "expected_result": "One allowed result label.",
        "stop_condition": "Stop if verifier fails.",
    }
    payload.update(overrides)
    return json.dumps(payload)


def metric(path: Path, accepted: int, valid_rate: float, verifier: str = "verifier-a", metadata: dict | None = None) -> None:
    if metadata is None:
        metadata = {
            "prompt_hashes": ["prompt-a"],
            "response_hashes": ["response-a"],
            "model_revision": [{"resolved_revision": "abc123", "model_id": "Qwen/Qwen3.5-4B"}],
            "decoding_settings": [{"max_new_tokens": 32, "do_sample": False}],
            "verifier_version": [verifier],
        }
    write_json(
        path,
        {
            "status": "pass",
            "verifier_version": verifier,
            "prompt_ids": ["p1"],
            "valid_json_rate": valid_rate,
            "accepted_proposal_count": accepted,
            "measurement_metadata": metadata,
        },
    )


def torch_and_safetensors_available() -> bool:
    try:
        import torch  # noqa: F401
        import safetensors.torch  # noqa: F401
    except Exception:
        return False
    return True


class JsonExtractionTests(unittest.TestCase):
    def test_extracts_first_parseable_object_after_invalid_candidate(self) -> None:
        parsed = extract_json_object("prefix {bad json} then {\"ok\": {\"nested\": true}}")
        self.assertEqual(parsed, {"ok": {"nested": True}})

    def test_reports_unterminated_object(self) -> None:
        parsed, reason = extract_json_object_with_reason("text {\"claim\": \"unfinished\"")
        self.assertIsNone(parsed)
        self.assertEqual(reason, "unterminated_json_object")

    def test_strict_parser_accepts_exact_object_with_whitespace(self) -> None:
        parsed, reason = extract_single_json_object_with_reason("\n {\"ok\": true} \t")
        self.assertEqual(parsed, {"ok": True})
        self.assertIsNone(reason)

    def test_strict_parser_rejects_trailing_chat_text(self) -> None:
        parsed, reason = extract_single_json_object_with_reason("{\"ok\": true}\nuser\nReturn JSON")
        self.assertIsNone(parsed)
        self.assertEqual(reason, "not_exactly_one_json_object")

    def test_strict_parser_rejects_text_before_json(self) -> None:
        parsed, reason = extract_single_json_object_with_reason("Here is JSON: {\"ok\": true}")
        self.assertIsNone(parsed)
        self.assertEqual(reason, "not_exactly_one_json_object")

    def test_strict_parser_rejects_two_json_objects(self) -> None:
        parsed, reason = extract_single_json_object_with_reason("{\"a\": 1}{\"b\": 2}")
        self.assertIsNone(parsed)
        self.assertEqual(reason, "not_exactly_one_json_object")

    def test_strict_parser_rejects_think_after_json(self) -> None:
        parsed, reason = extract_single_json_object_with_reason("{\"ok\": true}\n<think></think>")
        self.assertIsNone(parsed)
        self.assertEqual(reason, "not_exactly_one_json_object")

    def test_strict_parser_rejects_top_level_array(self) -> None:
        parsed, reason = extract_single_json_object_with_reason("[{\"ok\": true}]")
        self.assertIsNone(parsed)
        self.assertEqual(reason, "not_exactly_one_json_object")

    def test_strict_parser_preserves_unterminated_object_reason(self) -> None:
        parsed, reason = extract_single_json_object_with_reason("{\"claim\": \"unfinished\"")
        self.assertIsNone(parsed)
        self.assertEqual(reason, "unterminated_json_object")


class VerifierTests(unittest.TestCase):
    def test_accepts_complete_grounded_response(self) -> None:
        score = score_response(full_response(), REQUIRED_FIELDS)
        self.assertTrue(score["accepted"])
        self.assertEqual(score["failure_categories"], [])

    def test_classifies_missing_required_field(self) -> None:
        score = score_response(full_response(risk_boundary=""), REQUIRED_FIELDS)
        self.assertFalse(score["accepted"])
        self.assertEqual(score["failure_category"], "missing required field")

    def test_classifies_truncated_output(self) -> None:
        score = score_response("{\"claim\": \"unfinished\"", REQUIRED_FIELDS)
        self.assertFalse(score["accepted"])
        self.assertEqual(score["failure_category"], "truncated output")

    def test_rejects_extra_text_after_valid_json(self) -> None:
        score = score_response(full_response() + "\nuser\nReturn JSON now.", REQUIRED_FIELDS)
        self.assertFalse(score["valid_json"])
        self.assertFalse(score["exact_json"])
        self.assertTrue(score["json_trailing_text"])
        self.assertEqual(score["strict_parse_failure_reason"], "not_exactly_one_json_object")
        self.assertEqual(score["failure_category"], "invalid JSON")

    def test_strict_v2_reclassifies_old_adapter_v2_trailing_outputs(self) -> None:
        rows = read_jsonl(ROOT / "artifacts" / "runs" / "20260523_adapter_v2_targeted" / "eval" / "adapter_v2_responses.jsonl")
        scores = {row["id"]: score_response(row["response"], REQUIRED_FIELDS) for row in rows}
        self.assertTrue(scores["heldout_v2_001"]["accepted"])
        for prompt_id in ("heldout_v2_002", "heldout_v2_003"):
            self.assertFalse(scores[prompt_id]["accepted"])
            self.assertFalse(scores[prompt_id]["valid_json"])
            self.assertFalse(scores[prompt_id]["exact_json"])
            self.assertTrue(scores[prompt_id]["json_trailing_text"])
            self.assertEqual(scores[prompt_id]["strict_parse_failure_reason"], "not_exactly_one_json_object")
            self.assertEqual(scores[prompt_id]["failure_category"], "invalid JSON")

    def test_failure_taxonomy_contains_required_categories(self) -> None:
        self.assertIn("weak verification plan", FAILURE_TAXONOMY)
        self.assertIn("weight anomaly", FAILURE_TAXONOMY)


class ComparisonRuleTests(unittest.TestCase):
    def test_improved_requires_matching_measurement_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base.json"
            adapter = tmp_path / "adapter.json"
            output = tmp_path / "comparison.json"
            metric(base, accepted=0, valid_rate=1.0)
            metric(adapter, accepted=1, valid_rate=1.0)
            result = compare(base, adapter, output, mode="base-vs-adapter")
            self.assertEqual(result["result"], "improved")
            self.assertTrue(result["model_improvement_claim"])

    def test_verifier_change_is_not_model_improvement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base.json"
            adapter = tmp_path / "adapter.json"
            output = tmp_path / "comparison.json"
            metric(base, accepted=0, valid_rate=1.0, verifier="verifier-a")
            metric(adapter, accepted=1, valid_rate=1.0, verifier="verifier-b")
            result = compare(base, adapter, output, mode="base-vs-adapter")
            self.assertEqual(result["result"], "inconclusive")
            self.assertFalse(result["model_improvement_claim"])
            self.assertTrue(result["verifier_calibration"])

    def test_missing_metadata_blocks_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base = tmp_path / "base.json"
            adapter = tmp_path / "adapter.json"
            output = tmp_path / "comparison.json"
            metric(base, accepted=0, valid_rate=1.0, metadata={})
            metric(adapter, accepted=1, valid_rate=1.0)
            result = compare(base, adapter, output, mode="base-vs-adapter")
            self.assertEqual(result["result"], "inconclusive")


class TargetedDatasetTests(unittest.TestCase):
    def test_v2_sft_responses_match_verifier_contract(self) -> None:
        rows = read_jsonl(ROOT / "data" / "asi_arc_sft_v2.jsonl")
        self.assertGreaterEqual(len(rows), 12)
        for row in rows:
            assistant = [message for message in row["messages"] if message["role"] == "assistant"][-1]
            score = score_response(assistant["content"], REQUIRED_FIELDS)
            self.assertTrue(score["accepted"], f"{row['id']}: {score}")

    def test_v2_1_sft_responses_match_strict_verifier_contract(self) -> None:
        rows = read_jsonl(ROOT / "data" / "asi_arc_sft_v2_1.jsonl")
        self.assertGreaterEqual(len(rows), 23)
        for row in rows:
            assistant = [message for message in row["messages"] if message["role"] == "assistant"][-1]
            score = score_response(assistant["content"], REQUIRED_FIELDS)
            self.assertTrue(score["accepted"], f"{row['id']}: {score}")
            self.assertTrue(score["exact_json"], f"{row['id']}: {score}")

    def test_v2_sft_does_not_copy_heldout_prompts(self) -> None:
        train_rows = read_jsonl(ROOT / "data" / "asi_arc_sft_v2.jsonl")
        heldout_rows = read_jsonl(ROOT / "prompts" / "heldout_prompts_v2.jsonl")
        train_prompts = {
            message["content"].strip()
            for row in train_rows
            for message in row["messages"]
            if message["role"] == "user"
        }
        heldout_prompts = {row["prompt"].strip() for row in heldout_rows}
        self.assertTrue(train_prompts.isdisjoint(heldout_prompts))

    def test_v2_1_sft_does_not_copy_heldout_prompts(self) -> None:
        train_rows = read_jsonl(ROOT / "data" / "asi_arc_sft_v2_1.jsonl")
        heldout_rows = read_jsonl(ROOT / "prompts" / "heldout_prompts_v2.jsonl")
        train_prompts = {
            message["content"].strip()
            for row in train_rows
            for message in row["messages"]
            if message["role"] == "user"
        }
        heldout_prompts = {row["prompt"].strip() for row in heldout_rows}
        self.assertTrue(train_prompts.isdisjoint(heldout_prompts))


class ManifestTraceTests(unittest.TestCase):
    def test_score_run_manifest_records_trace_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            responses = tmp_path / "responses.jsonl"
            output = tmp_path / "metrics.json"
            run_dir = tmp_path / "run"
            responses.write_text(
                json.dumps(
                    {
                        "id": "p1",
                        "response": full_response(),
                        "prompt_hash": "prompt-hash-a",
                        "prompt_file_sha256": "prompt-file-hash-a",
                        "response_hash": "response-hash-a",
                        "model_revision": {"resolved_revision": "abc123"},
                        "adapter": "adapter-a",
                        "decoding_settings": {"max_new_tokens": 32, "do_sample": False},
                        "verifier_version": "verifier-a",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            cmd = [
                sys.executable,
                str(SCRIPTS / "benchmark_proposals.py"),
                "score",
                "--responses",
                str(responses),
                "--output",
                str(output),
                "--run-dir",
                str(run_dir),
            ]
            completed = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            manifest = read_json(run_dir / "run_manifest.json")
            self.assertEqual(manifest["prompt_hash"], "prompt-file-hash-a")
            self.assertEqual(manifest["adapter_path"], "adapter-a")
            self.assertEqual(manifest["model_revision"], {"resolved_revision": "abc123"})
            self.assertIn("command", manifest)
            self.assertIn("package_versions", manifest)
            self.assertIn("cuda_status", manifest)
            self.assertTrue(manifest["benchmark_score_metrics"]["responses"]["sha256"])
            self.assertTrue(manifest["benchmark_score_metrics"]["output_file"]["sha256"])


@unittest.skipUnless(torch_and_safetensors_available(), "torch and safetensors are required for tiny LoRA dry-run")
class TinyDryRunTests(unittest.TestCase):
    def test_tiny_lora_dry_run_writes_snapshots_and_nonzero_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir = tmp_path / "run"
            adapter_dir = tmp_path / "adapter"
            metrics = tmp_path / "metrics.json"
            loss_log = tmp_path / "loss.jsonl"
            cmd = [
                sys.executable,
                str(SCRIPTS / "train_lora.py"),
                "--dry-run-tiny",
                "--run-dir",
                str(run_dir),
                "--output-dir",
                str(adapter_dir),
                "--metrics",
                str(metrics),
                "--loss-log",
                str(loss_log),
                "--learning-rate",
                "0.1",
            ]
            completed = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue((run_dir / "run_manifest.json").exists())
            self.assertTrue((run_dir / "adapter_init.safetensors").exists())
            self.assertTrue((run_dir / "adapter_final.safetensors").exists())
            diff = read_json(run_dir / "adapter_diff_metrics.json")
            self.assertEqual(diff["status"], "pass")
            self.assertTrue(diff["summary"]["any_nonzero_delta"])
            self.assertEqual(diff["summary"]["nan_count"], 0)
            self.assertEqual(diff["summary"]["inf_count"], 0)


if __name__ == "__main__":
    unittest.main()
