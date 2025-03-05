# syntax=docker/dockerfile:1

# Comments are provided throughout this file to help you get started.
# If you need more help, visit the Dockerfile reference guide at
# https://docs.docker.com/engine/reference/builder/

ARG PYTHON_VERSION=3.12.0

FROM python:${PYTHON_VERSION}-slim AS build

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# copy the content of the local src directory to the working directory
COPY src/ .

# Install dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Using the distroless python3-debian12:nonroot image
FROM gcr.io/distroless/python3-debian12@sha256:66f3e24fd4906156a7360d2861731d31d3457a02f34fd3c4491f0b710a259988 AS runtime

ENV PYTHONPATH=/usr/local/lib/python3.12/site-packages

COPY --from=build /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=build /app /app

WORKDIR /app

# Run the application.
CMD ["main.py"]
