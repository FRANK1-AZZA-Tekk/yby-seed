#!/usr/bin/env python3
"""QLoRA DDP (2x RTX 3090) — Qwen2.5-Coder-7B-Instruct → adaptador compactado."""

from __future__ import annotations

import argparse
import json
import subprocess
import tarfile
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer


def _load_chatml_dataset(path: Path) -> Dataset:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            messages = payload.get("messages", [])
            text = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
            rows.append({"text": text})
    if not rows:
        raise SystemExit(f"dataset vazio: {path}")
    return Dataset.from_list(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("/workspace/input/validated_pairs.jsonl")
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--output-dir", type=Path, default=Path("/workspace/output/adapter"))
    parser.add_argument(
        "--bundle-out", type=Path, default=Path("/workspace/output/yby-seed-adapter.tar.zst")
    )
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--max-seq-len", type=int, default=8192)
    args = parser.parse_args()

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)

    lora = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules="all-linear",
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)

    dataset = _load_chatml_dataset(args.dataset)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=10,
        save_strategy="epoch",
        bf16=torch.cuda.is_available(),
        optim="paged_adamw_8bit",
        report_to=[],
        ddp_find_unused_parameters=False,
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        processing_class=tokenizer,
        args=training_args,
        max_seq_length=args.max_seq_len,
    )
    trainer.train()
    trainer.model.save_pretrained(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    args.bundle_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["tar", "--zstd", "-cf", str(args.bundle_out), "-C", str(args.output_dir), "."],
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        with tarfile.open(args.bundle_out.with_suffix(".tar.gz"), "w:gz") as tar:
            tar.add(args.output_dir, arcname=".")
        args.bundle_out = args.bundle_out.with_suffix(".tar.gz")

    print(f"adaptador salvo em {args.bundle_out}")


if __name__ == "__main__":
    main()
