# Kafka 性能测试参数映射及使用说明

## 概述

本文档详细说明了 `test-spec.json` 中 `test_specification.parameters` 中各个参数的具体用途、在代码中的使用位置以及设置这些值的原因。

## 参数映射表

### 1. `cluster_throughput_mb_per_sec`

**用途**: 定义测试中要尝试的不同吞吐量级别（MB/秒）

**代码使用位置**:
- `run-tests-binary.sh` 第 155 行：从 JSON 配置中提取
- `run-tests-binary.sh` 第 182 行：在测试循环中使用
- `run-tests-binary.sh` 第 52 行：在 `run_test` 函数中计算每秒记录数

**具体使用**:
```bash
records_per_sec=$((throughput * 1024 * 1024 / 1024))  # throughput in records/sec
```

**为什么需要这个值**:
- 用于模拟不同负载水平下的性能表现
- 逐步增加吞吐量以找到集群的性能拐点
- 评估系统在不同负载下的延迟和吞吐量关系

**示例值**: `[20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300]`

---

### 2. `num_producers`

**用途**: 定义测试中使用的生产者数量

**代码使用位置**:
- `run-tests-binary.sh` 第 51 行：计算总任务数
- `run-tests-binary.sh` 第 74-91 行：循环启动生产者进程

**具体使用**:
```bash
local num_jobs=$((6 + consumer_groups * 6))  # 6 producers + (groups * 6 consumers)
```

**为什么需要这个值**:
- 控制并行生产者的数量以模拟真实场景
- 影响负载分布和集群资源利用率
- 不同生产者数量对性能表现有显著影响

**示例值**: `[12]` (在 large 规格中)

---

### 3. `consumer_groups`

**用途**: 定义测试中使用的消费者组配置数组

**代码使用位置**:
- `run-tests-binary.sh` 第 159-161 行：从 JSON 提取消费者组配置
- `run-tests-binary.sh` 第 183 行：在测试循环中使用
- `run-tests-binary.sh` 第 94-116 行：循环启动消费者进程

**具体使用**:
```bash
# 提取消费者组数量
consumer_nums = [cg['num_groups'] for cg in consumer_groups]
# 计算总任务数
local num_jobs=$((6 + consumer_groups * 6))
```

**为什么需要这个值**:
- 测试不同消费者负载对生产者性能的影响
- 模拟真实的生产和消费场景
- 评估消费者数量对整体系统性能的影响

**示例值**: 
```json
[
  { "num_groups": 0, "size": 12 },
  { "num_groups": 2, "size": 12 },
  { "num_groups": 4, "size": 12 }
]
```

---

### 4. `client_props`

**用途**: 定义 Kafka 客户端的配置参数

**代码使用位置**:
- `run-tests-binary.sh` 第 83-87 行：在生产者命令中使用
- 从配置中动态提取 producer 和 consumer 属性

**具体使用**:
```bash
--producer-props "bootstrap.servers=$bootstrap.servers" \
--producer-props "acks=all" \
--producer-props "linger.ms=5" \
--producer-props "batch.size=262114" \
--producer-props "buffer.memory=2147483648" \
```

**为什么需要这个值**:
- 控制消息可靠性级别（acks参数）
- 优化批处理行为（linger.ms, batch.size）
- 管理内存使用（buffer.memory）
- 不同配置对性能有显著影响

**示例值**:
```json
[
  {
    "producer": "acks=1 linger.ms=1 batch.size=32768 buffer.memory=536870912",
    "consumer": ""
  }
]
```

---

### 5. `num_partitions`

**用途**: 定义测试主题的分区数量

**代码使用位置**:
- `run-tests-binary.sh` 第 61-63 行：在创建主题时使用

**具体使用**:
```bash
--partitions 36 \  # 这里的值从配置中动态获取
```

**为什么需要这个值**:
- 分区数直接影响并行度和吞吐量
- 影响消费者的并行处理能力
- 不同分区数对性能表现有重要影响

**示例值**: `[48]` (在 large 规格中)

---

### 6. `record_size_byte`

**用途**: 定义每条消息的大小（字节）

**代码使用位置**:
- `run-tests-binary.sh` 第 54 行：初始化为 1024
- `run-tests-binary.sh` 第 82 行：在生产者命令中使用

**具体使用**:
```bash
--record-size $record_size \
```

**为什么需要这个值**:
- 影响网络传输效率
- 不同消息大小对性能有不同影响
- 模拟真实业务场景的消息大小

**示例值**: `[1024]` (1KB)

---

### 7. `replication_factor`

**用途**: 定义主题的副本因子

**代码使用位置**:
- `run-tests-binary.sh` 第 63 行：在创建主题时使用

**具体使用**:
```bash
--replication-factor 3 \
```

**为什么需要这个值**:
- 影响数据可靠性和可用性
- 不同副本数对写入性能有影响
- 影响磁盘空间使用

**示例值**: `[3]`

---

### 8. `duration_sec`

**用途**: 定义每个测试的持续时间（秒）

**代码使用位置**:
- `run-tests-binary.sh` 第 53 行：初始化为 300
- `run-tests-binary.sh` 第 80 行：计算总记录数
- `run-tests-binary.sh` 第 104 行：计算消费者消息数

**具体使用**:
```bash
--num-records $((records_per_sec * duration_sec)) \
--messages $((records_per_sec * duration_sec / 6)) \
```

**为什么需要这个值**:
- 确保测试有足够的运行时间来获得稳定结果
- 影响测试数据量的大小
- 不同时长对性能评估有不同意义

**示例值**: `[300]` (5分钟)

---

## 跳过条件参数

### `skip_remaining_throughput`

**用途**: 定义何时跳过剩余的高吞吐量测试

**代码使用位置**:
- 在原始 AWS 框架中有使用，但在当前二进制版本中主要用于配置参考

**为什么需要这个值**:
- 避免在集群已饱和时继续测试更高负载
- 节省测试时间和资源
- 防止对集群造成不必要的压力

**示例值**:
```json
{
  "less-than": [ "sent_div_requested_mb_per_sec", 0.98 ]
}
```

## 总结

这些参数共同构成了性能测试的配置矩阵，每个参数都有其特定的作用和影响。通过调整这些参数的组合，可以全面评估 Kafka 集群在不同配置下的性能表现。参数值的选择基于集群规模和预期负载，确保测试结果的实用性和参考价值。