# 安装指南

## 系统要求

- Python 3.8+
- Java 8+ (Kafka 依赖)
- Apache Kafka (真实测试需要)

## 快速安装

### 1. 安装 Python 依赖

```bash
cd local-kafka-test
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. 配置 Kafka 路径

编辑 `config.yaml`：

```yaml
kafka_home: /opt/kafka  # 修改为你的 Kafka 安装路径
bootstrap_servers: localhost:9092
results_dir: ./results
```

### 3. 验证安装

```bash
# Debug 模式测试（无需 Kafka）
python run_test.py --spec specs/small-spec.json --debug --test-name test1

# 生成报告
python generate_reports.py --test-name test1

# 查看报告
cat results/test1/reports/summary_report.txt
```

## 安装 Apache Kafka（如未安装）

### macOS

```bash
# 使用 Homebrew
brew install kafka
```

### Linux (Ubuntu/Debian)

```bash
# 手动安装
cd /opt
wget https://archive.apache.org/dist/kafka/3.4.0/kafka_2.13-3.4.0.tgz
tar -xzf kafka_2.13-3.4.0.tgz
ln -s kafka_2.13-3.4.0 kafka
```

### Linux (RHEL/CentOS)

```bash
sudo yum install kafka
```

## 启动 Kafka（真实测试需要）

```bash
# 终端 1: 启动 Zookeeper (Kafka < 3.0)
$KAFKA_HOME/bin/zookeeper-server-start.sh $KAFKA_HOME/config/zookeeper.properties

# 终端 2: 启动 Kafka Broker
$KAFKA_HOME/bin/kafka-server-start.sh $KAFKA_HOME/config/server.properties
```

## 验证 Kafka

```bash
# 列出 topics
$KAFKA_HOME/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

## 故障排除

### Java 未安装

```bash
# 检查 Java
java -version

# macOS 安装
brew install openjdk@11

# Ubuntu/Debian 安装
sudo apt-get install openjdk-11-jdk
```

### Python 版本过低

```bash
# 检查 Python 版本
python3 --version

# macOS 安装最新版
brew install python@3.9

# Ubuntu/Debian
sudo apt-get install python3 python3-venv python3-pip
```

### 权限问题

```bash
# 赋予 Kafka 脚本执行权限
chmod +x $KAFKA_HOME/bin/*.sh
```
