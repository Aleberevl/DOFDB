## Programa en Python (Flask)

Este script implementa las operaciones de **CRUD** (`GET`, `POST`, `PUT`, `DELETE`) para `/jedis` tal como se definen en el archivo `jedis.yaml`.

Guarda el siguiente código como `app.py`:

``` Python
from flask import Flask, request, jsonify, abort
import random
import time

app = Flask(__name__)

# Simulación de la "base de datos": una lista de diccionarios para almacenar Jedis
# Inicializamos con algunos datos para pruebas
jedis_db = [
    {
        "id": 1,
        "nombre": "Yoda",
        "rango": "Gran Maestro",
        "especie": "Desconocida",
        "padawanId": None,
        "midiclorianos": 20000
    },
    {
        "id": 2,
        "nombre": "Obi-Wan Kenobi",
        "rango": "Maestro",
        "especie": "Humano",
        "padawanId": 3,
        "midiclorianos": 13400
    },
    {
        "id": 3,
        "nombre": "Anakin Skywalker",
        "rango": "Caballero",
        "especie": "Humano",
        "padawanId": None,
        "midiclorianos": 27700
    }
]

# Inicializador de IDs (simulando autoincremento de DB)
last_jedi_id = 3

# --- FUNCIONES AUXILIARES ---
def generate_error_response(code, message):
    return jsonify({
        "codigo": f"JEDI_{code}",
        "mensaje": message
    })

def require_auth():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        # 401: UnauthorizedError
        abort(401, description="Acceso no autorizado. Falta el token de autenticación o es inválido.")
    # En un entorno real, aquí se validaría el token JWT

    
# --- IMPLEMENTACIÓN DE ENDPOINTS (PATHS) ---

# Endpoint 1: GET /jedis (Obtener lista y filtrar)
@app.route('/v1/jedis', methods=['GET'])
def get_jedis():
    require_auth()
    
    # Parámetros de consulta (query parameters)
    rango_filtro = request.args.get('rango')
    pagina = request.args.get('pagina', 1, type=int)
    
    filtrados = [j for j in jedis_db if not rango_filtro or j['rango'] == rango_filtro]
    
    # Simulación de paginación (tamaño 5 por página)
    items_por_pagina = 5
    inicio = (pagina - 1) * items_por_pagina
    fin = inicio + items_por_pagina
    
    # Se omiten datos sensibles (midiclorianos) en la respuesta de la lista
    resultado = [{k: v for k, v in j.items() if k != 'midiclorianos'} for j in filtrados[inicio:fin]]
    
    return jsonify(resultado), 200

# Endpoint 2: POST /jedis (Registrar un nuevo Jedi)
@app.route('/v1/jedis', methods=['POST'])
def create_jedi():
    global last_jedi_id
    require_auth()
    
    data = request.get_json()
    if not data or not all(k in data for k in ('nombre', 'rango', 'especie', 'midiclorianos')):
        # 400: BadRequestError
        return generate_error_response(400, "Faltan campos requeridos: nombre, rango, especie y midiclorianos."), 400

    last_jedi_id += 1
    new_jedi = {
        "id": last_jedi_id,
        "nombre": data['nombre'],
        "rango": data['rango'],
        "especie": data['especie'],
        "padawanId": data.get('padawanId'),
        "midiclorianos": data['midiclorianos']
    }
    
    jedis_db.append(new_jedi)

    # Se omiten datos sensibles (midiclorianos) en la respuesta POST
    response_jedi = {k: v for k, v in new_jedi.items() if k != 'midiclorianos'}
    
    return jsonify(response_jedi), 201

# Endpoint 3: GET /jedis/{jediId} (Consultar por ID)
@app.route('/v1/jedis/<int:jedi_id>', methods=['GET'])
def get_jedi_by_id(jedi_id):
    require_auth()
    
    jedi = next((j for j in jedis_db if j['id'] == jedi_id), None)
    
    if jedi is None:
        # 404: NotFoundError
        return generate_error_response(404, f"No se encontró ningún Jedi con el ID {jedi_id}."), 404

    # Se omiten datos sensibles (midiclorianos)
    response_jedi = {k: v for k, v in jedi.items() if k != 'midiclorianos'}
    return jsonify(response_jedi), 200

# Endpoint 4: PUT /jedis/{jediId} (Modificar completamente)
@app.route('/v1/jedis/<int:jedi_id>', methods=['PUT'])
def update_jedi(jedi_id):
    require_auth()
    
    data = request.get_json()
    if not data or not all(k in data for k in ('nombre', 'rango', 'especie', 'midiclorianos')):
        # 400: BadRequestError
        return generate_error_response(400, "Faltan campos requeridos para la actualización total."), 400

    jedi_index = next((i for i, j in enumerate(jedis_db) if j['id'] == jedi_id), -1)

    if jedi_index == -1:
        # 404: NotFoundError
        return generate_error_response(404, f"No se encontró ningún Jedi con el ID {jedi_id} para modificar."), 404

    # Actualizar todos los campos
    jedis_db[jedi_index].update({
        "nombre": data['nombre'],
        "rango": data['rango'],
        "especie": data['especie'],
        "padawanId": data.get('padawanId'),
        "midiclorianos": data['midiclorianos'] # Actualizar dato sensible
    })

    # Respuesta 200 OK con el objeto actualizado (sin midiclorianos)
    response_jedi = {k: v for k, v in jedis_db[jedi_index].items() if k != 'midiclorianos'}
    return jsonify(response_jedi), 200

# Endpoint 5: DELETE /jedis/{jediId} (Eliminar)
@app.route('/v1/jedis/<int:jedi_id>', methods=['DELETE'])
def delete_jedi(jedi_id):
    global jedis_db
    require_auth()
    
    jedi_index = next((i for i, j in enumerate(jedis_db) if j['id'] == jedi_id), -1)

    if jedi_index == -1:
        # 404: NotFoundError
        return generate_error_response(404, f"No se encontró ningún Jedi con el ID {jedi_id} para eliminar."), 404

    jedis_db.pop(jedi_index)
    
    # 204 No Content
    return '', 204

# Endpoint 6: PATCH /jedis/{jediId}/rango (Modificar solo el rango)
@app.route('/v1/jedis/<int:jedi_id>/rango', methods=['PATCH'])
def patch_jedi_rank(jedi_id):
    require_auth()
    
    # Simulación de que solo un "Maestro del Consejo" puede usar este endpoint (403 Prohibido)
    auth_header = request.headers.get('Authorization')
    if auth_header and "MAESTRO_CONSEJO_TOKEN" not in auth_header:
         return generate_error_response(403, "Prohibido. El usuario no es un Maestro del Consejo."), 403

    data = request.get_json()
    nuevo_rango = data.get('nuevoRango')

    if not nuevo_rango:
        return generate_error_response(400, "El campo 'nuevoRango' es requerido para la modificación parcial."), 400

    jedi_index = next((i for i, j in enumerate(jedis_db) if j['id'] == jedi_id), -1)

    if jedi_index == -1:
        # 404: NotFoundError
        return generate_error_response(404, f"No se encontró ningún Jedi con el ID {jedi_id} para modificar su rango."), 404

    # Actualizar solo el rango
    jedis_db[jedi_index]['rango'] = nuevo_rango

    # Respuesta 200 OK con el objeto actualizado (sin midiclorianos)
    response_jedi = {k: v for k, v in jedis_db[jedi_index].items() if k != 'midiclorianos'}
    return jsonify(response_jedi), 200

# Endpoint 7: GET /rangos (Lista de rangos)
@app.route('/v1/rangos', methods=['GET'])
def get_rangos():
    require_auth()
    
    # Datos estáticos que simulan el modelo 'Rango' del OpenAPI
    rangos = [
        {"nombre": "Padawan", "minJedis": 0},
        {"nombre": "Caballero", "minJedis": 10},
        {"nombre": "Maestro", "minJedis": 50},
        {"nombre": "Gran Maestro", "minJedis": 100}
    ]
    return jsonify(rangos), 200

# Manejo de Errores Globales (Para capturar los aborts)
@app.errorhandler(401)
def unauthorized_error(e):
    return generate_error_response(401, e.description), 401

@app.errorhandler(404)
def not_found_error(e):
    # Flask puede generar 404 para rutas no encontradas.
    # Usamos el modelo NotFoundError
    return generate_error_response(404, "El recurso solicitado no fue encontrado."), 404


if __name__ == '__main__':
    # Usamos puerto 5000 por defecto para Flask
    print("Iniciando API de la Orden Jedi en http://localhost:5000/v1")
    app.run(debug=True, port=5000)
```

