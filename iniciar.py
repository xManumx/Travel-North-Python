"""Inicia los tres proyectos y los detiene juntos con Ctrl+C."""

import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser

ROOT = Path(__file__).resolve().parent
COMPONENTS = (
    ('02_backend_api', 5000, '/api/health'),
    ('01_frontend_web', 5001, '/'),
    ('03_analitica_dashboard', 5002, '/'),
)


def environment_python(folder):
    directory = ROOT / folder / '.venv'
    return directory / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def wait_ready(process, url):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Una aplicacion se detuvo. Revisa la carpeta logs: {url}')
        try:
            with urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f'No se obtuvo respuesta de {url}. Revisa la carpeta logs.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sin-navegador', action='store_true')
    args = parser.parse_args()
    for folder, port, _ in COMPONENTS:
        if not environment_python(folder).is_file():
            print(f'Falta el entorno virtual de {folder}. Ejecuta preparar.ps1.', file=sys.stderr)
            return 1
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                print(f'El puerto {port} ya esta ocupado. Cierra esa aplicacion antes de iniciar.', file=sys.stderr)
                return 1
    processes = []
    log_files = []
    logs = ROOT / 'logs'
    logs.mkdir(exist_ok=True)
    try:
        for folder, port, health in COMPONENTS:
            log = (logs / f'{folder}.log').open('w', encoding='utf-8')
            log_files.append(log)
            environment = os.environ.copy()
            environment['PYTHONIOENCODING'] = 'utf-8'
            environment['PYTHONUNBUFFERED'] = '1'
            environment['PORT'] = str(port)
            # El lanzador usa las direcciones locales de la guia.
            environment['API_BASE_URL'] = 'http://127.0.0.1:5000/api'
            environment['FRONTEND_URL'] = 'http://127.0.0.1:5001'
            environment['DASHBOARD_URL'] = 'http://127.0.0.1:5002'
            process = subprocess.Popen(
                [str(environment_python(folder)), '-B', str(ROOT / folder / 'app.py')],
                cwd=ROOT / folder, env=environment, stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            processes.append(process)
            wait_ready(process, f'http://127.0.0.1:{port}{health}')
            print(f'{folder}: http://127.0.0.1:{port}', flush=True)
        if not args.sin_navegador:
            webbrowser.open('http://127.0.0.1:5001')
            webbrowser.open('http://127.0.0.1:5002')
        print('Las tres aplicaciones estan listas. Mantén esta terminal abierta. Ctrl+C para detener.', flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        raise RuntimeError('Una aplicacion se detuvo. Consulta logs antes de volver a iniciar.')
    except KeyboardInterrupt:
        print('\nDeteniendo las tres aplicaciones...')
        return 0
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for log in log_files:
            log.close()


if __name__ == '__main__':
    raise SystemExit(main())
