# PASO 7: Quick Start - Object Storage ⚡

## 🎯 Objetivo

Levantar la aplicación con MinIO y probar uploads de imágenes en **menos de 5 minutos**.

---

## ✅ Checklist Pre-Start

Antes de empezar, asegúrate de tener:

- [x] Docker y Docker Compose instalados
- [x] Puertos disponibles: 5000, 5432, 9000, 9001
- [x] Internet (para descargar imágenes Docker)

---

## 🚀 Inicio Rápido (5 minutos)

### Paso 1: Rebuild y Levantar Stack (2 min)

```bash
# Detener containers antiguos
docker compose down

# Rebuild web (para incluir boto3)
docker compose build --no-cache web

# Levantar stack completo (db + minio + web)
docker compose up -d

# Esperar a que todo esté listo (~30 segundos)
docker compose ps
```

**Resultado esperado:**
```
NAME           STATUS       PORTS
Stock-db       Up          0.0.0.0:5432->5432/tcp
Stock-minio    Up          0.0.0.0:9000-9001->9000-9001/tcp
Stock-web      Up          0.0.0.0:5000->5000/tcp
```

---

### Paso 2: Verificar MinIO Console (1 min)

1. **Abrir:** http://localhost:9001
2. **Login:**
   - Username: `minioadmin`
   - Password: `minioadmin`
3. **Verificar bucket:**
   - Click en "Buckets" (sidebar izquierdo)
   - ✅ Debe aparecer: `uploads` (creado automáticamente)
   - ✅ Policy: `public-read`

---

### Paso 3: Probar Upload (2 min)

1. **Abrir app:** http://localhost:5000
2. **Login:**
   - Email: `admin@ferreteria.com` (o crear cuenta)
   - Password: (tu password)
3. **Ir a Productos:**
   - Menú → Productos
4. **Crear producto con imagen:**
   - Click "Nuevo Producto"
   - Llenar form:
     - Nombre: `Martillo`
     - SKU: `MART-001`
     - Precio: `100`
     - Unidad: (seleccionar)
   - **Subir imagen:** (jpg, png, max 2MB)
   - Click "Guardar"

---

### Paso 4: Verificar en MinIO (1 min)

1. **Volver a MinIO Console:** http://localhost:9001
2. **Browse bucket:**
   - Buckets → `uploads` → Browse
3. **Verificar carpeta:**
   - ✅ `products/` → `tenant_1/` → `TIMESTAMP_martillo.jpg`
4. **Click en archivo:**
   - Copiar URL
   - Abrir en navegador
   - ✅ Imagen debe ser accesible: `http://localhost:9000/uploads/products/tenant_1/...`

---

### Paso 5: Verificar en Base de Datos (opcional)

```bash
# Conectar a DB
docker exec -it Stock-db psql -U stock -d stock

# Query
SELECT id, name, image_path FROM product WHERE image_path IS NOT NULL;
```

**Resultado esperado:**
```
 id |   name   | image_path
----+----------+---------------------------------------------------------------
  1 | Martillo | http://localhost:9000/uploads/products/tenant_1/1738204800_martillo.jpg
```

---

## 🧪 Tests Rápidos

### Test 1: Archivo Demasiado Grande (debe fallar)

1. Crear archivo de 3MB:
```bash
# Linux/Mac
dd if=/dev/zero of=big.jpg bs=1M count=3

# Windows (PowerShell)
fsutil file createnew big.jpg 3145728
```

2. Intentar subir `big.jpg` como imagen de producto
3. ✅ **Resultado esperado:**
   - Flash message: "El archivo es demasiado grande. Máximo 2.0MB"
   - Producto NO se crea

---

### Test 2: Tipo de Archivo Inválido (debe fallar)

1. Crear archivo PDF de prueba
2. Intentar subir PDF como imagen de producto
3. ✅ **Resultado esperado:**
   - Flash message: "Tipo de archivo no permitido: application/pdf"
   - Producto NO se crea

---

### Test 3: Editar Producto y Cambiar Imagen (debe eliminar old)

