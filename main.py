import os
import replicate
from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Servidor de Audio con Replicate")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configura tu token de Replicate en las Variables de Entorno de Railway (REPLICATE_API_TOKEN)
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
            raise HTTPException(status_code=500, detail="Falta la variable REPLICATE_API_TOKEN en Railway")

        # Subir temporalmente o enviar directamente a Replicate (Modelo HTDemucs / Demucs)
        output = replicate.run(
            "cjwbw/htdemucs:f52950c0857e040f2824be4c1e48e028b80b0f90e5f2e604fefd267868350d32",
            input={"audio": file.file}
        )
        
        # Replicate devuelve un diccionario/objeto con las URLs de los audios procesados
        return {
            "status": "exito",
            "mensaje": "Audio procesado con éxito",
            "urls": output
        }
    except Exception as e:
        print(f"--> Error en separar-audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar audio con IA: {str(e)}")

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
            raise HTTPException(status_code=500, detail="Falta la variable REPLICATE_API_TOKEN en Railway")

        output = replicate.run(
            "cjwbw/htdemucs:f52950c0857e040f2824be4c1e48e028b80b0f90e5f2e604fefd267868350d32",
            input={"audio": url}
        )
        
        return {
            "status": "exito",
            "mensaje": "URL procesada con éxito",
            "urls": output
        }
    except Exception as e:
        print(f"--> Error en separar-url: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al procesar URL con IA: {str(e)}")
