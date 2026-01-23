// RAG Document Cataloger - Frontend Application
// Dynamic categories, inline PDF viewer, smart extraction display

let currentDocId = null;
let currentDocFilename = null;
let currentCategories = [];
let currentSections = {};

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', function () {
    initEventListeners();
    loadDocuments();
});

function initEventListeners() {
    // Upload form
    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }

    // Drag and drop
    const dropZone = document.getElementById('drop-zone');
    if (dropZone) {
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('dragover');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length) {
                document.getElementById('file-input').files = files;
                // Show filename
                showSelectedFile(files[0].name);
            }
        });

        // Click to select
        dropZone.addEventListener('click', () => {
            document.getElementById('file-input').click();
        });
    }

    // File input change
    const fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                showSelectedFile(e.target.files[0].name);
            }
        });
    }

    // Refresh button
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadDocuments);
    }

    // Modal close buttons
    document.getElementById('modal-close')?.addEventListener('click', () => closeModal('content-modal'));
    document.getElementById('pdf-modal-close')?.addEventListener('click', () => closeModal('pdf-modal'));

    // Modal overlay clicks
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            e.target.closest('.modal').classList.remove('show');
        });
    });

    // Chat
    const chatSend = document.getElementById('chat-send');
    if (chatSend) {
        chatSend.addEventListener('click', sendChatMessage);
    }

    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendChatMessage();
        });
    }
}

function showSelectedFile(filename) {
    const uploadText = document.querySelector('.upload-text');
    if (uploadText) {
        uploadText.textContent = filename;
        uploadText.style.color = '#4a7c59';
    }
}

// Upload handler
async function handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('file-input');
    const file = fileInput?.files[0];

    if (!file) {
        showStatus('Please select a file', 'error');
        return;
    }

    showStatus('Processing document... This may take a moment.', 'loading');
    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<span class="loading-spinner-small"></span> Processing...';
    }

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showStatus(`Document processed! ${data.counts?.chunks || 0} chunks extracted.`, 'success');
            fileInput.value = '';

            // Reset upload text
            const uploadText = document.querySelector('.upload-text');
            if (uploadText) {
                uploadText.textContent = 'Drop file here or click to browse';
                uploadText.style.color = '';
            }

            // Reload documents list
            await loadDocuments();

            // Auto-select the new document
            loadDocument(data.doc_id, file.name);
        } else {
            showStatus('Error: ' + (data.detail || 'Upload failed'), 'error');
        }
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
    } finally {
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<span>Upload & Process</span>';
        }
    }
}

function showStatus(message, type) {
    const status = document.getElementById('upload-status');
    if (status) {
        status.textContent = message;
        status.className = 'status show ' + type;

        if (type === 'success') {
            setTimeout(() => {
                status.classList.remove('show');
            }, 5000);
        }
    }
}

// Load documents list
async function loadDocuments() {
    const container = document.getElementById('documents-list');
    if (!container) return;

    container.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><p>Loading documents...</p></div>';

    try {
        const response = await fetch('/api/documents');
        const data = await response.json();

        if (response.ok && data.success) {
            renderDocumentsList(data.documents);
        } else {
            container.innerHTML = '<div class="empty-state">Error loading documents</div>';
        }
    } catch (error) {
        container.innerHTML = '<div class="empty-state">Error loading documents</div>';
    }
}

function renderDocumentsList(documents) {
    const container = document.getElementById('documents-list');
    if (!container) return;

    if (!documents || documents.length === 0) {
        container.innerHTML = '<div class="empty-state">No documents uploaded yet. Upload a document to get started.</div>';
        return;
    }

    container.innerHTML = documents.map(doc => {
        const isActive = currentDocId === doc.doc_id;
        const chunks = doc.chunks_count || 0;
        const tables = doc.tables_count || 0;
        const topics = doc.topics_count || 0;

        return `
            <div class="document-item ${isActive ? 'active' : ''}" 
                 onclick="loadDocument('${doc.doc_id}', '${escapeHtml(doc.filename)}')">
                <div class="document-icon">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                        <polyline points="14 2 14 8 20 8"></polyline>
                    </svg>
                </div>
                <div class="document-info">
                    <h4>${escapeHtml(doc.filename)}</h4>
                    <p>${doc.filetype.toUpperCase()} • ${chunks} chunks • ${topics} sections</p>
                </div>
                <button class="document-delete" onclick="event.stopPropagation(); deleteDocument('${doc.doc_id}')" title="Delete">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        `;
    }).join('');
}

