// ============================================================
// RAG Document Cataloger - Frontend Application
// Handles: file upload, document listing, dynamic section tabs,
//          inline PDF viewer, authentication
// ============================================================

// --- Global State ---
let currentDocId = null;
let currentDocFilename = null;
let currentCategories = [];
let currentSections = {};

// --- Authentication ---

/**
 * Get the auth token from cookie or localStorage.
 * Cookies are the most reliable transport (set by the server at login).
 */
function getToken() {
    // 1. Try the auth_token cookie (set by the server)
    const cookieMatch = document.cookie.match(/(?:^|;\s*)auth_token=([^;]*)/);
    if (cookieMatch && cookieMatch[1]) {
        return cookieMatch[1];
    }
    // 2. Fallback to localStorage
    return localStorage.getItem('token');
}

/**
 * Build headers object that includes the Bearer token.
 * Redirects to login if no token is available.
 */
function getAuthHeaders() {
    const token = getToken();
    if (!token) {
        window.location.href = '/';
        return null;
    }
    return { 'Authorization': 'Bearer ' + token };
}

/**
 * Returns true (and redirects) when the response is a 401/403.
 */
function handleUnauthorized(response) {
    if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('token');
        document.cookie = 'auth_token=; path=/; max-age=0';
        window.location.href = '/';
        return true;
    }
    return false;
}

function logout() {
    localStorage.removeItem('token');
    document.cookie = 'auth_token=; path=/; max-age=0';
    fetch('/auth/logout', { method: 'POST' }).catch(function () { });
    window.location.href = '/';
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', function () {
    var token = getToken();
    if (!token) {
        window.location.href = '/';
        return;
    }
    initEventListeners();
    loadDocuments();
    addLogoutButton();
});

function addLogoutButton() {
    var sidebar = document.querySelector('.sidebar-header');
    if (sidebar && !document.getElementById('logout-btn')) {
        var btn = document.createElement('button');
        btn.id = 'logout-btn';
        btn.className = 'btn btn-secondary';
        btn.textContent = 'Logout';
        btn.style.marginTop = '10px';
        btn.style.width = '100%';
        btn.onclick = logout;
        sidebar.appendChild(btn);
    }
}

function initEventListeners() {
    var uploadForm = document.getElementById('upload-form');
    if (uploadForm) uploadForm.addEventListener('submit', handleUpload);

    var dropZone = document.getElementById('drop-zone');
    if (dropZone) {
        dropZone.addEventListener('dragover', function (e) {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        dropZone.addEventListener('dragleave', function () {
            dropZone.classList.remove('dragover');
        });
        dropZone.addEventListener('drop', function (e) {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            var files = e.dataTransfer.files;
            if (files.length) {
                document.getElementById('file-input').files = files;
                showSelectedFile(files[0].name);
            }
        });
        dropZone.addEventListener('click', function () {
            document.getElementById('file-input').click();
        });
    }

    var fileInput = document.getElementById('file-input');
    if (fileInput) {
        fileInput.addEventListener('change', function (e) {
            if (e.target.files.length) showSelectedFile(e.target.files[0].name);
        });
    }

    var refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', loadDocuments);

    var modalClose = document.getElementById('modal-close');
    if (modalClose) modalClose.addEventListener('click', function () { closeModal('content-modal'); });
    var pdfClose = document.getElementById('pdf-modal-close');
    if (pdfClose) pdfClose.addEventListener('click', function () { closeModal('pdf-modal'); });

    document.querySelectorAll('.modal-overlay').forEach(function (overlay) {
        overlay.addEventListener('click', function (e) {
            var modal = e.target.closest('.modal');
            if (modal) modal.classList.remove('show');
        });
    });
}

function showSelectedFile(filename) {
    var el = document.querySelector('.upload-text');
    if (el) {
        el.textContent = filename;
        el.style.color = '#4a7c59';
    }
}

// ─── Upload ───────────────────────────────────
async function handleUpload(e) {
    e.preventDefault();
    var fileInput = document.getElementById('file-input');
    var file = fileInput && fileInput.files[0];
    if (!file) { showStatus('Please select a file', 'error'); return; }

    showStatus('Processing document… This may take a moment.', 'loading');
    var uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<span class="loading-spinner-small"></span> Processing…';
    }

    try {
        var formData = new FormData();
        formData.append('file', file);

        var authHeaders = getAuthHeaders();
        if (!authHeaders) return;

        var response = await fetch('/api/upload', {
            method: 'POST',
            headers: authHeaders,
            body: formData
        });

        if (handleUnauthorized(response)) return;

        var data = await response.json();

        if (response.ok && data.success) {
            showStatus('Document processed! ' + (data.counts ? data.counts.chunks || 0 : 0) + ' chunks extracted.', 'success');
            fileInput.value = '';
            var uploadText = document.querySelector('.upload-text');
            if (uploadText) { uploadText.textContent = 'Drop file here or click to browse'; uploadText.style.color = ''; }
            await loadDocuments();
            loadDocument(data.doc_id, file.name);
        } else {
            showStatus('Error: ' + (data.detail || 'Upload failed'), 'error');
        }
    } catch (err) {
        showStatus('Error: ' + err.message, 'error');
    } finally {
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<span>Upload & Process</span>';
        }
    }
}

