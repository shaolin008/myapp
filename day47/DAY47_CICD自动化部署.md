# DAY 47：CI/CD 自动化部署（GitHub Actions）

**目标**：本地 `git push` → GitHub Actions 自动构建 → 自动部署到服务器。告别手动上传。

---

## 1. 整体流程

```
你 git push → GitHub Actions 触发
    → 在 GitHub 的服务器上 docker build
    → 通过 SSH 连到你的服务器
    → docker compose pull && up -d
    → 部署完成
```

---

## 2. 创建 GitHub Actions 工作流文件

在你的 Git 仓库根目录创建 `.github/workflows/deploy.yml`：

```yaml
name: Deploy to Server

on:
  push:
    branches:
      - master
    paths:
      - 'deploy/**'
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: 检出代码
        uses: actions/checkout@v4

      - name: 登录 Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_TOKEN }}

      - name: 构建镜像并推送
        run: |
          cd deploy
          TIMESTAMP=$(date +%Y%m%d%H%M%S)
          IMAGE_NAME=${{ secrets.DOCKER_USERNAME }}/myapp
          docker build -t $IMAGE_NAME:latest -t $IMAGE_NAME:$TIMESTAMP .
          docker push $IMAGE_NAME:latest
          docker push $IMAGE_NAME:$TIMESTAMP

      - name: SSH 到服务器并部署
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          script: |
            cd ~/deploy
            docker compose pull api
            docker compose up -d --remove-orphans
            docker image prune -f
```

---

## 3. 配置 GitHub Secrets

在 GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret：

| Secret 名 | 值 | 说明 |
|-----------|-----|------|
| `SERVER_HOST` | `你的服务器IP` | |
| `SERVER_USER` | `deployer` | |
| `SERVER_SSH_KEY` | 私钥内容 | `cat ~/.ssh/id_ed25519` |
| `DOCKER_USERNAME` | Docker Hub 用户名 | |
| `DOCKER_TOKEN` | Docker Hub Access Token | |

---

## 4. 修改 docker-compose.yml 使用远程镜像

```yaml
api:
  # build: .              # 注释掉本地构建
  image: 你的DockerHub用户名/myapp:latest
  # ... 其余不变
```

---

## 5. 测试

```bash
cd D:\AI相关\文件总集\开发学习
git add .github/workflows/deploy.yml
git commit -m "添加 CI/CD 自动部署流水线"
git push

# 去 GitHub → Actions 标签页看运行结果
# 绿色 ✅ 表示部署成功
```
