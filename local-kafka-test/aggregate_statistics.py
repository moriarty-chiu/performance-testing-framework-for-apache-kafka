"""
Aggregate test results from multiple test runs.

This module provides functions to aggregate and analyze Kafka performance
test results, similar to the original aggregate_statistics.py.
"""

import json
import glob
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
import statistics

import pandas as pd


def load_test_results(results_dir: str, pattern: str = "*.json") -> List[Dict[str, Any]]:
    """
    Load all test results from a directory.
    
    Args:
        results_dir: Directory containing result files
        pattern: Glob pattern for result files
        
    Returns:
        List of test result dictionaries
    """
    results = []
    results_path = Path(results_dir)
    
    for filepath in results_path.glob(pattern):
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                data['_source_file'] = str(filepath)
                results.append(data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load {filepath}: {e}")
    
    return results


def extract_producer_metrics(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract producer metrics from a test result.
    
    Args:
        result: Test result dictionary
        
    Returns:
        List of producer metric dictionaries
    """
    metrics = []
    test_params = result.get('test_params', {})
    
    for producer_result in result.get('producer_results', []):
        metric = {
            'test_id': test_params.get('test_id'),
            'throughput_series_id': test_params.get('throughput_series_id'),
            'topic_name': test_params.get('topic_name'),
            'mock_data': result.get('mock_data', False),
            
            # Test parameters
            'cluster_throughput_mb_per_sec': test_params.get('cluster_throughput_mb_per_sec'),
            'num_producers': test_params.get('num_producers'),
            'num_partitions': test_params.get('num_partitions'),
            'record_size_byte': test_params.get('record_size_byte'),
            'replication_factor': test_params.get('replication_factor'),
            'duration_sec': test_params.get('duration_sec'),
            'producer_id': producer_result.get('test_params', {}).get('producer_id'),
            
            # Client properties
            'client_props.producer': test_params.get('client_props', {}).get('producer', ''),
            'client_props.consumer': test_params.get('client_props', {}).get('consumer', ''),
            
            # Producer metrics
            'records_sent': producer_result.get('records_sent'),
            'records_per_sec': producer_result.get('records_per_sec'),
            'mb_per_sec': producer_result.get('mbPerSecSum'),
            'avg_latency_ms': producer_result.get('avg_latency_ms'),
            'p50_latency_ms': producer_result.get('p50_latency_ms'),
            'p99_latency_ms': producer_result.get('p99_latency_ms'),
            'elapsed_time_sec': producer_result.get('elapsed_time_sec'),
            
            # Derived metrics
            'sent_div_requested_mb_per_sec': (
                producer_result.get('mbPerSecSum', 0) / test_params.get('cluster_throughput_mb_per_sec', 1)
                if test_params.get('cluster_throughput_mb_per_sec', 0) > 0 else None
            ),
        }
        metrics.append(metric)
    
    return metrics


def extract_consumer_metrics(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract consumer metrics from a test result.
    
    Args:
        result: Test result dictionary
        
    Returns:
        List of consumer metric dictionaries
    """
    metrics = []
    test_params = result.get('test_params', {})
    
    for consumer_result in result.get('consumer_results', []):
        metric = {
            'test_id': test_params.get('test_id'),
            'throughput_series_id': test_params.get('throughput_series_id'),
            'topic_name': test_params.get('topic_name'),
            'mock_data': result.get('mock_data', False),
            
            # Test parameters
            'cluster_throughput_mb_per_sec': test_params.get('cluster_throughput_mb_per_sec'),
            'num_producers': test_params.get('num_producers'),
            'num_partitions': test_params.get('num_partitions'),
            'record_size_byte': test_params.get('record_size_byte'),
            'replication_factor': test_params.get('replication_factor'),
            'duration_sec': test_params.get('duration_sec'),
            'consumer_group_id': consumer_result.get('test_params', {}).get('consumer_group_id'),
            'consumer_id': consumer_result.get('test_params', {}).get('consumer_id'),
            'consumer_groups.num_groups': test_params.get('consumer_groups', {}).get('num_groups'),
            'consumer_groups.size': test_params.get('consumer_groups', {}).get('size'),
            
            # Client properties
            'client_props.producer': test_params.get('client_props', {}).get('producer', ''),
            'client_props.consumer': test_params.get('client_props', {}).get('consumer', ''),
            
            # Consumer metrics
            'bytes_consumed': consumer_result.get('bytes_consumed'),
            'mb_per_sec': consumer_result.get('mb_per_sec'),
            'fetch_rate': consumer_result.get('fetch_rate'),
            'avg_fetch_latency_ms': consumer_result.get('avg_fetch_latency_ms'),
            'elapsed_time_sec': consumer_result.get('elapsed_time_sec'),
        }
        metrics.append(metric)
    
    return metrics


def flatten_client_props(props: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten client properties for easier analysis.
    
    Args:
        props: Client properties dictionary
        
    Returns:
        Flattened properties dictionary
    """
    flattened = {}
    
    for key, value in props.items():
        if isinstance(value, str):
            # Parse space-separated properties
            for prop in value.split():
                if '=' in prop:
                    prop_key, prop_value = prop.split('=', 1)
                    flattened[f'{key}.{prop_key}'] = prop_value
        else:
            flattened[key] = value
    
    return flattened


def aggregate_by_groups(df: pd.DataFrame, 
                       group_keys: List[str], 
                       metric_columns: List[str]) -> pd.DataFrame:
    """
    Aggregate metrics by specified groups.
    
    Args:
        df: DataFrame with test metrics
        group_keys: Columns to group by
        metric_columns: Metric columns to aggregate
        
    Returns:
        Aggregated DataFrame
    """
    agg_funcs = ['mean', 'std', 'min', 'max', 'count']
    
    grouped = df.groupby(group_keys)[metric_columns].agg(agg_funcs)
    
    # Flatten column names
    grouped.columns = [f'{col}_{func}' for col, func in grouped.columns]
    
    return grouped.reset_index()


def create_summary_statistics(producer_df: pd.DataFrame, 
                             consumer_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Create summary statistics for test results.
    
    Args:
        producer_df: Producer metrics DataFrame
        consumer_df: Consumer metrics DataFrame
        
    Returns:
        Summary statistics dictionary
    """
    summary = {
        'producer_summary': {},
        'consumer_summary': {},
        'test_count': len(producer_df['test_id'].unique()) if 'test_id' in producer_df.columns else 0
    }
    
    # Producer summary
    if not producer_df.empty:
        summary['producer_summary'] = {
            'total_records_sent': producer_df['records_sent'].sum() if 'records_sent' in producer_df.columns else 0,
            'avg_throughput_mb_per_sec': producer_df['mb_per_sec'].mean() if 'mb_per_sec' in producer_df.columns else 0,
            'avg_latency_ms': producer_df['avg_latency_ms'].mean() if 'avg_latency_ms' in producer_df.columns else 0,
            'p99_latency_ms': producer_df['p99_latency_ms'].mean() if 'p99_latency_ms' in producer_df.columns else 0,
        }
    
    # Consumer summary
    if not consumer_df.empty:
        summary['consumer_summary'] = {
            'total_bytes_consumed': consumer_df['bytes_consumed'].sum() if 'bytes_consumed' in consumer_df.columns else 0,
            'avg_throughput_mb_per_sec': consumer_df['mb_per_sec'].mean() if 'mb_per_sec' in consumer_df.columns else 0,
            'avg_fetch_latency_ms': consumer_df['avg_fetch_latency_ms'].mean() if 'avg_fetch_latency_ms' in consumer_df.columns else 0,
        }
    
    return summary


def load_and_aggregate_results(results_dir: str) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Load all results and create aggregated DataFrames.
    
    Args:
        results_dir: Directory containing result files
        
    Returns:
        Tuple of (producer_df, consumer_df, summary)
    """
    all_results = load_test_results(results_dir)
    
    all_producer_metrics = []
    all_consumer_metrics = []
    
    for result in all_results:
        all_producer_metrics.extend(extract_producer_metrics(result))
        all_consumer_metrics.extend(extract_consumer_metrics(result))
    
    producer_df = pd.DataFrame(all_producer_metrics)
    consumer_df = pd.DataFrame(all_consumer_metrics)
    
    summary = create_summary_statistics(producer_df, consumer_df)
    
    return producer_df, consumer_df, summary


def filter_results(df: pd.DataFrame, 
                  filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """
    Filter results based on specified criteria.
    
    Args:
        df: DataFrame to filter
        filters: Dictionary of column:value pairs to filter on
        
    Returns:
        Filtered DataFrame
    """
    if filters is None:
        return df
    
    filtered = df.copy()
    
    for column, value in filters.items():
        if column in filtered.columns:
            if isinstance(value, (list, tuple)):
                filtered = filtered[filtered[column].isin(value)]
            else:
                filtered = filtered[filtered[column] == value]
    
    return filtered


def export_results(producer_df: pd.DataFrame, consumer_df: pd.DataFrame,
                  output_dir: str) -> None:
    """
    Export aggregated results to CSV files.
    
    Args:
        producer_df: Producer metrics DataFrame
        consumer_df: Consumer metrics DataFrame
        output_dir: Output directory
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    producer_df.to_csv(output_path / 'producer_metrics.csv', index=False)
    consumer_df.to_csv(output_path / 'consumer_metrics.csv', index=False)
    
    print(f"Results exported to {output_path}")
