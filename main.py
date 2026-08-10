import os
import tempfile
import requests
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

def subir_a_host_temporal(file_path):
    try:
        with open(file_path, "rb") as f:
            response = requests.post("https://tmpfiles.org/api/v1/upload", files={"file": f}, timeout=15)
            data = response.json()
            if response.status_code == 200 and "data" in data:
                return data["data"]["url"].replace("tmpfiles.org/", "tmpfiles.org/dl/")
    except Exception as e:
        print(f"--> Error subiendo archivo: {e}")
    return None

def Tarea_Separar_Audio(job_id: str, temp_path: str):
    try:
        TRABAJOS[job_id] = {"status": "procesando"}

        audio_url = subir_a_host_temporal(temp_path)
        if not audio_url:
            raise Exception("No se pudo subir el archivo temporal para procesar.")

        print(f"--> Procesando URL en Replicate: {audio_url}")

        output = replicate.run(
            "facebookresearch/demucs:e077d4f5a8251a16210db280249281a7b483161099f36f0412b1c73a114f6d4d",
            input={"audio": audio_url}
        )

        print(f"--> [ÉXITO]: {output}")

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
        print(f"--> Error en Replicate: {str(e)}")
        TRABAJOS[job_id] = {"status": "error", "mensaje": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# Rutas dobles (con y sin barra final) para evitar el Error 404
@app.post("/api/separar-audio")
@app.post("/api/separar-audio/")
async def separar_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    if not REPLICATE_API_TOKEN:
        raise HTTPException(status_code=500, detail="Falta REPLICATE_API_TOKEN en Railway")

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
        raise HTTPException(status_code=404, detail=f"Trabajo {job_id} no encontrado")
    return trabajo
