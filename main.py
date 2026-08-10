import os
import tempfile
import asyncio
import replicate
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
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
TRABAJOS = {}

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Servidor listo"}

def Tarea_Separar_Audio(job_id: str, temp_path: str):
    try:
        TRABAJOS[job_id] = {"status": "procesando"}

        print(f"--> [OK] Enviando archivo a Replicate (Demucs Oficial)...")

        # LLAMADA OFICIAL SIN HASH DEPRECIADO
        with open(temp_path, "rb") as audio_file:
            output = replicate.run(
                "facebookresearch/demucs",
                input={
                    "audio": audio_file
                }
            )

        print(f"--> [ÉXITO REPLICATE]: {output}")

        TRABAJOS[job_id] = {
            "status": "completado",
            "urls": {
                "voz": output.get("vocals"),
                "pista": output.get("no_vocals") or output.get("other"),
                "bajo": output.get("bass"),
                "bateria": output.get("drums")
            }
        }

    except Exception as e:
        print(f"--> [ERROR REPLICATE]: {str(e)}")
        TRABAJOS[job_id] = {"status": "error", "mensaje": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/api/separar-audio")
@app.post("/api/separar-audio/")
async def separar_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN en las variables de entorno.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    job_id = str(abs(hash(temp_path + str(os.urandom(8)))))
    TRABAJOS[job_id] = {"status": "pendiente"}

    background_tasks.add_task(Tarea_Separar_Audio, job_id, temp_path)
    return {"status": "exito", "job_id": job_id}

@app.get("/api/estado-trabajo/{job_id}")
@app.get("/api/estado-trabajo/{job_id}/")
def obtener_estado(job_id: str):
    trabajo = TRABAJOS.get(job_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return trabajo
