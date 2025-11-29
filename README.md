# Content API

Microservicio Content API para manejo de contenido musical:
canciones, playlists, colecciones (álbumes, EPs, singles), historial, likes, plays y popularidad.

Construido con FastAPI (Python) y MongoDB, con soporte para:
	•	Lanzamientos programados (release dates futuras)
	•	Métricas permanentes de reproducción
	•	Popularidad basada en múltiples señales (plays, likes, saves, shares)
	•	Sincronización de base remota → local para desarrollo

⸻

# Índice
1. [Stack y decisiones de diseño](#-stack-y-decisiones-de-diseño)

2. [Configuración y Ejecución](#️-configuración-y-ejecución)
   1. [Modo Local con base de datos local (PostgreSQL para pruebas + Mongo local)](#1-modo-local-con-base-de-datos-local-postgresql-para-pruebas--mongo-local)
   2. [Modo Remoto (conectar a DB remota)](#2-modo-remoto-conectar-a-db-remota)
   3. [Variables de Entorno](#-variables-de-entorno)

3. [📍 Rutas Principales (visión general)](#-rutas-principales-visión-general)

4. [Autenticación](#-autenticación)

5. [Testing](#-testing)

6. [Ejecutar](#-ejecutar)

7. [Sistema de Métricas de Reproducción](#-sistema-de-métricas-de-reproducción)
   1. [Sistema de Lanzamientos Programados](#-sistema-de-lanzamientos-programados)
   2. [Sistema de Popularidad Mejorado](#-sistema-de-popularidad-mejorado)

⸻

Si querés, puedo autogenerarte todas las secciones completas del README siguiendo este índice.

# 🧱 Stack y decisiones de diseño

### ¿Por qué Python + FastAPI?
	•	Velocidad de desarrollo: el equipo ya conoce Python, lo que permitió enfocarse en modelar el dominio (canciones, playlists, colecciones) sin curva de aprendizaje extra.
	•	FastAPI:
	•	Tipado fuerte y validación con Pydantic
	•	Documentación automática (/docs y /openapi.json)
	•	Manejo sencillo de dependencias (e.g. verify_token)
	•	Ecosistema sólido: fácil integración con otros servicios (user-api, player-api, etc.) y herramientas de testing (pytest, testcontainers).

### ¿Por qué MongoDB?
	•	Modelo flexible: álbumes, singles, playlists, colecciones y métricas tienen estructuras que evolucionan rápido. Documentos JSON en Mongo encajan muy bien sin migraciones complejas.
	•	Consultas ricas: facilita traer toda la información de una colección (metadatos + canciones + métricas) en una sola consulta.
	•	Escalabilidad: replica sets y sharding nativo para crecer con el volumen de reproducciones.
	•	Integración con Python: pymongo y herramientas de admin (Atlas) simplifican la operación.

⸻

## ✅ Requisitos
	•	Docker y Docker Compose
	•	Python 3.9+ (para desarrollo local y testing sin Docker)
	•	Make (para usar los comandos abreviados)

⸻

# ⚙️ Configuración y Ejecución

## 1. Modo Local con base de datos local (PostgreSQL para pruebas + Mongo local)

Para desarrollo y testing con la base local definida en el repo:

### Construir y levantar servicios (API + PostgreSQL local)
* make up-local 
* make down-local


Esta configuración:
	•	Levanta un contenedor PostgreSQL con credenciales predefinidas
	•	Inicializa la DB con src/db/init.sql (donde aplique)
	•	Expone la API en http://localhost:8080
	•	Expone PostgreSQL en localhost:5432
	•	MongoDB local (si está definido en tu docker-compose-local.yaml) se usa como datastore principal de contenido.

## 2. Modo Remoto (conectar a DB remota)

Para conectar la API a una base remota (ej. Mongo Atlas + Postgres remoto):

### Crear .env a partir del ejemplo
	cp .env.example .env

### Levantar solo la API, apuntando a DB remotas
* make up-remote
* make down-remote


⸻

## 🌍 Variables de Entorno

Para configuración remota (Postgres) se usan variables como:

	DATABASE_HOST=your_remote_host
	DATABASE_NAME=your_database_name
	DATABASE_PORT=5432
	DATABASE_USER=your_username
	DATABASE_PASSWORD=your_password
	DATABASE_SSLMODE=require

Para MongoDB usualmente se usa un DATABASE_URL / MONGODB_URI en el .env (definido en Notion).

📝 Las credenciales reales (remotas) se documentan en Notion y no viven en el repo.

⸻

# 📍 Rutas Principales (visión general)

La documentación completa de endpoints se puede consultar en
http://localhost:8080/docs (Swagger UI) una vez levantada la API.

Principales “bloques” funcionales:

###	•	Songs
	•	GET /songs → Lista de canciones
	•	POST /songs → Crear canción
###	•	Playlists
	•	GET /playlists
	•	POST /playlists
	•	POST /playlists/{playlist_id}/songs/{song_id}
###	•	Collections (álbumes, EPs, singles)
	•	POST /collections → Crear colección (soporta releaseDate futura)
	•	GET /collections (con filtros por tipo, artista, etc.)
	•	GET /collections/{collection_id}
	•	GET /collections/popular/{artistId} → colecciones ordenadas por popularidad
	•	POST /collections/{collection_id}/publish → publicación inmediata
###	•	History & Plays
	•	POST /history → registrar reproducción
	•	GET /history → historial del usuario
	•	DELETE /history → limpiar historial
	•	Likes / Shares / Saves
	•	likes y shares se registran a nivel canción; playlist saves impactan en popularidad de colecciones

Ejemplos rápidos (supuestos):
#### Obtener canciones
	curl -s http://localhost:8080/songs

#### Crear playlist simple
	curl -X POST http://localhost:8080/playlists \
	  -H "Content-Type: application/json" \
	  -H "Authorization: Bearer <JWT_USER>" \
	  -d '{
	    "name": "Mi Playlist",
	    "description": "Hecha con Content API"
	  }'

#### Ver colecciones populares de un artista
	curl -s http://localhost:8080/collections/popular/<artistId>


⸻

# 🔐 Autenticación

La Content API usa un mecanismo de autenticación similar al resto de Melodia:

•	Dependencia verify_token en los endpoints que requieren usuario autenticado.
•	JWT consumido desde Authorization: Bearer <token>.

Reglas importantes:

•	Endpoints de usuario final (ej. /history, /playlists, likes, etc.) se consumen con token de listener.
•	Endpoints de artista (ej. POST /collections) requieren que el usuario tenga stage_name → si el JWT corresponde a un listener, la API responde:

```
{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "User is not an artist",
  "instance": "/collections"
}
```


⸻

# 🧪 Testing

Tests con testcontainers

Los tests usan testcontainers para montar un contenedor de PostgreSQL temporal:

### Instalar dependencias de testing
pip install -r requirements-tests.txt

### Ejecutar tests
make test

## Desarrollo Local (sin Docker)

### Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-tests.txt

#### Levantar solo PostgreSQL local
docker compose -f docker-compose-local.yaml up postgres -d

### Configurar envs para apuntar a Postgres local
```
export DATABASE_HOST=localhost
export DATABASE_NAME=postgres
export DATABASE_PORT=5432
export DATABASE_USER=postgres
export DATABASE_PASSWORD=password
export DATABASE_SSLMODE=disable
```

# Ejecutar API
python src/main.py   # → http://localhost:8080


⸻

# 🎧 Sistema de Métricas de Reproducción

Arquitectura de dos colecciones (MongoDB)

Para separar historial de usuario de métricas permanentes se usan dos colecciones:

1.	History

	•	Historial personal (por usuario)

	•	El usuario lo puede limpiar (DELETE /history)

	•	Usado para “Escuchado recientemente”
2.	Plays

	•	Métrica permanente de reproducciones

	•	Nunca se elimina (aunque el usuario limpie su historial)

	•	Usado para popularidad, analytics y métricas de artistas

### Flujo típico:

POST /history
  → inserta en history
  → inserta en plays

DELETE /history
  → borra entradas en history
  → NO toca plays

### Índices recomendados en Mongo

  db.plays.createIndex({ "song_id": 1 });

  db.plays.createIndex({ "user_id": 1, "played_at": -1 });

  db.plays.createIndex({ "song_id": 1, "played_at": -1 });

**Esto optimiza:**

•	Consultas por canción (popularidad)

•	Consultas por usuario (historial reciente)

•	Agregaciones por período (played_at)

⸻

## ⏰ Sistema de Lanzamientos Programados

Las colecciones (album/EP/single) soportan releaseDate:

	•	Si releaseDate no se envía → la colección se considera publicada desde “ahora”.
	•	Si releaseDate es futura → la colección queda “programada” (no pública por defecto).

### Comportamiento de visibilidad
•	GET /collections → por defecto solo colecciones publicadas (releaseDate ≤ now).

•	includeUnpublished=true permite incluir colecciones no publicadas, ej.:
```
GET /collections/?includeUnpublished=true
GET /collections/{collection_id}?includeUnpublished=true
GET /collections/popular/{artistId}?includeUnpublished=true
```
Publicación inmediata

Para adelantar un lanzamiento programado:

POST /collections/{collection_id}/publish

#### Respuestas típicas:

	•	200 OK – Colección publicada
	•	400 Bad Request – Ya estaba publicada
	•	403 Forbidden – Usuario no es el propietario / artista
	•	404 Not Found – Colección inexistente

⸻

## ⭐ Sistema de Popularidad Mejorado

El endpoint:

**GET /collections/popular/{artistId}**
Calcula popularidad de colecciones combinando múltiples métricas:

	•	Plays (reproducciones) – peso 1.0
	•	Likes – peso 2.0
	•	Playlist Saves – peso 3.0
	•	Shares – peso 5.0

Las métricas se agregan a nivel de colección sumando todas las canciones que pertenecen a esa colección.

Respuesta típica:

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
      "songs": [ /* ... */ ]
    }
  ]
}
