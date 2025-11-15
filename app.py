# app.py
# Ejecuta con: python app.py
# Requiere:
#   pip install mysql-connector-python flask flask-cors requests PyPDF2

import io
import os
import glob
import requests
import mysql.connector
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS
from PyPDF2 import PdfReader

app = Flask(__name__)
CORS(app)

# ----------------------------------------------------------------------
# Configuración de la Conexión a la Base de Datos
# ----------------------------------------------------------------------
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "contrasena",   # ajusta si usaste otra
    "database": "dofdb",
    "port": 3306,
}

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BASE_PDF_DIR = "DOF_PDF"  # carpeta local con tus PDFs dentro del repo

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print(f"Error al conectar a MySQL: {err}")
        return None

# ----------------------------------------------------------------------
# Utilidades para leer PDF local o vía URL
# ----------------------------------------------------------------------
def _try_read(path: str) -> bytes | None:
    """Intenta leer un archivo binario si existe."""
    if path and os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None

def _fetch_pdf_bytes(storage_uri: str, public_url: str | None = None) -> bytes:
    """
    Orden de resolución:
    1) Ruta local dentro de DOF_PDF/<storage_uri>
    2) storage_uri tal cual como ruta absoluta/relativa al proyecto
    3) public_url http(s)
    4) storage_uri http(s)
    5) s3:// -> no implementado sin URL pública
    """
    # 1) DOF_PDF/<storage_uri>
    local_candidate = os.path.join(PROJECT_ROOT, BASE_PDF_DIR, storage_uri)
    data = _try_read(local_candidate)
    if data is not None:
        return data

    # 2) storage_uri como ruta (absoluta o relativa)
    abs_candidate = storage_uri
    if not os.path.isabs(abs_candidate):
        abs_candidate = os.path.join(PROJECT_ROOT, storage_uri)
    data = _try_read(abs_candidate)
    if data is not None:
        return data

    # 3) URL pública explícita
    if isinstance(public_url, str) and public_url.lower().startswith(("http://", "https://")):
        r = requests.get(public_url, stream=True, timeout=30)
        r.raise_for_status()
        return r.content

    # 4) storage_uri como URL
    if isinstance(storage_uri, str) and storage_uri.lower().startswith(("http://", "https://")):
        r = requests.get(storage_uri, stream=True, timeout=30)
        r.raise_for_status()
        return r.content

    # 5) s3 sin URL pública
    if isinstance(storage_uri, str) and storage_uri.lower().startswith("s3://"):
        raise NotImplementedError(
            "storage_uri s3:// requiere URL pública presignada (public_url)."
        )

    raise FileNotFoundError(
        f"No se pudo encontrar el PDF. Revisar storage_uri='{storage_uri}' y carpeta '{BASE_PDF_DIR}/'."
    )

def _safe_filename(base: str) -> str:
    return "".join(c for c in base if c.isalnum() or c in ("-", "_", ".", " ")).strip() or "document"

# ----------------------------------------------------------------------
# Raíz (índice simple)
# ----------------------------------------------------------------------
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "DOF Files API",
        "endpoints": [
            "GET /dof/files",
            "GET /dof/files/<file_id>",
            "GET /dof/files/<file_id>/download",
            "POST /admin/reindex_pages"
        ],
        "notes": {
            "publication_date": "Se deriva del nombre del PDF (DDMMYYYY-*.pdf)",
            "download": "Entrega solo el PDF; no incluye summary"
        }
    })

