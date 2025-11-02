# app.py
# Ejecuta con: python app.py
# Requiere: pip install mysql-connector-python flask flask-cors

import mysql.connector
from flask import Flask, request, jsonify
from flask_cors import CORS 

app = Flask(__name__)
CORS(app) 

# ----------------------------------------------------------------------
# Configuración de la Conexión a la Base de Datos
# ----------------------------------------------------------------------

DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "contrasena",
    "database": "dofdb",
    "port": 3306
}

def get_db_connection():
    """Establece y retorna una nueva conexión a la base de datos."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Error al conectar a MySQL: {err}")
        return None

# ----------------------------------------------------------------------
# Rutas de la API (Endpoints CRUD)
# ----------------------------------------------------------------------

# ------------------------------------------------------
# 1. CREATE (POST) - Crear un nuevo resumen
# REQUIERE TODOS LOS CAMPOS OBLIGATORIOS
@app.route('/summaries', methods=['POST'])
def create_summary():
    data = request.get_json()
    
    # Valida que todos los campos OBLIGATORIOS estén presentes.
    required_fields = ['object_type', 'object_id', 'model', 'summary_text', 'confidence']
    missing_fields = [field for field in required_fields if field not in data]
    
    if missing_fields:
        return jsonify({"message": f"Faltan campos obligatorios: {', '.join(missing_fields)}"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor()
    
    # La consulta SQL incluye todos los campos, usando .get() para los opcionales
    sql = """
    INSERT INTO summaries (object_type, object_id, model, model_version, lang, summary_text, confidence, created_by)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    values = (
        data['object_type'],
        data['object_id'],
        data['model'],
        data.get('model_version'),
        data.get('lang', 'es'), # Usa 'es' si no se provee
        data['summary_text'],
        data['confidence'],
        data.get('created_by')
    )

    try:
        cursor.execute(sql, values)
        conn.commit()
        new_id = cursor.lastrowid
        return jsonify({"message": "Resumen creado exitosamente", "id": new_id}), 201
    except mysql.connector.Error as err:
        conn.rollback()
        # Manejo específico para error de ENUM si object_type es incorrecto
        if "Data too long for column" in str(err) or "Incorrect enum value" in str(err):
            return jsonify({"message": f"Error de dato (ENUM o longitud): {err}"}), 400
        return jsonify({"message": f"Error al crear resumen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ------------------------------------------------------
# 2. READ (GET) - Obtener todos o uno
# MUESTRA TODOS LOS CAMPOS
@app.route('/summaries', methods=['GET'])
def get_summaries():
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True) # Retorna resultados como diccionarios
    
    try:
        # SELECCIONA * para asegurar que todos los campos, incluido summary_text, se muestren
        cursor.execute("SELECT * FROM summaries")
        summaries = cursor.fetchall()
        return jsonify(summaries), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al leer resúmenes: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/summaries/<int:summary_id>', methods=['GET'])
def get_summary(summary_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)

    try:
        # SELECCIONA * para asegurar que todos los campos se muestren
        cursor.execute("SELECT * FROM summaries WHERE id = %s", (summary_id,))
        summary = cursor.fetchone()
        
        if summary:
            return jsonify(summary), 200
        else:
            return jsonify({"message": "Resumen no encontrado"}), 404
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error al leer resumen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ------------------------------------------------------
# 3. UPDATE (PUT) - Actualizar un resumen existente
# Se mantiene la flexibilidad para actualizar solo los campos proporcionados.
@app.route('/summaries/<int:summary_id>', methods=['PUT'])
def update_summary(summary_id):
    data = request.get_json()
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"message": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor()
    
    # Construir la consulta de UPDATE dinámicamente con todos los campos actualizables
    fields = []
    values = []
    
    updatable_fields = ['object_type', 'object_id', 'model', 'model_version', 'lang', 'summary_text', 'confidence', 'created_by']
    
    for field in updatable_fields:
        if field in data:
            fields.append(f"{field} = %s")
            values.append(data[field])
        
    if not fields:
        return jsonify({"message": "No se proporcionaron campos para actualizar"}), 400

    sql = "UPDATE summaries SET " + ", ".join(fields) + " WHERE id = %s"
    values.append(summary_id)

    try:
        cursor.execute(sql, tuple(values))
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({"message": f"Resumen con ID {summary_id} actualizado"}), 200
        else:
            return jsonify({"message": f"Resumen con ID {summary_id} no encontrado o sin cambios"}), 404
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error al actualizar resumen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ------------------------------------------------------
# 4. DELETE (DELETE) - Eliminar un resumen
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
            return jsonify({"message": f"Resumen con ID {summary_id} eliminado exitosamente"}), 200
        else:
            return jsonify({"message": f"Resumen con ID {summary_id} no encontrado"}), 404
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"message": f"Error al eliminar resumen: {err}"}), 500
    finally:
        cursor.close()
        conn.close()

# ----------------------------------------------------------------------
# Inicialización de la Aplicación
# ----------------------------------------------------------------------

if __name__ == '__main__':
    print("Servidor Flask iniciado. Accede a http://127.0.0.1:5000")
    app.run( port = 8000, debug=True)
