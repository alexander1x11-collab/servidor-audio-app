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
    es_premium_bool = str(is_premium).lower() == "true"
    today = get_today_string()
    
    if not es_premium_bool:
        user_data = user_credits.get(user_id, {"date": today, "count": 0})
        if user_data.get("date") != today:
            user_data = {"date": today, "count": 0}
            
        if user_data.get("count", 0) >= 2:
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
    
    if isinstance(output, dict):
        return {"voz": output.get("vocals"), "pista": output.get("no_vocals")}
    elif hasattr(output, "vocals"):
        return {"voz": getattr(output, "vocals", None), "pista": getattr(output, "no_vocals", None)}
    else:
        return {"voz": str(output), "pista": None}

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Servidor de audio funcionando correctamente"}

# -------------------------------------------------------------
# 1. RUTA PARA ARCHIVOS SUBIDOS DESDE EL TELÉFONO
# -------------------------------------------------------------
@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header("usuario_anonimo"), 
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
        
        if not es_premium_bool and user_data:
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
# 2. RUTA PARA ENLACES DE YOUTUBE / URLS
# -------------------------------------------------------------
@app.post("/api/separar-url/")
async def separar_url(
    data: dict = Body(...),
    user_id: str = Header("usuario_anonimo"), 
    is_premium: str = Header("false")
):
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Falta la variable REPLICATE_API_TOKEN en Railway.")

    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Debes proporcionar una URL válida.")

    user_data, es_premium_bool = comprobar_limite(user_id, is_premium)
    
    url_hash = hashlib.md5(url.encode()).hexdigest()
    if url_hash in audio_cache:
        return {"status": "exito_cache", "urls": audio_cache[url_hash]}

    output_filename = f"temp_yt_{int(time.time())}"
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_filename}.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    temp_downloaded_file = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            temp_downloaded_file = ydl.prepare_filename(info)

        if not os.path.exists(temp_downloaded_file):
            raise Exception("No se pudo descargar el archivo de audio desde la URL dada.")

        urls_resultado = procesar_con_replicate(temp_downloaded_file, token)
        audio_cache[url_hash] = urls_resultado
        
        if not es_premium_bool and user_data:
            user_data["count"] += 1
            user_credits[user_id] = user_data

        if temp_downloaded_file and os.path.exists(temp_downloaded_file):
            os.remove(temp_downloaded_file)

        return {"status": "exito", "urls": urls_resultado}

    except Exception as e:
        if temp_downloaded_file and os.path.exists(temp_downloaded_file):
            os.remove(temp_downloaded_file)
        raise HTTPException(status_code=500, detail=f"Error procesando la URL: {str(e)}")
