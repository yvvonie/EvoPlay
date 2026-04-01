#!/bin/bash
# Continue Qwen benchmark from where it was interrupted
# 35B (from 2048 hard), 27B, 9B, 4B — all games × all difficulties

MODELS="Qwen/Qwen3.5-397B-A17B Qwen/Qwen3.5-122B-A10B Qwen/Qwen3.5-35B-A3B Qwen/Qwen3.5-27B Qwen/Qwen3.5-9B Qwen/Qwen3.5-4B"
DIFFICULTIES="easy medium hard"

API_KEY="sk-mddpokffjxrahhhldcqayiykgdzuinoyixvepfbxecdczpcn"
API_BASE="https://api.siliconflow.cn/v1"

SKIP_35B_EARLY=false

run() {
  local model=$1 game=$2 diff=$3 max_steps=$4
  echo ""
  echo "=========================================="
  echo "  $model | $game | $diff"
  echo "=========================================="

  CMD="conda run -n evoplay python agent/main.py --game $game --model openai/$model --api-key $API_KEY --api-base $API_BASE --difficulty $diff --delay 1 --max-tokens 150 --no-thinking"
  if [ -n "$max_steps" ]; then
    CMD="$CMD --max-steps $max_steps"
  fi

  eval $CMD
  echo "  → Done"
}

for model in $MODELS; do
  echo ""
  echo "############################################"
  echo "  MODEL: $model"
  echo "############################################"

  # 2048 (max 50 steps)
  for diff in $DIFFICULTIES; do
    if [ "$SKIP_35B_EARLY" = true ] && [ "$model" = "Qwen/Qwen3.5-35B-A3B" ] && [ "$diff" != "hard" ]; then
      echo "  Skipping $model 2048 $diff (already done)"
      continue
    fi
    run "$model" "2048" "$diff" 50
  done
  SKIP_35B_EARLY=false

  # MergeFall (max 50 steps)
  for diff in $DIFFICULTIES; do
    run "$model" "mergefall" "$diff" 50
  done

  # Four in a Row (no max steps)
  for diff in $DIFFICULTIES; do
    run "$model" "fourinarow" "$diff"
  done

  # Othello6 (no max steps)
  for diff in $DIFFICULTIES; do
    run "$model" "othello6" "$diff"
  done

  # Tic Tac Toe (no max steps)
  for diff in $DIFFICULTIES; do
    run "$model" "tictactoe" "$diff"
  done
done

echo ""
echo "============================================"
echo "  ALL REMAINING BENCHMARKS COMPLETE"
echo "============================================"
echo ""

conda run -n evoplay python analyze_cost.py
