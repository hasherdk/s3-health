FROM mcr.microsoft.com/devcontainers/python:1-3.12-bullseye
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY src /workspace/src
EXPOSE 8000
CMD ["python", "/workspace/src/main.py"]
