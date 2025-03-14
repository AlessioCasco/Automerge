FROM debian:12-slim AS build

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes python3-venv gcc libpython3-dev && \
    python3 -m venv /venv && \
    /venv/bin/pip install --upgrade pip setuptools wheel

FROM build AS build-venv
COPY requirements.txt .
RUN /venv/bin/pip install --disable-pip-version-check -r /requirements.txt

# Using the distroless python3-debian12:nonroot image
FROM gcr.io/distroless/python3-debian12@sha256:66f3e24fd4906156a7360d2861731d31d3457a02f34fd3c4491f0b710a259988 AS runtime
COPY --from=build-venv /venv /venv
# copy the content of the local src directory to the working directory
COPY src/ /app

WORKDIR /app

# Run the application.
ENTRYPOINT [ "/venv/bin/python3", "main.py"]
