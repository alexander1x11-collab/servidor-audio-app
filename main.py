import os
import replicate
import yt_dlp
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

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Servidor activo"}

@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header(default="anonimo"), 
    is_premium: str = Header(default="false")
):
    try:
        if not REPLICATE_API_TOKEN:
            raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN")

        output = replicate.run(
            "cjwbw/htdemucs:f52950c0857e040f2824be4c1e48e028b80b0f90e5f2e604fefd267868350d32",
            input={"audio": file.file}
        )
        return {"status": "exito", "urls": output}
    except Exception as e:
        print(f"--> Error en separar-audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar audio: {str(e)}")

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
        if not REPLICATE_API_TOKEN:
            raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN")

        # Extraer el enlace directo de audio para evitar el bloqueo de enlace web de YouTube
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info.get('url')

        # Enviar el stream directo de audio a Replicate
        output = replicate.run(
            "cjwbw/htdemucs:f52950c0857e040f2824be4c1e48e028b80b0f90e5f2e604fefd267868350d32",
            input={"audio": audio_url}
        )
        
        return {"status": "exito", "urls": output}
    except Exception as e:
        print(f"--> Error en separar-url: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar URL de YouTube: {str(e)}")
