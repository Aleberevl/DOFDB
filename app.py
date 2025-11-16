# app.py
# Ejecuta:  python app.py
# Requiere:
#   pip install flask flask-cors mysql-connector-python requests PyPDF2

import io
import os
import requests
import mysql.connector
from flask import Flask, jsonify, send_file, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================
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
        print(f"[DB] Error al conectar a MySQL: {err}")
        return None

# ============================================================================
# UTILIDADES
# ============================================================================
def _try_read(path: str):
    """Intenta leer archivo binario si existe. (typing opcional para compatibilidad)"""
    try:
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    except Exception as e:
        print(f"[FS] No se pudo leer '{path}': {e}")
    return None

def _fetch_pdf_bytes(storage_uri: str, public_url: str | None = None) -> bytes:
    """
    Orden de resolución:
      1) DOF_PDF/<storage_uri> (preferido)
      2) storage_uri como ruta absoluta/relativa al proyecto
      3) public_url http(s)
      4) storage_uri http(s)
      5) s3:// -> no implementado sin URL pública
    """
    # 1) DOF_PDF/<storage_uri>
    local_candidate = os.path.join(PROJECT_ROOT, BASE_PDF_DIR, storage_uri)
    data = _try_read(local_candidate)
    if data is not None:
        return data

    # 2) storage_uri como ruta en disco
    abs_candidate = storage_uri
    if not os.path.isabs(abs_candidate):
        abs_candidate = os.path.join(PROJECT_ROOT, storage_uri)
    data = _try_read(abs_candidate)
    if data is not None:
        return data

    # 3) public_url http(s)
    if isinstance(public_url, str) and public_url.lower().startswith(("http://", "https://")):
        r = requests.get(public_url, stream=True, timeout=60)
        r.raise_for_status()
        return r.content

    # 4) storage_uri http(s)
    if isinstance(storage_uri, str) and storage_uri.lower().startswith(("http://", "https://")):
        r = requests.get(storage_uri, stream=True, timeout=60)
        r.raise_for_status()
        return r.content

    # 5) s3 sin URL pública
    if isinstance(storage_uri, str) and storage_uri.lower().startswith("s3://"):
        raise NotImplementedError("storage_uri s3:// requiere URL pública (public_url) presignada.")

    raise FileNotFoundError(
        f"No se encontró el PDF. Revisa storage_uri='{storage_uri}' y carpeta '{BASE_PDF_DIR}/'."
    )

def _safe_filename(base: str) -> str:
    return "".join(c for c in base if c.isalnum() or c in ("-", "_", ".", " ")).strip() or "document"

# ============================================================================
# RAÍZ
# ============================================================================
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "DOF Files API",
        "endpoints": [
            # Archivos DOF (listar / detalle / descargar / reindexar páginas)
            "GET  /dof/files",
            "GET  /dof/files/<file_id>",
            "GET  /dof/files/<file_id>/download",
            "POST /admin/reindex_pages",
            # Summaries CRUD
            "POST /summaries",
            "GET  /summaries",
            "GET  /summaries/<summary_id>",
            "PUT  /summaries/<summary_id>",
            "DELETE /summaries/<summary_id>",
            "GET  /summaries/<summary_id>/share",
            # Publicaciones
            "GET  /dof/publications",
            "GET  /dof/publications/<pub_id>",
        ]
    })

# ============================================================================
# A) ARCHIVOS DOF — LISTAR ÚLTIMAS 5
# GET /dof/files
# publication_date derivada del nombre PDF: 04112025-MAT.pdf -> 2025-11-04
# ============================================================================
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

# ============================================================================
# B) ARCHIVOS DOF — DETALLE (PÁGINAS TOTALES)
# GET /dof/files/<id>
# Devuelve pages_total desde files.pages_count (no expandimos tabla pages)
# ============================================================================
@app.route("/dof/files/<int:file_id>", methods=["GET"])
def get_file_detail(file_id):
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
                f.mime,
                f.has_ocr,
                f.pages_count,
                p.source_url
            FROM files f
            JOIN publications p ON p.id = f.publication_id
            WHERE f.id = %s
            """,
            (file_id,),
        )
        file_row = cursor.fetchone()
        if not file_row:
            return jsonify({"message": "Archivo DOF no encontrado"}), 404

        cursor.execute(
            """
            SELECT summary_text
            FROM summaries
            WHERE object_type = 'publication' AND object_id = %s
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
            "source_url": file_row["source_url"],
            "pages_total": int(file_row["pages_count"] or 0),
            "summary": summary_text,
        }), 200

    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar archivo DOF: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# C) ARCHIVOS DOF — DESCARGAR PDF
