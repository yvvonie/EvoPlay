#!/bin/bash
# GPT-5.4 models: 2048 + MergeFall, all difficulties, no max steps (play until game over)

MODELS="gpt-5.4 gpt-5.4-mini gpt-5.4-nano"
DIFFICULTIES="easy medium hard"

run() {
  local model=$1 game=$2 diff=$3
  echo ""
  echo "=========================================="
  echo "  $model | $game | $diff"
  echo "=========================================="

  conda run -n evoplay python agent/main.py --game $game --model $model --difficulty $diff --delay 1 --max-tokens 50
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
