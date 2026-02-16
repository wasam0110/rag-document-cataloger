# RAG Document Cataloger

 **A production-ready RAG (Retrieval-Augmented Generation) system with email authentication, intelligent document extraction, and AI-powered Q&A.**

##  Key Features

###  Document Processing

- **Multi-format support**: PDF, DOCX, TXT, CSV
- **Intelligent extraction**:
  - Semantic chunking with overlap for better context
  - Table detection and extraction (with markdown formatting)
  - Section/topic detection (abstract, introduction, methodology, results, etc.)
  - Image/figure tracking
- **Smart indexing**: FAISS vector store for lightning-fast semantic search

###  RAG-Powered Q&A

- **State-of-the-art models**:
  - **Embeddings**: `BAAI/bge-base-en-v1.5` (768-dim, top retrieval quality)
  - **Generation**: `google/flan-t5-xl` (3B params, high-quality answers)
- **Smart retrieval**: Finds the most relevant passages using semantic similarity
- **AI-generated answers**: Context-aware responses with automatic citations `[1], [2]`
- **Interactive chat**: Ask questions and get comprehensive answers with source passages

###  Secure Authentication

- **Email verification**: No passwords stored until verified
- **JWT tokens**: Secure, stateless authentication
- **SMTP integration**: Real email delivery (Gmail-ready)
- **Session management**: Auto-logout, protected API endpoints

###  Modern UI

- **Responsive design**: Works on desktop and mobile
- **Dynamic sections**: Auto-detected document structure
- **Inline PDF viewer**: View documents without downloading
- **Expandable sources**: Toggle between answer and raw passages
- **Real-time feedback**: Loading states, progress indicators

##  Quick Start

### 1. Prerequisites

- **Python 3.8+** (3.11 recommended)
- **Git**

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/wasam0110/rag-document-cataloger.git
cd rag-document-cataloger

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

###  Configuration

Create a `.env` file:

```bash
cp .env.example .env
```

**Required settings:**

```env
# AI Models (Best free models for quality)
HUGGINGFACE_MODEL="google/flan-t5-xl"
EMBEDDING_MODEL="BAAI/bge-base-en-v1.5"
LLM_DEVICE="-1"  # -1 for CPU, 0 for GPU

# Email (Gmail example)
EMAIL_TEST_MODE="false"  # Set to "true" to skip sending emails
SMTP_SERVER="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USERNAME="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"  # Generate at myaccount.google.com/apppasswords
SMTP_FROM_EMAIL="your-email@gmail.com"

# Security (generate with: python -c "import secrets; print(secrets.token_urlsafe(32))")
SECRET_KEY="your-secret-key-here"
```

### 4. Run the Server

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

 Open **http://127.0.0.1:8000** in your browser!

##  Usage

### First-Time Setup

1. Navigate to `http://127.0.0.1:8000`
2. Click **Sign Up** and enter your email + password
3. Check your email for the 6-digit verification code
4. Enter the code to verify and log in

### Upload & Query Documents

1. Click **Upload Document** and select a file (PDF, DOCX, TXT, CSV)
2. Wait for processing (extraction + indexing)
3. Click the document in the sidebar to view sections
4. Use the **Chat** tab to ask questions:
   - _"What is the main conclusion?"_
   - _"Summarize the methodology"_
   - _"What are the key findings?"_
5. View the AI-generated answer with cited passages

##  How RAG Works

```
┌─────────────┐
│   Upload    │
│  Document   │
└─────┬───────┘
      │
      ▼
┌─────────────┐      ┌──────────────┐
│  Extraction │ ───▶ │   Chunking   │
│  (PDF/DOCX) │      │  (Semantic)  │
└─────────────┘      └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Embedding   │
                     │ (bge-base)   │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  FAISS Index │
                     │   (Vector)   │
                     └──────────────┘

        USER QUERY
           │
           ▼
    ┌──────────────┐
    │  Embed Query │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │ FAISS Search │  ───▶  Top 5 passages
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  Flan-T5-XL  │  ───▶  AI Answer + Citations
    │  (Generate)  │
    └──────────────┘
```

##  Tech Stack

| Component          | Technology                      |
| ------------------ | ------------------------------- |
| **Backend**        | FastAPI 0.100+                  |
| **Database**       | SQLite (with foreign keys)      |
| **Authentication** | JWT (python-jose) + Bcrypt      |
| **Email**          | SMTP (Gmail-compatible)         |
| **Embeddings**     | BAAI/bge-base-en-v1.5           |
| **LLM**            | google/flan-t5-xl (HuggingFace) |
| **Vector Store**   | FAISS (CPU)                     |
| **Extraction**     | pdfplumber, python-docx, pandas |
| **Frontend**       | Vanilla JS + Modern CSS         |

##  Model Performance

| Model                     | Size | Quality    | Speed  | Use Case               |
| ------------------------- | ---- | ---------- | ------ | ---------------------- |
| **BAAI/bge-base-en-v1.5** | 109M | ⭐⭐⭐⭐⭐ | Fast   | Embeddings (retrieval) |
| **google/flan-t5-xl**     | 3B   | ⭐⭐⭐⭐   | Medium | Generation (answers)   |

**Upgrade options** (if you have a GPU):

- `google/flan-t5-xxl` (11B) - Best quality, slower
- `mistralai/Mistral-7B-Instruct-v0.2` - Excellent, 7B params

##  Advanced Configuration

### Use GPU for Generation

```env
LLM_DEVICE="0"  # Use first GPU
```

### Adjust Chunk Size

```env
CHUNK_SIZE="500"  # Larger = more context per chunk
CHUNK_OVERLAP="50"  # Larger = more continuity
```

### Email Test Mode (Development)

```env
EMAIL_TEST_MODE="true"  # Codes logged instead of emailed
```

##  Project Structure

```
rag-document-cataloger/
├── app/
│   ├── api/              # API routes
│   │   ├── routes.py     # Document CRUD, query endpoint
│   │   └── auth_routes.py # Login, register, verification
│   ├── core/             # Configuration & logging
│   ├── db/               # SQLite operations
│   ├── models/           # Pydantic schemas
│   ├── services/         # Business logic
│   │   ├── ingest.py     # Document processing pipeline
│   │   ├── query.py      # RAG query handler
│   │   ├── llm.py        # LLM wrapper (generation)
│   │   ├── extract/      # PDF/DOCX/CSV/TXT extractors
│   │   └── index/        # FAISS store
│   └── static/           # Frontend (HTML/CSS/JS)
├── data/                 # SQLite DB + uploads
├── faiss_index/          # Vector indexes (per document)
├── requirements.txt      # Python dependencies
└── .env                  # Configuration (not in git)
```

- **Ask Questions**: Use the query feature to ask questions about the documents.

## Troubleshooting

- Ensure all dependencies are installed correctly.
- Check that Poppler and Tesseract are in your system PATH.
- If OCR is not working, verify that the `ENABLE_OCR` environment variable is set to `true` and that Tesseract is installed.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.
