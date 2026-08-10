import modal
import os

image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "requests",
    "replicate"
)

app = modal.App("audio-separation-backend", image=image)
replicate_secret = modal.Secret.from_name("replicate-secret")

TRABAJOS = {}

@app.function(secrets=[replicate_secret])
def Tarea_Separar_Audio_Task(job_id: str, audio_bytes: bytes):
    import replicate
    import tempfile

    try:
        TRABAJOS[job_id] = {"status": "procesando"}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        with open(temp_path, "rb") as audio_file:
            output = replicate.run(
                "facebookresearch/demucs",
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
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)

@app.function(secrets=[replicate_secret])
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware

    web_app = FastAPI(title="Servidor Audio Modal")

    web_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @web_app.get("/")
    def home():
        return {"status": "online", "mensaje": "Servidor Modal activo"}

    @web_app.post("/api/separar-audio")
    @web_app.post("/api/separar-audio/")
    async def separar_audio(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...)
    ):
        content = await file.read()
        job_id = str(abs(hash(str(content[:100]) + str(os.urandom(8)))))
        TRABAJOS[job_id] = {"status": "pendiente"}

        Tarea_Separar_Audio_Task.spawn(job_id, content)

        return {"status": "exito", "job_id": job_id}

    @web_app.get("/api/estado-trabajo/{job_id}")
    @web_app.get("/api/estado-trabajo/{job_id}/")
    def obtener_estado(job_id: str):
        trabajo = TRABAJOS.get(str(job_id).strip())
        if not trabajo:
            return {"status": "error", "mensaje": "El trabajo no fue encontrado."}
        return trabajo

    return web_app
