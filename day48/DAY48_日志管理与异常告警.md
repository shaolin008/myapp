# DAY 48：日志集中管理 + 异常告警

**目标**：结构化日志不用每次 `docker logs`，异常时第一时间收到通知。

---

## 1. 改造为结构化日志

修改 `deploy/main.py`，把所有 `print()` 替换为标准 logging：

```python
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(module)s","message":"%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)
```

关键位置加日志：

```python
# lifespan 函数里
logger.info(f"环境：{settings.APP_ENV}, Debug：{settings.DEBUG}")

# chat 函数里
import time

@app.post("/chat")
def chat(req: ChatRequest, current_user=Depends(get_current_user)):
    start = time.time()
    # ... 原有逻辑 ...
    elapsed = time.time() - start
    logger.info(f"用户 {current_user.email} 请求完成, 耗时 {elapsed:.2f}s, "
                f"模型 {req.model}, tokens {result['token_count']}")
    return ChatResponse(...)
```

---

## 2. Docker 日志配置

修改 `docker-compose.yml`，给每个服务加日志限制：

```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "app"
        tag: "api-{{.ID}}"

  nginx:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

> 不用 ELK 的原因：ELK 需要至少 4GB 内存，小服务器跑不动。JSON 文件 + 告警脚本目前足够。

---

## 3. 异常告警脚本

新建 `deploy/scripts/health-check.sh`：

```bash
#!/bin/bash
# 每 5 分钟运行一次，健康检查失败时发企业微信通知
HEALTH_URL="https://你的域名.com/health"
WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$HEALTH_URL")

if [ "$STATUS" != "200" ]; then
    MESSAGE=$(cat <<EOF
{
    "msgtype": "text",
    "text": {
        "content": "服务器告警 健康检查失败 HTTP状态码: $STATUS 时间: $(date '+%Y-%m-%d %H:%M:%S')"
    }
}
EOF
)
    curl -X POST -H "Content-Type: application/json" -d "$MESSAGE" "$WEBHOOK_URL"
fi
```

> 企业微信机器人 Webhook：群设置 → 群机器人 → 添加。

---

## 4. 配置定时任务

```bash
# SSH 到服务器
crontab -e

# 每 5 分钟检查一次
*/5 * * * * bash /home/deployer/deploy/scripts/health-check.sh >> /tmp/health-check.log 2>&1
```

---

## 5. 验证

```bash
docker compose stop api    # 模拟故障
# 等 5 分钟，企业微信群应收到告警
docker compose start api   # 恢复
```
