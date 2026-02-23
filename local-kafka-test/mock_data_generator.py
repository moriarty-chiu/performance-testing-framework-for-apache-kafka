"""
Mock data generator for Kafka performance tests.

Generates realistic mock data based on test specifications.
"""

import random
import math
from typing import Dict, List, Any
from datetime import datetime


class MockDataGenerator:
    """Generate realistic mock Kafka performance test data."""

    def __init__(self, seed: int = None):
        """
        Initialize the mock data generator.
        
        Args:
            seed: Random seed for reproducibility
        """
        if seed is not None:
            random.seed(seed)
        self.seed = seed

    def generate_producer_result(self, test_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate realistic producer test results based on parameters.
        
        Args:
            test_params: Test parameters from specification
            
        Returns:
            Mock producer result dictionary
        """
        cluster_throughput_mb = test_params.get('cluster_throughput_mb_per_sec', 0)
        num_producers = test_params.get('num_producers', 1)
        record_size_byte = test_params.get('record_size_byte', 1024)
        duration_sec = test_params.get('duration_sec', 60)
        num_partitions = test_params.get('num_partitions', 1)
        client_props = test_params.get('client_props', {}).get('producer', '')
        
        # Calculate base throughput per producer
        if cluster_throughput_mb > 0:
            target_throughput_per_producer = cluster_throughput_mb / num_producers
        else:
            # For depletion mode, use max throughput
            target_throughput_per_producer = 100  # MB/sec

        # Add realistic variance based on throughput level
        # Higher throughput = more variance and potential saturation
        # Only apply saturation at very high throughput (>200 MB/s) to allow normal testing
        saturation_factor = 1.0
        if cluster_throughput_mb > 200:
            # Simulate cluster saturation at very high throughput
            saturation_factor = max(0.7, 1.0 - (cluster_throughput_mb - 200) / 500)

        # Parse client properties for acks configuration
        acks_all = 'acks=all' in client_props
        linger_ms = self._parse_prop(client_props, 'linger.ms', 0)
        batch_size = self._parse_prop(client_props, 'batch.size', 16384)

        # Calculate latency based on configuration
        # Base latency increases with throughput
        base_latency = 2.0 + (cluster_throughput_mb / 20)  # ms

        # acks=all adds latency
        if acks_all:
            base_latency *= 1.3

        # Larger batch size reduces latency slightly
        batch_factor = max(0.8, 1.0 - (batch_size - 16384) / 100000)

        # Linger time adds to latency
        linger_factor = 1.0 + (linger_ms / 100)

        avg_latency = base_latency * batch_factor * linger_factor

        # Add some randomness (±10%)
        latency_variance = random.uniform(0.9, 1.1)
        avg_latency *= latency_variance

        # P99 is typically 2-3x average
        p99_latency = avg_latency * random.uniform(2.2, 2.8)

        # P50 is typically 0.8-0.9x average
        p50_latency = avg_latency * random.uniform(0.8, 0.9)

        # Calculate actual throughput with variance
        # Use small variance (±2%) to ensure tests pass skip condition normally
        # Only reduce throughput when approaching cluster limits (>200 MB/s)
        throughput_variance = 0.01 + (cluster_throughput_mb / 5000)
        actual_throughput_ratio = random.gauss(0.98, throughput_variance) * saturation_factor
        actual_throughput_ratio = max(0.95, min(1.02, actual_throughput_ratio))

        actual_mb_per_sec = target_throughput_per_producer * actual_throughput_ratio

        # Calculate records
        records_per_sec = (actual_mb_per_sec * 1024 * 1024) / record_size_byte
        total_records = int(records_per_sec * duration_sec)

        # Add realistic errors (rare at low throughput, more common at high)
        error_rate = 0.0
        if cluster_throughput_mb > 300:
            error_rate = min(0.05, (cluster_throughput_mb - 300) / 1000)

        timeout_count = int(total_records * error_rate * 0.1) if random.random() < 0.3 else 0
        error_count = int(total_records * error_rate * 0.05) if random.random() < 0.2 else 0

        # Calculate total cluster throughput (sum of all producers)
        # This is what sent_div_requested_mb_per_sec should compare against
        total_cluster_mb_per_sec = actual_mb_per_sec * num_producers

        return {
            'test_params': test_params,
            'records_sent': total_records,
            'records_per_sec': records_per_sec,
            'mbPerSecSum': total_cluster_mb_per_sec,  # Total cluster throughput
            'avg_latency_ms': avg_latency,
            'p50_latency_ms': p50_latency,
            'p99_latency_ms': p99_latency,
            'elapsed_time_sec': duration_sec * random.uniform(0.98, 1.02),
            'return_code': 0 if error_count == 0 else 1,
            'timeout_exception_count': timeout_count,
            'error_count': error_count,
            'raw_output': self._generate_raw_producer_output(
                total_records, records_per_sec, actual_mb_per_sec, avg_latency
            ),
            'raw_error': ''
        }

    def generate_consumer_result(self, test_params: Dict[str, Any], 
                                 consumer_group_id: int, 
                                 consumer_id: int) -> Dict[str, Any]:
        """
        Generate realistic consumer test results based on parameters.
        
        Args:
            test_params: Test parameters from specification
            consumer_group_id: Consumer group ID
            consumer_id: Consumer ID within group
            
        Returns:
            Mock consumer result dictionary
        """
        cluster_throughput_mb = test_params.get('cluster_throughput_mb_per_sec', 0)
        consumer_groups_config = test_params.get('consumer_groups', {})
        num_groups = consumer_groups_config.get('num_groups', 0)
        group_size = consumer_groups_config.get('size', 1)
        record_size_byte = test_params.get('record_size_byte', 1024)
        duration_sec = test_params.get('duration_sec', 60)
        
        if num_groups == 0 or cluster_throughput_mb <= 0:
            # No consumers or no throughput
            return {
                'test_params': {**test_params, 'consumer_group_id': consumer_group_id, 'consumer_id': consumer_id},
                'bytes_consumed': 0,
                'mb_per_sec': 0,
                'fetch_rate': 0,
                'avg_fetch_latency_ms': 0,
                'elapsed_time_sec': duration_sec,
                'return_code': 0,
                'raw_output': 'No consumers configured',
                'raw_error': ''
            }
        
        # Total consumers
        total_consumers = num_groups * group_size
        
        # Throughput per consumer (cluster throughput divided by total consumers)
        throughput_per_consumer = cluster_throughput_mb / total_consumers
        
        # Add variance (±5%)
        actual_throughput = throughput_per_consumer * random.uniform(0.95, 1.05)
        
        # Calculate bytes consumed
        total_bytes = int(actual_throughput * 1024 * 1024 * duration_sec)
        
        # Fetch rate (records per sec)
        fetch_rate = (actual_throughput * 1024 * 1024) / record_size_byte
        
        # Fetch latency (typically lower than producer latency)
        base_fetch_latency = 1.0 + (cluster_throughput_mb / 50)
        fetch_latency = base_fetch_latency * random.uniform(0.9, 1.1)
        
        return {
            'test_params': {**test_params, 'consumer_group_id': consumer_group_id, 'consumer_id': consumer_id},
            'bytes_consumed': total_bytes,
            'mb_per_sec': actual_throughput,
            'fetch_rate': fetch_rate,
            'avg_fetch_latency_ms': fetch_latency,
            'elapsed_time_sec': duration_sec * random.uniform(0.98, 1.02),
            'return_code': 0,
            'raw_output': self._generate_raw_consumer_output(total_bytes, actual_throughput, fetch_rate),
            'raw_error': ''
        }

    def _parse_prop(self, props: str, key: str, default: Any) -> Any:
        """Parse a property from client props string."""
        for prop in props.split():
            if prop.startswith(f'{key}='):
                try:
                    return int(prop.split('=')[1])
                except (ValueError, IndexError):
                    return default
        return default

    def _generate_raw_producer_output(self, records: int, records_per_sec: float,
                                      mb_per_sec: float, avg_latency: float) -> str:
        """Generate realistic raw producer output string."""
        return (
            f"{records} records sent, {records_per_sec:.2f} records/sec "
            f"({mb_per_sec:.2f} MB/sec), {avg_latency:.1f} ms avg latency, "
            f"{avg_latency * 2.5:.1f} ms p99 latency"
        )

    def _generate_raw_consumer_output(self, bytes_consumed: int, 
                                      mb_per_sec: float, fetch_rate: float) -> str:
        """Generate realistic raw consumer output string."""
        return (
            f"{bytes_consumed} bytes consumed, {mb_per_sec:.2f} MB/sec, "
            f"{fetch_rate:.2f} records/sec, fetch.latency avg = {mb_per_sec/10:.1f}"
        )

    def generate_test_results(self, test_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate complete mock test results for a test configuration.
        
        Args:
            test_params: Test parameters from specification
            
        Returns:
            Complete mock test results dictionary
        """
        num_producers = test_params.get('num_producers', 1)
        consumer_groups_config = test_params.get('consumer_groups', {})
        num_groups = consumer_groups_config.get('num_groups', 0)
        group_size = consumer_groups_config.get('size', 1)
        
        results = {
            'test_params': test_params,
            'producer_results': [],
            'consumer_results': [],
            'mock_data': True,
            'generated_at': datetime.now().isoformat()
        }
        
        # Generate producer results
        for i in range(num_producers):
            producer_result = self.generate_producer_result({
                **test_params,
                'producer_id': i
            })
            results['producer_results'].append(producer_result)
        
        # Generate consumer results if configured
        if num_groups > 0:
            for group_idx in range(num_groups):
                for consumer_idx in range(group_size):
                    consumer_result = self.generate_consumer_result(
                        test_params, group_idx, consumer_idx
                    )
                    results['consumer_results'].append(consumer_result)
        
        return results

    def generate_full_test_suite_results(self, spec: Dict[str, Any],
                                        seed: int = None) -> List[Dict[str, Any]]:
        """
        Generate mock results for an entire test suite.
        
        Args:
            spec: Test specification
            seed: Random seed for reproducibility
            
        Returns:
            List of mock test results
        """
        if seed is not None:
            random.seed(seed)
        
        from test_parameters import increment_index_and_update_parameters
        
        event = spec.copy()
        all_results = []
        max_tests = 1000
        test_count = 0
        
        while test_count < max_tests:
            event = increment_index_and_update_parameters(event)
            
            if event.get('all_tests_completed', False):
                break
            
            test_params = event['current_test']['parameters']
            test_count += 1
            
            # Generate mock results
            results = self.generate_test_results(test_params)
            all_results.append(results)
            
            # Simulate skip condition
            if 'skip_remaining_throughput' in event.get('test_specification', {}):
                if results['producer_results']:
                    producer_result = results['producer_results'][0]
                    event['producer_result'] = producer_result
                    
                    skip_condition = event['test_specification']['skip_remaining_throughput']
                    if self._evaluate_skip_condition_mock(skip_condition, event):
                        continue
        
        return all_results

    def _evaluate_skip_condition_mock(self, condition: Any, event: Dict[str, Any]) -> bool:
        """Evaluate skip condition for mock data."""
        if isinstance(condition, dict):
            if "less-than" in condition:
                args = condition["less-than"]
                left = self._evaluate_skip_condition_mock(args[0], event)
                right = self._evaluate_skip_condition_mock(args[1], event)
                return left < right
            elif "greater-than" in condition:
                args = condition["greater-than"]
                left = self._evaluate_skip_condition_mock(args[0], event)
                right = self._evaluate_skip_condition_mock(args[1], event)
                return left > right
        elif isinstance(condition, str):
            if condition == "sent_div_requested_mb_per_sec":
                producer_result = event.get('producer_result', {})
                mb_per_sec_sum = producer_result.get('mbPerSecSum', 0)
                requested = event['current_test']['parameters']['cluster_throughput_mb_per_sec']
                if requested <= 0:
                    return 1.0
                return mb_per_sec_sum / requested
        elif isinstance(condition, (int, float)):
            return float(condition)
        return False
