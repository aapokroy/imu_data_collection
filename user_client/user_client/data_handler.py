"""
Simple FastAPI server for transfering session data from sensor managers
to the user client.
"""


import os
import zipfile
import logging

import uvicorn
from fastapi import File, UploadFile, FastAPI, Request, Form

from config import Config


cfg = Config('./config.yml')


app = FastAPI()


@app.post("/upload")
async def upload(request: Request,
                 session_name: str = Form(...),
                 file: UploadFile = File(...)):
    if request.headers.get('Type') == "session_part":
        session_dir = os.path.join(cfg.path.sessions, session_name)
        if not os.path.isdir(cfg.path.sessions):
            os.mkdir(cfg.path.sessions)
        if not os.path.isdir(session_dir):
            os.mkdir(session_dir)
        try:
            contents = await file.read()
            file_path = os.path.join(session_dir, file.filename)
            with open(file_path, 'wb') as f:
                f.write(contents)
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(session_dir)
            os.remove(file_path)
        except Exception as e:
            logging.error(f'Error while uploading file: {e}')
        finally:
            await file.close()

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=cfg.data_handler.port)
