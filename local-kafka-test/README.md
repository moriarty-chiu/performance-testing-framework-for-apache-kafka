# Local Kafka Performance Testing Framework

一个用于本地 Kafka 集群的性能测试工具，基于 Apache Kafka 自带的 `kafka-producer-perf-test.sh` 和 `kafka-consumer-perf-test.sh` 工具构建。

## 功能特点

- ✅ **无需 AWS 环境**：完全在本地运行
- ✅ **灵活的测试配置**：支持多种 producer/consumer 配置组合
- ✅ **自动化测试流程**：自动创建/删除 topic，执行测试
- ✅ **可视化报告**：生成文本报告和图表
- ✅ **Debug 模式**：无需 Kafka 集群即可测试框架（生成模拟数据）
- ✅ **多集群规模支持**：预定义小/中/大三种集群规模的测试配置

## 快速开始

### 1. 安装依赖

```bash
cd local-kafka-test
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. 配置 Kafka 路径

编辑 `config.yaml`，设置你的 Kafka 安装路径：

```yaml
kafka_home: /opt/kafka  # 修改为你的 Kafka 路径
bootstrap_servers: localhost:9092
```

### 3. 运行测试

#### Debug 模式（无需 Kafka 集群）

```bash
# 测试框架功能，生成模拟数据
python run_test.py --spec specs/medium-spec.json --debug --test-name test-run
```

#### 真实 Kafka 测试

```bash
# 确保 Kafka 集群已启动，然后执行
python run_test.py --config config.yaml --spec specs/medium-spec.json --test-name prod-test
```

### 4. 查看报告

```bash
# 生成报告和图表
python generate_reports.py --test-name test-run

# 查看生成的文件
ls results/test-run/reports/
```

## 目录结构

```
local-kafka-test/
├── run_test.py              # 主测试脚本
├── generate_reports.py      # 报告生成脚本
├── mock_data_generator.py   # 模拟数据生成器（debug 模式使用）
├── test_parameters.py       # 测试参数管理
├── aggregate_statistics.py  # 统计数据聚合
├── plot.py                  # 图表生成
├── config.yaml              # 配置文件
├── requirements.txt         # Python 依赖
├── specs/                   # 测试规格定义
│   ├── small-spec.json      # 小集群测试配置
│   ├── medium-spec.json     # 中集群测试配置
│   └── large-spec.json      # 大集群测试配置
└── results/                 # 测试结果输出目录
    ├── <test-name>/
    │   ├── *.json           # 原始测试结果
    │   └── reports/         # 生成的报告和图表
```

## 配置说明

### config.yaml - 连接和安全配置

```yaml
# Kafka 连接
bootstrap_servers: localhost:9092
kafka_home: /opt/kafka

# 安全配置（可选）- 通过 --producer.config / --consumer.config / --command-config 传递
security:
  # SSL/SASL 配置
  security_protocol: SASL_SSL
  sasl_mechanism: SCRAM-SHA-512
  sasl_username: alice
  sasl_password: alice-secret
  
  # SSL 配置
  ssl_truststore_location: /path/to/truststore.jks
  ssl_truststore_password: password
  ssl_keystore_location: /path/to/keystore.jks
  ssl_keystore_password: password
  
  # SSL 端点识别算法（重要！）
  # - "" (空字符串): 禁用主机名验证（内网测试/开发环境）
  # - "HTTPS": 启用主机名验证（生产环境）
  # 注意：即使是空字符串也必须设置，否则 SASL_SSL 连接会失败
  ssl_endpoint_identification_algorithm: ""
```

**配置分层说明**：

| 参数位置 | 传递方式 | 用途 |
|---------|---------|------|
| `config.yaml` | `--producer.config` / `--consumer.config` / `--command-config` | 安全配置（SSL、SASL） |
| `spec` 文件 `client_props.producer` | `--producer-props` | 测试参数（acks、linger.ms、batch.size、compression.type 等） |

**生成的安全 properties 文件示例**（临时文件，自动清理）：

```properties
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-512
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="alice" password="alice-secret";
ssl.truststore.location=/path/to/truststore.jks
ssl.truststore.password=password
```

**Kafka 命令示例**：

```bash
# Producer
kafka-producer-perf-test.sh \
  --topic my-topic \
  --producer-props bootstrap.servers=localhost:9092 acks=all linger.ms=5 batch.size=65536 \
  --producer.config /tmp/kafka-security-xxx.properties

# Consumer
kafka-consumer-perf-test.sh \
  --consumer.config /tmp/kafka-security-xxx.properties \
  ...

# Topic management
kafka-topics.sh \
  --command-config /tmp/kafka-security-xxx.properties \
  ...
```

### spec 文件 - 测试参数配置

```json
{
  "test_specification": {
    "parameters": {
      "client_props": [
        {
          // 测试不同的压缩算法
          "producer": "acks=all compression.type=lz4 batch.size=65536",
          "consumer": "fetch.min.bytes=1048576"
        },
        {
          // 对比不同配置
          "producer": "acks=all compression.type=gzip batch.size=131072",
          "consumer": ""
        }
      ]
    }
  }
}
```

### 配置分层说明

| 配置类型 | 位置 | 示例 |
|---------|------|------|
| **连接/安全** | `config.yaml` | SSL、SASL、认证信息 |
| **测试变量** | `spec` 文件 | 压缩算法、acks、batch.size |

**优势**：
- ✅ 安全配置集中管理，避免在多个 spec 文件中重复
- ✅ 测试参数灵活变化，方便对比不同配置
- ✅ 切换集群时只需修改 `config.yaml`，无需改动 spec 文件

### 测试不同规模的集群

```bash
# 小集群测试（2 producers, 12 partitions, 4-16 MB/s）
python run_test.py --spec specs/small-spec.json --debug --test-name small

