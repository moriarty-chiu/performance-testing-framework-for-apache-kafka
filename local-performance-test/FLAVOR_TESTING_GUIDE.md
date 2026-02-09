# Cluster Flavor Performance Testing Guide

## 🎯 Test Suite Overview

This directory contains performance tests designed to find the limits of different Kafka cluster configurations (flavors).

## 📋 Available Test Configurations

### 1. **Small Cluster** (`test-spec-small.json`)
- **Target**: Entry-level or development clusters
- **Configuration**: 
  - 3 producers, 12 partitions
  - Single replica (no replication)
  - Lightweight client settings
- **Expected Range**: 5-50 MB/sec
- **Use Case**: Baseline performance, cost optimization

### 2. **Medium Cluster** (`test-spec-medium.json`)
- **Target**: Standard production workloads
- **Configuration**:
  - 6 producers, 24 partitions  
  - 2 replicas for fault tolerance
  - Balanced reliability vs performance
- **Expected Range**: 10-120 MB/sec
- **Use Case**: Typical production environments

### 3. **Large Cluster** (`test-spec-large.json`)
- **Target**: High-throughput production systems
- **Configuration**:
  - 12 producers, 48 partitions
  - 3 replicas for high availability
  - Multiple client configurations tested
- **Expected Range**: 20-300 MB/sec
- **Use Case**: Enterprise-scale applications

### 4. **XLarge Cluster** (`test-spec-xlarge.json`)
- **Target**: Maximum capacity testing
- **Configuration**:
  - 18 producers, 72 partitions
  - 3 replicas with aggressive settings
  - Multiple ACK configurations tested
- **Expected Range**: 50-600+ MB/sec
- **Use Case**: Capacity planning,极限性能测试

## 🚀 Running the Tests

### Quick Start
```bash
# Run all flavor tests automatically
./scripts/run-flavor-tests.sh

# Or run individual flavor tests
./scripts/run-tests.sh  # Uses current test-spec.json
```

### Manual Configuration
1. Select appropriate test spec:
   ```bash
   cp config/test-spec-medium.json config/test-spec.json
   ```
2. Update Kafka connection in `config/kafka.properties`
3. Run the test suite

## 📊 What You'll Get

### Individual Results (per flavor)
- Raw test logs in `results/{flavor}/`
- Processed JSON results
- Individual performance charts

### Comparative Analysis
- **Throughput comparison** across all flavors
- **Scaling efficiency** analysis
- **Performance limit summary**
- **Configuration recommendations**

## 🔍 Key Metrics Tracked

### Performance Indicators
- **Maximum sustainable throughput** (MB/sec)
- **Latency percentiles** (P50, P99)
- **Scaling efficiency** ratios
- **Resource utilization** patterns

### Quality Factors
- **Reliability settings impact** (acks=1 vs acks=all)
- **Batch size optimization** effects
- **Partition count scaling** behavior
- **Consumer group overhead**

## 📈 Expected Outcomes

### Performance Scaling Patterns
- **Linear scaling**: Each flavor roughly 2x the previous
- **Diminishing returns**: Larger clusters may not scale perfectly
- **Configuration sweet spots**: Optimal settings per cluster size

### Practical Insights
- **Cost/performance optimization points**
- **Reliability vs throughput trade-offs**
- **Resource bottlenecks identification**
- **Capacity planning guidelines**

## ⚙️ Customization Tips

### Adjust for Your Environment
- Modify throughput ranges based on your hardware
- Adjust producer/consumer counts for your cluster size
- Tune partition counts for your use case
- Update duration based on your testing window

### Advanced Testing
- Add more client configurations to test
- Include different message sizes
- Test various replication factors
- Add network latency scenarios

## 📝 Result Interpretation

The comparative analysis will help you:
1. **Identify your cluster's performance tier**
2. **Understand scaling characteristics**
3. **Optimize configuration for your workload**
4. **Plan capacity for future growth**

Check the generated charts and summary JSON for detailed insights into each cluster flavor's performance limits.

run-flavor-tests.sh:
  1. Copy test-spec-small.json -> test-spec.json
  2. Run run-tests-binary.sh
     -> run-tests-binary.sh reads test-spec.json
     -> run-tests-binary.sh calls run_all_tests_from_config()
     -> run_all_tests_from_config() parses test-spec.json
     -> run_all_tests_from_config() loops through all test combinations
     -> For each combination: run_test(throughput, consumer_groups, test_id)
  3. Results saved to results/small/
  4. Repeat for medium, large, xlarge configs