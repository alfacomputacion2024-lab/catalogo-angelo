# 🕒 Catálogo Angelo — catálogo online + panel + PDFs

Sistema completo para la joyería **Angelo** (Encarnación, Paraguay):

- **Panel de administración** con login (roles: *admin* y *socio-revendedor*)
- **Catálogo online** por marca con búsqueda, edición y borrado (login)
- **Catálogo para clientes/revendedores** en `/client` — solo lectura, sin precios, sin admin
- **PDFs por marca** con logo centrado, marca de agua "A", hasta 300 productos y sin páginas separadoras
- **Fotos propias** alojadas en el repositorio (`data/imagenes/`) — sin servicios externos de imágenes

🌐 Producción actual: **https://catalogo-angelo.onrender.com** (Render.com)
📂 Repositorio: `github.com/alfacomputacion2024-lab/catalogo-angelo` (rama `main`)

---

## 1. Mapa de archivos — qué es cada cosa

### Aplicación web (se ejecuta en el servidor)

| Archivo | Para qué sirve |
|---|---|
| `app.py` | **Servidor principal (Flask)**. Todas las rutas: panel, catálogos, login, PDF, APIs, fotos. |
| `marcas.py` | **Marca real por producto** (nunca la tienda de origen): `watch_brand()` + listas de marcas/tiendas. Lo comparten `app.py` y `db.py`. |
| `db.py` | Acceso a la base SQLite (`catalogo.db`): crear, consultar, editar productos. |
| `config.py` | Configuración general: rutas, marcas de scraping, límites, usuario-agente. |
| `images.py` | Descarga, recorte y optimización de fotos (JPEG, máx. 1200 px). |
| `pdf_catalog.py` | Generador de PDFs (reportlab): portada, grilla, marca de agua, precios. |
| `theme.json` | Diseño de los PDFs: colores, columnas, textos de contacto, logotipos. |
| `catalogo.db` | **La base de datos** (productos, precios, estados). Es un archivo. |
| `data/imagenes/` | **Todas las fotos** del catálogo, organizadas por origen (`casio/`, `ig_espinola/`…). |
| `logo.PNG` / `logo_A.png` | Logo de la marca (encabezado y favicon). |

### Plantillas HTML (el "cara" de cada página)

Las plantillas viven en la **raíz** en producción (y en `templates/` en desarrollo local — `app.py` detecta cuál).

| Archivo | Para qué sirve |
|---|---|
| `index.html` | **Panel admin** (`/`): contadores, tarjetas, precios, CSV, PDF. |
| `catalogo.html` | **Catálogo online** (`/catalogo`): oscuro, con marcas, búsqueda y edición. |
| `client_catalog.html` | **Catálogo de clientes** (`/client`): público, sin precios ni admin. |
| `login.html` | Pantalla de acceso. |
| `agregar.html` | Formulario de alta manual con subida de fotos. |

### Herramientas (`tools/` — se corren desde la PC, no en el servidor)

| Archivo | Para qué sirve |
|---|---|
| `tools/run_scrape.py` | **Extractor de productos** marca por marca desde los sitios proveedores. |
| `tools/scraper.py` | Motor de scraping: descarga y parseo de fichas (JSON-LD > OpenGraph > HTML). |
| `tools/classify.py` | Clasificador de línea (Hombre/Mujer) y familia de relojes. |
| `tools/cargar_casajoia.py` | Carga puntual de productos de Casa Joia (dataset histórico). |
| `tools/ver_marcas.py` / `ver_productos.py` | Conteos rápidos para inspeccionar la base. |

Uso: `python tools/run_scrape.py --list` (desde la raíz del repo).

### Infraestructura y calidad

| Archivo | Para qué sirve |
|---|---|
| `render.yaml` | Configuración de despliegue en Render (build, arranque, variables). |
| `requirements.txt` | Dependencias Python (Flask, reportlab, Pillow…). |
| `tests/test_smoke.py` | **Prueba de humo**: verifica logins, bloqueos de seguridad y fotos. Correr: `python tests/test_smoke.py`. |
| `.gitignore` | Archivos que NO se suben (cachés, `salida/`, bases demo). |

---

## 2. Rutas de la web

| Ruta | Acceso | Qué hay |
|---|---|---|
| `/client` | **Público** | Catálogo para clientes (solo lectura, sin precios) |
| `/catalogo` | Público (login para editar) | Catálogo online con búsqueda y edición |
| `/login` | Público | Acceso (admin y socio) |
| `/` | **Login** | Panel de administración |
| `/agregar` | **Login** | Alta manual de productos con fotos |
| `/pdf` | **Login** | Generación de PDFs por marca |
| `/img/<ruta>` | Público | Fotos desde `data/imagenes/` (proxy para URL remotas) |
| `/static/<ruta>` | Público | **Solo imágenes** (logos/favicon). Código y `.db` responden 404. |

