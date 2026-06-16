#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Publica el mapa de MEDIDORES en Neocities (hosting estatico gratis).

A diferencia de Netlify, Neocities NO tiene "despliegues" con creditos: es subida
de archivos por API, sin tope practico para actualizar cada 15 min. Subdominio
discreto (<sitename>.neocities.org), sin repositorio publico.

Config en .env (gitignored):
    NEOCITIES_API_KEY    API key del sitio (neocities.org/settings -> API Key)
    NEOCITIES_SITENAME   (opcional) solo para imprimir la URL final

Uso:
    python publicar_mapa_neocities.py
    python publicar_mapa_neocities.py mapa.html nombre_destino.html
"""
import os
import sys
from pathlib import Path

import requests

BASE = Path(__file__).parent
ENV = BASE / ".env"
API_UPLOAD = "https://neocities.org/api/upload"
API_INFO = "https://neocities.org/api/info"


def _load_env():
    if ENV.exists():
        for ln in ENV.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    _load_env()
    key = os.environ.get("NEOCITIES_API_KEY", "")
    if not key:
        raise SystemExit("FALTA NEOCITIES_API_KEY en .env. Obtenla en neocities.org/settings -> API Key.")

    local = Path(sys.argv[1]) if len(sys.argv) > 1 else (BASE / "mapa_medidores.html")
    destino = sys.argv[2] if len(sys.argv) > 2 else "index.html"
    if not local.exists():
        raise SystemExit(f"No existe {local.name}. Genera el mapa primero (python generar_mapa_medidores.py).")

    h = {"Authorization": f"Bearer {key}"}
    print(f"Subiendo {local.name} -> {destino} en Neocities...")
    with open(local, "rb") as f:
        r = requests.post(API_UPLOAD, headers=h,
                          files={destino: (destino, f, "text/html")}, timeout=120)
    if r.status_code != 200:
        raise SystemExit(f"Fallo la subida ({r.status_code}): {r.text[:300]}")
    print("Subido OK:", r.json().get("message", r.text[:120]))

    # URL final del sitio
    site = os.environ.get("NEOCITIES_SITENAME")
    try:
        info = requests.get(API_INFO, headers=h, timeout=30).json()
        site = (info.get("info") or {}).get("sitename") or site
    except Exception:
        pass
    if site:
        pag = "" if destino == "index.html" else destino
        print(f"Publicado. Link del mapa: https://{site}.neocities.org/{pag}")


if __name__ == "__main__":
    main()
