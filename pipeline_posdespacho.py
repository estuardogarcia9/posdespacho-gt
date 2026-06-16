"""
pipeline_posdespacho.py — AMM → SQLite → Groq → SQLite
=======================================================
Descarga el posdespacho del AMM, lo parsea, guarda en SQLite,
corre Groq para identificar eventos de interrupción y los almacena.

Uso:
    python pipeline_posdespacho.py               # día anterior (automático)
    python pipeline_posdespacho.py 2026-05-31    # fecha específica
    python pipeline_posdespacho.py 2026-05-26 2026-05-31  # rango
    python pipeline_posdespacho.py 2026-05-31 --forzar
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json, os, time, urllib.request, tempfile, subprocess
from datetime import date, timedelta, datetime
from pathlib import Path

import openpyxl
from openai import OpenAI   # compatible con xAI

from db_utils import (
    get_conn, buscar_id_activo, derivar_tipo_rep,
    fmt_fecha, fmt_hora, safe_float, safe_str,
)

# ── Rutas ──────────────────────────────────────────────────────────────────────
BASE       = Path(__file__).parent
MAPA_DIR   = BASE
SALIDA_DIR = BASE
EXCEL_ACUM = BASE / 'posdespachos_acumulado.xlsx'
LOG_FILE   = BASE / 'pipeline_log.txt'

from parsear_posdespacho import (
    guardar_excel, extraer_docx_desde_zip,
    parsear_rso1, parsear_rso2, fecha_desde_zip,
)
from descargar_posdespacho import url_para_fecha

# ── xAI ───────────────────────────────────────────────────────────────────────
XAI_API_KEY  = os.environ['XAI_API_KEY']
XAI_BASE_URL = 'https://api.x.ai/v1'
MODEL        = 'grok-4.3'
BATCH_SIZE   = 10
DELAY_SEG    = 0.2
BACKLOG_MAX  = 99999

KEYWORDS_SI = ['dispar', 'sin tension', 'sin servicio', 'sin suministro',
               'abierta por', 'abierto por', 'desenergiz', 'fuera de servicio',
               'quedo fuera', 'quedo sin', 'dejo sin', 'carga afectada',
               'usuarios afect', 'interrupcion']
KEYWORDS_NO = ['cobro vigencia', 'cobró vigencia', 'programa de despacho',
               'programa de redespacho', 'cerrada la interconexion',
               'cerrada la interconexión', 'genero forzada', 'generó forzada',
               'prueba de cierre positiva', 'recierre positivo']

SYSTEM_PROMPT = """Eres experto en sistemas electricos de potencia de Guatemala (AMM).
Recibes un batch de parrafos del posdespacho. Para CADA parrafo identifica eventos que causaron perdida real de suministro a usuarios.

VOCABULARIO CRITICO:
- 'Cerrado/Cerrada' = CONECTADO → NO es interrupcion
- 'Disparo'/'Abierta por disparo' = salida forzada → SI es interrupcion si hay carga afectada
- 'Genero forzada' = generador operando → NO es interrupcion
- 'Recierre positivo'/'Prueba cierre exitosa' = restauracion → NO incluir
- Solo incluir si menciona: 'sin tension', 'sin servicio', 'carga afectada', 'subestacion sin tension'

Campos por evento: activo (nombre+kV), hora_ini (HH:MM), hora_fin (HH:MM o null), tipo (disparo_forzado|apertura_manual|mantenimiento_programado), subestaciones_afectadas (lista), kv (entero)

