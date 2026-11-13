"""Crea las tablas y los índices sin borrar registros existentes."""

from app import app
from db import init_db


if __name__ == "__main__":
    with app.app_context():
        init_db()
    print("Base de datos lista. Los registros existentes se conservaron.")
