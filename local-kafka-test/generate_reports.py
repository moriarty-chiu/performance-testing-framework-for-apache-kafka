#!/usr/bin/env python3
"""
Generate reports and plots from Kafka performance test results.

This script creates visualizations and summary reports without requiring Jupyter.
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt

import aggregate_statistics
import plot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_text_report(producer_df: pd.DataFrame, consumer_df: pd.DataFrame,
                        output_path: str) -> None:
    """
    Generate a text-based summary report.
    
    Args:
        producer_df: Producer metrics DataFrame
        consumer_df: Consumer metrics DataFrame
        output_path: Path to save the report
    """
    output_file = Path(output_path)
    
    with open(output_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("KAFKA PERFORMANCE TEST REPORT\n")
        f.write("=" * 80 + "\n\n")
        
        # Check if this is mock data
        is_mock = 'mock_data' in producer_df.columns and producer_df['mock_data'].any()
        if is_mock:
            f.write("*** NOTE: This report was generated from MOCK DATA (debug mode) ***\n")
            f.write("*** Results are simulated and do not reflect actual cluster performance ***\n\n")
        
        # Overall summary
        f.write("OVERALL SUMMARY\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total test runs: {len(producer_df)}\n")
        if 'test_id' in producer_df.columns:
            f.write(f"Unique tests: {producer_df['test_id'].nunique()}\n")
        if 'mock_data' in producer_df.columns:
            mock_count = producer_df['mock_data'].sum()
            f.write(f"Mock data records: {mock_count}\n")
        f.write("\n")
        
        # Producer summary
        f.write("PRODUCER METRICS\n")
        f.write("-" * 40 + "\n")
        
        if not producer_df.empty:
            metrics_to_report = [
                ('mb_per_sec', 'Throughput (MB/sec)'),
                ('avg_latency_ms', 'Avg Latency (ms)'),
                ('p99_latency_ms', 'P99 Latency (ms)'),
                ('records_per_sec', 'Records/sec'),
            ]
            
            for col, label in metrics_to_report:
                if col in producer_df.columns:
                    f.write(f"{label}:\n")
                    f.write(f"  Mean: {producer_df[col].mean():.2f}\n")
                    f.write(f"  Std:  {producer_df[col].std():.2f}\n")
                    f.write(f"  Min:  {producer_df[col].min():.2f}\n")
                    f.write(f"  Max:  {producer_df[col].max():.2f}\n")
            
            # Group by configured throughput
            if 'cluster_throughput_mb_per_sec' in producer_df.columns:
                f.write("\nMetrics by Configured Throughput:\n")
                grouped = producer_df.groupby('cluster_throughput_mb_per_sec').agg({
                    'mb_per_sec': 'mean',
                    'avg_latency_ms': 'mean',
                    'p99_latency_ms': 'mean',
                    'sent_div_requested_mb_per_sec': 'mean'
                }).round(3)
                
                f.write(grouped.to_string())
                f.write("\n")
        else:
            f.write("No producer data available\n")
        
        f.write("\n")
        
        # Consumer summary
        f.write("CONSUMER METRICS\n")
        f.write("-" * 40 + "\n")
        
        if not consumer_df.empty:
            metrics_to_report = [
                ('mb_per_sec', 'Throughput (MB/sec)'),
                ('avg_fetch_latency_ms', 'Avg Fetch Latency (ms)'),
            ]
            
            for col, label in metrics_to_report:
                if col in consumer_df.columns:
                    f.write(f"{label}:\n")
                    f.write(f"  Mean: {consumer_df[col].mean():.2f}\n")
                    f.write(f"  Std:  {consumer_df[col].std():.2f}\n")
                    f.write(f"  Min:  {consumer_df[col].min():.2f}\n")
                    f.write(f"  Max:  {consumer_df[col].max():.2f}\n")
        else:
            f.write("No consumer data available\n")
        
        f.write("\n")
        f.write("=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")
    
    logger.info(f"Text report saved to {output_file}")


def generate_csv_export(producer_df: pd.DataFrame, consumer_df: pd.DataFrame,
                       output_dir: str) -> None:
    """
    Export results to CSV files.
    
    Args:
        producer_df: Producer metrics DataFrame
        consumer_df: Consumer metrics DataFrame
        output_dir: Output directory
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    producer_df.to_csv(output_path / 'producer_metrics.csv', index=False)
    consumer_df.to_csv(output_path / 'consumer_metrics.csv', index=False)
    
    logger.info(f"CSV files exported to {output_path}")


