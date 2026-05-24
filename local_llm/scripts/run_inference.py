from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from benchmark_proposals import VERIFIER_VERSION, score_response
from common import (
    ROOT,
    command_metadata,
    cuda_status,
    file_metadata,
    load_config,
    model_revision_metadata,
    package_versions,
    read_jsonl,
    resolve_run_dir,
    sha256_file,
    sha256_text,
    update_run_manifest,
    utc_now,
    write_jsonl,
)


SYSTEM_PROMPT = (
    "You are a local ASI/ARC proposal engine. Return exactly one JSON object "
    "with fields claim, evidence, proposal, executable_abstraction, "
    "verification_plan, risk_boundary, expected_result, and stop_condition. "
    "Separate facts from inferences and do not claim success without evidence."
)


def message_variants(prompt: str) -> list[list[dict[str, Any]]]:
    plain = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    multimodal = [
        {"role": "system", "content": [{"type": "text", "text": SYSTEM_PROMPT}]},
        {"role": "user", "content": [{"type": "text", "text": prompt}]},
    ]
    return [plain, multimodal]


def first_real_device(model: Any, torch: Any) -> Any:
    for param in model.parameters():
        if getattr(param, "device", None) is not None and param.device.type != "meta":
            return param.device
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def move_inputs(inputs: Any, device: Any) -> Any:
    if hasattr(inputs, "to"):
        return inputs.to(device)
    return {key: value.to(device) if hasattr(value, "to") else value for key, value in inputs.items()}


def load_model(args: argparse.Namespace) -> tuple[Any, Any, str]:
    import torch
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoProcessor, AutoTokenizer

    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    model_kwargs: dict[str, Any] = {
        "device_map": "auto",
        "local_files_only": args.local_files_only,
        "trust_remote_code": args.trust_remote_code,
    }
    if args.load_in_4bit:
        from transformers import BitsAndBytesConfig

        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=dtype,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    else:
        model_kwargs["torch_dtype"] = dtype

    try:
        processor = AutoProcessor.from_pretrained(
            args.model,
            local_files_only=args.local_files_only,
            trust_remote_code=args.trust_remote_code,
        )
        model = AutoModelForImageTextToText.from_pretrained(args.model, **model_kwargs)
        loader = "AutoModelForImageTextToText"
    except Exception as primary_exc:
        tokenizer = AutoTokenizer.from_pretrained(
            args.model,
            local_files_only=args.local_files_only,
            trust_remote_code=args.trust_remote_code,
        )
        model = AutoModelForCausalLM.from_pretrained(args.model, **model_kwargs)
        processor = tokenizer
        loader = f"AutoModelForCausalLM fallback after {type(primary_exc).__name__}"

    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter, is_trainable=False)
    model.eval()
    return processor, model, loader


def encode_chat(processor: Any, prompt: str, enable_thinking: bool) -> Any:
    last_error: Exception | None = None
    for messages in message_variants(prompt):
        try:
            return processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                enable_thinking=enable_thinking,
            )
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"chat template failed for prompt: {last_error}") from last_error


def decode_new_tokens(processor: Any, generated: Any, input_length: int) -> str:
    new_tokens = generated[:, input_length:]
    decoder = getattr(processor, "batch_decode", None)
    if decoder is None and hasattr(processor, "tokenizer"):
        decoder = processor.tokenizer.batch_decode
    if decoder is None:
        raise RuntimeError("processor/tokenizer has no batch_decode method")
    return decoder(new_tokens, skip_special_tokens=True)[0].strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run fixed ASI/ARC proposal prompts through a local model.")
    parser.add_argument("--model", default=str(ROOT / "models" / "Qwen--Qwen3.5-4B"))
    parser.add_argument("--prompts", type=Path, default=ROOT / "prompts" / "benchmark_prompts.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "responses.jsonl")
    parser.add_argument("--adapter", type=str, default="")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--enable-thinking", action="store_true", help="Enable Qwen thinking tokens; disabled by default for JSON benchmarking.")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()

    import torch

    if not args.allow_cpu and not torch.cuda.is_available():
        raise SystemExit("torch.cuda.is_available() is false; refusing GPU-required inference")

    run_started = time.perf_counter()
    run_dir = resolve_run_dir(args.run_id or None, args.run_dir, label="inference")
    prompt_file_sha256 = sha256_file(args.prompts)
    model_revision = model_revision_metadata(args.model)
    decoding_settings = {
        "max_new_tokens": args.max_new_tokens,
        "do_sample": False,
        "enable_thinking": args.enable_thinking,
        "load_in_4bit": args.load_in_4bit,
        "local_files_only": args.local_files_only,
    }
    update_run_manifest(
        run_dir,
        {
            "started_at": utc_now(),
            "model_revision": model_revision,
            "adapter_path": args.adapter or None,
            "prompt_hash": prompt_file_sha256,
            "verifier_version": VERIFIER_VERSION,
            "package_versions": package_versions(),
            "cuda_status": cuda_status(),
            "command": command_metadata(args),
            "decoding_settings": decoding_settings,
            "inference": {
                "status": "running",
                "prompts": file_metadata(args.prompts),
                "output": str(args.output),
            },
        },
    )

    processor, model, loader = load_model(args)
    device = first_real_device(model, torch)
    rows = []
    required_fields = list(load_config()["benchmark"]["required_fields"])
    for prompt_row in read_jsonl(args.prompts):
        prompt = str(prompt_row["prompt"])
        prompt_started = time.perf_counter()
        inputs = move_inputs(encode_chat(processor, prompt, args.enable_thinking), device)
        input_length = int(inputs["input_ids"].shape[-1])
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=args.max_new_tokens,
                do_sample=False,
                pad_token_id=getattr(getattr(processor, "tokenizer", processor), "eos_token_id", None),
            )
        latency_seconds = time.perf_counter() - prompt_started
        generated_token_count = int(generated.shape[-1] - input_length)
        response = decode_new_tokens(processor, generated, input_length)
        score = score_response(response, required_fields)
        rows.append(
            {
                "id": prompt_row["id"],
                "raw_prompt": prompt,
                "prompt": prompt,
                "prompt_hash": sha256_text(prompt),
                "prompt_file": str(args.prompts),
                "prompt_file_sha256": prompt_file_sha256,
                "raw_response": response,
                "response": response,
                "response_hash": sha256_text(response),
                "parsed_json": score.get("parsed"),
                "parse_failure_reason": score.get("parse_failure_reason"),
                "strict_parse_failure_reason": score.get("strict_parse_failure_reason"),
                "exact_json": bool(score.get("exact_json")),
                "json_trailing_text": bool(score.get("json_trailing_text")),
                "verifier_version": VERIFIER_VERSION,
                "verifier_reasons": score.get("reasons", []),
                "accepted": bool(score.get("accepted")),
                "status": "accepted" if score.get("accepted") else "rejected",
                "failure_category": score.get("failure_category"),
                "input_token_count": input_length,
                "generated_token_count": generated_token_count,
                "token_count": generated_token_count,
                "latency_seconds": latency_seconds,
                "decoding_settings": decoding_settings,
                "model": args.model,
                "model_revision": model_revision,
                "adapter": args.adapter or None,
                "loader": loader,
                "generated_at": utc_now(),
            }
        )
        print(json.dumps(rows[-1], ensure_ascii=True, sort_keys=True))

    write_jsonl(args.output, rows)
    update_run_manifest(
        run_dir,
        {
            "completed_at": utc_now(),
            "inference": {
                "status": "pass",
                "output": str(args.output),
                "response_count": len(rows),
                "wall_clock_seconds": time.perf_counter() - run_started,
            },
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
