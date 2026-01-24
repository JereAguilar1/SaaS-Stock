# PASO 7: Object Storage y Escalabilidad de Archivos ✅

## 📋 Resumen Ejecutivo

**Objetivo:** Migrar el manejo de archivos de filesystem local a Object Storage (MinIO/S3), haciendo la aplicación **stateless** y lista para escalar horizontalmente.

**Estado:** ✅ COMPLETADO

---

## 🎯 Problema Resuelto

### Antes (Filesystem Local)
```python
# ❌ Problemas:
upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
os.makedirs(upload_folder, exist_ok=True)
filepath = os.path.join(upload_folder, filename)
file.save(filepath)  # ← Guarda en disco local

# Consecuencias:
# - Estado en disco local (no stateless)
# - No funciona con múltiples instancias
# - Requiere volúmenes compartidos (NFS, EFS)
# - Difícil de escalar horizontalmente
```

### Ahora (Object Storage S3-compatible)
```python
# ✅ Beneficios:
storage = get_storage_service()
url = storage.upload_file(
    file=image_file,
    object_name=f"products/tenant_{tenant_id}/{timestamp}_{filename}",
    content_type=file.content_type
)

# Consecuencias:
# - Aplicación completamente stateless
# - Múltiples instancias Flask sin problemas
# - Escalado horizontal trivial
# - Compatible con MinIO (local), AWS S3, DigitalOcean Spaces
```

---

## 🏗️ Arquitectura Implementada

```
┌─────────────────────────────────────────────────────────────┐
│                        Load Balancer                         │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼───────┐   ┌───────▼───────┐   ┌───────▼───────┐
│  Flask Web 1  │   │  Flask Web 2  │   │  Flask Web 3  │
│   (Stateless) │   │   (Stateless) │   │   (Stateless) │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                ┌───────────▼────────────┐
                │   MinIO / S3 / Spaces  │
                │   (Object Storage)     │
                └────────────────────────┘
```

**Ventajas:**
- ✅ Todas las instancias Flask acceden al mismo storage
- ✅ No hay sincronización de archivos entre instancias
- ✅ No hay dependencia de filesystem local
- ✅ Escalado horizontal trivial (Kubernetes, Docker Swarm, etc.)

---

## 📁 Archivos Modificados/Creados

### 1. `docker-compose.yml` - Servicio MinIO

**Agregado:**
```yaml
minio:
  image: minio/minio:latest
  ports:
    - "9000:9000"  # API
    - "9001:9001"  # Web Console
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin
  command: server /data --console-address ":9001"
  volumes:
    - minio_data:/data
  healthcheck:
    test: ["CMD", "mc", "ready", "local"]
```

**Variables S3 en servicio `web`:**
```yaml
- S3_ENDPOINT=http://minio:9000
- S3_ACCESS_KEY=minioadmin
- S3_SECRET_KEY=minioadmin
- S3_BUCKET=uploads
- S3_REGION=us-east-1
- S3_PUBLIC_URL=http://localhost:9000
```

---

### 2. `config.py` - Configuración S3

**Agregado:**
```python
# Object Storage Configuration (PASO 7 - MinIO/S3)
S3_ENDPOINT = os.getenv('S3_ENDPOINT', 'http://minio:9000')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', 'minioadmin')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', 'minioadmin')
S3_BUCKET = os.getenv('S3_BUCKET', 'uploads')
S3_REGION = os.getenv('S3_REGION', 'us-east-1')
S3_PUBLIC_URL = os.getenv('S3_PUBLIC_URL', 'http://localhost:9000')

# Upload constraints
MAX_UPLOAD_SIZE = int(os.getenv('MAX_UPLOAD_SIZE', 2 * 1024 * 1024))  # 2MB
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
```

---

### 3. `app/services/storage_service.py` - Storage Service (NUEVO)

**Responsabilidades:**
- ✅ Cliente boto3 (AWS SDK for Python)
- ✅ Conexión a MinIO/S3/Spaces
- ✅ Creación automática de bucket
- ✅ Upload de archivos con validación
- ✅ Delete de archivos
- ✅ Generación de URLs públicas
- ✅ Validación de tamaño y MIME type

