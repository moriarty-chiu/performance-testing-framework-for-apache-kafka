#!/usr/bin/env python3
"""
Local Kafka Performance Test Runner

This script runs Kafka performance tests locally using the built-in
kafka-producer-perf-test.sh and kafka-consumer-perf-test.sh tools.
"""

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import yaml

from test_parameters import (
    increment_index_and_update_parameters,
    evaluate_skip_condition,
    load_test_specification,
)
from mock_data_generator import MockDataGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class KafkaPerformanceTester:
    """Main class for running Kafka performance tests locally."""

    def __init__(self, config_path: str, debug_mode: bool = False):
        """
        Initialize the tester with configuration.

        Args:
            config_path: Path to configuration YAML file
            debug_mode: If True, generate mock data instead of running real tests
        """
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.kafka_home = Path(self.config['kafka_home']) if not debug_mode else None
        self.bootstrap_servers = self.config.get('bootstrap_servers', 'localhost:9092')
        self.results_dir = Path(self.config.get('results_dir', './results'))
        self.java_heap_opts = self.config.get('java_heap_opts', '-Xms1G -Xmx3584m')
        self.debug_mode = debug_mode

        # Load security configuration
        self.security_config = self.config.get('security', {})
        self.security_props = self._build_security_properties()

        # Mock data generator for debug mode
        if self.debug_mode:
            self.mock_generator = MockDataGenerator(seed=42)  # Fixed seed for reproducibility
            logger.info("DEBUG MODE: Using mock data generator")
        else:
            # Find Kafka binaries
            self.bin_dir = self._find_kafka_bin_dir()

        # Create results directory
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Track running processes
        self.running_processes = []

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _build_security_properties(self) -> Dict[str, str]:
        """Build security properties dictionary from config."""
        props = {}

        security_protocol = self.security_config.get('security_protocol', 'PLAINTEXT')
        if security_protocol != 'PLAINTEXT':
            props['security.protocol'] = security_protocol

        # SASL configuration
        sasl_mechanism = self.security_config.get('sasl_mechanism')
        if sasl_mechanism:
            props['sasl.mechanism'] = sasl_mechanism

        sasl_username = self.security_config.get('sasl_username')
        sasl_password = self.security_config.get('sasl_password')
        if sasl_username and sasl_password:
            # SCRAM JAAS configuration - must be a single line
            jaas_config = (
                f'org.apache.kafka.common.security.scram.ScramLoginModule required '
                f'username="{sasl_username}" password="{sasl_password}";'
            )
            props['sasl.jaas.config'] = jaas_config

        # SSL configuration
        ssl_truststore = self.security_config.get('ssl_truststore_location')
        ssl_truststore_password = self.security_config.get('ssl_truststore_password')
        if ssl_truststore:
            props['ssl.truststore.location'] = ssl_truststore
        if ssl_truststore_password:
            props['ssl.truststore.password'] = ssl_truststore_password

        ssl_keystore = self.security_config.get('ssl_keystore_location')
        ssl_keystore_password = self.security_config.get('ssl_keystore_password')
        if ssl_keystore:
            props['ssl.keystore.location'] = ssl_keystore
        if ssl_keystore_password:
            props['ssl.keystore.password'] = ssl_keystore_password

        # SSL endpoint identification algorithm
        # Important: This must be set even if empty (for internal testing)
        # - Empty string (""): Disable hostname verification (testing/internal networks)
        # - "HTTPS": Enable hostname verification (production)
        ssl_endpoint_algo = self.security_config.get('ssl_endpoint_identification_algorithm')
        if ssl_endpoint_algo is not None:
            # Always set this if present in config, even if empty string
            props['ssl.endpoint.identification.algorithm'] = ssl_endpoint_algo

        return props

    def _create_security_properties_file(self) -> str:
        """
        Create a temporary properties file with security configuration only.
        Used for --producer.config, --consumer.config, --command-config
        
        Returns:
            Path to the temporary properties file
        """
        # Write to temporary file
        fd, path = tempfile.mkstemp(suffix='.properties', prefix='kafka-security-')
        with os.fdopen(fd, 'w') as f:
            for key, value in self.security_props.items():
                f.write(f'{key}={value}\n')
        
        return path

    def _find_kafka_bin_dir(self) -> Path:
        """Find the Kafka bin directory."""
        # Try common locations
        possible_paths = [
            self.kafka_home / 'bin',
            self.kafka_home,
            Path('/opt/kafka/bin'),
            Path('/usr/local/kafka/bin'),
        ]
        
        for path in possible_paths:
            if (path / 'kafka-producer-perf-test.sh').exists():
                return path
            # Try with kafka_*.*/bin pattern
            if self.kafka_home.exists():
                for item in self.kafka_home.glob('kafka_*'):
                    if item.is_dir():
                        bin_path = item / 'bin'
                        if (bin_path / 'kafka-producer-perf-test.sh').exists():
                            return bin_path
        
        raise FileNotFoundError(
            f"Cannot find Kafka binaries in {self.kafka_home}. "
            "Please set kafka_home correctly in config.yaml"
        )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.cleanup()
        sys.exit(1)

    def cleanup(self):
        """Clean up running processes."""
        logger.info("Cleaning up running processes...")
        for proc in self.running_processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

    def run_kafka_command(self, cmd: List[str], env: Optional[Dict] = None) -> Tuple[str, str, int]:
        """
        Run a Kafka command and capture output.
        
        Args:
            cmd: Command to run
            env: Environment variables
            
        Returns:
            Tuple of (stdout, stderr, return_code)
        """
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=full_env
        )
        
        self.running_processes.append(proc)
        
        stdout, stderr = proc.communicate()
        
        self.running_processes.remove(proc)
        
        return stdout, stderr, proc.returncode

    def create_topic(self, topic_name: str, num_partitions: int, 
                    replication_factor: int, extra_configs: Optional[List[str]] = None) -> bool:
        """
        Create a Kafka topic.
        
        Reference: AWS CDK docker/run-kafka-command.sh create-topics

        Args:
            topic_name: Topic name
            num_partitions: Number of partitions
            replication_factor: Replication factor
            extra_configs: Additional topic configurations
            
        Returns:
            True if successful
        """
        # Create security properties file for --command-config
        security_props_file = self._create_security_properties_file()

        cmd = [
            str(self.bin_dir / 'kafka-topics.sh'),
            '--bootstrap-server', self.bootstrap_servers,
            '--create',
            '--topic', topic_name,
            '--partitions', str(num_partitions),
            '--replication-factor', str(replication_factor),
            '--command-config', security_props_file,
        ]

        if extra_configs:
            for config in extra_configs:
                cmd.extend(['--config', config])

        stdout, stderr, returncode = self.run_kafka_command(cmd)

        # Cleanup temporary properties file
        try:
            os.unlink(security_props_file)
        except:
            pass

        if returncode == 0:
            logger.info(f"Topic '{topic_name}' created successfully")
        else:
            logger.error(f"Failed to create topic '{topic_name}': {stderr}")

        return returncode == 0

    def delete_topic(self, topic_name: str) -> bool:
        """
        Delete a Kafka topic.
        
        Reference: AWS CDK docker/run-kafka-command.sh delete-topics

        Args:
            topic_name: Topic name
            
        Returns:
            True if successful
        """
        # Create security properties file for --command-config
        security_props_file = self._create_security_properties_file()

        cmd = [
            str(self.bin_dir / 'kafka-topics.sh'),
            '--bootstrap-server', self.bootstrap_servers,
            '--delete',
            '--topic', topic_name,
            '--command-config', security_props_file,
        ]

        stdout, stderr, returncode = self.run_kafka_command(cmd)

        # Cleanup temporary properties file
        try:
            os.unlink(security_props_file)
        except:
            pass

        if returncode == 0:
            logger.info(f"Topic '{topic_name}' deleted successfully")
        else:
            logger.error(f"Failed to delete topic '{topic_name}': {stderr}")

        return returncode == 0

    def list_topics(self) -> List[str]:
        """List all Kafka topics."""
        # Create security properties file for --command-config
        security_props_file = self._create_security_properties_file()

        cmd = [
            str(self.bin_dir / 'kafka-topics.sh'),
            '--bootstrap-server', self.bootstrap_servers,
            '--list',
            '--command-config', security_props_file,
        ]

        stdout, stderr, returncode = self.run_kafka_command(cmd)

        # Cleanup temporary properties file
        try:
            os.unlink(security_props_file)
        except:
            pass

        if returncode == 0:
            return [line.strip() for line in stdout.split('\n') if line.strip()]
        return []

    def run_producer_perf_test(self, topic: str, num_records: int, throughput: int,
                               record_size: int, producer_props: str,
                               test_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Kafka producer performance test.
        
        Reference: AWS CDK docker/run-kafka-command.sh producer_command()

        Args:
            topic: Topic name
            num_records: Number of records to produce
            throughput: Target throughput (records/sec), -1 for max
            record_size: Record size in bytes
            producer_props: Producer properties string (acks, linger.ms, batch.size, etc.)
            test_params: Test parameters for logging

        Returns:
            Dictionary with test results
        """
        # Create security properties file for --producer.config
        security_props_file = self._create_security_properties_file()

        cmd = [
            str(self.bin_dir / 'kafka-producer-perf-test.sh'),
            '--topic', topic,
            '--num-records', str(num_records),
            '--throughput', str(throughput),
            '--record-size', str(record_size),
            # --producer-props: test-specific properties (acks, linger.ms, batch.size, etc.)
            '--producer-props', f'bootstrap.servers={self.bootstrap_servers}',
        ]

        # Add test-specific producer properties
        for prop in producer_props.split():
            if prop.strip():
                cmd.append(prop)

        # Add --producer.config for security properties
        cmd.extend(['--producer.config', security_props_file])

        env = {
            'KAFKA_HEAP_OPTS': self.java_heap_opts
        }

        logger.info(f"Starting producer test: {num_records} records, "
                   f"throughput={throughput} rec/sec, record_size={record_size} bytes")
        logger.debug(f"Security properties file: {security_props_file}")
        if producer_props:
            logger.debug(f"Test-specific properties (--producer-props): {producer_props}")

        start_time = time.time()
        stdout, stderr, returncode = self.run_kafka_command(cmd, env)
        elapsed_time = time.time() - start_time

        # Cleanup temporary properties file
        try:
            os.unlink(security_props_file)
        except:
            pass

        # Parse output
        result = self._parse_producer_output(stdout, stderr, test_params)
        result['elapsed_time_sec'] = elapsed_time
        result['return_code'] = returncode

        return result

    def run_consumer_perf_test(self, topic: str, num_messages: int,
                               consumer_props: str, consumer_group: str,
                               test_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run Kafka consumer performance test.
        
        Reference: AWS CDK docker/run-kafka-command.sh consumer_command()

        Args:
            topic: Topic name
            num_messages: Number of messages to consume
            consumer_props: Consumer properties string
            consumer_group: Consumer group ID
            test_params: Test parameters for logging

        Returns:
            Dictionary with test results
        """
        # Create security properties file for --consumer.config
        security_props_file = self._create_security_properties_file()

        cmd = [
            str(self.bin_dir / 'kafka-consumer-perf-test.sh'),
            '--topic', topic,
            '--messages', str(num_messages),
            '--broker-list', self.bootstrap_servers,
            '--group', consumer_group,
            '--consumer.config', security_props_file,
            '--print-metrics',
            '--show-detailed-stats',
            '--timeout', '16000'
        ]

        env = {
            'KAFKA_HEAP_OPTS': self.java_heap_opts
        }

        logger.info(f"Starting consumer test: {num_messages} messages, group={consumer_group}")
        logger.debug(f"Security properties file: {security_props_file}")
        if consumer_props:
            logger.debug(f"Test-specific properties: {consumer_props}")

        start_time = time.time()
        stdout, stderr, returncode = self.run_kafka_command(cmd, env)
        elapsed_time = time.time() - start_time

        # Cleanup temporary properties file
        try:
            os.unlink(security_props_file)
        except:
            pass

        # Parse output
        result = self._parse_consumer_output(stdout, stderr, test_params)
        result['elapsed_time_sec'] = elapsed_time
        result['return_code'] = returncode

        return result

    def _parse_producer_output(self, stdout: str, stderr: str, 
                               test_params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse producer test output."""
        result = {
            'test_params': test_params,
            'raw_output': stdout,
            'raw_error': stderr,
        }
        
        # Parse metrics from output
        # Example output:
        # 100000 records sent, 100000.00 records/sec (100.00 MB/sec), 5.0 ms avg latency
        
        output = stdout + stderr
        
        # Extract records sent
        records_match = re.search(r'(\d+)\s+records\s+sent', output)
        if records_match:
            result['records_sent'] = int(records_match.group(1))
        
        # Extract throughput
        throughput_match = re.search(r'([\d.]+)\s+records/sec\s+\(([\d.]+)\s+MB/sec\)', output)
        if throughput_match:
            result['records_per_sec'] = float(throughput_match.group(1))
            result['mbPerSecSum'] = float(throughput_match.group(2))
        
        # Extract latency
        latency_match = re.search(r'([\d.]+)\s+ms\s+avg\s+latency', output)
        if latency_match:
            result['avg_latency_ms'] = float(latency_match.group(1))
        
        # Extract p99 latency if available
        p99_match = re.search(r'([\d.]+)\s+ms\s+p99\s+latency', output)
        if p99_match:
            result['p99_latency_ms'] = float(p99_match.group(1))
        
        # Extract p50 latency if available
        p50_match = re.search(r'([\d.]+)\s+ms\s+p50\s+latency', output)
        if p50_match:
            result['p50_latency_ms'] = float(p50_match.group(1))
        
        return result

    def _parse_consumer_output(self, stdout: str, stderr: str,
                               test_params: Dict[str, Any]) -> Dict[str, Any]:
        """Parse consumer test output."""
        result = {
            'test_params': test_params,
            'raw_output': stdout,
            'raw_error': stderr,
        }
        
        output = stdout + stderr
        
        # Extract data consumed
        data_match = re.search(r'(\d+)\s+bytes\s+consumed', output)
        if data_match:
            result['bytes_consumed'] = int(data_match.group(1))
        
        # Extract throughput
        throughput_match = re.search(r'([\d.]+)\s+MB/sec', output)
        if throughput_match:
            result['mb_per_sec'] = float(throughput_match.group(1))
        
        # Extract fetch rate
        fetch_match = re.search(r'fetch.rate\s*=\s*([\d.]+)', output)
        if fetch_match:
            result['fetch_rate'] = float(fetch_match.group(1))
        
        # Extract fetch latency
        latency_match = re.search(r'fetch.latency\s*avg\s*=\s*([\d.]+)', output)
        if latency_match:
            result['avg_fetch_latency_ms'] = float(latency_match.group(1))
        
        return result

    def save_results(self, results: Dict[str, Any], test_id: str, 
                    result_type: str) -> str:
        """
        Save test results to file.
        
        Args:
            results: Test results dictionary
            test_id: Test ID
            result_type: Type of result ('producer' or 'consumer')
            
        Returns:
            Path to saved results file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{test_id}_{result_type}_{timestamp}.json"
        filepath = self.results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Results saved to {filepath}")
        return str(filepath)

    def run_test(self, test_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single performance test.
        
        Args:
            test_params: Test parameters dictionary
            
        Returns:
            Combined test results
        """
        topic = test_params['topic_name']
        num_partitions = test_params['num_partitions']
        replication_factor = test_params['replication_factor']
        num_producers = test_params['num_producers']
        consumer_groups_config = test_params['consumer_groups']
        client_props = test_params['client_props']
        record_size = test_params['record_size_byte']
        duration_sec = test_params['duration_sec']
        cluster_throughput_mb = test_params['cluster_throughput_mb_per_sec']
        
        results = {
            'test_params': test_params,
            'producer_results': [],
            'consumer_results': []
        }
        
        # Debug mode: generate mock data
        if self.debug_mode:
            logger.info(f"[DEBUG] Generating mock data for topic: {topic}")
            results = self.mock_generator.generate_test_results(test_params)
            
            # Save combined results
            self.save_results(results, test_params['test_id'], 'combined')
            
            return results
        
        try:
            # Create topic
            logger.info(f"Creating topic: {topic}")
            self.create_topic(topic, num_partitions, replication_factor)
            
            # Run producer tests
            if cluster_throughput_mb > 0:
                throughput_per_producer = int(
                    cluster_throughput_mb * 1024 * 1024 / num_producers / record_size
                )
            else:
                throughput_per_producer = -1  # Max throughput
            
            num_records_per_producer = test_params['num_records_producer']
            
            logger.info(f"Running {num_producers} producer(s)...")
            for i in range(num_producers):
                producer_result = self.run_producer_perf_test(
                    topic=topic,
                    num_records=num_records_per_producer,
                    throughput=throughput_per_producer,
                    record_size=record_size,
                    producer_props=client_props['producer'],
                    test_params={**test_params, 'producer_id': i}
                )
                results['producer_results'].append(producer_result)
                
                # Save individual producer results
                self.save_results(producer_result, test_params['test_id'], 'producer')
            
            # Run consumer tests if configured
            if consumer_groups_config['num_groups'] > 0:
                num_consumers_per_group = consumer_groups_config['size']
                num_consumer_jobs = consumer_groups_config['num_groups'] * num_consumers_per_group
                
                if cluster_throughput_mb > 0:
                    throughput_per_consumer = int(
                        cluster_throughput_mb * 1024 * 1024 / num_consumer_jobs / record_size
                    )
                else:
                    throughput_per_consumer = -1
                
                num_records_per_consumer = test_params['num_records_consumer']
                
                logger.info(f"Running {num_consumer_jobs} consumer(s) in "
                           f"{consumer_groups_config['num_groups']} group(s)...")
                
                for group_idx in range(consumer_groups_config['num_groups']):
                    for consumer_idx in range(num_consumers_per_group):
                        consumer_group = f"test-group-{test_params['test_id']}-{group_idx}"
                        
                        consumer_result = self.run_consumer_perf_test(
                            topic=topic,
                            num_messages=num_records_per_consumer,
                            consumer_props=client_props.get('consumer', ''),
                            consumer_group=consumer_group,
                            test_params={
                                **test_params,
                                'consumer_group_id': group_idx,
                                'consumer_id': consumer_idx
                            }
                        )
                        results['consumer_results'].append(consumer_result)
                        
                        # Save individual consumer results
                        self.save_results(consumer_result, test_params['test_id'], 'consumer')
            
            # Delete topic after test
            logger.info(f"Deleting topic: {topic}")
            self.delete_topic(topic)
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
            results['error'] = str(e)
            # Try to cleanup topic
            try:
                self.delete_topic(topic)
            except:
                pass
        
        # Save combined results
        self.save_results(results, test_params['test_id'], 'combined')
        
        return results

    def run_test_suite(self, spec_path: str) -> List[Dict[str, Any]]:
        """
        Run a complete test suite from specification.

        Args:
            spec_path: Path to test specification JSON file

        Returns:
            List of all test results
        """
        logger.info(f"Loading test specification from {spec_path}")
        event = load_test_specification(spec_path)

        all_results = []
        test_count = 0
        max_tests = 1000  # Safety limit

        while test_count < max_tests:
            # Increment to next test configuration
            event = increment_index_and_update_parameters(event)

            if event.get('all_tests_completed', False):
                logger.info("All tests completed!")
                break

            test_params = event['current_test']['parameters']
            test_count += 1

            logger.info(f"\n{'='*60}")
            logger.info(f"Running test {test_count}")
            logger.info(f"Topic: {test_params['topic_name']}")
            logger.info(f"Throughput: {test_params['cluster_throughput_mb_per_sec']} MB/sec")
            logger.info(f"Producers: {test_params['num_producers']}")
            logger.info(f"Consumer groups: {test_params['consumer_groups']}")
            logger.info(f"{'='*60}\n")

            # Run the test
            results = self.run_test(test_params)
            all_results.append(results)

            # Check skip condition AFTER running the test
            if 'skip_remaining_throughput' in event.get('test_specification', {}):
                # Set producer result for skip condition evaluation
                event['producer_result'] = results['producer_results'][0] if results['producer_results'] else {}

                skip_condition = event['test_specification']['skip_remaining_throughput']
                if evaluate_skip_condition(skip_condition, event):
                    logger.info(f"Skip condition met (sent/requested = {event['producer_result'].get('mbPerSecSum', 0) / test_params['cluster_throughput_mb_per_sec']:.3f}), skipping remaining throughput values")

        return all_results


def main():
    parser = argparse.ArgumentParser(
        description='Run Kafka performance tests locally'
    )
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Path to configuration YAML file (default: config.yaml)'
    )
    parser.add_argument(
        '--spec', '-s',
        required=True,
        help='Path to test specification JSON file'
    )
    parser.add_argument(
        '--test-name', '-n',
        default=None,
        help='Test run name (used for organizing results in subdirectories). If not specified, uses spec filename without extension.'
    )
    parser.add_argument(
        '--output-dir', '-o',
        default=None,
        help='Base output directory for results (default: ./results)'
    )
    parser.add_argument(
        '--topic', '-t',
        help='Run a single test with specified topic (overrides spec)'
    )
    parser.add_argument(
        '--cleanup',
        action='store_true',
        help='Cleanup mode: delete topics matching pattern'
    )
    parser.add_argument(
        '--topic-pattern',
        default='test-id-*',
        help='Topic pattern for cleanup (default: test-id-*)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Debug mode: generate mock data instead of running real tests (no Kafka connection required)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Determine test name from spec filename if not provided
    if args.test_name is None:
        args.test_name = Path(args.spec).stem
    
    # Determine output directory
    if args.output_dir is None:
        args.output_dir = Path('./results')
    else:
        args.output_dir = Path(args.output_dir)
    
    # Create test-specific output directory
    args.results_dir = args.output_dir / args.test_name
    args.results_dir.mkdir(parents=True, exist_ok=True)
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Update config with test-specific results directory
    if os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
        config['results_dir'] = str(args.results_dir)
        
        # Write updated config to temp file
        import tempfile
        temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(config, temp_config)
        temp_config_path = temp_config.name
        temp_config.close()
    else:
        # Create minimal config
        temp_config_path = None
    
    tester = KafkaPerformanceTester(temp_config_path if temp_config_path else args.config, debug_mode=args.debug)
    
    try:
        if args.cleanup:
            # Cleanup mode
            if args.debug:
                logger.info("[DEBUG] Cleanup skipped in debug mode")
            else:
                topics = tester.list_topics()
                pattern = args.topic_pattern.replace('*', '.*')
                for topic in topics:
                    if re.match(pattern, topic):
                        tester.delete_topic(topic)
                logger.info("Cleanup completed")
        else:
            # Run tests
            results = tester.run_test_suite(args.spec)
            logger.info(f"\nCompleted {len(results)} tests")
            logger.info(f"Results saved to: {args.results_dir.absolute()}")
            
            # Print summary
            for i, result in enumerate(results):
                if 'error' not in result and not result.get('mock_data', False):
                    producer_results = result.get('producer_results', [])
                    if producer_results:
                        avg_throughput = sum(
                            r.get('mbPerSecSum', 0) for r in producer_results
                        ) / len(producer_results)
                        logger.info(f"Test {i+1}: Avg throughput = {avg_throughput:.2f} MB/sec")
                elif result.get('mock_data', False):
                    # Print mock data summary
                    producer_results = result.get('producer_results', [])
                    if producer_results:
                        avg_throughput = sum(
                            r.get('mbPerSecSum', 0) for r in producer_results
                        ) / len(producer_results)
                        logger.info(f"[MOCK] Test {i+1}: Avg throughput = {avg_throughput:.2f} MB/sec")
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)
    finally:
        tester.cleanup()
        # Clean up temp config file
        if temp_config_path and os.path.exists(temp_config_path):
            os.unlink(temp_config_path)


if __name__ == '__main__':
    main()
