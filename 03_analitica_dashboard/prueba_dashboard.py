"""Comprueba la vista, la configuración y los recursos locales del tablero.

La interacción con la API y el dibujo de gráficas se verifican en el navegador
durante la prueba de integración; el cliente de Flask no ejecuta JavaScript.
"""

import json
import unittest
from html.parser import HTMLParser
from unittest.mock import patch

from app import create_app


class DashboardHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.resources = []
        self.links = []
        self.canvases = []
        self.config_text = ""
        self.reading_config = False
        self.tables = 0

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "script":
            self.reading_config = attrs.get("id") == "dashboard-config"
            if "src" in attrs:
                self.resources.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.resources.append(attrs["href"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "canvas":
            self.canvases.append(attrs)
        if tag == "table":
            self.tables += 1

    def handle_endtag(self, tag):
        if tag == "script":
            self.reading_config = False

    def handle_data(self, data):
        if self.reading_config:
            self.config_text += data


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def read_page(self, client=None):
        response = (client or self.client).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/html")
        parsed = DashboardHTML()
        parsed.feed(response.get_data(as_text=True))
        return parsed

    def test_local_resources_are_served_with_expected_mime_types(self):
        page = self.read_page()
        expected = {
            "/static/css/dashboard.css": "text/css",
            "/static/js/chart.umd.min.js": "javascript",
            "/static/js/dashboard.js": "javascript",
        }
        self.assertEqual(set(page.resources), set(expected))
        for path, mime in expected.items():
            with self.subTest(path=path):
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(mime, response.mimetype)
                    self.assertGreater(len(response.data), 100)
        self.assertEqual(self.client.get("/static/js/no-existe.js").status_code, 404)

    def test_five_indicators_charts_and_accessible_data_tables(self):
        page = self.read_page()
        self.assertEqual(len(page.ids), len(set(page.ids)), "Hay identificadores HTML repetidos.")
        self.assertEqual(len([item for item in page.ids if item.startswith("kpi-")]), 5)
        self.assertEqual(len(page.canvases), 5)
        self.assertEqual(page.tables, 5)
        for canvas in page.canvases:
            self.assertEqual(canvas.get("role"), "img")
            self.assertIn(canvas["aria-labelledby"], page.ids)
            for description in canvas["aria-describedby"].split():
                self.assertIn(description, page.ids)
            suffix = canvas["id"].removeprefix("grafica-")
            self.assertIn("tabla-" + suffix, page.ids)

    def test_configuration_uses_environment_and_cannot_be_changed_by_query(self):
        with patch.dict("os.environ", {
            "API_BASE_URL": "http://localhost:5050/api/",
            "FRONTEND_URL": "http://localhost:5051",
        }):
            app = create_app({"TESTING": True})
        client = app.test_client()
        page = self.read_page(client)
        self.assertEqual(json.loads(page.config_text), {
            "reportUrl": "http://localhost:5050/api/analitica/reporte",
        })
        self.assertIn("http://localhost:5051", page.links)
        tampered = client.get("/?API_BASE_URL=http://otro-servidor/api")
        parsed = DashboardHTML()
        parsed.feed(tampered.get_data(as_text=True))
        self.assertEqual(json.loads(parsed.config_text), json.loads(page.config_text))

    def test_explicit_configuration_is_escaped_and_apps_are_independent(self):
        unusual = "http://localhost:5000/api/?nota=</script><script>alert(1)</script>"
        first = create_app({"TESTING": True, "API_BASE_URL": unusual})
        second = create_app({"TESTING": True, "API_BASE_URL": "http://localhost:6000/api"})
        first_page = self.read_page(first.test_client())
        second_page = self.read_page(second.test_client())
        self.assertEqual(json.loads(first_page.config_text)["reportUrl"], unusual + "/analitica/reporte")
        self.assertEqual(json.loads(second_page.config_text)["reportUrl"], "http://localhost:6000/api/analitica/reporte")
        self.assertNotIn("</script>", first_page.config_text)

    def test_server_only_serves_view_and_does_not_accept_mutations(self):
        self.assertEqual(self.client.post("/", json={"nombre": "Prueba"}).status_code, 405)
        self.assertEqual(self.client.get("/api/analitica/reporte").status_code, 404)
        self.assertEqual(self.client.get("/ruta-inexistente").status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
