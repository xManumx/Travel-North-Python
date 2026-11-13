"""Agregaciones SQL del reporte. Los importes se convierten a COP al responder."""

from datetime import datetime, timezone

from db import get_db


def reporte():
    connection = get_db()
    # Una sola lectura transaccional mantiene coherencia entre KPI y series.
    connection.execute("BEGIN")
    try:
        kpis = dict(connection.execute(
            """SELECT
                (SELECT COUNT(*) FROM destinos) AS destinos_registrados,
                (SELECT COUNT(*) FROM paquetes WHERE activo = 1) AS paquetes_activos,
                (SELECT COUNT(*) FROM reservas WHERE estado <> ?) AS reservas_vigentes,
                (SELECT COALESCE(SUM(cantidad_personas), 0) FROM reservas
                    WHERE estado <> ?) AS personas_reservadas,
                (SELECT COALESCE(SUM(total_centavos), 0) FROM reservas
                    WHERE estado = ?) AS valor_confirmado""",
            ("CANCELADA", "CANCELADA", "CONFIRMADA"),
        ).fetchone())
        kpis["valor_confirmado"] /= 100

        meses = [dict(row) for row in connection.execute(
            """SELECT substr(fecha_reserva, 1, 7) AS label, COUNT(*) AS value
               FROM reservas WHERE estado <> ? GROUP BY label ORDER BY label""",
            ("CANCELADA",),
        )]
        if meses:
            conteos = {row["label"]: row["value"] for row in meses}
            anio, mes = map(int, meses[0]["label"].split("-"))
            ultimo = meses[-1]["label"]
            meses = []
            while f"{anio:04d}-{mes:02d}" <= ultimo:
                etiqueta = f"{anio:04d}-{mes:02d}"
                meses.append({"label": etiqueta, "value": conteos.get(etiqueta, 0)})
                anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)

        paquetes = [dict(row) for row in connection.execute(
            """SELECT p.id, p.nombre AS label, COUNT(*) AS value
               FROM reservas r JOIN paquetes p ON p.id = r.paquete_id
               WHERE r.estado <> ? GROUP BY p.id, p.nombre
               ORDER BY value DESC, p.nombre COLLATE NOCASE, p.id LIMIT 5""",
            ("CANCELADA",),
        )]
        conteos_estado = dict(connection.execute(
            "SELECT estado, COUNT(*) FROM reservas GROUP BY estado"
        ).fetchall())
        estados = [{"label": estado, "value": conteos_estado.get(estado, 0)}
                   for estado in ("PENDIENTE", "CONFIRMADA", "CANCELADA")]

        valores = []
        for row in connection.execute(
            """SELECT p.id, p.nombre AS label, SUM(r.total_centavos) AS value
               FROM reservas r JOIN paquetes p ON p.id = r.paquete_id
               WHERE r.estado = ? GROUP BY p.id, p.nombre
               ORDER BY value DESC, p.nombre COLLATE NOCASE, p.id""",
            ("CONFIRMADA",),
        ):
            item = dict(row)
            item["value"] /= 100
            valores.append(item)

        viajeros = [dict(row) for row in connection.execute(
            """SELECT d.id, d.nombre || ' - ' || d.ciudad AS label,
                      SUM(r.cantidad_personas) AS value
               FROM reservas r
               JOIN paquete_destino pd ON pd.paquete_id = r.paquete_id
               JOIN destinos d ON d.id = pd.destino_id
               WHERE r.estado <> ? GROUP BY d.id, d.nombre, d.ciudad
               ORDER BY value DESC, d.nombre COLLATE NOCASE, d.id""",
            ("CANCELADA",),
        )]
    finally:
        connection.rollback()

    return {
        "meta": {
            "generado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "moneda": "COP",
            "fuente": "SQLite",
        },
        "kpis": kpis,
        "series": {
            "reservas_por_mes": meses,
            "paquetes_mas_reservados": paquetes,
            "reservas_por_estado": estados,
            "valor_por_paquete": valores,
            "viajeros_por_destino": viajeros,
        },
    }