# GET /dof/files/<id>/download
# Prioriza DOF_PDF/<storage_uri>; si no está, usa public_url/http(s)
# Nombre descarga usa fecha derivada del filename + tipo publicación
# ============================================================================
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

        try:
            pdf_bytes = _fetch_pdf_bytes(frow["storage_uri"], frow.get("public_url"))
        except FileNotFoundError as fe:
            return jsonify({"message": str(fe)}), 404
        except requests.HTTPError as he:
            return jsonify({"message": f"HTTP error al descargar PDF: {he}"}), 502
        except Exception as e:
            return jsonify({"message": f"No se pudo obtener el PDF: {e}"}), 502

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

    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al preparar descarga: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# D) ADMIN — RECONTAR PÁGINAS DESDE PDFs LOCALES
# POST /admin/reindex_pages
# Lee cada PDF y actualiza files.pages_count
# ============================================================================
@app.route("/admin/reindex_pages", methods=["POST"])
def admin_reindex_pages():
    try:
        from PyPDF2 import PdfReader
    except Exception as e:
        return jsonify({"message": f"PyPDF2 no disponible: {e}"}), 500

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, storage_uri FROM files")
        files = cursor.fetchall()

        updated = []
        not_found = []
        errors = []

        for row in files:
            fid = row["id"]
            storage_uri = row["storage_uri"]
            local_path = os.path.join(PROJECT_ROOT, BASE_PDF_DIR, storage_uri)
            if not os.path.exists(local_path):
                alt = storage_uri if os.path.isabs(storage_uri) else os.path.join(PROJECT_ROOT, storage_uri)
                if os.path.exists(alt):
                    local_path = alt
                else:
                    not_found.append({"id": fid, "storage_uri": storage_uri})
                    continue

            try:
                with open(local_path, "rb") as f:
                    reader = PdfReader(f)
                    total = len(reader.pages)
            except Exception as e:
                errors.append({"id": fid, "storage_uri": storage_uri, "error": str(e)})
                continue

            try:
                cursor2 = conn.cursor()
                cursor2.execute("UPDATE files SET pages_count=%s WHERE id=%s", (total, fid))
                cursor2.close()
                updated.append({"id": fid, "pages_count": total})
            except mysql.connector.Error as e:
                errors.append({"id": fid, "db_error": str(e)})

        conn.commit()
        return jsonify({
            "updated": updated,
            "not_found": not_found,
            "errors": errors
        }), 200

    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error en reindex_pages: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# E) SUMMARIES — CRUD