## 3. Usuarios

| Rol | Email | Contraseña por defecto |
|---|---|---|
| admin | `admin@mitienda.com.py` | `admin123` |
| socio (revendedor) | `socio@mitienda.com.py` | `socio123` |

En producción se pueden cambiar sin tocar código con las variables `ADMIN_PASSWORD`, `SOCIO_PASSWORD` y `SECRET_KEY`.

---

## 4. Correr en local

```bash
pip install -r requirements.txt
python app.py                # http://127.0.0.1:5000
python tests/test_smoke.py   # prueba de humo (21 checks)
```

---

## 5. Cómo se publican los cambios (Render)

> **⚠️ Antes de CADA despliegue: rescatar los precios.** Render restaura `catalogo.db`
> desde el repositorio en cada deploy, así que lo que el cliente cargue en el panel
> (precios) vive solo hasta el próximo despliegue. Correr desde la raíz del repo:
> ```powershell
> python tools/rescatar_precios.py --aplicar    # baja los precios del servidor al repo
> ```
> y sumar `catalogo.db` al commit. Sin ese paso, los precios cargados en producción se pierden.

1. Subir el cambio a GitHub (rama `main`).
2. Disparar el **deploy hook** (URL secreta guardada en la PC del administrador):
   ```powershell
   Invoke-WebRequest -Uri "https://api.render.com/deploy/srv-…?key=…" 
   ```
   Render construye y publica en ~40 s. (El Auto-Deploy "On Commit" está activo pero la conexión
   GitHub→Render no empuja eventos, por eso usamos el hook.)

## 6. Migración a Hostinger (cuando se decida)

**Qué llevar:** este repositorio completo (código + `catalogo.db` + `data/imagenes/` ≈ 110 MB).

Pasos generales:

1. **Exportar**: generar un ZIP del repo (sin `.git/`, sin `__pycache__/`, sin `salida/`).
2. **Subir** por el Administrador de Archivos de Hostinger a la carpeta raíz del dominio.
3. **Asegurar soporte Python**: el plan debe poder correr `python` + `gunicorn`
   (VPS = garantizado; hosting compartido = verificar la sección "Terminal/Python" del hPanel).
4. **Configurar arranque**:
   ```bash
   pip install -r requirements.txt
   gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1 --threads 2
   ```
5. **Variables de entorno**: `CATALOGO_DATA_DIR=data`, `SECRET_KEY`, `ADMIN_PASSWORD`, `SOCIO_PASSWORD`.
6. **Verificar** con la misma prueba: `python tests/test_smoke.py` y entrar a `/client`.

> Cuando decidas el momento, se hace junto a vos paso a paso y se deja el Render actual
> andando como respaldo hasta validar la migración.

---

## 7. Seguridad (blindada — verificar antes de cada despliegue)

- Panel, PDF, CSV y acciones masivas **requieren login**; APIs responden **401 sin sesión**.
- `/static` solo entrega **imágenes** — la base `catalogo.db` y el código `.py` responden 404.
- `/client` nunca muestra precios ni controles de administración.
- `tests/test_smoke.py` verifica todo lo anterior (21 checks).

## 8. Cómo extender el catálogo

- **Nueva marca para scrapear**: agregar una entrada en `config.BRANDS` y correr
  `python tools/run_scrape.py --brand <clave>`.
- **Nueva categoría visible** (ej. una tienda nueva de lentes): sumarla en el set
  correspondiente de `marcas.py` (`TIENDAS_LENTES`, `TIENDAS_PERFUMES`, `TIENDAS_RELOJES`).
- **Nueva marca en el menú**: agregarla a `MARCAS_RELOJ`/`CLAVES_MARCA` en `marcas.py`.
- **Cambiar diseño de PDFs**: editar `theme.json` (colores, columnas, textos de contacto).
- **Productos manuales**: desde el panel → *Agregar*, con fotos desde la PC.

## 9. Estructura de datos (tabla `products`)

`brand` (marca/tienda), `reference`, `name`, `line`, `gender`, `description`,
`price` (origen), `sell_price` (venta), `images` (JSON de rutas relativas),
`url` (ficha de origen), `status` (`active`/`deleted` — nunca se borra de verdad).
