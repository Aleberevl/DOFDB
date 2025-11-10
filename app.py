# app.py
# Ejecuta con: python app.py
# Requiere: pip install mysql-connector-python flask flask-cors

import mysql.connector
from flask import Flask, jsonify
from flask_cors import CORS

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

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        print(f"Error al conectar a MySQL: {err}")
        return None

# ----------------------------------------------------------------------
# 1) GET /dof/files  -> lista de archivos + datos básicos de publicación
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
            p.dof_date   AS publication_date,
            p.type       AS publication_type,
            p.source_url AS source_url
        FROM files f
        JOIN publications p ON f.publication_id = p.id
        ORDER BY f.id
    """

    try:
        cursor.execute(sql)
        rows = cursor.fetchall()

        # convertir has_ocr a booleano
        for r in rows:
            r["has_ocr"] = bool(r["has_ocr"])

        return jsonify(rows), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar archivos DOF: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# 2) GET /dof/files/{file_id} -> detalle de archivo + páginas + resumen
# ----------------------------------------------------------------------
@app.route("/dof/files/<int:file_id>", methods=["GET"])
def get_file_detail(file_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        # Datos del archivo
        cursor.execute(
            """
            SELECT
                id,
                publication_id,
                storage_uri,
                mime,
                has_ocr
            FROM files
            WHERE id = %s
            """,
            (file_id,),
        )
        file_row = cursor.fetchone()

        if not file_row:
            return jsonify({"message": "Archivo DOF no encontrado"}), 404

        # Páginas del archivo
        cursor.execute(
            """
            SELECT
                page_no,
                text,
                image_uri
            FROM pages
            WHERE file_id = %s
            ORDER BY page_no
            """,
            (file_id,),
        )
        pages = cursor.fetchall()

        # Resumen opcional desde summaries
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
        summary_row = cursor.fetchone()
        summary_text = summary_row["summary_text"] if summary_row else None

        result = {
            "id": file_row["id"],
            "publication_id": file_row["publication_id"],
            "storage_uri": file_row["storage_uri"],
            "mime": file_row["mime"],
            "has_ocr": bool(file_row["has_ocr"]),
            "pages": pages,
            "summary": summary_text,
        }

        return jsonify(result), 200

    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al recuperar archivo DOF: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# Inicialización
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print("Servidor Flask iniciado. Accede a http://127.0.0.1:8000")
    app.run(port=8000, debug=True)
