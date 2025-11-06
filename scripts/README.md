# Scripts de Utilidad

Esta carpeta contiene scripts auxiliares para el mantenimiento de la base de datos.

## 📦 copy_db.py

Script para copiar todos los datos desde la base de datos remota (MongoDB Atlas) a la base de datos local.

### Requisitos previos

1. La base de datos local debe estar corriendo:
   ```bash
   make up-local
   ```

2. El archivo `.env` debe tener configurada la variable `DATABASE_URL` con la conexión a MongoDB Atlas.

### Uso

```bash
# Opción 1: Usar Make (recomendado)
make copy

# Opción 2: Ejecutar directamente
python scripts/copy_db.py
```

### ¿Qué hace?

1. Se conecta a la base de datos remota (MongoDB Atlas)
2. Se conecta a la base de datos local (Docker)
3. Copia todas las colecciones:
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

4. **Importante**: Antes de copiar cada colección, elimina su contenido local (drop) para evitar duplicados.

### Configuración

Las URLs de conexión están configuradas en el script:

- **Remota**: Lee de `DATABASE_URL` en `.env`
- **Local**: `mongodb://admin:admin_password@localhost:27017/userdb?authSource=admin`

Si necesitas cambiar la URL local, edita la variable `LOCAL_URL` en el script.

### Ejemplo de salida

```
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

## ⚠️ Advertencias

- **Este script BORRA los datos existentes en la base de datos local** antes de copiar.
- No lo ejecutes si tienes cambios locales que quieras conservar.
- Solo copia datos, no copia índices ni configuraciones especiales de MongoDB.