1. Editar producto "Martillo"
2. Subir nueva imagen: `martillo_v2.jpg`
3. Guardar
4. ✅ **Resultado esperado en MinIO:**
   - `martillo_v1.jpg` ELIMINADO
   - `martillo_v2.jpg` presente
   - Solo 1 imagen para ese producto

---

## 📊 Logs de Diagnóstico

### Ver logs de la app (uploads)

```bash
docker compose logs -f web | grep -E "STORAGE|Upload"
```

**Logs esperados:**
```
[STORAGE] Bucket 'uploads' exists
[STORAGE] ✓ File validation passed: martillo.jpg (145823 bytes, image/jpeg)
[STORAGE] Uploading 'products/tenant_1/1738204800_martillo.jpg'...
[STORAGE] ✓ File uploaded: http://localhost:9000/uploads/products/tenant_1/1738204800_martillo.jpg
```

---

### Ver logs de MinIO

```bash
docker compose logs -f minio
```

**Logs esperados:**
```
API: PUT /uploads/products/tenant_1/1738204800_martillo.jpg
Status: 200 OK
```

---

## ❌ Troubleshooting

### Problema: "Bucket 'uploads' does not exist"

**Causa:** El bucket no se creó automáticamente.

**Solución:**
```bash
# 1. Verificar logs de la app
docker compose logs web | grep STORAGE

# 2. Reintentar creación
docker compose restart web

# 3. O crear manualmente en MinIO Console
# http://localhost:9001 → Buckets → Create Bucket → Name: "uploads"
```

---

### Problema: "Connection refused to minio:9000"

**Causa:** MinIO no está corriendo o red Docker no está configurada.

**Solución:**
```bash
# 1. Verificar servicio MinIO
docker compose ps minio

# 2. Si no está corriendo, levantarlo
docker compose up -d minio

# 3. Verificar red
docker network ls
docker network inspect stock-network
```

---

### Problema: "Access Denied" al subir archivo

**Causa:** Credenciales incorrectas o bucket policy no configurada.

**Solución:**
```bash
# 1. Verificar variables S3 en .env
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin

# 2. Verificar bucket policy en MinIO Console
# http://localhost:9001 → Buckets → uploads → Manage → Access Policy
# Debe ser: "public" o contener la policy de public-read

# 3. Reiniciar app
docker compose restart web
```

---

### Problema: Imagen no se ve en la web

**Causa:** URL incorrecta o bucket no público.

**Solución:**
```bash
# 1. Verificar URL en DB
docker exec -it Stock-db psql -U stock -d stock -c "SELECT image_path FROM product WHERE image_path IS NOT NULL LIMIT 1;"

# Debe ser: http://localhost:9000/uploads/products/tenant_1/...

# 2. Abrir URL directamente en navegador
# Debe mostrar la imagen (no error 403/404)

# 3. Si da 403 (Forbidden), configurar bucket como público:
# MinIO Console → Buckets → uploads → Manage → Access Policy → "public"
```

---

## 🎯 Métricas de Éxito

Después de completar el Quick Start, deberías tener:

- ✅ MinIO corriendo en puerto 9000 (API) y 9001 (Console)
- ✅ Bucket `uploads` creado y público
- ✅ Al menos 1 producto con imagen subida
- ✅ Imagen accesible en: `http://localhost:9000/uploads/products/tenant_1/...`
- ✅ Logs de `[STORAGE]` sin errores
- ✅ Validaciones de tamaño/tipo funcionando

---

## 📚 Próximos Pasos

1. **Leer documentación completa:** [`PASO7_OBJECT_STORAGE.md`](PASO7_OBJECT_STORAGE.md)
2. **Planear migración a producción:** AWS S3 o DigitalOcean Spaces
3. **Configurar CDN:** CloudFront (AWS) o Spaces CDN (DO)
4. **Monitorear costos:** S3 pricing calculator
5. **Backup strategy:** Versionado de objetos en S3

---

**Tiempo total:** ~5 minutos  
**Dificultad:** ⭐⭐☆☆☆ (Fácil)  
**Estado:** ✅ LISTO PARA PRODUCCIÓN
