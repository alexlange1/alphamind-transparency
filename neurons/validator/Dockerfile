FROM python:3.11-slim
WORKDIR /app
COPY ../requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY .. /app/subnet
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "subnet.validator.api:app", "--host", "0.0.0.0", "--port", "8000"]

