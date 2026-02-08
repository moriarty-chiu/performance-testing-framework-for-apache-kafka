#!/usr/bin/env python3

"""
Generate comparative performance charts across different cluster flavors
"""

import json
import matplotlib.pyplot as plt
import numpy as np
import os
import argparse
import glob
from collections import defaultdict

def load_flavor_results(input_dir):
    """Load results for all flavors"""
    flavor_results = {}
    
    # Find all flavor result files
    result_files = glob.glob(os.path.join(input_dir, "*-results.json"))
    
    for file_path in result_files:
        flavor_name = os.path.basename(file_path).replace('-results.json', '')
        try:
            with open(file_path, 'r') as f:
                flavor_results[flavor_name] = json.load(f)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return flavor_results

def create_throughput_comparison_chart(flavor_results, output_dir):
    """Create throughput comparison across all flavors"""
    plt.figure(figsize=(15, 10))
    
    flavors = ['small', 'medium', 'large', 'xlarge']
    colors = ['lightblue', 'orange', 'green', 'red']
    
    max_throughputs = []
    avg_throughputs = []
    
    for i, flavor in enumerate(flavors):
        if flavor in flavor_results:
            results = flavor_results[flavor]
            throughputs = [r['total_mb_per_sec'] for r in results]
            if throughputs:
                max_throughputs.append(max(throughputs))
                avg_throughputs.append(np.mean(throughputs))
            else:
                max_throughputs.append(0)
                avg_throughputs.append(0)
        else:
            max_throughputs.append(0)
            avg_throughputs.append(0)
    
    # Filter out zero values
    valid_flavors = [f for f, m in zip(flavors, max_throughputs) if m > 0]
    valid_max = [m for m in max_throughputs if m > 0]
    valid_avg = [a for a in avg_throughputs if a > 0]
    valid_colors = [c for c, m in zip(colors, max_throughputs) if m > 0]
    
    x_pos = range(len(valid_flavors))
    
    # Bar chart for maximum throughput
    bars1 = plt.bar([x - 0.2 for x in x_pos], valid_max, 0.4, 
                    label='Maximum Throughput', color=valid_colors, alpha=0.8)
    
    # Bar chart for average throughput
    bars2 = plt.bar([x + 0.2 for x in x_pos], valid_avg, 0.4,
                    label='Average Throughput', color=valid_colors, alpha=0.5)
    
    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom')
    
    for bar in bars2:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom')
    
    plt.xlabel('Cluster Flavor')
    plt.ylabel('Throughput (MB/sec)')
    plt.title('Kafka Cluster Performance: Throughput by Flavor')
    plt.xticks(x_pos, valid_flavors)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_file = os.path.join(output_dir, 'flavor_throughput_comparison.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Throughput comparison chart saved to {output_file}")

def create_scaling_efficiency_chart(flavor_results, output_dir):
    """Create scaling efficiency analysis"""
    plt.figure(figsize=(12, 8))
    
    flavors = ['small', 'medium', 'large', 'xlarge']
    baseline_throughput = None
    scaling_factors = [1, 2, 4, 8]  # Approximate relative sizes
    
    actual_throughputs = []
    expected_throughputs = []
    flavor_labels = []
    
    for i, flavor in enumerate(flavors):
        if flavor in flavor_results and flavor_results[flavor]:
            results = flavor_results[flavor]
            avg_throughput = np.mean([r['total_mb_per_sec'] for r in results])
            actual_throughputs.append(avg_throughput)
            expected_throughputs.append(scaling_factors[i] * 50)  # Baseline assumption
            flavor_labels.append(flavor)
            
            if baseline_throughput is None:
                baseline_throughput = avg_throughput
    
    if actual_throughputs:
        # Calculate scaling efficiency
        efficiencies = []
        for i, (actual, expected) in enumerate(zip(actual_throughputs, expected_throughputs)):
            efficiency = actual / expected * 100
            efficiencies.append(efficiency)
        
        x_pos = range(len(flavor_labels))
        
        plt.bar(x_pos, efficiencies, color=['lightblue', 'orange', 'green', 'red'])
        
        # Add value labels
        for i, (pos, efficiency) in enumerate(zip(x_pos, efficiencies)):
            plt.text(pos, efficiency + 1, f'{efficiency:.1f}%', 
                    ha='center', va='bottom')
        
        plt.xlabel('Cluster Flavor')
        plt.ylabel('Scaling Efficiency (%)')
        plt.title('Kafka Cluster Scaling Efficiency')
        plt.xticks(x_pos, flavor_labels)
        plt.grid(True, alpha=0.3, axis='y')
        plt.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='Linear Scaling')
        plt.legend()
        plt.tight_layout()
        
        output_file = os.path.join(output_dir, 'scaling_efficiency.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Scaling efficiency chart saved to {output_file}")

def create_performance_limit_summary(flavor_results, output_dir):
    """Create detailed performance limit summary"""
    summary = {
        'flavor_analysis': {},
        'scaling_insights': {},
        'recommendations': {}
    }
    
    flavors = ['small', 'medium', 'large', 'xlarge']
    flavor_specs = {
        'small': {'producers': 3, 'partitions': 12, 'replication': 1},
        'medium': {'producers': 6, 'partitions': 24, 'replication': 2},
        'large': {'producers': 12, 'partitions': 48, 'replication': 3},
        'xlarge': {'producers': 18, 'partitions': 72, 'replication': 3}
    }
    
    for flavor in flavors:
        if flavor in flavor_results and flavor_results[flavor]:
            results = flavor_results[flavor]
            throughputs = [r['total_mb_per_sec'] for r in results]
            p50_latencies = [r['avg_latency_ms_p50'] for r in results]
            p99_latencies = [r['avg_latency_ms_p99'] for r in results]
            
            summary['flavor_analysis'][flavor] = {
                'max_throughput': max(throughputs) if throughputs else 0,
                'avg_throughput': np.mean(throughputs) if throughputs else 0,
                'min_p50_latency': min(p50_latencies) if p50_latencies else 0,
                'max_p50_latency': max(p50_latencies) if p50_latencies else 0,
                'avg_p50_latency': np.mean(p50_latencies) if p50_latencies else 0,
                'total_tests': len(results),
                'config': flavor_specs.get(flavor, {})
            }
    
    # Generate scaling insights
    flavor_throughputs = [summary['flavor_analysis'][f]['max_throughput'] 
                         for f in flavors 
                         if f in summary['flavor_analysis']]
    
    if len(flavor_throughputs) >= 2:
        for i in range(1, len(flavor_throughputs)):
            if flavor_throughputs[i-1] > 0:
                scaling_ratio = flavor_throughputs[i] / flavor_throughputs[i-1]
                summary['scaling_insights'][f'{flavors[i-1]}_to_{flavors[i]}'] = {
                    'scaling_factor': scaling_ratio,
                    'description': f'{flavors[i]} is {scaling_ratio:.2f}x faster than {flavors[i-1]}'
                }
    
    # Generate recommendations
    if summary['flavor_analysis']:
        max_flavor = max(summary['flavor_analysis'].keys(), 
                        key=lambda x: summary['flavor_analysis'][x]['max_throughput'])
        summary['recommendations'] = {
            'best_performance': max_flavor,
            'max_throughput_achieved': summary['flavor_analysis'][max_flavor]['max_throughput'],
            'latency_characteristics': {
                'p50_range': f"{min([summary['flavor_analysis'][f]['min_p50_latency'] for f in summary['flavor_analysis']]):.1f} - {max([summary['flavor_analysis'][f]['max_p50_latency'] for f in summary['flavor_analysis']]):.1f} ms",
                'typical_p99': f"{np.mean([summary['flavor_analysis'][f]['avg_p50_latency'] for f in summary['flavor_analysis']]):.1f} ms"
            }
        }
    
    # Save summary
    summary_file = os.path.join(output_dir, 'performance_limit_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Performance limit summary saved to {summary_file}")
    
    # Print human-readable summary
    print("\n=== Performance Limit Analysis Summary ===")
    for flavor, data in summary['flavor_analysis'].items():
        print(f"\n{flavor.upper()} Cluster:")
        print(f"  Max Throughput: {data['max_throughput']:.1f} MB/sec")
        print(f"  Avg Throughput: {data['avg_throughput']:.1f} MB/sec")
        print(f"  P50 Latency: {data['avg_p50_latency']:.1f} ms")
        print(f"  Tests Completed: {data['total_tests']}")
    
    if 'best_performance' in summary['recommendations']:
        print(f"\n🏆 Best Performance: {summary['recommendations']['best_performance'].upper()}")
        print(f"   Maximum Throughput: {summary['recommendations']['max_throughput_achieved']:.1f} MB/sec")

def main():
    parser = argparse.ArgumentParser(description='Generate comparative performance charts for cluster flavors')
    parser.add_argument('--input-dir', default='../results/comparison', 
                       help='Directory containing flavor results')
    parser.add_argument('--output-dir', default='../results/comparison', 
                       help='Directory for output charts')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    print("Loading flavor results...")
    flavor_results = load_flavor_results(args.input_dir)
    
    if not flavor_results:
        print("No flavor results found to process")
        return
    
    print("Generating comparative analysis...")
    create_throughput_comparison_chart(flavor_results, args.output_dir)
    create_scaling_efficiency_chart(flavor_results, args.output_dir)
    create_performance_limit_summary(flavor_results, args.output_dir)
    
    print(f"\n✅ Comparative analysis completed in {args.output_dir}")

if __name__ == "__main__":
    main()