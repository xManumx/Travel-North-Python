"""Pruebas locales con SQLite temporal: no utilizan la base de la exposición."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from app import create_app
from db import get_db, init_db
from seed_demo import seed_demo


class PruebaAPI(unittest.TestCase):
    def setUp(self):
        self.directorio = tempfile.TemporaryDirectory()
        self.addCleanup(self.directorio.cleanup)
        self.app = create_app({"TESTING": True, "DATABASE": str(Path(self.directorio.name) / "prueba.db")})
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()

    def destino_data(self, **cambios):
        data = {"codigo": "MED", "nombre": "Medellín", "pais": "Colombia", "ciudad": "Medellín", "descripcion": "Cultura"}
        return data | cambios

    def crear_destino(self, **cambios):
        response = self.client.post("/api/destinos", json=self.destino_data(**cambios))
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def paquete_data(self, ids, **cambios):
        inicio = date.today() + timedelta(days=30)
        data = {
            "nombre": "Ruta Andina", "descripcion": "Viaje de prueba", "precio": 100.01,
            "duracion_dias": 3, "fecha_inicio": inicio.isoformat(),
            "fecha_fin": (inicio + timedelta(days=2)).isoformat(),
            "cupo_maximo": 20, "activo": True, "destino_ids": ids,
        }
        return data | cambios

    def crear_paquete(self, ids=None, **cambios):
        if ids is None:
            ids = [self.crear_destino()["id"]]
        response = self.client.post("/api/paquetes", json=self.paquete_data(ids, **cambios))
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def reserva_data(self, paquete_base_id, **cambios):
        return {
            "cliente_nombre": "Ana Torres", "cliente_email": "ana@example.com",
            "cantidad_personas": 2, "estado": "CONFIRMADA", "paquete_id": paquete_base_id,
        } | cambios

    def crear_reserva(self, paquete_id, **cambios):
        response = self.client.post("/api/reservas", json=self.reserva_data(paquete_id, **cambios))
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def actualizar_fecha_reserva(self, reserva_id, fecha):
        with self.app.app_context():
            get_db().execute("UPDATE reservas SET fecha_reserva=? WHERE id=?", (fecha, reserva_id))
            get_db().commit()

    def test_salud_y_base_vacia(self):
        self.assertEqual(self.client.get("/api/health").get_json()["status"], "UP")
        for recurso in ("destinos", "paquetes", "reservas"):
            self.assertEqual(self.client.get(f"/api/{recurso}").get_json(), [])
            self.assertEqual(self.client.get(f"/api/{recurso}/999").status_code, 404)
            self.assertEqual(self.client.get(f"/api/{recurso}/999999999999999999999").status_code, 404)
        reporte = self.client.get("/api/analitica/reporte").get_json()
        self.assertTrue(all(value == 0 for value in reporte["kpis"].values()))
        for nombre, serie in reporte["series"].items():
            if nombre == "reservas_por_estado":
                self.assertEqual([item["value"] for item in serie], [0, 0, 0])
            else:
                self.assertEqual(serie, [])

    def test_crud_completo_y_relaciones(self):
        destino = self.crear_destino()
        destino_id = destino["id"]
        editado = self.client.put(f"/api/destinos/{destino_id}", json=self.destino_data(nombre="Valle de Aburrá"))
        self.assertEqual(editado.get_json()["nombre"], "Valle de Aburrá")
        paquete = self.crear_paquete([destino_id])
        paquete_id = paquete["id"]
        self.assertEqual(paquete["destino_ids"], [destino_id])
        self.assertEqual(paquete["destinos"][0]["nombre"], "Valle de Aburrá")
        reserva = self.crear_reserva(paquete_id)
        self.assertEqual(reserva["total"], 200.02)
        self.assertEqual(reserva["fecha_reserva"], date.today().isoformat())
        self.assertEqual(reserva["paquete_nombre"], "Ruta Andina")
        self.assertEqual(self.client.get(f"/api/paquetes/{paquete_id}").get_json()["cupos_disponibles"], 18)
        self.assertEqual(self.client.delete(f"/api/destinos/{destino_id}").status_code, 409)
        self.assertEqual(self.client.delete(f"/api/paquetes/{paquete_id}").status_code, 409)
        actualizada = self.client.put(f"/api/reservas/{reserva['id']}", json=self.reserva_data(paquete_id, cliente_nombre="Ana Ruiz"))
        self.assertEqual(actualizada.get_json()["cliente_nombre"], "Ana Ruiz")
        for recurso, registro_id in (("reservas", reserva["id"]), ("paquetes", paquete_id), ("destinos", destino_id)):
            self.assertEqual(self.client.delete(f"/api/{recurso}/{registro_id}").status_code, 204)
            self.assertEqual(self.client.get(f"/api/{recurso}/{registro_id}").status_code, 404)

    def test_duplicados_y_valores_incorrectos(self):
        self.crear_destino()
        self.assertEqual(self.client.post("/api/destinos", json=self.destino_data(codigo="med")).status_code, 409)
        for cambios in ({"nombre": " "}, {"codigo": "ABCDEFGHIJK"}, {"pais": 1}, {"ciudad": None}):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.client.post("/api/destinos", json=self.destino_data(**cambios)).status_code, 400)
        for cuerpo in ([], None, "texto"):
            self.assertEqual(self.client.post("/api/destinos", json=cuerpo).status_code, 400)
        self.assertEqual(self.client.post("/api/destinos", data="{", content_type="application/json").status_code, 400)

    def test_validaciones_paquetes_y_relacion_inexistente(self):
        destino = self.crear_destino()["id"]
        for cambios in (
            {"precio": 0}, {"precio": -1}, {"precio": 1.001}, {"precio": True}, {"precio": "NaN"},
            {"cupo_maximo": True}, {"duracion_dias": 1.5}, {"activo": "true"},
            {"destino_ids": []}, {"destino_ids": [True]}, {"destino_ids": [destino, destino]},
            {"fecha_inicio": "2026-02-30"}, {"fecha_inicio": "2020-01-01"}, {"fecha_fin": "2020-01-01"},
        ):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.client.post("/api/paquetes", json=self.paquete_data([destino], **cambios)).status_code, 400)
        self.assertEqual(self.client.post("/api/paquetes", json=self.paquete_data([999])).status_code, 404)
        self.assertEqual(self.client.get("/api/paquetes").get_json(), [])
        self.crear_paquete([destino])
        self.assertEqual(self.client.post("/api/paquetes", json=self.paquete_data([destino], nombre="ruta andina")).status_code, 409)

    def test_validaciones_reservas_y_datos_calculados(self):
        paquete_id = self.crear_paquete()["id"]
        for cambios in (
            {"cantidad_personas": 0}, {"cantidad_personas": True}, {"cantidad_personas": 1.5},
            {"cantidad_personas": 1000001}, {"cliente_email": "correo-invalido"},
            {"cliente_nombre": ""}, {"estado": "PAGADA"}, {"estado": []}, {"paquete_id": False},
            {"total": 1}, {"fecha_reserva": "2020-01-01"},
        ):
            with self.subTest(cambios=cambios):
                self.assertEqual(self.client.post("/api/reservas", json=self.reserva_data(paquete_id, **cambios)).status_code, 400)
        self.assertEqual(self.client.post("/api/reservas", json=self.reserva_data(999)).status_code, 404)

    def test_actualizacion_de_relaciones_es_atomica(self):
        d1 = self.crear_destino()["id"]
        d2 = self.crear_destino(codigo="BOG", ciudad="Bogotá")["id"]
        a = self.crear_paquete([d1], nombre="A")
        b = self.crear_paquete([d1], nombre="B")
        ruta = f"/api/paquetes/{a['id']}"
        fallida = self.client.put(ruta, json=self.paquete_data([d2], nombre="B"))
        self.assertEqual(fallida.status_code, 409)
        self.assertEqual(self.client.get(ruta).get_json()["destino_ids"], [d1])
        correcta = self.client.put(ruta, json=self.paquete_data([d2], nombre="A"))
        self.assertEqual(correcta.status_code, 200)
        self.assertEqual(correcta.get_json()["destino_ids"], [d2])
        self.assertEqual(self.client.delete(f"/api/paquetes/{b['id']}").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/destinos/{d1}").status_code, 204)

    def test_cupos_al_editar_cancelar_y_reactivar(self):
        paquete = self.crear_paquete(cupo_maximo=3)
        paquete_id = paquete["id"]
        reserva = self.crear_reserva(paquete_id, estado="PENDIENTE")
        ruta = f"/api/reservas/{reserva['id']}"
        self.assertEqual(self.client.post("/api/reservas", json=self.reserva_data(paquete_id)).status_code, 409)
        self.assertEqual(self.client.put(ruta, json=self.reserva_data(paquete_id, cantidad_personas=3)).status_code, 200)
        self.assertEqual(self.client.get(f"/api/paquetes/{paquete_id}").get_json()["cupos_ocupados"], 3)
        reducido = self.client.put(f"/api/paquetes/{paquete_id}", json=self.paquete_data(paquete["destino_ids"], cupo_maximo=2))
        self.assertEqual(reducido.status_code, 409)
        self.assertEqual(self.client.put(ruta, json=self.reserva_data(paquete_id, estado="CANCELADA", cantidad_personas=3)).status_code, 200)
        self.crear_reserva(paquete_id, cantidad_personas=3)
        self.assertEqual(self.client.put(ruta, json=self.reserva_data(paquete_id, cantidad_personas=3)).status_code, 409)
        self.assertEqual(self.client.get(ruta).get_json()["estado"], "CANCELADA")

    def test_cambiar_paquete_libera_cupos_y_recalcula_total(self):
        destino = self.crear_destino()["id"]
        primero = self.crear_paquete([destino], cupo_maximo=2)
        segundo = self.crear_paquete([destino], nombre="Otra ruta", precio=50, cupo_maximo=3)
        reserva = self.crear_reserva(primero["id"])
        response = self.client.put(f"/api/reservas/{reserva['id']}", json=self.reserva_data(segundo["id"], cantidad_personas=3))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["total"], 150)
        self.assertEqual(self.client.get(f"/api/paquetes/{primero['id']}").get_json()["cupos_disponibles"], 2)
        self.assertEqual(self.client.get(f"/api/paquetes/{segundo['id']}").get_json()["cupos_disponibles"], 0)

    def test_conservar_total_al_cambiar_cliente_o_estado(self):
        paquete = self.crear_paquete()
        reserva = self.crear_reserva(paquete["id"])
        self.client.put(f"/api/paquetes/{paquete['id']}", json=self.paquete_data(paquete["destino_ids"], precio=500))
        response = self.client.put(f"/api/reservas/{reserva['id']}", json=self.reserva_data(paquete["id"], estado="PENDIENTE"))
        self.assertEqual(response.get_json()["total"], 200.02)
        self.assertEqual(response.get_json()["fecha_reserva"], reserva["fecha_reserva"])

    def test_paquetes_inactivos_vencidos_y_cancelacion(self):
        paquete = self.crear_paquete()
        reserva = self.crear_reserva(paquete["id"])
        self.client.put(f"/api/paquetes/{paquete['id']}", json=self.paquete_data(paquete["destino_ids"], activo=False))
        self.assertEqual(self.client.post("/api/reservas", json=self.reserva_data(paquete["id"])).status_code, 400)
        with self.app.app_context():
            get_db().execute("UPDATE paquetes SET fecha_inicio=?, fecha_fin=? WHERE id=?",
                             ("2020-01-01", "2020-01-03", paquete["id"]))
            get_db().commit()
        cancelada = self.client.put(f"/api/reservas/{reserva['id']}", json=self.reserva_data(paquete["id"], estado="CANCELADA"))
        self.assertEqual(cancelada.status_code, 200)
        with self.app.app_context():
            get_db().execute("UPDATE paquetes SET activo=1 WHERE id=?", (paquete["id"],))
            get_db().commit()
        self.assertEqual(self.client.post("/api/reservas", json=self.reserva_data(paquete["id"])).status_code, 400)

    def test_reporte_exacto_sin_duplicar_personas_ni_canceladas(self):
        d1 = self.crear_destino(nombre="Destino", ciudad="Ciudad A")["id"]
        d2 = self.crear_destino(codigo="BOG", nombre="Destino", ciudad="Ciudad B")["id"]
        a = self.crear_paquete([d1, d2], nombre="A")
        b = self.crear_paquete([d1], nombre="B", precio=50)
        self.crear_paquete([d2], nombre="C", activo=False)
        r1 = self.crear_reserva(a["id"], cantidad_personas=2)
        r2 = self.crear_reserva(a["id"], cantidad_personas=1, estado="PENDIENTE")
        r3 = self.crear_reserva(b["id"], cantidad_personas=4, estado="CANCELADA")
        r4 = self.crear_reserva(b["id"], cantidad_personas=3)
        for reserva, fecha in ((r1,"2025-01-01"), (r2,"2025-03-01"), (r3,"2025-02-01"), (r4,"2025-03-02")):
            self.actualizar_fecha_reserva(reserva["id"], fecha)
        reporte = self.client.get("/api/analitica/reporte").get_json()
        self.assertEqual(reporte["kpis"], {
            "destinos_registrados": 2, "paquetes_activos": 2, "reservas_vigentes": 3,
            "personas_reservadas": 6, "valor_confirmado": 350.02,
        })
        series = reporte["series"]
        self.assertEqual(series["reservas_por_mes"], [
            {"label":"2025-01","value":1}, {"label":"2025-02","value":0}, {"label":"2025-03","value":2},
        ])
        self.assertEqual(series["paquetes_mas_reservados"], [
            {"id":a["id"],"label":"A","value":2}, {"id":b["id"],"label":"B","value":1},
        ])
        self.assertEqual([item["value"] for item in series["reservas_por_estado"]], [1,2,1])
        self.assertEqual(series["valor_por_paquete"], [
            {"id":a["id"],"label":"A","value":200.02}, {"id":b["id"],"label":"B","value":150.0},
        ])
        self.assertEqual(series["viajeros_por_destino"], [
            {"id":d1,"label":"Destino - Ciudad A","value":6},
            {"id":d2,"label":"Destino - Ciudad B","value":3},
        ])
        self.assertEqual(reporte["meta"]["fuente"], "SQLite")
        self.assertTrue(reporte["meta"]["generado_en"].endswith("+00:00"))

    def test_top_cinco_y_desempate_por_nombre(self):
        destino = self.crear_destino()["id"]
        for nombre in ("F", "D", "B", "E", "A", "C"):
            paquete = self.crear_paquete([destino], nombre=nombre)
            self.crear_reserva(paquete["id"])
        top = self.client.get("/api/analitica/reporte").get_json()["series"]["paquetes_mas_reservados"]
        self.assertEqual([item["label"] for item in top], ["A", "B", "C", "D", "E"])

    def test_cors_solo_permite_los_dos_clientes_locales(self):
        for origen in ("http://localhost:5001", "http://127.0.0.1:5001", "http://localhost:5002", "http://127.0.0.1:5002"):
            response = self.client.options("/api/reservas", headers={"Origin":origen,"Access-Control-Request-Method":"POST"})
            self.assertEqual(response.status_code, 204)
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], origen)
        response = self.client.get("/api/destinos", headers={"Origin":"https://externo.example"})
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.assertEqual(self.client.get("/api/destinos").headers["Cache-Control"], "no-store")

    def test_integridad_sql_e_inicializacion_idempotente(self):
        destino = self.crear_destino(nombre="Ruta '); DROP TABLE destinos; --")
        self.crear_paquete([destino["id"]])
        with self.app.app_context():
            init_db()
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM destinos").fetchone()[0], 1)
            self.assertEqual(get_db().execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with self.assertRaises(sqlite3.IntegrityError):
                get_db().execute("DELETE FROM destinos WHERE id=?", (destino["id"],))
            get_db().rollback()
        self.assertEqual(len(self.client.get("/api/destinos").get_json()), 1)

    def test_dos_solicitudes_no_consumen_el_mismo_cupo(self):
        paquete = self.crear_paquete(cupo_maximo=1)
        data = self.reserva_data(paquete["id"], cantidad_personas=1)
        def reservar(_indice):
            with self.app.test_client() as client:
                return client.post("/api/reservas", json=data).status_code
        with ThreadPoolExecutor(max_workers=2) as executor:
            codigos = list(executor.map(reservar, range(2)))
        self.assertEqual(sorted(codigos), [201,409])
        self.assertEqual(self.client.get(f"/api/paquetes/{paquete['id']}").get_json()["cupos_ocupados"], 1)

    def test_seed_seis_meses_futuros_y_sin_duplicados(self):
        with self.app.app_context():
            self.assertTrue(seed_demo())
            self.assertFalse(seed_demo())
        reporte = self.client.get("/api/analitica/reporte").get_json()
        self.assertEqual(reporte["kpis"]["destinos_registrados"], 6)
        self.assertEqual(len(reporte["series"]["reservas_por_mes"]), 6)
        self.assertGreater(len({item["value"] for item in reporte["series"]["reservas_por_mes"]}), 1)
        self.assertGreater(len({item["value"] for item in reporte["series"]["paquetes_mas_reservados"]}), 1)
        self.assertEqual(len(self.client.get("/api/reservas").get_json()), 30)
        for paquete in self.client.get("/api/paquetes").get_json():
            self.assertGreater(paquete["fecha_inicio"], date.today().isoformat())
            self.assertGreaterEqual(paquete["cupos_disponibles"], 0)

    def test_seed_no_mezcla_datos_existentes(self):
        self.crear_destino()
        with self.app.app_context():
            self.assertFalse(seed_demo())
        self.assertEqual(self.client.get("/api/paquetes").get_json(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
