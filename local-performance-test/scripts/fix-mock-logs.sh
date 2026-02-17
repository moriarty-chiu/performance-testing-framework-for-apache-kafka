#!/bin/bash

# Fix script to ensure mock data generation creates proper log files
# This script should be run after run-tests-binary.sh --use-mock-data

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_ROOT/config"
RESULTS_DIR="$PROJECT_ROOT/results"

echo "Ensuring proper mock log files are created..."

# Parse test specification from JSON using Python for proper parsing
python3 << EOF
import json
import os

# Load the test specification
with open('$CONFIG_DIR/test-spec.json', 'r') as f:
    config = json.load(f)

spec = config['test_specification']['parameters']

# Extract parameters
throughput_values = spec.get('cluster_throughput_mb_per_sec', [])
consumer_groups_list = spec.get('consumer_groups', [])
num_producers_list = spec.get('num_producers', [6])
# For simplicity, we'll use the first values of other parameters
num_partitions_list = spec.get('num_partitions', [36])
replication_factor_list = spec.get('replication_factor', [3])
duration_sec_list = spec.get('duration_sec', [300])
record_size_byte_list = spec.get('record_size_byte', [1024])

test_counter = 1

# Create all combinations of tests
for throughput in throughput_values:
    for consumer_group in consumer_groups_list:
        consumer_groups = consumer_group['num_groups']
        for num_producers in num_producers_list:
            print(f"Creating mock logs for test {test_counter}: throughput={throughput}, consumer_groups={consumer_groups}, num_producers={num_producers}")
            
            # Create producer log files
            for p_id in range(num_producers):
                producer_log = os.path.join('$RESULTS_DIR', f"test-{test_counter}-producer-{p_id}.log")
                with open(producer_log, 'w') as f:
                    # Generate realistic mock producer data based on throughput
                    avg_throughput = throughput / num_producers  # distribute throughput among producers
                    # Add variation to latency based on throughput level (higher throughput = higher latency)
                    base_latency = 15.0 + (throughput * 0.1)  # Base latency increases with throughput
                    p50_latency = base_latency - 8
                    p95_latency = base_latency + 5
                    p99_latency = base_latency + 15
                    p999_latency = base_latency + 25
                    max_latency = base_latency + 35
                    
                    f.write(f"100000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), {base_latency:.1f} ms avg latency, {max_latency:.1f} ms max latency, {p50_latency:.2f} ms 50th, {p95_latency:.2f} ms 95th, {p99_latency:.2f} ms 99th, {p999_latency:.2f} ms 99.9th\n")
                    f.write(f"200000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), {base_latency-1:.1f} ms avg latency, {max_latency-2:.1f} ms max latency, {p50_latency-0.5:.2f} ms 50th, {p95_latency-0.5:.2f} ms 95th, {p99_latency-0.5:.2f} ms 99th, {p999_latency-0.5:.2f} ms 99.9th\n")
                    f.write(f"300000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), {base_latency-1.5:.1f} ms avg latency, {max_latency-3:.1f} ms max latency, {p50_latency-1.0:.2f} ms 50th, {p95_latency-1.0:.2f} ms 95th, {p99_latency-1.0:.2f} ms 99th, {p999_latency-1.0:.2f} ms 99.9th\n")
                    f.write(f"400000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), {base_latency-2.0:.1f} ms avg latency, {max_latency-4:.1f} ms max latency, {p50_latency-1.5:.2f} ms 50th, {p95_latency-1.5:.2f} ms 95th, {p99_latency-1.5:.2f} ms 99th, {p999_latency-1.5:.2f} ms 99.9th\n")
                    f.write(f"500000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), {base_latency-2.5:.1f} ms avg latency, {max_latency-5:.1f} ms max latency, {p50_latency-2.0:.2f} ms 50th, {p95_latency-2.0:.2f} ms 95th, {p99_latency-2.0:.2f} ms 99th, {p999_latency-2.0:.2f} ms 99.9th\n")
                    f.write(f"records sent, 60 second, {avg_throughput*1000:.2f}/sec, {avg_throughput:.2f} MB/sec, {avg_throughput:.2f} MB/sec, {base_latency-3.0:.2f} ms avg latency, {max_latency-6.0:.2f} ms max latency, {p50_latency-2.5:.2f} ms 50th, {p95_latency-2.5:.2f} ms 95th, {p99_latency-2.5:.2f} ms 99th, {p999_latency-2.5:.2f} ms 99.9th\n")
            
            # Create consumer log files if there are consumer groups
            if consumer_groups > 0:
                # Each consumer group has 6 consumers (based on the original script logic)
                for cg_id in range(consumer_groups):
                    for c_id in range(6):  # 6 consumers per group (based on original script)
                        consumer_log = os.path.join('$RESULTS_DIR', f"test-{test_counter}-consumer-{cg_id}-{c_id}.log")
                        with open(consumer_log, 'w') as f:
                            f.write("start.time, end.time, data.consumed.in.MB, MB.sec, records.per.sec, avg.partition.latency.ms, max.partition.latency.ms\n")
                            f.write(f"2023-01-01 10:00:00:000, 2023-01-01 10:01:00:000, {throughput * 0.95:.3f}, {throughput * 0.95:.3f}, {throughput * 1000 * 0.95:.1f}, 17.20, 73.00\n")
                            f.write(f"Consumed {int(throughput * 1000 * 300 * 0.95)} records\n")
            
            test_counter += 1

print(f"Created mock log files for {test_counter-1} test combinations")
EOF

echo "Mock log files have been created successfully!"