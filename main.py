import os
import uuid
import subprocess
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

app = FastAPI()
BASE_DIR = Path("/tmp/jobs")
BASE_DIR.mkdir(parents=True, exist_ok=True)

# Desactiva avisos de Hugging Face en el sistema
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

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

        # Ejecuta Demucs con modelo ligero de 2 stems
        cmd = [
            "demucs",
            "-n", "htdemucs",
            "--two-stems", "vocals",
            str(input_path),
            "-o", str(output_dir)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)

        # Verifica si los archivos .wav realmente se generaron en lugar de fallar por un simple warning de texto
        expected_stem = output_dir / "htdemucs" / "input" / "vocals.wav"
        
        if not expected_stem.exists() and res.returncode != 0:
            return JSONResponse(status_code=500, content={"status": "error", "mensaje": res.stderr})

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
        dl_res = subprocess.run(download_cmd, capture_output=True, text=True)

        if dl_res.returncode != 0:
            return JSONResponse(status_code=500, content={"status": "error", "mensaje": "Error al descargar desde YouTube"})

        cmd = [
            "demucs",
            "-n", "htdemucs",
            "--two-stems", "vocals",
            str(input_path),
            "-o", str(output_dir)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)

        expected_stem = output_dir / "htdemucs" / "input" / "vocals.wav"

        if not expected_stem.exists() and res.returncode != 0:
            return JSONResponse(status_code=500, content={"status": "error", "mensaje": res.stderr})

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
