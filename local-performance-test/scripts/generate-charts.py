#!/usr/bin/env python3

"""
Generate performance charts from test results
Based on the AWS framework's visualization logic
"""

import json
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os

def load_results(results_file):
    """Load processed results from JSON file"""
    with open(results_file, 'r') as f:
        return json.load(f)

def create_throughput_vs_latency_chart(results, output_dir):
    """Create throughput vs latency chart"""
    # Group results by consumer group count
    grouped_results = {}
    for result in results:
        # Extract consumer group info from test_id (simplified)
        consumer_groups = 0  # This would need to be parsed from test configuration
        if consumer_groups not in grouped_results:
            grouped_results[consumer_groups] = []
        grouped_results[consumer_groups].append(result)
    
    plt.figure(figsize=(12, 8))
    
    # Plot for each consumer group configuration
    colors = ['blue', 'red', 'green']
    for i, (consumer_groups, group_results) in enumerate(grouped_results.items()):
        if not group_results:
            continue
            
        # Sort by throughput
        sorted_results = sorted(group_results, key=lambda x: x['total_mb_per_sec'])
        throughputs = [r['total_mb_per_sec'] for r in sorted_results]
        p50_latencies = [r['avg_latency_ms_p50'] for r in sorted_results]
        p99_latencies = [r['avg_latency_ms_p99'] for r in sorted_results]
        
        plt.plot(throughputs, p50_latencies, 
                marker='o', linestyle='-', color=colors[i], 
                label=f'P50 Latency ({consumer_groups} consumer groups)')
        plt.plot(throughputs, p99_latencies, 
                marker='s', linestyle='--', color=colors[i], 
                label=f'P99 Latency ({consumer_groups} consumer groups)')
    
    plt.xlabel('Throughput (MB/sec)')
    plt.ylabel('Latency (ms)')
    plt.title('Kafka Performance: Throughput vs Latency')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_file = os.path.join(output_dir, 'throughput_vs_latency.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Chart saved to {output_file}")

def create_throughput_efficiency_chart(results, output_dir):
    """Create throughput efficiency chart"""
    plt.figure(figsize=(10, 6))
    
    # Calculate efficiency (this would need actual requested vs sent throughput)
    efficiencies = []
    throughputs = []
    
    for result in results:
        # Simplified efficiency calculation
        requested_throughput = result['test_id'] * 8  # Dummy calculation
        actual_throughput = result['total_mb_per_sec']
        efficiency = actual_throughput / requested_throughput if requested_throughput > 0 else 0
        
        efficiencies.append(efficiency)
        throughputs.append(actual_throughput)
    
    plt.scatter(throughputs, efficiencies, alpha=0.7, s=50)
    plt.xlabel('Actual Throughput (MB/sec)')
    plt.ylabel('Efficiency Ratio')
    plt.title('Throughput Efficiency')
    plt.grid(True, alpha=0.3)
    plt.axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='100% Efficiency')
    plt.legend()
    plt.tight_layout()
    
    output_file = os.path.join(output_dir, 'throughput_efficiency.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Chart saved to {output_file}")

def create_summary_table(results, output_dir):
    """Create a summary table of results"""
    # Create summary statistics
    throughputs = [r['total_mb_per_sec'] for r in results]
    p50_latencies = [r['avg_latency_ms_p50'] for r in results]
    p99_latencies = [r['avg_latency_ms_p99'] for r in results]
    
    summary = {
        'min_throughput': min(throughputs),
        'max_throughput': max(throughputs),
        'avg_throughput': np.mean(throughputs),
        'min_p50_latency': min(p50_latencies),
        'max_p50_latency': max(p50_latencies),
        'avg_p50_latency': np.mean(p50_latencies),
        'min_p99_latency': min(p99_latencies),
        'max_p99_latency': max(p99_latencies),
        'avg_p99_latency': np.mean(p99_latencies),
        'total_tests': len(results)
    }
    
    # Save summary to JSON
    summary_file = os.path.join(output_dir, 'summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary saved to {summary_file}")
    print("\n📊 Performance Summary:")
    print(f"Throughput: {summary['min_throughput']:.1f} - {summary['max_throughput']:.1f} MB/sec")
    print(f"P50 Latency: {summary['min_p50_latency']:.1f} - {summary['max_p50_latency']:.1f} ms")
    print(f"P99 Latency: {summary['min_p99_latency']:.1f} - {summary['max_p99_latency']:.1f} ms")
    print(f"Average tests: {summary['total_tests']}")

def main():
    parser = argparse.ArgumentParser(description='Generate performance charts from test results')
    parser.add_argument('--results-file', default='../results/processed-results.json', 
                       help='Processed results JSON file')
    parser.add_argument('--output-dir', default='../results/charts', 
                       help='Directory for output charts')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    print("Generating performance charts...")
    
    try:
        results = load_results(args.results_file)
        if not results:
            print("No results found to process")
            return
            
        create_throughput_vs_latency_chart(results, args.output_dir)
        create_throughput_efficiency_chart(results, args.output_dir)
        create_summary_table(results, args.output_dir)
        
        print(f"\n✅ All charts generated in {args.output_dir}")
        
    except FileNotFoundError:
        print(f"Error: Results file not found: {args.results_file}")
    except Exception as e:
        print(f"Error generating charts: {e}")

if __name__ == "__main__":
    main()