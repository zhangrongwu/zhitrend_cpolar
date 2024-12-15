import asyncio
import json
import logging
import websockets
import aiohttp
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TunnelClient:
    def __init__(self, server_url, local_port, public_port, custom_domain=None):
        self.server_url = server_url
        self.local_port = local_port
        self.public_port = public_port
        self.custom_domain = custom_domain
        self.websocket = None
        self.client_id = None
        self.running = False
        
    async def connect_websocket(self):
        while True:
            try:
                async with websockets.connect(f"{self.server_url}/ws/{self.client_id}") as websocket:
                    self.websocket = websocket
                    logger.info("Connected to server")
                    
                    # 发送隧道请求
                    await self.send_tunnel_request()
                    
                    # 保持连接并处理消息
                    while True:
                        message = await websocket.recv()
                        await self.handle_message(message)
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Connection closed, attempting to reconnect...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Error in websocket connection: {str(e)}")
                await asyncio.sleep(5)
                
    async def send_tunnel_request(self):
        request = {
            "type": "tunnel_request",
            "local_port": self.local_port,
            "public_port": self.public_port,
            "custom_domain": self.custom_domain
        }
        await self.websocket.send(json.dumps(request))
        
    async def handle_message(self, message):
        try:
            data = json.loads(message)
            if data["type"] == "tunnel_request":
                # 处理新的隧道请求
                await self.handle_tunnel_request(data)
            elif data["type"] == "tunnel_response":
                logger.info(f"Tunnel response received: {data['status']}")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received: {message}")
            
    async def handle_tunnel_request(self, data):
        try:
            # 创建到本地服务的连接
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method=data["method"],
                    url=f"http://localhost:{self.local_port}{data['path']}",
                    headers=data["headers"],
                    data=data.get("body")
                ) as response:
                    # 将响应发送回服务器
                    response_data = {
                        "type": "tunnel_response",
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": await response.text()
                    }
                    await self.websocket.send(json.dumps(response_data))
        except Exception as e:
            logger.error(f"Error handling tunnel request: {str(e)}")
            error_response = {
                "type": "tunnel_response",
                "status": 500,
                "error": str(e)
            }
            await self.websocket.send(json.dumps(error_response))
            
    async def start(self):
        self.running = True
        self.client_id = os.urandom(16).hex()
        await self.connect_websocket()
        
    async def stop(self):
        self.running = False
        if self.websocket:
            await self.websocket.close()

async def main():
    # 从环境变量或配置文件获取这些值
    server_url = os.getenv("SERVER_URL", "ws://localhost:8080")
    local_port = int(os.getenv("LOCAL_PORT", "8000"))
    public_port = int(os.getenv("PUBLIC_PORT", "8888"))
    custom_domain = os.getenv("CUSTOM_DOMAIN")
    
    client = TunnelClient(server_url, local_port, public_port, custom_domain)
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Shutting down client...")
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main())
