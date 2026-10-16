#!/usr/bin/env bash
# Benchmark do Ollama com metricas medidas durante a geracao.
#
# - TTFT: primeiro evento com texto nao vazio, lido durante o stream.
# - Primeiro thinking: primeiro evento com campo thinking nao vazio, se existir.
# - Pico de VRAM: amostrado em paralelo durante a geracao.
# - Tokens/s: calculado do evento final (done=true) com eval_count/eval_duration.
# - Streams incompletos ou com erro sao rejeitados.
# - Medicoes indisponiveis sao registradas como null, nunca como zero.
set -euo pipefail

MODEL="${1:-qwen3:4b}"
CTX="${2:-4096}"
REPEATS="${3:-3}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
OUT="data/bench/${MODEL//[:\/]/_}_ctx${CTX}_$(date -u +%Y%m%dT%H%M%SZ).jsonl"

mkdir -p "$(dirname "$OUT")"
command -v jq >/dev/null || { echo "ERRO: jq nao encontrado" >&2; exit 2; }
command -v curl >/dev/null || { echo "ERRO: curl nao encontrado" >&2; exit 2; }

curl -fsS --max-time 3 "$OLLAMA_URL/api/tags" >/dev/null || { echo "ERRO: Ollama nao respondeu" >&2; exit 2; }
curl -fsS --max-time 10 "$OLLAMA_URL/api/tags" | jq -e --arg m "$MODEL" '.models[] | select(.name == $m or .name == ($m + ":latest"))' >/dev/null || { echo "ERRO: modelo $MODEL nao encontrado; execute ollama pull $MODEL" >&2; exit 2; }

SHORT_PROMPT="Resuma em tres frases o que e um exocortex pessoal."
LONG_PROMPT="Explique em portugues do Brasil como projetar um sistema local-first de IA pessoal considerando privacidade, custo, latencia e resiliencia."

sample_vram_once() {
  nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null || true
}

run_generation() {
  local payload="$1" final_file="$2" vram_file="$3"
  : > "$vram_file"
  ( while :; do sample_vram_once >> "$vram_file"; sleep 0.2; done ) &
  local sampler_pid=$!
  ttft=""
  first_thinking=""
  local done_seen=0 had_error=0 line
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if jq -e '(.error != null)' >/dev/null 2>&1 <<<"$line"; then
      had_error=1
      break
    fi
    if [[ -z "$ttft" ]] && jq -e '(.response // "") != ""' >/dev/null 2>&1 <<<"$line"; then
      ttft=$(date +%s%N)
    fi
    if [[ -z "$first_thinking" ]] && jq -e '(.thinking // "") != ""' >/dev/null 2>&1 <<<"$line"; then
      first_thinking=$(date +%s%N)
    fi
    if jq -e '.done == true' >/dev/null 2>&1 <<<"$line"; then
      done_seen=1
      printf '%s\n' "$line" > "$final_file"
    fi
  done < <(curl -fsS --max-time 600 "$OLLAMA_URL/api/generate" -H 'Content-Type: application/json' -d "$payload")
  kill "$sampler_pid" 2>/dev/null || true
  wait "$sampler_pid" 2>/dev/null || true
  (( had_error )) && return 4
  (( done_seen )) || return 4
  return 0
}

