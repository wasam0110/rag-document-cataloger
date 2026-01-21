let currentDocId = null;
let currentTableData = null;

function onEl(id, eventName, handler) {
    const el = document.getElementById(id);
    if (!el) {
        console.warn(`Missing element #${id}`);
        return;
    }
    el.addEventListener(eventName, handler);
}

document.addEventListener('DOMContentLoaded', function () {
    initEventListeners();
    loadDocuments();
});

function initEventListeners() {
    onEl('upload-form', 'submit', handleUpload);
    onEl('refresh-docs-btn', 'click', loadDocuments);

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', handleTabClick);
    });

    onEl('modal-close', 'click', closeTableModal);
    onEl('pdf-modal-close', 'click', closePdfModal);
    onEl('open-pdf-btn', 'click', openInPdf);
    onEl('view-inline-btn', 'click', viewInline);

    const tableModal = document.getElementById('table-modal');
    if (tableModal) {
        tableModal.addEventListener('click', function (e) {
            if (e.target === this) closeTableModal();
        });
    }

    const pdfModal = document.getElementById('pdf-modal');
    if (pdfModal) {
        pdfModal.addEventListener('click', function (e) {
            if (e.target === this) closePdfModal();
        });
    }
}

async function handleUpload(e) {
    e.preventDefault();

    const fileInput = document.getElementById('file-input');
    const file = fileInput ? fileInput.files[0] : null;

    if (!file) {
        showStatus('Please select a file', 'error');
        return;
    }

    showStatus('Uploading and processing document...', 'loading');

    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) uploadBtn.disabled = true;

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok && data.success) {
            const counts = data.counts;
            showStatus(
                `✅ Uploaded! Chunks: ${counts.chunks}, Tables: ${counts.tables}`,
                'success'
            );
            fileInput.value = '';
            loadDocuments();
            loadCatalog(data.doc_id);
        } else {
            showStatus(`❌ Error: ${data.detail || 'Upload failed'}`, 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showStatus(`❌ Network error: ${error.message}`, 'error');
    } finally {
        if (uploadBtn) uploadBtn.disabled = false;
    }
}

function showStatus(message, type) {
    const status = document.getElementById('upload-status');
    if (!status) return;
    status.textContent = message;
    status.className = 'status ' + type;
}

async function loadDocuments() {
    const container = document.getElementById('documents-list');
    if (!container) return;

    container.innerHTML = '<p>Loading...</p>';

    try {
        const response = await fetch('/api/documents');
        const data = await response.json();

        if (response.ok && data.success) {
            renderDocumentsList(data.documents);
        } else {
            container.innerHTML = '<p>Error loading documents</p>';
        }
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = '<p>Error loading documents</p>';
    }
}

function renderDocumentsList(documents) {
    const container = document.getElementById('documents-list');
    if (!container) return;

    if (!documents || documents.length === 0) {
        container.innerHTML = '<p>No documents uploaded yet.</p>';
        return;
    }

    let html = '';
    for (const doc of documents) {
        html += `
            <div class="document-item" data-doc-id="${doc.doc_id}">
                <div class="document-info">
                    <h4>${escapeHtml(doc.filename)}</h4>
                    <p>Type: ${doc.filetype} | Tables: ${doc.tables_count} | Chunks: ${doc.chunks_count}</p>
                </div>
                <div class="document-actions">
                    <button class="view-btn" onclick="loadCatalog('${doc.doc_id}')">📋 View</button>
                    <button class="delete-btn" onclick="deleteDocument('${doc.doc_id}')">🗑️</button>
                </div>
            </div>
        `;
    }
    container.innerHTML = html;
}

async function loadCatalog(docId) {
    currentDocId = docId;

    const catalogSection = document.getElementById('catalog-section');
    if (catalogSection) catalogSection.classList.remove('hidden');

    const catalogHeader = document.getElementById('catalog-header');
    const catalogCounts = document.getElementById('catalog-counts');
    const tablesGallery = document.getElementById('tables-gallery');

    if (catalogHeader) catalogHeader.innerHTML = '<p>Loading...</p>';
    if (catalogCounts) catalogCounts.innerHTML = '';
    if (tablesGallery) tablesGallery.innerHTML = '';

    try {
        const response = await fetch(`/api/catalog/${docId}`);
        const data = await response.json();

        if (response.ok && data.success) {
            renderCatalog(data);
        } else {
            if (catalogHeader) catalogHeader.innerHTML = '<p>Error loading catalog</p>';
        }
    } catch (error) {
        console.error('Error:', error);
        if (catalogHeader) catalogHeader.innerHTML = '<p>Error loading catalog</p>';
    }

    if (catalogSection) catalogSection.scrollIntoView({ behavior: 'smooth' });
}

