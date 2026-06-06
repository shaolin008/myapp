#!/bin/bash
DOMAIN=$1
EMAIL=${2:-"admin@$DOMAIN"}

if [ -z "$DOMAIN" ]; then
    echo "用法: bash init-letsencrypt.sh sharing188.com [邮箱]"
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