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

# Function to check system resources
check_system_resources() {
    echo "🔍 Checking system resources..."
    
    # Check available memory
    if command -v free >/dev/null 2>&1; then
        # Linux system
        local total_memory_mb=$(free -m | awk 'NR==2{print $2}')
        local available_memory_mb=$(free -m | awk 'NR==2{print $7}')
    elif command -v vm_stat >/dev/null 2>&1; then
        # macOS system
        local pages_free=$(vm_stat | grep free | awk '{print $3}' | sed 's/\.//')
        local pages_inactive=$(vm_stat | grep inactive | awk '{print $3}' | sed 's/\.//')
        local page_size_kb=$(pagesize)
        local available_memory_mb=$(( (pages_free + pages_inactive) * page_size_kb / 1024 ))
        local total_memory_pages=$(sysctl hw.memsize | awk '{print $2}')
        local total_memory_mb=$((total_memory_pages / 1024 / 1024))
    else
        echo "⚠️  Unable to determine system memory, continuing without validation"
        return 0
    fi
    
    echo "Available memory: ${available_memory_mb}MB, Total memory: ${total_memory_mb}MB"
    
    # Warn if available memory is low
    if [ $available_memory_mb -lt 2048 ]; then
        echo "⚠️  Warning: Available memory is low (${available_memory_mb}MB). Tests may fail due to insufficient memory."
        echo "💡 Consider closing other applications or using smaller test configurations."
    fi
    
    # Check CPU cores
    if command -v nproc >/dev/null 2>&1; then
        # Linux
        local cpu_cores=$(nproc)
    elif command -v sysctl >/dev/null 2>&1; then
        # macOS
        local cpu_cores=$(sysctl -n hw.ncpu)
    else
        local cpu_cores=4  # Default assumption
    fi
    
    echo "CPU cores detected: $cpu_cores"
    
    # Recommend max number of concurrent processes based on resources
    local max_processes=$((cpu_cores * 2))
    echo "Recommended max concurrent processes: $max_processes"
}

# Perform system resource check
check_system_resources

echo "🚀 Starting Kafka Performance Tests (Binary Mode)"
echo "Kafka Home: $KAFKA_HOME"
echo "Kafka Bootstrap Servers: $bootstrap.servers"
echo "Results will be saved to: $RESULTS_DIR"

