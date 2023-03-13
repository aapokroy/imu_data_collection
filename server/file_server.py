"""
Simple file server using FastAPI.
Handles data from sensor managers and sends it to the user client.
"""

import shutil
import os

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse


app = FastAPI()


@app.get("/ping")
async def ping():
    return {"message": "Server is working"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    with open(file.filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename, "url": f"/download/{file.filename}"}


@app.get("/download/{filename}")
async def download_file(filename: str):
    return FileResponse(filename)


@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    os.remove(filename)
    return {"message": f"File {filename} deleted successfully"}