function showStatus(message, type) {
    var el = document.getElementById('upload-status');
    if (!el) return;
    el.textContent = message;
    el.className = 'status show ' + type;
    if (type === 'success') setTimeout(function () { el.classList.remove('show'); }, 5000);
}

// ─── Documents list ───────────────────────────
async function loadDocuments() {
    var container = document.getElementById('documents-list');
    if (!container) return;
    container.innerHTML = '<div class="loading-state"><div class="loading-spinner"></div><p>Loading…</p></div>';

    try {
        var authHeaders = getAuthHeaders();
        if (!authHeaders) return;

        var response = await fetch('/api/documents', { headers: authHeaders });
        if (handleUnauthorized(response)) return;

        var data = await response.json();
        if (response.ok && data.success) {
            renderDocumentsList(data.documents);
        } else {
            container.innerHTML = '<div class="empty-state"><p>No documents yet. Upload one to get started.</p></div>';
        }
    } catch (err) {
        container.innerHTML = '<div class="empty-state"><p>No documents yet. Upload one to get started.</p></div>';
    }
}

function renderDocumentsList(documents) {
    var container = document.getElementById('documents-list');
    if (!container) return;

    if (!documents || documents.length === 0) {
        container.innerHTML =
            '<div class="empty-state">' +
            '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:.4;margin-bottom:8px;">' +
            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>' +
            '<polyline points="14 2 14 8 20 8"></polyline></svg>' +
            '<p>No documents uploaded yet.</p>' +
            '<p style="font-size:.8rem;margin-top:4px;">Upload a document to get started.</p></div>';
        return;
    }

    container.innerHTML = documents.map(function (doc) {
        var isActive = currentDocId === doc.doc_id;
        var chunks = doc.chunks_count || 0;
        var topics = doc.topics_count || 0;

        return '<div class="document-item ' + (isActive ? 'active' : '') + '" onclick="loadDocument(\'' + doc.doc_id + '\', \'' + escapeAttr(doc.filename) + '\')">' +
            '<div class="document-icon">' +
            '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
            '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>' +
            '<polyline points="14 2 14 8 20 8"></polyline></svg></div>' +
            '<div class="document-info">' +
            '<h4>' + escapeHtml(doc.filename) + '</h4>' +
            '<p>' + doc.filetype.toUpperCase() + ' &bull; ' + chunks + ' chunks &bull; ' + topics + ' sections</p></div>' +
            '<div class="document-actions">' +
            '<button class="document-delete" onclick="event.stopPropagation(); deleteDocument(\'' + doc.doc_id + '\')" title="Delete">' +
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
            '<polyline points="3 6 5 6 21 6"></polyline>' +
            '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button></div></div>';
    }).join('');
}

