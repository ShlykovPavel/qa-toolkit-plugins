#!/bin/bash
# run_big_smoke_tests.sh — Run smoke tests and generate an Allure report.
# Usage: ./run_big_smoke_tests.sh

set -e

ALLURE_RESULTS_DIR="testresults/"
ALLURE_REPORT_DIR="allure-report/"
LOG_FILE="logs/pytest_output.log"

mkdir -p logs

# Clear previous results
rm -rf "$ALLURE_RESULTS_DIR" "$ALLURE_REPORT_DIR"

echo "Running smoke tests..."
# Код возврата берём у pytest, а не у tee: пайп маскирует падения.
# 0 — все тесты прошли; 1 — есть падения; 5 — не собрано ни одного теста.
set +e
pytest -v --alluredir="$ALLURE_RESULTS_DIR" Tests/Smoke_tests | tee "$LOG_FILE"
PYTEST_EXIT_CODE=${PIPESTATUS[0]}
set -e

echo "Generating Allure report..."
allure generate --single-file "$ALLURE_RESULTS_DIR" -o "$ALLURE_REPORT_DIR" --clean

if [ "$PYTEST_EXIT_CODE" -ne 0 ]; then
    echo "WARNING: pytest exited with code $PYTEST_EXIT_CODE — check the Allure report."
    exit "$PYTEST_EXIT_CODE"
else
    echo "All smoke tests passed!"
fi