// Load document details with dynamic categories
async function loadDocument(docId, filename) {
    currentDocId = docId;
    currentDocFilename = filename;

    // Update UI
    document.getElementById('welcome-state').classList.add('hidden');
    document.getElementById('document-view').classList.remove('hidden');
    document.getElementById('document-title').textContent = filename;

    // Update active state in list
    document.querySelectorAll('.document-item').forEach(item => {
        item.classList.remove('active');
        if (item.onclick && item.onclick.toString().includes(docId)) {
            item.classList.add('active');
        }
    });

    // Show loading in tabs area
    const tabsContainer = document.getElementById('section-tabs');
    const tabContents = document.getElementById('tab-contents');

    if (tabsContainer) {
        tabsContainer.innerHTML = '<div class="loading-spinner"></div>';
    }
    if (tabContents) {
        tabContents.innerHTML = '';
    }

    // Reset chat
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="chat-welcome">
                <p>Ask me anything about this document. I can help you understand the content, find specific information, or summarize sections.</p>
            </div>
        `;
    }

    // Load sections with dynamic categories
    try {
        const response = await fetch(`/api/documents/${docId}/sections`);
        const data = await response.json();

        if (response.ok && data.success) {
            currentCategories = data.categories || [];
            currentSections = data.sections || {};

            // Build dynamic tabs
            renderDynamicTabs(currentCategories, currentSections);

            // Update document meta
            const meta = document.getElementById('document-meta');
            if (meta) {
                meta.textContent = `${currentCategories.length} sections detected`;
            }
        } else {
            tabsContainer.innerHTML = '<div class="empty-state">Error loading document sections</div>';
        }
    } catch (error) {
        console.error('Error loading sections:', error);
        tabsContainer.innerHTML = '<div class="empty-state">Error loading document sections</div>';
    }
}

function renderDynamicTabs(categories, sections) {
    const tabsContainer = document.getElementById('section-tabs');
    const tabContents = document.getElementById('tab-contents');

    if (!tabsContainer || !tabContents) return;

    // Filter categories that have content
    const categoriesWithContent = categories.filter(cat => {
        const items = sections[cat];
        return items && items.length > 0;
    });

    if (categoriesWithContent.length === 0) {
        tabsContainer.innerHTML = '<div class="empty-state">No content sections found</div>';
        tabContents.innerHTML = '';
        return;
    }

    // Create tab buttons
    tabsContainer.innerHTML = categoriesWithContent.map((cat, idx) => {
        const displayName = formatCategoryName(cat);
        const count = sections[cat]?.length || 0;
        return `
            <button class="tab-btn ${idx === 0 ? 'active' : ''}" data-tab="${cat}">
                ${displayName} <span class="tab-count">(${count})</span>
            </button>
        `;
    }).join('');

    // Create tab content areas
    tabContents.innerHTML = categoriesWithContent.map((cat, idx) => {
        return `
            <div class="tab-content ${idx === 0 ? 'active' : ''}" id="${cat}-tab">
                <div id="${cat}-content" class="section-content"></div>
            </div>
        `;
    }).join('');

    // Add click handlers to tabs
    tabsContainer.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', handleTabClick);
    });

    // Render content for each category
    categoriesWithContent.forEach(cat => {
        const items = sections[cat] || [];
        if (cat === 'tables') {
            renderTablesSection(items);
        } else if (cat === 'images') {
            renderImagesSection(items);
        } else {
            renderTextSection(cat, items);
        }
    });
}

function formatCategoryName(category) {
    // Convert category name to display format
    if (!category) return 'Other';

    // Handle page_X format
    if (category.startsWith('page_')) {
        return `Page ${category.replace('page_', '')}`;
    }

    // Title case
    return category
        .split(/[\s_-]+/)
        .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
        .join(' ');
}

function renderTextSection(sectionType, items) {
    const container = document.getElementById(`${sectionType}-content`);
    if (!container) return;

    const sectionName = formatCategoryName(sectionType);

    if (!items || items.length === 0) {
        container.innerHTML = `<div class="empty-section">No ${sectionName} content found</div>`;
        return;
    }

    container.innerHTML = items.map(item => {
        const page = item.start_page || item.page_number || 1;
        const content = item.content || '';
        const title = item.title || sectionName;
        const preview = content.length > 400 ? content.substring(0, 400) + '...' : content;

        return `
            <div class="section-card">
                <div class="section-card-header">
                    <span class="section-card-title">${escapeHtml(title)}</span>
                    <span class="section-card-page">Page ${page}</span>
                </div>
                <div class="section-card-content">${escapeHtml(preview)}</div>
                <div class="section-card-actions">
                    <button class="btn btn-primary" onclick="viewContent('${escapeAttr(title)}', \`${escapeTemplate(content)}\`)">
                        View Full Content
                    </button>
                    <button class="btn btn-secondary" onclick="openPdfAtPage(${page})">
                        View in PDF
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function renderTablesSection(tables) {
    const container = document.getElementById('tables-content');
    if (!container) return;

    if (!tables || tables.length === 0) {
        container.innerHTML = '<div class="empty-section">No tables found in this document</div>';
        return;
    }

    container.innerHTML = `<div class="tables-grid">${tables.map(table => {
        const page = table.page_number || 1;
        return `
            <div class="table-card section-card">
                <div class="section-card-header">
                    <span class="section-card-title">Table ${(table.table_index || 0) + 1}</span>
                    <span class="section-card-page">Page ${page}</span>
                </div>
                <div class="section-card-content">
                    ${table.rows_count || 0} rows × ${table.cols_count || 0} columns
                </div>
                <div class="section-card-actions">
                    <button class="btn btn-primary" onclick="viewTable('${table.table_id}')">View Table</button>
                    <button class="btn btn-secondary" onclick="openPdfAtPage(${page})">View in PDF</button>
                </div>
            </div>
        `;
    }).join('')}</div>`;
}

function renderImagesSection(images) {
    const container = document.getElementById('images-content');
    if (!container) return;

    if (!images || images.length === 0) {
        container.innerHTML = '<div class="empty-section">No images found in this document</div>';
        return;
    }

    container.innerHTML = `<div class="images-grid">${images.map(image => {
        const page = image.page_number || 1;
        return `
            <div class="image-card">
                <div class="image-card-info">
                    <div class="section-card-header">
                        <span class="section-card-title">Image ${(image.image_index || 0) + 1}</span>
                        <span class="section-card-page">Page ${page}</span>
                    </div>
                    <div class="section-card-actions" style="margin-top: 12px;">
                        <button class="btn btn-secondary" onclick="openPdfAtPage(${page})">View in PDF</button>
                    </div>
                </div>
            </div>
        `;
    }).join('')}</div>`;
}

// Tab handling
function handleTabClick(e) {
    const tabId = e.target.closest('.tab-btn')?.dataset.tab;
    if (!tabId) return;

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    e.target.closest('.tab-btn').classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(`${tabId}-tab`)?.classList.add('active');
}

// Modal functions
function viewContent(title, content) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = `<div style="white-space: pre-wrap; line-height: 1.8;">${escapeHtml(content)}</div>`;
    document.getElementById('content-modal').classList.add('show');
}

