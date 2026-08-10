import os
import tempfile
import replicate
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Servidor de Audio Asíncrono")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPLICATE_API_TOKEN = os.environ.get("REPLICATE_API_TOKEN")

# Almacenamiento temporal de trabajos en memoria
TRABAJOS = {}

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Servidor listo"}

def Tarea_Separar_Audio(job_id: str, file_path: str):
    try:
        TRABAJOS[job_id] = {"status": "procesando"}
        
        # Ejecución en Replicate (Demucs)
        with open(file_path, "rb") as audio_file:
            output = replicate.run(
                "facebookresearch/demucs:e077d4f5a8251a16210db280249281a7b483161099f36f0412b1c73a114f6d4d",
                input={"audio": audio_file}
            )

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
        TRABAJOS[job_id] = {"status": "error", "mensaje": str(e)}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/api/separar-audio/")
async def separar_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN en Railway")

    # Guardar archivo temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    # Crear ID único de trabajo
    job_id = str(hash(temp_path + str(os.urandom(8))))
    TRABAJOS[job_id] = {"status": "pendiente"}

    # Iniciar procesamiento en segundo plano (NO bloquea la conexión)
    background_tasks.add_task(Tarea_Separar_Audio, job_id, temp_path)

    # Responde DE INMEDIATO al teléfono (en 1 segundo)
    return {"status": "exito", "job_id": job_id}

@app.get("/api/estado-trabajo/{job_id}")
def obtener_estado(job_id: str):
    trabajo = TRABAJOS.get(job_id)
    if not trabajo:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    return trabajo
