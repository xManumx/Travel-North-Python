# Travel North: proyecto integrador en Python

Aplicación local para administrar destinos turísticos, paquetes y reservas de una agencia de viajes. Adapta el dominio y las reglas de Travel North a tres proyectos Flask independientes que se comunican mediante HTTP y JSON. La información se guarda en SQLite.

## Descargar en otro computador

Repositorio: https://github.com/xManumx/Travel-North-Python

En GitHub, selecciona **Code > Download ZIP** y extrae el archivo completo. Abre PowerShell en la carpeta que contiene `preparar.ps1` y sigue los dos comandos de preparación que aparecen abajo. No es necesario instalar Git para usar esta opción.

Si tienes Git instalado, puedes descargarlo con:

```powershell
git clone https://github.com/xManumx/Travel-North-Python.git
cd Travel-North-Python
```

Para la presentación detallada entre dos personas, abre [GUION_DETALLADO_DOS_PERSONAS.pdf](GUION_DETALLADO_DOS_PERSONAS.pdf). Está planeada para 15 minutos: 7 minutos y 30 segundos por persona, con 30 segundos de margen hasta el máximo de 8 minutos de cada intervención. Incluye el texto para decir, las acciones de demostración, la relación con los requisitos de la guía y respuestas para la sustentación. Las páginas de apoyo no se leen durante el tiempo del guion.

Si el profesor mantiene un límite de 10 minutos para toda la exposición, usa la versión breve `GUION_DOS_PERSONAS.txt`, planeada para 8 minutos y 30 segundos en total.

Esta versión adapta el proyecto original: https://github.com/Juan04786/Travel-North---Intergrador-

## Preparación en Windows

Se necesita Python 3.10 o superior. La instalación inicial de Flask requiere Internet. Después de preparar los entornos, las tres aplicaciones funcionan localmente sin Internet: SQLite, los estilos, los scripts y Chart.js están incluidos o instalados en el equipo.

Abre PowerShell en esta carpeta y ejecuta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\preparar.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\iniciar.ps1
```

`preparar.ps1` crea un entorno `.venv` en cada proyecto, instala sus dependencias, inicializa SQLite y carga datos ficticios de demostración si la base está vacía. Repetirlo no elimina ni duplica los registros existentes. Si tu equipo tiene varias instalaciones de Python, puedes seleccionar una:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\preparar.ps1 -PythonExe "C:\ruta\a\python.exe"
```

`iniciar.ps1` comprueba los puertos, inicia las tres aplicaciones y abre el navegador. Mantén la terminal abierta; pulsa Ctrl+C para detenerlas juntas. Los mensajes de los servidores se guardan en `logs/`. La política indicada en estos comandos solo se aplica a ese proceso de PowerShell.

| Proyecto | Dirección | Responsabilidad |
|---|---|---|
| `02_backend_api` | http://127.0.0.1:5000/api/health | Validaciones, CRUD, SQLite y reporte analítico |
| `01_frontend_web` | http://127.0.0.1:5001 | Formularios y listados |
| `03_analitica_dashboard` | http://127.0.0.1:5002 | Cinco KPI, cinco gráficas e interpretaciones |

## Ejecutar por separado

Después de preparar el proyecto, abre tres terminales desde esta carpeta:

```powershell
# Terminal 1
.\02_backend_api\.venv\Scripts\python.exe .\02_backend_api\app.py

# Terminal 2
.\01_frontend_web\.venv\Scripts\python.exe .\01_frontend_web\app.py

# Terminal 3
.\03_analitica_dashboard\.venv\Scripts\python.exe .\03_analitica_dashboard\app.py
```

Cada carpeta contiene `requirements.txt`. También se puede crear cada entorno manualmente con `python -m venv .venv` y luego instalar `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` dentro de ese proyecto. En macOS o Linux se utiliza `.venv/bin/python -m pip install -r requirements.txt`.

Antes de la primera ejecución manual, inicializa y carga la base:

```powershell
.\02_backend_api\.venv\Scripts\python.exe .\02_backend_api\init_db.py
.\02_backend_api\.venv\Scripts\python.exe .\02_backend_api\seed_demo.py
```

## Arquitectura y modelo

El navegador de gestión solicita datos a la API del puerto 5000 con `fetch()`. Flask valida la solicitud y ejecuta SQL parametrizado sobre SQLite. El navegador del tablero consulta `GET /api/analitica/reporte`; la API calcula las agregaciones y devuelve JSON. Chart.js dibuja las series y JavaScript redacta las interpretaciones. Los servidores de los puertos 5001 y 5002 solo publican vistas y recursos: no abren la base de datos.

Tablas principales:

- `destinos`: código, nombre, país, ciudad y descripción.
- `paquetes`: precio, duración, fechas, cupo y estado activo.
- `paquete_destino`: relación de varios destinos por paquete.
- `reservas`: cliente, correo, fecha, personas, estado, total y paquete.

Las claves foráneas protegen las relaciones. No se puede eliminar un destino incluido en un paquete ni un paquete con reservas. Las reservas pendientes y confirmadas ocupan cupo; las canceladas no. El total se calcula en el servidor. Los importes se almacenan como centavos enteros y la API los entrega en pesos colombianos.

## API