FORMATO DE RESPUESTA — objeto JSON con una clave por ID:
{"ID1": [...eventos...], "ID2": [], "ID3": [...eventos...]}
Si un parrafo no tiene interrupciones: lista vacia [].
Sin texto adicional, solo el JSON."""


# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    ts    = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linea = f'[{ts}] {msg}'
    print(linea)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(linea + '\n')


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 1: Descargar, parsear, guardar en Excel (backup) + SQLite
# ══════════════════════════════════════════════════════════════════════════════

def _fechas_ya_en_db(conn) -> set:
    rows = conn.execute(
        'SELECT DISTINCT fecha_ini FROM posdespachos_raw WHERE fecha_ini IS NOT NULL'
    ).fetchall()
    return {r[0][:10] for r in rows}


def _proximo_id_excel() -> int:
    if not EXCEL_ACUM.exists():
        return 1
    wb = openpyxl.load_workbook(EXCEL_ACUM, read_only=True, data_only=True)
    ws = wb.active
    ultimo = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        val = row[2]
        if val is not None:
            try:
                n = int(str(val))
                if n > ultimo:
                    ultimo = n
            except ValueError:
                pass
    wb.close()
    return ultimo + 1


def _insertar_eventos_sqlite(conn, todos: list, fecha_str: str):
    """Inserta en posdespachos_raw + estado_eventos los eventos ya parseados."""
    raw_rows    = []
    estado_rows = []
    vistos      = set()

    for ev in todos:
        id_unico = safe_str(ev.get('ID Único')) or f'{ev.get("ID")}.1'
        id_grupo = safe_str(ev.get('ID'))
        if not id_unico or id_unico in vistos:
            continue
        vistos.add(id_unico)

        hora_fin = ev.get('Hora Final')
        estado   = 'Cerrado' if hora_fin else 'Abierto'

        raw_rows.append((
            id_unico,
            id_grupo,
            estado,
            safe_str(ev.get('Categoría')),
            safe_str(ev.get('Narrativa del AMM')),
            fmt_fecha(ev.get('Fecha inicial')),
            fmt_fecha(ev.get('Fecha final')),
            fmt_hora(ev.get('Hora Inicial')),
            fmt_hora(hora_fin),
            safe_float(ev.get('Duración del evento en horas')),
            safe_str(ev.get('Detonante')),
            safe_str(ev.get('Sub-detonante')),
            safe_str(ev.get('Tipo de afectación')),
            safe_str(ev.get('Departamento')),
            safe_str(ev.get('Propietario')),
            safe_str(ev.get('Tipo de Propietario')),
            safe_str(ev.get('Activo indicado')),
            safe_str(ev.get('Activo')),
            safe_str(ev.get('Clasificación')),
            safe_str(ev.get('Dirección')),
            safe_float(ev.get('Carga afectada')),
            safe_str(ev.get('Código de Mantenimiento')),
            safe_str(ev.get('Narrativa')),
            safe_str(ev.get('Fuente')),
        ))
        estado_rows.append((id_grupo, estado, fecha_str))

    conn.executemany(
        '''INSERT OR IGNORE INTO posdespachos_raw
           (id_unico, id_grupo, estado, categoria, narrativa_amm,
            fecha_ini, fecha_fin, hora_ini, hora_fin, duracion_horas,
            detonante, sub_detonante, tipo_afectacion, departamento,
            propietario, tipo_propietario, activo_indicado, activo,
            clasificacion, direccion, carga_afectada, codigo_mantenimiento,
            narrativa, fuente)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        raw_rows
    )
    conn.executemany(
        'INSERT OR IGNORE INTO estado_eventos (id_grupo, estado, fecha_reporte) VALUES (?,?,?)',
        estado_rows
    )
    conn.commit()
    return len(raw_rows)


def etapa1_descargar_parsear(conn, fechas: list, forzar: bool) -> bool:
    log('─' * 50)
    log('ETAPA 1 · Descarga y parseo del AMM')

    fechas_existentes = _fechas_ya_en_db(conn)
    hubo_cambios = False

    for d in fechas:
        fecha_str = d.strftime('%Y-%m-%d')
        log(f'  [{d.strftime("%d/%m/%Y")}]')

        if not forzar and fecha_str in fechas_existentes:
            log('    Ya existe en la BD — saltando.')
            continue

        url      = url_para_fecha(d)
        zip_path = Path(tempfile.gettempdir()) / f'PD{d.strftime("%Y%m%d")}.zip'
        log('    Descargando desde AMM...')
        try:
            urllib.request.urlretrieve(url, zip_path)
            if zip_path.stat().st_size < 1000:
                zip_path.unlink(missing_ok=True)
                log('    No disponible aún en el AMM (404).')
                continue
        except Exception as e:
            log(f'    ERROR al descargar: {e}')
            continue

        try:
            rso1_bytes, rso2_bytes = extraer_docx_desde_zip(zip_path)
        except Exception as e:
            log(f'    ERROR al extraer docs: {e}')
            zip_path.unlink(missing_ok=True)
            continue

        fecha_doc = fecha_desde_zip(zip_path)
        ev1   = parsear_rso1(rso1_bytes, fecha_doc)
        ev2   = parsear_rso2(rso2_bytes, fecha_doc)
        todos = ev1 + ev2
        log(f'    RSO1: {len(ev1)} | RSO2: {len(ev2)} | Total: {len(todos)}')

        if not todos:
            log('    Sin eventos.')
            zip_path.unlink(missing_ok=True)
            continue

        # Backup Excel (legado)
        EXCEL_ACUM.parent.mkdir(parents=True, exist_ok=True)
        id_ini = _proximo_id_excel()
        id_fin = guardar_excel(todos, EXCEL_ACUM, id_ini)
        log(f'    Excel backup: IDs {id_ini}–{id_fin}')

        # SQLite (principal)
        n = _insertar_eventos_sqlite(conn, todos, fecha_str)
        log(f'    SQLite: {n} filas insertadas en posdespachos_raw')

        hubo_cambios = True
        zip_path.unlink(missing_ok=True)

    return hubo_cambios


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 2: Groq — lee de posdespachos_raw, escribe en checkpoint
# ══════════════════════════════════════════════════════════════════════════════

def _cargar_pendientes(conn, fechas: list) -> dict:
    fechas_set = {d.strftime('%Y-%m-%d') for d in fechas}
    placeholders = ','.join('?' * len(fechas_set))

    rows = conn.execute(
        f'''SELECT DISTINCT p.id_grupo, p.fecha_ini, p.narrativa_amm
            FROM posdespachos_raw p
            WHERE p.fecha_ini IN ({placeholders})
              AND p.id_grupo NOT IN (SELECT id_grupo FROM checkpoint)
              AND p.narrativa_amm IS NOT NULL
            GROUP BY p.id_grupo''',
        list(fechas_set)
    ).fetchall()

    pendientes = {}
    saltados   = 0
    for row in rows:
        narrativa = row[2] or ''
        nar_low   = narrativa.lower()
        tiene_si  = any(p in nar_low for p in KEYWORDS_SI)
        tiene_no  = any(p in nar_low for p in KEYWORDS_NO)
        if not tiene_si or tiene_no:
            saltados += 1
            continue
        pendientes[row[0]] = {'fecha': row[1][:10] if row[1] else None,
                              'narrativa': narrativa}
    log(f'    {len(pendientes)} párrafos para Groq ({saltados} saltados por pre-filtro).')
    return pendientes


def _llamar_groq(client, batch: list) -> dict:
    user_content = json.dumps(
        {item['id']: item['narrativa'] for item in batch},
        ensure_ascii=False
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',   'content': user_content},
        ],
        temperature=0,
        max_tokens=4096,
    )
    texto = resp.choices[0].message.content.strip()
    texto = texto.replace('```json', '').replace('```', '').strip()
    return json.loads(texto)


def etapa2_groq(conn, fechas: list):
    log('─' * 50)
    log('ETAPA 2 · Extracción IA con xAI')

    pendientes = _cargar_pendientes(conn, fechas)
    if not pendientes:
        log('    Nada nuevo que procesar.')
        return

    client = OpenAI(api_key=XAI_API_KEY, base_url=XAI_BASE_URL)
    ids    = list(pendientes.keys())
    total  = len(ids)
    total_lotes = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, total, BATCH_SIZE):
        batch_ids = ids[i:i + BATCH_SIZE]
        batch     = [{'id': bid, **pendientes[bid]} for bid in batch_ids]
        lote_num  = i // BATCH_SIZE + 1
        log(f'    Lote {lote_num}/{total_lotes} ({len(batch)} párrafos)...')
        try:
            resultado = _llamar_groq(client, batch)
            _guardar_resultados(conn, batch_ids, pendientes, resultado)
            n_ev = sum(len(v) for v in resultado.values() if isinstance(v, list))
            log(f'      OK — {n_ev} eventos detectados')
        except Exception as e:
            log(f'      ERROR: {e}')
            conn.executemany(
                'INSERT OR IGNORE INTO checkpoint (id_grupo, fecha, procesado) VALUES (?,?,2)',
                [(bid, pendientes[bid]['fecha']) for bid in batch_ids]
            )
            conn.commit()

        if i + BATCH_SIZE < total:
            time.sleep(DELAY_SEG)


def _guardar_resultados(conn, batch_ids, pendientes, resultado):
    """Inserta en checkpoint + eventos_ia + evento_subestaciones."""
    for bid in batch_ids:
        eventos_groq = resultado.get(bid, resultado.get(str(bid), []))
        n_ev = len([e for e in eventos_groq if e and e.get('activo')])
        fecha = pendientes[bid]['fecha']

        conn.execute(
            '''INSERT OR REPLACE INTO checkpoint (id_grupo, fecha, procesado, procesado_at, n_eventos)
               VALUES (?,?,1,datetime('now'),?)''',
            (bid, fecha, n_ev)
        )

        m = conn.execute(
            '''SELECT detonante, sub_detonante, codigo_mantenimiento,
                      categoria, tipo_afectacion, departamento, carga_afectada
               FROM posdespachos_raw WHERE id_grupo = ? LIMIT 1''',
            (bid,)
        ).fetchone()
        m = dict(m) if m else {}

        for ev in eventos_groq:
            if not ev or not ev.get('activo'):
                continue

            id_activo, _ = buscar_id_activo(conn, ev.get('activo', ''))
            cod          = ev.get('codigo_mantenimiento') or m.get('codigo_mantenimiento')
            tipo_rep, es_falla = derivar_tipo_rep(
                m.get('detonante'), m.get('sub_detonante'), cod
            )
            hora_ini = safe_str(ev.get('hora_ini'))
            hora_fin = safe_str(ev.get('hora_fin'))
            dt_ini   = f'{fecha} {hora_ini}' if (fecha and hora_ini) else fecha
            dt_fin   = f'{fecha} {hora_fin}' if (fecha and hora_fin) else None

            cur = conn.execute(
                '''INSERT INTO eventos_ia
                   (id_grupo, id_activo, activo_raw, fecha_ini, fecha_fin,
                    categoria, tipo, tipo_rep, es_falla_electrica, codigo_mantenimiento,
                    departamento, tipo_afectacion, carga_afectada_mw, kv)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    str(bid), id_activo, safe_str(ev.get('activo')),
                    dt_ini, dt_fin,
                    m.get('categoria'), safe_str(ev.get('tipo')),
                    tipo_rep, es_falla, safe_str(cod),
                    m.get('departamento'), m.get('tipo_afectacion'),
                    safe_float(m.get('carga_afectada')), ev.get('kv'),
                )
            )
            id_evento = cur.lastrowid

            for sub_raw in (ev.get('subestaciones_afectadas') or []):
                sub_str = safe_str(sub_raw)
                if not sub_str:
                    continue
                id_sub, _ = buscar_id_activo(conn, sub_str)
                try:
                    conn.execute(
                        'INSERT OR IGNORE INTO evento_subestaciones VALUES (?,?,?)',
                        (id_evento, sub_str, id_sub)
                    )
                except Exception:
                    pass

    conn.commit()


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 3: Backlog histórico (procesa hasta BACKLOG_MAX párrafos pendientes)
# ══════════════════════════════════════════════════════════════════════════════

def etapa3_backlog(conn):
    log('─' * 50)
    log('ETAPA 3 · Backlog histórico')

    pendientes_rows = conn.execute('''
        SELECT DISTINCT p.id_grupo, p.fecha_ini, p.narrativa_amm
        FROM posdespachos_raw p
        WHERE p.narrativa_amm IS NOT NULL
          AND p.id_grupo NOT IN (SELECT id_grupo FROM checkpoint)
        GROUP BY p.id_grupo
        ORDER BY p.fecha_ini DESC
        LIMIT ?
    ''', (BACKLOG_MAX * 3,)).fetchall()

    pendientes = {}
    saltados   = 0
    for row in pendientes_rows:
        if len(pendientes) >= BACKLOG_MAX:
            break
        narrativa = row[2] or ''
        nar_low   = narrativa.lower()
        tiene_si  = any(p in nar_low for p in KEYWORDS_SI)
        tiene_no  = any(p in nar_low for p in KEYWORDS_NO)
        if not tiene_si or tiene_no:
            conn.execute(
                '''INSERT OR IGNORE INTO checkpoint (id_grupo, fecha, procesado, procesado_at, n_eventos)
                   VALUES (?, ?, 1, datetime('now'), 0)''',
                (row[0], row[1][:10] if row[1] else None)
            )
            saltados += 1
            continue
        pendientes[row[0]] = {'fecha': row[1][:10] if row[1] else None, 'narrativa': narrativa}

    conn.commit()
    total_pendiente = conn.execute('''
        SELECT COUNT(DISTINCT id_grupo) FROM posdespachos_raw
        WHERE id_grupo NOT IN (SELECT id_grupo FROM checkpoint)
    ''').fetchone()[0]

    if not pendientes:
        log(f'    Sin backlog pendiente con keywords ({total_pendiente:,} totales pendientes de procesar).')
        return 0

    log(f'    {len(pendientes)} párrafos a procesar ({saltados} saltados por pre-filtro)')
    log(f'    Backlog restante total: {total_pendiente:,} párrafos')

    client = OpenAI(api_key=XAI_API_KEY, base_url=XAI_BASE_URL)
    ids    = list(pendientes.keys())
    total  = len(ids)
    total_lotes = (total + BATCH_SIZE - 1) // BATCH_SIZE
    procesados  = 0

    for i in range(0, total, BATCH_SIZE):
        batch_ids = ids[i:i + BATCH_SIZE]
        batch     = [{'id': bid, **pendientes[bid]} for bid in batch_ids]
        lote_num  = i // BATCH_SIZE + 1
        log(f'    Lote {lote_num}/{total_lotes} ({len(batch)} párrafos)...')
        try:
            resultado = _llamar_groq(client, batch)
            _guardar_resultados(conn, batch_ids, pendientes, resultado)
            n_ev = sum(len(v) for v in resultado.values() if isinstance(v, list))
            log(f'      OK — {n_ev} eventos detectados')
            procesados += len(batch_ids)
        except Exception as e:
            log(f'      ERROR en lote {lote_num}: {e}')
            log('      Saltando lote — continuando con el siguiente.')
            conn.executemany(
                '''INSERT OR IGNORE INTO checkpoint (id_grupo, fecha, procesado)
                   VALUES (?,?,2)''',
                [(bid, pendientes[bid]['fecha']) for bid in batch_ids]
            )
            conn.commit()
            continue

        if i + BATCH_SIZE < total:
            time.sleep(DELAY_SEG)

    return procesados


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 4: Resumen del día
# ══════════════════════════════════════════════════════════════════════════════

def etapa4_resumen(conn, fechas: list):
    log('─' * 50)
    log('ETAPA 4 · Resumen')
    fechas_set = {d.strftime('%Y-%m-%d') for d in fechas}
    placeholders = ','.join('?' * len(fechas_set))

    n_raw = conn.execute(
        f'SELECT COUNT(*) FROM posdespachos_raw WHERE fecha_ini IN ({placeholders})',
        list(fechas_set)
    ).fetchone()[0]

    n_ev = conn.execute(
        f'SELECT COUNT(*) FROM eventos_ia WHERE fecha_ini LIKE ?',
        (f'{list(fechas_set)[0][:7]}%',)
    ).fetchone()[0]

    n_falla = conn.execute(
        f'SELECT COUNT(*) FROM eventos_ia WHERE es_falla_electrica=1 AND fecha_ini LIKE ?',
        (f'{list(fechas_set)[0][:7]}%',)
    ).fetchone()[0]

    log(f'    posdespachos_raw (fechas del lote): {n_raw} filas')
    log(f'    eventos_ia (mes): {n_ev} total, {n_falla} fallas eléctricas')


# ══════════════════════════════════════════════════════════════════════════════
# ETAPA 5: Actualizar mapa en Neocities
# ══════════════════════════════════════════════════════════════════════════════

def etapa5_actualizar_mapa():
    log('─' * 50)
    log('ETAPA 5 · Actualizar mapa en Neocities')
    python = sys.executable
    pasos = [
        ('Exportar BD → JSON',    [python, 'exportar_db_a_mapa.py']),
        ('Generar HTML del mapa', [python, 'generar_mapa_gemini.py']),
        ('Publicar en Neocities', [python, 'publicar_mapa_neocities.py',
                                   'mapa_posdespachos_gemini.html', 'posdespachos.html']),
    ]
    for nombre, cmd in pasos:
        log(f'    {nombre}...')
        try:
            r = subprocess.run(cmd, cwd=str(MAPA_DIR), capture_output=True, text=True, timeout=180)
            salida = (r.stdout + r.stderr).strip()
            if r.returncode != 0:
                log(f'      ERROR (código {r.returncode}): {salida[:300]}')
                return
            for linea in salida.splitlines():
                log(f'      {linea}')
        except Exception as e:
            log(f'      ERROR: {e}')
            return
    log('    Mapa publicado correctamente.')


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def parse_fecha(s: str) -> date:
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y%m%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'Formato de fecha no reconocido: {s}')


def main():
    args   = [a for a in sys.argv[1:] if a != '--forzar']
    forzar = '--forzar' in sys.argv[1:]

    if not args:
        fecha_ini = date.today() - timedelta(days=1)
        fecha_fin = fecha_ini
    elif len(args) == 1:
        fecha_ini = parse_fecha(args[0])
        fecha_fin = fecha_ini
    else:
        fecha_ini = parse_fecha(args[0])
        fecha_fin = parse_fecha(args[1])

    fechas = [fecha_ini + timedelta(days=i)
              for i in range((fecha_fin - fecha_ini).days + 1)]

    log('=' * 50)
    log(f'Pipeline posdespacho AMM — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    log(f'Fechas: {fecha_ini} → {fecha_fin}  ({len(fechas)} día/s)')

    conn = get_conn()
    etapa1_descargar_parsear(conn, fechas, forzar)
    etapa2_groq(conn, fechas)
    n_backlog = etapa3_backlog(conn)
    etapa4_resumen(conn, fechas)
    if n_backlog:
        pendiente = conn.execute('''
            SELECT COUNT(DISTINCT id_grupo) FROM posdespachos_raw
            WHERE id_grupo NOT IN (SELECT id_grupo FROM checkpoint)
        ''').fetchone()[0]
        log(f'Backlog procesado hoy: {n_backlog} | Pendiente restante: {pendiente:,}')
    conn.close()

    etapa5_actualizar_mapa()

    log('=' * 50)
    log('Pipeline completado.')


if __name__ == '__main__':
    main()
