# Real Estate RAG ChatBot

Simple Retrieval-Augmented Generation (RAG) demo using FastAPI, LangChain and Chroma. This README explains how to ingest sample data, build and run with Docker, and access the API.

## Overview
- Sample dataset is provided in the `/data` folder. To use your own data, replace files in `/data` with the same format as the samples.
- You must run the ingestion step first to populate the vector store before starting the API.

## Prerequisites
- Docker (Desktop) and optionally Docker Compose
- .env (copy from `.env.example` and edit required variables)

## Prepare .env
Copy and edit:
```sh
copy .env.example .env        # Windows cmd
# or
cp .env.example .env         # PowerShell / WSL
```
Set required values (e.g., OPENAI_API_KEY, DATA_API_URL, API_TOKEN, PERSIST_DIR).

## Build Docker image
From project root (d:\Project\RagBotPython):
```sh
docker build -t rag-bot .
```

## Ingest data (required first step)
Run ingestion inside the built image. This must be done before starting the API.

- PowerShell (recommended on Windows):
```powershell
docker run --rm -it --env-file .env -v ${PWD}:/app -w /app rag-bot python ingest.py --use-openai
```

- CMD (Windows):
```cmd
docker run --rm -it --env-file .env -v %cd%:/app -w /app rag-bot python ingest.py --use-openai
```

- If using Docker Compose (replace `app` with the service name in your compose file):
```sh
docker-compose run --rm --env-file .env app python ingest.py --use-openai
```

Notes:
- The command mounts the project into the container so ingest uses `/data` inside the project.
- If you prefer local Python, run: `python ingest.py --use-openai` after activating your virtualenv and installing requirements.

## Run the API server (Docker)
After ingest completes, start the container mapping port 8000:

```sh
docker run --env-file .env -p 8000:8000 --name rag-bot -d rag-bot
docker logs -f rag-bot
```

To stop and remove:
```sh
docker stop rag-bot && docker rm rag-bot
```

With Docker Compose:
```sh
docker-compose --env-file .env up -d --build
docker-compose logs -f
```

## API endpoints
- Health:
```sh
curl http://localhost:8000/health
```

- Question (POST /question_hook):
Request JSON example:
```json
{
  "sender_id": "111",
  "sender_name": "Tester",
  "question": "Find houses for sale near Ringroad",
  "method": "hybrid"
}
```

Curl example:
```sh
curl -X POST http://localhost:8000/question_hook \
  -H "Content-Type: application/json" \
  -d "{\"sender_id\":\"111\",\"sender_name\":\"Tester\",\"question\":\"Find houses for sale near Ringroad\",\"method\":\"hybrid\"}"
```

Supported methods: `vector`, `api`, `hybrid` (depending on project code).

## Replace dataset
- Provided sample: `/data`
- To use your own data, replace files in `/data` with the same filenames/format as the samples, then re-run the ingest step.

## Troubleshooting
- If ingest fails, check `.env` and OPENAI/API keys.
- Inspect container logs: `docker logs -f rag-bot`
- Ensure `PERSIST_DIR` in `.env` points to a writable path inside the container (default persists inside project mount).

## Local (no Docker) quick run
```sh
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
python ingest.py --use-openai
uvicorn app:app --host 0.0.0.0 --port 8000
```

End.