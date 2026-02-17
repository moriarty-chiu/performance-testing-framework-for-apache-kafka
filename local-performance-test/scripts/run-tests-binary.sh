#!/bin/bash

# Kafka Performance Test Runner - Binary Version
# Uses locally installed Kafka binaries instead of Docker

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

# Skip environment validation if requested
if [ "$SKIP_ENV_CHECK" = false ]; then
    # Check if Kafka is installed
    if [ ! -d "$KAFKA_HOME" ] || [ ! -d "$KAFKA_BIN" ]; then
        echo "[ERROR] Kafka not found at $KAFKA_HOME"
        echo "Please set KAFKA_HOME environment variable to your Kafka installation directory"
        echo "Or modify the KAFKA_HOME variable in this script"
        exit 1
    fi

    # Check if required Kafka tools exist
    required_tools=("kafka-topics.sh" "kafka-producer-perf-test.sh" "kafka-consumer-perf-test.sh")
    for tool in "${required_tools[@]}"; do
        if [ ! -f "$KAFKA_BIN/$tool" ]; then
            echo "[ERROR] Required Kafka tool not found: $KAFKA_BIN/$tool"
            exit 1
        fi
    done
else
    echo "[INFO] Skipping environment validation as requested"
fi

# Load configuration
if [ "$USE_MOCK_DATA" = false ]; then
    # Extract bootstrap.servers from kafka.properties
    if [ -f "$CONFIG_DIR/kafka.properties" ]; then
        bootstrap.servers=$(grep "^bootstrap.servers=" "$CONFIG_DIR/kafka.properties" | cut -d'=' -f2-)
    fi
else
    # Still load the bootstrap server from kafka.properties for mock data but with a mock server
    if [ -f "$CONFIG_DIR/kafka.properties" ]; then
        # Extract bootstrap.servers from kafka.properties for reference
        grep "^bootstrap.servers=" "$CONFIG_DIR/kafka.properties" | cut -d'=' -f2- > /tmp/bootstrap_server_ref 2>/dev/null
    fi
    # Override the bootstrap servers for mock data
    echo "[INFO] Using mock configuration data"
    # Define a variable to hold the bootstrap servers value
    MOCK_BOOTSTRAP_SERVERS="mock-kafka-server:9092"
fi

