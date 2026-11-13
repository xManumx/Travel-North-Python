# Sustentación: Travel North

## Problema y solución

Travel North necesita organizar sus destinos, administrar paquetes turísticos y controlar reservas sin superar los cupos disponibles. Además, necesita conocer la demanda, los estados de las reservas y el valor de las reservas confirmadas.

La solución divide el trabajo en tres aplicaciones: una API que valida y almacena, una interfaz para registrar información y un tablero que resume los datos. Las tres se comunican con HTTP y JSON.

## Antes de presentar

1. Ejecutar `preparar.ps1` con tiempo para instalar las dependencias.
2. Ejecutar `iniciar.ps1` y mantener la terminal abierta.
3. Comprobar las páginas de gestión y analítica, y abrir el reporte en `http://127.0.0.1:5000/api/analitica/reporte`.
4. Elegir un paquete activo, con fecha futura y al menos dos cupos disponibles. Anotar su precio por persona.
5. Recordar que los registros incluidos son ficticios y se usan para demostrar el funcionamiento.

## Recorrido sugerido para la demostración

1. Presentar destinos, paquetes y reservas. Mostrar que un paquete puede incluir varios destinos.
2. Abrir el tablero y anotar las reservas vigentes, las personas reservadas y el valor confirmado.
3. Crear una reserva confirmada para dos personas desde Gestión. Usar un nombre ficticio y un correo como `demo@example.com`.
4. Explicar que JavaScript envía un `POST` con JSON a la API. Flask valida el paquete, las fechas y los cupos; calcula el total y guarda el registro en SQLite.
5. Volver al tablero y pulsar Actualizar información. Las reservas vigentes deben aumentar en uno, las personas en dos y el valor confirmado en dos veces el precio del paquete. Las series correspondientes también cambian.
6. Editar la reserva y pasarla a cancelada. Actualizar el tablero: deja de contar como vigente, libera cupos y sale del valor confirmado; permanece en la distribución de estados.
7. Eliminar esa reserva de prueba desde el formulario y volver a actualizar. El reporte debe regresar a los valores iniciales si no se realizaron otros cambios.

También se puede demostrar el control de cupos intentando registrar más personas de las disponibles. La API debe rechazar la solicitud con un mensaje entendible y conservar los datos anteriores.

## Qué explicar de cada proyecto

| Proyecto | Explicación |
|---|---|
| API, puerto 5000 | Recibe JSON, valida reglas, ejecuta consultas SQL y devuelve JSON con códigos HTTP |
| Web, puerto 5001 | Sirve formularios y listados; el navegador consume la API con `fetch()` |
| Analítica, puerto 5002 | Sirve la vista; solicita un reporte consolidado y dibuja cinco gráficas con Chart.js |

SQLite es una base de datos relacional en un archivo. Solo la API abre ese archivo. Las claves foráneas mantienen relaciones válidas; por ejemplo, una reserva debe pertenecer a un paquete existente.

## Preguntas probables

**¿Por qué el frontend no accede directamente a SQLite?**

Porque la API centraliza las reglas y el acceso a los datos. Así, todos los formularios pasan por las mismas validaciones y el navegador no necesita abrir archivos del servidor.

**¿Qué diferencia hay entre CRUD y analítica?**

CRUD trabaja con registros: crear, consultar, editar y eliminar. La analítica agrupa esos registros para responder preguntas, como cuántas reservas se registraron cada mes o qué paquete tiene más demanda.

**¿Qué papel cumple JSON?**

Es el formato de intercambio entre el navegador y la API. Una reserva viaja como un objeto con campos; el reporte contiene indicadores y listas de valores que Chart.js puede representar.

**¿Dónde se calculan los indicadores?**

En la API del puerto 5000, mediante consultas SQL. El tablero recibe los resultados y se encarga de mostrarlos. La interpretación se construye a partir de esos valores.

**¿Por qué estos tipos de gráficas?**

La línea permite seguir la evolución mensual. Las barras comparan paquetes y destinos. La dona muestra cómo se distribuyen las reservas entre estados, que son categorías excluyentes.

**¿El valor confirmado es dinero recibido?**

No. Es el valor total de las reservas en estado CONFIRMADA. El modelo no registra pagos, por lo que no permite afirmar cuánto dinero se ha cobrado.

**¿Por qué no se suman los viajeros de todos los destinos?**

Porque una persona puede visitar varios destinos dentro del mismo paquete. La gráfica cuenta su participación en cada destino; el indicador de personas suma las reservas sin repetirlas por destino. Tampoco representa clientes únicos entre distintas reservas.

**¿Qué pasa si se cancela una reserva?**

Libera cupos y deja de contar en reservas vigentes, personas vigentes y valor confirmado. Se conserva en la distribución por estado hasta que sea eliminada.

**¿Qué se aprovechó del proyecto original?**

La temática de la agencia, las entidades, sus relaciones, las reglas de negocio, los flujos de los formularios y los criterios de las estadísticas. La versión de esta entrega implementa esos conceptos con Flask y SQLite.

## Correspondencia con la guía

| Punto de la guía | Evidencia en Travel North |
|---|---|
| Tres proyectos independientes | Carpetas 01, 02 y 03 con dependencias y pruebas propias |
| API y SQLite | CRUD, validaciones, `schema.sql` e `init_db.py` |
| Formularios funcionales | Crear, consultar, editar y eliminar los tres recursos |
| Cinco KPI y cinco visualizaciones | Tablero con criterios explícitos y datos del reporte |
| Pregunta e historia por gráfica | Títulos orientados a preguntas e interpretaciones dinámicas |
| Comunicación HTTP y JSON | Solicitudes del navegador a la API |
| Cambio visible después del CRUD | Demostración de crear, cancelar y eliminar una reserva |
| Puertos simultáneos | 5000, 5001 y 5002 |
