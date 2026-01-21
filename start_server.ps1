# RAG Document Cataloger Server Startup Script
$ErrorActionPreference = "Stop"

# Set working directory
Set-Location "c:\Users\Wasam\rag-document-cataloger"

# Set PYTHONPATH
$env:PYTHONPATH = "c:\Users\Wasam\rag-document-cataloger"

# Activate virtual environment and start server
Write-Host "Starting RAG Document Cataloger server..." -ForegroundColor Green
& "c:\Users\Wasam\rag-document-cataloger\venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