# Function to check system resources
check_system_resources() {
    if [ "$SKIP_ENV_CHECK" = true ]; then
        echo "[INFO] Skipping system resource check as environment validation is disabled"
        return 0
    fi
    
    echo "Checking system resources..."

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
        echo "[WARNING] Unable to determine system memory, continuing without validation"
        return 0
    fi

    echo "Available memory: ${available_memory_mb}MB, Total memory: ${total_memory_mb}MB"

    # Warn if available memory is low
    if [ $available_memory_mb -lt 2048 ]; then
        echo "[WARNING] Available memory is low (${available_memory_mb}MB). Tests may fail due to insufficient memory."
        echo "Consider closing other applications or using smaller test configurations."
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

echo "Starting Kafka Performance Tests (Binary Mode)"
if [ "$USE_MOCK_DATA" = false ]; then
    echo "Kafka Home: $KAFKA_HOME"
    echo "Kafka Bootstrap Servers: $bootstrap.servers"
else
    echo "Kafka Home: [MOCK DATA MODE]"
    echo "Kafka Bootstrap Servers: $MOCK_BOOTSTRAP_SERVERS"
fi
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

    echo "Running test: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}, num_producers=${num_producers}, partitions=${num_partitions}, replication=${replication_factor}"

    # Skip resource validation if using mock data or skip env check
    if [ "$USE_MOCK_DATA" = false ] && [ "$SKIP_ENV_CHECK" = false ]; then
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
            echo "[WARNING] Unable to determine available memory, skipping validation"
            local available_memory_mb=8192  # Assume 8GB if we can't determine
        fi

        if [ $available_memory_mb -lt $required_memory_mb ]; then
            echo "[WARNING] Estimated required memory (${required_memory_mb}MB) exceeds available memory (${available_memory_mb}MB)"
            echo "[WARNING] Consider reducing num_producers or adjusting buffer.memory in client_props"
        fi
    fi

    local topic_name="perf-test-${test_id}-throughput-${throughput}-consumers-${consumer_groups}"
    local num_jobs=$(($num_producers + consumer_groups * 6))  # num_producers + (groups * 6 consumers)
    local records_per_sec=$((throughput * 1024 * 1024 / $record_size))  # throughput in records/sec

    # Create topic using Kafka binary tools (skip if using mock data)
    if [ "$USE_MOCK_DATA" = false ]; then
        # Determine the bootstrap servers to use for topic creation
        local topic_bs_servers
        if [ "$USE_MOCK_DATA" = true ]; then
            topic_bs_servers="$MOCK_BOOTSTRAP_SERVERS"
        else
            topic_bs_servers="$bootstrap.servers"
        fi
        
        echo "Creating topic: $topic_name with $num_partitions partitions and replication factor $replication_factor"
        if ! "$KAFKA_BIN/kafka-topics.sh" \
            --bootstrap-server "$topic_bs_servers" \
            --create \
            --topic "$topic_name" \
            --partitions $num_partitions \
            --replication-factor $replication_factor \
            --config retention.ms=60000; then
            echo "[ERROR] Failed to create topic $topic_name"
            return 1
        fi

        # Wait for topic creation
        sleep 5
    else
        echo "[MOCK] Creating topic: $topic_name with $num_partitions partitions and replication factor $replication_factor"
        sleep 1  # Simulate topic creation delay
    fi

    # Array to store background process PIDs
    declare -a pids

    # Extract client properties from configuration
    # For simplicity, we'll use a default set of properties, but ideally these should come from config
    local producer_props="acks=all linger.ms=5 batch.size=262114"

    # Try to get producer and consumer properties from the configuration if available
    if [ "$USE_MOCK_DATA" = false ]; then
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
    else
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
    else
        # Mock client properties
        echo "CLIENT_PRODUCER_PROPS=\"acks=all linger.ms=5 batch.size=262114\"" > /tmp/current_client_props.sh
        echo "CLIENT_CONSUMER_PROPS=\"\"" >> /tmp/current_client_props.sh
        echo "CLIENT_BUFFER_MEMORY=\"2147483648\"" >> /tmp/current_client_props.sh
    fi

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

        if [ "$USE_MOCK_DATA" = false ]; then
            # Determine the bootstrap servers to use
            local bs_servers
            if [ "$USE_MOCK_DATA" = true ]; then
                bs_servers="$MOCK_BOOTSTRAP_SERVERS"
            else
                bs_servers="$bootstrap.servers"
            fi
            
            # Build producer properties command line
            local prop_args="--producer-props bootstrap.servers=$bs_servers"
            # Add each property from CLIENT_PRODUCER_PROPS
            for prop in $CLIENT_PRODUCER_PROPS; do
                prop_args="$prop_args --producer-props $prop"
            done
            
            "$KAFKA_BIN/kafka-producer-perf-test.sh" \
                --topic "$topic_name" \
                --num-records $((records_per_sec * duration_sec)) \
                --throughput $records_per_sec \
                --record-size $record_size \
                $prop_args \
                > "$producer_log" 2>&1 &
        else
            # Generate realistic mock producer data
            cat > "$producer_log" << EOF
100000 records sent, 19999.6 records/sec (19.53 MB/sec), 21.2 ms avg latency, 110.0 ms max latency.
200000 records sent, 20001.6 records/sec (19.53 MB/sec), 18.1 ms avg latency, 82.0 ms max latency.
300000 records sent, 20000.0 records/sec (19.53 MB/sec), 17.6 ms avg latency, 77.0 ms max latency.
400000 records sent, 20000.8 records/sec (19.53 MB/sec), 17.4 ms avg latency, 75.0 ms max latency.
500000 records sent, 20000.8 records/sec (19.53 MB/sec), 17.3 ms avg latency, 74.0 ms max latency.
records sent, 60 second, 20000.00/sec, 19.53 MB/sec, 19.53 MB/sec, 17.20 ms avg latency, 73.00 ms max latency, 5.00 ms 50th, 35.00 ms 95th, 65.00 ms 99th, 70.00 ms 99.9th
EOF
            sleep 2  # Simulate execution time
        fi

        pids+=($!)
    done

    # Run consumers (remaining jobs)
    local consumer_group_count=0
    for ((i=num_producers; i<num_jobs; i++)); do
        local consumer_log="$RESULTS_DIR/test-${test_id}-consumer-${consumer_group_count}-$((i-num_producers)).log"
        local group_id="perf-test-consumer-group-${test_id}-${consumer_group_count}"

        echo "Starting consumer in group $group_id with properties: $CLIENT_CONSUMER_PROPS"

        if [ "$USE_MOCK_DATA" = false ]; then
            # Build consumer properties command line if CLIENT_CONSUMER_PROPS is not empty
            local consumer_prop_args=""
            if [ -n "$CLIENT_CONSUMER_PROPS" ]; then
                for prop in $CLIENT_CONSUMER_PROPS; do
                    consumer_prop_args="$consumer_prop_args --consumer-props $prop"
                done
            fi
            
            # Determine the bootstrap servers to use for consumers
            local consumer_bs_servers
            if [ "$USE_MOCK_DATA" = true ]; then
                consumer_bs_servers="$MOCK_BOOTSTRAP_SERVERS"
            else
                consumer_bs_servers="$bootstrap.servers"
            fi
            
            "$KAFKA_BIN/kafka-consumer-perf-test.sh" \
                --topic "$topic_name" \
                --broker-list "$consumer_bs_servers" \
                --group "$group_id" \
                --messages $((records_per_sec * duration_sec / num_producers)) \
                --print-metrics \
                --show-detailed-stats \
                --timeout $((duration_sec * 1000 + 10000)) \
                $consumer_prop_args \
                > "$consumer_log" 2>&1 &
        else
            # Generate realistic mock consumer data
            cat > "$consumer_log" << EOF
start.time, end.time, data.consumed.in.MB, MB.sec, records.per.sec, avg.partition.latency.ms, max.partition.latency.ms
2023-01-01 10:00:00:000, 2023-01-01 10:01:00:000, 1171.875, 19.531, 20000.000, 17.20, 73.00
Consumed 1200000 records
EOF
            sleep 2  # Simulate execution time
        fi

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

    echo "Running test: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}, num_producers=${num_producers}, partitions=${num_partitions}, replication=${replication_factor}"

    # Skip resource validation if using mock data or skip env check
    if [ "$USE_MOCK_DATA" = false ] && [ "$SKIP_ENV_CHECK" = false ]; then
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
            echo "[WARNING] Unable to determine available memory, skipping validation"
            local available_memory_mb=8192  # Assume 8GB if we can't determine
        fi

        if [ $available_memory_mb -lt $required_memory_mb ]; then
            echo "[WARNING] Estimated required memory (${required_memory_mb}MB) exceeds available memory (${available_memory_mb}MB)"
            echo "[WARNING] Consider reducing num_producers or adjusting buffer.memory in client_props"
        fi
    fi

    local topic_name="perf-test-${test_id}-throughput-${throughput}-consumers-${consumer_groups}"
    local num_jobs=$(($num_producers + consumer_groups * 6))  # num_producers + (groups * 6 consumers)
    local records_per_sec=$((throughput * 1024 * 1024 / $record_size))  # throughput in records/sec

    # Create topic using Kafka binary tools (skip if using mock data)
    if [ "$USE_MOCK_DATA" = false ]; then
        # Determine the bootstrap servers to use for topic creation
        local topic_bs_servers
        if [ "$USE_MOCK_DATA" = true ]; then
            topic_bs_servers="$MOCK_BOOTSTRAP_SERVERS"
        else
            topic_bs_servers="$bootstrap.servers"
        fi
        
        echo "Creating topic: $topic_name with $num_partitions partitions and replication factor $replication_factor"
        if ! "$KAFKA_BIN/kafka-topics.sh" \
            --bootstrap-server "$topic_bs_servers" \
            --create \
            --topic "$topic_name" \
            --partitions $num_partitions \
            --replication-factor $replication_factor \
            --config retention.ms=60000; then
            echo "[ERROR] Failed to create topic $topic_name"
            return 1
        fi

        # Wait for topic creation
        sleep 5
    else
        echo "[MOCK] Creating topic: $topic_name with $num_partitions partitions and replication factor $replication_factor"
        sleep 1  # Simulate topic creation delay
    fi

    # Array to store background process PIDs
    declare -a pids

    # Run producers (first num_producers jobs)
    for ((i=0; i<num_producers; i++)); do
        local producer_log="$RESULTS_DIR/test-${test_id}-producer-${i}.log"

        echo "Starting producer $i with properties: $CLIENT_PRODUCER_PROPS"

        if [ "$USE_MOCK_DATA" = false ]; then
            # Determine the bootstrap servers to use
            local bs_servers
            if [ "$USE_MOCK_DATA" = true ]; then
                bs_servers="$MOCK_BOOTSTRAP_SERVERS"
            else
                bs_servers="$bootstrap.servers"
            fi
            
            # Build producer properties command line
            local prop_args="--producer-props bootstrap.servers=$bs_servers"
            # Add each property from CLIENT_PRODUCER_PROPS
            for prop in $CLIENT_PRODUCER_PROPS; do
                prop_args="$prop_args --producer-props $prop"
            done
            
            "$KAFKA_BIN/kafka-producer-perf-test.sh" \
                --topic "$topic_name" \
                --num-records $((records_per_sec * duration_sec)) \
                --throughput $records_per_sec \
                --record-size $record_size \
                $prop_args \
                > "$producer_log" 2>&1 &
        else
            # Generate realistic mock producer data
            cat > "$producer_log" << EOF
100000 records sent, 19999.6 records/sec (19.53 MB/sec), 21.2 ms avg latency, 110.0 ms max latency.
200000 records sent, 20001.6 records/sec (19.53 MB/sec), 18.1 ms avg latency, 82.0 ms max latency.
300000 records sent, 20000.0 records/sec (19.53 MB/sec), 17.6 ms avg latency, 77.0 ms max latency.
400000 records sent, 20000.8 records/sec (19.53 MB/sec), 17.4 ms avg latency, 75.0 ms max latency.
500000 records sent, 20000.8 records/sec (19.53 MB/sec), 17.3 ms avg latency, 74.0 ms max latency.
records sent, 60 second, 20000.00/sec, 19.53 MB/sec, 19.53 MB/sec, 17.20 ms avg latency, 73.00 ms max latency, 5.00 ms 50th, 35.00 ms 95th, 65.00 ms 99th, 70.00 ms 99.9th
EOF
            sleep 2  # Simulate execution time
        fi

        pids+=($!)
    done

    # Run consumers (remaining jobs)
    local consumer_group_count=0
    for ((i=num_producers; i<num_jobs; i++)); do
        local consumer_log="$RESULTS_DIR/test-${test_id}-consumer-${consumer_group_count}-$((i-num_producers)).log"
        local group_id="perf-test-consumer-group-${test_id}-${consumer_group_count}"

        echo "Starting consumer in group $group_id with properties: $CLIENT_CONSUMER_PROPS"

        if [ "$USE_MOCK_DATA" = false ]; then
            # Build consumer properties command line if CLIENT_CONSUMER_PROPS is not empty
            local consumer_prop_args=""
            if [ -n "$CLIENT_CONSUMER_PROPS" ]; then
                for prop in $CLIENT_CONSUMER_PROPS; do
                    consumer_prop_args="$consumer_prop_args --consumer-props $prop"
                done
            fi
            
            # Determine the bootstrap servers to use for consumers
            local consumer_bs_servers
            if [ "$USE_MOCK_DATA" = true ]; then
                consumer_bs_servers="$MOCK_BOOTSTRAP_SERVERS"
            else
                consumer_bs_servers="$bootstrap.servers"
            fi
            
            "$KAFKA_BIN/kafka-consumer-perf-test.sh" \
                --topic "$topic_name" \
                --broker-list "$consumer_bs_servers" \
                --group "$group_id" \
                --messages $((records_per_sec * duration_sec / num_producers)) \
                --print-metrics \
                --show-detailed-stats \
                --timeout $((duration_sec * 1000 + 10000)) \
                $consumer_prop_args \
                > "$consumer_log" 2>&1 &
        else
            # Generate realistic mock consumer data
            cat > "$consumer_log" << EOF
start.time, end.time, data.consumed.in.MB, MB.sec, records.per.sec, avg.partition.latency.ms, max.partition.latency.ms
2023-01-01 10:00:00:000, 2023-01-01 10:01:00:000, 1171.875, 19.531, 20000.000, 17.20, 73.00
Consumed 1200000 records
EOF
            sleep 2  # Simulate execution time
        fi

        pids+=($!)

        # Increment group counter every 6 consumers
        if (((i-num_producers+1) % 6 == 0)); then
            ((consumer_group_count++))
        fi
    done

    # Wait for all jobs to complete
    echo "Waiting for all test jobs to complete..."
    if [ "$USE_MOCK_DATA" = false ]; then
        for pid in "${pids[@]}"; do
            wait $pid
        done
    else
        echo "[MOCK] Waiting for test jobs to complete..."
        sleep 3  # Simulate job completion time
    fi

    # Delete topic (skip if using mock data)
    echo "Cleaning up topic: $topic_name"
    if [ "$USE_MOCK_DATA" = false ]; then
        # Determine the bootstrap servers to use for topic deletion
        local delete_bs_servers
        if [ "$USE_MOCK_DATA" = true ]; then
            delete_bs_servers="$MOCK_BOOTSTRAP_SERVERS"
        else
            delete_bs_servers="$bootstrap.servers"
        fi
        
        "$KAFKA_BIN/kafka-topics.sh" \
            --bootstrap-server "$delete_bs_servers" \
            --delete \
            --topic "$topic_name" \
            2>/dev/null || echo "[WARNING] Could not delete topic $topic_name"
    else
        echo "[MOCK] Topic $topic_name would be deleted"
    fi

    echo "Test completed: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}"
}

