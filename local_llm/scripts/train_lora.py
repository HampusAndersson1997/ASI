from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path
from typing import Any

from benchmark_proposals import VERIFIER_VERSION
from common import (
    ROOT,
    adapter_diff_metrics,
    command_metadata,
    cuda_status,
    file_metadata,
    model_revision_metadata,
    package_versions,
    read_jsonl,
    resolve_run_dir,
    save_safetensors_state,
    sha256_file,
    update_run_manifest,
    utc_now,
    write_json,
    write_jsonl,
)


PREFERRED_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def first_real_device(model: Any, torch: Any) -> Any:
    for param in model.parameters():
        if getattr(param, "device", None) is not None and param.device.type != "meta":
            return param.device
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def get_tokenizer(processor: Any) -> Any:
    return getattr(processor, "tokenizer", processor)


def normalize_messages(messages: list[dict[str, Any]], multimodal: bool) -> list[dict[str, Any]]:
    if not multimodal:
        return messages
    normalized = []
    for message in messages:
        content = message["content"]
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        normalized.append({"role": message["role"], "content": content})
    return normalized


def apply_template(processor: Any, messages: list[dict[str, Any]], enable_thinking: bool) -> str:
    last_error: Exception | None = None
    for multimodal in (False, True):
        try:
            return processor.apply_chat_template(
                normalize_messages(messages, multimodal),
                tokenize=False,
                add_generation_prompt=False,
                enable_thinking=enable_thinking,
            )
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"chat template failed: {last_error}") from last_error


