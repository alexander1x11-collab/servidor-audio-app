import os
import time
import hashlib
import replicate
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Servidor Backend para Separación de Audio")

# Configurar CORS para permitir peticiones desde cualquier origen (App móvil / Web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Control de límites en memoria
user_credits = {}
audio_cache = {}

def get_today_string():
    return time.strftime("%Y-%m-%d")

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Servidor de audio funcionando correctamente"}

@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header(...), 
    is_premium: str = Header("false")
):
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise HTTPException(
            status_code=500, 
            detail="Falta configurar la variable REPLICATE_API_TOKEN en Railway."
        )

    # Convertir header is_premium a booleano
    es_premium_bool = is_premium.lower() == "true"
    today = get_today_string()
    
    # 1. Control de límites diarios
    if not es_premium_bool:
        user_data = user_credits.get(user_id, {"date": today, "count": 0})
        if user_data["date"] != today:
            user_data = {"date": today, "count": 0}
            
        if user_data["count"] >= 2:
            raise HTTPException(
                status_code=429, 
                detail="Has alcanzado tu límite de 2 canciones gratis hoy. Vuelve mañana o adquiere la suscripción Premium."
            )

    contents = await file.read()
    
    # 2. Control de Caché por MD5
    audio_hash = hashlib.md5(contents).hexdigest()
    if audio_hash in audio_cache:
        return {
            "status": "exito_cache",
            "mensaje": "Canción recuperada de la caché.",
            "urls": audio_cache[audio_hash]
        }

    # Guardar archivo localmente en el contenedor
    temp_path = f"temp_{int(time.time())}_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(contents)

    # 3. Procesamiento en Replicate con cliente autenticado
    try:
        client = replicate.Client(api_token=token)
        
        with open(temp_path, "rb") as audio_file:
            output = client.run(
                "facebookresearch/demucs:b55aed039233f2081d113f02a63200a00465c010c2262d4993d05267a6e133c0",
                input={
                    "audio": audio_file,
                    "two_stems": "vocals"
                }
            )
        
        # Estructurar resultado de salida
        urls_resultado = {
            "voz": output if isinstance(output, str) else output.get("vocals"),
            "pista": output.get("no_vocals") if isinstance(output, dict) else None
        }
        
        # Guardar en Caché
        audio_cache[audio_hash] = urls_resultado
        
        # Actualizar contador de créditos del usuario
        if not es_premium_bool:
            user_data["count"] += 1
            user_credits[user_id] = user_data

        if os.path.exists(temp_path):
            os.remove(temp_path)

        return {
            "status": "exito",
            "urls": urls_resultado
        }

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(
            status_code=500, 
            detail=f"Error en el procesamiento de Replicate: {str(e)}"
        )
