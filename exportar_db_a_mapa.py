#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Adaptador: exporta los eventos procesados de la base de datos
`posdespacho_amm.db` (otro pipeline, modelo dimensional) al formato JSON que
consume `generar_mapa_gemini.py`, sin modificar el generador.

Fuente de verdad: la tabla `eventos_ia` (descomposicion IA de fallas/eventos
electricos), enriquecida con:
  - hora de inicio/fin: embebida en eventos_ia.fecha_ini / fecha_fin ("YYYY-MM-DD HH:MM")
  - activo: dim_activos (nombre normalizado) con fallback a activo_raw
  - subestaciones afectadas: evento_subestaciones (preciso) o derivadas del nombre del activo
  - narrativa: posdespachos_raw agregada por id_grupo

Produce (sobre la carpeta del repo):
  - subeventos_gemini.json   (lista de sub-eventos con el shape del mapa)
  - narrativas_para_ia.json  (id -> fecha, requerido por el fecha_map del mapa)

Uso:
    python exportar_db_a_mapa.py
    POSDESPACHO_DB=ruta\\posdespacho_amm.db python exportar_db_a_mapa.py
"""

import os
import re
import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DB = Path(os.environ.get("POSDESPACHO_DB", Path(__file__).parent / "posdespacho_amm.db"))
OUT_SUBEVENTOS = BASE / "subeventos_gemini.json"
OUT_NARRATIVAS = BASE / "narrativas_para_ia.json"

# ─── Mapeo de tipologia de la BD -> tipo del mapa + etiqueta de causa ─────────
# El generador espera 'tipo' en: disparo|desenergizacion|mantenimiento|maniobra|
# generacion_forzada|regulacion_voltaje|redespacho|energizacion|otro
TIPO_MAP = {
    "disparo_forzado":           ("disparo",         "Disparo"),
    "indisponibilidad_forzada":  ("disparo",         "Indisponibilidad forzada"),
    "desenergizacion_forzada":   ("desenergizacion", "Desenergizacion forzada"),
    "mantenimiento_programado":  ("mantenimiento",   "Mantenimiento"),
    "desenergizacion_programada":("desenergizacion", "Desenergizacion programada"),
    "desenergizacion":           ("desenergizacion", "Desenergizacion"),
    "apertura_manual":           ("maniobra",        "Maniobra"),
    "seguridad_operativa":       ("otro",            "Seguridad operativa"),
}

PREFIJOS = re.compile(r'^(LT|TX|INT|SE|BARRA|CIRCUITO|GEN|HE|HM|GDR|CENTRAL)\s+(.*)$', re.IGNORECASE)


def hora_de(ts):
    """'2023-01-02 10:28' -> '10:28'  |  None/sin hora -> None."""
    if not ts or len(ts) < 16:
        return None
    h = ts[11:16].strip()
    return h if re.match(r'^\d{1,2}:\d{2}$', h) else None


def derivar_subestaciones(activo_nombre):
    """Devuelve nombres candidatos de subestacion a partir del nombre del activo.
    Lineas/interconexiones -> ambos extremos; subestaciones -> el nombre."""
    if not activo_nombre:
        return []
    n = activo_nombre.strip()

    # Caso transformador (activo_raw sin normalizar): la subestacion va tras el kV.
    # Ej: "transformador No. 2 69/13.8 kV Sayaxche" -> ["Sayaxche"]
    if re.search(r'transformador', n, re.IGNORECASE):
        m2 = re.search(r'kV\s+(?:en\s+)?(?:la\s+)?(?:subestaci[oó]n\s+)?(.+)$', n, re.IGNORECASE)
        return [m2.group(1).strip()] if m2 and m2.group(1).strip() else []

    m = PREFIJOS.match(n)
    pref = m.group(1).upper() if m else ''
    body = m.group(2) if m else n
    # quitar voltaje, incluyendo "69/13.8 kV" y "69/"
    body = re.sub(r'\d+(?:/\d+(?:\.\d+)?)?\s*kV', '', body, flags=re.IGNORECASE)
    body = re.sub(r'\([^)]*\)', '', body)                              # quitar (pais)
    if pref in ('LT', 'INT'):
        partes = re.split(r'\s*[\-–—]\s*', body)
        return [p.strip() for p in partes if p.strip()]
    body = body.strip(' /')
    return [body] if body else []


def main():
    if not DB.exists():
        raise SystemExit(f"No se encontro la BD: {DB}\nDefine POSDESPACHO_DB si esta en otra ruta.")

    con = sqlite3.connect(DB)
    cur = con.cursor()

    # dim_activos: id -> (nombre, tipo, kv)
    activos = {r[0]: (r[1], r[2], r[3])
               for r in cur.execute("SELECT id_activo, nombre, tipo, kv FROM dim_activos")}

    # evento_subestaciones: id_evento -> [nombres crudos]
    esub = {}
    for id_ev, nombre_raw in cur.execute("SELECT id_evento, nombre_sub_raw FROM evento_subestaciones"):
        if nombre_raw:
            esub.setdefault(id_ev, []).append(nombre_raw.strip())

    # posdespachos_raw agregada por id_grupo: narrativa unificada
    narr_por_grupo = {}
    for id_grupo, narr in cur.execute("SELECT id_grupo, narrativa_amm FROM posdespachos_raw"):
        if narr:
            narr_por_grupo.setdefault(id_grupo, []).append(narr.strip())

    eventos, narrativas = [], []
    geoloc_candidato = 0

    rows = cur.execute("""
        SELECT id_evento, id_grupo, id_activo, activo_raw, fecha_ini, fecha_fin,
               tipo, kv, carga_afectada_mw, codigo_mantenimiento, departamento
        FROM eventos_ia
    """).fetchall()

    for (id_ev, id_grupo, id_activo, activo_raw, fecha_ini, fecha_fin,
         db_tipo, kv, carga_mw, codigo, depto) in rows:

        tipo_mapa, causa = TIPO_MAP.get(db_tipo, ("otro", (db_tipo or "Otro").replace("_", " ").capitalize()))

        nombre_activo = activos.get(id_activo, (None,))[0] or (activo_raw or "")

        subs = esub.get(id_ev) or derivar_subestaciones(nombre_activo)
        if subs:
            geoloc_candidato += 1

        fecha = (fecha_ini or "")[:10]
        narr_grupo = " / ".join(dict.fromkeys(narr_por_grupo.get(id_grupo, [])))

        eventos.append({
            "id": id_ev,
            "tipo": tipo_mapa,
            "causa": causa,
            "activo_nombre": nombre_activo,
            "voltaje_kv": kv,
            "subestaciones_afectadas": subs,
            "hora_inicio": hora_de(fecha_ini),
            "hora_fin": hora_de(fecha_fin),
            "codigo_mantenimiento": codigo or "",
            "carga_afectada": bool(carga_mw and carga_mw > 0),
            "mw_perdidos": carga_mw if carga_mw else None,
            "generadores_afectados": [],
            "narrativa_original": narr_grupo,
        })
        narrativas.append({"id": id_ev, "fecha": fecha, "narrativa": narr_grupo})

    con.close()

    OUT_SUBEVENTOS.write_text(json.dumps(eventos, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_NARRATIVAS.write_text(json.dumps(narrativas, ensure_ascii=False, indent=2), encoding="utf-8")

    fechas = sorted(f["fecha"] for f in narrativas if f["fecha"])
    print(f"Eventos exportados: {len(eventos)}")
    print(f"  con subestaciones candidatas (geolocalizables): {geoloc_candidato}")
    print(f"  con hora de inicio: {sum(1 for e in eventos if e['hora_inicio'])}")
    print(f"  rango de fechas: {fechas[0]} -> {fechas[-1]}")
    print(f"Escrito: {OUT_SUBEVENTOS.name}, {OUT_NARRATIVAS.name}")


if __name__ == "__main__":
    main()
