import os
import time
import hashlib
import replicate
import yt_dlp
from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Body
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Servidor Backend para Separación de Audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

user_credits = {}
audio_cache = {}

def get_today_string():
    return time.strftime("%Y-%m-%d")

def comprobar_limite(user_id: str, is_premium: str):
    es_premium_bool = is_premium.lower() == "true"
    today = get_today_string()
    
    if not es_premium_bool:
        user_data = user_credits.get(user_id, {"date": today, "count": 0})
        if user_data["date"] != today:
            user_data = {"date": today, "count": 0}
            
        if user_data["count"] >= 2:
            raise HTTPException(
                status_code=429, 
                detail="Has alcanzado tu límite de 2 canciones gratis hoy. Vuelve mañana o adquiere la suscripción Premium."
            )
        return user_data, False
    return None, True

def procesar_con_replicate(file_path: str, token: str):
    client = replicate.Client(api_token=token)
    with open(file_path, "rb") as audio_file:
        output = client.run(
            "facebookresearch/demucs:b55aed039233f2081d113f02a63200a00465c010c2262d4993d05267a6e133c0",
            input={
                "audio": audio_file,
                "two_stems": "vocals"
            }
        )
    return {
        "voz": output if isinstance(output, str) else output.get("vocals"),
        "pista": output.get("no_vocals") if isinstance(output, dict) else None
    }

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Servidor de audio funcionando correctamente"}

# -------------------------------------------------------------
# 1. RUTA PARA ARCHIVOS SUBIDOS DESDE EL TELÉFONO
# -------------------------------------------------------------
@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header(...), 
    is_premium: str = Header("false")
):
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Falta la variable REPLICATE_API_TOKEN en Railway.")

    user_data, es_premium_bool = comprobar_limite(user_id, is_premium)
    contents = await file.read()
    
    audio_hash = hashlib.md5(contents).hexdigest()
    if audio_hash in audio_cache:
        return {"status": "exito_cache", "urls": audio_cache[audio_hash]}

    temp_path = f"temp_{int(time.time())}_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(contents)

    try:
        urls_resultado = procesar_con_replicate(temp_path, token)
        audio_cache[audio_hash] = urls_resultado
        
        if not es_premium_bool:
            user_data["count"] += 1
            user_credits[user_id] = user_data

        if os.path.exists(temp_path):
            os.remove(temp_path)

        return {"status": "exito", "urls": urls_resultado}

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Error en Replicate: {str(e)}")

# -------------------------------------------------------------
# 2. NUEVA RUTA PARA ENLACES DE YOUTUBE U OTRAS URLS
# -------------------------------------------------------------
@app.post("/api/separar-url/")
async def separar_url(
    data: dict = Body(...),
    user_id: str = Header(...), 
    is_premium: str = Header("false")
):
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Falta la variable REPLICATE_API_TOKEN en Railway.")

    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Debes proporcionar una URL válida.")

    user_data, es_premium_bool = comprobar_limite(user_id, is_premium)
    
    # Caché basada en la URL del video
    url_hash = hashlib.md5(url.encode()).hexdigest()
    if url_hash in audio_cache:
        return {"status": "exito_cache", "urls": audio_cache[url_hash]}

    output_filename = f"temp_yt_{int(time.time())}"
    
    # Opciones de extracción con yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_filename}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    temp_file_mp3 = f"{output_filename}.mp3"

    try:
        # Descargar el audio desde la URL de YouTube o web
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(temp_file_mp3):
            # Si el postprocesador no cambió la extensión
            for file in os.listdir("."):
                if file.startswith(output_filename):
                    temp_file_mp3 = file
                    break

        urls_resultado = procesar_con_replicate(temp_file_mp3, token)
        audio_cache[url_hash] = urls_resultado
        
        if not es_premium_bool:
            user_data["count"] += 1
            user_credits[user_id] = user_data

        if os.path.exists(temp_file_mp3):
            os.remove(temp_file_mp3)

        return {"status": "exito", "urls": urls_resultado}

    except Exception as e:
        if os.path.exists(temp_file_mp3):
            os.remove(temp_file_mp3)
        raise HTTPException(status_code=500, detail=f"Error procesando la URL: {str(e)}")
