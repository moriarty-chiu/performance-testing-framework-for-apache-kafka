#!/usr/bin/env python3

"""
Create mock log files based on test-spec.json to ensure all test combinations are represented
"""

import json
import os

def create_mock_logs():
    # Load the test specification
    with open('config/test-spec.json', 'r') as f:
        config = json.load(f)
    
    spec = config['test_specification']['parameters']
    
    throughput_values = spec.get('cluster_throughput_mb_per_sec', [])
    consumer_groups = spec.get('consumer_groups', [])
    num_producers = spec.get('num_producers', [6])
    
    results_dir = "results"
    
    test_counter = 1
    
    # Create all combinations of tests
    for throughput in throughput_values:
        for consumer_group in consumer_groups:
            consumer_count = consumer_group['num_groups']
            for producer_count in num_producers:
                
                # Create producer log files
                for p_id in range(producer_count):
                    producer_log = os.path.join(results_dir, f"test-{test_counter}-producer-{p_id}.log")
                    with open(producer_log, 'w') as f:
                        # Generate realistic mock producer data based on throughput
                        avg_throughput = throughput / producer_count  # distribute throughput among producers
                        f.write(f"100000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), 21.2 ms avg latency, 110.0 ms max latency, 5.00 ms 50th, 35.00 ms 95th, 65.00 ms 99th, 70.00 ms 99.9th\n")
                        f.write(f"200000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), 18.1 ms avg latency, 82.0 ms max latency, 6.00 ms 50th, 36.00 ms 95th, 66.00 ms 99th, 71.00 ms 99.9th\n")
                        f.write(f"300000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), 17.6 ms avg latency, 77.0 ms max latency, 7.00 ms 50th, 37.00 ms 95th, 67.00 ms 99th, 72.00 ms 99.9th\n")
                        f.write(f"400000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), 17.4 ms avg latency, 75.0 ms max latency, 8.00 ms 50th, 38.00 ms 95th, 68.00 ms 99th, 73.00 ms 99.9th\n")
                        f.write(f"500000 records sent, {avg_throughput*1000:.1f} records/sec ({avg_throughput:.2f} MB/sec), 17.3 ms avg latency, 74.0 ms max latency, 9.00 ms 50th, 39.00 ms 95th, 69.00 ms 99th, 74.00 ms 99.9th\n")
                        f.write(f"records sent, 60 second, {avg_throughput*1000:.2f}/sec, {avg_throughput:.2f} MB/sec, {avg_throughput:.2f} MB/sec, 17.20 ms avg latency, 73.00 ms max latency, 5.00 ms 50th, 35.00 ms 95th, 65.00 ms 99th, 70.00 ms 99.9th\n")
                
                # Create consumer log files if there are consumer groups
                if consumer_count > 0:
                    # Each consumer group has 6 consumers
                    for cg_id in range(consumer_count):
                        for c_id in range(6):  # 6 consumers per group
                            consumer_log = os.path.join(results_dir, f"test-{test_counter}-consumer-{cg_id}-{c_id}.log")
                            with open(consumer_log, 'w') as f:
                                f.write("start.time, end.time, data.consumed.in.MB, MB.sec, records.per.sec, avg.partition.latency.ms, max.partition.latency.ms\n")
                                f.write(f"2023-01-01 10:00:00:000, 2023-01-01 10:01:00:000, {throughput * 0.95:.3f}, {throughput * 0.95:.3f}, {throughput * 1000 * 0.95:.1f}, 17.20, 73.00\n")
                                f.write(f"Consumed {int(throughput * 1000 * 300 * 0.95)} records\n")
                
                test_counter += 1
    
    print(f"Created mock log files for {test_counter-1} test combinations")

if __name__ == "__main__":
    create_mock_logs()