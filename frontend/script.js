// Research Paper Analyzer - Frontend JavaScript

// Configuration
const API_BASE_URL = 'https://your-railway-app.up.railway.app';  // Replace with your Railway URL
// For local development: const API_BASE_URL = 'http://localhost:8000';

let selectedFile = null;
let currentDocumentId = null;

// Initialize app when DOM loads
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupFileUpload();
    setupTabNavigation();
    loadDocuments();
}

// Tab Navigation
function showTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabName + '-tab').classList.add('active');
    
    // Add active class to clicked button
    event.target.classList.add('active');
    
    // Load documents when documents tab is shown
    if (tabName === 'documents') {
        loadDocuments();
    }
}

function setupTabNavigation() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.textContent.includes('Upload') ? 'upload' : 'documents';
            showTab(tabName);
        });
    });
}

// File Upload Setup
function setupFileUpload() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-input');
    
    // Click to upload
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });
    
    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });
    
    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
}

function handleFileSelect(file) {
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showError('Please select a PDF file.');
        return;
    }
    
    // Validate file size (50MB limit)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
        showError('File too large. Maximum size is 50MB.');
        return;
    }
    
    selectedFile = file;
    displayFileInfo(file);
}

function displayFileInfo(file) {
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const fileSize = document.getElementById('file-size');
    
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    
    fileInfo.classList.remove('hidden');
    
    // Hide upload area
    document.getElementById('upload-area').style.display = 'none';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// File Upload
async function uploadFile() {
    if (!selectedFile) {
        showError('Please select a file first.');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    try {
        // Show processing status
        showProcessingStatus('Uploading file...');
        
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Upload failed');
        }
        
        const result = await response.json();
        currentDocumentId = result.document_id;
        
        showSuccess('File uploaded successfully!');
        updateProcessingStatus('Processing with GROBID...', 10);
        
        // Start polling for results
        pollForResults(currentDocumentId);
        
    } catch (error) {
        showError('Upload failed: ' + error.message);
        hideProcessingStatus();
    }
}

// Status Polling
async function pollForResults(documentId) {
    const maxAttempts = 60; // 60 seconds max
    let attempts = 0;
    
    const poll = async () => {
        try {
            attempts++;
            const progress = Math.min((attempts / maxAttempts) * 90, 90);
            updateProcessingStatus('Processing with GROBID...', progress);
            
            const response = await fetch(`${API_BASE_URL}/status/${documentId}`);
            
            if (!response.ok) {
                throw new Error('Failed to check status');
            }
            
            const status = await response.json();
            
            if (status.status === 'completed') {
                updateProcessingStatus('Processing completed!', 100);
                setTimeout(() => {
                    hideProcessingStatus();
                    displayResults(status.result);
                }, 1000);
                
            } else if (status.status === 'failed') {
                throw new Error(status.error || 'Processing failed');
                
            } else if (attempts < maxAttempts) {
                // Continue polling
                setTimeout(poll, 1000);
            } else {
                throw new Error('Processing timeout');
            }
            
        } catch (error) {
            showError('Processing failed: ' + error.message);
            hideProcessingStatus();
        }
    };
    
    poll();
}

// Display Results
function displayResults(result) {
    if (result.status !== 'success') {
        showError('Processing failed: ' + (result.error || 'Unknown error'));
        return;
    }
    
    // Update metrics
    document.getElementById('sections-count').textContent = result.sections?.length || 0;
    document.getElementById('authors-count').textContent = result.authors?.length || 0;
    document.getElementById('references-count').textContent = result.references?.length || 0;
    document.getElementById('process-time').textContent = (result.processing_time || 0).toFixed(1) + 's';
    
    // Paper information
    document.getElementById('paper-title').textContent = result.title || 'Title not found';
    
    // Abstract
    const abstractEl = document.getElementById('paper-abstract');
    if (result.abstract && result.abstract !== 'Abstract not found') {
        abstractEl.textContent = result.abstract;
    } else {
        abstractEl.innerHTML = '<em>Abstract not found in the document</em>';
    }
    
    // Authors
    displayAuthors(result.authors || []);
    
    // Sections
    displaySections(result.sections || []);
    
    // References
    displayReferences(result.references || []);
    
    // Show results section
    document.getElementById('results-section').classList.remove('hidden');
    
    // Scroll to results
    document.getElementById('results-section').scrollIntoView({ behavior: 'smooth' });
}

function displayAuthors(authors) {
    const authorsContainer = document.getElementById('paper-authors');
    
    if (authors.length === 0) {
        authorsContainer.innerHTML = '<em>No authors found</em>';
        return;
    }
    
    authorsContainer.innerHTML = authors.slice(0, 8).map(author => `
        <div class="author-item">
            <span class="author-name">${escapeHtml(author.name || 'Unknown')}</span>
            <span class="author-affiliation">${escapeHtml(author.affiliation || 'No affiliation')}</span>
        </div>
    `).join('');
}

function displaySections(sections) {
    const sectionsContainer = document.getElementById('paper-sections');
    
    if (sections.length === 0) {
        sectionsContainer.innerHTML = '<em>No sections found</em>';
        return;
    }
    
    sectionsContainer.innerHTML = sections.map((section, index) => `
        <div class="section-item">
            <div class="section-header" onclick="toggleSection(${index})">
                <span>${escapeHtml(section.title || 'Untitled Section')}</span>
                <span class="toggle-icon" id="toggle-${index}">▼</span>
            </div>
            <div class="section-content" id="content-${index}">
                ${escapeHtml(section.content || 'No content available')}
            </div>
        </div>
    `).join('');
}

function displayReferences(references) {
    const referencesContainer = document.getElementById('paper-references');
    
    if (references.length === 0) {
        referencesContainer.innerHTML = '<em>No references found</em>';
        return;
    }
    
    referencesContainer.innerHTML = references.slice(0, 5).map((ref, index) => `
        <div class="reference-item">
            <strong>${index + 1}.</strong> ${escapeHtml(ref)}
        </div>
    `).join('');
}

function toggleSection(index) {
    const content = document.getElementById(`content-${index}`);
    const icon = document.getElementById(`toggle-${index}`);
    
    if (content.classList.contains('open')) {
        content.classList.remove('open');
        icon.classList.remove('open');
    } else {
        content.classList.add('open');
        icon.classList.add('open');
    }
}

// Documents Management
async function loadDocuments() {
    const documentsContainer = document.getElementById('documents-list');
    documentsContainer.innerHTML = '<div class="loading">Loading documents...</div>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        
        if (!response.ok) {
            throw new Error('Failed to load documents');
        }
        
        const documents = await response.json();
        displayDocuments(documents);
        
    } catch (error) {
        documentsContainer.innerHTML = `
            <div class="error-message">
                <p>Failed to load documents: ${error.message}</p>
                <button onclick="loadDocuments()" class="btn-secondary">Retry</button>
            </div>
        `;
    }
}