# Function to run all tests based on configuration
run_all_tests_from_config() {
    # Parse test specification from JSON using Python for proper parsing
    # Always parse the configuration regardless of mock data usage
    echo "Parsing test configuration..."

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
        temp_file.write(f"throughput_values=({ ' '.join(map(str, throughput_values)) })\n")

        # Process consumer_groups
        consumer_groups = spec.get('consumer_groups', [])
        consumer_nums = [cg['num_groups'] for cg in consumer_groups]
        temp_file.write(f"consumer_group_configs=({ ' '.join(map(str, consumer_nums)) })\n")

        # Process num_producers
        num_producers_list = spec.get('num_producers', [6])  # Default to 6 if not specified
        temp_file.write(f"num_producers_list=({ ' '.join(map(str, num_producers_list)) })\n")

        # Process client_props - simplest approach
        client_props_list = spec.get('client_props', [{'producer': 'acks=all linger.ms=5 batch.size=262114 buffer.memory=2147483648'}])
        temp_file.write(f"client_props_count={len(client_props_list)}\n")
        # Store client props as JSON string to avoid shell parsing issues
        import json
        temp_file.write(f"client_props_json='{json.dumps(client_props_list).replace(chr(39), chr(92)+chr(39))}'\n")

        # Process num_partitions
        num_partitions_list = spec.get('num_partitions', [36])  # Default to 36 if not specified
        temp_file.write(f"num_partitions_list=({ ' '.join(map(str, num_partitions_list)) })\n")

        # Process replication_factor
        replication_factor_list = spec.get('replication_factor', [3])  # Default to 3 if not specified
        temp_file.write(f"replication_factor_list=({ ' '.join(map(str, replication_factor_list)) })\n")

        # Process duration_sec
        duration_sec_list = spec.get('duration_sec', [300])  # Default to 300 if not specified
        temp_file.write(f"duration_sec_list=({ ' '.join(map(str, duration_sec_list)) })\n")

        # Process record_size_byte
        record_size_byte_list = spec.get('record_size_byte', [1024])  # Default to 1024 if not specified
        temp_file.write(f"record_size_byte_list=({ ' '.join(map(str, record_size_byte_list)) })\n")

except Exception as e:
    print(f"Error parsing test-spec.json: {e}", file=sys.stderr)
    sys.exit(1)
EOF

    # Source the parameters extracted from JSON
    if [ -f "/tmp/kafka_test_params.sh" ]; then
        source "/tmp/kafka_test_params.sh"
    else
        echo "[ERROR] Failed to parse test-spec.json"
        exit 1
    fi

    # Create results directory
    mkdir -p "$RESULTS_DIR"

    # Calculate total number of tests for progress indication
    # Use client_props_count instead of array length since we changed the storage method
    local total_tests=$((${#throughput_values[@]} * ${#consumer_group_configs[@]} * ${#num_producers_list[@]} * client_props_count))
    echo "Total test combinations to run: $total_tests"

    local test_counter=1

    # Run all test combinations - now including all parameter variations
    for throughput in "${throughput_values[@]}"; do
        for consumer_groups in "${consumer_group_configs[@]}"; do
            for num_producers in "${num_producers_list[@]}"; do
                for client_props_idx in "${!client_props_list[@]}"; do
                    # Get the specific client properties for this test from the JSON string
                    local producer_props_str=$(python3 -c "import json; data=json.loads('''${client_props_json}'''); print(data[$client_props_idx].get('producer', ''))")
                    local consumer_props_str=$(python3 -c "import json; data=json.loads('''${client_props_json}'''); print(data[$client_props_idx].get('consumer', ''))")

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
                    echo "[$test_counter/$total_tests] Starting test: throughput=${throughput}MB/s, consumer_groups=${consumer_groups}, num_producers=${num_producers}, client_props_idx=${client_props_idx}"
                    run_test_with_params $throughput $consumer_groups $test_counter $num_producers $num_partitions_val $replication_factor_val $duration_sec_val $record_size_val

                    ((test_counter++))
                    if [ "$USE_MOCK_DATA" = false ]; then
                        sleep 10  # Brief pause between tests
                    else
                        sleep 1  # Shorter pause for mock tests
                    fi
                done
            done
        done
    done
}

# Function to generate mock results for analysis tools
generate_mock_results() {
    echo "Generating mock results for analysis tools..."
    
    # Create a mock results file that can be processed by process-results-binary.py
    local mock_result_file="$RESULTS_DIR/mock-test-results.json"
    
    cat > "$mock_result_file" << EOF
{
  "test_results": [
    {
      "test_id": "mock-test-1",
      "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "parameters": {
        "throughput_target": 10,
        "consumer_groups": 2,
        "num_producers": 4,
        "num_partitions": 12,
        "replication_factor": 3,
        "duration_sec": 300,
        "record_size_byte": 1024
      },
      "producer_metrics": {
        "avg_records_per_sec": 19950,
        "avg_mb_per_sec": 19.48,
        "avg_latency_ms": 17.5,
        "max_latency_ms": 75
      },
      "consumer_metrics": {
        "avg_records_per_sec": 19900,
        "avg_mb_per_sec": 19.43,
        "avg_latency_ms": 18.2,
        "max_latency_ms": 80
      }
    },
    {
      "test_id": "mock-test-2",
      "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "parameters": {
        "throughput_target": 20,
        "consumer_groups": 4,
        "num_producers": 6,
        "num_partitions": 24,
        "replication_factor": 3,
        "duration_sec": 300,
        "record_size_byte": 1024
      },
      "producer_metrics": {
        "avg_records_per_sec": 19850,
        "avg_mb_per_sec": 19.38,
        "avg_latency_ms": 18.2,
        "max_latency_ms": 82
      },
      "consumer_metrics": {
        "avg_records_per_sec": 19800,
        "avg_mb_per_sec": 19.33,
        "avg_latency_ms": 19.1,
        "max_latency_ms": 85
      }
    }
  ]
}
EOF

    echo "Mock results generated in: $mock_result_file"
}

# Define project root for dependency check
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if Python dependencies are installed
# PYTHON_CMD="python3"
# if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
#     PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
# fi

# if ! $PYTHON_CMD -c "import matplotlib, numpy" &> /dev/null; then
#     echo "Installing Python dependencies..."
#     $PYTHON_CMD -m pip install -r "$PROJECT_ROOT/requirements.txt"
# fi

# Main execution - run all tests based on configuration
run_all_tests_from_config

# If using mock data, also generate mock results for analysis
if [ "$USE_MOCK_DATA" = true ]; then
    generate_mock_results
fi

echo "All tests completed!"
echo "Results saved in: $RESULTS_DIR"
echo "Next steps:"
echo "1. Process results with: python $SCRIPT_DIR/process-results-binary.py"
echo "2. Generate charts with: python $SCRIPT_DIR/generate-charts.py"