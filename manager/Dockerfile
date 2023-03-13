FROM arm32v7/python:3.10-slim-buster
WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY ./imu_manager ./imu_manager
CMD ["python3", "-m", "imu_manager"]