"""API de Travel North: CRUD, reglas de reservas y reporte para el tablero."""

import os
import sqlite3
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from analitica import reporte
from db import close_db, get_db, transaction
from validaciones import (
    ErrorAPI, cuerpo_json, validar_destino, validar_paquete, validar_reserva,
)


CAMPOS_DESTINO = ("codigo", "nombre", "pais", "ciudad", "descripcion")
CAMPOS_PAQUETE = (
    "nombre", "descripcion", "precio", "duracion_dias", "fecha_inicio",
    "fecha_fin", "cupo_maximo", "activo", "destino_ids",
)
CAMPOS_RESERVA = (
    "cliente_nombre", "cliente_email", "cantidad_personas", "estado", "paquete_id",
)
ORIGENES = {
    f"http://{host}:{puerto}"
    for host in ("localhost", "127.0.0.1")
    for puerto in (5001, 5002)
}


def buscar(tabla, registro_id):
    # Los nombres de tabla son constantes internas; el identificador es un parámetro.
    if not 1 <= registro_id <= 9223372036854775807:
        raise ErrorAPI("No se encontró el registro solicitado.", 404)
    row = get_db().execute(f"SELECT * FROM {tabla} WHERE id = ?", (registro_id,)).fetchone()
    if row is None:
        raise ErrorAPI("No se encontró el registro solicitado.", 404)
    return row


def ocupados(paquete_id, excluir_reserva=None):
    return get_db().execute(
        """SELECT COALESCE(SUM(cantidad_personas), 0) FROM reservas
           WHERE paquete_id = ? AND estado <> ? AND (? IS NULL OR id <> ?)""",
        (paquete_id, "CANCELADA", excluir_reserva, excluir_reserva),
    ).fetchone()[0]


def paquete_json(row):
    data = dict(row)
    data["precio"] = data.pop("precio_centavos") / 100
    data["activo"] = bool(data["activo"])
    data["destinos"] = [dict(destino) for destino in get_db().execute(
        """SELECT d.* FROM destinos d JOIN paquete_destino pd ON d.id = pd.destino_id
           WHERE pd.paquete_id = ? ORDER BY d.nombre COLLATE NOCASE, d.id""", (row["id"],),
    )]
    data["destino_ids"] = [destino["id"] for destino in data["destinos"]]
    data["cupos_ocupados"] = ocupados(row["id"])
    data["cupos_disponibles"] = row["cupo_maximo"] - data["cupos_ocupados"]
    return data


def reserva_json(row):
    data = dict(row)
    data["total"] = data.pop("total_centavos") / 100
    data["paquete_nombre"] = buscar("paquetes", row["paquete_id"])["nombre"]
    return data


def comprobar_destinos(ids):
    placeholders = ",".join("?" for _ in ids)
    encontrados = get_db().execute(
        f"SELECT COUNT(*) FROM destinos WHERE id IN ({placeholders})", ids
    ).fetchone()[0]
    if encontrados != len(ids):
        raise ErrorAPI("Uno o más destinos seleccionados no existen.", 404)


def guardar_relaciones(connection, paquete_id, ids):
    connection.execute("DELETE FROM paquete_destino WHERE paquete_id = ?", (paquete_id,))
    connection.executemany(
        "INSERT INTO paquete_destino(paquete_id, destino_id) VALUES (?, ?)",
        [(paquete_id, destino_id) for destino_id in ids],
    )


def comprobar_disponibilidad(paquete, data, anterior=None):
    # Cancelar un registro existente permite liberar cupos incluso después del viaje.
    cancelacion_existente = (
        anterior is not None and data["estado"] == "CANCELADA"
        and anterior["paquete_id"] == data["paquete_id"]
    )
    if not cancelacion_existente:
        if not paquete["activo"]:
            raise ErrorAPI("El paquete no está activo para recibir reservas.")
        if paquete["fecha_inicio"] < date.today().isoformat():
            raise ErrorAPI("El viaje ya inició; no se pueden registrar o reactivar reservas.")
    if data["estado"] != "CANCELADA":
        usados = ocupados(paquete["id"], anterior["id"] if anterior else None)
        if usados + data["cantidad_personas"] > paquete["cupo_maximo"]:
            raise ErrorAPI("No hay suficientes cupos para esa cantidad de personas.", 409)


