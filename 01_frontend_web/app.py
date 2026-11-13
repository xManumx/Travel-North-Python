"""Interfaz de gestión de Travel North. Los datos se consultan mediante la API."""

import os
from urllib.parse import urlsplit

from flask import Flask, render_template


def _validar_url(valor, nombre):
    """La configuración acepta direcciones HTTP; nunca código del navegador."""
    if not isinstance(valor, str):
        raise ValueError(f"{nombre} debe ser una dirección HTTP o HTTPS.")
    valor = valor.strip().rstrip("/")
    partes = urlsplit(valor)
    if (
        partes.scheme not in {"http", "https"}
        or not partes.hostname
        or partes.username
        or partes.password
        or partes.query
        or partes.fragment
        or any(caracter.isspace() for caracter in valor)
    ):
        raise ValueError(f"{nombre} debe ser una dirección HTTP o HTTPS sin credenciales.")
    return valor


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        API_BASE_URL=os.getenv("API_BASE_URL", "http://127.0.0.1:5000/api"),
        DASHBOARD_URL=os.getenv("DASHBOARD_URL", "http://127.0.0.1:5002"),
    )
    if config:
        app.config.update(config)
    for nombre in ("API_BASE_URL", "DASHBOARD_URL"):
        app.config[nombre] = _validar_url(app.config[nombre], nombre)

    @app.get("/")
    def inicio():
        return render_template(
            "index.html",
            dashboard_url=app.config["DASHBOARD_URL"],
            configuracion={"apiBaseUrl": app.config["API_BASE_URL"]},
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
