FROM python:3.10-slim
WORKDIR /app
COPY ../requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY .. /app/subnet
ENV PYTHONPATH=/app
CMD ["python", "-m", "subnet.miner.loop"]