run_case() {
  local label="$1" prompt="$2" max_predict="$3" i phase payload
  for ((i=1;i<=REPEATS;i++)); do
    if (( i == 1 )); then
      phase="cold"
    else
      if (( i == 2 )); then
        payload=$(jq -nc --arg model "$MODEL" --arg prompt "$prompt" --argjson ctx "$CTX" --argjson predict "$max_predict" '{model:$model,prompt:$prompt,stream:true,options:{num_ctx:$ctx,num_predict:$predict,temperature:0.2}}')
        curl -fsS --max-time 600 "$OLLAMA_URL/api/generate" -H 'Content-Type: application/json' -d "$payload" >/dev/null || { echo "ERRO: aquecimento falhou" >&2; exit 3; }
      fi
      phase="warm"
    fi

    payload=$(jq -nc --arg model "$MODEL" --arg prompt "$prompt" --argjson ctx "$CTX" --argjson predict "$max_predict" '{model:$model,prompt:$prompt,stream:true,options:{num_ctx:$ctx,num_predict:$predict,temperature:0.2}}')
    local start end total_ms ttft_json ft_json peak_vram_json
    start=$(date +%s%N)
    final_file=$(mktemp)
    vram_file=$(mktemp)
    if ! run_generation "$payload" "$final_file" "$vram_file"; then
      rm -f "$final_file" "$vram_file"
      echo "ERRO: stream invalido ou incompleto na repeticao $i" >&2
      exit 4
    fi
    end=$(date +%s%N)
    total_ms=$(( (end-start)/1000000 ))

    if [[ -n "$ttft" ]]; then
      ttft_json=$(( (ttft-start)/1000000 ))
    else
      ttft_json="null"
    fi
    if [[ -n "$first_thinking" ]]; then
      ft_json=$(( (first_thinking-start)/1000000 ))
    else
      ft_json="null"
    fi
    if [[ -s "$vram_file" ]]; then
      peak_vram_json=$(jq -s 'max' "$vram_file" 2>/dev/null) || peak_vram_json="null"
    else
      peak_vram_json="null"
    fi

    local eval_count eval_duration prompt_eval_count tps_json
    eval_count=$(jq -r '.eval_count // "null"' "$final_file")
    eval_duration=$(jq -r '.eval_duration // "null"' "$final_file")
    prompt_eval_count=$(jq -r '.prompt_eval_count // "null"' "$final_file")
    if [[ "$eval_count" != "null" && "$eval_duration" != "null" && "$eval_duration" -gt 0 ]]; then
      tps_json=$(jq -n --argjson c "$eval_count" --argjson d "$eval_duration" '($c / ($d / 1000000000))')
    else
      tps_json="null"
    fi

    jq -nc \
      --arg model "$MODEL" --argjson ctx "$CTX" --arg case "$label" \
      --argjson repeat "$i" --arg phase "$phase" \
      --argjson ttft_ms "$ttft_json" --argjson first_thinking_ms "$ft_json" \
      --argjson total_ms "$total_ms" --argjson peak_vram_mb "$peak_vram_json" \
      --argjson prompt_eval_count "$prompt_eval_count" \
      --argjson eval_count "$eval_count" --argjson eval_duration "$eval_duration" \
      --argjson tokens_per_second "$tps_json" \
      --slurpfile metrics "$final_file" \
      '{timestamp:now,model:$model,num_ctx:$ctx,case:$case,repeat:$repeat,phase:$phase,ttft_ms:$ttft_ms,first_thinking_ms:$first_thinking_ms,total_ms:$total_ms,peak_vram_mb:$peak_vram_mb,prompt_eval_count:$prompt_eval_count,eval_count:$eval_count,eval_duration_ns:$eval_duration,tokens_per_second:$tokens_per_second,metrics:$metrics[0]}' >> "$OUT"
    rm -f "$final_file" "$vram_file"
  done
}

run_case short "$SHORT_PROMPT" 128
run_case long "$LONG_PROMPT" 512

jq -s '
  def median: sort | if length == 0 then null else .[length/2|floor] end;
  group_by(.case) | map({
    case: .[0].case,
    runs: length,
    ttft_ms_median: (map(.ttft_ms | select(. != null)) | median),
    total_ms_median: (map(.total_ms) | median),
    tokens_per_second_median: (map(.tokens_per_second | select(. != null)) | median),
    peak_vram_mb_max: (map(.peak_vram_mb | select(. != null)) | max // null),
    prompt_eval_count_median: (map(.prompt_eval_count | select(. != null)) | median)
  })
' "$OUT" > "${OUT%.jsonl}.summary.json"

echo "Benchmark concluido: $OUT"
echo "Resumo: ${OUT%.jsonl}.summary.json"