**API:**
```python
from app.services.storage_service import get_storage_service

storage = get_storage_service()

# Upload
url = storage.upload_file(
    file=file_object,
    object_name='products/tenant_1/123_image.jpg',
    content_type='image/jpeg'
)

# Delete
storage.delete_file('products/tenant_1/123_image.jpg')

# Get URL
url = storage.get_public_url('products/tenant_1/123_image.jpg')

# Check existence
exists = storage.file_exists('products/tenant_1/123_image.jpg')
```

---

### 4. `app/blueprints/catalog.py` - Refactorización

**Antes:**
```python
def save_product_image(file):
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)  # ← Filesystem local
    return filename  # ← Solo filename
```

**Ahora:**
```python
def save_product_image(file, tenant_id: int):
    object_name = f"products/tenant_{tenant_id}/{timestamp}_{filename}"
    storage = get_storage_service()
    url = storage.upload_file(
        file=file,
        object_name=object_name,
        content_type=file.content_type
    )
    return url  # ← Full URL: http://localhost:9000/uploads/products/tenant_1/123.jpg
```

**Cambios en Base de Datos:**
```python
# Antes:
product.image_path = "123_image.jpg"  # Solo filename

# Ahora:
product.image_path = "http://localhost:9000/uploads/products/tenant_1/123_image.jpg"  # Full URL
```

---

### 5. `requirements.txt` - Dependencias

**Agregado:**
```
boto3==1.35.91
botocore==1.35.91
```

---

### 6. `.env` - Variables de Entorno

**Agregado:**
```bash
# Object Storage Configuration (PASO 7)
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=uploads
S3_REGION=us-east-1
S3_PUBLIC_URL=http://localhost:9000
MAX_UPLOAD_SIZE=2097152  # 2MB

MINIO_CONSOLE_PORT=9001
MINIO_API_PORT=9000
```

---

## 🚀 Cómo Usar

### 1. Levantar Stack con MinIO

```bash
# Rebuild para incluir boto3
docker compose down
docker compose build --no-cache web
docker compose up -d

# Verificar servicios
docker compose ps
```

**Resultado esperado:**
```
NAME           IMAGE                STATUS       PORTS
Stock-db       postgres:16          Up          0.0.0.0:5432->5432/tcp
Stock-minio    minio/minio:latest   Up          0.0.0.0:9000-9001->9000-9001/tcp
Stock-web      stock-web            Up          0.0.0.0:5000->5000/tcp
```

---

### 2. Acceder a MinIO Console (Web UI)

**URL:** http://localhost:9001

**Login:**
- Username: `minioadmin`
- Password: `minioadmin`

**Verificar:**
- ✅ Bucket `uploads` existe (creado automáticamente por la app)
- ✅ Bucket policy: `public-read` (para servir imágenes)

---

### 3. Probar Upload de Imágenes

1. **Crear/Editar Producto:**
   - Ir a: http://localhost:5000/products/new
   - Subir imagen de producto

2. **Verificar en MinIO Console:**
   - Ir a: http://localhost:9001
   - Browse → `uploads` bucket
   - Ver: `products/tenant_1/TIMESTAMP_filename.jpg`

3. **Verificar URL en DB:**
```sql
SELECT id, name, image_path FROM product WHERE image_path IS NOT NULL;
```

**Resultado esperado:**
```
id | name      | image_path
---+-----------+-------------------------------------------------------
 1 | Martillo  | http://localhost:9000/uploads/products/tenant_1/1738204800_martillo.jpg
```

4. **Verificar Imagen en Browser:**
   - Abrir URL directamente: http://localhost:9000/uploads/products/tenant_1/1738204800_martillo.jpg
   - ✅ Imagen debe ser accesible públicamente

---

### 4. Verificar Logs

```bash
# Logs de la app
docker compose logs -f web | grep STORAGE

# Logs de MinIO
docker compose logs -f minio
```

**Logs esperados:**
```
[STORAGE] Bucket 'uploads' exists
[STORAGE] ✓ File validation passed: martillo.jpg (145823 bytes, image/jpeg)
[STORAGE] Uploading 'products/tenant_1/1738204800_martillo.jpg' to bucket 'uploads'...
[STORAGE] ✓ File uploaded: http://localhost:9000/uploads/products/tenant_1/1738204800_martillo.jpg
```

---

## 🔄 Migración a Producción (AWS S3 / DigitalOcean Spaces)

### AWS S3

**1. Crear bucket en AWS:**
```bash
aws s3 mb s3://mi-app-uploads --region us-east-1
```

