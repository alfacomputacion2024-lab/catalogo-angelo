# -*- coding: utf-8 -*-
"""Respaldo automático de producción a GitHub (rama `respaldos`).

PRUEBA DE PERSISTENCIA (27/09/2026): Render (plan gratis) duerme el sitio a
los ~15 minutos sin visitas y al reactivarlo RESTAURA el filesystem desde el
último deploy: todo lo cargado en el panel (precios, ediciones, bajas, fotos)
se pierde. Este módulo lo hace durable sin depender de nadie:

  * `respaldar()`  -> después de cada carga en el panel, sube catalogo.db (y
    las fotos nuevas, registradas en `data/respaldo_fotos.json`) a la rama
    `respaldos`, en segundo plano; jamás rompe la operación del usuario.
  * `restaurar()`  -> al arrancar el servidor (antes de aceptar pedidos), si
    la rama `respaldos` tiene un respaldo MÁS NUEVO que la base local, la
    restaura; después, en segundo plano, baja las fotos subidas en producción
    que falten. Así lo cargado sobrevive tanto a dormidas como a despliegues.

Requiere la variable de entorno RESPALDO_GITHUB_TOKEN (token con permiso
`repo`). Sin ella el módulo queda inerte (uso local y tests).

La rama `respaldos` está separada de `main`: sus commits NUNCA disparan
despliegues ni ensucian la historia de la que se despliega.

NOTA de diseño: NO se sondean las fotos referenciadas en la base que no
existen (hay 516 huecos del scrape original); solo se restauran las fotos
registradas en el manifiesto, que son las que realmente se subieron.
"""
import base64
import datetime as _dt
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time

import requests

API = "https://api.github.com"
REPO = os.environ.get("RESPALDO_GITHUB_REPO", "alfacomputacion2024-lab/catalogo-angelo")
RAMA = "respaldos"
TOKEN = os.environ.get("RESPALDO_GITHUB_TOKEN", "")
MANIFIESTO = "data/respaldo_fotos.json"

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalogo.db")
IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "imagenes")


def _log(msg):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(f"[RESPALDO] {msg}", flush=True)


