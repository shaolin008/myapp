# DAY 43：Nginx 反向代理 + 静态文件

**目标**：Nginx 作为"前台接待"，80 端口接收请求，转发给后端 8000 端口。

---

## 1. 理解反向代理

```
用户浏览器 → http://你的IP/ → Nginx(80端口) → FastAPI(8000端口)
```

Nginx 的好处：
- 用户不用记端口号，直接访问 80（HTTP 标准端口）
- Nginx 处理静态文件（CSS/JS/图片）比 FastAPI 快 10 倍+
- 一个 Nginx 可以代理多个后端服务
- Nginx 可以限速、压缩、缓存

---

## 2. 创建 nginx 文件夹

```
deploy/
├── nginx/
│   ├── nginx.conf           # 主配置文件
│   └── conf.d/
│       └── app.conf         # 你的应用配置
```

---

## 3. 主配置文件 nginx.conf

```nginx
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] '
                    '"$request" $status $body_bytes_sent '
                    '"$http_referer" "$http_user_agent" '
                    'rt=$request_time';

    access_log /var/log/nginx/access.log main;

    sendfile        on;
    tcp_nopush      on;
    keepalive_timeout 65;
    gzip            on;
    gzip_min_length 1024;
    gzip_types      text/plain application/json application/javascript text/css;

    include /etc/nginx/conf.d/*.conf;
}
```

---

## 4. 站点配置 conf.d/app.conf（核心）

```nginx
upstream backend {
    server api:8000;
}

server {
    listen 80;
    server_name _;

    client_max_body_size 50m;

    # 静态文件直接由 Nginx 返回
    location /static/ {
        alias /usr/share/nginx/html/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API 请求转发给 FastAPI
    location / {
        proxy_pass http://backend;

        # 把客户端真实信息传给后端
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置（AI 对话比较慢）
        proxy_read_timeout 120s;
        proxy_connect_timeout 10s;
    }

    # 健康检查不记日志
    location /health {
        proxy_pass http://backend;
        access_log off;
    }
}
```

---

## 5. 修改 docker-compose.yml 加入 Nginx

关键变化：API 服务的 `ports: - "8000:8000"` 改成 `expose: - "8000"`，外部只能通过 Nginx 80 端口访问。

```yaml
services:
  # db, redis, api 保持不变...

  api:
    # ...
    # ports 注释掉：
    # ports:
    #   - "8000:8000"
    expose:
      - "8000"

  # ── Nginx 反向代理 ─────────────────────
  
```  
nginx:
    image: nginx:1.27-alpine
    container_name: myapp_nginx
    restart: unless-stopped
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
    depends_on:
      - api

---

## 6. 验证

```bash
cd D:\AI相关\文件总集\开发学习\deploy

# 重建
docker compose down
docker compose up -d

# 测试 80 端口（经过 Nginx 代理）
curl http://localhost/health
# 应该返回 {"status":"ok"}

# Swagger 文档
# 浏览器打开 http://localhost/docs
```

---

## 7. 查看 Nginx 日志

```bash
docker compose exec nginx cat /var/log/nginx/access.log
```
