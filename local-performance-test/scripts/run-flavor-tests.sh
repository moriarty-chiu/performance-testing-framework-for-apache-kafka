#!/bin/bash

# Performance Testing Suite for Different Cluster Flavors
# This script runs comprehensive tests to find performance limits

set -e

# Parse command-line arguments
SKIP_ENV_CHECK=false
USE_MOCK_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-env-check)
            SKIP_ENV_CHECK=true
            shift
            ;;
        --use-mock-data)
            USE_MOCK_DATA=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--skip-env-check] [--use-mock-data]"
            exit 1
            ;;
    esac
done

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

    echo "Starting $flavor cluster performance test"
    echo "Config: $config_file"
    echo "Results will be saved to: $flavor_results_dir"

    # Create flavor-specific results directory
    mkdir -p "$flavor_results_dir"

    # Backup current config
    cp "$CONFIG_DIR/test-spec.json" "$CONFIG_DIR/test-spec.json.backup"

    # Copy flavor config
    cp "$config_file" "$CONFIG_DIR/test-spec.json"

    # Run the test - use binary version with same flags
    echo "Starting test execution..."
    "$SCRIPT_DIR/run-tests-binary.sh" $( [ "$SKIP_ENV_CHECK" = true ] && echo "--skip-env-check" ) $( [ "$USE_MOCK_DATA" = true ] && echo "--use-mock-data" )

    # Move results to flavor directory
    mv "$RESULTS_DIR"/test-*.log "$flavor_results_dir/" 2>/dev/null || true

    # Restore original config
    mv "$CONFIG_DIR/test-spec.json.backup" "$CONFIG_DIR/test-spec.json"

    echo "$flavor test completed"
    echo "Results in: $flavor_results_dir"
    echo "----------------------------------------"
}

# Function to generate comparative analysis
generate_comparison() {
    echo "Generating comparative performance analysis..."

    local comparison_dir="$RESULTS_DIR/comparison"
    mkdir -p "$comparison_dir"

    # Process each flavor's results
    for flavor in small medium large xlarge; do
        if [ -d "$RESULTS_DIR/$flavor" ]; then
            echo "Processing $flavor results..."
            if [ -f "$RESULTS_DIR/$flavor/mock-$flavor-results.json" ]; then
                # If mock results exist, copy them instead of processing real results
                echo "Using mock results for $flavor"
                cp "$RESULTS_DIR/$flavor/mock-$flavor-results.json" "$comparison_dir/${flavor}-results.json"
            else
                # Process real results
                PYTHON_CMD="python3"
                if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
                    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
                fi
                
                $PYTHON_CMD "$SCRIPT_DIR/process-results-binary.py" \
                    --results-dir "$RESULTS_DIR/$flavor" \
                    --output "$comparison_dir/${flavor}-results.json"
            fi
        fi
    done

    # Generate comparison charts
    PYTHON_CMD="python3"
    if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
        PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    fi
    
    $PYTHON_CMD "$SCRIPT_DIR/generate-comparison-charts.py" \
        --input-dir "$comparison_dir" \
        --output-dir "$comparison_dir"

    echo "Comparison charts generated in: $comparison_dir"
}

# Main execution
main() {
    echo "=== Kafka Cluster Performance Testing Suite ==="
    echo "Finding performance limits for different cluster flavors"
    echo

    # Check if Kafka is available (for binary mode)
    if [ ! -f "$SCRIPT_DIR/run-tests-binary.sh" ]; then
        echo "[ERROR] Binary test script not found at $SCRIPT_DIR/run-tests-binary.sh"
        echo "Please ensure the binary mode scripts are present"
        exit 1
    fi

    # Skip environment validation if requested
    if [ "$SKIP_ENV_CHECK" = false ]; then
        if [ ! -d "$KAFKA_HOME" ] || [ ! -d "$KAFKA_BIN" ]; then
            echo "[ERROR] Kafka not found at $KAFKA_HOME for binary mode"
            echo "Please set KAFKA_HOME environment variable to your Kafka installation directory"
            exit 1
        fi
        echo "Using binary mode with Kafka at: $KAFKA_HOME"
    else
        echo "[INFO] Skipping environment validation as requested"
    fi

    # Check if Python dependencies are installed
    PYTHON_CMD="python3"
    if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
        PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    fi

    if ! $PYTHON_CMD -c "import matplotlib, numpy" &> /dev/null; then
        echo "Installing Python dependencies..."
        $PYTHON_CMD -m pip install -r "$PROJECT_ROOT/requirements.txt"
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

    # If using mock data, also generate mock results for analysis
    if [ "$USE_MOCK_DATA" = true ]; then
        generate_mock_results
    fi

    echo "All performance tests completed!"
    echo "Summary of results:"
    echo "- Small cluster: Baseline performance"
    echo "- Medium cluster: Standard production workload"
    echo "- Large cluster: High-throughput scenarios"
    echo "- XLarge cluster: Maximum capacity testing"
    echo
    echo "Check individual results in: $RESULTS_DIR/{flavor}/"
    echo "Check comparison analysis in: $RESULTS_DIR/comparison/"
}

# Function to generate mock results for analysis tools
generate_mock_results() {
    echo "Generating mock results for analysis tools..."
    
    # Create mock results for each flavor
    for flavor in small medium large xlarge; do
        local mock_result_file="$RESULTS_DIR/$flavor/mock-$flavor-results.json"
        mkdir -p "$RESULTS_DIR/$flavor"
        
        cat > "$mock_result_file" << EOF
{
  "test_results": [
    {
      "test_id": "$flavor-mock-test-1",
      "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "parameters": {
        "throughput_target": 5,
        "consumer_groups": 1,
        "num_producers": 2,
        "num_partitions": 6,
        "replication_factor": 3,
        "duration_sec": 60,
        "record_size_byte": 1024
      },
      "producer_metrics": {
        "avg_records_per_sec": 4950,
        "avg_mb_per_sec": 4.83,
        "avg_latency_ms": 22.1,
        "max_latency_ms": 95
      },
      "consumer_metrics": {
        "avg_records_per_sec": 4900,
        "avg_mb_per_sec": 4.78,
        "avg_latency_ms": 23.5,
        "max_latency_ms": 102
      }
    }
  ]
}
EOF
    done

    # Also create a comparison mock results file
    local comparison_dir="$RESULTS_DIR/comparison"
    mkdir -p "$comparison_dir"
    local mock_comparison_file="$comparison_dir/mock-comparison-results.json"
    
    cat > "$mock_comparison_file" << EOF
{
  "comparison_results": {
    "small": {
      "avg_throughput_mb_per_sec": 4.83,
      "avg_producer_latency_ms": 22.1,
      "avg_consumer_latency_ms": 23.5
    },
    "medium": {
      "avg_throughput_mb_per_sec": 9.65,
      "avg_producer_latency_ms": 19.8,
      "avg_consumer_latency_ms": 20.9
    },
    "large": {
      "avg_throughput_mb_per_sec": 14.21,
      "avg_producer_latency_ms": 17.3,
      "avg_consumer_latency_ms": 18.2
    },
    "xlarge": {
      "avg_throughput_mb_per_sec": 18.76,
      "avg_producer_latency_ms": 16.2,
      "avg_consumer_latency_ms": 17.1
    }
  },
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

    echo "Mock results generated for all flavors and comparison"
}

# Run main function
main "$@"