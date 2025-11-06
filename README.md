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

## Sistema de Métricas de Reproducción

### Arquitectura de Dos Tablas

El sistema utiliza dos colecciones separadas en MongoDB para gestionar reproducciones:

1. **`history`** - Historial personal del usuario
   - Contiene el historial de reproducción de cada usuario
   - Puede ser limpiado por el usuario (DELETE /history)
   - Usado para mostrar "Escuchado recientemente"

2. **`plays`** - Métricas permanentes
   - Almacena todas las reproducciones de forma permanente
   - NUNCA se elimina, ni siquiera cuando el usuario limpia su historial
   - Usado para calcular popularidad, métricas de artistas y analytics

### Flujo de Reproducción

Cuando un usuario reproduce una canción (POST /history):
```
1. Se registra en `history` (historial personal)
2. Se registra en `plays` (métrica permanente)
```

Cuando un usuario limpia su historial (DELETE /history):
```
1. Se elimina de `history` ✓
2. Se mantiene en `plays` ✓
```

### Índices Recomendados

Para optimizar el rendimiento, ejecuta el script de índices:

```bash
docker exec -it mongodb mongosh userdb /docker-entrypoint-initdb.d/mongo-indexes.js
```

O manualmente:
```bash
docker exec -it mongodb mongosh -u admin -p admin_password --authenticationDatabase admin userdb
```

```javascript
db.plays.createIndex({ "song_id": 1 });
db.plays.createIndex({ "user_id": 1, "played_at": -1 });
db.plays.createIndex({ "song_id": 1, "played_at": -1 });
```

### Migración de Datos Existentes

Si tienes datos existentes en `history` que quieres preservar en `plays`:

```javascript
db.history.find().forEach(function(doc) {
    db.plays.insert({
        user_id: doc.userId,
        song_id: doc.songId,
        played_at: doc.playedAt
    });
});
```

Para más detalles, consulta [MIGRATION_NOTES.md](./MIGRATION_NOTES.md)

## Sistema de Lanzamientos Programados

### Descripción

Las colecciones (álbumes, singles, EPs) ahora soportan lanzamientos programados. Esto permite a los artistas crear colecciones con una fecha de lanzamiento futura, manteniéndolas ocultas hasta que llegue esa fecha.

### Características

1. **Fecha de lanzamiento opcional**
   - Al crear una colección, puedes especificar un campo `releaseDate`
   - Si no se especifica, la colección se publica inmediatamente (fecha = ahora)
   - Las colecciones con fecha futura no son visibles por defecto

2. **Control de visibilidad**
   - Por defecto, solo las colecciones publicadas (releaseDate ≤ ahora) son visibles
   - Parámetro `includeUnpublished=true` permite ver colecciones no publicadas
   - Aplica a todos los endpoints de obtención de colecciones

3. **Publicación anticipada**
   - Endpoint especial para publicar una colección inmediatamente
   - Solo el artista propietario puede publicar su colección
   - No se puede "despublicar" una colección ya lanzada

### Endpoints Actualizados

#### Crear colección con fecha de lanzamiento
```bash
POST /collections/
{
  "name": "Mi Nuevo Álbum",
  "type": "album",
  "songIds": ["song_id_1", "song_id_2"],
  "releaseDate": "2025-12-31T00:00:00Z"  # Opcional
}
```

#### Obtener colecciones (solo publicadas por defecto)
```bash
GET /collections/
GET /collections/?type=album
GET /collections/?artistId=artist_123
GET /collections/{collection_id}
GET /collections/popular/{artistId}
```

#### Obtener colecciones incluyendo no publicadas
```bash
GET /collections/?includeUnpublished=true
GET /collections/{collection_id}?includeUnpublished=true
GET /collections/popular/{artistId}?includeUnpublished=true
```

#### Publicar colección inmediatamente
```bash
POST /collections/{collection_id}/publish
```

Responde con:
- `200 OK` - Colección publicada exitosamente
- `400 Bad Request` - Colección ya está publicada
- `403 Forbidden` - No eres el propietario de la colección
- `404 Not Found` - Colección no encontrada

### Casos de Uso

**Artista programa un lanzamiento:**
```bash
# 1. Crear colección con fecha futura
POST /collections/
{
  "name": "Summer Hits 2025",
  "type": "album",
  "songIds": [...],
  "releaseDate": "2025-06-21T00:00:00Z"
}

# 2. Verificar que no es visible públicamente
GET /collections/  # No aparece

# 3. Verificar como artista (con includeUnpublished)
GET /collections/?includeUnpublished=true  # Sí aparece

# 4. Publicar anticipadamente si es necesario
POST /collections/{collection_id}/publish
```

### Tests

