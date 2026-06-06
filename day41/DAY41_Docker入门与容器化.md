# DAY 41：Docker 基础 + 编写 Dockerfile

**目标**：把 FastAPI 应用打包成 Docker 镜像，在容器里跑起来。

---

## 1. 安装 Docker Desktop

下载地址：https://www.docker.com/products/docker-desktop/

Windows 安装后重启电脑。验证安装：

```bash
docker --version
# 期望输出：Docker version 27.x.x

docker run hello-world
# 期望输出：Hello from Docker!
```

---

## 2. 整理项目文件

在项目根目录新建 `deploy/`，把 day29 的核心文件**复制**进去（不要移动原文件）：

```
deploy/
├── main.py          # 从 day29 复制
├── models.py        # 从 day29 复制
├── database.py      # 从 day29 复制
├── config.py        # 从 day29 复制
├── crud.py          # 从 day29 复制
├── schemas.py       # 从 day29 复制
├── ai.py            # 从 day29 复制
├── auth.py          # 从 day29 复制
├── security.py      # 从 day29 复制
├── requirements.txt # 新建
└── .env.prod        # 新建，生产环境配置
```

**requirements.txt**：

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
python-jose[cryptography]==3.3.0
pydantic-settings==2.7.1
openai==1.59.3
python-dotenv==1.0.1
passlib[bcrypt]==1.7.4
python-multipart==0.0.19
```

> 生产环境用 `psycopg2-binary` 而非 `psycopg2`，避免编译依赖问题。

**.env.prod**（先用假值占位，后面逐步替换）：

```
APP_ENV=prod
DEBUG=false
DATABASE_URL=postgresql://chat_user:你的密码@db:5432/chat_db
SECRET_KEY=改成随机字符串至少32位
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DEEPSEEK_API_KEY=sk-你的deepseekkey
DEFAULT_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
ALLOWED_ORIGINS=http://你的服务器IP,https://你的域名
```

---

## 3. 写 Dockerfile

在 `deploy/` 目录下新建 `Dockerfile`（无后缀名）：

```dockerfile
# 阶段1：构建阶段——安装依赖
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
# 安装依赖到临时目录，不保留缓存
RUN pip install --no-cache-dir --target=/install -r requirements.txt

# 阶段2：运行阶段——只保留必要文件，镜像更小
FROM python:3.11-slim

WORKDIR /app
# 从构建阶段复制已安装的包
COPY --from=builder /install /usr/local/lib/python3.11/site-packages
# 复制应用代码
COPY . .

# 创建非 root 用户，安全最佳实践
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> 多阶段构建：最终镜像约 200MB，如果直接 `pip install` 会膨胀到 600MB+。

---

## 4. 写 .dockerignore

在 `deploy/` 下新建 `.dockerignore`，防止把无关文件打进镜像：

```
__pycache__
*.pyc
.env
.env.*
!.env.prod
.git
.idea
.vscode
venv
*.db
uploads
```

---

_## 5. 构建并运行

```bash
cd D:\AI相关\文件总集\开发学习\deploy

# 构建镜像（第一次比较慢，3-5分钟）
docker build -t myapp:1.0 .

# 查看镜像
docker images | grep myapp

# 试运行
docker run -p 8000:8000 --env-file .env.prod myapp:1.0
```_

打开浏览器访问 `http://localhost:8000/health`，看到 `{"status":"ok"}` 即成功。

---

## 常见问题排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: xxx` | requirements.txt 漏了包 | 补充后重新 build |
| 容器启动后立刻退出 | .env.prod 变量缺失 | `docker logs <容器名>` 查看错误 |
| 端口被占用 | Windows 上 8000 端口冲突 | 改成 `-p 8008:8000` 映射到其他端口 |
