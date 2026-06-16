"""
db_utils.py — Utilidades compartidas para la base de datos SQLite del proyecto.
"""
import re
import sqlite3
import unicodedata
from pathlib import Path

DB_PATH = Path(__file__).parent / 'posdespacho_amm.db'

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ── Catálogo de activos de transmisión (importado del Diccionario.xlsx) ───────
CREATE TABLE IF NOT EXISTS dim_activos (
    id_activo        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre           TEXT    NOT NULL UNIQUE,
    nombre_norm      TEXT    NOT NULL,          -- para búsqueda sin acentos/prefijos
    clasificacion    TEXT,                       -- "LT 230 kV", "SE 69 kV", etc.
    tipo             TEXT,                       -- linea | subestacion | interconexion | generador | otro
    kv               INTEGER,
    propietario      TEXT,
    tipo_propietario TEXT,
    departamento     TEXT
);

-- ── Sinónimos: activo_indicado → canónico (ambas direcciones de una línea) ────
CREATE TABLE IF NOT EXISTS sinonimos_activos (
    id_sinonimo  INTEGER PRIMARY KEY AUTOINCREMENT,
    indicado     TEXT NOT NULL,
    indicado_norm TEXT NOT NULL,
    id_activo    INTEGER NOT NULL REFERENCES dim_activos(id_activo)
);

-- ── Posdespachos crudos del AMM ───────────────────────────────────────────────
-- id_unico = "ID Único" del Excel (ej. "21763.1") — PRIMARY KEY real
-- id_grupo = "ID" base del Excel (ej. "21763")    — agrupa sub-eventos
CREATE TABLE IF NOT EXISTS posdespachos_raw (
    id_unico             TEXT PRIMARY KEY,
    id_grupo             TEXT NOT NULL,
    estado               TEXT,
    categoria            TEXT,
    narrativa_amm        TEXT,
    fecha_ini            TEXT,           -- ISO "YYYY-MM-DD"
    fecha_fin            TEXT,
    hora_ini             TEXT,           -- "HH:MM"
    hora_fin             TEXT,
    duracion_horas       REAL,
    detonante            TEXT,
    sub_detonante        TEXT,
    tipo_afectacion      TEXT,
    departamento         TEXT,
    propietario          TEXT,
    tipo_propietario     TEXT,
    activo_indicado      TEXT,
    activo               TEXT,
    clasificacion        TEXT,
    direccion            TEXT,
    carga_afectada       REAL,
    codigo_mantenimiento TEXT,
    narrativa            TEXT,
    fuente               TEXT,
    ingresado_at         TEXT DEFAULT (datetime('now'))
);

-- ── Historial de cambios de estado por evento ─────────────────────────────────
CREATE TABLE IF NOT EXISTS estado_eventos (
    id_estado     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_grupo      TEXT    NOT NULL,
    estado        TEXT    NOT NULL,      -- 'Abierto' | 'Cerrado'
    fecha_reporte TEXT    NOT NULL,      -- fecha del posdespacho que lo reportó
    registrado_at TEXT    DEFAULT (datetime('now'))
);

-- ── Checkpoint de procesamiento Groq ─────────────────────────────────────────
-- Una fila por id_grupo (base ID del Excel)
CREATE TABLE IF NOT EXISTS checkpoint (
    id_grupo      TEXT PRIMARY KEY,
    fecha         TEXT,
    procesado     INTEGER DEFAULT 0,     -- 0=pendiente, 1=OK, 2=error
    procesado_at  TEXT,
    n_eventos     INTEGER DEFAULT 0
);

-- ── Eventos confirmados por IA ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS eventos_ia (
    id_evento            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_grupo             TEXT    REFERENCES checkpoint(id_grupo),
    id_activo            INTEGER REFERENCES dim_activos(id_activo),
    activo_raw           TEXT    NOT NULL,
    fecha_ini            TEXT,           -- "YYYY-MM-DD HH:MM"
    fecha_fin            TEXT,
    categoria            TEXT,
    tipo                 TEXT,           -- groq: disparo_forzado | apertura_manual | mantenimiento_programado
    tipo_rep             TEXT,           -- P | NP | IF | FP | C | S
    es_falla_electrica   INTEGER,        -- 1 = disparo real, 0 = mantenimiento
    codigo_mantenimiento TEXT,
    departamento         TEXT,
    tipo_afectacion      TEXT,
    carga_afectada_mw    REAL,
    kv                   INTEGER,
    creado_at            TEXT DEFAULT (datetime('now'))
);

-- ── Subestaciones afectadas por evento (M:N) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS evento_subestaciones (
    id_evento      INTEGER REFERENCES eventos_ia(id_evento),
    nombre_sub_raw TEXT    NOT NULL,
    id_subestacion INTEGER REFERENCES dim_activos(id_activo),
    PRIMARY KEY (id_evento, nombre_sub_raw)
);

