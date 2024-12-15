# 内网穿透服务部署指南

本文档介绍如何将内网穿透服务部署到公网，并配置 Cloudflare。

## 1. 准备工作

### 1.1 域名准备
1. 注册一个域名（如果没有）
2. 将域名添加到 Cloudflare
   - 注册 Cloudflare 账号
   - 添加你的域名
   - 按照 Cloudflare 的指引修改域名的 NS 记录
   - 等待域名解析生效（通常需要 24 小时内）

### 1.2 服务器准备
1. 购买云服务器（推荐配置）：
   - CPU: 1核或以上
   - 内存: 2GB或以上
   - 系统: Ubuntu 20.04 LTS
   - 带宽: 5Mbps以上

2. 安全组/防火墙配置：
   - 开放 80 端口 (HTTP)
   - 开放 443 端口 (HTTPS)
   - 开放 8080 端口（管理界面）
   - 开放你计划使用的其他端口

## 2. 服务器配置

### 2.1 基础环境安装
```bash
# 更新系统
sudo apt update
sudo apt upgrade -y

# 安装 Python 和依赖
sudo apt install python3 python3-pip python3-venv nginx -y

# 安装 certbot（用于 SSL 证书）
sudo apt install certbot python3-certbot-nginx -y
```

### 2.2 项目部署
1. 创建项目目录：
```bash
mkdir -p /var/www/tunnel
cd /var/www/tunnel
```

2. 创建虚拟环境：
```bash
python3 -m venv venv
source venv/bin/activate
```

3. 克隆项目并安装依赖：
```bash
git clone [你的项目地址]
cd [项目目录]
pip install -r requirements.txt
```

4. 创建环境变量文件：
```bash
cat > .env << EOF
SERVER_HOST=0.0.0.0
SERVER_PORT=8080
JWT_SECRET=your_secure_jwt_secret
SERVER_URL=wss://your-domain.com
EOF
```

### 2.3 配置 Systemd 服务
```bash
sudo nano /etc/systemd/system/tunnel.service
```

添加以下内容：
```ini
[Unit]
Description=Tunnel Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/tunnel
Environment="PATH=/var/www/tunnel/venv/bin"
ExecStart=/var/www/tunnel/venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8080

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl start tunnel
sudo systemctl enable tunnel
```

## 3. Nginx 配置

### 3.1 创建 Nginx 配置文件
```bash
sudo nano /etc/nginx/sites-available/tunnel
```

添加以下内容：
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/tunnel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 4. SSL 证书配置

### 4.1 使用 Certbot 获取证书
```bash
sudo certbot --nginx -d your-domain.com
```

## 5. Cloudflare 配置

### 5.1 DNS 设置
1. 在 Cloudflare DNS 设置中添加 A 记录：
   - 类型: A
   - 名称: @
   - 内容: [你的服务器 IP]
   - 代理状态: 已代理（橙色云朵）

### 5.2 SSL/TLS 设置
1. 进入 SSL/TLS 设置
2. 加密模式选择：
   - 选择 "Full" 或 "Full (Strict)"

### 5.3 Page Rules（可选）
1. 创建 Page Rule：
   - URL 匹配: `*your-domain.com/proxy/*`
   - 设置:
     - Cache Level: Bypass
     - SSL: Full
     - WebSocket: On

## 6. 安全建议

1. 更改默认端口
2. 配置防火墙规则
3. 启用 Cloudflare 的安全功能：
   - Web 应用防火墙（WAF）
   - DDoS 防护
   - Rate Limiting

## 7. 维护和监控

### 7.1 日志查看
```bash
# 查看服务日志
sudo journalctl -u tunnel -f

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 7.2 服务管理
```bash
# 重启服务
sudo systemctl restart tunnel

# 查看状态
sudo systemctl status tunnel
```

### 7.3 备份
定期备份重要文件：
```bash
# 备份配置文件
sudo cp /var/www/tunnel/.env /var/www/tunnel/.env.backup
sudo cp /var/www/tunnel/users.json /var/www/tunnel/users.json.backup
```

## 8. 故障排除

1. 检查服务状态：
```bash
sudo systemctl status tunnel
sudo systemctl status nginx
```

2. 检查端口占用：
```bash
sudo netstat -tulpn | grep LISTEN
```

3. 检查防火墙规则：
```bash
sudo ufw status
```

4. 检查日志：
```bash
sudo journalctl -u tunnel -n 100
```

## 9. 更新维护

1. 代码更新：
```bash
cd /var/www/tunnel
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart tunnel
```

2. 系统更新：
```bash
sudo apt update
sudo apt upgrade -y
```

## 10. 性能优化

1. 启用 Nginx 缓存
2. 配置 worker_processes
3. 优化 Python 性能
4. 使用 Cloudflare 的 CDN 功能

## 注意事项

1. 确保所有密码和密钥的安全性
2. 定期更新系统和依赖
3. 监控服务器资源使用情况
4. 定期备份数据
5. 设置监控告警
