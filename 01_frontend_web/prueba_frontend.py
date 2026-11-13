"""Pruebas de la vista y los recursos que necesita el navegador."""

import json
import unittest
from html.parser import HTMLParser

from app import create_app


class Documento(HTMLParser):
    def __init__(self):
        super().__init__()
        self.recursos = []
        self.enlaces = []
        self.ids = set()
        self.labels = []
        self.en_configuracion = False
        self.configuracion = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "label" and "for" in attrs:
            self.labels.append(attrs["for"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.recursos.append(attrs["href"])
        if tag == "script" and attrs.get("src"):
            self.recursos.append(attrs["src"])
        if tag == "a":
            self.enlaces.append(attrs.get("href"))
        if tag == "script" and attrs.get("id") == "configuracion":
            self.en_configuracion = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.en_configuracion = False

    def handle_data(self, data):
        if self.en_configuracion:
            self.configuracion += data


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "API_BASE_URL": "http://127.0.0.1:5000/api/",
            "DASHBOARD_URL": "http://127.0.0.1:5002/",
        })
        self.client = self.app.test_client()

    def documento(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        parsed = Documento()
        parsed.feed(response.get_data(as_text=True))
        return parsed

    def test_vista_configura_api_y_enlace_al_dashboard(self):
        page = self.documento()
        self.assertEqual(json.loads(page.configuracion), {"apiBaseUrl": "http://127.0.0.1:5000/api"})
        self.assertIn("http://127.0.0.1:5002", page.enlaces)

    def test_recursos_referenciados_existen_y_son_locales(self):
        page = self.documento()
        self.assertEqual(len(page.recursos), 2)
        for path in page.recursos:
            with self.subTest(path=path):
                self.assertTrue(path.startswith("/static/"))
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertGreater(len(response.data), 100)
                    self.assertNotIn("text/html", response.content_type)

    def test_formulario_tiene_etiquetas_y_campos_para_los_tres_crud(self):
        page = self.documento()
        for label in page.labels:
            self.assertIn(label, page.ids)
        for field in ("destino-codigo", "paquete-precio", "destination-options", "reserva-cliente", "reserva-paquete", "form-error"):
            self.assertIn(field, page.ids)

    def test_frontend_no_expone_operaciones_de_datos(self):
        for path in ("/api/destinos", "/api/paquetes", "/api/reservas"):
            self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.post("/", json={}).status_code, 405)

    def test_rechaza_configuracion_ejecutable_o_con_credenciales(self):
        for key in ("API_BASE_URL", "DASHBOARD_URL"):
            for value in ("javascript:alert(1)", "file:///tmp/datos", "https://usuario:clave@example.com", "https://example.com/#ruta", "http://host con espacios/"):
                with self.subTest(key=key, value=value):
                    with self.assertRaises(ValueError):
                        create_app({key: value})

    def test_json_de_configuracion_no_puede_cerrar_la_etiqueta_script(self):
        url = "http://localhost:5000/api/</script><script>alert(1)</script>"
        app = create_app({"TESTING": True, "API_BASE_URL": url})
        response = app.test_client().get("/")
        html = response.get_data(as_text=True)
        self.assertNotIn("</script><script>alert(1)</script>", html)
        parsed = Documento()
        parsed.feed(html)
        self.assertEqual(json.loads(parsed.configuracion)["apiBaseUrl"], url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