# Function to run a single test
run_test() {
    local throughput=$1
    local consumer_groups=$2
    local test_id=$3

    # Use configuration values from JSON, with defaults
    local num_producers=${num_producers_default:-6}
    local num_partitions=${num_partitions_default:-36}
    local replication_factor=${replication_factor_default:-3}
    local duration_sec=${duration_sec_default:-300}
    local record_size=${record_size_byte_default:-1024}

    echo "🧪 Running test: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}, num_producers=${num_producers}, partitions=${num_partitions}, replication=${replication_factor}"

    # Validate system resources before starting test
    local required_memory_mb=$((256 * num_producers))  # Rough estimate: 256MB per producer
    if command -v free >/dev/null 2>&1; then
        # Linux system
        local available_memory_mb=$(free -m | awk 'NR==2{print $7}')
    elif command -v vm_stat >/dev/null 2>&1; then
        # macOS system
        local pages_free=$(vm_stat | grep free | awk '{print $3}' | sed 's/\.//')
        local pages_inactive=$(vm_stat | grep inactive | awk '{print $3}' | sed 's/\.//')
        local page_size_kb=$(pagesize)
        local available_memory_mb=$(( (pages_free + pages_inactive) * page_size_kb / 1024 ))
    else
        echo "⚠️  Unable to determine available memory, skipping validation"
        local available_memory_mb=8192  # Assume 8GB if we can't determine
    fi

    if [ $available_memory_mb -lt $required_memory_mb ]; then
        echo "⚠️  Warning: Estimated required memory (${required_memory_mb}MB) exceeds available memory (${available_memory_mb}MB)"
        echo "⚠️  Consider reducing num_producers or adjusting buffer.memory in client_props"
    fi

    local topic_name="perf-test-${test_id}-throughput-${throughput}-consumers-${consumer_groups}"
    local num_jobs=$(($num_producers + consumer_groups * 6))  # num_producers + (groups * 6 consumers)
    local records_per_sec=$((throughput * 1024 * 1024 / $record_size))  # throughput in records/sec

    # Create topic using Kafka binary tools
    echo "Creating topic: $topic_name with $num_partitions partitions and replication factor $replication_factor"
    if ! "$KAFKA_BIN/kafka-topics.sh" \
        --bootstrap-server "$bootstrap.servers" \
        --create \
        --topic "$topic_name" \
        --partitions $num_partitions \
        --replication-factor $replication_factor \
        --config retention.ms=60000; then
        echo "❌ Failed to create topic $topic_name"
        return 1
    fi

    # Wait for topic creation
    sleep 5

    # Array to store background process PIDs
    declare -a pids

    # Extract client properties from configuration
    # For simplicity, we'll use a default set of properties, but ideally these should come from config
    local producer_props="acks=all linger.ms=5 batch.size=262114"
    
    # Try to get producer and consumer properties from the configuration if available
    python3 << EOF > /tmp/current_client_props.sh
import json
import sys

try:
    with open('$CONFIG_DIR/test-spec.json', 'r') as f:
        config = json.load(f)
    
    spec = config['test_specification']['parameters']
    client_props_list = spec.get('client_props', [])
    
    if client_props_list:
        # Use the first client_props entry as default
        producer_props_str = client_props_list[0].get('producer', 'acks=all linger.ms=5 batch.size=262114')
        consumer_props_str = client_props_list[0].get('consumer', '')  # Consumer props might be empty
        
        # Extract buffer.memory from producer_props if present
        import re
        buffer_match = re.search(r'buffer\.memory=(\d+)', producer_props_str)
        if buffer_match:
            buffer_memory = buffer_match.group(1)
        else:
            buffer_memory = '2147483648'  # Default to 2GB if not specified
        
        # Write to temporary file
        with open('/tmp/current_client_props.sh', 'w') as f:
            f.write(f"CLIENT_PRODUCER_PROPS=\"{producer_props_str}\"\n")
            f.write(f"CLIENT_CONSUMER_PROPS=\"{consumer_props_str}\"\n")
            f.write(f"CLIENT_BUFFER_MEMORY=\"{buffer_memory}\"\n")
    else:
        # Default values
        with open('/tmp/current_client_props.sh', 'w') as f:
            f.write("CLIENT_PRODUCER_PROPS=\"acks=all linger.ms=5 batch.size=262114\"\n")
            f.write("CLIENT_CONSUMER_PROPS=\"\"\n")
            f.write("CLIENT_BUFFER_MEMORY=\"2147483648\"\n")

except Exception as e:
    print(f"Error parsing client_props: {e}", file=sys.stderr)
    # Write default values
    with open('/tmp/current_client_props.sh', 'w') as f:
        f.write("CLIENT_PRODUCER_PROPS=\"acks=all linger.ms=5 batch.size=262114\"\n")
        f.write("CLIENT_CONSUMER_PROPS=\"\"\n")
        f.write("CLIENT_BUFFER_MEMORY=\"2147483648\"\n")
EOF

    # Source the client properties
    if [ -f "/tmp/current_client_props.sh" ]; then
        source "/tmp/current_client_props.sh"
    else
        # Default values
        CLIENT_PRODUCER_PROPS="acks=all linger.ms=5 batch.size=262114"
        CLIENT_BUFFER_MEMORY="2147483648"
    fi

    # Run producers (first num_producers jobs)
    for ((i=0; i<num_producers; i++)); do
        local producer_log="$RESULTS_DIR/test-${test_id}-producer-${i}.log"

        echo "Starting producer $i with properties: $CLIENT_PRODUCER_PROPS"
        "$KAFKA_BIN/kafka-producer-perf-test.sh" \
            --topic "$topic_name" \
            --num-records $((records_per_sec * duration_sec)) \
            --throughput $records_per_sec \
            --record-size $record_size \
            --producer-props "bootstrap.servers=$bootstrap.servers" \
            $(echo "$CLIENT_PRODUCER_PROPS" | sed 's/ /\ --producer-props /g') \
            > "$producer_log" 2>&1 &

        pids+=($!)
    done

    # Run consumers (remaining jobs)
    local consumer_group_count=0
    for ((i=num_producers; i<num_jobs; i++)); do
        local consumer_log="$RESULTS_DIR/test-${test_id}-consumer-${consumer_group_count}-$((i-num_producers)).log"
        local group_id="perf-test-consumer-group-${test_id}-${consumer_group_count}"

        echo "Starting consumer in group $group_id with properties: $CLIENT_CONSUMER_PROPS"
        "$KAFKA_BIN/kafka-consumer-perf-test.sh" \
            --topic "$topic_name" \
            --broker-list "$bootstrap.servers" \
            --group "$group_id" \
            --messages $((records_per_sec * duration_sec / num_producers)) \
            --print-metrics \
            --show-detailed-stats \
            --timeout $((duration_sec * 1000 + 10000)) \
            $(if [ -n "$CLIENT_CONSUMER_PROPS" ]; then echo "$CLIENT_CONSUMER_PROPS" | sed 's/ /\ --consumer-props /g'; else echo ""; fi) \
            > "$consumer_log" 2>&1 &

        pids+=($!)

        # Increment group counter every 6 consumers
        if (((i-num_producers+1) % 6 == 0)); then
            ((consumer_group_count++))
        fi
    done
}