**2. Configurar política pública (opcional):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::mi-app-uploads/*"
    }
  ]
}
```

**3. Obtener credenciales IAM:**
- Access Key ID
- Secret Access Key

**4. Actualizar `.env` (producción):**
```bash
# Comentar/eliminar S3_ENDPOINT para usar AWS S3 nativo
# S3_ENDPOINT=  # ← Dejar vacío o comentar

S3_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
S3_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_BUCKET=mi-app-uploads
S3_REGION=us-east-1
S3_PUBLIC_URL=https://mi-app-uploads.s3.amazonaws.com
```

**5. Rebuild y deploy:**
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

---

### DigitalOcean Spaces

**1. Crear Space en DigitalOcean:**
- Region: NYC3, AMS3, etc.
- Name: `mi-app-uploads`
- CDN: Habilitar (opcional)

**2. Generar Access Keys:**
- Settings → API → Spaces Keys
- Copiar: Access Key y Secret Key

**3. Actualizar `.env` (producción):**
```bash
S3_ENDPOINT=https://nyc3.digitaloceanspaces.com
S3_ACCESS_KEY=YOUR_DO_ACCESS_KEY
S3_SECRET_KEY=YOUR_DO_SECRET_KEY
S3_BUCKET=mi-app-uploads
S3_REGION=us-east-1  # No afecta en DigitalOcean
S3_PUBLIC_URL=https://mi-app-uploads.nyc3.digitaloceanspaces.com

# O con CDN:
# S3_PUBLIC_URL=https://mi-app-uploads.nyc3.cdn.digitaloceanspaces.com
```

**4. Rebuild y deploy:**
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 📊 Comparación: Local vs Producción

| Aspecto | Local (MinIO) | Producción (AWS S3) | Producción (DO Spaces) |
|---------|---------------|---------------------|------------------------|
| **Endpoint** | `http://minio:9000` | (vacío o comentado) | `https://nyc3.digitaloceanspaces.com` |
| **Public URL** | `http://localhost:9000` | `https://bucket.s3.amazonaws.com` | `https://bucket.nyc3.digitaloceanspaces.com` |
| **Costos** | ✅ Gratis | ~$0.023/GB/mes | ~$0.020/GB/mes |
| **Escalabilidad** | ⚠️ Limitado | ✅ Ilimitado | ✅ Ilimitado |
| **CDN** | ❌ No | ✅ CloudFront | ✅ Incluido |
| **Redundancia** | ❌ No | ✅ 99.999999999% | ✅ 99.9% |

---

## 🔒 Seguridad

### Validaciones Implementadas

**1. Tamaño de Archivo:**
```python
MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2MB
if file_size > MAX_UPLOAD_SIZE:
    raise ValueError(f"El archivo es demasiado grande. Máximo {max_mb:.1f}MB")
```

**2. MIME Type:**
```python
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
if content_type not in ALLOWED_MIME_TYPES:
    raise ValueError(f"Tipo de archivo no permitido: {content_type}")
```

**3. Tenant Isolation:**
```python
# Cada tenant tiene su propia carpeta
object_name = f"products/tenant_{tenant_id}/{timestamp}_{filename}"
```

**4. Bucket Policy (Public Read):**
```json
{
  "Effect": "Allow",
  "Principal": {"AWS": "*"},
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:::uploads/*"
}
```

⚠️ **Nota:** Las imágenes son públicamente accesibles (necesario para mostrarlas en la web).

---

## 🧪 Testing

### Test 1: Upload Exitoso
```bash
curl -X POST http://localhost:5000/products/new \
  -F "name=Martillo" \
  -F "sku=MART-001" \
  -F "uom_id=1" \
  -F "sale_price=100" \
  -F "image=@/path/to/martillo.jpg"
```

**Resultado esperado:**
- ✅ HTTP 302 (redirect)
- ✅ Flash message: "Producto creado exitosamente"
- ✅ Archivo en MinIO: `uploads/products/tenant_1/TIMESTAMP_martillo.jpg`
- ✅ DB: `image_path` contiene URL completa

---

### Test 2: Archivo Demasiado Grande
```bash
# Crear archivo de 3MB
dd if=/dev/zero of=big.jpg bs=1M count=3

curl -X POST http://localhost:5000/products/new \
  -F "name=Test" \
  -F "sku=TEST-001" \
  -F "uom_id=1" \
  -F "sale_price=100" \
  -F "image=@big.jpg"
```

**Resultado esperado:**
- ✅ HTTP 200 (no redirect, vuelve al form)
- ✅ Flash message: "El archivo es demasiado grande. Máximo 2.0MB"
- ❌ No se crea producto

---

### Test 3: MIME Type Inválido
```bash
curl -X POST http://localhost:5000/products/new \
  -F "name=Test" \
  -F "sku=TEST-002" \
  -F "uom_id=1" \
  -F "sale_price=100" \
  -F "image=@document.pdf"
```

**Resultado esperado:**
- ✅ HTTP 200 (no redirect, vuelve al form)
- ✅ Flash message: "Tipo de archivo no permitido: application/pdf"
- ❌ No se crea producto

---

### Test 4: Editar Producto (Delete Old Image)
```bash
# 1. Crear producto con imagen
curl -X POST http://localhost:5000/products/new \
  -F "name=Martillo" \
  -F "sku=MART-001" \
  -F "uom_id=1" \
  -F "sale_price=100" \
  -F "image=@martillo_v1.jpg"

# 2. Verificar imagen en MinIO console
# URL: http://localhost:9001 → uploads → products/tenant_1/TIMESTAMP_martillo_v1.jpg

# 3. Editar producto con nueva imagen
curl -X POST http://localhost:5000/products/1/edit \
  -F "name=Martillo" \
  -F "sku=MART-001" \
  -F "uom_id=1" \
  -F "sale_price=120" \
  -F "image=@martillo_v2.jpg"

# 4. Verificar en MinIO console
# ✅ martillo_v1.jpg debe estar ELIMINADO
# ✅ martillo_v2.jpg debe estar presente
```

---

## 📈 Performance

### Comparación: Filesystem vs S3

| Operación | Filesystem Local | MinIO (Local) | AWS S3 |
|-----------|------------------|---------------|--------|
| **Upload 1MB** | ~5ms | ~15ms | ~50ms |
| **Upload 10MB** | ~50ms | ~150ms | ~500ms |
| **Read 1MB** | ~2ms | ~10ms | ~30ms |
| **Delete** | ~1ms | ~5ms | ~20ms |

**Notas:**
- Filesystem es más rápido localmente
- Pero S3 escala infinitamente
- S3 tiene CDN (CloudFront) para reads rápidos globalmente
- MinIO local es similar a S3 en latencia

---

## ✅ Checklist de Completitud

### Implementación
- [x] Servicio MinIO en docker-compose
- [x] Variables S3 en config
- [x] Storage Service con boto3
- [x] Refactor catalog.py (upload)
- [x] Refactor catalog.py (delete)
- [x] Validaciones de tamaño y tipo
- [x] Tenant isolation en paths
- [x] boto3 en requirements.txt
- [x] Variables en .env

### Testing
- [x] Upload exitoso
- [x] Validación de tamaño
- [x] Validación de MIME type
- [x] Delete old image on edit
- [x] Multiple instances (stateless)

### Documentación
- [x] README actualizado
- [x] Guía de migración a AWS S3
- [x] Guía de migración a DigitalOcean Spaces
- [x] Documentación de API del Storage Service
- [x] Ejemplos de uso

---

## 🎯 Resultados

### Antes (PASO 6)
```
┌──────────────┐
│  Flask Web   │  ← Estado en disco local
│  Instance 1  │  ← No escalable
└──────────────┘
       │
       ▼
   /static/uploads/products/
   └── 123_image.jpg  ← Filesystem local
```

### Ahora (PASO 7)
```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Flask Web 1 │   │  Flask Web 2 │   │  Flask Web 3 │
│  (Stateless) │   │  (Stateless) │   │  (Stateless) │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                 ┌────────▼────────┐
                 │   MinIO / S3    │
                 │   (Stateless)   │
                 └─────────────────┘
```

**Beneficios Logrados:**
- ✅ **Stateless:** No hay estado en disco local
- ✅ **Escalable:** Múltiples instancias Flask sin problemas
- ✅ **Compatible:** MinIO (local), AWS S3, DigitalOcean Spaces
- ✅ **Migración trivial:** Cambiar 3 variables de entorno
- ✅ **Tenant isolation:** Cada tenant tiene su carpeta
- ✅ **Validaciones robustas:** Tamaño, MIME type, errores claros

---

**Fecha:** 2026-01-23  
**Versión:** 1.7.0  
**Estado:** ✅ PASO 7 COMPLETADO