async function viewTable(tableId) {
    document.getElementById('modal-title').textContent = 'Table';
    document.getElementById('modal-body').innerHTML = '<div class="loading-spinner"></div>';
    document.getElementById('content-modal').classList.add('show');

    try {
        const response = await fetch(`/api/tables/${tableId}`);
        const data = await response.json();

        if (response.ok && data.success) {
            const tableText = data.table_text || 'No content';
            // Try to render markdown table or show as preformatted
            document.getElementById('modal-body').innerHTML = `
                <div class="table-view">
                    <pre style="overflow-x: auto; white-space: pre-wrap;">${escapeHtml(tableText)}</pre>
                </div>
            `;
        } else {
            document.getElementById('modal-body').innerHTML = '<p>Error loading table</p>';
        }
    } catch (error) {
        document.getElementById('modal-body').innerHTML = '<p>Error loading table</p>';
    }
}

function openPdfAtPage(page) {
    if (!currentDocId) return;

    document.getElementById('pdf-modal-title').textContent = `${currentDocFilename} - Page ${page}`;

    // Use page fragment for PDF.js compatible viewers
    // The #page=X parameter tells the browser's PDF viewer to go to that page
    const pdfUrl = `/api/pdf/${currentDocId}#page=${page}`;
    document.getElementById('pdf-iframe').src = pdfUrl;
    document.getElementById('pdf-modal').classList.add('show');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        // Clear PDF iframe to stop loading
        if (modalId === 'pdf-modal') {
            document.getElementById('pdf-iframe').src = '';
        }
    }
}