// ─── Document view ────────────────────────────
async function loadDocument(docId, filename) {
    currentDocId = docId;
    currentDocFilename = filename;

    document.getElementById('welcome-state').classList.add('hidden');
    document.getElementById('document-view').classList.remove('hidden');
    document.getElementById('document-title').textContent = filename;

    // Ensure we're in content mode by default (chat hidden)
    showDocumentContentMode();

    document.querySelectorAll('.document-item').forEach(function (item) {
        item.classList.remove('active');
        if (item.onclick && item.onclick.toString().indexOf(docId) !== -1) item.classList.add('active');
    });

    var tabsContainer = document.getElementById('section-tabs');
    var tabContents = document.getElementById('tab-contents');
    if (tabsContainer) tabsContainer.innerHTML = '<div class="loading-spinner"></div>';
    if (tabContents) tabContents.innerHTML = '';

    try {
        var authHeaders = getAuthHeaders();
        if (!authHeaders) return;

        var response = await fetch('/api/documents/' + docId + '/sections', { headers: authHeaders });
        if (handleUnauthorized(response)) return;

        var data = await response.json();
        if (response.ok && data.success) {
            currentCategories = data.categories || [];
            currentSections = data.sections || {};
            renderDynamicTabs(currentCategories, currentSections);
            var meta = document.getElementById('document-meta');
            if (meta) meta.textContent = currentCategories.length + ' sections detected';
        } else {
            if (tabsContainer) tabsContainer.innerHTML = '<div class="empty-state">No content sections found</div>';
        }
    } catch (err) {
        console.error('Error loading sections:', err);
        if (tabsContainer) tabsContainer.innerHTML = '<div class="empty-state">Error loading document sections</div>';
    }
}

function renderDynamicTabs(categories, sections) {
    var tabsContainer = document.getElementById('section-tabs');
    var tabContents = document.getElementById('tab-contents');
    if (!tabsContainer || !tabContents) return;

    var cats = categories.filter(function (c) { var items = sections[c]; return items && items.length > 0; });
    if (cats.length === 0) {
        tabsContainer.innerHTML = '<div class="empty-state">No content sections found</div>';
        tabContents.innerHTML = '';
        return;
    }

    tabsContainer.innerHTML = cats.map(function (cat, i) {
        var name = formatCategoryName(cat);
        var count = sections[cat] ? sections[cat].length : 0;
        return '<button class="tab-btn ' + (i === 0 ? 'active' : '') + '" data-tab="' + cat + '">' + name + ' <span class="tab-count">(' + count + ')</span></button>';
    }).join('');

    tabContents.innerHTML = cats.map(function (cat, i) {
        return '<div class="tab-content ' + (i === 0 ? 'active' : '') + '" id="' + cat + '-tab"><div id="' + cat + '-content" class="section-content"></div></div>';
    }).join('');

    tabsContainer.querySelectorAll('.tab-btn').forEach(function (btn) { btn.addEventListener('click', handleTabClick); });

    cats.forEach(function (cat) {
        var items = sections[cat] || [];
        if (cat === 'tables') renderTablesSection(items);
        else if (cat === 'images') renderImagesSection(items);
        else renderTextSection(cat, items);
    });
}

function formatCategoryName(c) {
    if (!c) return 'Other';
    if (c.startsWith('page_')) return 'Page ' + c.replace('page_', '');
    return c.split(/[\s_-]+/).map(function (w) { return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); }).join(' ');
}

function renderTextSection(sectionType, items) {
    var container = document.getElementById(sectionType + '-content');
    if (!container) return;
    var name = formatCategoryName(sectionType);
    if (!items || items.length === 0) { container.innerHTML = '<div class="empty-section">No ' + name + ' content found</div>'; return; }

    container.innerHTML = items.map(function (item) {
        var page = item.start_page || item.page_number || 1;
        var content = item.content || '';
        var title = item.title || name;
        var preview = content.length > 400 ? content.substring(0, 400) + '…' : content;
        return '<div class="section-card"><div class="section-card-header"><span class="section-card-title">' + escapeHtml(title) + '</span><span class="section-card-page">Page ' + page + '</span></div>' +
            '<div class="section-card-content">' + escapeHtml(preview) + '</div>' +
            '<div class="section-card-actions"><button class="btn btn-primary" onclick="viewContent(\'' + escapeAttr(title) + '\', `' + escapeTemplate(content) + '`)">View Full Content</button>' +
            '<button class="btn btn-secondary" onclick="openPdfAtPage(' + page + ')">View in PDF</button></div></div>';
    }).join('');
}

