FROM python:3.10-slim
WORKDIR /app
COPY ../requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY .. /app/subnet
ENV PYTHONPATH=/app
EXPOSE 8002
CMD ["uvicorn", "subnet.validator.api:app", "--host", "0.0.0.0", "--port", "8002"]

