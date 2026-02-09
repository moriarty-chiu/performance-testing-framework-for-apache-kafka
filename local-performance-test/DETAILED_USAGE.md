# Local Kafka Performance Testing Framework - Detailed Guide

## Table of Contents
- [Overview](#overview)
- [Scripts Description](#scripts-description)
- [How to Use](#how-to-use)
- [Parameter Specifications](#parameter-specifications)
- [How Parameters Affect Testing](#how-parameters-affect-testing)
- [Best Practices](#best-practices)

## Overview

This directory contains a comprehensive performance testing framework for Apache Kafka that runs on local or self-deployed Kafka clusters. It leverages local Kafka binaries instead of AWS services to provide a flexible and accessible performance evaluation tool.

## Scripts Description

### Main Execution Scripts

#### `run-tests-binary.sh`
- **Purpose**: Executes performance tests using locally installed Kafka binaries
- **Features**:
  - Creates topics with specified configurations
  - Launches multiple producer and consumer instances
  - Collects performance metrics
  - Cleans up resources after tests
  - Validates system resources before running tests

#### `run-flavor-tests.sh`
- **Purpose**: Orchestrates testing across different cluster flavors (small, medium, large, xlarge)
- **Features**:
  - Runs tests for all predefined cluster configurations
  - Manages configuration switching between flavors
  - Aggregates results across different flavors
  - Generates comparative analysis

### Result Processing Scripts

#### `process-results-binary.py`
- **Purpose**: Parses and aggregates raw test results from Kafka performance tools
- **Features**:
  - Extracts metrics from producer and consumer logs
  - Calculates aggregate statistics
  - Handles various Kafka output formats
  - Generates JSON output for visualization

#### `generate-charts.py`
- **Purpose**: Creates visualizations from processed test results
- **Features**:
  - Generates throughput vs latency charts
  - Creates efficiency metrics visualizations
  - Produces summary statistics

#### `generate-comparison-charts.py`
- **Purpose**: Creates comparative analysis across different cluster flavors
- **Features**:
  - Compares performance across cluster sizes
  - Identifies optimal configurations
  - Highlights performance differences

## How to Use

### Prerequisites
1. Apache Kafka 2.8.0 or later installed locally
2. Python 3.6+ with matplotlib and numpy packages
3. Access to a Kafka cluster (can be local or remote)

### Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Kafka Environment**
   ```bash
   export KAFKA_HOME=/path/to/your/kafka/installation
   ```

3. **Configure Kafka Connection**
   Edit `config/kafka.properties`:
   ```properties
   bootstrap.servers=localhost:9092
   # Add authentication settings if needed
   ```

4. **Run Single Test**
   ```bash
   ./scripts/run-tests-binary.sh
   ```

5. **Run All Flavor Tests** (Recommended)
   ```bash
   ./scripts/run-flavor-tests.sh
   ```

6. **Process Results**
   ```bash
   python scripts/process-results-binary.py
   ```

7. **Generate Charts**
   ```bash
   python scripts/generate-charts.py
   ```

### Advanced Usage

#### Custom Test Configuration
1. Modify `config/test-spec.json` to customize test parameters
2. Or create a new configuration file and copy it to `test-spec.json`

#### Specific Flavor Testing
Run tests for a specific flavor only:
```bash
# Backup current config
cp config/test-spec.json config/test-spec.json.backup

# Copy specific flavor config
cp config/test-spec-medium.json config/test-spec.json

# Run tests
./scripts/run-tests-binary.sh

# Restore original config
mv config/test-spec.json.backup config/test-spec.json
```

## Parameter Specifications

### Core Test Parameters

#### `cluster_throughput_mb_per_sec`
- **Type**: Array of integers
- **Description**: Target throughput values to test in MB/sec
- **Example**: `[10, 20, 30, 40, 50]`
- **Default Range**: Varies by flavor (5-600 MB/sec)

#### `num_producers`
- **Type**: Array of integers  
- **Description**: Number of concurrent producer instances to run
- **Example**: `[3, 6, 12]`
- **Default Values**: Varies by flavor (3-18)

#### `consumer_groups`
- **Type**: Array of objects
- **Description**: Configuration for consumer groups
- **Structure**: `{ "num_groups": integer, "size": integer }`
- **Example**: 
  ```json
  [
    { "num_groups": 0, "size": 3 },
    { "num_groups": 1, "size": 3 },
    { "num_groups": 2, "size": 3 }
  ]
  ```

#### `client_props`
- **Type**: Array of objects
- **Description**: Kafka client configuration properties for both producers and consumers
- **Structure**: `{ "producer": string, "consumer": string }`
- **Example**:
  ```json
  [
    {
      "producer": "acks=all linger.ms=5 batch.size=65536 buffer.memory=1073741824",
      "consumer": "fetch.min.bytes=1024 fetch.max.wait.ms=500"
    }
  ]
  ```
- **Producer Properties**:
  - `acks`: Acknowledgment settings (0, 1, all)
  - `linger.ms`: Time to wait for batching (0-50ms typical)
  - `batch.size`: Size of message batches (typically 32KB-128KB)
  - `buffer.memory`: Memory allocated for buffering (typically 1-8GB)
  - `compression.type`: Compression algorithm (none, gzip, snappy, lz4, zstd)
- **Consumer Properties**:
  - `fetch.min.bytes`: Minimum bytes to fetch (1-1024)
  - `fetch.max.wait.ms`: Max time to wait for fetch (50-500ms)
  - `max.partition.fetch.bytes`: Max bytes per partition fetch (1MB typical)
  - `session.timeout.ms`: Session timeout (10000ms typical)
  - `heartbeat.interval.ms`: Heartbeat interval (3000ms typical)

### Infrastructure Parameters

#### `num_partitions`
- **Type**: Array of integers
- **Description**: Number of partitions for test topics
- **Example**: `[12, 24, 48]`
- **Default Values**: Varies by flavor (12-72)

#### `replication_factor`
- **Type**: Array of integers
- **Description**: Replication factor for test topics
- **Example**: `[1, 2, 3]`
- **Default Values**: Varies by flavor (1-3)

#### `record_size_byte`
- **Type**: Array of integers
- **Description**: Size of each message in bytes
- **Example**: `[512, 1024, 2048]`
- **Default Value**: `1024`

#### `duration_sec`
- **Type**: Array of integers
- **Description**: Duration of each test in seconds
- **Example**: `[120, 300, 600]`
- **Default Values**: Varies by flavor (120-600)

### Control Parameters

#### `skip_remaining_throughput`
- **Type**: Object
- **Description**: Condition to skip higher throughput tests when cluster is saturated
- **Example**:
  ```json
  {
    "less-than": [ "sent_div_requested_mb_per_sec", 0.95 ]
  }
  ```
- **Default**: Varies by flavor (0.95-0.99)

## How Parameters Affect Testing

### Throughput Impact (`cluster_throughput_mb_per_sec`)

**Effect**: Determines the load applied to the Kafka cluster
- **Low values** (5-30 MB/sec): Tests baseline performance, minimal resource pressure
- **Medium values** (30-100 MB/sec): Tests typical production loads
- **High values** (100+ MB/sec): Tests maximum capacity and identifies bottlenecks

**Recommendation**: Start with lower values and gradually increase to find the performance ceiling

### Producer Count Impact (`num_producers`)

**Effect**: Controls parallelism and resource utilization
- **Few producers** (1-3): Lower parallelism, may not fully utilize cluster
- **Moderate producers** (4-8): Balanced approach for most clusters
- **Many producers** (9+): High parallelism, maximum cluster utilization

**Trade-offs**:
- More producers = Higher throughput potential but increased resource usage
- Fewer producers = Lower resource usage but potentially underutilized cluster

### Consumer Configuration Impact (`consumer_groups`)

**Effect**: Simulates real-world consumption patterns
- **No consumers** (num_groups: 0): Tests pure producer performance
- **Single consumer group**: Tests producer-consumer balance
- **Multiple consumer groups**: Tests complex consumption scenarios

**Performance Implications**:
- Consumers compete for resources with producers
- Multiple consumer groups increase cluster load
- Helps identify consumption bottlenecks

### Client Properties Impact (`client_props`)

#### Producer Properties:
- **`acks`**: Controls durability vs performance trade-off
  - `acks=0`: Fastest, no durability guarantee
  - `acks=1`: Balanced, leader acknowledgment
  - `acks=all`: Slowest, highest durability
- **`linger.ms`**: Controls batching behavior
  - `0`: Immediate sends, higher latency
  - `5-10`: Good batching, lower latency
- **`batch.size`**: Controls message batching
  - Larger batches: Better throughput, higher memory usage
  - Smaller batches: Lower latency, less memory usage
- **`buffer.memory`**: Controls memory allocation
  - Higher values: More buffering, higher throughput
  - Lower values: Less memory usage, potential backpressure
- **`compression.type`**: Affects throughput and CPU usage
  - `none`: No compression, fastest
  - `snappy`: Good balance of speed and compression
  - `gzip`: Higher compression, more CPU usage

#### Consumer Properties:
- **`fetch.min.bytes`**: Minimum bytes to accumulate before returning
  - Higher values: Better throughput, higher latency
  - Lower values: Lower latency, potentially lower throughput
- **`fetch.max.wait.ms`**: Max time to wait for minimum bytes
  - Higher values: Better batching, higher latency
  - Lower values: Lower latency, potentially lower throughput
- **`max.partition.fetch.bytes`**: Max bytes to fetch per partition
  - Higher values: Better throughput, higher memory usage
  - Lower values: Lower memory usage, potentially lower throughput
- **`session.timeout.ms`**: Time before consumer marked dead
  - Affects rebalancing frequency and fault detection
- **`heartbeat.interval.ms`**: Frequency of heartbeats to coordinator
  - Affects responsiveness to rebalancing

### Infrastructure Parameters Impact

#### Topic Configuration:
- **Partitions**: Higher = More parallelism, but more overhead
- **Replication Factor**: Higher = More durability, more network traffic
- **Record Size**: Larger = More data per message, different performance characteristics

#### Test Duration:
- **Short tests** (120s): Quick validation, may not reach steady state
- **Long tests** (600s+): More accurate results, captures steady-state performance

## Best Practices

### Resource Planning
1. **Memory Requirements**: Estimate ~256MB per producer thread plus buffer.memory settings
2. **CPU Cores**: Plan for 2-4 processes per CPU core
3. **Network Bandwidth**: Ensure sufficient bandwidth for target throughput

### Configuration Strategy
1. **Start Small**: Begin with small cluster configurations to validate setup
2. **Gradual Scaling**: Increase parameters incrementally to find limits
3. **Monitor Resources**: Watch system resources during tests

### Test Execution
1. **Isolated Environment**: Run tests on dedicated clusters
2. **Consistent Hardware**: Use consistent hardware for comparable results
3. **Baseline Measurements**: Establish baselines before making changes

### Result Interpretation
1. **Statistical Significance**: Run multiple iterations for reliable results
2. **Compare Like with Like**: Only compare tests with similar configurations
3. **Consider Context**: Account for hardware and network conditions

### Troubleshooting
1. **Insufficient Memory**: Reduce num_producers or buffer.memory
2. **Timeout Errors**: Increase duration or reduce throughput
3. **Connection Issues**: Verify Kafka cluster connectivity and configuration

This framework provides comprehensive tools for evaluating Kafka performance across different configurations and workloads. Proper parameter selection and interpretation of results will help optimize your Kafka deployment for specific use cases.