# Function to run a single test with specific parameters
run_test_with_params() {
    local throughput=$1
    local consumer_groups=$2
    local test_id=$3
    local num_producers=$4
    local num_partitions=$5
    local replication_factor=$6
    local duration_sec=$7
    local record_size=$8

    # Source the client properties for this test
    if [ -f "/tmp/current_client_props.sh" ]; then
        source "/tmp/current_client_props.sh"
    else
        # Default values
        CLIENT_PRODUCER_PROPS="acks=all linger.ms=5 batch.size=262114"
        CLIENT_BUFFER_MEMORY="2147483648"
    fi

    echo "🧪 Running test: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}, num_producers=${num_producers}, partitions=${num_partitions}, replication=${replication_factor}"

    # Validate system resources before starting test
    local required_memory_mb=$((256 * num_producers))  # Rough estimate: 256MB per producer
    if command -v free >/dev/null 2>&1; then
        # Linux system
        local available_memory_mb=$(free -m | awk 'NR==2{print $7}')
    elif command -v vm_stat >/dev/null 2>&1; then
        # macOS system
        local pages_free=$(vm_stat | grep free | awk '{print $3}' | sed 's/\.//')
        local pages_inactive=$(vm_stat | grep inactive | awk '{print $3}' | sed 's/\.//')
        local page_size_kb=$(pagesize)
        local available_memory_mb=$(( (pages_free + pages_inactive) * page_size_kb / 1024 ))
    else
        echo "⚠️  Unable to determine available memory, skipping validation"
        local available_memory_mb=8192  # Assume 8GB if we can't determine
    fi

    if [ $available_memory_mb -lt $required_memory_mb ]; then
        echo "⚠️  Warning: Estimated required memory (${required_memory_mb}MB) exceeds available memory (${available_memory_mb}MB)"
        echo "⚠️  Consider reducing num_producers or adjusting buffer.memory in client_props"
    fi

    local topic_name="perf-test-${test_id}-throughput-${throughput}-consumers-${consumer_groups}"
    local num_jobs=$(($num_producers + consumer_groups * 6))  # num_producers + (groups * 6 consumers)
    local records_per_sec=$((throughput * 1024 * 1024 / $record_size))  # throughput in records/sec

    # Create topic using Kafka binary tools
    echo "Creating topic: $topic_name with $num_partitions partitions and replication factor $replication_factor"
    if ! "$KAFKA_BIN/kafka-topics.sh" \
        --bootstrap-server "$bootstrap.servers" \
        --create \
        --topic "$topic_name" \
        --partitions $num_partitions \
        --replication-factor $replication_factor \
        --config retention.ms=60000; then
        echo "❌ Failed to create topic $topic_name"
        return 1
    fi

    # Wait for topic creation
    sleep 5

    # Array to store background process PIDs
    declare -a pids

    # Run producers (first num_producers jobs)
    for ((i=0; i<num_producers; i++)); do
        local producer_log="$RESULTS_DIR/test-${test_id}-producer-${i}.log"

        echo "Starting producer $i with properties: $CLIENT_PRODUCER_PROPS"
        "$KAFKA_BIN/kafka-producer-perf-test.sh" \
            --topic "$topic_name" \
            --num-records $((records_per_sec * duration_sec)) \
            --throughput $records_per_sec \
            --record-size $record_size \
            --producer-props "bootstrap.servers=$bootstrap.servers" \
            $(echo "$CLIENT_PRODUCER_PROPS" | sed 's/ /\ --producer-props /g') \
            > "$producer_log" 2>&1 &

        pids+=($!)
    done

    # Run consumers (remaining jobs)
    local consumer_group_count=0
    for ((i=num_producers; i<num_jobs; i++)); do
        local consumer_log="$RESULTS_DIR/test-${test_id}-consumer-${consumer_group_count}-$((i-num_producers)).log"
        local group_id="perf-test-consumer-group-${test_id}-${consumer_group_count}"

        echo "Starting consumer in group $group_id with properties: $CLIENT_CONSUMER_PROPS"
        "$KAFKA_BIN/kafka-consumer-perf-test.sh" \
            --topic "$topic_name" \
            --broker-list "$bootstrap.servers" \
            --group "$group_id" \
            --messages $((records_per_sec * duration_sec / num_producers)) \
            --print-metrics \
            --show-detailed-stats \
            --timeout $((duration_sec * 1000 + 10000)) \
            $(if [ -n "$CLIENT_CONSUMER_PROPS" ]; then echo "$CLIENT_CONSUMER_PROPS" | sed 's/ /\ --consumer-props /g'; else echo ""; fi) \
            > "$consumer_log" 2>&1 &

        pids+=($!)

        # Increment group counter every 6 consumers
        if (((i-num_producers+1) % 6 == 0)); then
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
        2>/dev/null || echo "Warning: Could not delete topic $topic_name"

    echo "✅ Test completed: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}"
}
    
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

