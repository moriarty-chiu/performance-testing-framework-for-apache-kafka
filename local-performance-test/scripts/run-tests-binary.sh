#!/bin/bash

# Kafka Performance Test Runner - Binary Version
# Uses locally installed Kafka binaries instead of Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_ROOT/config"
RESULTS_DIR="$PROJECT_ROOT/results"

# Default Kafka installation path - modify this to match your setup
KAFKA_HOME="${KAFKA_HOME:-/opt/kafka}"
KAFKA_BIN="$KAFKA_HOME/bin"

# Check if Kafka is installed
if [ ! -d "$KAFKA_HOME" ] || [ ! -d "$KAFKA_BIN" ]; then
    echo "❌ Kafka not found at $KAFKA_HOME"
    echo "Please set KAFKA_HOME environment variable to your Kafka installation directory"
    echo "Or modify the KAFKA_HOME variable in this script"
    exit 1
fi

# Check if required Kafka tools exist
required_tools=("kafka-topics.sh" "kafka-producer-perf-test.sh" "kafka-consumer-perf-test.sh")
for tool in "${required_tools[@]}"; do
    if [ ! -f "$KAFKA_BIN/$tool" ]; then
        echo "❌ Required Kafka tool not found: $KAFKA_BIN/$tool"
        exit 1
    fi
done

# Load configuration
source "$CONFIG_DIR/kafka.properties"

echo "🚀 Starting Kafka Performance Tests (Binary Mode)"
echo "Kafka Home: $KAFKA_HOME"
echo "Kafka Bootstrap Servers: $bootstrap.servers"
echo "Results will be saved to: $RESULTS_DIR"

# Function to run a single test
run_test() {
    local throughput=$1
    local consumer_groups=$2
    local test_id=$3
    
    echo "🧪 Running test: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}"
    
    local topic_name="perf-test-${test_id}-throughput-${throughput}-consumers-${consumer_groups}"
    local num_jobs=$((6 + consumer_groups * 6))  # 6 producers + (groups * 6 consumers)
    local records_per_sec=$((throughput * 1024 * 1024 / 1024))  # throughput in records/sec
    local duration_sec=300
    local record_size=1024
    
    # Create topic using Kafka binary tools
    echo "Creating topic: $topic_name"
    "$KAFKA_BIN/kafka-topics.sh" \
        --bootstrap-server "$bootstrap.servers" \
        --create \
        --topic "$topic_name" \
        --partitions 36 \
        --replication-factor 3 \
        --config retention.ms=60000 \
        2>/dev/null || true
    
    # Wait for topic creation
    sleep 5
    
    # Array to store background process PIDs
    declare -a pids
    
    # Run producers (first 6 jobs)
    for ((i=0; i<6; i++)); do
        local producer_log="$RESULTS_DIR/test-${test_id}-producer-${i}.log"
        
        echo "Starting producer $i"
        "$KAFKA_BIN/kafka-producer-perf-test.sh" \
            --topic "$topic_name" \
            --num-records $((records_per_sec * duration_sec)) \
            --throughput $records_per_sec \
            --record-size $record_size \
            --producer-props "bootstrap.servers=$bootstrap.servers" \
            --producer-props "acks=all" \
            --producer-props "linger.ms=5" \
            --producer-props "batch.size=262114" \
            --producer-props "buffer.memory=2147483648" \
            > "$producer_log" 2>&1 &
        
        pids+=($!)
    done
    
    # Run consumers (remaining jobs)
    local consumer_group_count=0
    for ((i=6; i<num_jobs; i++)); do
        local consumer_log="$RESULTS_DIR/test-${test_id}-consumer-${consumer_group_count}-$((i-6)).log"
        local group_id="perf-test-consumer-group-${test_id}-${consumer_group_count}"
        
        echo "Starting consumer in group $group_id"
        "$KAFKA_BIN/kafka-consumer-perf-test.sh" \
            --topic "$topic_name" \
            --broker-list "$bootstrap.servers" \
            --group "$group_id" \
            --messages $((records_per_sec * duration_sec / 6)) \
            --print-metrics \
            --show-detailed-stats \
            --timeout $((duration_sec * 1000 + 10000)) \
            > "$consumer_log" 2>&1 &
        
        pids+=($!)
        
        # Increment group counter every 6 consumers
        if (((i-5) % 6 == 0)); then
            ((consumer_group_count++))
        fi
    done
    
    # Wait for all jobs to complete
    echo "Waiting for all test jobs to complete..."
    for pid in "${pids[@]}"; do
        wait $pid
    done
    
    # Delete topic
    echo "Cleaning up topic: $topic_name"
    "$KAFKA_BIN/kafka-topics.sh" \
        --bootstrap-server "$bootstrap.servers" \
        --delete \
        --topic "$topic_name" \
        2>/dev/null || true
    
    echo "✅ Test completed: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}"
}

# Parse test specification
echo "📋 Parsing test configuration..."
test_spec=$(cat "$CONFIG_DIR/test-spec.json")

# Extract parameters (simplified parsing for this example)
# In production, you'd want to properly parse the JSON
throughput_values=(16 24 32 40 48 56 64 72 80)
consumer_group_configs=(0 1 2)

# Create results directory
mkdir -p "$RESULTS_DIR"

test_counter=1

# Run all test combinations
for throughput in "${throughput_values[@]}"; do
    for consumer_groups in "${consumer_group_configs[@]}"; do
        run_test $throughput $consumer_groups $test_counter
        ((test_counter++))
        sleep 10  # Brief pause between tests
    done
done

echo "🎉 All tests completed!"
echo "📊 Results saved in: $RESULTS_DIR"
echo "Next steps:"
echo "1. Process results with: python $SCRIPT_DIR/process-results-binary.py"
echo "2. Generate charts with: python $SCRIPT_DIR/generate-charts.py"