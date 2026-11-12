#!/usr/bin/env bash
# Merge LoRA + quantização GGUF IQ4_XS (1x RTX 3090, ~3.85 GB para GTX 1650 4GB VRAM)
set -euo pipefail

MODEL_BASE="${MODEL_BASE:-Qwen/Qwen2.5-Coder-7B-Instruct}"
ADAPTER_DIR="${ADAPTER_DIR:-/workspace/input/adapter}"
WORKDIR="${WORKDIR:-/workspace/output/quantize}"
LLAMA_CPP="${LLAMA_CPP:-/opt/llama.cpp}"
CALIB="${CALIB:-/workspace/input/validated_pairs.jsonl}"
OUT_GGUF="${OUT_GGUF:-/workspace/output/YBY-SEED-Coder-7B-IQ4_XS.gguf}"

mkdir -p "${WORKDIR}/merged" "${WORKDIR}/gguf"

python3 - <<'PY'
import os
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = os.environ["MODEL_BASE"]
adapter = os.environ["ADAPTER_DIR"]
out = os.path.join(os.environ["WORKDIR"], "merged")

tokenizer = AutoTokenizer.from_pretrained(base, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    base,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True,
)
model = PeftModel.from_pretrained(model, adapter)
model = model.merge_and_unload()
model.save_pretrained(out, safe_serialization=True)
tokenizer.save_pretrained(out)
print(f"merge concluído em {out}")
PY

python3 "${LLAMA_CPP}/convert_hf_to_gguf.py" \
  "${WORKDIR}/merged" \
  --outfile "${WORKDIR}/gguf/model-f16.gguf"

python3 "${LLAMA_CPP}/examples/imatrix/imatrix.py" \
  -m "${WORKDIR}/gguf/model-f16.gguf" \
  -f "${CALIB}" \
  -o "${WORKDIR}/gguf/yby.imatrix" \
  -c 2048 \
  --in-format text || true

"${LLAMA_CPP}/llama-quantize" \
  --imatrix "${WORKDIR}/gguf/yby.imatrix" \
  "${WORKDIR}/gguf/model-f16.gguf" \
  "${OUT_GGUF}" \
  IQ4_XS

ls -lh "${OUT_GGUF}"
echo "GGUF pronto: ${OUT_GGUF}"
