# 🛒 Bot Asistente de Compras — Telegram

Bot de Telegram con IA que te ayuda a gestionar el inventario de tu hogar. Podés decirle en lenguaje natural qué tenés, qué te falta, y pedirle la lista de compras.

---

## ✨ Funcionalidades

- Registrar cantidades de productos en lenguaje natural
- Consultar el stock de un producto
- Ver la lista de lo que falta comprar
- Eliminar productos del inventario
- Resetear productos comprados al volver del super

---

## 🗣️ Ejemplos de uso

| Mensaje | Acción |
|---|---|
| `Queda 1 leche` | Actualiza leche a cantidad 1 |
| `Me quedé sin papel` | Marca papel como agotado |
| `Agregá 3 yogures` | Agrega 3 yogures al inventario |
| `Mostrame la lista` | Muestra qué falta comprar |
| `Cuánta leche tengo` | Consulta el stock de leche |
| `Saqué el azúcar` | Elimina azúcar del inventario |
| `Ya fui de compras` | Resetea los productos agotados |

También podés mandar varias órdenes juntas, una por línea.

### Comandos disponibles

- `/start` — Muestra el mensaje de bienvenida con ejemplos
- `/lista` — Lista de compras (lo que falta)
- `/inventario` — Inventario completo con estado de cada producto

---

## 🧱 Stack

| Componente | Tecnología |
|---|---|
| Bot | Python + python-telegram-bot |
| IA | Groq API (llama-3.3-70b-versatile) |
| Base de datos | PostgreSQL en Neon |
| Hosting | Render (free tier) |
| Keep-alive | cron-job.org |

---

## ⚙️ Variables de entorno

Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
TELEGRAM_TOKEN=tu_token_de_botfather
GROQ_API_KEY=tu_api_key_de_groq
DATABASE_URL=postgresql://usuario:password@host/db?sslmode=require
WEBHOOK_URL=https://tu-servicio.onrender.com
```

---

## 🚀 Setup y deploy

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/tu-repo.git
cd tu-repo
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

**requirements.txt** debe incluir:

```
python-telegram-bot[webhooks]
groq
psycopg2-binary
python-dotenv
```

> ⚠️ Es necesario el extra `[webhooks]` en python-telegram-bot para que funcione `run_webhook`.

### 3. Base de datos en Neon

1. Crear cuenta en [neon.tech](https://neon.tech)
2. Crear un nuevo proyecto
3. Copiar el connection string (incluye `?sslmode=require`)
4. Pegarlo como `DATABASE_URL` en las variables de entorno

> **¿Por qué Neon y no Supabase?** Render free tier solo soporta IPv4. Supabase migró sus conexiones directas a IPv6, lo que hace que sean incompatibles. Neon provee endpoints IPv4 directamente.

### 4. Deploy en Render

1. Crear una cuenta en [render.com](https://render.com)
2. Crear un nuevo **Web Service** conectado al repositorio de GitHub
3. Configurar:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
4. Agregar las variables de entorno en **Environment**
5. Hacer deploy

### 5. Registrar el webhook de Telegram

Una vez que el servicio esté corriendo en Render, registrar el webhook manualmente abriendo esta URL en el navegador:

```
https://api.telegram.org/botTU_TOKEN/setWebhook?url=https://tu-servicio.onrender.com/webhook
```

Debe responder:
```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

Para verificar que quedó bien:
```
https://api.telegram.org/botTU_TOKEN/getWebhookInfo
```

### 6. Keep-alive con cron-job.org

Render free tier duerme el servicio después de 15 minutos sin actividad. Para evitarlo:

1. Crear cuenta en [cron-job.org](https://cron-job.org)
2. Crear un nuevo cron job con:
   - **URL:** `https://tu-servicio.onrender.com`
   - **Schedule:** cada 10 minutos
3. Guardar

Esto mantiene el servicio siempre activo dentro de las 750 horas gratuitas mensuales de Render.

---

## 🗄️ Estructura de la base de datos

```sql
CREATE TABLE inventario (
    producto TEXT PRIMARY KEY,
    cantidad INTEGER NOT NULL
);
```

- `cantidad = 0` → agotado ❌
- `cantidad = 1` → queda poco ⚠️
- `cantidad >= 2` → en stock ✅

---

## 🔧 Detalle técnico del webhook

El bot usa webhook en lugar de polling. El parámetro `url_path` es necesario para que PTB registre correctamente la ruta `/webhook`:

```python
app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 8443)),
    url_path="webhook",
    webhook_url=f"{WEBHOOK_URL}/webhook"
)
```

---

## 📁 Estructura del proyecto

```
├── bot.py
├── requirements.txt
├── .env
└── README.md
```
