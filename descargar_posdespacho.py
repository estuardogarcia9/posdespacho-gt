"""
Descargador de Posdespacho Diario - AMM Guatemala
==================================================
Descarga el ZIP del posdespacho diario desde el portal público del AMM.

URL base: https://www.amm.org.gt/pdfs2/post_despacho/POSDESPACHO_DIARIO/
Patrón:   {YYYY}/{MM}_{MES}/PD{YYYYMMDD}.zip

Uso:
    python descargar_posdespacho.py                 # descarga el de HOY
    python descargar_posdespacho.py 2026-04-07      # descarga fecha específica
    python descargar_posdespacho.py 2026-04-01 2026-04-08  # rango de fechas
"""

import sys
import os
import requests
from datetime import date, timedelta
from pathlib import Path

CARPETA_DESTINO = Path(os.environ.get("POSDESPACHO_ZIPS", Path.home() / "Downloads"))
BASE_URL = "https://www.amm.org.gt/pdfs2/post_despacho/POSDESPACHO_DIARIO"

MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL",
    5: "MAYO", 6: "JUNIO", 7: "JULIO", 8: "AGOSTO",
    9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def url_para_fecha(d: date) -> str:
    nombre = f"PD{d.strftime('%Y%m%d')}.zip"
    carpeta = f"{d.year}/{d.month:02d}_{MESES[d.month]}"
    return f"{BASE_URL}/{carpeta}/{nombre}"


def descargar(d: date, forzar: bool = False) -> Path | None:
    """
    Descarga el ZIP del posdespacho para la fecha dada.
    Retorna la ruta local del ZIP descargado, o None si falla.
    """
    nombre = f"PD{d.strftime('%Y%m%d')}.zip"
    ruta_local = CARPETA_DESTINO / nombre

    if ruta_local.exists() and not forzar:
        print(f"Ya existe: {ruta_local.name} ({ruta_local.stat().st_size:,} bytes)")
        return ruta_local

    url = url_para_fecha(d)
    print(f"Descargando: {url}")

    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        if r.status_code == 404:
            print(f"  No disponible aun (404): {d.strftime('%d/%m/%Y')}")
            return None
        r.raise_for_status()

        total = int(r.headers.get("Content-Length", 0))
        descargado = 0
        with open(ruta_local, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
                descargado += len(chunk)

        print(f"  OK: {nombre} ({descargado:,} bytes)")
        return ruta_local

    except requests.RequestException as e:
        print(f"  ERROR descargando {d.strftime('%d/%m/%Y')}: {e}")
        return None


def parse_fecha(s: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return date.fromisoformat(s) if fmt == "%Y-%m-%d" else \
                   __import__('datetime').datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Formato de fecha no reconocido: {s}")


def main():
    args = sys.argv[1:]

    if not args:
        fechas = [date.today()]
    elif len(args) == 1:
        fechas = [parse_fecha(args[0])]
    else:
        inicio = parse_fecha(args[0])
        fin = parse_fecha(args[1])
        fechas = [inicio + timedelta(days=i) for i in range((fin - inicio).days + 1)]

    descargados = []
    for d in fechas:
        ruta = descargar(d)
        if ruta:
            descargados.append(ruta)

    print(f"\nTotal descargados: {len(descargados)}/{len(fechas)}")
    return descargados


if __name__ == "__main__":
    main()
