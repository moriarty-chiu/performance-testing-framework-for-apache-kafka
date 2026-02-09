# Kafka Performance Test Specification Parameters Guide

## Overview

This document provides a detailed explanation of each parameter in the `test-spec.json` file and how they influence the performance testing process and results.

## Parameter Breakdown

### `cluster_throughput_mb_per_sec`

**Purpose**: Defines the target throughput values (in MB/s) that the test will attempt to achieve.

**Usage in Script**: 
- Used to calculate the number of records per second: `records_per_sec = throughput * 1024 * 1024 / record_size`
- Each test iteration will attempt to push this amount of data through the Kafka cluster
- The script iterates through all values in the array sequentially

**Performance Impact**:
- **Low values (5-30 MB/s)**: Tests baseline performance under light load
- **Medium values (30-100 MB/s)**: Evaluates typical production workloads
- **High values (100+ MB/s)**: Stresses the cluster to identify bottlenecks and maximum capacity
- Increasing values help identify the performance ceiling of the cluster

### `num_producers`

**Purpose**: Specifies the number of concurrent producer instances to run during each test.

**Usage in Script**:
- Controls the number of producer processes launched: `for ((i=0; i<num_producers; i++))`
- Affects the total number of processes: `num_jobs = num_producers + consumer_groups * 6`
- Influences the distribution of workload across multiple threads

**Performance Impact**:
- **Few producers (1-3)**: Lower parallelism, may underutilize cluster resources
- **Moderate producers (4-8)**: Balanced approach for most cluster sizes
- **Many producers (9+)**: High parallelism, maximizes cluster utilization but increases resource consumption
- More producers can achieve higher aggregate throughput but require more system resources

### `consumer_groups`

**Purpose**: Defines the consumer group configurations to test different consumption patterns.

**Usage in Script**:
- Creates multiple consumer groups based on the configuration: `{ "num_groups": X, "size": Y }`
- Each group has Y consumers, and X groups are created
- Total consumer processes = `consumer_groups * size`

**Performance Impact**:
- **No consumers (num_groups: 0)**: Tests pure producer performance
- **Single consumer group**: Evaluates producer-consumer balance
- **Multiple consumer groups**: Tests complex consumption scenarios with competing consumers
- Consumers add additional load to the cluster and compete with producers for resources

### `client_props`

**Purpose**: Configures Kafka client properties for both producers and consumers.

**Usage in Script**:
- Producer properties are applied to `kafka-producer-perf-test.sh` with `--producer-props`
- Consumer properties are applied to `kafka-consumer-perf-test.sh` with `--consumer-props`
- Properties are parsed and converted to command-line arguments

**Performance Impact**:

#### Producer Properties:
- **`acks`**: Controls durability vs performance
  - `acks=0`: Fastest, no durability guarantee
  - `acks=1`: Balanced, leader acknowledgment
  - `acks=all`: Slowest, highest durability but guaranteed persistence
- **`linger.ms`**: Controls batching behavior
  - `0`: Immediate sends, higher per-message overhead
  - `5-50`: Allows batching, better throughput at slight latency cost
- **`batch.size`**: Size of message batches
  - Larger: Better throughput, higher memory usage
  - Smaller: Lower latency, less memory usage
- **`buffer.memory`**: Memory allocated for buffering
  - Higher: More buffering capability, higher throughput
  - Lower: Less memory usage, potential backpressure
- **`compression.type`**: Affects CPU usage and network efficiency
  - `none`: Fastest, largest network payload
  - `snappy`: Good balance of speed and compression
  - `gzip`: Higher compression, more CPU usage

#### Consumer Properties:
- **`fetch.min.bytes`**: Minimum bytes to accumulate before returning
  - Higher: Better throughput, higher latency
  - Lower: Lower latency, potentially lower throughput
- **`fetch.max.wait.ms`**: Max time to wait for minimum bytes
  - Higher: Better batching, higher latency
  - Lower: Lower latency, potentially lower throughput
- **`max.partition.fetch.bytes`**: Max bytes to fetch per partition
  - Higher: Better throughput, higher memory usage
  - Lower: Lower memory usage, potentially lower throughput

### `num_partitions`

