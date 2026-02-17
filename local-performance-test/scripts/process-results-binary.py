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
            # More flexible regex to handle various output formats
            # Handle both decimal and integer values in various positions
            match = re.search(r'(\d+) records sent,\s*([0-9.]+) records/sec \(([0-9.]+) MB/sec\),\s*([0-9.]+) ms avg latency,\s*([0-9.]+) ms max latency', line)
            if match:
                # Extract the basic metrics first
                metrics = {
                    'records_sent': int(match.group(1)),
                    'records_per_sec': float(match.group(2)),
                    'mb_per_sec': float(match.group(3)),
                    'avg_latency_ms': float(match.group(4)),
                    'max_latency_ms': float(match.group(5))
                }
                
                # Look for percentile latencies in the rest of the line
                # Match patterns like "2ms 50th, 15ms 95th, 20ms 99th, 25ms 99.9th" or "2.50 ms 50th"
                p50_match = re.search(r'(\d+(?:\.\d+)?)\s*ms\s+50th', line)
                if p50_match:
                    metrics['latency_ms_p50'] = float(p50_match.group(1))

                p95_match = re.search(r'(\d+(?:\.\d+)?)\s*ms\s+95th', line)
                if p95_match:
                    metrics['latency_ms_p95'] = float(p95_match.group(1))

                p99_match = re.search(r'(\d+(?:\.\d+)?)\s*ms\s+99th', line)
                if p99_match:
                    metrics['latency_ms_p99'] = float(p99_match.group(1))

                p999_match = re.search(r'(\d+(?:\.\d+)?)\s*ms\s+99.9th', line)
                if p999_match:
                    metrics['latency_ms_p999'] = float(p999_match.group(1))
                
                break
            else:
                # Try alternative format that might appear in different Kafka versions
                match = re.search(r'(\d+) records sent,\s*([0-9.]+) records/sec \(([0-9.]+) MB/sec\)', line)
                if match:
                    metrics = {
                        'records_sent': int(match.group(1)),
                        'records_per_sec': float(match.group(2)),
                        'mb_per_sec': float(match.group(3))
                    }

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
            # Calculate aggregate metrics with error handling
            records_sent_sum = sum(m.get('records_sent', 0) for m in producer_metrics)
            records_per_sec_avg = sum(m.get('records_per_sec', 0) for m in producer_metrics) / len(producer_metrics)
            mb_per_sec_sum = sum(m.get('mb_per_sec', 0) for m in producer_metrics)
            mb_per_sec_avg = mb_per_sec_sum / len(producer_metrics)
            
            # Calculate percentiles with error checking
            p50_values = [m.get('latency_ms_p50', 0) for m in producer_metrics if 'latency_ms_p50' in m]
            p95_values = [m.get('latency_ms_p95', 0) for m in producer_metrics if 'latency_ms_p95' in m]
            p99_values = [m.get('latency_ms_p99', 0) for m in producer_metrics if 'latency_ms_p99' in m]
            p999_values = [m.get('latency_ms_p999', 0) for m in producer_metrics if 'latency_ms_p999' in m]
            
            avg_latency_ms_p50 = sum(p50_values) / len(p50_values) if p50_values else 0
            avg_latency_ms_p95 = sum(p95_values) / len(p95_values) if p95_values else 0
            avg_latency_ms_p99 = sum(p99_values) / len(p99_values) if p99_values else 0
            avg_latency_ms_p999 = sum(p999_values) / len(p999_values) if p999_values else 0
            
            max_latency_ms = max(m.get('max_latency_ms', 0) for m in producer_metrics)

            # Create aggregated result
            aggregated = {
                'test_id': test_id,
                'num_producers': len(producer_metrics),
                'num_consumers': len(consumer_metrics),
                'total_records_sent': records_sent_sum,
                'avg_records_per_sec': records_per_sec_avg,
                'total_mb_per_sec': mb_per_sec_sum,
                'avg_mb_per_sec': mb_per_sec_avg,
                'avg_latency_ms_p50': avg_latency_ms_p50,
                'avg_latency_ms_p95': avg_latency_ms_p95,
                'avg_latency_ms_p99': avg_latency_ms_p99,
                'avg_latency_ms_p999': avg_latency_ms_p999,
                'max_latency_ms': max_latency_ms,
                'producer_success_rate': len(producer_metrics) / len(glob.glob(os.path.join(results_dir, f"test-{test_id}-producer-*.log"))) if producer_files else 1.0
            }

            # Add consumer metrics if available
            if consumer_metrics:
                consumer_mb_per_sec_sum = sum(m.get('mb_per_sec', 0) for m in consumer_metrics)
                aggregated['consumer_total_mb_per_sec'] = consumer_mb_per_sec_sum
                aggregated['consumer_avg_mb_per_sec'] = consumer_mb_per_sec_sum / len(consumer_metrics) if consumer_metrics else 0
                aggregated['consumer_success_rate'] = len(consumer_metrics) / len(glob.glob(os.path.join(results_dir, f"test-{test_id}-consumer-*-*log"))) if consumer_files else 1.0

            test_results.append(aggregated)

    print(f"📊 Processed {len(test_results)} test results")
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
        print("\n💡 Possible reasons:")
        print("- The run-tests-binary.sh script hasn't been executed yet")
        print("- The tests were run with --use-mock-data flag, but logs weren't generated")
        print("- The Kafka cluster wasn't available during test execution")
        print("- Log files were generated in a different directory")
        
        print(f"\n📋 Expected log file patterns in {args.results_dir}/:")
        print("- Producer logs: test-*-producer-*.log (e.g., test-1-producer-0.log)")
        print("- Consumer logs: test-*-consumer-*-*.log (e.g., test-1-consumer-0-0.log)")
        
        print(f"\n🔍 Found files in {args.results_dir}/:")
        import os
        for file in os.listdir(args.results_dir):
            print(f"- {file}")
            
        print("\n🔧 Suggestions:")
        print("- Run './scripts/run-tests-binary.sh --use-mock-data' to generate sample logs")
        print("- Or run './scripts/run-tests-binary.sh' with a working Kafka cluster")
        print("- Verify that KAFKA_HOME is set correctly if using real Kafka")

if __name__ == "__main__":
    main()