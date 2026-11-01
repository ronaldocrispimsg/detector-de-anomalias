import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
import os

SECRET_KEY = os.getenv("NETSPOT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def hash_password(password: str) -> str:
    # O bcrypt possui limite nativo de 72 bytes UTF-8
    pwd_bytes = (password or "").encode('utf-8')
    if len(pwd_bytes) > 72:
        raise ValueError("A senha não pode exceder 72 bytes")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    # Compara a senha digitada com o hash guardado respeitando o limite de 72 bytes do bcrypt
    if not password or not hashed:
        return False
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        return False
    hashed_bytes = hashed.encode('utf-8')
    try:
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except ValueError:
        return False

def create_access_token(data: dict):
    if not SECRET_KEY:
        raise RuntimeError("NETSPOT_SECRET_KEY não configurada no ambiente")
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    if not SECRET_KEY:
        raise RuntimeError("NETSPOT_SECRET_KEY não configurada no ambiente")
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
