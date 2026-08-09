import os
import tempfile
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
    return {"status": "online", "mensaje": "Servidor funcionando correctamente"}

@app.post("/api/separar-audio/")
async def separar_audio(
    file: UploadFile = File(...), 
    user_id: str = Header(default="anonimo"), 
    is_premium: str = Header(default="false")
):
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN en las variables de Railway")

    try:
        # 1. Guardar archivo temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        print(f"--> [OK] Archivo recibido ({len(content)} bytes). Enviando a Replicate...")

        # 2. Llamada directa a Replicate
        with open(temp_path, "rb") as audio_file:
            output = replicate.run(
                "cjwbw/htdemucs:f52950c0857e040f2824be4c1e48e028b80b0f90e5f2e604fefd267868350d32",
                input={"audio": audio_file}
            )

        # 3. Limpieza de archivo temporal
        if os.path.exists(temp_path):
            os.remove(temp_path)

        print(f"--> [ÉXITO] Salida de Replicate recibida: {output}")
        return {"status": "exito", "urls": output}

    except Exception as e:
        print(f"--> [ERROR CRÍTICO]: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar archivo: {str(e)}")

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
        raise HTTPException(status_code=400, detail="URL no proporcionada")

    try:
        print(f"--> [OK] Procesando URL: {url}")
        output = replicate.run(
            "cjwbw/htdemucs:f52950c0857e040f2824be4c1e48e028b80b0f90e5f2e604fefd267868350d32",
            input={"audio": url}
        )
        return {"status": "exito", "urls": output}
    except Exception as e:
        print(f"--> [ERROR CRÍTICO URL]: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar URL: {str(e)}")