function displayDocuments(documents) {
    const documentsContainer = document.getElementById('documents-list');
    
    if (documents.length === 0) {
        documentsContainer.innerHTML = `
            <div class="loading">
                <p>No documents uploaded yet.</p>
                <p>Use the "Upload Paper" tab to get started!</p>
            </div>
        `;
        return;
    }
    
    documentsContainer.innerHTML = documents.map(doc => `
        <div class="document-card">
            <div class="document-header">
                <div class="document-info">
                    <div class="document-title">📄 ${escapeHtml(doc.filename)}</div>
                    <div class="document-meta">
                        <span class="status-badge status-${doc.status}">${doc.status}</span>
                        <span>Size: ${formatFileSize(doc.file_size)}</span>
                        <span>Uploaded: ${formatDate(doc.upload_time)}</span>
                    </div>
                    ${doc.status === 'completed' ? `
                        <div class="document-meta" style="margin-top: 8px;">
                            <span>Title: ${escapeHtml(doc.title || 'N/A')}</span><br>
                            <span>Authors: ${doc.authors_count || 0}</span>
                            <span>Sections: ${doc.sections_count || 0}</span>
                        </div>
                    ` : ''}
                </div>
                <div class="document-actions">
                    ${doc.status === 'completed' ? `
                        <button class="btn-small btn-view" onclick="viewDocument('${doc.document_id}')">
                            👁️ View
                        </button>
                    ` : ''}
                    <button class="btn-small btn-delete" onclick="deleteDocument('${doc.document_id}', '${escapeHtml(doc.filename)}')">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

async function viewDocument(documentId) {
    try {
        showProcessingStatus('Loading document...', 50);
        
        const response = await fetch(`${API_BASE_URL}/status/${documentId}`);
        
        if (!response.ok) {
            throw new Error('Failed to load document');
        }
        
        const status = await response.json();
        
        if (status.status === 'completed' && status.result) {
            hideProcessingStatus();
            
            // Switch to upload tab and show results
            showTab('upload');
            displayResults(status.result);
            
            // Hide upload area and file info
            document.getElementById('upload-area').style.display = 'none';
            document.getElementById('file-info').classList.add('hidden');
            
        } else {
            throw new Error('Document not ready or failed to process');
        }
        
    } catch (error) {
        hideProcessingStatus();
        showError('Failed to load document: ' + error.message);
    }
}

async function deleteDocument(documentId, filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/documents/${documentId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete document');
        }
        
        showSuccess('Document deleted successfully!');
        loadDocuments(); // Reload documents list
        
    } catch (error) {
        showError('Failed to delete document: ' + error.message);
    }
}

// Processing Status
function showProcessingStatus(message, progress = 0) {
    const statusSection = document.getElementById('processing-status');
    const statusText = document.getElementById('status-text');
    const progressFill = document.getElementById('progress');
    
    statusText.textContent = message;
    progressFill.style.width = progress + '%';
    statusSection.classList.remove('hidden');
}

function updateProcessingStatus(message, progress) {
    const statusText = document.getElementById('status-text');
    const progressFill = document.getElementById('progress');
    
    statusText.textContent = message;
    progressFill.style.width = progress + '%';
}

function hideProcessingStatus() {
    document.getElementById('processing-status').classList.add('hidden');
}

// Message System
function showError(message) {
    const errorMsg = document.getElementById('error-message');
    const errorText = document.getElementById('error-text');
    
    errorText.textContent = message;
    errorMsg.classList.remove('hidden');
    
    // Auto hide after 5 seconds
    setTimeout(() => {
        hideError();
    }, 5000);
}

function showSuccess(message) {
    const successMsg = document.getElementById('success-message');
    const successText = document.getElementById('success-text');
    
    successText.textContent = message;
    successMsg.classList.remove('hidden');
    
    // Auto hide after 3 seconds
    setTimeout(() => {
        hideSuccess();
    }, 3000);
}

function hideError() {
    document.getElementById('error-message').classList.add('hidden');
}

function hideSuccess() {
    document.getElementById('success-message').classList.add('hidden');
}

// Utility Functions
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

// Reset form for new upload
function resetUploadForm() {
    selectedFile = null;
    currentDocumentId = null;
    
    document.getElementById('upload-area').style.display = 'block';
    document.getElementById('file-info').classList.add('hidden');
    document.getElementById('processing-status').classList.add('hidden');
    document.getElementById('results-section').classList.add('hidden');
    document.getElementById('file-input').value = '';
}

// Add reset button functionality
document.addEventListener('DOMContentLoaded', function() {
    // Add reset button to results section
    const resultsSection = document.getElementById('results-section');
    if (resultsSection) {
        const resetButton = document.createElement('button');
        resetButton.textContent = '📤 Upload Another Paper';
        resetButton.className = 'btn-secondary';
        resetButton.style.marginTop = '20px';
        resetButton.onclick = resetUploadForm;
        
        resultsSection.appendChild(resetButton);
    }
});