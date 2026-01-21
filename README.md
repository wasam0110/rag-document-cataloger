# RAG Document Cataloger

## Overview
The RAG Document Cataloger is a web application that allows users to upload documents (PDF, DOCX, TXT, CSV) and extracts their content for categorization and indexing. The application utilizes FastAPI for the backend, LangChain for the RAG framework, and FAISS for vector storage. It provides a simple user interface for document management and querying.

## Features
- Upload documents and extract content.
- Perform OCR on scanned PDFs.
- Categorize documents into topics, tables, chunks, figures, and keywords.
- Index extracted content in a local FAISS vector store.
- Search and retrieve answers from documents with citations.

## Requirements
- Python 3.8 or higher
- Poppler for PDF processing (required for `pdf2image`)
- Tesseract OCR (required for OCR functionality)

## Setup Instructions

### Windows Setup
1. **Install Python**: Download and install Python from the official website. Ensure that Python is added to your PATH.
2. **Install Poppler**:
   - Download the latest Poppler binaries for Windows from [this link](http://blog.alivate.com.au/poppler-windows/).
   - Extract the files and add the `bin` directory to your system PATH.
3. **Install Tesseract OCR**:
   - Download the Tesseract installer from [this link](https://github.com/UB-Mannheim/tesseract/wiki).
   - Install Tesseract and add its installation path to your system PATH.
4. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd rag-document-cataloger
   ```
5. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Environment Variables
- Create a `.env` file based on the `.env.example` provided in the root directory. Set the necessary environment variables.

### Running the Application
To start the application, run the following command:
```bash
uvicorn app.main:app --reload
```
The application will be accessible at `http://127.0.0.1:8000`.

### Usage
- **Upload Documents**: Use the web interface to upload documents.
- **View Catalog**: Load the catalog to see the categorized documents.
- **Ask Questions**: Use the query feature to ask questions about the documents.

## Troubleshooting
- Ensure all dependencies are installed correctly.
- Check that Poppler and Tesseract are in your system PATH.
- If OCR is not working, verify that the `ENABLE_OCR` environment variable is set to `true` and that Tesseract is installed.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.