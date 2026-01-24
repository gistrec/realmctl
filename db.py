import os

from typing import Optional

from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import sessionmaker, declarative_base


MYSQL_USER     = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_HOST     = os.getenv("MYSQL_HOST")
MYSQL_PORT     = os.getenv("MYSQL_PORT")
MYSQL_DB       = os.getenv("MYSQL_DB")


# Как можно скачать сертификат для подключения к MySQL
# mkdir ~/.mysql
# curl -o ~/.mysql/root.crt https://storage.yandexcloud.net/cloud-certs/CA.pem
ssl_ca_path = os.path.expanduser("~/.mysql/root.crt")
assert os.path.isfile(ssl_ca_path), "Не найден сертификат для подключения к MySQL"

engine = create_engine(f"mysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?ssl_ca={ssl_ca_path}", pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base = declarative_base()


class Setting(Base):
    __tablename__ = 'settings'

    key   = Column(String(64), primary_key=True, nullable=False)
    value = Column(String, nullable=False)


def set_setting(key: str, value: str) -> None:
    with SessionLocal() as session:
        setting = session.get(Setting, key)
        if setting:
            setting.value = value
        else:
            session.add(Setting(key=key, value=value))

        session.commit()


def get_setting(key: str) -> Optional[str]:
    with SessionLocal() as session:
        setting = session.get(Setting, key)
        return setting.value if setting else None


def remove_setting(key: str) -> None:
    with SessionLocal() as session:
        setting = session.get(Setting, key)
        if setting:
            session.delete(setting)
            session.commit()
