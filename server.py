import asyncio
import json
import logging
import os
from typing import Dict, Set
import uuid
import websockets
from fastapi import FastAPI, WebSocket, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI应用
app = FastAPI()

# 模板引擎
templates = Jinja2Templates(directory="templates")

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 安全相关配置
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 数据模型
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

# 连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.tunnels: Dict[str, Dict] = {}
        self.domain_mappings: Dict[str, str] = {}  # 域名到客户端ID的映射
        
    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")
        
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            # 删除相关的域名映射
            for domain, cid in list(self.domain_mappings.items()):
                if cid == client_id:
                    del self.domain_mappings[domain]
            logger.info(f"Client {client_id} disconnected")
            
    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)
            
    def register_tunnel(self, client_id: str, local_port: int, public_port: int, custom_domain: str = None):
        self.tunnels[client_id] = {
            "local_port": local_port,
            "public_port": public_port,
            "custom_domain": custom_domain,
            "created_at": datetime.now().isoformat()
        }
        if custom_domain:
            self.domain_mappings[custom_domain] = client_id
            
    def get_tunnel_info(self, client_id: str):
        return self.tunnels.get(client_id)

manager = ConnectionManager()

# 用户认证
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    return token_data

# WebSocket路由
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message["type"] == "tunnel_request":
                    manager.register_tunnel(
                        client_id,
                        message["local_port"],
                        message["public_port"],
                        message.get("custom_domain")
                    )
                    await websocket.send_text(json.dumps({
                        "type": "tunnel_response",
                        "status": "success"
                    }))
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received: {data}")
    except websockets.exceptions.WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"Error in websocket connection: {str(e)}")
        manager.disconnect(client_id)

# Web界面路由
@app.get("/", response_class=HTMLResponse)
async def get_admin_panel(request: Request):
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "active_connections": len(manager.active_connections),
            "tunnels": manager.tunnels
        }
    )

# API路由
@app.post("/api/tunnels")
async def create_tunnel(
    local_port: int,
    public_port: int,
    custom_domain: str = None,
    current_user: User = Depends(get_current_user)
):
    client_id = str(uuid.uuid4())
    # 检查域名是否已被使用
    if custom_domain and custom_domain in manager.domain_mappings:
        raise HTTPException(status_code=400, detail="Domain already in use")
    manager.register_tunnel(client_id, local_port, public_port, custom_domain)
    return {"client_id": client_id, "status": "success", "custom_domain": custom_domain}

@app.get("/api/tunnels")
async def list_tunnels(current_user: User = Depends(get_current_user)):
    return manager.tunnels

@app.delete("/api/tunnels/{client_id}")
async def delete_tunnel(
    client_id: str,
    current_user: User = Depends(get_current_user)
):
    if client_id in manager.tunnels:
        del manager.tunnels[client_id]
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Tunnel not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host=os.getenv("SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", 8080)),
        reload=True
    )