class ChatDataset:
    def __init__(self, rows: list[dict[str, Any]], processor: Any, max_length: int, enable_thinking: bool):
        self.processor = processor
        self.tokenizer = get_tokenizer(processor)
        self.max_length = max_length
        self.enable_thinking = enable_thinking
        self.examples: list[dict[str, Any]] = []
        self.sample_stats: list[dict[str, Any]] = []
        self.skipped_count = 0
        self.truncated_count = 0
        if getattr(self.tokenizer, "pad_token", None) is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        for index, row in enumerate(rows):
            text = apply_template(self.processor, row["messages"], self.enable_thinking)
            full_encoded = self.tokenizer(text, truncation=False, return_attention_mask=False)
            token_count = len(full_encoded["input_ids"])
            if token_count <= 0:
                self.skipped_count += 1
                self.sample_stats.append(
                    {
                        "id": row.get("id", index),
                        "token_count": token_count,
                        "truncated": False,
                        "skipped": True,
                    }
                )
                continue
            truncated = token_count > self.max_length
            if truncated:
                self.truncated_count += 1
            encoded = self.tokenizer(
                text,
                truncation=True,
                max_length=self.max_length,
                return_attention_mask=True,
            )
            input_ids = encoded["input_ids"]
            attention_mask = encoded["attention_mask"]
            labels = [token if mask else -100 for token, mask in zip(input_ids, attention_mask)]
            self.examples.append({"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels})
            self.sample_stats.append(
                {
                    "id": row.get("id", index),
                    "token_count": token_count,
                    "effective_token_count": len(input_ids),
                    "truncated": truncated,
                    "skipped": False,
                }
            )

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.examples[index]


def collate(batch: list[dict[str, Any]], pad_token_id: int, torch: Any) -> dict[str, Any]:
    max_len = max(len(item["input_ids"]) for item in batch)
    input_ids = []
    attention_mask = []
    labels = []
    for item in batch:
        pad_len = max_len - len(item["input_ids"])
        input_ids.append(item["input_ids"] + [pad_token_id] * pad_len)
        attention_mask.append(item["attention_mask"] + [0] * pad_len)
        labels.append(item["labels"] + [-100] * pad_len)
    return {
        "input_ids": torch.tensor(input_ids, dtype=torch.long),
        "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
        "labels": torch.tensor(labels, dtype=torch.long),
    }


def infer_lora_targets(model: Any) -> list[str]:
    seen: set[str] = set()
    for name, _module in model.named_modules():
        leaf = name.rsplit(".", 1)[-1]
        if leaf in PREFERRED_TARGETS:
            seen.add(leaf)
    return [target for target in PREFERRED_TARGETS if target in seen]


def load_processor_model(args: argparse.Namespace) -> tuple[Any, Any, str]:
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
    return processor, model, loader


def tiny_adapter_state(model: Any) -> dict[str, Any]:
    return {f"tiny_lora.{name}": parameter.detach().clone() for name, parameter in model.named_parameters()}


def dry_run_tiny_lora(args: argparse.Namespace) -> int:
    import torch

    run_started = time.perf_counter()
    run_dir = resolve_run_dir(args.run_id or None, args.run_dir, label="tiny_lora_dry_run")
    init_path = run_dir / "adapter_init.safetensors"
    final_path = run_dir / "adapter_final.safetensors"
    diff_path = run_dir / "adapter_diff_metrics.json"
    dataset_hash = sha256_file(args.dataset) if args.dataset.exists() else None
    update_run_manifest(
        run_dir,
        {
            "started_at": utc_now(),
            "model_revision": model_revision_metadata(args.model),
            "adapter_path": str(args.output_dir),
            "dataset_hash": dataset_hash,
            "prompt_hash": None,
            "seed": args.seed,
            "verifier_version": VERIFIER_VERSION,
            "package_versions": package_versions(),
            "cuda_status": cuda_status(),
            "command": command_metadata(args),
            "training": {
                "status": "running",
                "mode": "dry_run_tiny_lora",
                "dataset": file_metadata(args.dataset),
                "metrics": str(args.metrics),
                "loss_log": str(args.loss_log),
                "adapter_init": str(init_path),
                "adapter_final": str(final_path),
                "adapter_diff_metrics": str(diff_path),
            },
        },
    )

    torch.manual_seed(args.seed)

    class TinyLora(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.lora_A = torch.nn.Linear(4, 2, bias=False)
            self.lora_B = torch.nn.Linear(2, 4, bias=False)
            torch.nn.init.normal_(self.lora_A.weight, mean=0.0, std=0.02)
            torch.nn.init.zeros_(self.lora_B.weight)

        def forward(self, values: Any) -> Any:
            return values + self.lora_B(self.lora_A(values))

    model = TinyLora()
    save_safetensors_state(tiny_adapter_state(model), init_path)

    optimizer = torch.optim.SGD(model.parameters(), lr=args.learning_rate)
    inputs = torch.eye(4)
    targets = torch.zeros_like(inputs)
    loss_rows = []
    optimizer.zero_grad(set_to_none=True)
    for step in range(3):
        started = time.perf_counter()
        outputs = model(inputs)
        loss = torch.nn.functional.mse_loss(outputs, targets)
        if torch.isnan(loss) or torch.isinf(loss):
            raise SystemExit(f"NaN/Inf loss at dry-run step={step}")
        loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(list(model.parameters()), 1.0)
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        row = {
            "logged_at": utc_now(),
            "epoch": 0,
            "batch_index": step,
            "global_step": step + 1,
            "optimizer_step": True,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "grad_norm": float(grad_norm.detach().cpu()),
            "loss": float(loss.detach().cpu()),
            "batch_size": int(inputs.shape[0]),
            "tokens_per_sample": [int(inputs.shape[1])] * int(inputs.shape[0]),
            "wall_clock_seconds": time.perf_counter() - started,
        }
        loss_rows.append(row)
        print(json.dumps(row, sort_keys=True))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    save_safetensors_state(tiny_adapter_state(model), final_path)
    save_safetensors_state(tiny_adapter_state(model), args.output_dir / "adapter_model.safetensors")
    diff_metrics = adapter_diff_metrics(init_path, final_path, diff_path)
    write_jsonl(args.loss_log, loss_rows)
    metrics = {
        "created_at": utc_now(),
        "status": "pass" if diff_metrics["status"] == "pass" and diff_metrics["summary"]["any_nonzero_delta"] else "failed",
        "mode": "dry_run_tiny_lora",
        "record_count": int(inputs.shape[0]),
        "output_dir": str(args.output_dir),
        "epochs": 1,
        "global_steps": len(loss_rows),
        "final_loss": loss_rows[-1]["loss"] if loss_rows else None,
        "nan_or_inf_loss": False,
        "adapter_init": str(init_path),
        "adapter_final": str(final_path),
        "adapter_diff_metrics": str(diff_path),
        "gpu_memory_peak_bytes": 0,
        "wall_clock_seconds": time.perf_counter() - run_started,
    }
    write_json(args.metrics, metrics)
    update_run_manifest(
        run_dir,
        {
            "completed_at": utc_now(),
            "adapter_path": str(args.output_dir),
            "dataset_hash": dataset_hash,
            "prompt_hash": None,
            "seed": args.seed,
            "verifier_version": VERIFIER_VERSION,
            "package_versions": package_versions(),
            "cuda_status": cuda_status(),
            "command": command_metadata(args),
            "training": {
                "status": metrics["status"],
                "mode": "dry_run_tiny_lora",
                "metrics": str(args.metrics),
                "loss_log": str(args.loss_log),
                "adapter_init": str(init_path),
                "adapter_final": str(final_path),
                "adapter_diff_metrics": str(diff_path),
            },
        },
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0 if metrics["status"] == "pass" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Train a small LoRA/QLoRA adapter for ASI/ARC proposal JSON.")
    parser.add_argument("--model", default=str(ROOT / "models" / "Qwen--Qwen3.5-4B"))
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "asi_arc_sft_v1.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "adapters" / "asi_arc_lora_v1")
    parser.add_argument("--metrics", type=Path, default=ROOT / "artifacts" / "train_lora_metrics.json")
    parser.add_argument("--loss-log", type=Path, default=ROOT / "logs" / "train_lora_loss.jsonl")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=4)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=115)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--enable-thinking", action="store_true", help="Enable thinking tokens during SFT; disabled by default for JSON adapter behavior.")
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--dry-run-tiny", action="store_true", help="Run a CPU toy LoRA update to verify snapshots and diff metrics.")
    args = parser.parse_args()

    if args.dry_run_tiny:
        return dry_run_tiny_lora(args)

    import torch
    from peft import LoraConfig, TaskType, get_peft_model, get_peft_model_state_dict, prepare_model_for_kbit_training
    from torch.utils.data import DataLoader
    from transformers import get_linear_schedule_with_warmup

    run_started = time.perf_counter()
    run_dir = resolve_run_dir(args.run_id or None, args.run_dir, label="train_lora")
    init_path = run_dir / "adapter_init.safetensors"
    final_path = run_dir / "adapter_final.safetensors"
    diff_path = run_dir / "adapter_diff_metrics.json"
    update_run_manifest(
        run_dir,
        {
            "started_at": utc_now(),
            "model_revision": model_revision_metadata(args.model),
            "adapter_path": str(args.output_dir),
            "dataset_hash": sha256_file(args.dataset) if args.dataset.exists() else None,
            "prompt_hash": None,
            "verifier_version": VERIFIER_VERSION,
            "seed": args.seed,
            "package_versions": package_versions(),
            "cuda_status": cuda_status(),
            "command": command_metadata(args),
            "training": {
                "status": "running",
                "dataset": file_metadata(args.dataset),
                "metrics": str(args.metrics),
                "loss_log": str(args.loss_log),
                "adapter_init": str(init_path),
                "adapter_final": str(final_path),
                "adapter_diff_metrics": str(diff_path),
            },
        },
    )

    if not args.allow_cpu and not torch.cuda.is_available():
        raise SystemExit("torch.cuda.is_available() is false; refusing GPU-required training")
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    processor, model, loader = load_processor_model(args)
    tokenizer = get_tokenizer(processor)
    if getattr(tokenizer, "pad_token", None) is None:
        tokenizer.pad_token = tokenizer.eos_token
    pad_token_id = int(tokenizer.pad_token_id)

    if args.load_in_4bit:
        model = prepare_model_for_kbit_training(model)
    if hasattr(model, "config"):
        model.config.use_cache = False
    if hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    targets = infer_lora_targets(model)
    if not targets:
        raise SystemExit("No LoRA target modules found. Inspect model.named_modules() and set target modules explicitly.")

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        target_modules=targets,
    )
    model = get_peft_model(model, lora_config)
    save_safetensors_state(get_peft_model_state_dict(model), init_path)
    model.train()

    rows = read_jsonl(args.dataset)
    dataset = ChatDataset(rows, processor, args.max_seq_length, args.enable_thinking)
    if len(dataset) <= 0:
        raise SystemExit("training dataset has no usable tokenized samples")
    loader_dl = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=lambda batch: collate(batch, pad_token_id, torch),
    )
    trainable_params = [param for param in model.parameters() if param.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=args.learning_rate)
    total_steps = math.ceil(len(loader_dl) * args.epochs / args.gradient_accumulation_steps)
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=max(total_steps, 1))
    device = first_real_device(model, torch)

    loss_rows = []
    global_step = 0
    optimizer.zero_grad(set_to_none=True)
    for epoch in range(args.epochs):
        for batch_index, batch in enumerate(loader_dl):
            batch_started = time.perf_counter()
            tokens_per_sample = [int(value.item()) for value in batch["attention_mask"].sum(dim=1)]
            batch = {key: value.to(device) for key, value in batch.items()}
            outputs = model(**batch)
            raw_loss = outputs.loss
            if torch.isnan(raw_loss) or torch.isinf(raw_loss):
                raise SystemExit(f"NaN/Inf loss at epoch={epoch} batch={batch_index}")
            loss = raw_loss / args.gradient_accumulation_steps
            loss.backward()
            should_step = (batch_index + 1) % args.gradient_accumulation_steps == 0 or (batch_index + 1) == len(loader_dl)
            grad_norm_value = None
            if should_step:
                grad_norm = torch.nn.utils.clip_grad_norm_(trainable_params, 1.0)
                grad_norm_value = float(grad_norm.detach().cpu())
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
                global_step += 1
            loss_rows.append(
                {
                    "logged_at": utc_now(),
                    "epoch": epoch,
                    "batch_index": batch_index,
                    "global_step": global_step,
                    "optimizer_step": should_step,
                    "learning_rate": float(scheduler.get_last_lr()[0]),
                    "grad_norm": grad_norm_value,
                    "batch_size": len(tokens_per_sample),
                    "tokens_per_sample": tokens_per_sample,
                    "loss": float(raw_loss.detach().cpu()),
                    "wall_clock_seconds": time.perf_counter() - batch_started,
                }
            )
            print(json.dumps(loss_rows[-1], sort_keys=True))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    save_safetensors_state(get_peft_model_state_dict(model), final_path)
    model.save_pretrained(args.output_dir)
    if hasattr(processor, "save_pretrained"):
        processor.save_pretrained(args.output_dir)
    diff_metrics = adapter_diff_metrics(init_path, final_path, diff_path)
    write_jsonl(args.loss_log, loss_rows)
    gpu_memory_peak_bytes = int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else 0

    metrics = {
        "created_at": utc_now(),
        "status": "pass" if diff_metrics["status"] == "pass" else "failed",
        "loader": loader,
        "dataset": str(args.dataset),
        "dataset_sha256": sha256_file(args.dataset),
        "record_count": len(rows),
        "usable_record_count": len(dataset),
        "skipped_sample_count": dataset.skipped_count,
        "truncated_sample_count": dataset.truncated_count,
        "tokens_per_sample": dataset.sample_stats,
        "output_dir": str(args.output_dir),
        "epochs": args.epochs,
        "global_steps": global_step,
        "lora_targets": targets,
        "final_loss": loss_rows[-1]["loss"] if loss_rows else None,
        "nan_or_inf_loss": False,
        "adapter_init": str(init_path),
        "adapter_final": str(final_path),
        "adapter_diff_metrics": str(diff_path),
        "adapter_diff_status": diff_metrics["status"],
        "adapter_nonzero_delta": diff_metrics["summary"]["any_nonzero_delta"],
        "gpu_memory_peak_bytes": gpu_memory_peak_bytes,
        "wall_clock_seconds": time.perf_counter() - run_started,
    }
    write_json(args.metrics, metrics)
    update_run_manifest(
        run_dir,
        {
            "completed_at": utc_now(),
            "training": {
                "status": metrics["status"],
                "metrics": str(args.metrics),
                "loss_log": str(args.loss_log),
                "adapter_init": str(init_path),
                "adapter_final": str(final_path),
                "adapter_diff_metrics": str(diff_path),
                "global_steps": global_step,
                "gpu_memory_peak_bytes": gpu_memory_peak_bytes,
                "wall_clock_seconds": metrics["wall_clock_seconds"],
            },
        },
    )
    print(json.dumps(metrics, indent=2, sort_keys=True))
    return 0 if metrics["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
