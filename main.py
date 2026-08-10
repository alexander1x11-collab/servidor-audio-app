import os
import tempfile
import asyncio
import replicate
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Servidor de Audio Estable")

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
    return {"status": "online", "mensaje": "Servidor funcionando"}

@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header(default="anonimo"), 
    is_premium: str = Header(default="false")
):
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN en Railway")

    try:
        # Guardar archivo local temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        print(f"--> Archivo recibido correctamente ({len(content)} bytes). Procesando en Replicate...")

        # Función de ejecución en hilo secundario con límite de tiempo
        def ejecutar_replicate():
            with open(temp_path, "rb") as audio_file:
                return replicate.run(
                    "cjwbw/htdemucs:f52950c0857e040f2824be4c1e48e028b80b0f90e5f2e604fefd267868350d32",
                    input={"audio": audio_file}
                )

        loop = asyncio.get_event_loop()
        output = await asyncio.wait_for(loop.run_in_executor(None, ejecutar_replicate), timeout=120.0)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        urls_mapeadas = {
            "voz": output.get("vocals") or output.get("voz"),
            "pista": output.get("no_vocals") or output.get("pista") or output.get("other"),
            "bajo": output.get("bass"),
            "bateria": output.get("drums")
        }

        print(f"--> ÉXITO: Pistas generadas: {urls_mapeadas}")
        return {"status": "exito", "urls": urls_mapeadas}

    except asyncio.TimeoutError:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=504, detail="El tiempo de procesamiento en la nube excedió los 2 minutos.")
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"--> ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en servidor: {str(e)}")

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
        def ejecutar_replicate_url():
            return replicate.run(
                "cjwbw/htdemucs:f52950c0857e040f2824be4c1e48e028b80b0f90e5f2e604fefd267868350d32",
                input={"audio": url}
            )

        loop = asyncio.get_event_loop()
        output = await asyncio.wait_for(loop.run_in_executor(None, ejecutar_replicate_url), timeout=120.0)

        urls_mapeadas = {
            "voz": output.get("vocals") or output.get("voz"),
            "pista": output.get("no_vocals") or output.get("pista") or output.get("other"),
            "bajo": output.get("bass"),
            "bateria": output.get("drums")
        }

        return {"status": "exito", "urls": urls_mapeadas}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Tiempo de procesamiento excedido en la nube.")
    except Exception as e:
        print(f"--> ERROR URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error en servidor: {str(e)}")