**Purpose**: Specifies the number of partitions for test topics.

**Usage in Script**:
- Passed to `kafka-topics.sh` during topic creation: `--partitions $num_partitions`
- Affects parallelism within the topic

**Performance Impact**:
- **Few partitions (1-12)**: Lower parallelism, simpler management
- **Moderate partitions (12-48)**: Good balance of parallelism and overhead
- **Many partitions (48+)**: Higher parallelism but more coordination overhead
- More partitions allow for greater producer/consumer parallelism but increase Zookeeper coordination overhead

### `replication_factor`

**Purpose**: Sets the replication factor for test topics.

**Usage in Script**:
- Passed to `kafka-topics.sh` during topic creation: `--replication-factor $replication_factor`
- Determines how many copies of each partition exist across brokers

**Performance Impact**:
- **Factor 1**: No replication, fastest but no fault tolerance
- **Factor 2**: Single backup, moderate performance impact
- **Factor 3**: Two backups, highest durability but more network traffic
- Higher replication factors increase durability but also network overhead and storage requirements

### `record_size_byte`

**Purpose**: Defines the size of each message in bytes.

**Usage in Script**:
- Passed to performance tools: `--record-size $record_size`
- Affects the calculation of records per second from target throughput

**Performance Impact**:
- **Small records (100-500 bytes)**: Higher message rates, more per-message overhead
- **Medium records (500-2000 bytes)**: Balanced approach
- **Large records (2000+ bytes)**: Lower message rates, less per-message overhead
- Larger records generally achieve higher throughput in MB/s but lower message rates

### `duration_sec`

**Purpose**: Specifies the duration of each individual test in seconds.

**Usage in Script**:
- Controls how long each producer runs: `--num-records $((records_per_sec * duration_sec))`
- Sets consumer timeout: `--timeout $((duration_sec * 1000 + 10000))`

**Performance Impact**:
- **Short tests (60-180s)**: Quick validation, may not reach steady state
- **Medium tests (180-300s)**: Reasonable for most performance evaluations
- **Long tests (300s+)**: More accurate results, captures steady-state performance
- Longer tests provide more statistically significant results but take more time

## Conditional Parameters

### `skip_remaining_throughput`

**Purpose**: Defines conditions to skip higher throughput tests when the cluster is saturated.

**Usage in Script**:
- Monitors the ratio of actual vs requested throughput
- If the condition is met, skips remaining higher throughput values
- Helps prevent overloading the cluster unnecessarily

**Performance Impact**:
- **Lower threshold (0.90-0.95)**: More aggressive testing, may stress cluster beyond capacity
- **Higher threshold (0.97-0.99)**: Conservative approach, stops testing when cluster nears saturation
- Prevents waste of time on tests that are unlikely to succeed

## Parameter Interactions

### Throughput vs Producers
- More producers can achieve higher aggregate throughput
- Diminishing returns occur when producers exceed cluster capacity
- Optimal producer count depends on cluster resources and configuration

### Partitions vs Producers/Consumers
- More partitions allow for more concurrent producers/consumers
- Should generally scale with the number of producers and consumers
- Too few partitions can create bottlenecks; too many create overhead

### Record Size vs Throughput
- Larger records achieve higher MB/s with fewer messages
- Smaller records achieve higher message rates but lower MB/s
- Network and storage efficiency varies with record size

### Replication vs Performance
- Higher replication factors reduce write performance due to network overhead
- Provides fault tolerance at the cost of performance
- Trade-off between durability and throughput

## Best Practices for Parameter Selection

### For Capacity Planning
- Use realistic values based on expected production workloads
- Test with multiple parameter combinations to understand trade-offs
- Consider peak load scenarios with higher throughput values

### For Optimization
- Start with baseline configurations and adjust one parameter at a time
- Monitor resource utilization (CPU, memory, network) during tests
- Use the results to tune Kafka broker and client configurations

### For Stability Testing
- Include longer duration tests to identify memory leaks or resource exhaustion
- Test with various consumer configurations to simulate real usage patterns
- Use conservative skip thresholds to ensure thorough testing

This comprehensive parameter guide helps understand how each configuration option influences the performance testing process and results, enabling better planning and interpretation of Kafka performance tests.