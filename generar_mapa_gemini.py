#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Genera mapa interactivo HTML con Leaflet.js usando sub-eventos
descompuestos por Gemini AI desde los posdespachos del AMM.
"""

import re
import json
import math
import pandas as pd
from datetime import datetime
from pathlib import Path
from collections import Counter, defaultdict

# ─── Paths ────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
SUBS_CSV = BASE / "geodata" / "subestaciones.csv"
LINES_CSV = BASE / "geodata" / "lineas_transmision.csv"
GEMINI_JSON = BASE / "subeventos_gemini.json"
NARR_JSON = BASE / "narrativas_para_ia.json"
OUTPUT_HTML = BASE / "mapa_posdespachos_gemini.html"

# ─── Alias dictionary ────────────────────────────────────────────────────
ALIASES = {
    'ALBORADA': 'ALBORADA (ESCUINTLA)',
    'BELEM': 'BELEM (MANIOBRAS)',
    'PETEN': 'PETEN (IXPANPAJUL)',
    'PETÉN': 'PETEN (IXPANPAJUL)',
    'PETEN IXPANPAJUL': 'PETEN (IXPANPAJUL)',
    'PETÉN IXPANPAJUL': 'PETEN (IXPANPAJUL)',
    'GUATE SUR': 'GUATEMALA SUR',
    'GUATE NORTE': 'GUATEMALA NORTE',
    'GUATE ESTE': 'GUATEMALA ESTE',
    'XELAJU': 'XELA',
    'TECULUTAN 2': 'TECULUTAN II',
    'TECULUTÁN 2': 'TECULUTAN II',
    'HUEHUETENANGO 2': 'HUEHUETENANGO II',
    'GENERADORA COSTA SUR': 'COSTA SUR',
    'ROOSVELT': 'ROOSEVELT',
    'TACANA': 'TACANÁ',
    'SAN ANTONIO SUCHITEPEQUEZ': 'SAN ANTONIO SUCHITEPEQUEZ',
    'SAN ANTONIO SUCHITEPÉQUEZ': 'SAN ANTONIO SUCHITEPEQUEZ',
    'FRAY BARTOLOME DE LAS CASAS': 'Fray Bartolomé de las Casas',
    'FRAY BARTOLOMÉ DE LAS CASAS': 'Fray Bartolomé de las Casas',
    'FRAY BARTOLOME': 'Fray Bartolomé de las Casas',
    'FRAY BARTOLOMÉ': 'Fray Bartolomé de las Casas',
    'GENOR': 'GENOSA',
    'RIO BOBOS': 'RIO BOBOS',
    'MONTE MARIA': 'MONTE MARIA',
    'MONTE MARÍA': 'MONTE MARIA',
    'CHOCOLA': 'CHOCOLÁ',
    'PANZOS': 'PANZOS 69 KV',
    'PANZÓS': 'PANZOS 69 KV',
    'EL ESTOR': 'ESTOR',
    'LA ESPERANZA': 'ESPERANZA',
    'LA LIBERTAD': 'LA LIBERTAD I',
    'LIBERTAD': 'LA LIBERTAD I',
    'LA LIBERTAD 1': 'LA LIBERTAD I',
    'LIBERTAD 1': 'LA LIBERTAD I',
    'LA LIBERTAD 2': 'LA LIBERTAD II',
    'LIBERTAD 2': 'LA LIBERTAD II',
    'SUBESTACION LA LIBERTAD II': 'LA LIBERTAD II',
    'SUBESTACIÓN LA LIBERTAD II': 'LA LIBERTAD II',
    'SAN SEBASTIAN': 'SAN SEBASTIAN',
    'SAN SEBASTIÁN': 'SAN SEBASTIAN',
    'SANTA LUCIA': 'SANTA LUCIA COTZ.',
    'SANTA LUCÍA': 'SANTA LUCIA COTZ.',
    'TECUN UMAN': 'TECUN UMÁN',
    'TECÚN UMÁN': 'TECUN UMÁN',
    'POPTUN': 'POPTÚN',
    'POPTÚN': 'POPTÚN',
    'POPUN': 'POPTÚN',
    'DERIVACION LAGUNA': 'DERIVACIÓN LAGUNA',
    'DERIVACIÓN LAGUNA': 'DERIVACIÓN LAGUNA',
    'HECTOR FLORES': 'HÉCTOR FLORES',
    'HÉCTOR FLORES': 'HÉCTOR FLORES',
    'MALACATAN': 'MALACATÁN',
    'MALACATÁN': 'MALACATÁN',
    'TELEMAN': 'TELEMÁN',
    'TELEMÁN': 'TELEMÁN',
    'MODESTO MENDEZ': 'MODESTO MÉNDEZ',
    'MODESTO MÉNDEZ': 'MODESTO MÉNDEZ',
    'TECULUTAN': 'TECULUTÁN',
    'TECULUTÁN': 'TECULUTÁN',
    'SALAMA': 'SALAMÁ',
    'SALAMÁ': 'SALAMÁ',
    'RIO DULCE': 'Rio Dulce',
    'RÍO DULCE': 'Rio Dulce',
    'RIO GRANDE': 'Río Grande',
    'RÍO GRANDE': 'Río Grande',
    'PALIN': 'PALÍN',
    'PALÍN': 'PALÍN',
    'SANTA MONICA': 'SANTA MÓNICA',
    'SANTA MÓNICA': 'SANTA MÓNICA',
    'PANTALEON': 'PANTALEÓN',
    'PANTALEÓN': 'PANTALEÓN',
    'SANTA MARIA': 'SANTA MARÍA',
    'SANTA MARÍA': 'SANTA MARÍA',
    'CANADA': 'CANADÁ',
    'CANADÁ': 'CANADÁ',
    'SAN MARTIN': 'SAN MARTÍN',
    'SAN MARTÍN': 'SAN MARTÍN',
    'LA MAQUINA': 'LA MÁQUINA',
    'LA MÁQUINA': 'LA MÁQUINA',
    'SAN ISIDRO CHAMPERICO': 'SAN ISIDRO',
    'CHAMPERICO': 'CHAMPERICO',
    'LA CRUZ': 'LAS CRUCES',
    'PAINSA': 'PAINSA',
    'SANTA CRUZ': 'SANTA CRUZ EL QUICHE',
    'PUERTO BARRIOS': 'PUERTO BARRIOS',
    'SAN LUCAS': 'SAN LUCAS SACATEPEQUEZ',
    'SAN JUAN SACATEPEQUEZ': 'SAN JUAN SACATEPEQUEZ',
    'SAN JUAN SACATEPÉQUEZ': 'SAN JUAN SACATEPEQUEZ',
    'MAYAN GOLF': 'MAYAN GOLF',
    'LA VEGA II': 'LA VEGA II',
    'CAFETAL': 'CAFETAL',
    'TAXISCO': 'TAXISCO',
    'MOYUTA': 'MOYUTA',
    'COATEPEQUE': 'COATEPEQUE',
    'ALASKA': 'ALASKA',
    'LOS BRILLANTES': 'LOS BRILLANTES',
    'BARBERENA': 'BARBERENA',
    'PAMPLONA': 'PAMPLONA',
    'LA CASTELLANA': 'LA CASTELLANA',
    'AURORA': 'AURORA',
    'JALAPA': 'JALAPA',
    'LA LIBERTAD II': 'LA LIBERTAD II',
    'NORTE': 'NORTE',
    'CHIMALTENANGO': 'CHIMALTENANGO',
    'GUATEMALA NORTE': 'GUATEMALA NORTE',
    'GUADALUPE': 'GUADALUPE',
    'MAZATENANGO': 'MAZATENANGO',
    'ESCUINTLA': 'ESCUINTLA I',
    'GRAN USUARIO ACEROS SUÁREZ': 'ACEROS SUÁREZ',
    'GRAN USUARIO ACEROS SUAREZ': 'ACEROS SUÁREZ',
    'ACEROS SUÁREZ': 'ACEROS SUÁREZ',
    'ACEROS SUAREZ': 'ACEROS SUÁREZ',
}


def load_substations():
    df = pd.read_csv(SUBS_CSV)
    df = df.dropna(subset=['latitud', 'longitud'])
    return df


def build_name_index(subs_df):
    index = {}
    for _, row in subs_df.iterrows():
        name = str(row['nombre']).strip()
        lat, lon = float(row['latitud']), float(row['longitud'])
        v = int(row['voltaje_kv']) if pd.notna(row['voltaje_kv']) else 0
        key = name.upper().strip()
        if key not in index or v > index[key][3]:
            index[key] = (lat, lon, name, v)
    return index


def match_substation(name_raw, name_index):
    if not name_raw or not isinstance(name_raw, str):
        return None
    name = name_raw.strip().upper()

    if name in ALIASES:
        alias_target = ALIASES[name].upper()
        if alias_target in name_index:
            r = name_index[alias_target]
            return (r[0], r[1], r[2])

    if name in name_index:
        r = name_index[name]
        return (r[0], r[1], r[2])

    for key, r in name_index.items():
        if name in key or key in name:
            return (r[0], r[1], r[2])

    import unicodedata
    def strip_accents(s):
        return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    name_stripped = strip_accents(name)
    for key, r in name_index.items():
        if strip_accents(key) == name_stripped:
            return (r[0], r[1], r[2])

    return None


def parse_wkt_linestring(wkt):
    if not isinstance(wkt, str):
        return []
    m = re.search(r'LINESTRING\s*\((.*)\)', wkt, re.IGNORECASE)
    if not m:
        return []
    coords = []
    for pair in m.group(1).split(','):
        parts = pair.strip().split()
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
                coords.append([lat, lon])
            except ValueError:
                continue
    return coords


def compute_duration_hours(h_ini, h_fin):
    """Compute duration in hours from HH:MM strings."""
    if not h_ini:
        return 0.0
    try:
        parts_ini = h_ini.split(':')
        mins_ini = int(parts_ini[0]) * 60 + int(parts_ini[1])
    except (ValueError, IndexError):
        return 0.0

    if not h_fin:
        return 0.0  # unknown end
    try:
        parts_fin = h_fin.split(':')
        mins_fin = int(parts_fin[0]) * 60 + int(parts_fin[1])
    except (ValueError, IndexError):
        return 0.0

    diff = mins_fin - mins_ini
    if diff < 0:
        diff += 24 * 60  # crosses midnight
    return diff / 60.0


def map_causa_display(causa):
    """Map Gemini causa to display label."""
    mapping = {
        'disparo': 'Disparo',
        'mantenimiento_programado': 'Mantenimiento',
        'trabajos_forzados': 'Trabajos forzados',
        'vegetacion': 'Vegetacion',
        'clima': 'Clima',
        'bajo_voltaje': 'Bajo voltaje',
        'sobrecarga': 'Sobrecarga',
        'falla_equipo': 'Falla de equipo',
        'regulacion_voltaje': 'Regulacion voltaje',
        'error_humano': 'Error humano',
        'otro': 'Otro',
    }
    return mapping.get(causa, causa or 'Otro')


def map_tipo_display(tipo):
    """Map Gemini tipo to simplified category for colors."""
    if tipo in ('disparo',):
        return 'disparo'
    elif tipo in ('mantenimiento',):
        return 'mantenimiento'
    elif tipo in ('desenergizacion',):
        return 'desenergizacion'
    elif tipo in ('maniobra', 'energizacion', 'redespacho'):
        return 'maniobra'
    elif tipo in ('generacion_forzada', 'regulacion_voltaje'):
        return 'generacion'
    else:
        return 'otro'


def main():
    print("Cargando datos...")
    subs_df = load_substations()
    lines_df = pd.read_csv(LINES_CSV)

    # Load Gemini sub-events
    with open(GEMINI_JSON, 'r', encoding='utf-8') as f:
        subeventos = json.load(f)

    # Load narrativas for fecha lookup
    with open(NARR_JSON, 'r', encoding='utf-8') as f:
        narrativas = json.load(f)
    fecha_map = {n['id']: n['fecha'] for n in narrativas}

    name_index = build_name_index(subs_df)
    print(f"  Subestaciones geodata: {len(subs_df)}")
    print(f"  Lineas geodata: {len(lines_df)}")
    print(f"  Sub-eventos Gemini: {len(subeventos)}")

    # ─── Process substations for JSON ─────────────────────────────────
    _GENERADORAS_NOMBRES = {
        'ORZUNIL', 'GENOSA', 'TULULA', 'XACBAL',
        'SAN ANTONIO EL SITIO', 'SAN ANTONIO EL SITIO MANIOBRAS',
        'PALO GORDO MANIOBRAS', 'COVADONGA', 'COSTA SUR', 'ENRON',
        'CHOCOLÁ', 'CHOCOLA', 'PRONICO-P',
        'SUB MANIOBRAS HIDROELÉCTRICA LA LIBERTAD',
    }

    subs_json = []
    for _, row in subs_df.iterrows():
        nombre_upper = str(row['nombre']).strip().upper()
        es_gen = nombre_upper in _GENERADORAS_NOMBRES
        if not es_gen and str(row.get('fuente', '')) == 'Subestaciones V8':
            try:
                attrs = json.loads(str(row.get('attrs_json', '') or '{}'))
                es_gen = attrs.get('Tipo') == 'Generador'
            except Exception:
                pass
        subs_json.append({
            'name': str(row['nombre']),
            'lat': float(row['latitud']),
            'lon': float(row['longitud']),
            'v': int(row['voltaje_kv']) if pd.notna(row['voltaje_kv']) else 0,
            'g': es_gen,
        })

    # ─── Process transmission lines for JSON ─────────────────────────
    def simplify_coords(coords, max_points=80):
        if len(coords) <= max_points:
            return coords
        step = len(coords) / max_points
        result = [coords[int(i * step)] for i in range(max_points - 1)]
        result.append(coords[-1])
        return result

    lines_json = []
    for _, row in lines_df.iterrows():
        coords = parse_wkt_linestring(row['geometry_wkt'])
        if not coords:
            continue
        coords = simplify_coords(coords)
        lines_json.append({
            'name': str(row['nombre']),
            'v': int(row['voltaje_kv']) if pd.notna(row['voltaje_kv']) else 0,
            'coords': coords,
        })

    # ─── Process Gemini sub-events ────────────────────────────────────
    print("Procesando sub-eventos de Gemini...")
    all_events = []
    all_subevents = []   # todos los sub-eventos procesados (geolocalizados o no) para la pestaña "Procesados"/"Raw"
    matched_count = 0
    unmatched_subs = Counter()

    # Excluir de las pestanas Procesados/Raw las narrativas de categoria
    # "Aspectos operativos" (solo dejar las de Sistemas de transmision).
    def _norm_narr(t):
        return re.sub(r'\s+', ' ', (t or '')).strip().lower()
    oper_texts = set()
    _full_path = BASE / "narrativas_full.json"
    if _full_path.exists():
        with open(_full_path, encoding='utf-8') as _f:
            for _n in json.load(_f):
                if str(_n.get('categoria', '')).lower().startswith('aspectos'):
                    oper_texts.add(_norm_narr(_n.get('narrativa', '')))
        print(f"  Aspectos operativos excluidos de las pestanas: {len(oper_texts)} narrativas")

    for sev in subeventos:
        sev_id = sev.get('id')
        fecha = fecha_map.get(sev_id, '')
        tipo_raw = sev.get('tipo', 'otro')
        tipo = map_tipo_display(tipo_raw)
        causa = map_causa_display(sev.get('causa', 'otro'))

        h_ini = sev.get('hora_inicio', '')
        h_fin = sev.get('hora_fin', '')
        duracion = compute_duration_hours(h_ini, h_fin)

        activo = sev.get('activo_nombre', '')
        narrativa = sev.get('narrativa_original', '')
        carga = sev.get('carga_afectada', False)
        mw = sev.get('mw_perdidos')
        codigo = sev.get('codigo_mantenimiento', '')
        generadores = sev.get('generadores_afectados', [])

        hora_str = ''
        if h_ini:
            hora_str = h_ini
            if h_fin:
                hora_str += f'-{h_fin}'

        event_base = {
            'fecha': fecha,
            'hora': hora_str,
            'tipo': tipo,
            'tipo_detalle': tipo_raw,
            'causa': causa,
            'duracion': round(duracion, 4),
            'activo': activo[:100],
            'narrativa': narrativa.replace('"', "'").replace('\n', ' ').strip(),
            'carga_afectada': carga,
            'mw_perdidos': mw,
            'codigo': codigo or '',
            'generadores': ', '.join(generadores) if generadores else '',
        }

        # Geolocate using subestaciones_afectadas
        subs_afectadas = sev.get('subestaciones_afectadas', [])

        # Registro plano del sub-evento procesado (independiente de geolocalizacion),
        # omitiendo los de categoria "Aspectos operativos".
        if _norm_narr(event_base['narrativa']) not in oper_texts:
            all_subevents.append({
                'nid': sev_id,
                'fecha': fecha,
                'tipo': tipo,
                'tipo_detalle': tipo_raw,
                'causa': causa,
                'hora': hora_str,
                'duracion': round(duracion, 4),
                'activo': activo[:120],
                'subs': ', '.join(s for s in subs_afectadas if isinstance(s, str)),
                'narrativa': event_base['narrativa'],
            })
        found = False

        for sub_name in subs_afectadas:
            result = match_substation(sub_name, name_index)
            if result:
                lat, lon, matched_name = result
                ev = dict(event_base)
                ev['lat'] = lat
                ev['lon'] = lon
                ev['sub'] = matched_name
                all_events.append(ev)
                found = True
                matched_count += 1
            else:
                unmatched_subs[sub_name] += 1

        # If no substations matched, try from activo_nombre
        if not found and not subs_afectadas:
            # Try extracting from activo name
            for pattern in [r'SE\s+(.+)', r'en\s+(?:SE\s+)?(.+)']:
                m = re.search(pattern, activo, re.IGNORECASE)
                if m:
                    result = match_substation(m.group(1).strip(), name_index)
                    if result:
                        lat, lon, matched_name = result
                        ev = dict(event_base)
                        ev['lat'] = lat
                        ev['lon'] = lon
                        ev['sub'] = matched_name
                        all_events.append(ev)
                        found = True
                        matched_count += 1
                        break

    print(f"  Eventos geolocalizados: {matched_count}")
    print(f"  Total registros para mapa: {len(all_events)}")
    if unmatched_subs:
        print(f"  Subestaciones sin match ({len(unmatched_subs)}):")
        for name, count in unmatched_subs.most_common(15):
            print(f"    {name} ({count}x)")

    # Get unique causas and tipos for filter panel
    causas_set = sorted(set(ev['causa'] for ev in all_events))
    tipos_detalle_set = sorted(set(ev['tipo_detalle'] for ev in all_events))

    # ─── Generate HTML ────────────────────────────────────────────────
    print("Generando HTML...")

    subs_js = json.dumps(subs_json, ensure_ascii=False)
    lines_js = json.dumps(lines_json, ensure_ascii=False)
    events_js = json.dumps(all_events, ensure_ascii=False)
    subevents_js = json.dumps(all_subevents, ensure_ascii=False)

    # ─── Capa de Vulnerabilidad Topologica (opcional, si existen los archivos) ─
    topo_subs_js, topo_lines_js = "[]", "[]"
    tps, tpl = BASE / "subestaciones_topologia.json", BASE / "lineas_topologia.json"
    if tps.exists() and tpl.exists():
        tsubs = json.load(open(tps, encoding="utf-8"))
        tlines = json.load(open(tpl, encoding="utf-8"))
        coordmap = {s["subestacion"]: (s["latitud"], s["longitud"])
                    for s in tsubs if s.get("latitud") is not None}
        topo_subs_out = [s for s in tsubs if s.get("latitud") is not None and s.get("en_red_principal")]
        topo_lines_out = []
        for L in tlines:
            if not L.get("en_red_principal"):
                continue
            o, d = coordmap.get(L["origen"]), coordmap.get(L["destino"])
            if o and d:
                LL = dict(L); LL["o"] = list(o); LL["d"] = list(d)
                topo_lines_out.append(LL)
        topo_subs_js = json.dumps(topo_subs_out, ensure_ascii=False)
        topo_lines_js = json.dumps(topo_lines_out, ensure_ascii=False)
        print(f"  Topologia: {len(topo_subs_out)} subestaciones, {len(topo_lines_out)} lineas")

    # ─── Contorno de departamentos (para la capa Satelital del 3D) ─────
    deptos_geo_js = "null"
    deptos_geojson = BASE / "geodata" / "departamentos_gt.geojson"
    if deptos_geojson.exists():
        deptos_geo_js = deptos_geojson.read_text(encoding="utf-8").strip()

    # Build filter checkboxes dynamically
    tipo_labels = {
        'disparo': 'Disparo',
        'desenergizacion': 'Desenergizacion',
        'mantenimiento': 'Mantenimiento',
        'maniobra': 'Maniobra',
        'generacion_forzada': 'Generacion forzada',
        'regulacion_voltaje': 'Regulacion voltaje',
        'redespacho': 'Redespacho',
        'energizacion': 'Energizacion',
        'otro': 'Otro',
    }
    tipo_checkboxes = ''
    for t in tipos_detalle_set:
        label = tipo_labels.get(t, t)
        tipo_checkboxes += f'            <label><input type="checkbox" class="tipo-cb" value="{t}" checked> {label}</label>\n'

    # Variante de los checkboxes de tipo para el panel de filtros de la vista 3D
    tipo_checkboxes_3d = ''
    for t in tipos_detalle_set:
        label = tipo_labels.get(t, t)
        tipo_checkboxes_3d += f'            <label class="d3-fcheck"><input type="checkbox" class="tipo3-cb" value="{t}" checked> {label}</label>\n'

    fechas = sorted(set(ev['fecha'] for ev in all_events if ev['fecha']))
    date_min = '2026-01-01'
    date_max = fechas[-1] if fechas else '2026-05-31'

    _MESES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']
    try:
        _dm = datetime.strptime(date_max, '%Y-%m-%d')
        fecha_display = f"{_dm.day} {_MESES[_dm.month-1]} {_dm.year}"
    except Exception:
        fecha_display = date_max

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Atlas de Eventos del SNI - Gemini AI - CNEE Guatemala</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"/>
<style>
@import url('https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500;600;700&display=swap');
:root {{
    /* Paleta oficial CNEE: navy #233453 + dorado #CE9332 */
    --navy:#233453; --navy-950:#101a2e; --navy-900:#15223a; --navy-800:#1b2a47;
    --navy-700:#233453; --navy-650:#2a3d60; --navy-600:#324669; --navy-500:#3d527a;
    --gold:#CE9332; --gold-300:#E2B45F; --gold-100:#F0D399;
    --gold-veil:rgba(206,147,50,.14); --gold-line:rgba(206,147,50,.34);
    --white:#fff; --ink-100:#eef3fb; --ink-300:#bcc8de; --ink-400:#8c9bb8;
    --hair:rgba(255,255,255,.09); --hair-strong:rgba(255,255,255,.16);
    --alert:#E0584F; --alert-soft:rgba(224,88,79,.16);
    --cnee-font:'Century Gothic','Jost','Questrial',ui-rounded,'Segoe UI',system-ui,sans-serif;
    --ease:cubic-bezier(.22,.61,.36,1);
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: var(--cnee-font); -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility; }}
#map {{ width:100vw; height:100vh; }}

.title-overlay {{
    position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
    z-index: 1000; background: var(--navy-700); color: var(--white);
    padding: 11px 30px; border-radius: 11px; font-size: 16px; font-weight: 700;
    letter-spacing: 0.4px; text-align: center;
    box-shadow: 0 14px 40px rgba(0,0,0,.45);
    border: 1px solid var(--hair); border-top: 2px solid var(--gold);
    pointer-events: none;
}}
.title-overlay small {{ font-weight: 400; color: var(--ink-300); display: block; font-size: 11px; margin-top: 3px; letter-spacing: .02em; }}

.info-panel {{
    position: absolute; top: 70px; right: 10px; z-index: 1000;
    background: linear-gradient(180deg, var(--navy-650) 0, var(--navy-700) 64px);
    color: var(--ink-100); padding: 15px 16px 16px; width: 300px; font-size: 12px;
    border: 1px solid var(--hair); border-top: 3px solid var(--gold);
    border-radius: 13px; box-shadow: 0 18px 50px rgba(0,0,0,.5);
    max-height: calc(100vh - 90px); overflow-y: auto;
    transition: max-height 0.3s ease;
}}
.info-panel.collapsed {{ max-height: 56px; overflow: hidden; }}
.info-panel h3 {{
    color: var(--white); margin: 0 0 12px; padding-bottom: 12px; font-size: 16px; font-weight: 700;
    border-bottom: 1px solid var(--hair); display: flex; align-items: center; gap: 8px;
    cursor: pointer; user-select: none;
}}
.info-panel h3 .toggle-icon {{ margin-left: auto; font-size: 12px; color: var(--gold-300); }}
.info-panel .stat {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 11px 2px; border-bottom: 1px solid var(--hair); font-size: 12.5px; }}
.info-panel .stat > span:first-child {{ color: var(--ink-300); }}
.info-panel .stat-val {{ font-weight: 700; font-size: 15px; color: var(--white); font-variant-numeric: tabular-nums; white-space: nowrap; }}
.info-panel .stat-val.red {{ color: var(--alert); }}
.info-panel .stat-val.orange {{ color: var(--gold-300); }}
.info-panel .stat-val.blue {{ color: #6B97C4; }}
.info-panel .stat-val.green {{ color: var(--gold-300); }}
.info-panel h4 {{ color: var(--gold-300); margin: 16px 0 8px; font-size: 11px; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }}
.info-panel .rank {{ padding: 6px 6px; font-size: 12px; border-radius: 8px; transition: background .15s; }}
.info-panel .rank:hover {{ background: rgba(255,255,255,.04); }}
.info-panel .rank-num {{ display: inline-grid; place-items: center; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 6px; background: var(--gold-veil); color: var(--gold-100); font-weight: 700; font-size: 11px; margin-right: 8px; }}

/* Pestanas del panel (Resumen / Procesados / Raw) */
.info-panel .tab-bar {{ display: flex; gap: 3px; margin-bottom: 12px; }}
.info-panel .tab-btn {{
    flex: 1; padding: 7px 2px; font-family: inherit; font-size: 10px; font-weight: 600;
    cursor: pointer; background: var(--navy-900); color: var(--ink-300);
    border: 1px solid var(--hair); border-radius: 7px; transition: .15s var(--ease);
    white-space: nowrap;
}}
.info-panel .tab-btn:hover {{ color: var(--white); background: var(--navy-650); }}
.info-panel .tab-btn.active {{ background: var(--gold); color: var(--navy-950); border-color: var(--gold); }}
.info-panel .tab-count {{ font-size: 11px; color: var(--ink-400); margin-bottom: 8px; }}
.info-panel .ev-row {{ padding: 8px 7px; border-bottom: 1px solid var(--hair); font-size: 12px; line-height: 1.45; }}
.info-panel .ev-row:hover {{ background: rgba(255,255,255,.04); }}
.info-panel .ev-clickable {{ cursor: pointer; }}
.info-panel .ev-expand {{ float: right; color: var(--ink-400); font-size: 9px; margin-top: 3px; }}
.info-panel .ev-row .ev-date {{ color: var(--gold-300); font-weight: 600; font-size: 11px; }}
.info-panel .ev-row .ev-tag {{ display: inline-block; padding: 1px 6px; border-radius: 5px; font-size: 9px; font-weight: 700; margin-left: 6px; vertical-align: middle; text-transform: uppercase; letter-spacing: .04em; }}
.info-panel .ev-row .ev-activo {{ color: var(--white); font-weight: 600; margin-top: 2px; }}
.info-panel .ev-row .ev-meta {{ color: var(--ink-400); font-size: 11px; margin-top: 2px; }}
.info-panel .ev-row .ev-narr {{ color: var(--ink-300); font-size: 11px; margin-top: 4px; padding: 6px 8px; background: rgba(255,255,255,.05); border-radius: 6px; border-left: 2px solid var(--gold-line); }}
.tag-disparo {{ background: var(--alert-soft); color: #f2a39c; }}
.tag-mantenimiento {{ background: var(--gold-veil); color: var(--gold-300); }}
.tag-desenergizacion {{ background: rgba(156,39,176,.22); color: #ce93d8; }}
.tag-maniobra {{ background: rgba(107,151,196,.18); color: #8fb4dc; }}
.tag-generacion {{ background: rgba(155,134,194,.2); color: #b9a6e0; }}
.tag-otro {{ background: rgba(255,255,255,.08); color: var(--ink-300); }}

.toggle-panel {{
    position: absolute; top: 70px; right: 10px; z-index: 1001;
    background: var(--navy-700); color: var(--white); padding: 8px 14px;
    border-radius: 9px; cursor: pointer; font-size: 12px; font-weight: 600;
    border: 1px solid var(--hair); border-top: 2px solid var(--gold);
    box-shadow: 0 14px 40px rgba(0,0,0,.4);
    display: none;
}}
.toggle-panel:hover {{ background: var(--navy-650); }}

.filter-panel {{
    position: absolute; top: 366px; left: 10px; z-index: 1000;
    background: linear-gradient(180deg, var(--navy-650) 0, var(--navy-700) 64px);
    color: var(--ink-100); padding: 15px 16px 16px; width: 250px; font-size: 11px;
    border: 1px solid var(--hair); border-top: 3px solid var(--gold);
    border-radius: 13px; box-shadow: 0 18px 50px rgba(0,0,0,.5);
    max-height: calc(100vh - 386px); overflow-y: auto;
    transition: max-height 0.3s ease;
}}
.filter-panel.collapsed {{ max-height: 50px; overflow: hidden; }}
.filter-panel h3 {{
    color: var(--white); margin: 0 0 12px; padding-bottom: 12px; font-size: 15px; font-weight: 700;
    border-bottom: 1px solid var(--hair); cursor: pointer; user-select: none;
}}
.filter-panel h3 .toggle-icon {{ float: right; font-size: 12px; color: var(--gold-300); }}
.filter-panel label {{ display: flex; align-items: center; gap: 9px; padding: 5px 6px; cursor: pointer; border-radius: 8px; font-size: 13px; color: var(--ink-100); transition: background .15s; }}
.filter-panel label:hover {{ background: rgba(255,255,255,.045); color: var(--white); }}
.filter-panel input[type="checkbox"] {{ accent-color: var(--gold); width: 15px; height: 15px; flex: none; margin: 0; }}
.filter-panel input[type="date"] {{
    flex: 1; min-width: 0; font-family: inherit; font-size: 12px;
    color: var(--ink-100); background: var(--navy-900);
    border: 1px solid var(--hair); border-radius: 9px; padding: 8px 9px;
    transition: .2s var(--ease);
}}
.filter-panel input[type="date"]:focus {{ outline: none; border-color: var(--gold); box-shadow: 0 0 0 3px var(--gold-veil); }}
.filter-panel input[type="date"]::-webkit-calendar-picker-indicator {{ filter: invert(.75) sepia(.6) saturate(4) hue-rotate(2deg); opacity: .8; cursor: pointer; }}
.filter-section {{ margin-bottom: 16px; }}
.filter-section h4 {{ color: var(--gold-300); margin: 0 0 9px; font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }}
.filter-btn {{
    font-family: inherit; background: var(--gold); color: var(--navy-950); border: 0;
    padding: 9px 14px; border-radius: 9px; cursor: pointer; font-size: 13px; font-weight: 600;
    transition: .2s var(--ease);
}}
.filter-btn:hover {{ background: var(--gold-300); box-shadow: 0 6px 18px rgba(206,147,50,.36); }}
.filter-btn.reset {{ width: 100%; background: transparent; color: #f2a39c; border: 1px solid rgba(224,88,79,.5); }}
.filter-btn.reset:hover {{ background: var(--alert-soft); color: #ffc4bd; border-color: var(--alert); }}
.filter-links {{ margin: 4px 0 6px; }}
.filter-links a {{ color: var(--ink-400); cursor: pointer; font-size: 11px; font-weight: 600; margin-right: 4px; padding: 3px 7px; border-radius: 7px; text-decoration: none; transition: .18s var(--ease); }}
.filter-links a:hover {{ color: var(--gold-300); background: var(--gold-veil); }}

.legend {{
    position: absolute; bottom: 30px; right: 10px; z-index: 1000;
    background: linear-gradient(180deg, var(--navy-650) 0, var(--navy-700) 64px);
    color: var(--ink-100); padding: 15px 16px 16px; font-size: 11px;
    border: 1px solid var(--hair); border-top: 3px solid var(--gold);
    border-radius: 13px; box-shadow: 0 18px 50px rgba(0,0,0,.5);
    transition: max-height 0.3s ease;
}}
.legend.collapsed {{ max-height: 48px; overflow: hidden; }}
.legend h3 {{
    color: var(--white); margin: 0 0 11px; padding-bottom: 10px; font-size: 14px; font-weight: 700;
    border-bottom: 1px solid var(--hair); cursor: pointer; user-select: none;
}}
.legend h3 .toggle-icon {{ float: right; font-size: 12px; color: var(--gold-300); }}
.legend h4 {{ color: var(--gold-300); margin-bottom: 11px; font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; }}
.legend-item {{ display: flex; align-items: center; gap: 11px; margin: 8px 0; font-size: 13px; color: var(--ink-100); }}
.legend-color {{ width: 28px; height: 4px; margin: 0; border-radius: 3px; flex: none; }}
.legend-circle {{ width: 13px; height: 13px; border-radius: 50%; margin: 0; flex: none; }}
.legend-sep {{ border-top: 1px solid var(--hair); margin: 13px 0; }}

.leaflet-popup-content-wrapper {{
    background: var(--navy-700) !important; color: var(--ink-100) !important;
    border-radius: 11px !important; box-shadow: 0 18px 50px rgba(0,0,0,.55) !important;
    border: 1px solid var(--hair) !important; border-top: 3px solid var(--gold) !important;
}}
.leaflet-popup-tip {{ background: var(--navy-700) !important; }}
.leaflet-popup-content {{ font-size: 12px; line-height: 1.5; font-family: var(--cnee-font); }}
.leaflet-popup-content h3 {{ color: var(--gold-300); margin: 0 0 6px; font-size: 14px; }}
.leaflet-popup-content .ev-type {{ font-size: 11px; margin: 2px 0; }}
.leaflet-popup-content .ev-list {{ max-height: 250px; overflow-y: auto; margin-top: 8px; }}
.leaflet-popup-content .ev-item {{ padding: 4px 0; border-top: 1px solid var(--hair); font-size: 11px; }}
.leaflet-popup-content .ev-date {{ color: var(--gold-300); }}
.leaflet-popup-content .ev-disp {{ color: var(--alert); font-weight: 600; }}
.leaflet-popup-content .ev-mant {{ color: var(--gold); }}
.leaflet-popup-content .ev-man {{ color: #6B97C4; }}
.leaflet-popup-content .ev-gen {{ color: #9B86C2; }}
.leaflet-popup-content .ev-desen {{ color: #ce93d8; font-weight: 600; }}

.badge {{
    display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 9px;
    font-weight: 600; margin-left: 4px; vertical-align: middle;
}}
.badge-carga {{ background: var(--alert-soft); color: var(--alert); border: 1px solid rgba(224,88,79,.3); }}
.badge-mw {{ background: var(--gold-veil); color: var(--gold-300); border: 1px solid var(--gold-line); }}
.badge-codigo {{ background: rgba(107,151,196,.18); color: #6B97C4; border: 1px solid rgba(107,151,196,.3); }}

/* Control de capas de Leaflet — tematizado CNEE */
.leaflet-control-layers {{
    background: var(--navy-700) !important; color: var(--ink-100) !important;
    border: 1px solid var(--hair) !important; border-top: 3px solid var(--gold) !important;
    border-radius: 11px !important; box-shadow: 0 14px 40px rgba(0,0,0,.45) !important;
}}
.leaflet-control-layers-expanded {{ padding: 12px 14px !important; font-family: var(--cnee-font) !important; font-size: 13px; }}
.leaflet-control-layers label {{ color: var(--ink-100) !important; margin: 4px 0 !important; }}
.leaflet-control-layers-selector {{ accent-color: var(--gold) !important; margin-right: 6px; }}
.leaflet-control-layers-separator {{ border-top: 1px solid var(--hair) !important; }}
.leaflet-control-layers-toggle {{ background-color: var(--navy-700) !important; border-radius: 9px !important; border-top: 2px solid var(--gold) !important; }}
.leaflet-bar a, .leaflet-bar a:hover {{ background: var(--navy-700) !important; color: var(--ink-100) !important; border-bottom-color: var(--hair) !important; }}
.leaflet-bar a:hover {{ background: var(--navy-650) !important; }}

/* ─── Vista 3D (deck.gl) ─────────────────────────────────────────── */
.btn-3d {{
    position: absolute; bottom: 28px; left: 50%; transform: translateX(-50%);
    z-index: 1500; background: var(--gold); color: var(--navy-950); border: 0;
    padding: 11px 22px; border-radius: 999px; font-family: var(--cnee-font);
    font-weight: 700; font-size: 14px; cursor: pointer;
    box-shadow: 0 10px 30px rgba(206,147,50,.45); transition: .2s var(--ease);
}}
.btn-3d:hover {{ background: var(--gold-300); box-shadow: 0 12px 34px rgba(206,147,50,.55); }}
#deck3d {{ position: fixed; inset: 0; z-index: 2000; display: none; background: var(--navy-950); }}
#deck3dCanvas {{ position: absolute; inset: 0; }}
.d3-hud {{ position: absolute; z-index: 5; font-family: var(--cnee-font); }}
.d3-title {{
    top: 14px; left: 50%; transform: translateX(-50%); text-align: center;
    background: var(--navy-700); border: 1px solid var(--hair); border-top: 2px solid var(--gold);
    padding: 11px 30px; border-radius: 11px; font-weight: 700; font-size: 16px; color: var(--white);
    box-shadow: 0 14px 40px rgba(0,0,0,.45); pointer-events: none;
}}
.d3-title small {{ display: block; font-weight: 400; color: var(--ink-300); font-size: 11px; margin-top: 3px; }}
.d3-back {{
    position: absolute; top: 18px; right: 18px; z-index: 6;
    background: var(--navy-700); color: var(--white); border: 1px solid var(--hair); border-top: 2px solid var(--gold);
    padding: 9px 16px; border-radius: 9px; font-family: var(--cnee-font); font-weight: 600; font-size: 13px;
    cursor: pointer; box-shadow: 0 14px 40px rgba(0,0,0,.4); transition: .18s var(--ease);
}}
.d3-back:hover {{ background: var(--alert); border-color: var(--alert); }}
.d3-panel {{
    top: 84px; left: 18px; width: 240px;
    background: linear-gradient(180deg, var(--navy-650) 0, var(--navy-700) 64px);
    border: 1px solid var(--hair); border-top: 3px solid var(--gold); border-radius: 13px;
    box-shadow: 0 18px 50px rgba(0,0,0,.5); padding: 15px 16px 16px;
    max-height: calc(100vh - 110px); overflow-y: auto;
}}
.d3-panel h4 {{ color: var(--gold-300); font-size: 11px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; margin: 0 0 8px; }}
.d3-panel h4:not(:first-child) {{ margin-top: 14px; }}
.d3-seg {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.d3-seg button {{
    flex: 1 1 auto; font-family: inherit; font-size: 12px; font-weight: 600; cursor: pointer;
    padding: 7px 9px; border-radius: 8px; border: 1px solid var(--hair);
    background: rgba(255,255,255,.05); color: var(--ink-300); transition: .18s var(--ease);
}}
.d3-seg button:hover {{ color: var(--white); }}
.d3-seg button.active {{ background: var(--gold); color: var(--navy-950); border-color: var(--gold); }}
.d3-check {{ display: flex; align-items: center; gap: 9px; margin-top: 14px; font-size: 13px; color: var(--ink-100); cursor: pointer; }}
.d3-check input {{ accent-color: var(--gold); width: 15px; height: 15px; }}
.d3-panel input[type="range"] {{ width: 100%; accent-color: var(--gold); margin-top: 4px; }}
.d3-legend {{ margin-top: 10px; }}
.d3-bar {{ height: 10px; border-radius: 5px; background: linear-gradient(90deg, #CE9332, #E0584F); }}
.d3-ends {{ display: flex; justify-content: space-between; font-size: 11px; color: var(--ink-400); margin-top: 4px; }}
.d3-hint {{ bottom: 16px; left: 50%; transform: translateX(-50%); font-size: 11px; color: var(--ink-400); background: rgba(16,26,46,.7); padding: 6px 14px; border-radius: 999px; border: 1px solid var(--hair); pointer-events: none; }}
.deck-tooltip {{
    font-family: var(--cnee-font) !important; background: var(--navy-700) !important; color: var(--ink-100) !important;
    border: 1px solid var(--hair) !important; border-top: 2px solid var(--gold) !important;
    border-radius: 9px !important; padding: 8px 11px !important; font-size: 12px !important;
    box-shadow: 0 14px 40px rgba(0,0,0,.5) !important;
}}
.d3-fdate {{ display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }}
.d3-fdate input[type="date"] {{ flex: 1; min-width: 0; font-family: inherit; font-size: 11.5px; color: var(--ink-100); background: var(--navy-900); border: 1px solid var(--hair); border-radius: 8px; padding: 6px 7px; }}
.d3-fdate span {{ color: var(--ink-400); }}
.d3-fbtn {{ width: 100%; font-family: inherit; background: var(--gold); color: var(--navy-950); border: 0; padding: 8px 12px; border-radius: 8px; cursor: pointer; font-size: 12px; font-weight: 600; }}
.d3-fbtn:hover {{ background: var(--gold-300); }}
.d3-fbtn.reset {{ background: transparent; color: #f2a39c; border: 1px solid rgba(224,88,79,.5); margin-top: 8px; }}
.d3-fbtn.reset:hover {{ background: var(--alert-soft); color: #ffc4bd; }}
.d3-fgroup {{ margin-top: 10px; }}
.d3-fhead {{ display: flex; justify-content: space-between; align-items: baseline; font-size: 11px; font-weight: 600; letter-spacing: .1em; text-transform: uppercase; color: var(--gold-300); margin: 0 0 5px; }}
.d3-fhead a {{ color: var(--ink-400); cursor: pointer; font-size: 10px; font-weight: 600; text-transform: none; letter-spacing: 0; margin-left: 5px; }}
.d3-fhead a:hover {{ color: var(--gold-300); }}
.d3-fcheck {{ display: flex; align-items: center; gap: 8px; padding: 3px 4px; border-radius: 7px; font-size: 12.5px; color: var(--ink-100); cursor: pointer; }}
.d3-fcheck:hover {{ background: rgba(255,255,255,.045); }}
.d3-fcheck input {{ accent-color: var(--gold); width: 14px; height: 14px; flex: none; }}
</style>
</head>
<body>
<div id="map"></div>

<div class="title-overlay">
    ATLAS - POSDESPACHOS
</div>

<div class="info-panel" id="infoPanel">
    <h3 onclick="togglePanel('infoPanel','infoToggleIcon')">&#9889; Posdespachos <span class="toggle-icon" id="infoToggleIcon">&#x25B2;</span></h3>
    <div class="tab-bar">
        <button class="tab-btn active" id="tabbtn-procesados" onclick="switchTab('procesados')">Procesados</button>
        <button class="tab-btn" id="tabbtn-raw" onclick="switchTab('raw')">Raw</button>
    </div>
    <div class="tab-content" id="tab-procesados"></div>
    <div class="tab-content" id="tab-raw" style="display:none;"></div>
    <div style="text-align:right;margin-top:8px;">
        <span style="cursor:pointer;color:#E2B45F;font-size:11px;" onclick="document.getElementById('infoPanel').style.display='none';document.getElementById('toggleBtn').style.display='block';">&#x2715; Cerrar</span>
    </div>
</div>
<div class="toggle-panel" id="toggleBtn" onclick="document.getElementById('infoPanel').style.display='block';this.style.display='none';">&#9776; Panel</div>

<div class="filter-panel" id="filterPanel">
    <h3 onclick="toggleFilterPanel()">Filtros <span class="toggle-icon" id="filterToggleIcon">&#x25B2;</span></h3>
    <div id="filterBody">
        <div class="filter-section">
            <h4>Rango de fechas</h4>
            <div style="display:flex;gap:4px;align-items:center;margin-bottom:4px;">
                <input type="date" id="dateFrom" value="{date_min}">
                <span>-</span>
                <input type="date" id="dateTo" value="{date_max}">
            </div>
            <button class="filter-btn" onclick="applyFilters()">Aplicar</button>
        </div>

        <div class="filter-section">
            <h4>Tipo de evento</h4>
            <div class="filter-links">
                <a onclick="setAll('.tipo-cb',true)">Todos</a>
                <a onclick="setAll('.tipo-cb',false)">Ninguno</a>
            </div>
{tipo_checkboxes}
        </div>

        <div style="text-align:center;margin-top:6px;">
            <button class="filter-btn reset" onclick="resetFilters()">&#x21BA; Reset filtros</button>
        </div>
    </div>
</div>

<div class="legend collapsed" id="legendPanel">
    <h3 onclick="togglePanel('legendPanel','legendToggleIcon')">Leyenda <span class="toggle-icon" id="legendToggleIcon">&#x25BC;</span></h3>
    <h4>Voltaje de Lineas</h4>
    <div class="legend-item"><div class="legend-color" style="background:#d32f2f;height:5px;"></div>400 kV</div>
    <div class="legend-item"><div class="legend-color" style="background:#ff9800;height:4px;"></div>230 kV</div>
    <div class="legend-item"><div class="legend-color" style="background:#1976d2;height:3px;"></div>138 kV</div>
    <div class="legend-item"><div class="legend-color" style="background:#388e3c;height:2px;"></div>69 kV</div>
    <div class="legend-sep"></div>
    <h4>Tipo de Evento</h4>
    <div class="legend-item"><div class="legend-circle" style="background:#ff5252;"></div>Disparo</div>
    <div class="legend-item"><div class="legend-circle" style="background:#ffa726;"></div>Mantenimiento / Desenergizacion</div>
    <div class="legend-item"><div class="legend-circle" style="background:#42a5f5;"></div>Maniobra / Energizacion</div>
    <div class="legend-item"><div class="legend-circle" style="background:#ab47bc;"></div>Generacion forzada</div>
</div>

<div class="legend" id="topoLegend" style="display:none; left:10px; right:auto; bottom:30px;">
    <h4>Vulnerabilidad Topologica</h4>
    <div style="font-size:10px;color:#9aa;margin-bottom:6px;">Color = criticidad estructural (subestaciones y lineas)</div>
    <div class="legend-item"><div class="legend-circle" style="background:#d50000;"></div>Critica</div>
    <div class="legend-item"><div class="legend-circle" style="background:#ff6d00;"></div>Alta</div>
    <div class="legend-item"><div class="legend-circle" style="background:#ffd600;"></div>Media</div>
    <div class="legend-item"><div class="legend-circle" style="background:#00c853;"></div>Baja</div>
    <div class="legend-sep"></div>
    <h4>Subestaciones</h4>
    <div class="legend-item"><div class="legend-circle" style="background:transparent;border:2px solid #ff1744;"></div>Articulacion: su caida divide la red</div>
    <div style="font-size:10px;color:#9aa;margin:2px 0;">Tamano del circulo &asymp; indice de criticidad</div>
    <div class="legend-sep"></div>
    <h4>Lineas</h4>
    <div class="legend-item"><div class="legend-color" style="background:#d50000;height:4px;"></div>Enlace critico sin respaldo (puente)</div>
    <div class="legend-item"><div class="legend-color" style="background:transparent;height:0;border-top:2px dashed #00c853;"></div>Con ruta de respaldo (punteada)</div>
</div>


<button id="btn2d" class="btn-3d" title="Ver en 3D" style="display:none;">&#x26F0;&#xFE0F; Ver en 3D</button>
<div id="lastUpdateBadge" style="position:fixed;bottom:28px;left:10px;z-index:900;background:rgba(11,21,46,0.82);color:#E2B45F;font-size:11px;padding:4px 9px;border-radius:4px;pointer-events:none;border:1px solid rgba(226,180,95,0.3);letter-spacing:0.3px;">&#x1F4C5; &Uacute;ltimo posdespacho: {fecha_display}</div>

<div id="deck3d">
    <div id="deck3dCanvas"></div>
    <div class="d3-hud d3-title">ATLAS 3D</div>
    <button id="btnClose3d" class="d3-back">&#x2715; Volver al mapa 2D</button>
    <div class="d3-hud d3-panel">
        <label class="d3-check"><input type="checkbox" id="d3lines" checked> L&iacute;neas de transmisi&oacute;n</label>
        <h4 style="margin-top:14px">Altura de columnas</h4>
        <input type="range" id="d3elev" min="50" max="800" value="300" step="10">
        <div class="d3-legend"><div class="d3-bar"></div><div class="d3-ends"><span>menos</span><span>m&aacute;s</span></div></div>

        <h4 style="margin-top:16px">Filtros</h4>
        <div class="d3-fdate">
            <input type="date" id="d3DateFrom" value="{date_min}">
            <span>&mdash;</span>
            <input type="date" id="d3DateTo" value="{date_max}">
        </div>
        <button class="d3-fbtn" id="d3DateApply">Aplicar fechas</button>
        <div class="d3-fgroup">
            <div class="d3-fhead"><span>Tipo de evento</span><span><a onclick="d3setAll('.tipo3-cb',true)">Todos</a><a onclick="d3setAll('.tipo3-cb',false)">Ninguno</a></span></div>
{tipo_checkboxes_3d}
        </div>
        <button class="d3-fbtn reset" id="d3Reset">&#x21BA; Reset filtros</button>
    </div>
    <div class="d3-hud" style="bottom:8px;left:10px;font-size:11px;color:#fff;pointer-events:none;">Autor CNEE: Cient&iacute;fico de datos, Ing. Estuardo Garc&iacute;a<br><span style="color:#E2B45F;">&#x1F4C5; &Uacute;ltimo posdespacho: {fecha_display}</span></div>
    <button id="btn3d" class="btn-3d" title="Ver en 2D">&#x1F5FA;&#xFE0F; Ver en 2D</button>
    <div id="d3popup" style="display:none;position:absolute;top:60px;right:10px;width:310px;max-height:calc(100vh - 80px);overflow-y:auto;background:rgba(11,21,46,0.97);border:1px solid rgba(200,160,60,0.25);border-top:3px solid #E2B45F;border-radius:10px;padding:14px;font-family:inherit;color:#ccd6f6;z-index:20;box-shadow:0 10px 40px rgba(0,0,0,0.6);">
        <div id="d3popupContent"></div>
        <div style="text-align:right;margin-top:10px;"><span onclick="document.getElementById('d3popup').style.display='none'" style="cursor:pointer;color:#8c9bb8;font-size:11px;">&#x2715; Cerrar</span></div>
    </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script src="https://unpkg.com/deck.gl@9.0.0/dist.min.js"></script>
<script>
var SUBS = {subs_js};
var LINES = {lines_js};
var ALL_EVENTS = {events_js};
var ALL_SUBEVENTS = {subevents_js};
var TOPO_SUBS = {topo_subs_js};
var TOPO_LINES = {topo_lines_js};

function vColor(v) {{
    if (v >= 400) return '#d32f2f';
    if (v >= 230) return '#ff9800';
    if (v >= 138) return '#1976d2';
    return '#388e3c';
}}
function vWeight(v) {{
    if (v >= 400) return 4;
    if (v >= 230) return 3;
    if (v >= 138) return 2.5;
    return 1.5;
}}
function evColor(type) {{
    if (type === 'disparo') return '#ff5252';
    if (type === 'mantenimiento') return '#ffa726';
    if (type === 'desenergizacion') return '#9c27b0';
    if (type === 'maniobra') return '#42a5f5';
    if (type === 'generacion') return '#ab47bc';
    return '#888';
}}
function tipoIcon(tipo) {{
    var icons = {{
        'disparo': '&#x26A0;', 'desenergizacion': '&#x1F50C;',
        'mantenimiento': '&#x1F527;', 'maniobra': '&#x2699;',
        'generacion_forzada': '&#x26A1;', 'regulacion_voltaje': '&#x1F4CA;',
        'redespacho': '&#x1F504;', 'energizacion': '&#x1F50B;',
    }};
    return icons[tipo] || '&#x25CF;';
}}

var darkMatter = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}@2x.png', {{
    attribution: '&copy; CartoDB', maxZoom: 18
}});
var osmLight = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap', maxZoom: 18
}});

// Satelital (Esri World Imagery) y variante con etiquetas
var esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    attribution: '&copy; Esri, Maxar, Earthstar Geographics', maxZoom: 19
}});
var esriLabels = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
    maxZoom: 19, opacity: 0.9
}});
var satelital = L.layerGroup([esriSat, esriLabels]);

var map = L.map('map', {{ center: [14.6, -90.5], zoom: 8, layers: [darkMatter] }});
map.attributionControl.setPrefix('Autor CNEE: Cient&iacute;fico de datos, Ing. Estuardo Garc&iacute;a');

var linesLayer = L.layerGroup();
LINES.forEach(function(ln) {{
    if (ln.coords.length < 2) return;
    var poly = L.polyline(ln.coords, {{ color: vColor(ln.v), weight: vWeight(ln.v), opacity: 0.65 }});
    poly.bindPopup('<h3>' + ln.name + '</h3><div>Voltaje: <b>' + ln.v + ' kV</b></div>');
    linesLayer.addLayer(poly);
}});

var subsCluster = L.markerClusterGroup({{
    maxClusterRadius: 30, disableClusteringAtZoom: 11,
    iconCreateFunction: function(cluster) {{
        var count = cluster.getChildCount();
        var size = count < 10 ? 28 : count < 50 ? 34 : 40;
        return L.divIcon({{
            html: '<div style="background:rgba(56,142,60,0.85);color:#fff;border-radius:50%;width:'+size+'px;height:'+size+'px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;border:2px solid rgba(255,255,255,0.3);">'+count+'</div>',
            className: '', iconSize: [size, size],
        }});
    }}
}});
var genCluster = L.markerClusterGroup({{
    maxClusterRadius: 30, disableClusteringAtZoom: 11,
    iconCreateFunction: function(cluster) {{
        var count = cluster.getChildCount();
        var size = count < 10 ? 28 : count < 50 ? 34 : 40;
        return L.divIcon({{
            html: '<div style="background:rgba(230,81,0,0.9);color:#fff;border-radius:50%;width:'+size+'px;height:'+size+'px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;border:2px solid rgba(255,255,255,0.3);">'+count+'</div>',
            className: '', iconSize: [size, size],
        }});
    }}
}});
SUBS.forEach(function(s) {{
    if (s.g) {{
        var marker = L.circleMarker([s.lat, s.lon], {{
            radius: 5, fillColor: '#e65100', color: '#fff', weight: 1, fillOpacity: 0.9,
        }});
        marker.bindPopup('<h3>' + s.name + '</h3><div>Tipo: <b>Generadora</b></div><div>Voltaje: <b>' + s.v + ' kV</b></div>');
        genCluster.addLayer(marker);
    }} else {{
        var marker = L.circleMarker([s.lat, s.lon], {{
            radius: 4, fillColor: vColor(s.v), color: '#fff', weight: 0.5, fillOpacity: 0.85,
        }});
        marker.bindPopup('<h3>' + s.name + '</h3><div>Voltaje: <b>' + s.v + ' kV</b></div>');
        subsCluster.addLayer(marker);
    }}
}});

var eventsLayer = L.layerGroup();
var tripsLayer = L.layerGroup();

linesLayer.addTo(map);
eventsLayer.addTo(map);

// ─── Capa Vulnerabilidad Topologica (toggleable, apagada por defecto) ───
function critColor(c) {{
    if (c === 'critica') return '#d50000';
    if (c === 'alta') return '#ff6d00';
    if (c === 'media') return '#ffd600';
    return '#00c853';
}}
function topoLineColor(t) {{
    if (t.es_puente || t.criticidad_topologica === 'critica') return '#d50000';
    if (t.nivel_redundancia === 'baja') return '#ff6d00';
    if (t.nivel_redundancia === 'media') return '#ffd600';
    return '#00c853';
}}
var topoLayer = L.layerGroup();
TOPO_LINES.forEach(function(t) {{
    var poly = L.polyline([t.o, t.d], {{ color: topoLineColor(t), weight: t.es_puente ? 4 : 2.5, opacity: 0.85, dashArray: t.es_puente ? null : '4,3' }});
    var resumen;
    if (t.es_puente) resumen = '&#9888; <b>Enlace critico sin respaldo.</b> Es la unica conexion por aqui: si esta linea falla, una zona se queda sin servicio.';
    else if (t.nivel_redundancia === 'media') resumen = '<b>Respaldo limitado.</b> Si falla, hay otra ruta pero pocas.';
    else resumen = '&#9989; <b>Bien respaldada.</b> Si falla, la electricidad puede tomar otra ruta.';
    var h = '<h3>' + t.linea + '</h3>';
    h += '<div style="margin:6px 0;padding:7px;background:rgba(255,255,255,0.07);border-radius:5px;line-height:1.4;">' + resumen + '</div>';
    h += '<div>&iquest;Unica conexion sin respaldo?: <b>' + (t.es_puente ? 'Si' : 'No') + '</b></div>';
    h += '<div>&iquest;Hay otra ruta si falla?: <b>' + (t.tiene_ruta_alterna ? 'Si' : 'No') + '</b></div>';
    h += '<div>Lineas en paralelo (circuitos): <b>' + t.circuitos + '</b></div>';
    h += '<div>Nivel de respaldo: <b>' + t.nivel_redundancia + '</b></div>';
    h += '<div style="color:#9aa;font-size:10px;margin-top:5px;border-top:1px solid rgba(255,255,255,0.1);padding-top:4px;">Indice de criticidad: ' + t.criticidad_topologica + ' (' + t.criticidad_topologica_score + '/100)</div>';
    poly.bindPopup(h);
    topoLayer.addLayer(poly);
}});
TOPO_SUBS.forEach(function(s) {{
    var r = 4 + (s.criticidad_topologica_score / 100) * 10;
    var marker = L.circleMarker([s.latitud, s.longitud], {{
        radius: r, fillColor: critColor(s.criticidad_topologica),
        color: s.es_articulacion ? '#ff1744' : '#fff',
        weight: s.es_articulacion ? 3 : 1, fillOpacity: 0.85
    }});
    var resumen;
    if (s.es_articulacion) resumen = '&#9888; <b>Subestacion clave.</b> Si falla, parte la red en zonas separadas y deja sin conexion a otras subestaciones.';
    else if (s.grado_conexion === 1) resumen = '<b>Punto final de la red.</b> Depende de una sola linea: puede quedar aislada si esa linea falla (pero su caida no afecta a otras).';
    else if (s.nivel_redundancia === 'baja') resumen = '<b>Conexion fragil.</b> Tiene pocas rutas alternativas.';
    else resumen = '&#9989; <b>Bien conectada.</b> Tiene varias rutas alternativas.';
    var h = '<h3>' + s.subestacion + '</h3>';
    h += '<div style="margin:6px 0;padding:7px;background:rgba(255,255,255,0.07);border-radius:5px;line-height:1.4;">' + resumen + '</div>';
    h += '<div>Lineas que la conectan: <b>' + s.grado_conexion + '</b></div>';
    h += '<div>&iquest;Su caida divide la red?: <b>' + (s.es_articulacion ? 'Si' : 'No') + '</b></div>';
    h += '<div>Lineas sin respaldo conectadas: <b>' + s.lineas_puente_cercanas + '</b></div>';
    h += '<div>Nivel de respaldo: <b>' + s.nivel_redundancia + '</b></div>';
    h += '<div style="color:#9aa;font-size:10px;margin-top:5px;border-top:1px solid rgba(255,255,255,0.1);padding-top:4px;">Indice de criticidad: ' + s.criticidad_topologica + ' (' + s.criticidad_topologica_score + '/100)</div>';
    marker.bindPopup(h);
    topoLayer.addLayer(marker);
}});


L.control.layers(
    {{ "Oscuro": darkMatter, "Claro (OSM)": osmLight, "Satelital + etiquetas": satelital }},
    {{ "Lineas de Transmision": linesLayer, "Eventos": eventsLayer, "Subestaciones": subsCluster, "Generadoras": genCluster, "Solo Disparos": tripsLayer, "Vulnerabilidad Topologica": topoLayer }},
    {{ collapsed: false, position: 'topleft' }}
).addTo(map);

// Mostrar la leyenda topologica solo cuando la capa esta activa
map.on('overlayadd', function(e) {{
    if (e.name === 'Vulnerabilidad Topologica') document.getElementById('topoLegend').style.display = 'block';
}});
map.on('overlayremove', function(e) {{
    if (e.name === 'Vulnerabilidad Topologica') document.getElementById('topoLegend').style.display = 'none';
}});

function getFilterState() {{
    var dateFrom = document.getElementById('dateFrom').value;
    var dateTo = document.getElementById('dateTo').value;
    var tipos = []; document.querySelectorAll('.tipo-cb').forEach(function(cb) {{ if (cb.checked) tipos.push(cb.value); }});
    return {{ dateFrom: dateFrom, dateTo: dateTo, tipos: tipos }};
}}

function filterEvents() {{
    var f = getFilterState();
    return ALL_EVENTS.filter(function(ev) {{
        if (f.dateFrom && ev.fecha < f.dateFrom) return false;
        if (f.dateTo && ev.fecha > f.dateTo) return false;
        if (f.tipos.indexOf(ev.tipo_detalle) === -1) return false;
        return true;
    }});
}}

function aggregateByLocation(filtered) {{
    var locs = {{}};
    filtered.forEach(function(ev) {{
        var key = ev.sub;
        if (!locs[key]) {{
            locs[key] = {{
                name: ev.sub, lat: ev.lat, lon: ev.lon,
                disparo: 0, mantenimiento: 0, desenergizacion: 0, maniobra: 0, generacion: 0, otro: 0,
                total: 0, totalHrs: 0, dispHrs: 0, mantHrs: 0, desenHrs: 0,
                cargaAfectada: 0, events: []
            }};
        }}
        var loc = locs[key];
        loc[ev.tipo] = (loc[ev.tipo] || 0) + 1;
        loc.total += 1;
        var d = ev.duracion || 0;
        loc.totalHrs += d;
        if (ev.tipo === 'disparo') loc.dispHrs += d;
        if (ev.tipo === 'mantenimiento') loc.mantHrs += d;
        if (ev.tipo === 'desenergizacion') loc.desenHrs += d;
        if (ev.carga_afectada) loc.cargaAfectada++;
        loc.events.push(ev);
    }});
    var result = [];
    for (var k in locs) {{
        var loc = locs[k];
        loc.events.sort(function(a,b) {{ return b.fecha > a.fecha ? 1 : -1; }});
        var tc = {{ disparo: loc.disparo, mantenimiento: loc.mantenimiento, desenergizacion: loc.desenergizacion, maniobra: loc.maniobra, generacion: loc.generacion }};
        var pmax = 0, predominant = 'otro';
        for (var t in tc) {{ if (tc[t] > pmax) {{ pmax = tc[t]; predominant = t; }} }}
        loc.predominant = predominant;
        result.push(loc);
    }}
    return result;
}}

function rebuildEventLayers(filtered) {{
    eventsLayer.clearLayers();
    tripsLayer.clearLayers();
    var byLoc = aggregateByLocation(filtered);

    byLoc.forEach(function(ev) {{
        var r = Math.min(6 + Math.sqrt(ev.total) * 4, 30);
        var circle = L.circleMarker([ev.lat, ev.lon], {{
            radius: r, fillColor: evColor(ev.predominant),
            color: '#fff', weight: 1.5, fillOpacity: 0.75,
        }});

        var evHtml = '<h3>' + ev.name + '</h3>';
        evHtml += '<div style="margin:6px 0;"><b>Total sub-eventos: ' + ev.total + '</b> &mdash; <span style="color:#66bb6a;font-weight:700;">' + ev.totalHrs.toFixed(1) + ' horas acum.</span></div>';
        if (ev.cargaAfectada > 0) evHtml += '<div><span class="badge badge-carga">CARGA AFECTADA: ' + ev.cargaAfectada + 'x</span></div>';
        evHtml += '<div class="ev-type"><span class="ev-disp">&#x26A0; Disparos: ' + ev.disparo + ' (' + ev.dispHrs.toFixed(1) + 'h)</span></div>';
        evHtml += '<div class="ev-type"><span class="ev-mant">&#x1F527; Mantenimiento: ' + ev.mantenimiento + ' (' + ev.mantHrs.toFixed(1) + 'h)</span></div>';
        if (ev.desenergizacion > 0) evHtml += '<div class="ev-type"><span style="color:#ce93d8;">&#x1F50C; Desenergizaci&oacute;n: ' + ev.desenergizacion + ' (' + ev.desenHrs.toFixed(1) + 'h)</span></div>';
        evHtml += '<div class="ev-type"><span class="ev-man">&#x2699; Maniobras: ' + ev.maniobra + '</span></div>';
        if (ev.generacion > 0) evHtml += '<div class="ev-type"><span class="ev-gen">&#x26A1; Gen. forzada: ' + ev.generacion + '</span></div>';

        if (ev.events.length > 0) {{
            evHtml += '<div class="ev-list" style="max-height:280px;">';
            ev.events.forEach(function(e, idx) {{
                var cls = e.tipo === 'disparo' ? 'ev-disp' : (e.tipo === 'mantenimiento' ? 'ev-mant' : (e.tipo === 'desenergizacion' ? 'ev-desen' : (e.tipo === 'generacion' ? 'ev-gen' : 'ev-man')));
                var uid = ev.name.replace(/[^a-zA-Z0-9]/g,'') + '_' + idx;
                evHtml += '<div class="ev-item" style="cursor:pointer;" onclick="var el=document.getElementById(\\'' + uid + '\\');el.style.display=el.style.display===\\'none\\'?\\'block\\':\\'none\\';">';
                evHtml += '<span class="ev-date">' + e.fecha + '</span> ' + (e.hora||'') + ' ';
                evHtml += tipoIcon(e.tipo_detalle) + ' <span class="' + cls + '">' + (e.tipo_detalle||'').toUpperCase() + '</span>';
                if (e.duracion > 0) evHtml += ' <span style="color:#66bb6a;font-size:10px;">(' + e.duracion.toFixed(1) + 'h)</span>';
                if (e.carga_afectada) evHtml += ' <span class="badge badge-carga">CARGA</span>';
                if (e.mw_perdidos) evHtml += ' <span class="badge badge-mw">' + e.mw_perdidos + ' MW</span>';
                if (e.codigo) evHtml += ' <span class="badge badge-codigo">' + e.codigo + '</span>';
                evHtml += '<br><small style="color:#aaa;">' + (e.causa||'') + ' &mdash; ' + (e.activo||'') + '</small>';
                if (e.generadores) evHtml += '<br><small style="color:#ab47bc;">Gen: ' + e.generadores + '</small>';
                evHtml += '<div id="' + uid + '" style="display:none;margin-top:4px;padding:6px;background:rgba(255,255,255,0.06);border-radius:4px;font-size:11px;color:#ccc;line-height:1.4;max-height:150px;overflow-y:auto;">' + (e.narrativa||'') + '</div>';
                evHtml += '</div>';
            }});
            evHtml += '</div>';
        }}
        circle.bindPopup(evHtml, {{maxWidth: 400, maxHeight: 500}});
        eventsLayer.addLayer(circle);
    }});

    // Trips layer
    byLoc.forEach(function(ev) {{
        if (ev.disparo === 0) return;
        var r = Math.min(8 + Math.sqrt(ev.disparo) * 5, 35);
        tripsLayer.addLayer(L.circleMarker([ev.lat, ev.lon], {{
            radius: r + 6, fillColor: '#ff1744', color: '#ff1744', weight: 0, fillOpacity: 0.15,
        }}));
        var circle = L.circleMarker([ev.lat, ev.lon], {{
            radius: r, fillColor: '#ff1744', color: '#fff', weight: 2, fillOpacity: 0.85,
        }});
        var html = '<h3 style="color:#ff5252;">&#x26A1; ' + ev.name + '</h3>';
        html += '<div style="margin:4px 0;"><b>Disparos: ' + ev.disparo + '</b> &mdash; <span style="color:#66bb6a;">' + ev.dispHrs.toFixed(1) + ' horas</span></div>';
        var tripEvs = ev.events.filter(function(e) {{ return e.tipo === 'disparo'; }});
        if (tripEvs.length > 0) {{
            html += '<div class="ev-list" style="max-height:280px;">';
            tripEvs.forEach(function(e, idx) {{
                var uid = 'trip_' + ev.name.replace(/[^a-zA-Z0-9]/g,'') + '_' + idx;
                html += '<div class="ev-item" style="cursor:pointer;" onclick="var el=document.getElementById(\\'' + uid + '\\');el.style.display=el.style.display===\\'none\\'?\\'block\\':\\'none\\';">';
                html += '<span class="ev-date">' + e.fecha + '</span> ' + (e.hora||'');
                if (e.duracion > 0) html += ' <span style="color:#66bb6a;font-size:10px;">(' + e.duracion.toFixed(1) + 'h)</span>';
                if (e.carga_afectada) html += ' <span class="badge badge-carga">CARGA</span>';
                html += '<br><small style="color:#aaa;">' + (e.causa||'') + ' &mdash; ' + (e.activo||'') + '</small>';
                html += '<div id="' + uid + '" style="display:none;margin-top:4px;padding:6px;background:rgba(255,255,255,0.06);border-radius:4px;font-size:11px;color:#ccc;line-height:1.4;">' + (e.narrativa||'') + '</div>';
                html += '</div>';
            }});
            html += '</div>';
        }}
        circle.bindPopup(html, {{maxWidth: 400, maxHeight: 500}});
        tripsLayer.addLayer(circle);
    }});
}}

function applyFilters() {{
    var filtered = filterEvents();
    rebuildEventLayers(filtered);
    refreshActiveTab();
}}

// ─── Pestanas del panel: Procesados / Raw ───
var currentTab = 'procesados';
var TAB_LIMIT = 300;  // tope de filas para no congelar el panel

function switchTab(name) {{
    currentTab = name;
    ['procesados','raw'].forEach(function(t) {{
        document.getElementById('tab-' + t).style.display = (t === name) ? 'block' : 'none';
        document.getElementById('tabbtn-' + t).classList.toggle('active', t === name);
    }});
    refreshActiveTab();
}}

// Mismo predicado que el mapa (fecha + tipo), pero sobre TODOS los sub-eventos procesados
function filterSubevents() {{
    var f = getFilterState();
    return ALL_SUBEVENTS.filter(function(s) {{
        if (f.dateFrom && s.fecha < f.dateFrom) return false;
        if (f.dateTo && s.fecha > f.dateTo) return false;
        if (f.tipos.indexOf(s.tipo_detalle) === -1) return false;
        return true;
    }});
}}

function escHtml(t) {{
    return (t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}}

function renderProcesados() {{
    var subs = filterSubevents();
    var el = document.getElementById('tab-procesados');
    var h = '<div class="tab-count">' + subs.length + ' sub-eventos procesados</div>';
    if (subs.length === 0) {{ el.innerHTML = h + '<div class="ev-meta" style="padding:8px;">Sin eventos para este filtro.</div>'; return; }}
    subs.slice(0, TAB_LIMIT).forEach(function(s, i) {{
        var tag = s.tipo || 'otro';
        var uid = 'proc-narr-' + i;
        h += '<div class="ev-row ev-clickable" onclick="toggleNarr(\\'' + uid + '\\', this)">';
        h += '<span class="ev-date">' + s.fecha + (s.hora ? ' &middot; ' + s.hora : '') + '</span>';
        h += '<span class="ev-tag tag-' + tag + '">' + escHtml(s.tipo_detalle) + '</span>';
        h += '<span class="ev-expand">&#x25BC;</span>';
        h += '<div class="ev-activo">' + escHtml(s.activo || '(sin activo)') + '</div>';
        var meta = [];
        if (s.subs) meta.push(escHtml(s.subs));
        if (s.causa) meta.push('causa: ' + escHtml(s.causa));
        if (s.duracion) meta.push(s.duracion.toFixed(1) + ' h');
        if (meta.length) h += '<div class="ev-meta">' + meta.join(' &middot; ') + '</div>';
        h += '<div class="ev-narr" id="' + uid + '" style="display:none;"><b style="color:var(--gold-300);">Narrativa AMM original:</b><br>' + escHtml(s.narrativa || '(sin texto)') + '</div>';
        h += '</div>';
    }});
    if (subs.length > TAB_LIMIT) h += '<div class="ev-meta" style="padding:8px;text-align:center;">Mostrando ' + TAB_LIMIT + ' de ' + subs.length + '. Afina los filtros para ver mas.</div>';
    el.innerHTML = h;
}}

function renderRaw() {{
    var subs = filterSubevents();
    // Un parrafo crudo una sola vez: deduplicar por TEXTO de narrativa (varios
    // sub-eventos comparten el mismo parrafo, cada uno con id distinto).
    var seen = {{}}, narrs = [];
    subs.forEach(function(s) {{
        var key = s.narrativa || ('__nid' + s.nid);
        if (seen[key]) {{
            seen[key].tipos[s.tipo] = true;
            if (s.nid < seen[key].ord) seen[key].ord = s.nid;  // conservar el id mas temprano
            return;
        }}
        var rec = {{ ord: s.nid, fecha: s.fecha, narrativa: s.narrativa, tipos: {{}} }};
        rec.tipos[s.tipo] = true;
        seen[key] = rec; narrs.push(rec);
    }});
    // Orden original del posdespacho: por id mas temprano (cronologico y en el orden del documento)
    narrs.sort(function(a, b) {{ return a.ord - b.ord; }});
    var el = document.getElementById('tab-raw');
    var h = '<div class="tab-count">' + narrs.length + ' narrativas del AMM (sin procesar)</div>';
    if (narrs.length === 0) {{ el.innerHTML = h + '<div class="ev-meta" style="padding:8px;">Sin narrativas para este filtro.</div>'; return; }}
    narrs.slice(0, TAB_LIMIT).forEach(function(n) {{
        h += '<div class="ev-row">';
        h += '<span class="ev-date">' + n.fecha + '</span>';
        Object.keys(n.tipos).forEach(function(t) {{ h += '<span class="ev-tag tag-' + t + '">' + t + '</span>'; }});
        h += '<div class="ev-narr">' + escHtml(n.narrativa || '(sin texto)') + '</div>';
        h += '</div>';
    }});
    if (narrs.length > TAB_LIMIT) h += '<div class="ev-meta" style="padding:8px;text-align:center;">Mostrando ' + TAB_LIMIT + ' de ' + narrs.length + '.</div>';
    el.innerHTML = h;
}}

function refreshActiveTab() {{
    if (currentTab === 'procesados') renderProcesados();
    else if (currentTab === 'raw') renderRaw();
}}


// Despliega/oculta la narrativa AMM original de un evento procesado al hacer clic
function toggleNarr(id, row) {{
    var d = document.getElementById(id);
    if (!d) return;
    var open = d.style.display === 'none';
    d.style.display = open ? 'block' : 'none';
    if (row) {{
        var ar = row.querySelector('.ev-expand');
        if (ar) ar.innerHTML = open ? '&#x25B2;' : '&#x25BC;';
    }}
}}

function resetFilters() {{
    document.getElementById('dateFrom').value = '{date_min}';
    document.getElementById('dateTo').value = '{date_max}';
    document.querySelectorAll('.tipo-cb').forEach(function(cb) {{ cb.checked = true; }});
    applyFilters();
}}

function setAll(sel, val) {{
    document.querySelectorAll(sel).forEach(function(cb) {{ cb.checked = val; }});
    applyFilters();
}}

function toggleFilterPanel() {{
    var panel = document.getElementById('filterPanel');
    var icon = document.getElementById('filterToggleIcon');
    panel.classList.toggle('collapsed');
    icon.innerHTML = panel.classList.contains('collapsed') ? '&#x25BC;' : '&#x25B2;';
}}

// Minimizar/expandir cualquier panel (Resumen, Leyenda) con su icono triangular
function togglePanel(panelId, iconId) {{
    var panel = document.getElementById(panelId);
    var icon = document.getElementById(iconId);
    panel.classList.toggle('collapsed');
    if (icon) icon.innerHTML = panel.classList.contains('collapsed') ? '&#x25BC;' : '&#x25B2;';
}}

document.querySelectorAll('.tipo-cb').forEach(function(cb) {{
    cb.addEventListener('change', applyFilters);
}});

applyFilters();

/* ═══════════════ Vista 3D (deck.gl) — activable desde el mapa 2D ═══════════════ */
var deck3d = null;
var d3state = {{ rep:'col', metric:'count', color:'intensity', base:'sat', lines:true, elev:300, dim:'3d' }};

var D3_SUBS = [], D3_PTS = [], D3_MAXC = 1, D3_MAXH = 1;

function d3getFilter() {{
    var df = document.getElementById('d3DateFrom').value;
    var dt = document.getElementById('d3DateTo').value;
    var tipos = []; document.querySelectorAll('.tipo3-cb').forEach(function(cb){{ if (cb.checked) tipos.push(cb.value); }});
    return {{ df: df, dt: dt, tipos: tipos }};
}}
function d3applyFilter() {{
    var f = d3getFilter();
    var evs = ALL_EVENTS.filter(function(e) {{
        if (e.lat == null || e.lon == null) return false;
        if (f.df && e.fecha < f.df) return false;
        if (f.dt && e.fecha > f.dt) return false;
        if (f.tipos.indexOf(e.tipo_detalle) === -1) return false;
        return true;
    }});
    var m = {{}};
    evs.forEach(function(e) {{
        var k = e.sub;
        if (!m[k]) m[k] = {{ sub: k, lat: e.lat, lon: e.lon, count: 0, hours: 0, tipos: {{}} }};
        m[k].count += 1; m[k].hours += (e.duracion || 0);
        m[k].tipos[e.tipo] = (m[k].tipos[e.tipo] || 0) + 1;
    }});
    D3_SUBS = Object.keys(m).map(function(k) {{
        var d = m[k], best = 'otro', bn = -1;
        for (var t in d.tipos) {{ if (d.tipos[t] > bn) {{ bn = d.tipos[t]; best = t; }} }}
        d.pred = best; d.hours = Math.round(d.hours * 10) / 10; return d;
    }});
    D3_MAXC = D3_SUBS.reduce(function(a,d){{ return Math.max(a, d.count); }}, 1);
    D3_MAXH = D3_SUBS.reduce(function(a,d){{ return Math.max(a, d.hours); }}, 1);
    D3_PTS = evs.map(function(e){{ return [e.lon, e.lat]; }});
    d3refresh();
}}
function d3activeData() {{ return D3_SUBS; }}
function d3setAll(sel, val) {{ document.querySelectorAll(sel).forEach(function(cb){{ cb.checked = val; }}); d3applyFilter(); }}
var D3_LINES = LINES.map(function(ln){{ return {{ v: ln.v, path: ln.coords.map(function(c){{ return [c[1], c[0]]; }}) }}; }});
var DEPTOS_GEO = {deptos_geo_js};

var D3_BASEMAPS = {{
    dark: 'https://a.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}.png',
    sat:  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}'
}};

function d3typeColor(t) {{
    if (t === 'disparo') return [224,88,79];
    if (t === 'mantenimiento') return [206,147,50];
    if (t === 'maniobra') return [107,151,196];
    if (t === 'generacion') return [155,134,194];
    return [140,155,184];
}}
function d3intensity(frac) {{
    var a = [206,147,50], b = [224,88,79], t = Math.min(1, frac || 0);
    return [Math.round(a[0]+(b[0]-a[0])*t), Math.round(a[1]+(b[1]-a[1])*t), Math.round(a[2]+(b[2]-a[2])*t), 225];
}}
function d3metricVal(d) {{ return d3state.metric === 'hours' ? d.hours : d.count; }}
function d3metricMax() {{
    return d3state.metric === 'hours' ? D3_MAXH : D3_MAXC;
}}

function d3basemap() {{
    return new deck.TileLayer({{
        id: 'd3base-' + d3state.base, data: D3_BASEMAPS[d3state.base],
        minZoom: 0, maxZoom: 19, tileSize: 256,
        renderSubLayers: function(props) {{
            var b = props.tile.bbox;
            return new deck.BitmapLayer(props, {{ data: null, image: props.data, bounds: [b.west, b.south, b.east, b.north] }});
        }}
    }});
}}
function d3columns() {{
    return new deck.ColumnLayer({{
        id: 'd3cols', data: d3activeData(), diskResolution: 12, radius: 1300,
        extruded: d3state.dim === '3d', pickable: true,
        elevationScale: d3state.dim === '3d' ? d3state.elev * 200 : 0,
        getPosition: function(d){{ return [d.lon, d.lat]; }},
        getElevation: function(d){{ return d3metricVal(d) / d3metricMax(); }},
        getFillColor: function(d){{ return d3state.color === 'type' ? d3typeColor(d.pred).concat(225) : d3intensity(d3metricVal(d) / d3metricMax()); }},
        material: {{ ambient: 0.55, diffuse: 0.6, shininess: 32, specularColor: [255,255,255] }},
        updateTriggers: {{
            getElevation: [d3state.metric, d3state.fuente, d3state.medCorr],
            getFillColor: [d3state.color, d3state.metric, d3state.fuente, d3state.medCorr],
            elevationScale: [d3state.dim, d3state.elev]
        }}
    }});
}}
function d3linesLayer() {{
    return new deck.PathLayer({{
        id: 'd3lines', data: D3_LINES, getPath: function(d){{ return d.path; }},
        getColor: function(d){{ return d.v >= 400 ? [211,47,47] : d.v >= 230 ? [255,152,0] : d.v >= 138 ? [25,118,210] : [56,142,60]; }},
        getWidth: function(d){{ return d.v >= 230 ? 3 : 2; }},
        widthUnits: 'pixels', widthMinPixels: 1, opacity: 0.55, pickable: false
    }});
}}
function d3borders() {{
    return new deck.GeoJsonLayer({{
        id: 'd3borders', data: DEPTOS_GEO,
        stroked: true, filled: false, pickable: false,
        getLineColor: [255, 255, 255, 165], getLineWidth: 1.5,
        lineWidthUnits: 'pixels', lineWidthMinPixels: 1
    }});
}}
function d3layers() {{
    var ls = [d3basemap()];
    if (d3state.base === 'sat' && DEPTOS_GEO) ls.push(d3borders());
    if (d3state.lines) ls.push(d3linesLayer());
    ls.push(d3columns());
    return ls;
}}

var D3_POPUP_EVS = [];
function d3toggleNarr3d(idx) {{
    var el = document.getElementById('d3pn_' + idx);
    if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
}}
function d3renderPopup(obj) {{
    var f = d3getFilter();
    D3_POPUP_EVS = ALL_EVENTS.filter(function(e) {{
        return e.sub === obj.sub &&
            (!f.df || e.fecha >= f.df) &&
            (!f.dt || e.fecha <= f.dt) &&
            f.tipos.indexOf(e.tipo_detalle) !== -1;
    }});
    D3_POPUP_EVS.sort(function(a,b) {{ return b.fecha > a.fecha ? 1 : -1; }});
    var h = '<div style="color:#E2B45F;font-weight:700;font-size:14px;margin-bottom:6px;">' + escHtml(obj.sub) + '</div>';
    h += '<div style="margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.1);font-size:12px;">';
    h += '<b>' + D3_POPUP_EVS.length + ' sub-eventos</b> &bull; <span style="color:#66bb6a;">' + obj.hours.toFixed(1) + ' h acum.</span></div>';
    D3_POPUP_EVS.forEach(function(e, idx) {{
        var cls = e.tipo === 'disparo' ? '#ff5252' : e.tipo === 'mantenimiento' ? '#E2B45F' : e.tipo === 'generacion' ? '#ab47bc' : '#6B97C4';
        h += '<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.06);cursor:pointer;" onclick="d3toggleNarr3d(' + idx + ')">';
        h += '<span style="color:#8c9bb8;font-size:10px;">' + e.fecha + (e.hora ? ' &middot; ' + e.hora : '') + '</span> ';
        h += '<span style="color:' + cls + ';font-weight:600;font-size:11px;">' + escHtml((e.tipo_detalle||'').toUpperCase()) + '</span>';
        if (e.duracion > 0) h += ' <span style="color:#66bb6a;font-size:10px;">(' + e.duracion.toFixed(1) + 'h)</span>';
        h += '<br><small style="color:#9aa;">' + escHtml(e.activo||'') + '</small>';
        h += '<div id="d3pn_' + idx + '" style="display:none;margin-top:5px;padding:7px;background:rgba(255,255,255,0.05);border-radius:5px;font-size:11px;color:#ccc;line-height:1.5;max-height:130px;overflow-y:auto;">' + escHtml(e.narrativa||'(sin narrativa)') + '</div>';
        h += '</div>';
    }});
    document.getElementById('d3popupContent').innerHTML = h;
    document.getElementById('d3popup').style.display = 'block';
}}

var D3_VIEW = {{ longitude: -90.45, latitude: 15.35, zoom: 7.0, pitch: 50, bearing: -17 }};
function d3init() {{
    deck3d = new deck.DeckGL({{
        container: document.getElementById('deck3dCanvas'),
        initialViewState: D3_VIEW, controller: true,
        parameters: {{ clearColor: [0.063, 0.102, 0.18, 1] }},
        layers: d3layers(),
        getTooltip: function(o) {{
            if (!o.object) return null;
            var obj = o.object;
            return {{ html: '<b style="color:#E2B45F">' + obj.sub + '</b><br>' + obj.count + ' eventos &bull; ' + obj.hours.toFixed(1) + ' h<br><span style="color:#8c9bb8">predom.: ' + obj.pred + '</span>' }};
        }},
        onClick: function(o) {{
            if (!o.object) {{ document.getElementById('d3popup').style.display = 'none'; return; }}
            d3renderPopup(o.object);
        }}
    }});
}}
function d3refresh() {{ if (deck3d) deck3d.setProps({{ layers: d3layers() }}); }}
function d3setView() {{
    if (deck3d) deck3d.setProps({{ initialViewState: Object.assign({{}}, D3_VIEW, {{ pitch: d3state.dim === '3d' ? 50 : 0, bearing: d3state.dim === '3d' ? -17 : 0 }}) }});
}}

function open3D() {{
    document.getElementById('deck3d').style.display = 'block';
    document.getElementById('btn2d').style.display = 'none';
    if (!deck3d) {{ d3applyFilter(); d3init(); }}
}}
function close3D() {{
    document.getElementById('deck3d').style.display = 'none';
    document.getElementById('btn2d').style.display = 'block';
}}

function d3seg(id, key, cb) {{
    document.getElementById(id).addEventListener('click', function(e) {{
        var b = e.target.closest('button'); if (!b) return;
        d3state[key] = b.dataset.val;
        this.querySelectorAll('button').forEach(function(x){{ x.classList.toggle('active', x === b); }});
        if (cb) cb();
    }});
}}
document.getElementById('d3lines').addEventListener('change', function(){{ d3state.lines = this.checked; d3refresh(); }});
document.getElementById('d3elev').addEventListener('input', function(){{ d3state.elev = +this.value; d3refresh(); }});
document.getElementById('btn3d').addEventListener('click', close3D);
document.getElementById('btn2d').addEventListener('click', open3D);
document.getElementById('btnClose3d').addEventListener('click', close3D);
open3D();

// Filtros del 3D (Causa, Tipo, Fecha) — mismo predicado que el mapa 2D
document.querySelectorAll('.tipo3-cb').forEach(function(cb){{ cb.addEventListener('change', d3applyFilter); }});
document.getElementById('d3DateApply').addEventListener('click', d3applyFilter);
document.getElementById('d3DateFrom').addEventListener('change', d3applyFilter);
document.getElementById('d3DateTo').addEventListener('change', d3applyFilter);
document.getElementById('d3Reset').addEventListener('click', function() {{
    document.getElementById('d3DateFrom').value = '{date_min}';
    document.getElementById('d3DateTo').value = '{date_max}';
    document.querySelectorAll('.tipo3-cb').forEach(function(cb){{ cb.checked = true; }});
    d3applyFilter();
}});
</script>
</body>
</html>"""

    OUTPUT_HTML.write_text(html, encoding='utf-8')
    size_kb = OUTPUT_HTML.stat().st_size / 1024
    print(f"\n[OK] Mapa generado: {OUTPUT_HTML}")
    print(f"  Tamano: {size_kb:.0f} KB ({size_kb/1024:.1f} MB)")


if __name__ == '__main__':
    main()