function renderTablesSection(tables) {
    var container = document.getElementById('tables-content');
    if (!container) return;
    if (!tables || tables.length === 0) { container.innerHTML = '<div class="empty-section">No tables found</div>'; return; }
    container.innerHTML = '<div class="tables-grid">' + tables.map(function (t) {
        var page = t.page_number || 1;
        return '<div class="table-card section-card"><div class="section-card-header"><span class="section-card-title">Table ' + ((t.table_index || 0) + 1) + '</span><span class="section-card-page">Page ' + page + '</span></div>' +
            '<div class="section-card-content">' + (t.rows_count || 0) + ' rows &times; ' + (t.cols_count || 0) + ' columns</div>' +
            '<div class="section-card-actions"><button class="btn btn-primary" onclick="viewTable(\'' + t.table_id + '\')">View Table</button><button class="btn btn-secondary" onclick="openPdfAtPage(' + page + ')">View in PDF</button></div></div>';
    }).join('') + '</div>';
}

function renderImagesSection(images) {
    var container = document.getElementById('images-content');
    if (!container) return;
    if (!images || images.length === 0) { container.innerHTML = '<div class="empty-section">No images found</div>'; return; }
    container.innerHTML = '<div class="images-grid">' + images.map(function (img) {
        var page = img.page_number || 1;
        return '<div class="image-card"><div class="image-card-info"><div class="section-card-header"><span class="section-card-title">Image ' + ((img.image_index || 0) + 1) + '</span><span class="section-card-page">Page ' + page + '</span></div>' +
            '<div class="section-card-actions" style="margin-top:12px;"><button class="btn btn-secondary" onclick="openPdfAtPage(' + page + ')">View in PDF</button></div></div></div>';
    }).join('') + '</div>';
}

// ─── Tabs ─────────────────────────────────────
function handleTabClick(e) {
    var tabId = e.target.closest('.tab-btn') && e.target.closest('.tab-btn').dataset.tab;
    if (!tabId) return;
    document.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
    e.target.closest('.tab-btn').classList.add('active');
    document.querySelectorAll('.tab-content').forEach(function (c) { c.classList.remove('active'); });
    var el = document.getElementById(tabId + '-tab');
    if (el) el.classList.add('active');
}

// ─── Modals ───────────────────────────────────
function viewContent(title, content) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = '<div style="white-space:pre-wrap;line-height:1.8;">' + escapeHtml(content) + '</div>';
    document.getElementById('content-modal').classList.add('show');
}

async function viewTable(tableId) {
    document.getElementById('modal-title').textContent = 'Table';
    document.getElementById('modal-body').innerHTML = '<div class="loading-spinner"></div>';
    document.getElementById('content-modal').classList.add('show');
    try {
        var authHeaders = getAuthHeaders();
        if (!authHeaders) return;
        var response = await fetch('/api/tables/' + tableId, { headers: authHeaders });
        if (handleUnauthorized(response)) return;
        var data = await response.json();
        if (response.ok && data.success) {
            document.getElementById('modal-body').innerHTML = '<div class="table-view"><pre style="overflow-x:auto;white-space:pre-wrap;">' + escapeHtml(data.table_text || 'No content') + '</pre></div>';
        } else {
            document.getElementById('modal-body').innerHTML = '<p>Error loading table</p>';
        }
    } catch (err) {
        document.getElementById('modal-body').innerHTML = '<p>Error loading table</p>';
    }
}

function openPdfAtPage(page) {
    if (!currentDocId) return;
    document.getElementById('pdf-modal-title').textContent = currentDocFilename + ' – Page ' + page;
    document.getElementById('pdf-iframe').src = '/api/pdf/' + currentDocId + '#page=' + page;
    document.getElementById('pdf-modal').classList.add('show');
}

function closeModal(id) {
    var modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('show');
        if (id === 'pdf-modal') document.getElementById('pdf-iframe').src = '';
    }
}

// ─── Delete ───────────────────────────────────
async function deleteDocument(docId) {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
        var authHeaders = getAuthHeaders();
        if (!authHeaders) return;
        var response = await fetch('/api/documents/' + docId, { method: 'DELETE', headers: authHeaders });
        if (handleUnauthorized(response)) return;
        if (response.ok) {
            await loadDocuments();
            if (currentDocId === docId) {
                document.getElementById('welcome-state').classList.remove('hidden');
                document.getElementById('document-view').classList.add('hidden');
                currentDocId = null; currentDocFilename = null; currentCategories = []; currentSections = {};
            }
        } else { alert('Error deleting document'); }
    } catch (err) { alert('Error: ' + err.message); }
}

// ─── Utilities ────────────────────────────────
function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
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
