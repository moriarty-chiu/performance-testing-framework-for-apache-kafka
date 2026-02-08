#!/bin/bash

# Performance Testing Suite for Different Cluster Flavors
# This script runs comprehensive tests to find performance limits

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_ROOT/config"
RESULTS_DIR="$PROJECT_ROOT/results"

# Default Kafka installation path - modify this to match your setup
KAFKA_HOME="${KAFKA_HOME:-/opt/kafka}"
KAFKA_BIN="$KAFKA_HOME/bin"

# Function to run test for specific flavor
run_flavor_test() {
    local flavor=$1
    local config_file=$2
    local flavor_results_dir="$RESULTS_DIR/$flavor"
    
    echo "🚀 Starting $flavor cluster performance test"
    echo "Config: $config_file"
    echo "Results will be saved to: $flavor_results_dir"
    
    # Create flavor-specific results directory
    mkdir -p "$flavor_results_dir"
    
    # Backup current config
    cp "$CONFIG_DIR/test-spec.json" "$CONFIG_DIR/test-spec.json.backup"
    
    # Copy flavor config
    cp "$config_file" "$CONFIG_DIR/test-spec.json"
    
    # Run the test - use binary version
    echo "Starting test execution..."
    "$SCRIPT_DIR/run-tests-binary.sh"
    
    # Move results to flavor directory
    mv "$RESULTS_DIR"/test-*.log "$flavor_results_dir/" 2>/dev/null || true
    
    # Restore original config
    mv "$CONFIG_DIR/test-spec.json.backup" "$CONFIG_DIR/test-spec.json"
    
    echo "✅ $flavor test completed"
    echo "Results in: $flavor_results_dir"
    echo "----------------------------------------"
}

# Function to generate comparative analysis
generate_comparison() {
    echo "📊 Generating comparative performance analysis..."
    
    local comparison_dir="$RESULTS_DIR/comparison"
    mkdir -p "$comparison_dir"
    
    # Process each flavor's results
    for flavor in small medium large xlarge; do
        if [ -d "$RESULTS_DIR/$flavor" ]; then
            echo "Processing $flavor results..."
            python "$SCRIPT_DIR/process-results-binary.py" \
                --results-dir "$RESULTS_DIR/$flavor" \
                --output "$comparison_dir/${flavor}-results.json"
        fi
    done
    
    # Generate comparison charts
    python "$SCRIPT_DIR/generate-comparison-charts.py" \
        --input-dir "$comparison_dir" \
        --output-dir "$comparison_dir"
    
    echo "📈 Comparison charts generated in: $comparison_dir"
}

# Main execution
main() {
    echo "=== Kafka Cluster Performance Testing Suite ==="
    echo "Finding performance limits for different cluster flavors"
    echo
    
    # Check if Kafka is available (for binary mode)
    if [ ! -f "$SCRIPT_DIR/run-tests-binary.sh" ]; then
        echo "❌ Binary test script not found at $SCRIPT_DIR/run-tests-binary.sh"
        echo "Please ensure the binary mode scripts are present"
        exit 1
    fi
    
    if [ ! -d "$KAFKA_HOME" ] || [ ! -d "$KAFKA_BIN" ]; then
        echo "❌ Kafka not found at $KAFKA_HOME for binary mode"
        echo "Please set KAFKA_HOME environment variable to your Kafka installation directory"
        exit 1
    fi
    echo "Using binary mode with Kafka at: $KAFKA_HOME"
    
    # Check if Python dependencies are installed
    if ! python -c "import matplotlib, numpy" &> /dev/null; then
        echo "Installing Python dependencies..."
        pip install -r "$PROJECT_ROOT/requirements.txt"
    fi
    
    # Run tests for each flavor
    echo "Starting performance limit testing..."
    
    # Small cluster test
    run_flavor_test "small" "$CONFIG_DIR/test-spec-small.json"
    
    # Medium cluster test  
    run_flavor_test "medium" "$CONFIG_DIR/test-spec-medium.json"
    
    # Large cluster test
    run_flavor_test "large" "$CONFIG_DIR/test-spec-large.json"
    
    # XLarge cluster test
    run_flavor_test "xlarge" "$CONFIG_DIR/test-spec-xlarge.json"
    
    # Generate comparative analysis
    generate_comparison
    
    echo "🎉 All performance tests completed!"
    echo "Summary of results:"
    echo "- Small cluster: Baseline performance"
    echo "- Medium cluster: Standard production workload"
    echo "- Large cluster: High-throughput scenarios"  
    echo "- XLarge cluster: Maximum capacity testing"
    echo
    echo "Check individual results in: $RESULTS_DIR/{flavor}/"
    echo "Check comparison analysis in: $RESULTS_DIR/comparison/"
}

# Run main function
main "$@"