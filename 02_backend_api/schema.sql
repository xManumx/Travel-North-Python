PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS destinos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(codigo) BETWEEN 1 AND 10),
    nombre TEXT NOT NULL CHECK(length(nombre) BETWEEN 1 AND 100),
    pais TEXT NOT NULL CHECK(length(pais) BETWEEN 1 AND 60),
    ciudad TEXT NOT NULL CHECK(length(ciudad) BETWEEN 1 AND 60),
    descripcion TEXT CHECK(descripcion IS NULL OR length(descripcion) <= 500)
);

CREATE TABLE IF NOT EXISTS paquetes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(nombre) BETWEEN 1 AND 120),
    descripcion TEXT CHECK(descripcion IS NULL OR length(descripcion) <= 1000),
    precio_centavos INTEGER NOT NULL CHECK(precio_centavos BETWEEN 1 AND 9999999999),
    duracion_dias INTEGER NOT NULL CHECK(duracion_dias BETWEEN 1 AND 3650),
    fecha_inicio TEXT NOT NULL,
    fecha_fin TEXT NOT NULL CHECK(fecha_fin >= fecha_inicio),
    cupo_maximo INTEGER NOT NULL CHECK(cupo_maximo BETWEEN 1 AND 1000000),
    activo INTEGER NOT NULL DEFAULT 1 CHECK(activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS paquete_destino (
    paquete_id INTEGER NOT NULL REFERENCES paquetes(id) ON DELETE CASCADE,
    destino_id INTEGER NOT NULL REFERENCES destinos(id) ON DELETE RESTRICT,
    PRIMARY KEY (paquete_id, destino_id)
);

CREATE TABLE IF NOT EXISTS reservas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_nombre TEXT NOT NULL CHECK(length(cliente_nombre) BETWEEN 1 AND 120),
    cliente_email TEXT NOT NULL CHECK(length(cliente_email) BETWEEN 3 AND 160),
    fecha_reserva TEXT NOT NULL,
    cantidad_personas INTEGER NOT NULL CHECK(cantidad_personas BETWEEN 1 AND 1000000),
    total_centavos INTEGER NOT NULL CHECK(total_centavos > 0),
    estado TEXT NOT NULL DEFAULT 'PENDIENTE'
        CHECK(estado IN ('PENDIENTE', 'CONFIRMADA', 'CANCELADA')),
    paquete_id INTEGER NOT NULL REFERENCES paquetes(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_reservas_paquete_estado ON reservas(paquete_id, estado);
CREATE INDEX IF NOT EXISTS idx_reservas_fecha ON reservas(fecha_reserva);
CREATE INDEX IF NOT EXISTS idx_paquete_destino_destino ON paquete_destino(destino_id);
