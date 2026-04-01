#!/bin/bash
# Qwen3.5 models: 2048 + MergeFall, all difficulties, no max steps (play until game over)

MODELS="Qwen/Qwen3.5-397B-A17B Qwen/Qwen3.5-122B-A10B Qwen/Qwen3.5-35B-A3B Qwen/Qwen3.5-27B Qwen/Qwen3.5-9B Qwen/Qwen3.5-4B"
DIFFICULTIES="easy medium hard"

API_KEY="sk-mddpokffjxrahhhldcqayiykgdzuinoyixvepfbxecdczpcn"
API_BASE="https://api.siliconflow.cn/v1"

run() {
  local model=$1 game=$2 diff=$3
  echo ""
  echo "=========================================="
  echo "  $model | $game | $diff"
  echo "=========================================="

  conda run -n evoplay python agent/main.py --game $game --model openai/$model --api-key $API_KEY --api-base $API_BASE --difficulty $diff --delay 1 --max-tokens 150 --no-thinking
  echo "  → Done"
}

for model in $MODELS; do
  echo ""
  echo "############################################"
  echo "  MODEL: $model"
  echo "############################################"

  for diff in $DIFFICULTIES; do
    run "$model" "2048" "$diff"
  done

  for diff in $DIFFICULTIES; do
    run "$model" "mergefall" "$diff"
  done
done

echo ""
echo "============================================"
echo "  ALL BENCHMARKS COMPLETE"
echo "============================================"
conda run -n evoplay python analyze_cost.py