Instalar dependencias
```
pip3 install flask requests
```

Correr el programa
```
python app.py
```


***

## Ejemplos de Consumo con `curl`

Para probar estos servicios, se asume que el servidor Flask está corriendo en `localhost:5000`. Es necesario que abra **otra** terminal, para que los servicios web sigan corriendo.

**Nota:** El programa de Python requiere un _token de autorización_ simulado (`<YOUR_JWT_TOKEN>`) para la mayoría de las operaciones, de acuerdo con la especificación `BearerAuth` del `jedis.yaml`.

### 1. POST /jedis (Registrar un nuevo Jedi)

Registra un nuevo Jedi en la lista.

Bash

```
curl -X POST 'http://localhost:5000/v1/jedis' \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer <YOUR_JWT_TOKEN>' \
-d '{
    "nombre": "Ahsoka Tano",
    "rango": "Padawan",
    "especie": "Togruta",
    "midiclorianos": 12000
}'
```

**Respuesta Esperada (201 Created):**

JSON

```
{
    "id": 4, 
    "nombre": "Ahsoka Tano", 
    "rango": "Padawan", 
    "especie": "Togruta", 
    "padawanId": null
}
```

### 2. GET /jedis (Consultar la Lista)

Obtiene todos los Jedis, con paginación y filtro opcional.

