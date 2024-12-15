import asyncio
import json
import logging
import os
from typing import Dict, Set
import uuid
import websockets
from fastapi import FastAPI, WebSocket, HTTPException, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
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

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

# 用户数据存储
def load_users():
    try:
        with open('users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # 如果文件不存在，创建默认管理员账户
        default_users = {
            "admin": {
                "username": "admin",
                "hashed_password": get_password_hash("admin"),
                "disabled": False
            }
        }
        save_users(default_users)
        return default_users

def save_users(users):
    with open('users.json', 'w') as f:
        json.dump(users, f, indent=4)

# 初始化用户数据
users_db = load_users()

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

# 用户认证相关函数
def get_user(username: str):
    if username in users_db:
        user_dict = users_db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def verify_password(plain_password, hashed_password):
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except:
        return False

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = get_user(username)
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# 认证相关API
@app.post("/api/register")
async def register(user: UserCreate):
    if user.username in users_db:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    hashed_password = get_password_hash(user.password)
    users_db[user.username] = {
        "username": user.username,
        "hashed_password": hashed_password,
        "disabled": False
    }
    save_users(users_db)  # 保存到文件
    return {"message": "User created successfully"}

@app.post("/api/login", response_model=Token)
async def login(form_data: UserLogin):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 生成token
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # 返回token
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

# Web界面路由
@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def get_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse)
async def get_admin_panel(request: Request, token: str | None = None):
    try:
        # 从查询参数获取token
        if not token:
            return RedirectResponse(url="/login")
            
        # 验证token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return RedirectResponse(url="/login")
            
        user = get_user(username)
        if not user:
            return RedirectResponse(url="/login")
            
        return templates.TemplateResponse(
            "admin.html",
            {
                "request": request,
                "username": username,
                "active_connections": len(manager.active_connections),
                "tunnels": manager.tunnels
            }
        )
    except JWTError:
        return RedirectResponse(url="/login")

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

# API路由
@app.get("/api/tunnels")
async def list_tunnels(current_user: User = Depends(get_current_user)):
    return manager.tunnels

@app.post("/api/tunnels")
async def create_tunnel(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    try:
        data = await request.json()
        logger.info(f"Received tunnel creation request: {data}")
        
        # 检查必需字段
        if 'local_port' not in data or 'public_port' not in data:
            logger.error("Missing required fields in request")
            raise HTTPException(status_code=400, detail="Missing required fields: local_port and public_port are required")
        
        local_port = data.get("local_port")
        public_port = data.get("public_port")
        custom_domain = data.get("custom_domain")
        
        # 验证端口值
        if not isinstance(local_port, int) or not isinstance(public_port, int):
            logger.error(f"Invalid port values: local_port={local_port}, public_port={public_port}")
            raise HTTPException(status_code=400, detail="Port values must be integers")
            
        if local_port < 1 or local_port > 65535 or public_port < 1 or public_port > 65535:
            logger.error(f"Port values out of range: local_port={local_port}, public_port={public_port}")
            raise HTTPException(status_code=400, detail="Port values must be between 1 and 65535")
            
        # 检查端口是否已被使用
        for tunnel in manager.tunnels.values():
            if tunnel["public_port"] == public_port:
                logger.error(f"Public port {public_port} already in use")
                raise HTTPException(status_code=400, detail=f"Public port {public_port} is already in use")
        
        # 验证自定义域名
        if custom_domain:
            if not isinstance(custom_domain, str):
                logger.error(f"Invalid domain type: {type(custom_domain)}")
                raise HTTPException(status_code=400, detail="Custom domain must be a string")
                
            custom_domain = custom_domain.strip()
            if not custom_domain:
                custom_domain = None
            elif custom_domain in manager.domain_mappings:
                logger.error(f"Domain {custom_domain} already in use")
                raise HTTPException(status_code=400, detail=f"Domain {custom_domain} is already in use")
            
        # 创建隧道
        client_id = str(uuid.uuid4())
        logger.info(f"Creating new tunnel with ID {client_id}")
        manager.register_tunnel(client_id, local_port, public_port, custom_domain)
        
        # 返回成功响应
        response_data = {
            "client_id": client_id,
            "status": "success",
            "local_port": local_port,
            "public_port": public_port,
            "custom_domain": custom_domain
        }
        logger.info(f"Tunnel created successfully: {response_data}")
        return response_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except ValueError as e:
        logger.error(f"Value error in request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating tunnel: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
        reload=True,  # 启用热重载
        reload_dirs=["templates", "."],  # 监视这些目录的变化
        reload_delay=0.25  # 重载延迟，防止过于频繁
    )
