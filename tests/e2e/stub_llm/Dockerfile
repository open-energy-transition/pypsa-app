# Stub-LLM container image
# Used by E2E tests when no live LLM is available.
# Built from tests/e2e/stub-llm/ context.

FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn

# Match the repo import path so __main__.py can import from tests.e2e.stub_llm.app
COPY app.py __init__.py __main__.py tests/e2e/stub_llm/

EXPOSE 8001

CMD ["python", "-m", "tests.e2e.stub_llm"]
