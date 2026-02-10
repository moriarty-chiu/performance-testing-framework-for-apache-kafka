✦ cluster_throughput_mb_per_sec 参数是 Kafka 性能测试框架中的关键参数，如果不设置会产生以下影响：

    不设置 cluster_throughput_mb_per_sec 的影响

    1. 测试目标不明确
     - 没有明确的吞吐量目标，测试将缺乏方向性
     - 无法衡量集群在特定负载下的表现
     - 得到的结果难以与业务需求关联

    2. 测试执行方式改变
     - 框架可能会使用默认值或随机值进行测试
     - 可能会尝试尽可能高的吞吐量直到系统崩溃
     - 测试结果可能不稳定且难以重现

    3. 资源利用不充分
     - 没有目标吞吐量，测试可能无法充分压测系统
     - 无法识别系统的性能瓶颈
     - 可能错过发现系统容量的机会

    cluster_throughput_mb_per_sec 的作用

    1. 测试驱动参数
     - 指定生产者需要达到的目标吞吐量
     - 控制测试负载的强度
     - 用于验证系统在特定负载下的表现

    2. 性能基准
     - 为性能测试提供明确的基准线
     - 便于不同配置间的性能对比
     - 支持回归测试和性能监控

    推荐的设置方法

    基于硬件规格估算

      1 def estimate_throughput(broker_count, disk_speed_mb_s=500,
      2                        network_bandwidth_mb_s=1000):
      3     """
      4     估算集群吞吐量能力
      5
      6     Args:
      7         broker_count: broker 数量
      8         disk_speed_mb_s: 单个磁盘的读写速度 (MB/s)
      9         network_bandwidth_mb_s: 网络带宽 (MB/s)
     10
     11     Returns:
     12         estimated_throughput: 估算的吞吐量范围
     13     """
     14     # 基于磁盘 I/O 的限制
     15     disk_limit = broker_count * disk_speed_mb_s * 0.7  # 保留 30% 余量
     16
     17     # 基于网络带宽的限制
     18     network_limit = broker_count * network_bandwidth_mb_s * 0.6  # 保留 40% 余量
     19
     20     # 取较小值作为理论上限
     21     theoretical_max = min(disk_limit, network_limit)
     22
     23     # 推荐测试范围：理论上限的 30%-80%
     24     test_range = {
     25         'min': theoretical_max * 0.3,
     26         'max': theoretical_max * 0.8,
     27         'recommended_values': [
     28             theoretical_max * 0.3,
     29             theoretical_max * 0.4,
     30             theoretical_max * 0.5,
     31             theoretical_max * 0.6,
     32             theoretical_max * 0.7,
     33             theoretical_max * 0.8
     34         ]
     35     }
     36
     37     return test_range

    基于 12 个 broker 的具体示例

      1 # 假设每个 broker 有 500MB/s 磁盘速度和 1GB/s 网络带宽
      2 broker_count = 12
      3 disk_speed = 500  # MB/s
      4 network_bandwidth = 1000  # MB/s
      5
      6 # 计算理论上限
      7 disk_limit = 12 * 500 * 0.7 = 4200 MB/s  # 磁盘限制
      8 network_limit = 12 * 1000 * 0.6 = 7200 MB/s  # 网络限制
      9
     10 theoretical_max = min(4200, 7200) = 4200 MB/s
     11
     12 # 推荐测试范围
     13 test_range = [1260, 1680, 2100, 2520, 2940, 3360]  # MB/s

    渐进式测试策略

      1 def generate_throughput_steps(theoretical_max, steps=10):
      2     """
      3     生成渐进式吞吐量测试步骤
      4     """
      5     step_size = theoretical_max * 0.8 / steps
      6     return [round(step_size * i, -1) for i in range(1, steps + 1)]
      7
      8 # 示例：12 个 broker，理论最大 4200MB/s
      9 throughput_steps = generate_throughput_steps(4200, 10)
     10 # 结果: [340, 670, 1010, 1340, 1680, 2020, 2350, 2690, 3020, 3360]

    不同规模的推荐设置

    基于 12 个 broker 的配置建议


    ┌──────────┬─────────────────────────────────────┬──────────────┐
    │ 测试规模 │ 推荐吞吐量范围 (MB/s)               │ 说明         │
    ├──────────┼─────────────────────────────────────┼──────────────┤
    │ Small    │ [50, 100, 150, 200, 250, 300]       │ 轻负载测试   │
    │ Medium   │ [200, 400, 600, 800, 1000, 1200]    │ 中等负载测试 │
    │ Large    │ [500, 1000, 1500, 2000, 2500, 3000] │ 重负载测试   │
    │ X-Large  │ [1000, 2000, 3000, 4000, 4200]      │ 接近极限测试 │
    └──────────┴─────────────────────────────────────┴──────────────┘


    最佳实践建议

    1. 分阶段测试
     - 从小吞吐量开始，逐步增加
     - 监控系统指标（CPU、内存、磁盘 I/O、网络）

    2. 多轮验证
     - 每个吞吐量级别运行多次测试
     - 确保结果的稳定性和可重现性

    3. 监控关键指标
     - Producer 端：发送延迟、失败率
     - Consumer 端：消费延迟、滞后量
     - Broker 端：CPU 使用率、磁盘 I/O、网络流量

    4. 设置合理的跳过阈值

     1 {
     2   "skip_remaining_throughput": {
     3     "less-than": ["sent_div_requested_mb_per_sec", 0.95]
     4   }
     5 }

    总结: cluster_throughput_mb_per_sec 是性能测试的核心参数，必须设置。建议根据硬件规格估算理论上限，然后设置一系列渐进式的测试值，以全面了解系统在不同负载下的性能表现。