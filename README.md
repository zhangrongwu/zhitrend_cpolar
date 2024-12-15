# Simple NAT Traversal System

这是一个简单的内网穿透系统，类似于cpolar。它允许你将内网服务暴露到公网。

## 功能特性

- 支持TCP隧道
- Web管理界面
- 实时连接状态监控
- 安全的通信加密

## 系统组件

1. 服务器端 (server.py)
   - 处理公网请求
   - 管理客户端连接
   - 提供Web管理界面

2. 客户端 (client.py)
   - 与服务器建立长连接
   - 转发本地服务请求
   - 支持多隧道配置

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

1. 启动服务器：
```bash
python server.py
```

2. 启动客户端：
```bash
python client.py
```

3. 访问管理界面：
http://localhost:8080

## 配置说明

在运行之前，请确保创建 .env 文件并设置以下环境变量：

```
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
JWT_SECRET=your_jwt_secret
```
