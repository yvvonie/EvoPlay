#!/bin/bash
# EvoPlay LLM Benchmark Script
# Runs gpt-4o-mini on all games × all difficulties, then gemini-pro on mergefall
# Each task runs sequentially (waits for completion before next)

set -e

AGENT_CMD="conda run -n evoplay python agent/main.py"
DELAY=1

echo "=========================================="
echo "  EvoPlay LLM Benchmark"
echo "=========================================="

run_game() {
    local game=$1
    local model=$2
    local difficulty=$3
    local max_steps=$4
    local provider=${5:-"openai"}

    echo ""
    echo "------------------------------------------"
    echo "  Game: $game | Model: $model | Difficulty: $difficulty | Max steps: $max_steps"
    echo "------------------------------------------"

    $AGENT_CMD \
        --game "$game" \
        --model "$model" \
        --api-provider "$provider" \
        --difficulty "$difficulty" \
        --delay "$DELAY" \
        --max-steps "$max_steps" \
        --max-tokens 150

    echo "  Done: $game ($difficulty)"
}

# ── gpt-4o-mini runs ──────────────────────────────────────

echo ""
echo ">>> 2048 (gpt-4o-mini) max_steps=50"
for diff in easy medium hard; do
    run_game "2048" "gpt-4o-mini" "$diff" 50
done

echo ""
echo ">>> Tic Tac Toe (gpt-4o-mini)"
for diff in easy medium hard; do
    run_game "tictactoe" "gpt-4o-mini" "$diff" 0
done

echo ""
echo ">>> Othello 6x6 (gpt-4o-mini)"
for diff in easy medium hard; do
    run_game "othello6" "gpt-4o-mini" "$diff" 0
done

echo ""
echo ">>> Four in a Row (gpt-4o-mini)"
for diff in easy medium hard; do
    run_game "fourinarow" "gpt-4o-mini" "$diff" 0
done

echo ""
echo ">>> MergeFall (gpt-4o-mini) max_steps=50"
for diff in easy medium hard; do
    run_game "mergefall" "gpt-4o-mini" "$diff" 50
done

# ── gemini-3-pro-preview runs ─────────────────────────────

echo ""
echo ">>> MergeFall (gemini-3-pro-preview) max_steps=50"
for diff in easy medium hard; do
    run_game "mergefall" "gemini/gemini-3-pro-preview" "$diff" 50 "gemini"
done

echo ""
echo "=========================================="
echo "  Benchmark Complete!"
echo "  Logs: backend/logs/ and backend/llm_logs/"
echo "=========================================="
