"""Comprueba por HTTP los tres proyectos con una base SQLite temporal."""

from datetime import date, timedelta
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from werkzeug.serving import WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parent


def load_application(folder, module_name):
    directory = ROOT / folder
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location(module_name, directory / 'app.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class QuietHandler(WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        pass


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'script' and attributes.get('src'):
            self.assets.append(attributes['src'])
        if tag == 'link' and attributes.get('rel') == 'stylesheet':
            self.assets.append(attributes['href'])


class IntegracionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='travelnorth-prueba-')
        cls.servers = []
        cls.threads = []
        cls.addClassCleanup(cls.cleanup)
        api_module = load_application('02_backend_api', 'travelnorth_api_prueba')
        api = api_module.create_app({
            'TESTING': True,
            'DATABASE': str(Path(cls.temporary.name) / 'integracion.sqlite3'),
        })
        from db import init_db
        with api.app_context():
            init_db()
        cls.api_url = cls.start_server(api) + '/api'
        front_module = load_application('01_frontend_web', 'travelnorth_front_prueba')
        dashboard_module = load_application('03_analitica_dashboard', 'travelnorth_dashboard_prueba')
        cls.front_url = cls.start_server(front_module.create_app({
            'TESTING': True, 'API_BASE_URL': cls.api_url,
        }))
        cls.dashboard_url = cls.start_server(dashboard_module.create_app({
            'TESTING': True, 'API_BASE_URL': cls.api_url,
        }))

    @classmethod
    def start_server(cls, app):
        server = make_server('127.0.0.1', 0, app, threaded=True, request_handler=QuietHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        cls.servers.append(server)
        cls.threads.append(thread)
        thread.start()
        return f'http://127.0.0.1:{server.server_port}'

    @classmethod
    def cleanup(cls):
        for server in cls.servers:
            server.shutdown()
            server.server_close()
        for thread in cls.threads:
            thread.join(timeout=3)
        cls.temporary.cleanup()

    def request(self, path, method='GET', payload=None, expected=200):
        body = json.dumps(payload).encode('utf-8') if payload is not None else None
        request = Request(self.api_url + path, data=body, method=method,
                          headers={'Content-Type': 'application/json'} if body else {})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            content = response.read()
            self.assertEqual(response.status, expected, content.decode('utf-8'))
            return json.loads(content) if content else None

    def test_vistas_y_recursos_disponibles_por_http(self):
        for base_url in (self.front_url, self.dashboard_url):
            with self.subTest(url=base_url):
                with urlopen(base_url, timeout=5) as response:
                    html = response.read().decode('utf-8')
                    self.assertEqual(response.status, 200)
                self.assertIn(self.api_url, html)
                parser = AssetParser()
                parser.feed(html)
                self.assertGreaterEqual(len(parser.assets), 2)
                for asset in parser.assets:
                    self.assertFalse(asset.startswith(('https://', 'http://', '//')),
                                     'Los recursos deben estar disponibles localmente.')
                    with urlopen(urljoin(base_url, asset), timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        self.assertGreater(len(response.read()), 20)
        with urlopen(self.dashboard_url + '/static/js/chart.umd.min.js', timeout=5) as response:
            self.assertIn(b'Chart.js v4.4.7', response.read()[:150])

    def test_crud_actualiza_reporte_por_http(self):
        before = self.request('/analitica/reporte')
        self.assertEqual(before['kpis']['reservas_vigentes'], 0)
        destinations = []
        for code, city in (('TESTA', 'Medellín'), ('TESTB', 'Bogotá')):
            destinations.append(self.request('/destinos', 'POST', {
                'codigo': code, 'nombre': 'Centro histórico', 'pais': 'Colombia',
                'ciudad': city, 'descripcion': 'Registro temporal de prueba.',
            }, expected=201))
        start = date.today() + timedelta(days=30)
        package_payload = {
            'nombre': 'Recorrido de prueba', 'descripcion': 'Paquete temporal.',
            'precio': 250000.50, 'duracion_dias': 3,
            'fecha_inicio': start.isoformat(), 'fecha_fin': (start + timedelta(days=2)).isoformat(),
            'cupo_maximo': 4, 'activo': True, 'destino_ids': [item['id'] for item in destinations],
        }
        package = self.request('/paquetes', 'POST', package_payload, expected=201)
        payload = {
            'cliente_nombre': 'Cliente de prueba', 'cliente_email': 'prueba@example.com',
            'cantidad_personas': 2, 'estado': 'CONFIRMADA', 'paquete_id': package['id'],
        }
        reservation = self.request('/reservas', 'POST', payload, expected=201)
        self.assertEqual(reservation['total'], 500001)
        report = self.request('/analitica/reporte')
        self.assertEqual(report['kpis']['reservas_vigentes'], 1)
        self.assertEqual(report['kpis']['personas_reservadas'], 2)
        self.assertEqual(report['kpis']['valor_confirmado'], 500001)
        self.assertEqual(len(report['series']['viajeros_por_destino']), 2)
        self.assertEqual(sum(item['value'] for item in report['series']['viajeros_por_destino']), 4)
        self.request('/paquetes/' + str(package['id']), 'DELETE', expected=409)

        # Una reserva sin cupo se rechaza sin alterar el reporte.
        rejected = self.request('/reservas', 'POST', {**payload, 'cantidad_personas': 5}, expected=409)
        self.assertTrue(rejected['error'])
        self.assertEqual(self.request('/analitica/reporte')['kpis'], report['kpis'])

        reservation_path = '/reservas/' + str(reservation['id'])
        self.request(reservation_path, 'PUT', {**payload, 'cantidad_personas': 3})
        edited = self.request('/analitica/reporte')
        self.assertEqual(edited['kpis']['personas_reservadas'], 3)
        self.assertEqual(edited['kpis']['valor_confirmado'], 750001.50)

        self.request(reservation_path, 'PUT', {**payload, 'cantidad_personas': 3, 'estado': 'CANCELADA'})
        cancelled = self.request('/analitica/reporte')
        self.assertEqual(cancelled['kpis']['reservas_vigentes'], 0)
        self.assertEqual(cancelled['kpis']['personas_reservadas'], 0)
        self.assertEqual(cancelled['kpis']['valor_confirmado'], 0)
        states = {row['label']: row['value'] for row in cancelled['series']['reservas_por_estado']}
        self.assertEqual(states['CANCELADA'], 1)
        self.assertEqual(self.request('/paquetes/' + str(package['id']))['cupos_disponibles'], 4)

        self.request(reservation_path, 'DELETE', expected=204)
        self.request('/paquetes/' + str(package['id']), 'DELETE', expected=204)
        for destination in destinations:
            self.request('/destinos/' + str(destination['id']), 'DELETE', expected=204)
        self.assertEqual(self.request('/analitica/reporte')['kpis'], before['kpis'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
