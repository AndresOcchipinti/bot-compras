import os
import json
import psycopg2
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from dotenv import load_dotenv

# ── Carga variables del .env ──────────────────────────────────────────────────
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
DATABASE_URL   = os.getenv("DATABASE_URL")

# ── Configura Groq ────────────────────────────────────────────────────────────
cliente_ia = Groq(api_key=GROQ_API_KEY)


# ── Base de datos ─────────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Crea la tabla si no existe."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inventario (
                    producto TEXT PRIMARY KEY,
                    cantidad INTEGER NOT NULL
                )
            """)
        conn.commit()

def db_get_inventario() -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT producto, cantidad FROM inventario")
            return {row[0]: row[1] for row in cur.fetchall()}

def db_set_producto(producto: str, cantidad: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO inventario (producto, cantidad)
                VALUES (%s, %s)
                ON CONFLICT (producto) DO UPDATE SET cantidad = EXCLUDED.cantidad
            """, (producto, cantidad))
        conn.commit()

def db_delete_producto(producto: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM inventario WHERE producto = %s", (producto,))
        conn.commit()

def db_resetear_agotados():
    """Pone en 2 todos los productos con cantidad <= 1 y devuelve cuáles fueron."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT producto FROM inventario WHERE cantidad <= 1")
            productos = [row[0] for row in cur.fetchall()]
            if productos:
                cur.execute("UPDATE inventario SET cantidad = 2 WHERE cantidad <= 1")
        conn.commit()
    return productos


# ── Función principal de IA ───────────────────────────────────────────────────
def analizar_mensaje(mensaje: str) -> dict:
    respuesta = cliente_ia.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """Sos un asistente que interpreta mensajes sobre inventario del hogar.
Analizá el mensaje y respondé SOLO con un JSON con este formato (sin texto extra, sin markdown, sin backticks):
{
  "accion": "actualizar" | "consultar" | "lista" | "eliminar" | "vaciar" | "desconocido",
  "producto": "nombre del producto en minúsculas o null",
  "cantidad": numero entero o null,
  "agotado": true si el mensaje dice que se acabo/no queda, sino false
}

Ejemplos:
- "queda 1 leche" -> {"accion":"actualizar","producto":"leche","cantidad":1,"agotado":false}
- "me quede sin papel" -> {"accion":"actualizar","producto":"papel","cantidad":0,"agotado":true}
- "agrega 3 yogures" -> {"accion":"actualizar","producto":"yogur","cantidad":3,"agotado":false}
- "cuanta leche tengo" -> {"accion":"consultar","producto":"leche","cantidad":null,"agotado":false}
- "mostrame la lista" -> {"accion":"lista","producto":null,"cantidad":null,"agotado":false}
- "saque el azucar de la lista" -> {"accion":"eliminar","producto":"azucar","cantidad":null,"agotado":false}
- "ya fui de compras, vacia la lista" -> {"accion":"vaciar","producto":null,"cantidad":null,"agotado":false}
- "volvi del super" -> {"accion":"vaciar","producto":null,"cantidad":null,"agotado":false}
- "compre todo" -> {"accion":"vaciar","producto":null,"cantidad":null,"agotado":false}"""
            },
            {
                "role": "user",
                "content": mensaje
            }
        ],
        temperature=0,
        max_tokens=200
    )

    texto = respuesta.choices[0].message.content.strip()
    texto = texto.replace("```json", "").replace("```", "").strip()
    return json.loads(texto)


# ── Helpers ───────────────────────────────────────────────────────────────────
def generar_lista_compras() -> str:
    inventario = db_get_inventario()

    if not inventario:
        return "📦 Tu inventario está vacío. Contame qué tenés en casa."

    necesitan_compra = {p: c for p, c in inventario.items() if c <= 1}
    tienen_stock     = {p: c for p, c in inventario.items() if c > 1}

    texto = "🛒 *Lista de compras*\n\n"

    if necesitan_compra:
        texto += "❌ *Necesitás comprar:*\n"
        for producto, cantidad in necesitan_compra.items():
            if cantidad == 0:
                texto += f"  • {producto.capitalize()} (agotado)\n"
            else:
                texto += f"  • {producto.capitalize()} (queda {cantidad})\n"
    else:
        texto += "✅ No necesitás comprar nada por ahora.\n"

    if tienen_stock:
        texto += "\n📦 *Tenés en stock:*\n"
        for producto, cantidad in tienen_stock.items():
            texto += f"  • {producto.capitalize()}: {cantidad}\n"

    return texto


async def procesar_accion(datos: dict, update: Update) -> str | None:
    accion   = datos.get("accion")
    producto = datos.get("producto")
    cantidad = datos.get("cantidad")
    agotado  = datos.get("agotado", False)

    if accion == "actualizar" and producto:
        cantidad_final = 0 if agotado else (cantidad if cantidad is not None else 1)
        db_set_producto(producto, cantidad_final)
        if cantidad_final == 0:
            return f"❌ *{producto.capitalize()}* agotado, agregado a la lista."
        else:
            return f"✅ *{producto.capitalize()}*: {cantidad_final} unidad(es)."

    elif accion == "consultar" and producto:
        inventario = db_get_inventario()
        if producto in inventario:
            cant   = inventario[producto]
            estado = "agotado ❌" if cant == 0 else f"{cant} unidad(es)"
            return f"📦 *{producto.capitalize()}*: {estado}"
        else:
            return f"🤷 No tengo registro de *{producto}*."

    elif accion == "lista":
        await update.message.reply_text(generar_lista_compras(), parse_mode="Markdown")
        return None

    elif accion == "eliminar" and producto:
        inventario = db_get_inventario()
        if producto in inventario:
            db_delete_producto(producto)
            return f"🗑️ *{producto.capitalize()}* eliminado."
        else:
            return f"🤷 No tenía *{producto}* en el inventario."

    elif accion == "vaciar":
        productos_reseteados = db_resetear_agotados()
        if productos_reseteados:
            lista = ", ".join([p.capitalize() for p in productos_reseteados])
            await update.message.reply_text(
                f"🛍️ ¡Buenísimo! Marqué como comprados:\n_{lista}_\n\nEl inventario quedó actualizado.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("🛍️ No había nada pendiente de comprar.")
        return None

    return None


# ── Comandos ──────────────────────────────────────────────────────────────────
async def comando_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 ¡Hola! Soy tu asistente de compras.\n\n"
        "Podés decirme cosas como:\n"
        "• *'Queda 1 leche'*\n"
        "• *'Me quedé sin papel'*\n"
        "• *'Agregá 3 yogures'*\n"
        "• *'Mostrame la lista'*\n"
        "• *'Cuánta leche tengo'*\n"
        "• *'Saqué el azúcar'* (para eliminar)\n"
        "• *'Ya fui de compras'* (resetea los agotados)\n\n"
        "También podés mandar varias órdenes juntas, una por línea.\n\n"
        "Usá /lista o /inventario para ver el estado.",
        parse_mode="Markdown"
    )


async def comando_lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(generar_lista_compras(), parse_mode="Markdown")


async def comando_inventario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inventario = db_get_inventario()

    if not inventario:
        await update.message.reply_text("📦 El inventario está vacío.")
        return

    texto = "📦 *Inventario completo:*\n\n"
    for producto, cantidad in sorted(inventario.items()):
        emoji = "❌" if cantidad == 0 else "⚠️" if cantidad == 1 else "✅"
        texto += f"{emoji} {producto.capitalize()}: {cantidad}\n"

    await update.message.reply_text(texto, parse_mode="Markdown")


# ── Manejador de mensajes ─────────────────────────────────────────────────────
async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.message.text
    lineas  = [l.strip() for l in mensaje.strip().splitlines() if l.strip()]

    try:
        if len(lineas) == 1:
            datos     = analizar_mensaje(lineas[0])
            respuesta = await procesar_accion(datos, update)
            if respuesta:
                await update.message.reply_text(respuesta, parse_mode="Markdown")
        else:
            respuestas = []
            for linea in lineas:
                try:
                    datos     = analizar_mensaje(linea)
                    respuesta = await procesar_accion(datos, update)
                    if respuesta:
                        respuestas.append(respuesta)
                except Exception:
                    respuestas.append(f"⚠️ No entendí: _{linea}_")

            if respuestas:
                await update.message.reply_text("\n".join(respuestas), parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text("⚠️ Hubo un error procesando tu mensaje. Intentá de nuevo.")
        print(f"Error: {e}")


# ── Arranque ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🤖 Bot iniciando...")
    init_db()
    print("✅ Base de datos lista.")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",      comando_inicio))
    app.add_handler(CommandHandler("lista",      comando_lista))
    app.add_handler(CommandHandler("inventario", comando_inventario))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, manejar_mensaje))

    print("✅ Bot corriendo. Presioná Ctrl+C para detenerlo.")
    app.run_polling()
