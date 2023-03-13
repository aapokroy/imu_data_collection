FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt
COPY ./.streamlit ./.streamlit
COPY ./user_client ./user_client
RUN mkdir ./sessions
EXPOSE 8080
CMD ["streamlit", "run", "user_client/site.py"]