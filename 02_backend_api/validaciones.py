"""Reglas de entrada compartidas por los formularios de la API."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import request


class ErrorAPI(Exception):
    def __init__(self, mensaje, codigo=400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo


def cuerpo_json(campos):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ErrorAPI("Envía un objeto JSON válido.")
    if set(data) - set(campos):
        raise ErrorAPI("La solicitud contiene campos no permitidos.")
    return data


def texto(data, campo, maximo, requerido=True):
    value = data.get(campo)
    if value is None and not requerido:
        return None
    if not isinstance(value, str):
        raise ErrorAPI(f"{campo}: debe ser un texto.")
    value = value.strip()
    if not value:
        if requerido:
            raise ErrorAPI(f"{campo}: es obligatorio.")
        return None
    if len(value) > maximo:
        raise ErrorAPI(f"{campo}: admite hasta {maximo} caracteres.")
    return value


def entero(value, campo, maximo=1000000):
    if type(value) is not int or not 1 <= value <= maximo:
        raise ErrorAPI(f"{campo}: debe ser un entero entre 1 y {maximo}.")
    return value


def fecha(data, campo):
    value = data.get(campo)
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ErrorAPI(f"{campo}: usa una fecha válida con formato AAAA-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ErrorAPI(f"{campo}: la fecha no existe.") from None


def precio_centavos(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ErrorAPI("precio: debe ser un número positivo con máximo dos decimales.")
    try:
        decimal = Decimal(str(value))
    except InvalidOperation:
        raise ErrorAPI("precio: debe ser un número válido.") from None
    if not decimal.is_finite() or not Decimal("0.01") <= decimal <= Decimal("99999999.99"):
        raise ErrorAPI("precio: debe estar entre 0.01 y 99999999.99 COP.")
    centavos = decimal * 100
    if centavos != centavos.to_integral_value():
        raise ErrorAPI("precio: admite máximo dos decimales.")
    return int(centavos)


def validar_destino(data):
    return {
        "codigo": texto(data, "codigo", 10).upper(),
        "nombre": texto(data, "nombre", 100),
        "pais": texto(data, "pais", 60),
        "ciudad": texto(data, "ciudad", 60),
        "descripcion": texto(data, "descripcion", 500, False),
    }


def validar_paquete(data):
    inicio = fecha(data, "fecha_inicio")
    fin = fecha(data, "fecha_fin")
    if inicio < date.today():
        raise ErrorAPI("La fecha de inicio no puede estar en el pasado.")
    if fin < inicio:
        raise ErrorAPI("La fecha de fin debe ser igual o posterior a la fecha de inicio.")
    activo = data.get("activo", True)
    if type(activo) is not bool:
        raise ErrorAPI("activo: debe ser verdadero o falso.")
    ids = data.get("destino_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
        raise ErrorAPI("Selecciona entre 1 y 100 destinos.")
    for destino_id in ids:
        entero(destino_id, "destino_ids", 9223372036854775807)
    if len(set(ids)) != len(ids):
        raise ErrorAPI("No repitas destinos dentro del paquete.")
    return {
        "nombre": texto(data, "nombre", 120),
        "descripcion": texto(data, "descripcion", 1000, False),
        "precio_centavos": precio_centavos(data.get("precio")),
        "duracion_dias": entero(data.get("duracion_dias"), "duracion_dias", 3650),
        "fecha_inicio": inicio.isoformat(),
        "fecha_fin": fin.isoformat(),
        "cupo_maximo": entero(data.get("cupo_maximo"), "cupo_maximo"),
        "activo": int(activo),
        "destino_ids": ids,
    }


def validar_reserva(data, estado_anterior="PENDIENTE"):
    email = texto(data, "cliente_email", 160).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ErrorAPI("cliente_email: escribe un correo válido.")
    estado = data.get("estado", estado_anterior)
    if not isinstance(estado, str) or estado not in {"PENDIENTE", "CONFIRMADA", "CANCELADA"}:
        raise ErrorAPI("estado: usa PENDIENTE, CONFIRMADA o CANCELADA.")
    return {
        "cliente_nombre": texto(data, "cliente_nombre", 120),
        "cliente_email": email,
        "cantidad_personas": entero(data.get("cantidad_personas"), "cantidad_personas"),
        "estado": estado,
        "paquete_id": entero(data.get("paquete_id"), "paquete_id", 9223372036854775807),
    }
