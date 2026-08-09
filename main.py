import os
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Servidor de Audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Servidor funcionando correctamente"}

@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header(default="anonimo"), 
    is_premium: str = Header(default="false")
):
    try:
        # Guardar archivo temporalmente para verificar subida
        temp_dir = "temp"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file.filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"--> Archivo recibido y guardado con éxito: {file_path}")

        # AQUÍ PROCESAS CON TU MODELO/REPLICATE
        # Retornamos URLs de prueba mientras procesa correctamente
        return {
            "status": "exito",
            "mensaje": "Audio recibido y procesado",
            "urls": {
                "voz": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                "pista": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"
            }
        }
    except Exception as e:
        print(f"--> Error procesando audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en servidor al procesar audio: {str(e)}")

@app.post("/api/separar-url/")
async def separar_url(
    data: dict,
    user_id: str = Header(default="anonimo"),
    is_premium: str = Header(default="false")
):
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL no proporcionada")
        
    try:
        print(f"--> Procesando URL: {url}")
        # Para evitar bloqueos de bots en YouTube con yt-dlp:
        # Debes usar cookies o procesar mediante audio stream directo
        return {
            "status": "exito",
            "mensaje": "URL procesada",
            "urls": {
                "voz": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                "pista": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"
            }
        }
    except Exception as e:
        print(f"--> Error en URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al descargar URL de YouTube: {str(e)}")