Se agregaron 12 tests completos que cubren:
- ✅ Creación de colecciones con fecha futura
- ✅ Creación de colecciones sin fecha (publicación inmediata)
- ✅ Visibilidad de colecciones no publicadas
- ✅ Filtrado con parámetro includeUnpublished
- ✅ Publicación inmediata de colecciones
- ✅ Validación de permisos de publicación
- ✅ Colecciones con fechas pasadas (ya publicadas)
- ✅ Endpoints populares con/sin includeUnpublished

Ejecutar tests:
```bash
# Todos los tests de colecciones
pytest tests/test_collections_controller.py -v

# Solo tests de lanzamientos programados
pytest tests/test_collections_controller.py -k "release_date or unpublished or publish" -v
```

## Sistema de Popularidad Mejorado

### Descripción

El endpoint `/collections/popular/{artistId}` ahora calcula la popularidad usando múltiples métricas en lugar de solo reproducciones:

### Métricas Consideradas

1. **Plays** (reproducciones) - peso: 1.0
2. **Likes** (me gusta) - peso: 2.0
3. **Playlist Saves** (guardado en playlists) - peso: 3.0
4. **Shares** (compartidos) - peso: 5.0

### Fórmula de Popularidad

```python
popularityScore = (
    totalPlays * 1.0 +
    totalLikes * 2.0 +
    totalPlaylistSaves * 3.0 +
    totalShares * 5.0
)
```

Los pesos reflejan el valor relativo de cada acción:
- **Plays**: acción pasiva, menor peso
- **Likes**: indica interés moderado
- **Playlist Saves**: indica alto interés (quiere volver a escuchar)
- **Shares**: máximo valor (potencial viral, recomienda a otros)

### Respuesta del Endpoint

```json
GET /collections/popular/{artistId}

{
  "data": [
    {
      "id": "collection_id",
      "name": "Álbum Popular",
      "artistId": "artist_123",
      "artistName": "Artista",
      "type": "album",
      "totalPlays": 1500,
      "totalLikes": 234,
      "totalPlaylistSaves": 89,
      "totalShares": 45,
      "popularityScore": 2443.0,
      "songs": [...]
    }
  ]
}
```

### Notas Importantes

- Las métricas se calculan sumando los valores de **todas las canciones** de la colección
- Los likes son a nivel de canción, no de colección
- Las colecciones se ordenan por `popularityScore` descendente
- Los pesos pueden ajustarse según las necesidades del negocio

## 📦 Copiar Base de Datos Remota a Local

### Descripción

Script de utilidad para copiar todos los datos desde la base de datos remota (MongoDB Atlas) a la base de datos local. Útil para:
- Desarrollo con datos reales
- Testing con datos de producción
- Depuración de problemas
- Sincronización de entornos

### Uso

```bash
# 1. Asegurarse que la base de datos local esté corriendo
make up-local

# 2. Copiar datos desde remoto
make copy
```

### ¿Qué hace el comando?

1. ✅ Se conecta a la base de datos remota (usando `DATABASE_URL` del `.env`)
2. ✅ Se conecta a la base de datos local (Docker)
3. ✅ Copia todas las colecciones:
   - songs
   - playlists
   - playlist_songs
   - collections
   - collection_songs
   - likes
   - shares
   - plays
   - history
   - artist_about

4. ⚠️ **Importante**: Elimina el contenido local de cada colección antes de copiar

### Ejemplo de Salida

```
📦 Copying database from remote to local...
⚠️  Make sure your local MongoDB is running first!

============================================================
  📦 MongoDB Database Copy Tool
  Remote → Local
============================================================

🔌 Connecting to databases...
✅ Connected to REMOTE database: mongodb+srv://...
✅ Connected to LOCAL database: mongodb://admin:admin_password@localhost:27017/...

📋 Starting copy process...

  ✅ songs: Copied 150 documents
  ✅ playlists: Copied 45 documents
  ✅ playlist_songs: Copied 320 documents
  ✅ collections: Copied 25 documents
  ✅ collection_songs: Copied 180 documents
  ✅ likes: Copied 500 documents
  ✅ shares: Copied 120 documents
  ✅ plays: Copied 2500 documents
  ⚠️  history: No documents found (skipping)
  ✅ artist_about: Copied 10 documents

============================================================
  ✨ Copy completed successfully!
  Total documents copied: 3850
============================================================
```

### ⚠️ Advertencias

- **Este script BORRA los datos existentes en la base de datos local** antes de copiar
- No lo ejecutes si tienes cambios locales que quieras conservar
- Solo copia datos, no copia índices ni configuraciones especiales de MongoDB

Para más detalles, consulta [scripts/README.md](./scripts/README.md)
