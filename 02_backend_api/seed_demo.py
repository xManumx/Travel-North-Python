"""Carga un escenario ficticio de seis meses únicamente cuando la base está vacía."""

from datetime import date, timedelta

from app import app
from db import init_db, transaction


def seed_demo():
    init_db()
    hoy = date.today()
    with transaction() as connection:
        if any(connection.execute(f"SELECT 1 FROM {tabla} LIMIT 1").fetchone()
               for tabla in ("destinos", "paquetes", "reservas")):
            return False

        destinos = [
            ("BOG", "Centro histórico", "Colombia", "Bogotá", "Recorrido cultural por la capital."),
            ("MED", "Valle de Aburrá", "Colombia", "Medellín", "Naturaleza y cultura en Antioquia."),
            ("CTG", "Ciudad amurallada", "Colombia", "Cartagena", "Patrimonio y costa Caribe."),
            ("SMR", "Parque Tayrona", "Colombia", "Santa Marta", "Senderos y playas del Caribe."),
            ("ADZ", "Mar de siete colores", "Colombia", "San Andrés", "Experiencia insular."),
            ("GUA", "Piedra del Peñol", "Colombia", "Guatapé", "Paisajes y arquitectura tradicional."),
        ]
        destino_ids = []
        for values in destinos:
            cursor = connection.execute(
                "INSERT INTO destinos(codigo,nombre,pais,ciudad,descripcion) VALUES (?,?,?,?,?)", values
            )
            destino_ids.append(cursor.lastrowid)

        ofertas = [
            ("Bogotá cultural", 45000000, 3, [0]),
            ("Escapada antioqueña", 62000000, 4, [1, 5]),
            ("Cartagena histórica", 89000000, 4, [2]),
            ("Tayrona natural", 78000000, 5, [3]),
            ("San Andrés en familia", 125000000, 5, [4]),
            ("Ruta del Caribe", 98000000, 6, [2, 3]),
        ]
        paquetes = []
        for indice, (nombre, centavos, duracion, destinos_oferta) in enumerate(ofertas):
            inicio = hoy + timedelta(days=30 + indice * 7)
            cursor = connection.execute(
                """INSERT INTO paquetes(nombre,descripcion,precio_centavos,duracion_dias,
                   fecha_inicio,fecha_fin,cupo_maximo,activo) VALUES (?,?,?,?,?,?,?,?)""",
                (nombre, "Paquete de demostración de Travel North.", centavos, duracion,
                 inicio.isoformat(), (inicio + timedelta(days=duracion - 1)).isoformat(), 60, 1),
            )
            paquete_id = cursor.lastrowid
            paquetes.append((paquete_id, centavos))
            connection.executemany(
                "INSERT INTO paquete_destino(paquete_id,destino_id) VALUES (?,?)",
                [(paquete_id, destino_ids[index]) for index in destinos_oferta],
            )

        nombres = ("Ana Torres", "Luis Rojas", "Sara Gómez", "Camilo Pérez", "María Ruiz")
        estados = ("CONFIRMADA", "PENDIENTE", "CANCELADA", "CONFIRMADA", "CONFIRMADA")
        reservas_por_mes = (3, 4, 5, 6, 7, 5)
        demanda_paquetes = (2, 1, 5, 2, 3, 4, 1, 0, 2, 5, 3)
        numero_reserva = 0
        mes_actual = hoy.year * 12 + hoy.month - 1
        for numero_mes, desplazamiento in enumerate(range(5, -1, -1)):
            anio, mes_cero = divmod(mes_actual - desplazamiento, 12)
            for indice in range(reservas_por_mes[numero_mes]):
                nombre = nombres[indice % len(nombres)]
                estado = estados[indice % len(estados)]
                dia = 3 + indice * 3
                if desplazamiento == 0:
                    dia = min(dia, hoy.day)
                registro = date(anio, mes_cero + 1, dia)
                paquete_id, precio = paquetes[demanda_paquetes[numero_reserva % len(demanda_paquetes)]]
                personas = 1 + (numero_mes + indice) % 4
                connection.execute(
                    """INSERT INTO reservas(cliente_nombre,cliente_email,fecha_reserva,
                       cantidad_personas,total_centavos,estado,paquete_id) VALUES (?,?,?,?,?,?,?)""",
                    (nombre, f"viajero{numero_mes + 1}{indice + 1}@example.com", registro.isoformat(),
                     personas, precio * personas, estado, paquete_id),
                )
                numero_reserva += 1
    return True


if __name__ == "__main__":
    with app.app_context():
        cargados = seed_demo()
    print("Datos ficticios cargados: 6 destinos, 6 paquetes y 30 reservas." if cargados
          else "No se cargaron datos: la base ya contiene registros.")
