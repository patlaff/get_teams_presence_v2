FROM python:3.9.7-slim-buster

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential # python-dev libssl-dev openssl

COPY ./ .

RUN pip3 install -r requirements.txt

# ENV CELERY_BROKER_URL=redis://redis:6379/0

RUN celery -A app worker -l DEBUG
RUN celery -A app beat -l DEBUG

CMD ["python3", "-m" , "flask", "run", "--host=0.0.0.0" "--port=5000"]