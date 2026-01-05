FROM python:3.11.4

WORKDIR /app

COPY pyproject.toml .

RUN pip install --upgrade pip \
    && pip install .


COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
