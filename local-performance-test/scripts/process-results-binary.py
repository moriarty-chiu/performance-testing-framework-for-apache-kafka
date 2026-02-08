#!/usr/bin/env python3

"""
Process Kafka performance test results from binary execution
Enhanced version that handles binary tool output format
"""

import json
import os
import re
import glob
from collections import defaultdict
import argparse

def parse_producer_output_binary(log_content):
    """Parse producer performance test output from Kafka binary tools"""
    lines = log_content.strip().split('\n')
    metrics = {}
    
    # Look for the summary line in kafka-producer-perf-test output
    # Example output format:
    # 100000 records sent, 20000.0 records/sec (20.00 MB/sec), 5.0 ms avg latency, 10.0 ms max latency, 2ms 50th, 15ms 95th, 20ms 99th, 25ms 99.9th
    for line in lines:
        if 'records sent' in line and 'records/sec' in line and 'MB/sec' in line:
            # Parse the standard kafka-producer-perf-test output format
            match = re.search(r'(\d+) records sent, ([\d.]+) records/sec \(([\d.]+) MB/sec\), ([\d.]+) ms avg latency, ([\d.]+) ms max latency.*?(\d+)ms 50th.*?(\d+)ms 99th', line)
            if match:
                metrics = {
                    'records_sent': int(match.group(1)),
                    'records_per_sec': float(match.group(2)),
                    'mb_per_sec': float(match.group(3)),
                    'avg_latency_ms': float(match.group(4)),
                    'max_latency_ms': float(match.group(5)),
                    'latency_ms_p50': int(match.group(6)),
                    'latency_ms_p99': int(match.group(7))
                }
                break
    
    return metrics

def parse_consumer_output_binary(log_content):
    """Parse consumer performance test output from Kafka binary tools"""
    lines = log_content.strip().split('\n')
    metrics = {}
    
    # Look for consumer metrics in the output
    # Example output format:
    # 50000 records/sec (50.00 MB/sec)
    for line in lines:
        if 'records/sec' in line and 'MB/sec' in line:
            match = re.search(r'(\d+) records/sec \(([\d.]+) MB/sec\)', line)
            if match:
                metrics = {
                    'records_per_sec': int(match.group(1)),
                    'mb_per_sec': float(match.group(2))
                }
                break
    
    # Also look for detailed metrics if available
    # Example: start.ms=123456789 end.ms=123456799 fetch.size=1048576 data.consumed.in.ms=1000
    for line in lines:
        if 'start.ms=' in line and 'end.ms=' in line:
            # Parse timing information
            start_match = re.search(r'start\.ms=(\d+)', line)
            end_match = re.search(r'end\.ms=(\d+)', line)
            if start_match and end_match:
                start_time = int(start_match.group(1))
                end_time = int(end_match.group(1))
                duration_ms = end_time - start_time
                metrics['duration_ms'] = duration_ms
                break
    
    return metrics

def process_test_results_binary(results_dir):
    """Process all test results from binary execution"""
    test_results = []
    
    # Find all test log files
    producer_files = glob.glob(os.path.join(results_dir, "test-*-producer-*.log"))
    consumer_files = glob.glob(os.path.join(results_dir, "test-*-consumer-*-*.log"))
    
    # Group by test ID
    test_groups = defaultdict(lambda: {'producers': [], 'consumers': []})
    
    # Process producer files
    for log_file in producer_files:
        match = re.search(r'test-(\d+)-producer-(\d+)\.log', os.path.basename(log_file))
        if match:
            test_id = int(match.group(1))
            producer_id = int(match.group(2))
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                metrics = parse_producer_output_binary(content)
                if metrics:
                    test_groups[test_id]['producers'].append(metrics)
            except Exception as e:
                print(f"Error processing producer {log_file}: {e}")
    
    # Process consumer files
    for log_file in consumer_files:
        match = re.search(r'test-(\d+)-consumer-(\d+)-(\d+)\.log', os.path.basename(log_file))
        if match:
            test_id = int(match.group(1))
            consumer_group = int(match.group(2))
            consumer_id = int(match.group(3))
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                metrics = parse_consumer_output_binary(content)
                if metrics:
                    test_groups[test_id]['consumers'].append(metrics)
            except Exception as e:
                print(f"Error processing consumer {log_file}: {e}")
    
    # Process each test group
    for test_id, data in test_groups.items():
        producer_metrics = data['producers']
        consumer_metrics = data['consumers']
        
        if producer_metrics:
            # Aggregate producer metrics
            aggregated = {
                'test_id': test_id,
                'num_producers': len(producer_metrics),
                'num_consumers': len(consumer_metrics),
                'avg_mb_per_sec': sum(m['mb_per_sec'] for m in producer_metrics) / len(producer_metrics),
                'total_mb_per_sec': sum(m['mb_per_sec'] for m in producer_metrics),
                'avg_latency_ms_p50': sum(m['latency_ms_p50'] for m in producer_metrics) / len(producer_metrics),
                'avg_latency_ms_p99': sum(m['latency_ms_p99'] for m in producer_metrics) / len(producer_metrics),
                'max_latency_ms': max(m['max_latency_ms'] for m in producer_metrics),
                'total_records_sent': sum(m['records_sent'] for m in producer_metrics)
            }
            
            # Add consumer metrics if available
            if consumer_metrics:
                aggregated['consumer_total_mb_per_sec'] = sum(m.get('mb_per_sec', 0) for m in consumer_metrics)
                aggregated['consumer_avg_mb_per_sec'] = aggregated['consumer_total_mb_per_sec'] / len(consumer_metrics) if consumer_metrics else 0
            
            test_results.append(aggregated)
    
    return test_results

def save_results(results, output_file):
    """Save processed results to JSON file"""
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Process Kafka performance test results (Binary version)')
    parser.add_argument('--results-dir', default='../results', help='Directory containing test results')
    parser.add_argument('--output', default='../results/processed-results.json', help='Output file for processed results')
    
    args = parser.parse_args()
    
    print("Processing Kafka performance test results (Binary mode)...")
    results = process_test_results_binary(args.results_dir)
    
    if results:
        save_results(results, args.output)
        print(f"Processed {len(results)} test results")
        
        # Print summary
        print("\n📊 Summary:")
        for result in results:
            print(f"Test {result['test_id']}: {result['total_mb_per_sec']:.2f} MB/s (producers), "
                  f"{result.get('consumer_total_mb_per_sec', 0):.2f} MB/s (consumers), "
                  f"P50 latency: {result['avg_latency_ms_p50']:.1f}ms, "
                  f"P99 latency: {result['avg_latency_ms_p99']:.1f}ms")
    else:
        print("No results found to process")

if __name__ == "__main__":
    main()