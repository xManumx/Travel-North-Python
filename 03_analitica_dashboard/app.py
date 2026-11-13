"""Servidor de la interfaz analítica de Travel North."""

import os

from flask import Flask, render_template


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        API_BASE_URL=os.getenv("API_BASE_URL", "http://127.0.0.1:5000/api"),
        FRONTEND_URL=os.getenv("FRONTEND_URL", "http://127.0.0.1:5001"),
    )
    if config:
        app.config.update(config)

    @app.get("/")
    def dashboard():
        return render_template(
            "dashboard.html",
            api_report_url=app.config["API_BASE_URL"].rstrip("/") + "/analitica/reporte",
            frontend_url=app.config["FRONTEND_URL"],
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)
