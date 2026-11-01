from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from Backend.database import get_db
from Backend.models import User
from Backend.security import decode_token

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    request: Request = None,
):
    try:
        payload = decode_token(credentials.credentials)
        username = payload.get("sub")

        user = db.query(User).filter(User.username == username).first()

        if not user:
            raise HTTPException(status_code=401, detail="Usuário não encontrado")

        if user.locked:
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            if user.locked_until and user.locked_until <= now_utc:
                user.locked = False
                user.locked_until = None
                user.attempts = 0
                db.commit()
            else:
                raise HTTPException(status_code=403, detail="Conta de usuário bloqueada")

        if getattr(user, "must_change_password", False):
            path = request.url.path if (request is not None and getattr(request, "url", None)) else ""
            if not path.endswith(("/auth/first-password", "/auth/change-password")):
                raise HTTPException(
                    status_code=403,
                    detail="Troca de senha obrigatória antes de acessar os recursos do sistema",
                )

        return user

    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
    
def get_current_admin(user: User = Depends(get_current_user)):
    is_admin = bool(getattr(user, "is_admin", False) or getattr(user, "username", "") == "admin")
    if not is_admin:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return user
