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
# 让系统能找到 pip 安装的命令（uvicorn 等）
ENV PATH="/usr/local/lib/python3.11/site-packages/bin:$PATH"
# 复制应用代码
COPY . .

# 创建非 root 用户，安全最佳实践
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]