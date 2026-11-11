#!/usr/bin/env bash
set -e
mkdir -p results

PROMPT="Explique em 200 palavras o que é RAG (Retrieval-Augmented Generation) e como ele se aplica a um assistente de IA local."

for MODEL in qwen2.5:3b qwen2.5-coder:3b; do
  echo "===== $MODEL ====="
  ollama run "$MODEL" "ok" > /dev/null 2>&1
  ollama run "$MODEL" "$PROMPT" --verbose 2>&1 | tee "results/${MODEL//:/_}.txt"
  ollama ps | tee -a "results/${MODEL//:/_}.txt"
  nvidia-smi --query-gpu=memory.used,temperature.gpu,power.draw --format=csv | tee -a "results/${MODEL//:/_}.txt"
done

echo "===== RESUMO ====="
grep -H "eval rate" results/*.txt
