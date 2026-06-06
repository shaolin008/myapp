# DAY 46：云服务器部署

**目标**：把 Docker 环境搬到阿里云/腾讯云服务器上，公网可访问。

---

## 1. 选购云服务器

| 平台 | 推荐型号 | 配置 | 参考价格 |
|------|---------|------|---------|
| 阿里云 | 轻量应用服务器 | 2核2G / 60G SSD / 3Mbps | 约 68 元/年（新用户） |
| 腾讯云 | 轻量应用服务器 | 2核2G / 50G SSD / 4Mbps | 约 58 元/年（新用户） |

选择镜像：**Ubuntu 22.04 LTS**。

---

## 2. 登录并初始化服务器

```bash
ssh root@你的服务器IP
# 首次登录输入 yes
```

逐条执行：

```bash
# 1. 更新系统
apt update && apt upgrade -y

# 2. 创建普通用户
adduser deployer
usermod -aG sudo deployer

# 3. 配置防火墙
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status

# 4. 设置时区
sudo timedatectl set-timezone Asia/Shanghai
```

> 云服务商**控制台**也有防火墙（安全组），需要在那边同步开放 22、80、443 端口。

---

## 3. 安装 Docker

```bash
# 官方安装脚本
curl -fsSL https://get.docker.com | sudo bash

# 把 deployer 加入 docker 组
sudo usermod -aG docker deployer

# 安装 docker compose 插件
sudo apt install -y docker-compose-plugin

# 重新登录使权限生效
exit
ssh deployer@你的服务器IP

# 验证
docker --version
docker compose version
```

---

## 4. 把项目代码传上服务器

**方案 A：用 Git（推荐）**

先在本地把项目推送到 GitHub，然后：

```bash
cd ~
git clone https://github.com/你的用户名/你的仓库.git
cd 你的仓库/deploy
```

**方案 B：用 scp 直接传**

在本地 PowerShell：
```bash
scp -r D:\AI相关\文件总集\开发学习\deploy deployer@你的服务器IP:~/deploy
```

---

## 5. 配置并启动

```bash
cd ~/deploy

# 编辑生产配置
nano .env.prod
# 修改 ALLOWED_ORIGINS 为服务器 IP 或域名

# 启动
docker compose up -d

# 查看状态
docker compose ps
docker compose logs api
```

---

## 6. 验证

在本机浏览器访问：
- `http://你的服务器IP/health`
- `http://你的服务器IP/docs`

如果打不开，依次检查：
1. 云服务器控制台安全组是否开放 80 端口
2. `docker compose ps` 是否所有服务 Up
3. `docker compose logs nginx` 有无报错
