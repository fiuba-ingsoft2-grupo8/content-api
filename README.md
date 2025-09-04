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
