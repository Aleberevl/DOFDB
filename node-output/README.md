## Actividad: Definición del API con OpenAPI

### Objetivo
Los estudiantes aplicarán los principios de diseño para definir formalmente la interfaz de programación de aplicaciones (API) RESTful del proyecto de su curso, utilizando la Especificación OpenAPI (OAS). El resultado será un contrato digital que servirá como fuente para el desarrollo, la documentación y las pruebas.

### Contexto
En arquitecturas modernas, como las de microservicios, el contrato de API es el punto de integración más crítico. La coherencia, claridad y completitud de este contrato son esenciales para la interoperabilidad y el desarrollo paralelo.

### Requisitos de la entrega
Cada equipo debe crear un archivo de especificación OpenAPI (en formato **YAML**) que defina la API de su proyecto de curso.

1.  **Versión de OpenAPI:** Utilizar OAS 3.0 o 3.1.
2.  **Mínimo de Endpoints:** El archivo debe definir al menos **10 endpoints** distintos para las funcionalidades principales del proyecto (por ejemplo. gestión de usuarios, pedidos, inventario, análisis).
3.  **Operaciones REST:** Se deben utilizar al menos tres métodos HTTP diferentes (GET, POST, PUT, DELETE, PATCH, etc.).

### Tareas específicas para el archivo .yaml

1.  **Sección de Metadatos (`info`):**
    * Definir el `title`, `description` y `version` de la API de manera clara y profesional.
    * Incluir el objeto `contact` con información simulada del equipo de desarrollo.
2.  **Definición de Esquemas (`components/schemas`):**
    * Definir los **modelos de datos** clave de la aplicación (ej. `Usuario`, `Producto`, `Pedido`).
    * Cada esquema debe incluir descripciones, tipos de datos (`type`), formato (`format`) y propiedades requeridas.
    * (Opcional) Puede demostrar el uso de relaciones mediante `$ref` para referenciar esquemas entre sí.
3.  **Definición de Endpoints (`paths`):**
    * Para cada uno de los 10+ endpoints, definir las operaciones HTTP correspondientes.
    * Especificar claramente los **parámetros** de cada operación (path, query, header, o cookie) con su tipo y descripción.
4.  **Respuestas:**
    * Para cada operación, definir al menos dos códigos de respuesta HTTP (ej. 200/201 para éxito, 400/404 para error).
    * Especificar el contenido del cuerpo de la respuesta (`content`) usando media type (e.g., `application/json`) y referenciando los esquemas definidos en `components/schemas`.

### Herramientas Recomendadas
* **Editor en línea:** [Swagger Editor](https://editor.swagger.io/)
* **Herramientas locales:** VS Code con extensiones de YAML/OpenAPI.
* **Herramientas alternas:** Puede usar cualquier herramienta que gusten.

### Entrega
Entregar el archivo `.yaml`

**NO entregan** código que implementen endpoints, solo archivo con especificación (.yaml)

Si usa algún BaaS o similar para su proyecto, **revise la documentación REST para la plataforma seleccionada** y con base en esto puede generar su archivo .yaml para los endpoints, cumpliendo con la rúbrica marcada.

***

## Ejemplos
En este mismo repositorio, este es un archivo ejemplo [jedis.yaml](jedis.yaml).
Además, en este archivo [JedisAPI](JedisAPI.md) puede encontrar la implementación de dicho contrato de API. 

## Rúbrica de Evaluación

| Criterio                                            | Peso (%) | Excelente (4)                                                                                                                         | Competente (3)                                                                                                                     | Básico (2)                                                                                                        | Insuficiente (1)                                                                  |
|-----------------------------------------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| **Completitud de la Especificación**                | 30%      | Define 10+ endpoints con al menos 3 verbos HTTP. Incluye todos los objetos requeridos (`info`, `servers`, `paths`, `schemas`).        | Define 8-9 endpoints y usa 2-3 verbos. Falta uno de los objetos menores (`servers` o `contact`).                                   | Define 5-7 endpoints. Uso limitado a 1-2 verbos HTTP. Faltan varios objetos clave o secciones.                    | Menos de 5 endpoints definidos o el archivo está incompleto/no es válido.         |
| **Definición de Esquemas (`components/schemas`)**   | 30%      | Modelos de datos (3+ esquemas) son detallados, usan tipos correctos y descripciones                                                   | Los modelos son correctos (2-3 esquemas) y usan `$ref`, pero carecen de descripciones o detalles de formato.                       | Solo se definen 1-2 esquemas simples.                                                                             | Ausencia de la sección de esquemas o la definición es incorrecta y no utilizable. |
| **Claridad del Contrato (Parámetros y Respuestas)** | 25%      | Todas las operaciones tienen parámetros bien definidos y al menos 2 códigos de respuesta detallados, referenciando esquemas de datos. | La mayoría de las operaciones tienen 2 respuestas y parámetros, pero algunas referencias a esquemas son incorrectas o incompletas. | La definición de respuestas es superficial (solo códigos de estado). Los parámetros son vagos o solo usan `path`. | La API no tiene definidas las respuestas ni los parámetros de manera funcional.   |
| **Adherencia al Estándar y Seguridad**              | 15%      | El archivo es 100% **válido** según OAS, utiliza la sintaxis correcta (YAML/JSON)                                                     | El archivo es válido, pero presenta errores menores de sintaxis.                                                                   | El archivo presenta errores de validación mayores.                                                                | La especificación no es válida y no se adhiere a la estructura OpenAPI.           |
