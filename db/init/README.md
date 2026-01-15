# Database Initialization Scripts

Este directorio contiene scripts SQL que se ejecutan **automáticamente** cuando el contenedor de PostgreSQL se inicia por primera vez.

## ⚠️ Importante

- Los scripts solo se ejecutan en la **primera inicialización** del volumen `postgres_data`
- Si el volumen ya existe, los scripts **NO se ejecutarán** de nuevo
- Para re-ejecutar los scripts, debes eliminar el volumen: `docker compose down -v`

## 📁 Estructura

Los archivos se ejecutan en orden alfabético:
- `001_schema.sql` - Esquema de la base de datos (tablas, índices, constraints)
- `002_seeds.sql` - Datos iniciales (opcional)

## 🚀 Uso

### Opción 1: Esquema ya existe en la base de datos

Si ya tienes la base de datos configurada y solo quieres ejecutar la aplicación:
- Deja esta carpeta vacía
- Conéctate a la base de datos existente configurando `.env` con las credenciales correctas

### Opción 2: Inicializar base de datos desde cero

Si quieres que Docker cree el esquema automáticamente:

1. **Obtener el esquema SQL:**
   - Desde pgAdmin: Tools → Backup → Format "Plain" → Solo esquema
   - Desde psql: `pg_dump -U usuario -d ferreteria --schema-only > schema.sql`
   - O usar el DDL que ya tengas

2. **Colocar el esquema:**
   - Copiar el archivo SQL a esta carpeta como `001_schema.sql`
   - Si tienes seeds/datos iniciales, créalos como `002_seeds.sql`

3. **Iniciar Docker:**
```bash
docker compose up --build
```

## 📝 Ejemplo de 001_schema.sql

```sql
-- Crear extensiones
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Crear tipos enum
CREATE TYPE invoice_status AS ENUM ('PENDING', 'PAID');
CREATE TYPE ledger_type AS ENUM ('INCOME', 'EXPENSE');
-- ... más tipos

-- Crear tablas
CREATE TABLE uom (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ... más tablas
```

## 🔄 Reiniciar desde Cero

Si necesitas reiniciar la base de datos:

```bash
# Detener y eliminar volúmenes
docker compose down -v

# Iniciar de nuevo (ejecutará los scripts)
docker compose up --build
```

## 📖 Más Información

Ver el README principal del proyecto para instrucciones completas.