# 中集群测试（4 producers, 24 partitions, 16-80 MB/s）
python run_test.py --spec specs/medium-spec.json --debug --test-name medium

# 大集群测试（8 producers, 48 partitions, 64-256 MB/s）
python run_test.py --spec specs/large-spec.json --debug --test-name large
```

### 自定义测试配置

创建自定义的 JSON 规格文件：

```json
{
  "test_specification": {
    "parameters": {
      "cluster_throughput_mb_per_sec": [16, 32, 64],
      "num_producers": [4],
      "consumer_groups": [
        {"num_groups": 0, "size": 4},
        {"num_groups": 1, "size": 4}
      ],
      "client_props": [
        {
          "producer": "acks=all linger.ms=5 batch.size=65536",
          "consumer": ""
        }
      ],
      "num_partitions": [24],
      "record_size_byte": [1024],
      "replication_factor": [1],
      "duration_sec": [60]
    },
    "skip_remaining_throughput": {
      "less-than": ["sent_div_requested_mb_per_sec", 0.95]
    }
  }
}
```

运行自定义测试：

```bash
python run_test.py --spec my-custom-spec.json --debug --test-name custom-test
```

### 查看测试结果

```bash
# 查看文本报告
cat results/test-run/reports/summary_report.txt

# 查看 CSV 数据
cat results/test-run/reports/producer_metrics.csv

# 查看生成的图表
open results/test-run/reports/*.png  # macOS
xdg-open results/test-run/reports/*.png  # Linux
```

## 命令行参数

### run_test.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config, -c` | 配置文件路径 | `config.yaml` |
| `--spec, -s` | 测试规格 JSON 文件 | **必需** |
| `--test-name, -n` | 测试名称（用于组织结果目录） | 使用 spec 文件名 |
| `--output-dir, -o` | 结果输出基础目录 | `./results` |
| `--debug` | Debug 模式（生成模拟数据） | `False` |
| `--verbose, -v` | 详细日志输出 | `False` |

### generate_reports.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--test-name, -n` | 测试名称 | 自动检测最近的测试 |
| `--results-dir, -r` | 结果目录路径 | 根据 test-name 构建 |
| `--output-dir, -o` | 报告输出目录 | `<results-dir>/reports` |
| `--no-plots` | 不生成图表 | `False` |
| `--no-report` | 不生成文本报告 | `False` |

## 生成的报告

### 文本报告 (summary_report.txt)

包含：
- 总体测试摘要（测试次数、记录数等）
- Producer 指标（吞吐量、延迟统计）
- Consumer 指标（吞吐量、延迟统计）
- 按配置吞吐量分组的详细指标

### CSV 数据

- `producer_metrics.csv`: 所有 producer 测试的详细指标
- `consumer_metrics.csv`: 所有 consumer 测试的详细指标

### 图表 (PNG)

1. **producer_throughput_vs_latency.png**: 吞吐量 vs 延迟散点图
2. **producer_latency_percentiles.png**: 延迟百分位数（P50, P99）
3. **producer_throughput_efficiency.png**: 实际吞吐量/请求吞吐量比率
4. **latency_vs_throughput.png**: 延迟随吞吐量变化趋势
5. **consumer_throughput.png**: 消费者吞吐量按组分布

## 常见问题

### Q: 找不到 Kafka 二进制文件

**错误**: `Cannot find Kafka binaries`

**解决**:
1. 确认 `config.yaml` 中的 `kafka_home` 路径正确
2. 确认 `$KAFKA_HOME/bin/kafka-producer-perf-test.sh` 存在
3. 赋予执行权限：`chmod +x $KAFKA_HOME/bin/*.sh`

### Q: 连接被拒绝

**错误**: `Connection refused`

**解决**:
1. 确认 Kafka 集群已启动
2. 检查 `bootstrap_servers` 配置是否正确
3. 确认防火墙未阻止 9092 端口

### Q: 如何使用 debug 模式？

**解决**: 添加 `--debug` 参数即可，无需 Kafka 集群：

```bash
python run_test.py --spec specs/medium-spec.json --debug
```

### Q: 如何清理测试数据？

**解决**: Debug 模式不需要清理。真实测试后，topic 会自动删除。如需手动清理：

```bash
# 删除特定测试的结果
rm -rf results/test-name

# 删除所有测试结果
rm -rf results/*
```

## 技术细节

### 测试流程

1. 读取测试规格文件
2. 遍历所有参数组合
3. 对每个组合：
   - 创建 Kafka topic
   - 启动 producer 性能测试
   - 启动 consumer 性能测试（如配置）
   - 收集指标
   - 删除 topic
4. 保存结果并生成报告

### Skip Condition

当实际吞吐量低于请求吞吐量的一定比例时，跳过剩余吞吐量测试：

```json
"skip_remaining_throughput": {
  "less-than": ["sent_div_requested_mb_per_sec", 0.95]
}
```

这有助于在集群达到饱和时节省测试时间。

### Debug 模式

Debug 模式下，`mock_data_generator.py` 根据测试参数生成逼真的模拟数据：
- 考虑配置影响（acks、batch.size、linger.ms 等）
- 模拟高吞吐量时的饱和效应
- 添加合理的随机方差
- 固定随机种子（结果可复现）

## 许可证

MIT License