-- ── Índices ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_raw_id_grupo   ON posdespachos_raw(id_grupo);
CREATE INDEX IF NOT EXISTS idx_raw_fecha      ON posdespachos_raw(fecha_ini);
CREATE INDEX IF NOT EXISTS idx_ev_fecha       ON eventos_ia(fecha_ini);
CREATE INDEX IF NOT EXISTS idx_ev_id_activo   ON eventos_ia(id_activo);
CREATE INDEX IF NOT EXISTS idx_ev_tipo_rep    ON eventos_ia(tipo_rep);
CREATE INDEX IF NOT EXISTS idx_ev_falla       ON eventos_ia(es_falla_electrica);
CREATE INDEX IF NOT EXISTS idx_sin_norm       ON sinonimos_activos(indicado_norm);
CREATE INDEX IF NOT EXISTS idx_act_norm       ON dim_activos(nombre_norm);
CREATE INDEX IF NOT EXISTS idx_estado_grupo   ON estado_eventos(id_grupo);
"""


# ── Conexión ──────────────────────────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def crear_schema(conn: sqlite3.Connection):
    for stmt in SCHEMA_SQL.split(';'):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()


# ── Normalización ─────────────────────────────────────────────────────────────

def normalizar_nombre(s: str) -> str:
    """Quita acentos, prefijos técnicos y nivel de tensión para búsqueda fuzzy."""
    if not s:
        return ''
    s = unicodedata.normalize('NFD', str(s))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.upper()
    # Quitar prefijos comunes
    s = re.sub(
        r'\b(LT|SE|INT|GEN|HE|GDR|LINEA|SUBESTACION|SUBESTACI.N|'
        r'TRANSFORMADOR|INTERRUPTOR|CIRCUITO|CENTRAL|BARRA)\b', '', s
    )
    # Quitar nivel de tensión (ej. "230 KV", "69KV")
    s = re.sub(r'\b\d+(\.\d+)?\s*KV\b', '', s)
    # Normalizar separadores
    s = re.sub(r'[-–/\s]+', ' ', s)
    return s.strip()


# ── Lookup de activos ─────────────────────────────────────────────────────────

def buscar_id_activo(conn: sqlite3.Connection, nombre_raw: str):
    """
    Busca id_activo en la jerarquía: sinónimos → canónicos → None.
    Retorna (id_activo, nombre_canonico) o (None, None).
    """
    norm = normalizar_nombre(nombre_raw)
    if not norm:
        return None, None

    row = conn.execute(
        'SELECT id_activo FROM sinonimos_activos WHERE indicado_norm = ?', (norm,)
    ).fetchone()
    if row:
        canon = conn.execute(
            'SELECT nombre FROM dim_activos WHERE id_activo = ?', (row[0],)
        ).fetchone()
        return row[0], (canon[0] if canon else None)

    row = conn.execute(
        'SELECT id_activo, nombre FROM dim_activos WHERE nombre_norm = ?', (norm,)
    ).fetchone()
    if row:
        return row[0], row[1]

    return None, None


# ── Derivar tipo_rep y es_falla_electrica ────────────────────────────────────

def derivar_tipo_rep(detonante, sub_detonante, codigo_mant):
    """
    Retorna (tipo_rep: str | None, es_falla_electrica: int).
    Basado en el glosario REP de CNEE.
    """
    det = (detonante or '').lower()
    sub = (sub_detonante or '').lower()
    cod = bool(codigo_mant and str(codigo_mant).strip()
               and str(codigo_mant).strip().upper() not in ('NONE', 'N/A', ''))

    if 'cancel' in det or 'cancel' in sub:
        return 'C', 0
    if 'programad' in det:
        return ('P' if cod else 'NP'), 0
    if 'forzad' in det:
        es_falla = 1 if ('disparo' in sub and not cod) else 0
        return 'IF', es_falla
    return None, 0


# ── Helpers de clasificación (desde Diccionario.xlsx) ─────────────────────────

def tipo_desde_clasificacion(clasif: str) -> str:
    if not clasif:
        return 'otro'
    c = str(clasif).strip().upper()
    if c.startswith('LT'):
        return 'linea'
    if c.startswith('SE'):
        return 'subestacion'
    if c.startswith('INT'):
        return 'interconexion'
    if any(c.startswith(p) for p in ('GEN', 'HE ', 'HE\t', 'GDR', 'CENTRAL')):
        return 'generador'
    if c == 'GU':
        return 'gran_usuario'
    return 'otro'


def kv_desde_clasificacion(clasif: str):
    if not clasif:
        return None
    m = re.search(r'(\d+)\s*kV', str(clasif), re.IGNORECASE)
    return int(m.group(1)) if m else None


# ── Formateo de fechas/horas para SQLite ─────────────────────────────────────

def fmt_fecha(val) -> str:
    if val is None:
        return None
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d')
    return str(val)[:10]


def fmt_hora(val) -> str:
    if val is None:
        return None
    if hasattr(val, 'strftime'):
        return val.strftime('%H:%M')
    s = str(val)
    return s[:5] if len(s) >= 5 else s


def fmt_datetime(fecha_val, hora_val) -> str:
    f = fmt_fecha(fecha_val)
    h = fmt_hora(hora_val)
    if f and h:
        return f'{f} {h}'
    return f


def safe_float(val):
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def safe_str(val) -> str:
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ('none', 'nan') else None