# ============================================================================
# 1) CREATE
@app.route('/summaries', methods=['POST'])
def create_summary():
    data = request.get_json() or {}
    required_fields = ['object_type', 'object_id', 'model', 'summary_text', 'confidence']
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"message": f"Faltan campos obligatorios: {', '.join(missing)}"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor()

    sql = """
    INSERT INTO summaries (object_type, object_id, model, model_version, lang, summary_text, confidence, created_by)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        data['object_type'],
        data['object_id'],
        data['model'],
        data.get('model_version'),
        data.get('lang', 'es'),
        data['summary_text'],
        data['confidence'],
        data.get('created_by')
    )

    try:
        cursor.execute(sql, values)
        conn.commit()
        return jsonify({"message": "Resumen creado exitosamente", "id": cursor.lastrowid}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        if "Incorrect enum value" in str(err) or "Data too long" in str(err):
            return jsonify({"message": f"Error de dato (ENUM/longitud): {err}"}), 400
        return jsonify({"message": f"Error al crear resumen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# 2) READ (lista)
@app.route('/summaries', methods=['GET'])
def get_summaries():
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM summaries ORDER BY created_at DESC")
        return jsonify(cursor.fetchall()), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al leer resúmenes: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# 2b) READ (detalle)
@app.route('/summaries/<int:summary_id>', methods=['GET'])
def get_summary(summary_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM summaries WHERE id = %s", (summary_id,))
        row = cursor.fetchone()
        if row:
            return jsonify(row), 200
        return jsonify({"message": "Resumen no encontrado"}), 404
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al leer resumen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# 3) UPDATE
@app.route('/summaries/<int:summary_id>', methods=['PUT'])
def update_summary(summary_id):
    data = get_json_safely()
    if data is None:
        data = request.get_json() or {}

    updatable = ['object_type', 'object_id', 'model', 'model_version', 'lang', 'summary_text', 'confidence', 'created_by']
    sets, vals = [], []
    for f in updatable:
        if f in data:
            sets.append(f"{f}=%s")
            vals.append(data[f])
    if not sets:
        return jsonify({"message": "No se proporcionaron campos para actualizar"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE summaries SET " + ", ".join(sets) + " WHERE id = %s", (*vals, summary_id))
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({"message": f"Resumen {summary_id} actualizado"}), 200
        return jsonify({"message": "Resumen no encontrado o sin cambios"}), 404
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error al actualizar resumen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# 4) DELETE
@app.route('/summaries/<int:summary_id>', methods=['DELETE'])
def delete_summary(summary_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM summaries WHERE id = %s", (summary_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({"message": f"Resumen {summary_id} eliminado"}), 200
        return jsonify({"message": "Resumen no encontrado"}), 404
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error al eliminar resumen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# 5) SHARE: devolver summary + link oficial según objeto
@app.route("/summaries/<int:summary_id>/share", methods=["GET"])
def share_summary(summary_id: int):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500
    c = conn.cursor(dictionary=True)

    try:
        # Obtener summary
        c.execute("""
            SELECT id, summary_text, object_type, object_id
            FROM summaries
            WHERE id = %s
        """, (summary_id,))
        s = c.fetchone()
        if not s:
            return jsonify({"message": "Resumen no encontrado"}), 404

        source_url = None
        if s["object_type"] == "publication":
            c.execute("SELECT source_url FROM publications WHERE id = %s", (s["object_id"],))
            row = c.fetchone()
            source_url = row["source_url"] if row else None
        elif s["object_type"] == "section":
            c.execute("""
                SELECT p.source_url
                FROM sections sec
                JOIN publications p ON p.id = sec.publication_id
                WHERE sec.id = %s
            """, (s["object_id"],))
            row = c.fetchone()
            source_url = row["source_url"] if row else None
        elif s["object_type"] == "item":
            c.execute("""
                SELECT p.source_url
                FROM items i
                JOIN sections sec ON sec.id = i.section_id
                JOIN publications p ON p.id = sec.publication_id
                WHERE i.id = %s
            """, (s["object_id"],))
            row = c.fetchone()
            source_url = row["source_url"] if row else None
        else:
            source_url = None  # 'chunk' u otro tipo no trazable directamente

        return jsonify({
            "summary_id": s["id"],
            "summary_text": s["summary_text"],
            "source_url": source_url
        }), 200

    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al compartir resumen: {err}"}), 500
    finally:
        c.close()
        conn.close()

# ============================================================================
# F) PUBLICACIONES — LISTA
# GET /dof/publications
# ============================================================================
@app.route("/dof/publications", methods=["GET"])
def get_publications_list():
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT
            p.id,
            p.dof_date,
            p.issue_number,
            p.type,
            p.source_url,
            p.status,
            f.id AS file_id,
            f.pages_count
        FROM publications p
        LEFT JOIN files f ON p.id = f.publication_id
        ORDER BY p.dof_date DESC
        LIMIT 10
    """
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        return jsonify(rows), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar publicaciones: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# G) PUBLICACIONES — DETALLE ESTRUCTURADO
# GET /dof/publications/<pub_id>
# Publicación con secciones, items, entidades y páginas (del archivo)
# ============================================================================
@app.route("/dof/publications/<int:pub_id>", methods=["GET"])
def get_publication_detail(pub_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        # 1) Publicación + archivo
        cursor.execute("""
            SELECT
                p.id, p.dof_date, p.issue_number, p.type, p.source_url, p.status, p.published_at,
                f.id AS file_id, f.storage_uri, f.public_url, f.pages_count, f.mime, f.has_ocr
            FROM publications p
            LEFT JOIN files f ON p.id = f.publication_id
            WHERE p.id = %s
        """, (pub_id,))
        pub_row = cursor.fetchone()
        if not pub_row:
            return jsonify({"message": f"Publicación {pub_id} no encontrada"}), 404

        file_id = pub_row["file_id"]

        # 2) Secciones + items + posible resumen de item
        cursor.execute("""
            SELECT
                s.id AS section_id, s.name AS section_name, s.seq,
                s.page_start AS sec_page_start, s.page_end AS sec_page_end,
                i.id AS item_id, i.item_type, i.title AS item_title, i.issuing_entity,
                i.page_from AS item_page_from, i.page_to AS item_page_to, i.raw_text,
                s_item.summary_text AS item_summary
            FROM sections s
            LEFT JOIN items i ON s.id = i.section_id
            LEFT JOIN summaries s_item ON s_item.object_type = 'item' AND s_item.object_id = i.id
            WHERE s.publication_id = %s
            ORDER BY s.seq, i.page_from
        """, (pub_id,))
        section_item_rows = cursor.fetchall()

        # 3) Entidades por item de la publicación
        cursor.execute("""
            SELECT
                ie.item_id,
                e.id AS entity_id, e.name AS entity_name, e.type AS entity_type, e.norm_name,
                ie.evidence_span
            FROM item_entities ie
            JOIN entities e ON ie.entity_id = e.id
            JOIN items i ON ie.item_id = i.id
            JOIN sections s ON i.section_id = s.id
            WHERE s.publication_id = %s
            ORDER BY ie.item_id
        """, (pub_id,))
        entity_rows = cursor.fetchall()

        # 4) Páginas del archivo (si hay file_id)
        pages = []
        if file_id is not None:
            cursor.execute("""
                SELECT page_no, text, image_uri
                FROM pages
                WHERE file_id = %s
                ORDER BY page_no
            """, (file_id,))
            pages = cursor.fetchall()

        # 5) Armar jerarquía secciones -> items -> entidades
        sections = {}
        item_map = {}
        for r in section_item_rows:
            sid = r["section_id"]
            iid = r["item_id"]
            if sid not in sections:
                sections[sid] = {
                    "id": sid,
                    "name": r["section_name"],
                    "sequence": r["seq"],
                    "page_range": (r["sec_page_start"], r["sec_page_end"]),
                    "items": []
                }
            if iid:
                item_data = {
                    "id": iid,
                    "type": r["item_type"],
                    "title": r["item_title"],
                    "issuing_entity": r["issuing_entity"],
                    "page_range": (r["item_page_from"], r["item_page_to"]),
                    "raw_text": r["raw_text"],
                    "summary": r["item_summary"],
                    "entities": []
                }
                sections[sid]["items"].append(item_data)
                item_map[iid] = item_data

        for er in entity_rows:
            iid = er["item_id"]
            if iid in item_map:
                item_map[iid]["entities"].append({
                    "id": er["entity_id"],
                    "name": er["entity_name"],
                    "type": er["entity_type"],
                    "normalized_name": er["norm_name"],
                    "evidence": er["evidence_span"]
                })

        result = {
            "publication": {
                "id": pub_row["id"],
                "date": pub_row["dof_date"].isoformat() if pub_row["dof_date"] else None,
                "issue_number": pub_row["issue_number"],
                "type": pub_row["type"],
                "status": pub_row["status"],
                "source_url": pub_row["source_url"],
            },
            "file": {
                "id": pub_row["file_id"],
                "mime": pub_row["mime"],
                "pages_count": pub_row["pages_count"],
                "has_ocr": bool(pub_row["has_ocr"]) if pub_row["has_ocr"] is not None else None,
                "storage_uri": pub_row["storage_uri"],
                "public_url": pub_row["public_url"],
            },
            "sections": list(sections.values()),
            "pages": pages,
        }
        return jsonify(result), 200

    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar detalle de publicación: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ============================================================================
# Helper para robustez en PUT (algunos clientes envían text/plain)
# ============================================================================
def get_json_safely():
    """
    Intenta obtener JSON aunque el cliente no mande application/json.
    Devuelve dict o None.
    """
    try:
        return request.get_json(force=False, silent=True)
    except Exception:
        return None

# ============================================================================
# BOOT
# ============================================================================
if __name__ == "__main__":
    print("Servidor Flask iniciado. Accede a http://127.0.0.1:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)