# Function to run all tests based on configuration
run_all_tests_from_config() {
    # Parse test specification from JSON using Python for proper parsing
    echo "📋 Parsing test configuration..."

    # Use Python to extract parameters from test-spec.json
    python3 << EOF
import json
import sys

try:
    with open('$CONFIG_DIR/test-spec.json', 'r') as f:
        config = json.load(f)

    # Extract parameters from the JSON configuration
    spec = config['test_specification']['parameters']

    # Write to temporary file for shell to source
    with open('/tmp/kafka_test_params.sh', 'w') as temp_file:
        # Process throughput values
        throughput_values = spec.get('cluster_throughput_mb_per_sec', [])
        temp_file.write(f"throughput_values={repr(throughput_values)}\n")

        # Process consumer_groups
        consumer_groups = spec.get('consumer_groups', [])
        consumer_nums = [cg['num_groups'] for cg in consumer_groups]
        temp_file.write(f"consumer_group_configs={repr(consumer_nums)}\n")

        # Process num_producers
        num_producers_list = spec.get('num_producers', [6])  # Default to 6 if not specified
        temp_file.write(f"num_producers_list={repr(num_producers_list)}\n")

        # Process client_props
        client_props_list = spec.get('client_props', [{'producer': 'acks=all linger.ms=5 batch.size=262114 buffer.memory=2147483648'}])
        temp_file.write(f"client_props_list={repr(client_props_list)}\n")

        # Process num_partitions
        num_partitions_list = spec.get('num_partitions', [36])  # Default to 36 if not specified
        temp_file.write(f"num_partitions_list={repr(num_partitions_list)}\n")

        # Process replication_factor
        replication_factor_list = spec.get('replication_factor', [3])  # Default to 3 if not specified
        temp_file.write(f"replication_factor_list={repr(replication_factor_list)}\n")

        # Process duration_sec
        duration_sec_list = spec.get('duration_sec', [300])  # Default to 300 if not specified
        temp_file.write(f"duration_sec_list={repr(duration_sec_list)}\n")

        # Process record_size_byte
        record_size_byte_list = spec.get('record_size_byte', [1024])  # Default to 1024 if not specified
        temp_file.write(f"record_size_byte_list={repr(record_size_byte_list)}\n")

except Exception as e:
    print(f"Error parsing test-spec.json: {e}", file=sys.stderr)
    sys.exit(1)
EOF

    # Source the parameters extracted from JSON
    if [ -f "/tmp/kafka_test_params.sh" ]; then
        source "/tmp/kafka_test_params.sh"
    else
        echo "❌ Failed to parse test-spec.json"
        exit 1
    fi

    # Create results directory
    mkdir -p "$RESULTS_DIR"

    # Calculate total number of tests for progress indication
    local total_tests=$((${#throughput_values[@]} * ${#consumer_group_configs[@]} * ${#num_producers_list[@]} * ${#client_props_list[@]}))
    echo "📋 Total test combinations to run: $total_tests"

    local test_counter=1

    # Run all test combinations - now including all parameter variations
    for throughput in "${throughput_values[@]}"; do
        for consumer_groups in "${consumer_group_configs[@]}"; do
            for num_producers in "${num_producers_list[@]}"; do
                for client_props_idx in "${!client_props_list[@]}"; do
                    # Get the specific client properties for this test
                    local producer_props_str=$(python3 -c "import json; f=open('$CONFIG_DIR/test-spec.json'); config=json.load(f); f.close(); print(config['test_specification']['parameters']['client_props'][$client_props_idx]['producer'])")
                    local consumer_props_str=$(python3 -c "import json; f=open('$CONFIG_DIR/test-spec.json'); config=json.load(f); f.close(); print(config['test_specification']['parameters']['client_props'][$client_props_idx].get('consumer', ''))")
                    
                    # Write current client props to temp file
                    echo "CLIENT_PRODUCER_PROPS=\"$producer_props_str\"" > /tmp/current_client_props.sh
                    echo "CLIENT_CONSUMER_PROPS=\"$consumer_props_str\"" >> /tmp/current_client_props.sh
                    
                    # Extract buffer.memory from producer_props if present
                    local buffer_memory=$(echo "$producer_props_str" | grep -o 'buffer.memory=[0-9]*' | cut -d'=' -f2)
                    if [ -z "$buffer_memory" ]; then
                        buffer_memory="2147483648"  # Default to 2GB if not specified
                    fi
                    echo "CLIENT_BUFFER_MEMORY=\"$buffer_memory\"" >> /tmp/current_client_props.sh

                    # Get other parameters for this specific test combination
                    local num_partitions_val="${num_partitions_list[0]}"  # Use first value or implement cycling if needed
                    local replication_factor_val="${replication_factor_list[0]}"
                    local duration_sec_val="${duration_sec_list[0]}"
                    local record_size_val="${record_size_byte_list[0]}"

                    # Run the test with specific parameters
                    echo "🧪 [$test_counter/$total_tests] Starting test: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}, num_producers=${num_producers}, client_props_idx=${client_props_idx}"
                    run_test_with_params $throughput $consumer_groups $test_counter $num_producers $num_partitions_val $replication_factor_val $duration_sec_val $record_size_val

                    ((test_counter++))
                    sleep 10  # Brief pause between tests
                done
            done
        done
    done
}

# Main execution - run all tests based on configuration
run_all_tests_from_config

echo "🎉 All tests completed!"
echo "📊 Results saved in: $RESULTS_DIR"
echo "Next steps:"
echo "1. Process results with: python $SCRIPT_DIR/process-results-binary.py"
echo "2. Generate charts with: python $SCRIPT_DIR/generate-charts.py"