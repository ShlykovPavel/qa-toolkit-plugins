#!/bin/bash
# run_tests_docker_compose.sh — Pull images, start docker-compose, run regression tests.
# Usage: ./run_tests_docker_compose.sh

set -e

RESULTS_DIR="all_results"
ALLURE_RESULTS_DIR="$RESULTS_DIR/allure-results"
ALLURE_REPORT_DIR="$RESULTS_DIR/allure-report"
LOGS_DIR="$RESULTS_DIR/logs"

echo "Pulling latest Docker images..."
docker-compose pull

echo "Starting services..."
docker-compose up -d

echo "Waiting for services to become ready..."
sleep 20  # replace with a healthcheck loop if needed

# Clean previous results
rm -rf "$RESULTS_DIR"
mkdir -p "$ALLURE_RESULTS_DIR" "$ALLURE_REPORT_DIR" "$LOGS_DIR"

echo "Running regression tests..."
pytest -v --alluredir="$ALLURE_RESULTS_DIR" Tests/Regression_tests | tee "$LOGS_DIR/pytest_output.log"

echo "Generating Allure report..."
allure generate --single-file "$ALLURE_RESULTS_DIR" -o "$ALLURE_REPORT_DIR" --clean

echo "Done. Report saved to $ALLURE_REPORT_DIR"

# Uncomment to stop containers after tests:
# docker-compose down -v
