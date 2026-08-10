import os
import tempfile
import asyncio
import replicate
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Servidor Audio App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# Modelo Oficial Actualizado de Replicate para Demucs
MODELO_DEMUCS = "facebookresearch/demucs:e077d4f5a8251a16210db280249281a7b483161099f36f0412b1c73a114f6d4d"

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Servidor activo correctamente"}

@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header(default="anonimo"), 
    is_premium: str = Header(default="false")
):
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN en Railway")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        print(f"--> [OK] Archivo recibido de {user_id}. Enviando a Demucs...")

        def procesar():
            with open(temp_path, "rb") as audio_file:
                return replicate.run(
                    MODELO_DEMUCS,
                    input={
                        "audio": audio_file,
                        "stem": "none",
                        "two_stems": "vocals" # Genera 'vocals' y 'no_vocals' de forma ultra rápida
                    }
                )

        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, procesar)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Mapeo de respuesta
        urls_mapeadas = {
            "voz": output.get("vocals") or output.get("voz"),
            "pista": output.get("no_vocals") or output.get("other") or output.get("pista"),
            "bajo": output.get("bass"),
            "bateria": output.get("drums")
        }

        print(f"--> [ÉXITO] Salida: {urls_mapeadas}")
        return {"status": "exito", "urls": urls_mapeadas}

    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"--> Error en separar-audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en Replicate: {str(e)}")

@app.post("/api/separar-url/")
async def separar_url(
    data: dict,
    user_id: str = Header(default="anonimo"),
    is_premium: str = Header(default="false")
):
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN en Railway")

    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL requerida")

    try:
        print(f"--> [OK] URL recibida: {url}. Procesando en Demucs...")

        def procesar_url():
            return replicate.run(
                MODELO_DEMUCS,
                input={
                    "audio": url,
                    "stem": "none",
                    "two_stems": "vocals"
                }
            )

        loop = asyncio.get_event_loop()
        output = await loop.run_in_executor(None, procesar_url)

        urls_mapeadas = {
            "voz": output.get("vocals") or output.get("voz"),
            "pista": output.get("no_vocals") or output.get("other") or output.get("pista"),
            "bajo": output.get("bass"),
            "bateria": output.get("drums")
        }

        print(f"--> [ÉXITO URL] Salida: {urls_mapeadas}")
        return {"status": "exito", "urls": urls_mapeadas}

    except Exception as e:
        print(f"--> Error en separar-url: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en Replicate: {str(e)}")
