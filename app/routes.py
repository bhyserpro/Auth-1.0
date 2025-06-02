from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models, schemas, auth, database
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, status

# Константы
MAX_ATTEMPTS = 3               # Максимальное количество попыток
BLOCK_TIME_MINUTES = 1        # Время блокировки в минутах


router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    token = auth.create_access_token(data={"sub": db_user.username})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/token", response_model=schemas.Token)
def login(
    request: Request,  
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Получаем или создаем запись о попытках входа
    attempt = db.query(models.LoginAttempt).filter(
        models.LoginAttempt.username == form_data.username
    ).first()
    
    if not attempt:
        attempt = models.LoginAttempt(
            username=form_data.username,
            ip_address=request.client.host,  # Сохраняем IP
            attempts=0
        )
        db.add(attempt)
        db.commit()

    # Проверяем блокировку
    if attempt.blocked_until and datetime.now(timezone.utc) < attempt.blocked_until:
        remaining_time = attempt.blocked_until - datetime.now(timezone.utc)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Аккаунт заблокирован. Попробуйте через {int(remaining_time.total_seconds() / 60)} минут"
        )

    # Проверяем пароль
    user = db.query(models.User).filter(
        models.User.username == form_data.username
    ).first()
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        # Увеличиваем счетчик попыток
        attempt.attempts += 1
        
        
        if attempt.attempts >= MAX_ATTEMPTS:
            attempt.blocked_until = datetime.now(timezone.utc) + timedelta(minutes=BLOCK_TIME_MINUTES)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Слишком много попыток. Аккаунт заблокирован до {attempt.blocked_until}"
            )
        
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверный логин или пароль. Осталось попыток: {MAX_ATTEMPTS - attempt.attempts}"
        )

    # Сбрасываем счетчик при успешном входе
    attempt.attempts = 0
    attempt.blocked_until = None
    db.commit()

    # Генерируем токен
    token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = auth.decode_token(token)
        username = payload.get("sub")
        return {"username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")