Bash

```
# Consultar todos los Jedis
curl -X GET 'http://localhost:5000/v1/jedis' \
-H 'Authorization: Bearer <YOUR_JWT_TOKEN>'

# Consultar solo los de rango 'Maestro'
curl -X GET 'http://localhost:5000/v1/jedis?rango=Maestro' \
-H 'Authorization: Bearer <YOUR_JWT_TOKEN>'
```

### 3. GET /jedis/{jediId} (Consultar por ID)

Consulta los detalles del Jedi con ID 1 (Yoda).

Bash

```
curl -X GET 'http://localhost:5000/v1/jedis/1' \
-H 'Authorization: Bearer <YOUR_JWT_TOKEN>'
```

**Respuesta Esperada (200 OK):**

JSON

```
{
    "id": 1, 
    "nombre": "Yoda", 
    "rango": "Gran Maestro", 
    "especie": "Desconocida", 
    "padawanId": null
}
```

### 4. PUT /jedis/{jediId} (Modificar Completamente)

Actualiza completamente al Jedi con ID 3 (Anakin).

Bash

```
curl -X PUT 'http://localhost:5000/v1/jedis/3' \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer <YOUR_JWT_TOKEN>' \
-d '{
    "nombre": "Darth Vader",
    "rango": "Lord Sith",
    "especie": "Humano",
    "padawanId": null,
    "midiclorianos": 4000
}'
```

### 5. PATCH /jedis/{jediId}/rango (Modificación Parcial)

Modifica solo el rango del Jedi con ID 4 (Ahsoka).

**Nota:** Este endpoint simula una validación más estricta (`MAESTRO_CONSEJO_TOKEN`).

Bash

```
curl -X PATCH 'http://localhost:5000/v1/jedis/4/rango' \
-H 'Content-Type: application/json' \
-H 'Authorization: Bearer MAESTRO_CONSEJO_TOKEN' \
-d '{
    "nuevoRango": "Caballero"
}'
```

### 6. DELETE /jedis/{jediId} (Eliminar)

Elimina al Jedi con ID 3 (Darth Vader/Anakin).

Bash

```
curl -X DELETE 'http://localhost:5000/v1/jedis/3' \
-H 'Authorization: Bearer <YOUR_JWT_TOKEN>'
```

**Respuesta Esperada (204 No Content):**

Bash

```
# No hay cuerpo de respuesta
```

### 7. GET /rangos (Consultar Recursos Secundarios)

Consulta el catálogo de rangos.

Bash

```
curl -X GET 'http://localhost:5000/v1/rangos' \
-H 'Authorization: Bearer <YOUR_JWT_TOKEN>'
```

**Respuesta Esperada (200 OK):**

JSON

```
[
  { "nombre": "Padawan", "minJedis": 0 },
  { "nombre": "Caballero", "minJedis": 10 },
  { "nombre": "Maestro", "minJedis": 50 },
  { "nombre": "Gran Maestro", "minJedis": 100 }
]
```