def create_app(config=None):
    application = Flask(__name__)
    application.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", str(Path(__file__).parent / "database" / "travel_north.db")),
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if config:
        application.config.update(config)
    application.json.ensure_ascii = False
    application.teardown_appcontext(close_db)

    @application.before_request
    def revisar_origen():
        origen = request.headers.get("Origin")
        if origen and origen not in ORIGENES:
            raise ErrorAPI("El origen de la solicitud no está permitido.", 403)
        if request.method == "OPTIONS":
            return "", 204

    @application.after_request
    def agregar_cabeceras(response):
        origen = request.headers.get("Origin")
        if origen in ORIGENES:
            response.headers["Access-Control-Allow-Origin"] = origen
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Max-Age"] = "600"
            response.vary.add("Origin")
        response.headers["Cache-Control"] = "no-store"
        return response

    @application.errorhandler(ErrorAPI)
    def error_negocio(error):
        return jsonify(error=error.mensaje), error.codigo

    @application.errorhandler(sqlite3.IntegrityError)
    def error_integridad(_error):
        return jsonify(error="La operación afecta datos relacionados o repite un código o nombre existente."), 409

    @application.errorhandler(sqlite3.OperationalError)
    def error_base(error):
        application.logger.error("No se pudo consultar SQLite: %s", error)
        return jsonify(error="No se pudo acceder a la base de datos. Verifica que init_db.py haya terminado correctamente."), 503

    @application.errorhandler(HTTPException)
    def error_http(error):
        mensajes = {
            400: "La solicitud no es válida.", 404: "La ruta solicitada no existe.",
            405: "El método no está permitido para esta ruta.",
            413: "La solicitud supera el tamaño permitido.",
        }
        return jsonify(error=mensajes.get(error.code, "No se pudo procesar la solicitud.")), error.code

    @application.get("/api/health")
    def health():
        return jsonify(status="UP", application="Travel North API")

    @application.route("/api/destinos", methods=["GET", "POST"])
    def destinos():
        if request.method == "GET":
            return jsonify([dict(row) for row in get_db().execute(
                "SELECT * FROM destinos ORDER BY nombre COLLATE NOCASE, id"
            )])
        data = validar_destino(cuerpo_json(CAMPOS_DESTINO))
        with transaction() as connection:
            cursor = connection.execute(
                """INSERT INTO destinos(codigo, nombre, pais, ciudad, descripcion)
                   VALUES (:codigo, :nombre, :pais, :ciudad, :descripcion)""", data,
            )
            result = dict(buscar("destinos", cursor.lastrowid))
        return jsonify(result), 201

    @application.route("/api/destinos/<int:registro_id>", methods=["GET", "PUT", "DELETE"])
    def destino(registro_id):
        if request.method == "GET":
            return jsonify(dict(buscar("destinos", registro_id)))
        with transaction() as connection:
            buscar("destinos", registro_id)
            if request.method == "DELETE":
                if connection.execute(
                    "SELECT 1 FROM paquete_destino WHERE destino_id = ? LIMIT 1", (registro_id,),
                ).fetchone():
                    raise ErrorAPI("No se puede eliminar un destino asociado a un paquete.", 409)
                connection.execute("DELETE FROM destinos WHERE id = ?", (registro_id,))
                return "", 204
            data = validar_destino(cuerpo_json(CAMPOS_DESTINO))
            data["id"] = registro_id
            connection.execute(
                """UPDATE destinos SET codigo=:codigo, nombre=:nombre, pais=:pais,
                   ciudad=:ciudad, descripcion=:descripcion WHERE id=:id""", data,
            )
            result = dict(buscar("destinos", registro_id))
        return jsonify(result)

    @application.route("/api/paquetes", methods=["GET", "POST"])
    def paquetes():
        if request.method == "GET":
            return jsonify([paquete_json(row) for row in get_db().execute(
                "SELECT * FROM paquetes ORDER BY nombre COLLATE NOCASE, id"
            ).fetchall()])
        data = validar_paquete(cuerpo_json(CAMPOS_PAQUETE))
        with transaction() as connection:
            comprobar_destinos(data["destino_ids"])
            cursor = connection.execute(
                """INSERT INTO paquetes(nombre, descripcion, precio_centavos, duracion_dias,
                   fecha_inicio, fecha_fin, cupo_maximo, activo) VALUES
                   (:nombre, :descripcion, :precio_centavos, :duracion_dias,
                    :fecha_inicio, :fecha_fin, :cupo_maximo, :activo)""", data,
            )
            guardar_relaciones(connection, cursor.lastrowid, data["destino_ids"])
            result = paquete_json(buscar("paquetes", cursor.lastrowid))
        return jsonify(result), 201

    @application.route("/api/paquetes/<int:registro_id>", methods=["GET", "PUT", "DELETE"])
    def paquete(registro_id):
        if request.method == "GET":
            return jsonify(paquete_json(buscar("paquetes", registro_id)))
        with transaction() as connection:
            buscar("paquetes", registro_id)
            if request.method == "DELETE":
                if connection.execute(
                    "SELECT 1 FROM reservas WHERE paquete_id = ? LIMIT 1", (registro_id,),
                ).fetchone():
                    raise ErrorAPI("No se puede eliminar un paquete que tiene reservas.", 409)
                connection.execute("DELETE FROM paquetes WHERE id = ?", (registro_id,))
                return "", 204
            data = validar_paquete(cuerpo_json(CAMPOS_PAQUETE))
            comprobar_destinos(data["destino_ids"])
            if data["cupo_maximo"] < ocupados(registro_id):
                raise ErrorAPI("El cupo máximo no puede ser menor que las personas ya reservadas.", 409)
            data["id"] = registro_id
            connection.execute(
                """UPDATE paquetes SET nombre=:nombre, descripcion=:descripcion,
                   precio_centavos=:precio_centavos, duracion_dias=:duracion_dias,
                   fecha_inicio=:fecha_inicio, fecha_fin=:fecha_fin,
                   cupo_maximo=:cupo_maximo, activo=:activo WHERE id=:id""", data,
            )
            guardar_relaciones(connection, registro_id, data["destino_ids"])
            result = paquete_json(buscar("paquetes", registro_id))
        return jsonify(result)

    @application.route("/api/reservas", methods=["GET", "POST"])
    def reservas():
        if request.method == "GET":
            return jsonify([reserva_json(row) for row in get_db().execute(
                "SELECT * FROM reservas ORDER BY fecha_reserva DESC, id DESC"
            ).fetchall()])
        data = validar_reserva(cuerpo_json(CAMPOS_RESERVA))
        with transaction() as connection:
            selected = buscar("paquetes", data["paquete_id"])
            comprobar_disponibilidad(selected, data)
            data["fecha_reserva"] = date.today().isoformat()
            data["total_centavos"] = selected["precio_centavos"] * data["cantidad_personas"]
            cursor = connection.execute(
                """INSERT INTO reservas(cliente_nombre, cliente_email, fecha_reserva,
                   cantidad_personas, total_centavos, estado, paquete_id) VALUES
                   (:cliente_nombre, :cliente_email, :fecha_reserva,
                    :cantidad_personas, :total_centavos, :estado, :paquete_id)""", data,
            )
            result = reserva_json(buscar("reservas", cursor.lastrowid))
        return jsonify(result), 201

    @application.route("/api/reservas/<int:registro_id>", methods=["GET", "PUT", "DELETE"])
    def reserva(registro_id):
        if request.method == "GET":
            return jsonify(reserva_json(buscar("reservas", registro_id)))
        with transaction() as connection:
            anterior = buscar("reservas", registro_id)
            if request.method == "DELETE":
                connection.execute("DELETE FROM reservas WHERE id = ?", (registro_id,))
                return "", 204
            data = validar_reserva(cuerpo_json(CAMPOS_RESERVA), anterior["estado"])
            selected = buscar("paquetes", data["paquete_id"])
            comprobar_disponibilidad(selected, data, anterior)
            if (data["paquete_id"], data["cantidad_personas"]) == (
                anterior["paquete_id"], anterior["cantidad_personas"]
            ):
                data["total_centavos"] = anterior["total_centavos"]
            else:
                data["total_centavos"] = selected["precio_centavos"] * data["cantidad_personas"]
            data["id"] = registro_id
            connection.execute(
                """UPDATE reservas SET cliente_nombre=:cliente_nombre, cliente_email=:cliente_email,
                   cantidad_personas=:cantidad_personas, total_centavos=:total_centavos,
                   estado=:estado, paquete_id=:paquete_id WHERE id=:id""", data,
            )
            result = reserva_json(buscar("reservas", registro_id))
        return jsonify(result)

    @application.get("/api/analitica/reporte")
    def analitica():
        return jsonify(reporte())

    return application


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
