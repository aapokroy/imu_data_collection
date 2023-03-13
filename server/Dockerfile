FROM python:3.8-slim-buster
WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY file_server.py .
EXPOSE 8000
CMD ["uvicorn", "file_server:app", "--host", "0.0.0.0", "--port", "8000"]