// Chat - Query documents
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const messages = document.getElementById('chat-messages');

    if (!input || !messages || !input.value.trim() || !currentDocId) return;

    const message = input.value.trim();
    input.value = '';

    // Remove welcome message
    const welcome = messages.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // Add user message
    messages.innerHTML += `
        <div class="chat-message user">
            <div class="chat-bubble">${escapeHtml(message)}</div>
        </div>
    `;

    // Add loading message
    const loadingId = 'loading-' + Date.now();
    messages.innerHTML += `
        <div class="chat-message assistant" id="${loadingId}">
            <div class="chat-bubble"><div class="loading-spinner-small"></div> Searching document...</div>
        </div>
    `;
    messages.scrollTop = messages.scrollHeight;

    try {
        const response = await fetch(`/api/query?doc_id=${currentDocId}&query=${encodeURIComponent(message)}&top_k=5`);
        const data = await response.json();

        // Remove loading
        document.getElementById(loadingId)?.remove();

        if (response.ok && data.success && data.results && data.results.length > 0) {
            // Format results
            const answer = data.results.map((r, i) => {
                const page = r.page || r.metadata?.page || 'N/A';
                const content = r.content || r.text || '';
                return `**Result ${i + 1}** (Page ${page}):\n${content}`;
            }).join('\n\n---\n\n');

            messages.innerHTML += `
                <div class="chat-message assistant">
                    <div class="chat-bubble">${formatChatResponse(answer)}</div>
                </div>
            `;
        } else {
            messages.innerHTML += `
                <div class="chat-message assistant">
                    <div class="chat-bubble">I couldn't find relevant information for your query in this document. Try rephrasing your question or being more specific.</div>
                </div>
            `;
        }
    } catch (error) {
        document.getElementById(loadingId)?.remove();
        messages.innerHTML += `
            <div class="chat-message assistant">
                <div class="chat-bubble">Error searching document: ${error.message}</div>
            </div>
        `;
    }

    messages.scrollTop = messages.scrollHeight;
}

function formatChatResponse(text) {
    // Basic markdown formatting
    return escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

// Delete document
async function deleteDocument(docId) {
    if (!confirm('Are you sure you want to delete this document?')) return;

    try {
        const response = await fetch(`/api/documents/${docId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            await loadDocuments();
            if (currentDocId === docId) {
                document.getElementById('welcome-state').classList.remove('hidden');
                document.getElementById('document-view').classList.add('hidden');
                currentDocId = null;
                currentDocFilename = null;
                currentCategories = [];
                currentSections = {};
            }
        } else {
            alert('Error deleting document');
        }
    } catch (error) {
        alert('Error deleting document: ' + error.message);
    }
}

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function escapeAttr(text) {
    if (!text) return '';
    return String(text).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function escapeTemplate(text) {
    if (!text) return '';
    return String(text).replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$');
}
