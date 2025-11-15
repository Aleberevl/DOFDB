# BACKEND DOF – API Flask + MySQL (dofdb)

Este proyecto expone una **API REST en Flask** conectada a MySQL (`dofdb`) para trabajar con PDFs del Diario Oficial de la Federación (DOF) **que ya tienes en tu carpeta local del repo `DOF_PDF/`**.

---

## Endpoints

1) **Listar últimas 5 entradas**
   - **GET** `/dof/files`
   - Devuelve: `[ { id, publication_id, storage_uri, mime, bytes, sha256, has_ocr, pages_count, publication_date, publication_type, source_url }, ... ]`
   - **Nota:** `publication_date` se **deriva del nombre del archivo** (por ejemplo, `04112025-MAT.pdf` → `2025-11-04`). No depende de `publications.dof_date`.

2) **Detalle de un archivo**
   - **GET** `/dof/files/<file_id>`
   - Devuelve: metadatos del archivo + `pages` (si existen en tabla) + `summary` (si existe en `summaries`).

3) **Descargar PDF (solo PDF)**
   - **GET** `/dof/files/<file_id>/download`
   - Entrega el **PDF original** desde tu carpeta local `DOF_PDF/` (o desde `public_url` si está seteado como http/https). **No** incluye resumen.

4) **Recalcular páginas (contador automático)**
   - **POST** `/admin/reindex_pages`
   - Recorre la carpeta `DOF_PDF/`, lee cada PDF y actualiza `files.pages_count` usando `PyPDF2` (requiere tener `storage_uri` que coincida con el nombre de archivo).

---

## Estructura esperada del repo

```
.
├─ app.py
├─ DOF_PDF/
│  ├─ 04112025-MAT.pdf
│  ├─ 05112025-MAT.pdf
│  ├─ 06112025-MAT.pdf
│  ├─ 07112025-MAT.pdf
│  └─ 10112025-MAT.pdf
├─ tools/
│  └─ reindex_pages.py
├─ dofdb_estructura.sql
└─ requirements.txt  (flask, flask-cors, mysql-connector-python, PyPDF2)
```

> **Importante**: Los nombres de los PDFs en `DOF_PDF/` deben coincidir con `files.storage_uri`.

---

## MySQL con Docker (Codespaces o local)

1) Crear/arrancar MySQL (puerto 3306):
```bash
docker run --name mysql-container -e MYSQL_ROOT_PASSWORD=contrasena -p 3306:3306 -d mysql:latest
```

2) Crear la base y cargar el esquema seguro:
```bash
docker exec -i mysql-container mysql -u root -pcontrasena -e "CREATE DATABASE IF NOT EXISTS dofdb;"
docker exec -i mysql-container mysql -u root -pcontrasena dofdb < dofdb_estructura.sql
```

3) (Opcional) abrir consola MySQL:
```bash
docker exec -it mysql-container mysql -u root -pcontrasena
```

**DB_CONFIG esperado en `app.py`:**
```python
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "contrasena",
    "database": "dofdb",
    "port": 3306,
}
```

---

## Seed de datos (ejemplo real con tus 5 PDFs)

> Asegúrate de que *ya existen* los 5 PDFs en `DOF_PDF/` con exactamente estos nombres.

```sql
USE dofdb;

INSERT INTO publications (id, dof_date, issue_number, type, source_url, status) VALUES
(20251104, '2025-11-04', 'MAT', 'DOF', 'https://www.dof.gob.mx/index.php?year=2025&month=11&day=04&edicion=MAT#gsc.tab=0', 'parsed'),
(20251105, '2025-11-05', 'MAT', 'DOF', 'https://www.dof.gob.mx/index.php?year=2025&month=11&day=05&edicion=MAT#gsc.tab=0', 'parsed'),
(20251106, '2025-11-06', 'MAT', 'DOF', 'https://www.dof.gob.mx/index_113.php?year=2025&month=11&day=06#gsc.tab=0', 'parsed'),
(20251107, '2025-11-07', 'MAT', 'DOF', 'https://www.dof.gob.mx/index.php?year=2025&month=11&day=07&edicion=MAT#gsc.tab=0', 'parsed'),
(20251110, '2025-11-10', 'MAT', 'DOF', 'https://www.dof.gob.mx/index.php?year=2025&month=11&day=10&edicion=MAT#gsc.tab=0', 'parsed')
ON DUPLICATE KEY UPDATE dof_date=VALUES(dof_date), source_url=VALUES(source_url);

INSERT INTO files (id, publication_id, storage_uri, public_url, mime, bytes, sha256, has_ocr, pages_count) VALUES
(2001, 20251104, '04112025-MAT.pdf', NULL, 'application/pdf', NULL, NULL, 0, 0),
(2002, 20251105, '05112025-MAT.pdf', NULL, 'application/pdf', NULL, NULL, 0, 0),
(2003, 20251106, '06112025-MAT.pdf', NULL, 'application/pdf', NULL, NULL, 0, 0),
(2004, 20251107, '07112025-MAT.pdf', NULL, 'application/pdf', NULL, NULL, 0, 0),
(2005, 20251110, '10112025-MAT.pdf', NULL, 'application/pdf', NULL, NULL, 0, 0)
ON DUPLICATE KEY UPDATE storage_uri=VALUES(storage_uri), publication_id=VALUES(publication_id), mime=VALUES(mime);
```

---

## Ejecutar el API

Instala dependencias y arranca:

```bash
pip install flask flask-cors mysql-connector-python PyPDF2
python app.py
```

- **Local:** navega a <http://127.0.0.1:8000>
- **Codespaces:** usa la URL publicada del puerto 8000, por ejemplo  
  `https://<tu-alias>-8000.app.github.dev/`

---

## Probar Endpoints

> Reemplaza `<TU-URL>` por tu dominio de Codespaces o usa `http://127.0.0.1:8000` si estás local.

- **Listado (últimas 5):**  
  `<TU-URL>/dof/files`

- **Detalle de un archivo (ej. 2003):**  
  `<TU-URL>/dof/files/2003`

- **Descargar PDF (ej. 2003):**  
  `<TU-URL>/dof/files/2003/download`

- **Recalcular páginas:**  
  `POST <TU-URL>/admin/reindex_pages`

Ejemplos con `curl`:

```bash
curl -fsS <TU-URL>/dof/files | python -m json.tool
curl -fsS <TU-URL>/dof/files/2003 | python -m json.tool
curl -fSLOJ "<TU-URL>/dof/files/2003/download"
curl -fsS -X POST "<TU-URL>/admin/reindex_pages" | python -m json.tool
```

---

## Reindexar páginas (contar páginas de PDFs locales)

El script **`tools/reindex_pages.py`** actualiza `files.pages_count` leyendo los PDFs dentro de `DOF_PDF/`.

Ejecutar (desde la raíz del repo):
```bash
python tools/reindex_pages.py
```

Si necesitas instalar dependencias:
```bash
pip install PyPDF2 mysql-connector-python
python tools/reindex_pages.py
```

---

## Notas y resolución de problemas

- Si `/dof/files` sale vacío, revisa que insertaste filas en `files` y que `publication_id` exista.
- Si `/dof/files/<id>/download` da 404, valida que:
  - `files.storage_uri` exista físicamente como `DOF_PDF/<storage_uri>`,
  - el nombre coincide exactamente (incluyendo mayúsculas/minúsculas).
- Si `pages_count` = 0, ejecuta `POST /admin/reindex_pages` **o** `python tools/reindex_pages.py` para contar páginas reales.
- `publication_date` del listado **siempre** se deriva del nombre del PDF (`DDMMYYYY`).
