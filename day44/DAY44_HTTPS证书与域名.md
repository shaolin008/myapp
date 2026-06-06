# DAY 44：HTTPS 证书 + 域名配置

**目标**：从 HTTP 升级到 HTTPS，拿绿色小锁。

---

## 1. 前提准备

- 一个**已备案域名**（`.com` / `.cn` / `.top` 等）
- 域名 DNS 解析已指向服务器 IP（在域名控制台添加 A 记录）

> 如果还没买域名，今天先去买。国内备案需要 3-15 天不等。在备案下来之前先用 HTTP + IP 继续后面的学习。也可以先用 `nip.io` 测试：`你的IP.nip.io` 自动解析到你的 IP。

---

## 2. 说明

HTTPS 需要公网域名指向服务器。DAY 44 的内容**先在本地把配置写好**，等 DAY 46 上了云服务器再实际获取证书。

---

## 3. 完整 HTTPS Nginx 配置

更新 `deploy/nginx/conf.d/app.conf`：

```nginx
upstream backend {
    server api:8000;
}

# ── HTTP → 强制跳转 HTTPS ───────────────────
server {
    listen 80;
    server_name 你的域名.com www.你的域名.com;

    location /health {
        proxy_pass http://backend;
        access_log off;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# ── HTTPS 主站点 ─────────────────────────────
server {
    listen 443 ssl http2;
    server_name 你的域名.com www.你的域名.com;

    # SSL 证书路径（Certbot 自动管理）
    ssl_certificate     /etc/letsencrypt/live/你的域名.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/你的域名.com/privkey.pem;

    # SSL 安全配置（Mozilla 推荐，A+ 评级）
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    client_max_body_size 50m;

    location / {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 120s;
    }

    location /health {
        proxy_pass http://backend;
        access_log off;
    }
}
```

---

## 4. Certbot 申请脚本

新建 `deploy/scripts/init-letsencrypt.sh`：

```bash
#!/bin/bash
DOMAIN=$1
EMAIL=${2:-"admin@$DOMAIN"}

if [ -z "$DOMAIN" ]; then
    echo "用法: bash init-letsencrypt.sh 你的域名.com [邮箱]"
    exit 1
fi

echo "正在为 $DOMAIN 申请 SSL 证书..."

# 先用 --dry-run 测试
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --dry-run \
    -d "$DOMAIN" -d "www.$DOMAIN"

echo "测试通过！把 --dry-run 删除后重跑即可获取真实证书"
```

---

## 5. 更新 CORS 配置

修改 `.env.prod`：

```
ALLOWED_ORIGINS=https://你的域名.com,https://www.你的域名.com
```