| Método y ruta | Función |
|---|---|
| `GET /api/health` | Comprobar que la API responde |
| `GET /api/destinos`, `/api/paquetes`, `/api/reservas` | Listar registros |
| `GET /api/{recurso}/{id}` | Consultar un registro |
| `POST /api/{recurso}` | Crear; respuesta 201 |
| `PUT /api/{recurso}/{id}` | Editar; respuesta 200 |
| `DELETE /api/{recurso}/{id}` | Eliminar; respuesta 204 |
| `GET /api/analitica/reporte` | Obtener indicadores y series |

`{recurso}` corresponde a `destinos`, `paquetes` o `reservas`. Los errores devuelven JSON con un campo `error`: 400 para datos inválidos, 404 para registros inexistentes y 409 para conflictos de integridad o negocio.

Ejemplo de creación de una reserva, usando el ID real de un paquete disponible:

```json
{
  "cliente_nombre": "Laura Pérez",
  "cliente_email": "laura@example.com",
  "cantidad_personas": 2,
  "estado": "CONFIRMADA",
  "paquete_id": 1
}
```

La API asigna la fecha de registro y calcula el total; esos valores no se toman del formulario.

## Indicadores y gráficas

| Indicador | Definición |
|---|---|
| Destinos registrados | Número de destinos |
| Paquetes activos | Paquetes con el indicador activo habilitado |
| Reservas vigentes | Reservas pendientes o confirmadas |
| Personas en reservas vigentes | Suma de personas de esas reservas; no son clientes únicos |
| Valor de reservas confirmadas | Suma de sus totales; no representa pagos cobrados |

| Gráfica | Cálculo y criterio |
|---|---|
| Reservas por mes | Conteo de reservas vigentes por mes de registro |
| Cinco paquetes más reservados | Conteo de reservas vigentes por paquete |
| Reservas por estado | Conteo de todos los registros por estado |
| Valor confirmado por paquete | Suma de totales de reservas confirmadas |
| Viajeros por destino | Personas en reservas vigentes que incluyen cada destino |

Un paquete puede incluir varios destinos. En la última gráfica una persona participa en cada destino de su viaje; sumar las barras no produce el total de personas. El KPI de personas se calcula por separado, sin duplicarlas por destino. Las historias describen los resultados; no atribuyen causas que los datos no demuestran.

## Datos de demostración

`seed_demo.py` utiliza nombres ficticios, correos de ejemplo y reservas de varios meses. Los viajes quedan programados hacia el futuro a partir del día en que se realiza la carga. Esta preparación permite demostrar creación, edición, cancelación y actualización del tablero.

El programa no mezcla estos registros con una base ya poblada. Para una nueva demostración desde cero, detén los servidores, conserva una copia de la base si la necesitas y utiliza una carpeta nueva del proyecto. No es necesario reiniciar la base antes de cada exposición.

## Pruebas

Desde la carpeta principal:

```powershell
.\02_backend_api\.venv\Scripts\python.exe -B -m unittest discover -s .\02_backend_api -p "prueba_*.py" -v
.\01_frontend_web\.venv\Scripts\python.exe -B -m unittest discover -s .\01_frontend_web -p "prueba_*.py" -v
.\03_analitica_dashboard\.venv\Scripts\python.exe -B -m unittest discover -s .\03_analitica_dashboard -p "prueba_*.py" -v
.\02_backend_api\.venv\Scripts\python.exe -B .\prueba_integracion.py
```

Las pruebas de API e integración usan bases temporales y no modifican los datos de la demostración. La prueba de integración inicia servidores HTTP en puertos libres, comprueba recursos del frontend y tablero, y verifica que crear, editar, cancelar y eliminar una reserva cambie el reporte de la API. La revisión visual y el uso real del navegador complementan estas pruebas.

## Configuración

Los valores predeterminados corresponden a los puertos de la guía. `API_BASE_URL` permite cambiar la dirección de la API para las vistas; `FRONTEND_URL` y `DASHBOARD_URL` permiten cambiar sus enlaces de navegación. El lanzador establece las direcciones locales de la tabla anterior. Si cambias los puertos manualmente, también debes ajustar los orígenes permitidos por CORS en la API.

La variable `DATABASE` permite indicar otro archivo SQLite al backend. Sin esa variable se usa `02_backend_api/database/travel_north.db`. Inicializa y carga el mismo archivo que utilizarás al ejecutar la API.

Al editar una reserva, cambiar solo el cliente o el estado conserva su total original. Cambiar el paquete o la cantidad de personas recalcula el total con el precio actual del paquete. Cancelar una reserva existente permite liberar sus cupos aunque el viaje ya haya comenzado.

## Solución de problemas

| Situación | Acción |
|---|---|
| Python no se encuentra | Instalar Python o indicar su ruta con `-PythonExe` |
| Falta Flask | Ejecutar `preparar.ps1` o instalar el `requirements.txt` con el Python de ese entorno |
| Puerto ocupado | Cerrar la instancia anterior; el lanzador no detiene procesos ajenos |
| No se puede consultar la API | Comprobar que el puerto 5000 responde y revisar `logs/02_backend_api.log` |
| La reserva supera el cupo | Reducir personas o seleccionar un paquete disponible |
| No se puede eliminar un registro | Revisar sus relaciones; eliminar primero los registros dependientes si corresponde |
| La gráfica no cambia | Pulsar Actualizar información y comprobar el criterio del indicador |

La guía de sustentación está en `GUIA_EXPOSICION.md`. Para entregar, se incluyen el código y Chart.js con su licencia MIT; se excluyen `.venv`, `__pycache__`, bases generadas y logs. Esta carpeta puede incorporarse al repositorio original como `integrador-python/`.
