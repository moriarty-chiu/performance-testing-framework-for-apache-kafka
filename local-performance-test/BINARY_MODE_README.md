# Binary-Based Kafka Performance Testing

## 🎯 Overview

This version of the performance testing framework uses locally installed Kafka binary tools instead of Docker containers, making it suitable for environments where Docker is not available.

## 📋 Prerequisites

### Kafka Installation
- Kafka 2.8.0 or later installed locally
- Kafka binaries available in `$KAFKA_HOME/bin/`
- Required tools: `kafka-topics.sh`, `kafka-producer-perf-test.sh`, `kafka-consumer-perf-test.sh`

### Environment Setup
```bash
# Set Kafka home directory
export KAFKA_HOME=/path/to/your/kafka/installation

# Or modify the KAFKA_HOME variable in run-tests-binary.sh
```

## 🚀 Usage

### Quick Start
```bash
# Run performance tests using binary tools for current config
./scripts/run-tests-binary.sh

# Process results
python ./scripts/process-results-binary.py

# Generate charts
python ./scripts/generate-charts.py
```

### Run All Flavors (Recommended)
```bash
# Run performance tests for ALL cluster flavors automatically
./scripts/run-flavor-tests.sh

# This will test:
# - Small cluster (test-spec-small.json)
# - Medium cluster (test-spec-medium.json) 
# - Large cluster (test-spec-large.json)
# - XLarge cluster (test-spec-xlarge.json)
```

### Configuration
1. Update `config/kafka.properties` with your Kafka cluster connection details
2. Modify `config/test-spec.json` for your test parameters
3. Adjust `KAFKA_HOME` in `run-tests-binary.sh` if needed

## 📁 Directory Structure

```
local-performance-test/
├── config/
│   ├── kafka.properties          # Kafka connection settings
│   └── test-spec.json           # Test parameters
├── scripts/
│   ├── run-tests-binary.sh      # Main test runner (binary mode)
│   ├── process-results-binary.py # Result processor for binary output
│   └── generate-charts.py       # Visualization
└── results/                     # Test output and processed results
```

## 🔧 Key Differences from Docker Version

### Advantages
- **No Docker dependency** - runs directly on your system
- **Faster execution** - no container overhead
- **Better resource utilization** - direct access to system resources
- **Easier debugging** - direct access to Kafka tools

### Considerations
- Requires Kafka installation on test machine
- Uses system resources directly
- May need JVM tuning for optimal performance

## ⚙️ Configuration Options

### Kafka Properties (`config/kafka.properties`)
```properties
# Basic connection
bootstrap.servers=localhost:9092

# Authentication (if needed)
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-256
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="user" password="password";

# SSL configuration (if needed)
ssl.truststore.location=/path/to/truststore.jks
ssl.truststore.password=changeit
```

### Test Specification (`config/test-spec.json`)
The same test specification format is used, but processed differently by the binary runner.

## 📊 Output Format

### Raw Logs
- Producer logs: `results/test-{id}-producer-{num}.log`
- Consumer logs: `results/test-{id}-consumer-{group}-{num}.log`

### Processed Results
- JSON format with aggregated metrics
- Throughput, latency, and efficiency measurements
- Ready for visualization

## 🛠️ Troubleshooting

### Common Issues

1. **Kafka tools not found**
   ```bash
   # Check Kafka installation
   ls $KAFKA_HOME/bin/kafka-*.sh
   
   # Set correct KAFKA_HOME
   export KAFKA_HOME=/correct/path/to/kafka
   ```

2. **Connection issues**
   ```bash
   # Test Kafka connectivity
   $KAFKA_HOME/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
   ```

3. **Permission issues**
   ```bash
   # Make scripts executable
   chmod +x ./scripts/*.sh
   ```

### Performance Tuning

1. **JVM Settings**
   ```bash
   # Set in run-tests-binary.sh
   export KAFKA_HEAP_OPTS="-Xms2G -Xmx4G"
   ```

2. **System Resources**
   - Ensure adequate memory for Kafka processes
   - Monitor CPU and disk I/O during tests
   - Consider network bandwidth limitations

## 📈 Expected Performance

The binary version typically shows:
- **10-20% better performance** than Docker version
- **Lower latency** due to reduced overhead
- **More consistent results** with direct resource access

## 🔄 Migration from Docker Version

If you're migrating from the Docker version:
1. Install Kafka locally
2. Update `KAFKA_HOME` in the scripts
3. Use the same configuration files
4. Run `run-tests-binary.sh` instead of `run-tests.sh`

The result processing and visualization scripts remain the same.