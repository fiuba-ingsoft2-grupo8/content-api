# Content API

## Requisitos

- Docker y Docker Compose
- Python 3.9+ (para desarrollo local y testing)
- Make

## Configuración del Proyecto

### 1. Configuración con Base de Datos Local

Para desarrollo y testing con una base de datos PostgreSQL local:

```bash
# Construir y levantar los servicios (API + PostgreSQL local)
make up-local

# Para parar los servicios
make down-local
```

Esta configuración:
- Levanta un contenedor PostgreSQL con credenciales predefinidas
- Inicializa la base de datos con el script `src/db/init.sql`
- La API estará disponible en `http://localhost:8080`
- PostgreSQL estará disponible en `localhost:5432`

### 2. Configuración con Base de Datos Remota

Para conectar a una base de datos PostgreSQL remota:

```bash
# Crear archivo .env con las variables necesarias (ver sección de Variables de Entorno)
cp .env.example .env

# Construir y levantar solo la API
make up-remote

# Para parar el servicio
make down-remote
```

Esta configuración solo levanta el contenedor de la API y se conecta a la base de datos especificada en las variables de entorno.

## Variables de Entorno

Para la configuración remota, crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
DATABASE_HOST=your_remote_host
DATABASE_NAME=your_database_name
DATABASE_PORT=5432
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password
DATABASE_SSLMODE=require
```

**📝 Nota:** Las credenciales de las bases de datos remotas están disponibles en Notion.

## Justificación del stack utilizado

### ¿Por qué Python?

Se eligió Python para la parte de gestión del contenido por ventajas como:

- Facilidad y rapidez: ya es un lenguaje muy conocido por el equipo, lo que nos permitió empezar a desarrollar sin tener que invertir tiempo en aprender algo nuevo. Esto hizo que pudiéramos enfocarnos directamente en la lógica del servicio.

- Ecosistema backend sólido: con frameworks como FastAPI es sencillo armar una API REST bien estructurada y con buen soporte de documentación, validación y testing.

- Sintaxis clara y legible: escribir en Python es simple, y eso acelera el prototipado y facilita hacer cambios frecuentes durante el desarrollo.

- Integración sencilla: Python se conecta fácilmente con distintos motores de base de datos y con otros servicios, lo que nos da flexibilidad para adaptar esta parte del sistema al resto del stack.

### ¿Por qué MongoDB?

En cuanto al almacenamiento, elegimos MongoDB por las siguientes razones:

- Modelo flexible para colecciones: álbumes, singles y playlists pueden variar en estructura, tamaño y atributos. En MongoDB esto se representa naturalmente con documentos JSON, sin necesidad de un esquema fijo, lo que permite adaptabilidad y polimorfismo en el modelo de datos.

- Consultas prácticas: permite traer toda la información del contenido en una sola consulta, reduciendo la complejidad en el backend.

- Facilidad de evolución: si en el futuro se agregan nuevos campos, el modelo se puede extender sin migraciones complejas.

- Escalabilidad natural: ofrece particionamiento y replicación nativos, lo que facilita crecer horizontalmente en escenarios con más usuarios o mayor volumen de datos.

- Compatibilidad con Python: librerías como pymongo hacen que la integración sea directa y sin necesidad de configuraciones complejas.


## Documentación
Para correr la documentación se utiliza en este repositorio FastAPI, por lo que para ver información sobre los endpoints, basta con acceder a la documentación de localhost. Pasos:
```bash
# Levantar Docker local
make-up local

# Correr el servicio
python src/main.py

# Acceder por buscador a la FastAPI
localhost:8080/docs
```

## Testing

### Configuración para Tests

Los tests utilizan `testcontainers` para crear un contenedor PostgreSQL temporal durante la ejecución:

```bash
# Instalar dependencias de testing
pip install -r requirements-tests.txt

# Ejecutar tests
make test
```

### Desarrollo Local

Para desarrollo local sin Docker:

```bash
# Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-tests.txt

# Levantar solo PostgreSQL
docker compose -f docker-compose-local.yaml up postgres -d

# Ejecutar la API localmente
export DATABASE_HOST=localhost
export DATABASE_NAME=postgres
export DATABASE_PORT=5432
export DATABASE_USER=postgres
export DATABASE_PASSWORD=password
export DATABASE_SSLMODE=disable

python src/main.py
```

---


# Arquitectura del proyecto:
El proyecto sigue una arquitectura simple pero robusta, pensada para facilitar el desarrollo, la escalabilidad y el testing. Las principales decisiones tecnológicas son:

---
#### Python (FastAPI):
Se eligió Python como lenguaje base por su ecosistema maduro en el desarrollo de APIs, facilidad de integración con librerías de testing y data, y su curva de aprendizaje accesible. En particular, FastAPI permite construir endpoints de manera rápida y con tipado estático, lo que mejora la mantenibilidad y genera automáticamente documentación interactiva en /docs.


#### MongoDB:
Se utiliza MongoDB como base de datos NoSQL para aprovechar su flexibilidad en el manejo de documentos JSON, lo que se adapta muy bien al tipo de datos semiestructurados que maneja la API. A diferencia de un esquema rígido como PostgreSQL, MongoDB permite iterar rápidamente sobre el modelo de datos sin necesidad de migraciones complejas, lo cual resulta útil en un entorno académico y de experimentación.


#### Docker y Docker Compose:
Se emplea contenedorización para asegurar que el proyecto corra en cualquier entorno de manera consistente, reduciendo problemas de configuración local y facilitando el despliegue.

---

Esta combinación de tecnologías proporciona un balance entre velocidad de desarrollo, flexibilidad de datos y portabilidad del entorno, asegurando que tanto en etapas de aprendizaje como de producción el sistema se mantenga estable y fácil de extender.

