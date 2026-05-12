FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY orion_mcp/ orion_mcp/
RUN pip install --no-cache-dir .
RUN addgroup -S orion && adduser -S orion -G orion
USER orion
CMD ["orion-mcp"]
