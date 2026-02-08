#!/usr/bin/env python3

"""
Process Kafka performance test results
Based on the AWS framework's result processing logic
"""

import json
import os
import re
import glob
from collections import defaultdict
import argparse

def parse_producer_output(log_content):
    """Parse producer performance test output"""
    lines = log_content.strip().split('\n')
    metrics = {}
    
    # Look for the JSON summary line
    for line in reversed(lines):
        if line.startswith('{') and '"type": "producer"' in line:
            try:
                data = json.loads(line)
                # Extract metrics from test_summary
                summary = data.get('test_summary', '')
                # Parse the standard kafka-producer-perf-test output format
                # Example: 500000 records sent, 100.0 records/sec (100.0 MB/sec), 5.0 ms avg latency, 10.0 ms max latency, 2ms 50th, 15ms 95th, 20ms 99th, 25ms 99.9th
                match = re.search(r'(\d+) records sent, ([\d.]+) records/sec \(([\d.]+) MB/sec\), ([\d.]+) ms avg latency, ([\d.]+) ms max latency.*?(\d+)ms 50th.*?(\d+)ms 99th', summary)
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
            except json.JSONDecodeError:
                continue
    
    return metrics

def parse_consumer_output(log_content):
    """Parse consumer performance test output"""
    lines = log_content.strip().split('\n')
    metrics = {}
    
    # Look for the JSON summary line
    for line in reversed(lines):
        if line.startswith('{') and '"type": "consumer"' in line:
            try:
                data = json.loads(line)
                # Extract consumer metrics from the output
                # Parse consumer performance metrics
                for line in lines:
                    if 'records/sec' in line and 'MB/sec' in line:
                        match = re.search(r'(\d+) records/sec \(([\d.]+) MB/sec\)', line)
                        if match:
                            metrics = {
                                'records_per_sec': int(match.group(1)),
                                'mb_per_sec': float(match.group(2))
                            }
                        break
            except json.JSONDecodeError:
                continue
    
    return metrics

def process_test_results(results_dir):
    """Process all test results and generate aggregated statistics"""
    test_results = []
    
    # Find all test log files
    log_files = glob.glob(os.path.join(results_dir, "test-*-job-*.log"))
    
    # Group by test ID
    test_groups = defaultdict(list)
    for log_file in log_files:
        # Extract test ID from filename
        match = re.search(r'test-(\d+)-job-(\d+)\.log', os.path.basename(log_file))
        if match:
            test_id = int(match.group(1))
            job_id = int(match.group(2))
            test_groups[test_id].append((job_id, log_file))
    
    # Process each test group
    for test_id, job_files in test_groups.items():
        producer_metrics = []
        consumer_metrics = []
        
        # Parse each job file
        for job_id, log_file in job_files:
            try:
                with open(log_file, 'r') as f:
                    content = f.read()
                
                if '"type": "producer"' in content:
                    metrics = parse_producer_output(content)
                    if metrics:
                        producer_metrics.append(metrics)
                elif '"type": "consumer"' in content:
                    metrics = parse_consumer_output(content)
                    if metrics:
                        consumer_metrics.append(metrics)
            except Exception as e:
                print(f"Error processing {log_file}: {e}")
        
        # Aggregate producer metrics
        if producer_metrics:
            aggregated = {
                'test_id': test_id,
                'num_producers': len(producer_metrics),
                'avg_mb_per_sec': sum(m['mb_per_sec'] for m in producer_metrics) / len(producer_metrics),
                'total_mb_per_sec': sum(m['mb_per_sec'] for m in producer_metrics),
                'avg_latency_ms_p50': sum(m['latency_ms_p50'] for m in producer_metrics) / len(producer_metrics),
                'avg_latency_ms_p99': sum(m['latency_ms_p99'] for m in producer_metrics) / len(producer_metrics),
                'max_latency_ms': max(m['max_latency_ms'] for m in producer_metrics)
            }
            test_results.append(aggregated)
    
    return test_results

def save_results(results, output_file):
    """Save processed results to JSON file"""
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Process Kafka performance test results')
    parser.add_argument('--results-dir', default='../results', help='Directory containing test results')
    parser.add_argument('--output', default='../results/processed-results.json', help='Output file for processed results')
    
    args = parser.parse_args()
    
    print("Processing Kafka performance test results...")
    results = process_test_results(args.results_dir)
    
    if results:
        save_results(results, args.output)
        print(f"Processed {len(results)} test results")
        
        # Print summary
        print("\n📊 Summary:")
        for result in results:
            print(f"Test {result['test_id']}: {result['total_mb_per_sec']:.2f} MB/s, "
                  f"P50 latency: {result['avg_latency_ms_p50']:.1f}ms, "
                  f"P99 latency: {result['avg_latency_ms_p99']:.1f}ms")
    else:
        print("No results found to process")

if __name__ == "__main__":
    main()