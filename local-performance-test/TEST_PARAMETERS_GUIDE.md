# Kafka 性能测试参数详解文档

## 目录
- [概述](#概述)
- [小集群规格参数详解](#小集群规格参数详解)
- [中集群规格参数详解](#中集群规格参数详解)
- [大集群规格参数详解](#大集群规格参数详解)
- [超大集群规格参数详解](#超大集群规格参数详解)
- [通用参数说明](#通用参数说明)

## 概述

本文档详细解释了 `test-spec-*.json` 文件中每个参数的意义、设置理由和期望值。这些配置文件针对不同规模的 Kafka 集群进行了优化。

---

## 小集群规格参数详解

### 配置文件: `test-spec-small.json`

```json
{
  "parameters": {
    "cluster_throughput_mb_per_sec": [ 5, 10, 15, 20, 25, 30, 35, 40, 45, 50 ],
    "num_producers": [ 3 ],
    "consumer_groups": [ 
      { "num_groups": 0, "size": 3 }
    ],
    "client_props": [
      {
        "producer": "acks=1 linger.ms=1 batch.size=32768 buffer.memory=536870912",
        "consumer": ""
      }
    ],
    "num_partitions": [ 12 ],
    "record_size_byte": [ 1024 ],
    "replication_factor": [ 1 ],
    "duration_sec": [ 120 ]
  },
  "skip_remaining_throughput": {
    "less-than": [ "sent_div_requested_mb_per_sec", 0.95 ]
  }
}
```

### 参数详解

| 参数 | 值 | 意义 | 设置理由 | 期望值 |
|------|----|----|----------|---------|
| `cluster_throughput_mb_per_sec` | [5-50] | 测试吞吐量范围 | 小集群通常处理较低负载，5-50MB/s覆盖开发/测试环境常见范围 | 5-50MB/s |
| `num_producers` | [3] | 生产者数量 | 小集群资源有限，3个生产者足够产生有意义的负载而不压垮系统 | 3-8个 |
| `consumer_groups` | [{"num_groups": 0, "size": 3}] | 消费者组配置 | 初始测试无消费者，后续可扩展到1个组3个消费者 | 0-1个组，每组3个消费者 |
| `producer` props | acks=1 | 应答策略 | 平衡可靠性和性能，比acks=all快但比acks=0更可靠 | 1-5ms延迟 |
| `producer` props | linger.ms=1 | 批处理延迟 | 允许小批量合并以提高吞吐量，1ms最小延迟 | 1-5ms |
| `producer` props | batch.size=32768 | 批处理大小 | 32KB适合小集群，避免内存压力 | 16-64KB |
| `producer` props | buffer.memory=536870912 | 缓冲区大小 | 512MB缓冲区，适合小集群内存限制 | 256-1024MB |
| `num_partitions` | [12] | 分区数 | 小集群通常2-4个节点，12个分区提供足够并行度 | 8-16个 |
| `record_size_byte` | [1024] | 消息大小 | 1KB是常见消息大小，代表典型业务场景 | 0.5-2KB |
| `replication_factor` | [1] | 副本因子 | 小集群通常无副本或少量副本，减少资源消耗 | 1-2 |
| `duration_sec` | [120] | 测试时长 | 2分钟足够观察稳定性能，不占用过多资源 | 60-180秒 |
| `skip_remaining_throughput` | 0.95 | 停止阈值 | 当实际吞吐量低于请求的95%时停止，避免过度压力 | 90-98% |

---

## 中集群规格参数详解

### 配置文件: `test-spec-medium.json`

```json
{
  "parameters": {
    "cluster_throughput_mb_per_sec": [ 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120 ],
    "num_producers": [ 6 ],
    "consumer_groups": [ 
      { "num_groups": 0, "size": 6 },
      { "num_groups": 1, "size": 6 }
    ],
    "client_props": [
      {
        "producer": "acks=1 linger.ms=2 batch.size=65536 buffer.memory=1073741824",
        "consumer": ""
      },
      {
        "producer": "acks=all linger.ms=5 batch.size=131072 buffer.memory=2147483648",
        "consumer": ""
      }
    ],
    "num_partitions": [ 24 ],
    "record_size_byte": [ 1024 ],
    "replication_factor": [ 2 ],
    "duration_sec": [ 180 ]
  },
  "skip_remaining_throughput": {
    "less-than": [ "sent_div_requested_mb_per_sec", 0.97 ]
  }
}
```

### 参数详解

| 参数 | 值 | 意义 | 设置理由 | 期望值 |
|------|----|----|----------|---------|
| `cluster_throughput_mb_per_sec` | [10-120] | 测试吞吐量范围 | 中等生产环境常见负载范围，提供足够的性能基准 | 10-120MB/s |
| `num_producers` | [6] | 生产者数量 | 中等规模集群可以有效利用6个生产者进行负载测试 | 4-8个 |
| `consumer_groups` | [0,1个组，每组6个] | 消费者组配置 | 测试无消费者和有消费者两种场景，6个消费者提供合理负载 | 0-2个组，每组4-8个 |
| `producer` props | acks=1, acks=all | 可靠性对比 | 提供两种可靠性级别的性能对比 | acks=1: 更高吞吐量；acks=all: 更高可靠性 |
| `producer` props | linger.ms=2,5 | 批处理延迟 | 中等延迟允许更好的批处理效果 | 2-10ms |
| `producer` props | batch.size=65536,131072 | 批处理大小 | 64KB-128KB适合中等集群，优化网络效率 | 32-256KB |
| `producer` props | buffer.memory=1-2GB | 缓冲区大小 | 1-2GB缓冲区适应中等集群内存容量 | 1-4GB |
| `num_partitions` | [24] | 分区数 | 中等集群通常4-8个节点，24个分区提供良好并行度 | 16-32个 |
| `replication_factor` | [2] | 副本因子 | 2副本提供故障转移能力，同时控制资源使用 | 2-3 |
| `duration_sec` | [180] | 测试时长 | 3分钟允许系统达到稳定状态 | 120-300秒 |
| `skip_remaining_throughput` | 0.97 | 停止阈值 | 更严格的97%阈值，因为中等集群更接近生产环境 | 95-98% |

---

## 大集群规格参数详解

### 配置文件: `test-spec-large.json`

```json
{
  "parameters": {
    "cluster_throughput_mb_per_sec": [ 20, 40, 60, 80, 100, 120, 140, 160, 180, 200, 220, 240, 260, 280, 300 ],
    "num_producers": [ 12 ],
    "consumer_groups": [ 
      { "num_groups": 0, "size": 12 },
      { "num_groups": 2, "size": 12 },
      { "num_groups": 4, "size": 12 }
    ],
    "client_props": [
      {
        "producer": "acks=1 linger.ms=1 batch.size=32768 buffer.memory=1073741824",
        "consumer": ""
      },
      {
        "producer": "acks=all linger.ms=5 batch.size=262114 buffer.memory=4294967296",
        "consumer": ""
      }
    ],
    "num_partitions": [ 48 ],
    "record_size_byte": [ 1024 ],
    "replication_factor": [ 3 ],
    "duration_sec": [ 300 ]
  },
  "skip_remaining_throughput": {
    "less-than": [ "sent_div_requested_mb_per_sec", 0.98 ]
  }
}
```

### 参数详解

| 参数 | 值 | 意义 | 设置理由 | 期望值 |
|------|----|----|----------|---------|
| `cluster_throughput_mb_per_sec` | [20-300] | 测试吞吐量范围 | 大集群企业级负载范围，测试高吞吐量性能 | 20-300MB/s |
| `num_producers` | [12] | 生产者数量 | 12个生产者充分利用大集群的并行处理能力 | 8-16个 |
| `consumer_groups` | [0,2,4个组，每组12个] | 消费者组配置 | 多种消费者场景，测试高并发消费能力 | 0-6个组，每组8-16个 |
| `producer` props | acks=all | 高可靠性 | 企业环境通常要求最高可靠性保证 | 低吞吐量，高可靠性 |
| `producer` props | batch.size=262114 | 大批处理 | 256KB批次优化大集群网络传输效率 | 128-512KB |
| `producer` props | buffer.memory=4GB | 大缓冲区 | 4GB缓冲区适应大集群的高吞吐量需求 | 2-8GB |
| `num_partitions` | [48] | 分区数 | 大集群通常8-16个节点，48个分区提供充足并行度 | 32-64个 |
| `replication_factor` | [3] | 副本因子 | 3副本提供高可用性，满足企业级要求 | 3 |
| `duration_sec` | [300] | 测试时长 | 5分钟充分测试系统稳定性 | 300-600秒 |
| `skip_remaining_throughput` | 0.98 | 停止阈值 | 严格阈值，确保大集群性能测试准确性 | 97-99% |

---

## 超大集群规格参数详解

### 配置文件: `test-spec-xlarge.json`

```json
{
  "parameters": {
    "cluster_throughput_mb_per_sec": [ 50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600 ],
    "num_producers": [ 18 ],
    "consumer_groups": [ 
      { "num_groups": 0, "size": 18 },
      { "num_groups": 3, "size": 18 },
      { "num_groups": 6, "size": 18 }
    ],
    "client_props": [
      {
        "producer": "acks=1 linger.ms=0 batch.size=16384 buffer.memory=2147483648",
        "consumer": ""
      },
      {
        "producer": "acks=all linger.ms=2 batch.size=131072 buffer.memory=8589934592",
        "consumer": ""
      },
      {
        "producer": "acks=all linger.ms=10 batch.size=524288 buffer.memory=17179869184",
        "consumer": ""
      }
    ],
    "num_partitions": [ 72 ],
    "record_size_byte": [ 1024 ],
    "replication_factor": [ 3 ],
    "duration_sec": [ 600 ]
  },
  "skip_remaining_throughput": {
    "less-than": [ "sent_div_requested_mb_per_sec", 0.99 ]
  }
}
```

### 参数详解

| 参数 | 值 | 意义 | 设置理由 | 期望值 |
|------|----|----|----------|---------|
| `cluster_throughput_mb_per_sec` | [50-600] | 极限吞吐量测试 | 测试集群性能上限，寻找瓶颈 | 50-600+MB/s |
| `num_producers` | [18] | 最大生产者数量 | 18个生产者最大化利用集群资源 | 12-24个 |
| `consumer_groups` | [0,3,6个组，每组18个] | 高并发消费者 | 大量消费者测试极限消费能力 | 0-8个组，每组12-20个 |
| `producer` props | linger.ms=0,2,10 | 不同批处理策略 | 测试不同延迟要求下的性能表现 | 0-20ms |
| `producer` props | batch.size=16-512KB | 可变批处理大小 | 测试不同批处理大小的性能影响 | 16-512KB |
| `producer` props | buffer.memory=2-17GB | 巨大缓冲区 | 适应极限负载下的内存需求 | 4-32GB |
| `num_partitions` | [72] | 最大分区数 | 72个分区提供最大并行度 | 48-96个 |
| `replication_factor` | [3] | 高可用副本 | 3副本确保企业级高可用性 | 3 |
| `duration_sec` | [600] | 长时间测试 | 10分钟充分压力测试系统稳定性 | 600+秒 |
| `skip_remaining_throughput` | 0.99 | 极严格阈值 | 99%阈值确保精确的性能极限识别 | 98-99.5% |

---

## 通用参数说明

### 跳过条件参数
- **`skip_remaining_throughput`**: 当实际吞吐量与请求吞吐量比率低于指定值时，跳过剩余的更高吞吐量测试
- **设置理由**: 避免在集群已饱和时继续测试，节省时间和资源
- **期望值**: 随集群规模增加而提高（小集群95% → 超大集群99%）

### 消息大小参数
- **`record_size_byte`**: 固定为1024字节(1KB)
- **设置理由**: 1KB是典型业务消息大小，具有代表性
- **期望值**: 1KB适合大多数业务场景

### 客户端属性参数
- **`acks`**: 控制消息确认级别
  - `acks=1`: leader确认，平衡性能和可靠性
  - `acks=all`: 所有副本确认，最高可靠性
- **`linger.ms`**: 批处理延迟，允许消息合并
- **`batch.size`**: 批处理大小，影响网络效率
- **`buffer.memory`**: 生产者内存缓冲区大小

这些参数经过精心设计，确保在不同规模的 Kafka 集群上获得准确、有意义的性能基准测试结果。