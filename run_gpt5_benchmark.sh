#!/bin/bash
# Benchmark: gpt-5.4 / gpt-5.4-mini / gpt-5.4-nano across all games × all difficulties
# Sequential execution — each game finishes before the next starts

MODELS="gpt-5.4 gpt-5.4-mini gpt-5.4-nano"
DIFFICULTIES="easy medium hard"

# Games with max steps
# 2048 / mergefall: max 50 steps (single player, can run long)
# fourinarow / othello6 / tictactoe: no max steps (game ends naturally)

run() {
  local model=$1 game=$2 diff=$3 max_steps=$4
  echo ""
  echo "=========================================="
  echo "  $model | $game | $diff"
  echo "=========================================="

  CMD="conda run -n evoplay python agent/main.py --game $game --model $model --difficulty $diff --delay 1 --max-tokens 50"
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
    run "$model" "2048" "$diff" 50
  done

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
echo "  ALL BENCHMARKS COMPLETE"
echo "============================================"
echo ""

# Show cost analysis
conda run -n evoplay python analyze_cost.py