function renderCatalog(data) {
    const header = document.getElementById('catalog-header');
    if (header) {
        header.innerHTML = `
            <h3>${escapeHtml(data.document.filename)}</h3>
            <p>Type: ${data.document.filetype}</p>
        `;
    }

    const counts = data.counts;
    const countsContainer = document.getElementById('catalog-counts');
    if (countsContainer) {
        countsContainer.innerHTML = `
            <div class="count-card"><div class="count">${counts.tables}</div><div class="label">Tables</div></div>
            <div class="count-card"><div class="count">${counts.chunks}</div><div class="label">Chunks</div></div>
            <div class="count-card"><div class="count">${counts.topics}</div><div class="label">Topics</div></div>
            <div class="count-card"><div class="count">${counts.keywords}</div><div class="label">Keywords</div></div>
        `;
    }

    renderTablesGallery(data.tables);
    renderTopics(data.topics);
    renderKeywords(data.keywords);
}

function renderTablesGallery(tables) {
    const container = document.getElementById('tables-gallery');
    if (!container) return;

    if (!tables || tables.length === 0) {
        container.innerHTML = '<p>No tables detected.</p>';
        return;
    }

    let html = '';
    for (const table of tables) {
        const thumbnailHtml = table.thumbnail_url
            ? `<img src="${table.thumbnail_url}" alt="Table" loading="lazy">`
            : `<div class="no-thumbnail">📊</div>`;

        html += `
            <div class="gallery-item" onclick="openTableModal('${table.table_id}')">
                ${thumbnailHtml}
                <div class="item-info">
                    <h5>Table ${(table.table_index || 0) + 1}</h5>
                    <p>Page ${table.page_number}</p>
                </div>
            </div>
        `;
    }
    container.innerHTML = html;
}

function renderTopics(topics) {
    const container = document.getElementById('topics-list');
    if (!container) return;

    if (!topics || topics.length === 0) {
        container.innerHTML = '<p>No topics detected.</p>';
        return;
    }

    let html = '';
    for (const topic of topics) {
        html += `<div class="topic-item">📝 ${escapeHtml(topic.title)}</div>`;
    }
    container.innerHTML = html;
}

function renderKeywords(keywords) {
    const container = document.getElementById('keywords-list');
    if (!container) return;

    if (!keywords || keywords.length === 0) {
        container.innerHTML = '<p>No keywords extracted.</p>';
        return;
    }

    let html = '';
    for (const kw of keywords) {
        html += `<div class="keyword-item">${escapeHtml(kw.keyword)}</div>`;
    }
    container.innerHTML = html;
}

function handleTabClick(e) {
    const tabName = e.target.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    e.target.classList.add('active');
    const targetContent = document.getElementById(`${tabName}-content`);
    if (targetContent) targetContent.classList.add('active');
}

async function openTableModal(tableId) {
    const modal = document.getElementById('table-modal');
    const modalTitle = document.getElementById('modal-title');
    const tableImage = document.getElementById('table-image');
    const tableText = document.getElementById('table-text');

    if (!modal) return;

    if (modalTitle) modalTitle.textContent = 'Loading...';
    if (tableImage) tableImage.src = '';
    if (tableText) tableText.textContent = '';

    modal.classList.remove('hidden');

    try {
        const response = await fetch(`/api/tables/${tableId}`);
        const data = await response.json();

        if (response.ok && data.success) {
            currentTableData = data;
            if (modalTitle) modalTitle.textContent = `Table ${(data.table_index || 0) + 1} - Page ${data.page_number}`;
            if (tableImage && (data.full_image_url || data.thumbnail_url)) {
                tableImage.src = data.full_image_url || data.thumbnail_url;
            }
            if (tableText) tableText.textContent = data.table_text || 'No text available';
        } else {
            if (modalTitle) modalTitle.textContent = 'Error loading table';
        }
    } catch (error) {
        console.error('Error:', error);
        if (modalTitle) modalTitle.textContent = 'Error loading table';
    }
}

function closeTableModal() {
    const modal = document.getElementById('table-modal');
    if (modal) modal.classList.add('hidden');
    currentTableData = null;
}

function openInPdf() {
    if (!currentTableData) return;
    closeTableModal();
    const iframe = document.getElementById('pdf-iframe');
    const pdfModal = document.getElementById('pdf-modal');
    if (iframe) iframe.src = currentTableData.pdf_page_url;
    if (pdfModal) pdfModal.classList.remove('hidden');
}

function viewInline() {
    // Already viewing inline in modal
}

function closePdfModal() {
    const modal = document.getElementById('pdf-modal');
    const iframe = document.getElementById('pdf-iframe');
    if (modal) modal.classList.add('hidden');
    if (iframe) iframe.src = '';
}

async function deleteDocument(docId) {
    if (!confirm('Delete this document?')) return;

    try {
        const response = await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
        const data = await response.json();

        if (response.ok && data.success) {
            loadDocuments();
            if (currentDocId === docId) {
                const catalogSection = document.getElementById('catalog-section');
                if (catalogSection) catalogSection.classList.add('hidden');
                currentDocId = null;
            }
        } else {
            alert(`Error: ${data.detail || 'Delete failed'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}