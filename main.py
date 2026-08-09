import os
import time
import hashlib
import replicate
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Servidor Backend para Separación de Audio")

# Permitir conexiones desde la aplicación móvil / web (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# CONFIGURACIÓN Y VARIABLES
# -------------------------------------------------------------
# Se obtiene el token de Replicate guardado en las Variables de Entorno de Railway
REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# Base de datos en memoria para el control de créditos diarios (Reset diario)
# Estructura: { "user_id": {"date": "YYYY-MM-DD", "count": 1} }
user_credits = {}

# Memoria Caché para evitar volver a procesar y pagar por audios repetidos
# Estructura: { "md5_hash_audio": {"voz": "url_voz", "pista": "url_pista"} }
audio_cache = {}


def get_today_string():
    """Retorna la fecha actual en formato YYYY-MM-DD para calcular el límite diario."""
    return time.strftime("%Y-%m-%d")


@app.get("/")
def home():
    """Ruta de prueba para verificar que el servidor en Railway está activo."""
    return {"status": "online", "mensaje": "Servidor de audio funcionando correctamente"}


@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header(...), 
    is_premium: bool = Header(False)
):
    """
    Ruta principal para procesar el audio subido por el usuario desde la app.
    """
    if not REPLICATE_API_TOKEN:
        raise HTTPException(
            status_code=500, 
            detail="Falta configurar la variable REPLICATE_API_TOKEN en Railway."
        )

    today = get_today_string()
    
    # -------------------------------------------------------------
    # 1. CONTROL DE CRÉDITOS Y LÍMITES DIARIOS (2 CANCIONES / DÍA)
    # -------------------------------------------------------------
    if not is_premium:
        user_data = user_credits.get(user_id, {"date": today, "count": 0})
        
        # Si cambió el día, reiniciamos el contador del usuario a 0
        if user_data["date"] != today:
            user_data = {"date": today, "count": 0}
            
        # Verificar si el usuario superó el límite de 2 canciones
        if user_data["count"] >= 2:
            raise HTTPException(
                status_code=429, 
                detail="Has alcanzado tu límite de 2 canciones gratis hoy. Vuelve mañana o adquiere la suscripción Premium."
            )

    # Leer el archivo de audio enviado desde la aplicación
    contents = await file.read()
    
    # -------------------------------------------------------------
    # 2. SISTEMA DE CACHÉ (Ahorro de costes en la API)
    # -------------------------------------------------------------
    audio_hash = hashlib.md5(contents).hexdigest()
    
    if audio_hash in audio_cache:
        # Si la canción ya fue procesada anteriormente, se devuelve sin llamar a Replicate ($0 costo)
        return {
            "status": "exito_cache",
            "mensaje": "Canción recuperada instantáneamente de la caché.",
            "urls": audio_cache[audio_hash]
        }

    # Guardar temporalmente el archivo recibido en el disco del servidor
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(contents)

    # -------------------------------------------------------------
    # 3. LLAMADA A LA API DE REPLICATE (Modelo HTDemucs)
    # -------------------------------------------------------------
    try:
        # Ejecución del modelo de IA de Meta en la nube
        output = replicate.run(
            "facebookresearch/demucs:b55aed039233f2081d113f02a63200a00465c010c2262d4993d05267a6e133c0",
            input={
                "audio": open(temp_path, "rb"),
                "two_stems": "vocals"  # Separa únicamente Voz y Pista
            }
        )
        
        urls_resultado = {
            "voz": output.get("vocals"),
            "pista": output.get("no_vocals")
        }
        
        # Guardar en memoria Caché para futuros usuarios
        audio_cache[audio_hash] = urls_resultado
        
        # Descontar 1 crédito al usuario gratuito
        if not is_premium:
            user_data["count"] += 1
            user_credits[user_id] = user_data

        # Eliminar archivo temporal local
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return {
            "status": "exito",
            "creditos_usados_hoy": user_credits.get(user_id, {}).get("count", 0) if not is_premium else "Ilimitado",
            "urls": urls_resultado
        }

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(
            status_code=500, 
            detail=f"Error al procesar el audio en la API: {str(e)}"
        )
