# DAY 45：里程碑——本地环境完整验收

**目标**：在本地 Docker 环境跑通全流程，一切正常后才上云。

> 原则：每一关过了再过下一关。本地没跑通之前，绝对不要上云服务器。

---

## 1. 启动完整环境

```powershell
cd D:\AI相关\文件总集\开发学习\deploy

# 全新启动
docker compose down -v
docker compose up -d

# 等待所有服务就绪
docker compose ps
# 确认四个容器都是 healthy/up
```

---

## 2. 验收清单

### A. 健康检查

```powershell
curl.exe http://localhost/health
# 期望：{"status":"ok","env":"prod","debug":false,"version":"1.0.0"}
```

### B. 用户注册

```powershell
curl.exe -X POST http://localhost/register -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"Test123456"}'
# 期望返回用户信息（id, email, role, is_active）
```

### C. 用户登录

```powershell
curl.exe -X POST http://localhost/login -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"Test123456"}'
# 期望返回 user + token
# 把 access_token 复制下来
```

### D. 带认证的 AI 对话

```powershell
# 替换 YOUR_TOKEN
curl.exe -X POST http://localhost/chat -H "Content-Type: application/json" -H "Authorization: Bearer YOUR_TOKEN" -d '{"message":"你好，请用一句话介绍自己","model":"deepseek-v4-pro"}'
# 期望返回 AI 回复 + token_count
```

### E. Swagger 文档

浏览器打开 `http://localhost/docs`，右上角 Authorize 填入 token，测试 `/chat` 接口。

### F. Nginx 日志

```powershell
docker compose exec nginx cat /var/log/nginx/access.log
# 确认能看见刚才的请求记录
```

### G. 压力测试（简化版）

```powershell
# 连续发 20 个健康检查请求（PowerShell 版）
1..20 | ForEach-Object { curl.exe -s http://localhost/health }
echo "全部完成"
# 所有请求都返回 200
```

---

## 3. 保存进度

```bash
cd D:\AI相关\文件总集\开发学习
git add deploy/
git commit -m "DAY 41-45: Docker 化完成，本地环境验收通过"
git tag day45-milestone
```

---

## 4. 今天不做的事（留给后面）

- ❌ 不上云（DAY 46）
- ❌ 不做 CI/CD（DAY 47）
- ❌ 不做监控（DAY 50）
- ❌ 不做限流（DAY 49）
