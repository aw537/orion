FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY orion_mcp/ orion_mcp/
RUN pip install --no-cache-dir .
CMD ["orion-mcp"]