def _h():
    return {"Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "angelo-respaldo"}


def _reintentos(fn, veces=3, espera=1):
    """Reintenta ante caídas transitorias de red (nada crítico se pierde)."""
    ultimo = None
    for i in range(veces):
        try:
            return fn()
        except Exception as e:
            ultimo = e
            if i < veces - 1:
                time.sleep(espera * (i + 1))
    raise ultimo


def _fecha_local_db():
    return _dt.datetime.fromtimestamp(os.path.getmtime(DB), tz=_dt.timezone.utc)


def _contenido(ruta, rama=RAMA):
    """(contenido, sha) del archivo en GitHub. Para archivos >1 MB GitHub no
    devuelve el contenido (encoding "none"): queda (None, sha) — el sha igual
    sirve para el PUT. Usar _descargar() cuando haga falta el bytes completo."""
    r = _reintentos(lambda: requests.get(
        f"{API}/repos/{REPO}/contents/{ruta}",
        headers=_h(), params={"ref": rama}, timeout=(5, 30)))
    if r.status_code == 404:
        return None, None
    if r.status_code != 200:
        raise RuntimeError(f"GET contents {ruta}: {r.status_code} {r.text[:150]}")
    d = r.json()
    if d.get("encoding") == "base64" and d.get("content") is not None:
        return base64.b64decode(d["content"]), d.get("sha")
    return None, d.get("sha")            # >1 MB: solo metadata


def _descargar(ruta, rama=RAMA, veces=3):
    """Bytes completos del archivo (cualquier tamaño, vía media type raw)."""
    r = _reintentos(lambda: requests.get(
        f"{API}/repos/{REPO}/contents/{ruta}",
        headers={**_h(), "Accept": "application/vnd.github.raw+json"},
        params={"ref": rama}, timeout=(5, 30)), veces=veces)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError(f"GET raw {ruta}: {r.status_code} {r.text[:150]}")
    return r.content


def _git_sha(datos):
    """SHA1 del blob de git (permite comparar sin bajar el archivo)."""
    return hashlib.sha1(b"blob " + str(len(datos)).encode() + b"\0"
                        + datos).hexdigest()


def _ruta_valida(p):
    """Ruta de foto segura: relativa y sin saltos de directorio."""
    return (isinstance(p, str) and bool(p) and not p.startswith("http")
            and ".." not in p and not p.startswith("/") and ":" not in p
            and "\\" not in p)


def _subir(ruta, datos, mensaje, reintento=2):
    _, sha = _contenido(ruta)
    cuerpo = {"message": mensaje,
              "content": base64.b64encode(datos).decode(),
              "branch": RAMA}
    if sha:
        cuerpo["sha"] = sha
    for i in range(reintento + 1):
        r = _reintentos(lambda: requests.put(
            f"{API}/repos/{REPO}/contents/{ruta}",
            headers=_h(), json=cuerpo, timeout=(5, 60)), veces=2)
        if r.status_code in (200, 201):
            return True
        if r.status_code in (409, 422):   # sha vencido: releer y reintentar
            _, sha = _contenido(ruta)
            cuerpo["sha"] = sha
            continue
        raise RuntimeError(f"PUT {ruta}: {r.status_code} {r.text[:150]}")
    return False


def _snapshot_db():
    """Copia consistente de la base en memoria."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        src = sqlite3.connect(DB)
        dst = sqlite3.connect(tmp.name)
        src.backup(dst)
        dst.close()
        src.close()
        with open(tmp.name, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _asegurar_rama():
    """Crea la rama `respaldos` desde main si no existe todavía."""
    r = _reintentos(lambda: requests.get(
        f"{API}/repos/{REPO}/git/ref/heads/{RAMA}",
        headers=_h(), timeout=(5, 20)), veces=2)
    if r.status_code == 200:
        return
    if r.status_code != 404:
        raise RuntimeError(f"ref {RAMA}: {r.status_code} {r.text[:150]}")
    main = requests.get(f"{API}/repos/{REPO}/git/ref/heads/main",
                        headers=_h(), timeout=(5, 20))
    main.raise_for_status()
    c = requests.post(f"{API}/repos/{REPO}/git/refs", headers=_h(),
                      timeout=(5, 20),
                      json={"ref": f"refs/heads/{RAMA}",
                            "sha": main.json()["object"]["sha"]})
    if c.status_code not in (200, 201):
        raise RuntimeError(f"crear rama {RAMA}: {c.status_code} {c.text[:150]}")
    _log(f"rama '{RAMA}' creada desde main")


def _manifiesto():
    """Lista de fotos subidas en producción (registradas en la rama)."""
    try:
        datos = _descargar(MANIFIESTO, veces=2)
        if not datos:
            return []
        arr = json.loads(datos.decode("utf-8"))
        return [p for p in arr if _ruta_valida(p)]
    except Exception:
        return []


def respaldar(imagenes=()):
    """Sube la base (y fotos nuevas) a la rama `respaldos`; en segundo plano."""
    if not TOKEN:
        return

    def _trabajo():
        try:
            _asegurar_rama()
            datos = _snapshot_db()
            _subir("catalogo.db", datos,
                   "respaldo automatico "
                   + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            fotos = [p.replace("\\", "/") for p in imagenes if _ruta_valida(p)]
            if fotos:
                subidas = 0
                for p in fotos:
                    local = os.path.join(IMG, *p.split("/"))
                    if not os.path.exists(local):
                        continue
                    with open(local, "rb") as f:
                        datos_f = f.read()
                    _, sha_remoto = _contenido(f"data/imagenes/{p}")
                    if sha_remoto == _git_sha(datos_f):
                        continue     # idéntica: no genera commit de ruido
                    _subir(f"data/imagenes/{p}", datos_f,
                           f"foto {p} ({_dt.datetime.now().strftime('%H:%M:%S')})")
                    subidas += 1
                actual = _manifiesto()
                nuevos = sorted(set(actual) | set(fotos))
                if nuevos != actual:
                    _subir(MANIFIESTO,
                           json.dumps(nuevos, ensure_ascii=False,
                                      indent=1).encode(),
                           "manifiesto de fotos ("
                           + _dt.datetime.now().strftime("%H:%M:%S") + ")")
                _log(f"respaldo ok (base {len(datos)} bytes"
                     + (f", {subidas} foto(s)" if subidas else "") + ")")
            else:
                _log(f"respaldo ok (base {len(datos)} bytes)")
        except Exception as e:
            _log(f"error (no rompe nada): {type(e).__name__}: {e}")

    threading.Thread(target=_trabajo, daemon=True).start()


def _ultima_fecha_respaldo():
    r = _reintentos(lambda: requests.get(
        f"{API}/repos/{REPO}/commits", headers=_h(),
        params={"path": "catalogo.db", "sha": RAMA, "per_page": 1},
        timeout=(5, 20)), veces=2)
    if r.status_code != 200:
        return None
    arr = r.json()
    if not arr:
        return None
    iso = arr[0]["commit"]["committer"]["date"]     # 2026-09-27T22:10:00Z
    return _dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _bajar_fotos():
    """En segundo plano: fotos del manifiesto que falten en disco."""
    try:
        bajadas = 0
        for p in dict.fromkeys(_manifiesto()):
            local = os.path.join(IMG, *p.split("/"))
            if os.path.exists(local):
                continue
            try:
                datos = _descargar(f"data/imagenes/{p}", veces=2)
                if datos is None:
                    continue         # no existe ni en GitHub (se reintenta
                                     # cuando vuelva a subirse en el panel)
                os.makedirs(os.path.dirname(local), exist_ok=True)
                with open(local, "wb") as f:
                    f.write(datos)
                bajadas += 1
            except Exception as e:
                _log(f"foto {p} no se pudo bajar: {type(e).__name__}")
        if bajadas:
            _log(f"{bajadas} foto(s) restaurada(s)")
    except Exception as e:
        _log(f"fotos: {type(e).__name__}: {e}")


def restaurar():
    """Al arrancar (base síncrona, fotos en segundo plano): si el respaldo de
    GitHub es más nuevo que la base local, restaurar."""
    if not TOKEN:
        return
    try:
        fecha_resp = _ultima_fecha_respaldo()
        if fecha_resp is None:
            return                                  # nunca hubo respaldos
        if fecha_resp > _fecha_local_db():
            datos = _descargar("catalogo.db", veces=2)
            if datos:
                with open(DB, "wb") as f:
                    f.write(datos)
                _log(f"base restaurada desde GitHub ({len(datos)} bytes, "
                     f"respaldo {fecha_resp:%d/%m %H:%M})")
        threading.Thread(target=_bajar_fotos, daemon=True).start()
    except Exception as e:
        _log(f"restauración fallida (el sitio sigue funcionando): "
             f"{type(e).__name__}: {e}")