# ----------------------------------------------------------------------
# 1) GET /dof/files  -> últimas 5 con metadatos
#    publication_date se deriva del nombre del PDF (04112025-MAT.pdf -> 2025-11-04)
# ----------------------------------------------------------------------
@app.route("/dof/files", methods=["GET"])
def get_files():
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT
            f.id,
            f.publication_id,
            f.storage_uri,
            f.mime,
            f.bytes,
            f.sha256,
            f.has_ocr,
            f.pages_count,
            /* fecha derivada del nombre del PDF: 04112025-MAT.pdf -> 2025-11-04 */
            DATE_FORMAT(
              STR_TO_DATE(SUBSTRING_INDEX(f.storage_uri, '-', 1), '%d%m%Y'),
              '%Y-%m-%d'
            ) AS publication_date,
            p.type       AS publication_type,
            p.source_url AS source_url
        FROM files f
        JOIN publications p ON f.publication_id = p.id
        ORDER BY publication_date DESC, f.id DESC
        LIMIT 5
    """
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        for r in rows:
            r["has_ocr"] = bool(r["has_ocr"])
        return jsonify(rows), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar archivos DOF: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# 2) GET /dof/files/<id> -> detalle + páginas + resumen (JSON)
# ----------------------------------------------------------------------
@app.route("/dof/files/<int:file_id>", methods=["GET"])
def get_file_detail(file_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT id, publication_id, storage_uri, mime, has_ocr
            FROM files
            WHERE id = %s
            """,
            (file_id,),
        )
        file_row = cursor.fetchone()
        if not file_row:
            return jsonify({"message": "Archivo DOF no encontrado"}), 404

        cursor.execute(
            """
            SELECT page_no, text, image_uri
            FROM pages
            WHERE file_id = %s
            ORDER BY page_no
            """,
            (file_id,),
        )
        pages = cursor.fetchall()

        cursor.execute(
            """
            SELECT summary_text
            FROM summaries
            WHERE object_type = 'publication'
              AND object_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (file_row["publication_id"],),
        )
        srow = cursor.fetchone()
        summary_text = srow["summary_text"] if srow else None

        return jsonify({
            "id": file_row["id"],
            "publication_id": file_row["publication_id"],
            "storage_uri": file_row["storage_uri"],
            "mime": file_row["mime"],
            "has_ocr": bool(file_row["has_ocr"]),
            "pages": pages,
            "summary": summary_text,
        }), 200

    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar archivo DOF: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# 3) GET /dof/files/<id>/download -> descarga SIEMPRE el PDF local/URL
# ----------------------------------------------------------------------
@app.route("/dof/files/<int:file_id>/download", methods=["GET"])
def download_file(file_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                f.id,
                f.publication_id,
                f.storage_uri,
                f.public_url,
                f.mime,
                /* nombre base con fecha derivada del filename */
                DATE_FORMAT(
                  STR_TO_DATE(SUBSTRING_INDEX(f.storage_uri, '-', 1), '%d%m%Y'),
                  '%Y-%m-%d'
                ) AS dof_date_fmt,
                p.type AS publication_type
            FROM files f
            JOIN publications p ON f.publication_id = p.id
            WHERE f.id = %s
            """,
            (file_id,),
        )
        frow = cursor.fetchone()
        if not frow:
            return jsonify({"message": "Archivo DOF no encontrado"}), 404

        pdf_bytes = _fetch_pdf_bytes(frow["storage_uri"], frow.get("public_url"))

        base_name = _safe_filename(
            f"DOF_{frow['dof_date_fmt']}_{frow['publication_type']}_file{frow['id']}"
        )
        buf = io.BytesIO(pdf_bytes)
        buf.seek(0)
        mimetype = frow["mime"] or "application/pdf"
        return send_file(
            buf,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"{base_name}.pdf",
        )

    except FileNotFoundError as fe:
        return jsonify({"message": str(fe)}), 404
    except requests.HTTPError as he:
        return jsonify({"message": f"HTTP error al descargar PDF: {he}"}), 502
    except Exception as err:
        return jsonify({"message": f"Error al preparar descarga: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# 4) POST /admin/reindex_pages -> recalcula pages_count leyendo DOF_PDF/*
# ----------------------------------------------------------------------
@app.route("/admin/reindex_pages", methods=["POST"])
def reindex_pages():
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor()

    folder = os.path.join(PROJECT_ROOT, BASE_PDF_DIR)
    pdfs = glob.glob(os.path.join(folder, "*.pdf"))

    updated = {}
    try:
        for path in pdfs:
            fname = os.path.basename(path)
            try:
                n_pages = len(PdfReader(path).pages)
            except Exception:
                n_pages = 0

            cursor.execute(
                "UPDATE files SET pages_count=%s WHERE storage_uri=%s",
                (n_pages, fname),
            )
            updated[fname] = n_pages

        conn.commit()
        return jsonify({"updated": updated, "count": len(updated)}), 200
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error al actualizar pages_count: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# Inicialización
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Servidor Flask iniciado. Accede a http://127.0.0.1:8000")
    # Para Codespaces, escucha en 0.0.0.0
    app.run(host="0.0.0.0", port=8000, debug=True)
