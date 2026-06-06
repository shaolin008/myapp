# DAY 50：Prometheus + Grafana 监控面板

**目标**：可视化监控——请求量、响应时间、错误率、CPU/内存。

---

## 1. 整体架构

```
FastAPI → 暴露 /metrics → Prometheus 抓取 → Grafana 连接 Prometheus → 可视化面板
```

---

## 2. 给 FastAPI 加 Prometheus 指标

在 `deploy/requirements.txt` 添加：

```
prometheus-fastapi-instrumentator==7.1.0
```

在 `deploy/main.py` 中添加（只需 3 行）：

```python
from prometheus_fastapi_instrumentator import Instrumentator

# app = FastAPI(...) 之后

instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
)
instrumentator.instrument(app).expose(app, endpoint="/metrics")
```

自动暴露的指标：
- `http_requests_total` — 请求总数
- `http_request_duration_seconds` — 请求耗时分布
- `http_requests_in_progress` — 正在处理的请求数

---

## 3. Prometheus 配置

新建 `deploy/prometheus/prometheus.yml`：

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fastapi'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

---

## 4. 更新 docker-compose.yml 加入监控

```yaml
services:
  # 原有服务...

  prometheus:
    image: prom/prometheus:v2.55.0
    container_name: myapp_prometheus
    restart: unless-stopped
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:11.4.0
    container_name: myapp_grafana
    restart: unless-stopped
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=改成你的密码
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./grafana/datasources:/etc/grafana/provisioning/datasources:ro
    ports:
      - "3000:3000"

  node-exporter:
    image: prom/node-exporter:v1.8.2
    container_name: node_exporter
    restart: unless-stopped
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'

volumes:
  prometheus_data:
  grafana_data:
```

---

## 5. Grafana 数据源配置

新建 `deploy/grafana/datasources/datasource.yml`：

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

---

## 6. 部署并访问

```bash
# 服务器上
cd ~/deploy
docker compose down
docker compose up -d
docker compose ps
```

浏览器打开 `http://你的服务器IP:3000`：
- 用户名：`admin`
- 密码：你设的密码

---

## 7. 创建第一个 Dashboard

左侧菜单 → Dashboards → New → Add visualization，用以下查询：

| 面板 | PromQL 查询 | 说明 |
|------|-----------|------|
| 每秒请求数 | `rate(http_requests_total[1m])` | QPS |
| P95 延迟 | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[1m]))` | 95%请求耗时 |
| 5xx 错误率 | `rate(http_requests_total{status=~"5.."}[1m])` | 服务端错误 |
| CPU 使用率 | `100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)` | 服务器 CPU |

也可以 Import 社区模板 ID `11159`（FastAPI 专用面板）。

---

## 模块完成

从 DAY 41 到 DAY 50，你完成了：

```
公网用户 → HTTPS域名 → Nginx反向代理 → FastAPI(Docker)
                                    ├── PostgreSQL(Docker)
                                    ├── Redis(Docker)
                                    ├── Prometheus + Grafana 监控
                                    └── GitHub Actions 自动部署
```
