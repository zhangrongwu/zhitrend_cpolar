from passlib.context import CryptContext

# 创建密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 测试密码
password = "admin"
hashed = pwd_context.hash(password)
print(f"Original password: {password}")
print(f"Hashed password: {hashed}")

# 验证密码
stored_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKxcQw/IIXI79Ni"
is_valid = pwd_context.verify(password, stored_hash)
print(f"\nVerifying password against stored hash:")
print(f"Stored hash: {stored_hash}")
print(f"Is valid: {is_valid}")

# 生成新的哈希用于users.json
print(f"\nNew hash for users.json:")
new_hash = pwd_context.hash("admin")
print(new_hash)
