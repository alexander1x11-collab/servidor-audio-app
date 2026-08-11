import os
import uuid
import subprocess
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

# Desactiva avisos y limites de librerías en la consola
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["PYTHONWARNINGS"] = "ignore"

app = FastAPI()
BASE_DIR = Path("/tmp/jobs")
BASE_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/")
def home():
    return {"status": "ok", "mensaje": "Servidor Activo"}

@app.post("/separate")
async def separate(file: UploadFile = File(...)):
    try:
        job_id = str(uuid.uuid4())[:8]
        job_dir = BASE_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        input_path = job_dir / "input.mp3"
        output_dir = job_dir / "output"

        with open(input_path, "wb") as f:
            f.write(await file.read())

        # Ejecución limpia de Demucs
        cmd = [
            "demucs",
            "-n", "htdemucs",
            "--two-stems", "vocals",
            str(input_path),
            "-o", str(output_dir)
        ]
        
        # Redirige el flujo de errores de texto para evitar falsos positivos
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Revisa únicamente si el archivo final .wav fue generado exitosamente
        expected_stem = output_dir / "htdemucs" / "input" / "vocals.wav"

        if not expected_stem.exists():
            return JSONResponse(status_code=500, content={"status": "error", "mensaje": "No se pudo procesar el archivo de audio."})

        return {
            "status": "exito",
            "job_id": job_id,
            "stems": {
                "vocals": f"/get-stem?job_id={job_id}&pista=vocals",
                "drums": f"/get-stem?job_id={job_id}&pista=no_vocals",
                "bass": f"/get-stem?job_id={job_id}&pista=no_vocals",
                "other": f"/get-stem?job_id={job_id}&pista=no_vocals"
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "mensaje": str(e)})

@app.post("/separate-youtube")
async def separate_youtube(url: str = Form(...)):
    try:
        job_id = str(uuid.uuid4())[:8]
        job_dir = BASE_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        input_path = job_dir / "input.mp3"
        output_dir = job_dir / "output"

        download_cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "-o", str(input_path),
            url
        ]
        subprocess.run(download_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        cmd = [
            "demucs",
            "-n", "htdemucs",
            "--two-stems", "vocals",
            str(input_path),
            "-o", str(output_dir)
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        expected_stem = output_dir / "htdemucs" / "input" / "vocals.wav"

        if not expected_stem.exists():
            return JSONResponse(status_code=500, content={"status": "error", "mensaje": "No se pudo procesar la canción desde YouTube."})

        return {
            "status": "exito",
            "job_id": job_id,
            "stems": {
                "vocals": f"/get-stem?job_id={job_id}&pista=vocals",
                "drums": f"/get-stem?job_id={job_id}&pista=no_vocals",
                "bass": f"/get-stem?job_id={job_id}&pista=no_vocals",
                "other": f"/get-stem?job_id={job_id}&pista=no_vocals"
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "mensaje": str(e)})

@app.get("/get-stem")
def get_stem(job_id: str, pista: str = "vocals"):
    stem_path = BASE_DIR / job_id / "output" / "htdemucs" / "input" / f"{pista}.wav"
    if stem_path.exists():
        return FileResponse(str(stem_path), media_type="audio/wav")
    return JSONResponse(status_code=404, content={"status": "error", "mensaje": f"Pista '{pista}' no encontrada"})
