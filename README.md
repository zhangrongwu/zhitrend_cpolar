# 内网穿透管理系统

一个基于 FastAPI 的内网穿透管理系统，支持用户认证、隧道管理等功能。

## 功能特性

- 用户认证（JWT）
- 隧道管理
- 实时监控
- 自定义域名支持

## 系统要求

- Python 3.7+
- pip（Python 包管理器）
- 现代浏览器（支持 ES6+）

## 安装部署

1. 克隆项目：
```bash
git clone [项目地址]
cd zhitrend_cpolar
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
创建 `.env` 文件并设置以下变量：
```
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
JWT_SECRET=your_jwt_secret_key
SERVER_URL=ws://localhost:8080
LOCAL_PORT=8000
PUBLIC_PORT=8888
```

4. 启动服务：
```bash
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

## 验证指南

### 1. 用户注册和登录

1. 访问 http://localhost:8080/admin
2. 点击"注册"，填写用户信息
3. 使用注册的账号登录系统

### 2. 创建隧道

1. 登录后，在管理界面填写隧道信息：
   - 本地端口：要暴露的本地服务端口（如 8000）
   - 公网端口：外部访问端口（如 8888）
   - 自定义域名：（可选）

2. 点击"创建隧道"按钮

### 3. 验证隧道

1. **本地服务验证**：
   ```bash
   # 启动一个测试服务在本地端口
   python -m http.server 8000
   ```

2. **隧道连接验证**：
   - 通过公网端口访问：http://localhost:8888
   - 如果配置了自定义域名：http://your-domain:8888

3. **检查连接状态**：
   - 在管理界面查看隧道状态
   - 检查服务器日志：`tail -f server.log`

### 4. 常见问题排查

1. **端口被占用**：
   ```bash
   # 检查端口占用
   lsof -i :8000
   lsof -i :8888
   ```

2. **连接失败**：
   - 检查防火墙设置
   - 确认本地服务是否正常运行
   - 查看服务器日志中的错误信息

## API 文档

### 认证接口

- POST `/api/register` - 用户注册
- POST `/api/login` - 用户登录

### 隧道管理

- GET `/api/tunnels` - 获取隧道列表
- POST `/api/tunnels` - 创建新隧道
- DELETE `/api/tunnels/{client_id}` - 删除隧道

## 安全建议

1. 修改默认的 JWT 密钥
2. 使用强密码
3. 定期更新系统和依赖
4. 限制可用端口范围
5. 启用 HTTPS

## 监控和维护

1. **日志监控**：
```bash
tail -f server.log
```

2. **系统状态**：
- 访问管理界面查看实时状态
- 检查资源使用情况

3. **备份**：
定期备份用户数据和配置文件：
```bash
cp users.json users.json.backup
cp .env .env.backup
```

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 发起 Pull Request

## 许可证

[许可证类型]

## 联系方式

[联系信息]
