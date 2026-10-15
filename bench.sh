#!/usr/bin/env bash
set -euo pipefail
MODEL="${1:-qwen3:4b}"
CTX="${2:-4096}"
REPEATS="${3:-3}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
OUT="data/bench/${MODEL//[:\/]/_}_ctx${CTX}_$(date -u +%Y%m%dT%H%M%SZ).jsonl"
mkdir -p "$(dirname "$OUT")"
command -v jq >/dev/null || { echo "ERRO: jq nao encontrado" >&2; exit 2; }
curl -fsS --max-time 3 "$OLLAMA_URL/api/tags" >/dev/null || { echo "ERRO: Ollama nao respondeu" >&2; exit 2; }
curl -fsS "$OLLAMA_URL/api/tags" | jq -e --arg m "$MODEL" '.models[] | select(.name == $m or .name == ($m + ":latest"))' >/dev/null || { echo "ERRO: modelo $MODEL nao encontrado; execute ollama pull $MODEL" >&2; exit 2; }
SHORT_PROMPT="Resuma em tres frases o que e um exocortex pessoal."
LONG_PROMPT="Explique em portugues do Brasil como projetar um sistema local-first de IA pessoal considerando privacidade, custo, latencia e resiliencia."
sample_vram() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null || echo 0; }
run_case() {
  local label="$1" prompt="$2" max_predict="$3" i
  for ((i=1;i<=REPEATS;i++)); do
    payload=$(jq -nc --arg model "$MODEL" --arg prompt "$prompt" --argjson ctx "$CTX" --argjson predict "$max_predict" '{model:$model,prompt:$prompt,stream:true,options:{num_ctx:$ctx,num_predict:$predict,temperature:0.2}}')
    start=$(date +%s%N); first_token=""; peak_vram=0; tmp=$(mktemp)
    curl -fsS --max-time 120 "$OLLAMA_URL/api/generate" -H 'Content-Type: application/json' -d "$payload" > "$tmp" || { rm -f "$tmp"; echo "ERRO: chamada Ollama falhou" >&2; exit 3; }
    while IFS= read -r line; do
      vram=$(sample_vram); (( vram > peak_vram )) && peak_vram=$vram
      if [[ -z "$first_token" ]] && jq -e '.response != ""' >/dev/null 2>&1 <<<"$line"; then first_token=$(date +%s%N); fi
    done < "$tmp"
    end=$(date +%s%N)
    [[ -z "$first_token" ]] && { rm -f "$tmp"; echo "ERRO: nenhuma resposta recebida" >&2; exit 4; }
    ttft_ms=$(( (first_token-start)/1000000 )); total_ms=$(( (end-start)/1000000 ))
    jq -nc --arg model "$MODEL" --argjson ctx "$CTX" --arg case "$label" --argjson repeat "$i" --argjson ttft_ms "$ttft_ms" --argjson total_ms "$total_ms" --argjson peak_vram_mb "$peak_vram" --slurpfile response "$tmp" '{timestamp:now,model:$model,num_ctx:$ctx,case:$case,repeat:$repeat,ttft_ms:$ttft_ms,total_ms:$total_ms,peak_vram_mb:$peak_vram_mb,metrics:$response[0]}' >> "$OUT"
    rm -f "$tmp"
  done
}
run_case short "$SHORT_PROMPT" 128
run_case long "$LONG_PROMPT" 512
jq -s 'group_by(.case)|map({case:.[0].case,runs:length,ttft_ms_median:(map(.ttft_ms)|sort|.[length/2|floor]),total_ms_median:(map(.total_ms)|sort|.[length/2|floor]),tokens_per_second_median:(map(.metrics.eval_count/(.metrics.eval_duration/1000000000))|sort|.[length/2|floor]),peak_vram_mb_max:(map(.peak_vram_mb)|max)})' "$OUT" > "${OUT%.jsonl}.summary.json"
echo "Benchmark concluido: $OUT"
echo "Resumo: ${OUT%.jsonl}.summary.json"
