# Local Kafka Performance Testing

This directory contains the extracted performance testing components from the AWS framework, adapted for local/self-deployed Kafka clusters.

## 📁 Structure

```
local-performance-test/
├── config/                # Test configurations
├── scripts/               # Test execution scripts
├── results/               # Test output and logs
├── DETAILED_USAGE.md      # Comprehensive usage guide
├── BINARY_MODE_README.md  # Binary mode usage guide
├── FLAVOR_TESTING_GUIDE.md # Cluster flavor testing guide
└── requirements.txt       # Python dependencies
```

## 🚀 Quick Start

1. **Install Kafka** on your system and set `KAFKA_HOME` environment variable
2. **Configure your Kafka cluster connection** in `config/kafka.properties`
3. **Define test parameters** in `config/test-spec.json`
4. **Run the test suite for all flavors**: `./scripts/run-flavor-tests.sh`

## 🎯 Key Differences from AWS Version

- No AWS infrastructure dependencies
- Local execution using Kafka binary tools
- Simplified orchestration
- Direct result collection and visualization

## 📖 Detailed Documentation

For comprehensive information about:
- Script descriptions and purposes
- Parameter specifications and meanings
- How parameters affect testing
- Best practices and troubleshooting

See: [DETAILED_USAGE.md](DETAILED_USAGE.md)

## 📊 What You'll Get

- Throughput vs latency measurements
- Configuration comparison charts
- Statistical analysis of performance metrics
- CSV/JSON results for further analysis