def generate_all_plots(producer_df: pd.DataFrame, consumer_df: pd.DataFrame,
                      output_dir: str) -> list:
    """
    Generate all standard plots.
    
    Args:
        producer_df: Producer metrics DataFrame
        consumer_df: Consumer metrics DataFrame
        output_dir: Output directory
        
    Returns:
        List of generated plot file paths
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    plot_files = []
    
    if not producer_df.empty:
        # Plot 1: Throughput vs Latency
        try:
            fig = plot.plot_throughput_vs_latency(
                producer_df,
                x_col='mb_per_sec',
                y_col='avg_latency_ms',
                title='Producer: Throughput vs Average Latency'
            )
            fig_path = output_path / '01_producer_throughput_vs_latency.png'
            fig.savefig(fig_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            plot_files.append(str(fig_path))
            logger.info(f"Created: {fig_path}")
        except Exception as e:
            logger.warning(f"Could not create throughput vs latency plot: {e}")
        
        # Plot 2: Latency Percentiles
        try:
            fig = plot.plot_latency_percentiles(
                producer_df,
                x_col='cluster_throughput_mb_per_sec',
                title='Producer: Latency Percentiles vs Configured Throughput'
            )
            fig_path = output_path / '02_producer_latency_percentiles.png'
            fig.savefig(fig_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            plot_files.append(str(fig_path))
            logger.info(f"Created: {fig_path}")
        except Exception as e:
            logger.warning(f"Could not create latency percentiles plot: {e}")
        
        # Plot 3: Throughput Efficiency
        try:
            fig = plot.plot_throughput_efficiency(
                producer_df,
                x_col='cluster_throughput_mb_per_sec',
                y_col='sent_div_requested_mb_per_sec',
                title='Producer: Actual vs Requested Throughput Ratio'
            )
            fig_path = output_path / '03_producer_throughput_efficiency.png'
            fig.savefig(fig_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            plot_files.append(str(fig_path))
            logger.info(f"Created: {fig_path}")
        except Exception as e:
            logger.warning(f"Could not create throughput efficiency plot: {e}")
        
        # Plot 4: Latency by Throughput (line chart)
        try:
            if 'cluster_throughput_mb_per_sec' in producer_df.columns:
                fig, ax = plt.subplots(figsize=(10, 6))
                grouped = producer_df.groupby('cluster_throughput_mb_per_sec').agg({
                    'avg_latency_ms': ['mean', 'std']
                }).reset_index()
                grouped.columns = ['throughput', 'avg_latency', 'std_latency']
                
                ax.plot(grouped['throughput'], grouped['avg_latency'], 
                       marker='o', linewidth=2, label='Avg Latency')
                ax.fill_between(
                    grouped['throughput'],
                    grouped['avg_latency'] - grouped['std_latency'],
                    grouped['avg_latency'] + grouped['std_latency'],
                    alpha=0.3
                )
                ax.set_xlabel('Configured Throughput (MB/sec)')
                ax.set_ylabel('Latency (ms)')
                ax.set_title('Latency vs Throughput')
                ax.grid(True, alpha=0.3)
                plt.tight_layout()
                
                fig_path = output_path / '04_latency_vs_throughput.png'
                fig.savefig(fig_path, dpi=150, bbox_inches='tight')
                plt.close(fig)
                plot_files.append(str(fig_path))
                logger.info(f"Created: {fig_path}")
        except Exception as e:
            logger.warning(f"Could not create latency vs throughput plot: {e}")
    
    if not consumer_df.empty:
        # Plot 5: Consumer Throughput
        try:
            fig = plot.plot_consumer_throughput(
                consumer_df,
                x_col='cluster_throughput_mb_per_sec',
                y_col='mb_per_sec',
                group_col='consumer_groups.num_groups',
                title='Consumer: Throughput by Consumer Groups'
            )
            fig_path = output_path / '05_consumer_throughput.png'
            fig.savefig(fig_path, dpi=150, bbox_inches='tight')
            plt.close(fig)
            plot_files.append(str(fig_path))
            logger.info(f"Created: {fig_path}")
        except Exception as e:
            logger.warning(f"Could not create consumer throughput plot: {e}")
    
    return plot_files


def main():
    parser = argparse.ArgumentParser(
        description='Generate reports and plots from Kafka performance test results'
    )
    parser.add_argument(
        '--results-dir', '-r',
        default=None,
        help='Directory containing test results. If not specified, will auto-detect from --test-name or use ./results'
    )
    parser.add_argument(
        '--test-name', '-n',
        default=None,
        help='Test run name (subdirectory under results/). Auto-detected if --results-dir not specified.'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default=None,
        help='Directory to save reports and plots. Defaults to <results-dir>/reports'
    )
    parser.add_argument(
        '--base-results-dir',
        default='./results',
        help='Base results directory (default: ./results). Used with --test-name to construct full path.'
    )
    parser.add_argument(
        '--no-plots',
        action='store_true',
        help='Skip plot generation'
    )
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='Skip text report generation'
    )
    parser.add_argument(
        '--no-csv',
        action='store_true',
        help='Skip CSV export'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Determine results directory
    if args.results_dir is None:
        if args.test_name is None:
            # Auto-detect: use most recent test directory
            base_path = Path(args.base_results_dir)
            if base_path.exists():
                test_dirs = [d for d in base_path.iterdir() if d.is_dir()]
                if test_dirs:
                    args.results_dir = max(test_dirs, key=lambda d: d.stat().st_mtime)
                    logger.info(f"Auto-detected results directory: {args.results_dir}")
                else:
                    args.results_dir = base_path
            else:
                args.results_dir = base_path
        else:
            args.results_dir = Path(args.base_results_dir) / args.test_name
    
    args.results_dir = Path(args.results_dir)
    
    # Determine output directory
    if args.output_dir is None:
        args.output_dir = args.results_dir / 'reports'
    else:
        args.output_dir = Path(args.output_dir)
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load results
    logger.info(f"Loading results from {args.results_dir}")
    producer_df, consumer_df, summary = aggregate_statistics.load_and_aggregate_results(args.results_dir)
    
    logger.info(f"Loaded {len(producer_df)} producer records")
    logger.info(f"Loaded {len(consumer_df)} consumer records")
    
    if producer_df.empty and consumer_df.empty:
        logger.error("No data found. Please check the results directory.")
        sys.exit(1)
    
    # Create output directory
    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate outputs
    generated_files = []
    
    if not args.no_report:
        report_path = output_path / 'summary_report.txt'
        generate_text_report(producer_df, consumer_df, str(report_path))
        generated_files.append(str(report_path))
    
    if not args.no_csv:
        generate_csv_export(producer_df, consumer_df, str(output_path))
        generated_files.extend([
            str(output_path / 'producer_metrics.csv'),
            str(output_path / 'consumer_metrics.csv')
        ])
    
    if not args.no_plots:
        plot_files = generate_all_plots(producer_df, consumer_df, str(output_path))
        generated_files.extend(plot_files)
    
    # Print summary
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(f"Results directory: {args.results_dir.absolute()}")
    print(f"Output directory: {args.output_dir.absolute()}")
    print(f"Generated {len(generated_files)} files:")
    for f in generated_files:
        print(f"  - {f}")
    print("=" * 60)


if __name__ == '__main__':
    main()
