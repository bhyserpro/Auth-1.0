from sqlalchemy import Column, Integer, String, DateTime  # Добавлен DateTime
from sqlalchemy.sql import func
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    attempts = Column(Integer, default=0)
    blocked_until = Column(DateTime(timezone=True), nullable=True)  # Исправлено
    ip_address = Column(String)                       # IP-адрес (опционально)