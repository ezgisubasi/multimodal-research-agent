// Configuration
const API_BASE_URL = 'http://localhost:8000';

// DOM Elements
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const uploadProgress = document.getElementById('uploadProgress');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const searchResults = document.getElementById('searchResults');
const documentsList = document.getElementById('documentsList');
const refreshBtn = document.getElementById('refreshBtn');
const statusMessage = document.getElementById('statusMessage');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    loadDocuments();
    checkApiHealth();
});

function initializeEventListeners() {
    // File upload events
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', handleFileSelect);
    
    // Search events
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    
    // Refresh documents
    refreshBtn.addEventListener('click', loadDocuments);
}

function handleDragOver(e) {
    e.preventDefault();
    uploadArea.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    uploadArea.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileUpload(files[0]);
    }
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        handleFileUpload(file);
    }
}

async function handleFileUpload(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showStatus('Please select a PDF file', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    // Show progress
    document.querySelector('.upload-content').style.display = 'none';
    uploadProgress.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Uploading...';
    
    try {
        // Simulate upload progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 30;
            if (progress > 90) progress = 90;
            progressFill.style.width = progress + '%';
        }, 200);
        
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        clearInterval(progressInterval);
        
        if (response.ok) {
            const result = await response.json();
            progressFill.style.width = '100%';
            progressText.textContent = 'Upload complete! Indexing in progress...';
            
            showStatus(`File uploaded successfully: ${result.paper_id}`, 'success');
            
            // Reset after delay
            setTimeout(() => {
                resetUploadArea();
                loadDocuments();
            }, 2000);
        } else {
            throw new Error('Upload failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showStatus('Upload failed. Please try again.', 'error');
        resetUploadArea();
    }
}

function resetUploadArea() {
    document.querySelector('.upload-content').style.display = 'block';
    uploadProgress.style.display = 'none';
    fileInput.value = '';
}

async function performSearch() {
    const query = searchInput.value.trim();
    if (!query) {
        showStatus('Please enter a search query', 'error');
        return;
    }
    
    searchResults.innerHTML = '<div class="loading">Searching documents...</div>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/search`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: query,
                top_k: 5
            })
        });
        
        if (response.ok) {
            const results = await response.json();
            displaySearchResults(results);
        } else {
            throw new Error('Search failed');
        }
    } catch (error) {
        console.error('Search error:', error);
        searchResults.innerHTML = '<p class="placeholder">Search failed. Please try again.</p>';
        showStatus('Search failed. Please try again.', 'error');
    }
}

function displaySearchResults(results) {
    if (!results.results || results.results.length === 0) {
        searchResults.innerHTML = '<p class="placeholder">No results found for your query.</p>';
        return;
    }
    
    const resultsHtml = results.results.map(result => `
        <div class="result-card">
            <div class="result-header">
                <h4>📄 ${result.paper_id}</h4>
                <span class="result-score">${(result.score * 100).toFixed(1)}%</span>
            </div>
            <p><strong>Page:</strong> ${result.page_number + 1}</p>
            <p><strong>File:</strong> ${result.pdf_path.split('/').pop()}</p>
        </div>
    `).join('');
    
    searchResults.innerHTML = resultsHtml;
    showStatus(`Found ${results.total_results} results`, 'success');
}

async function loadDocuments() {
    documentsList.innerHTML = '<div class="loading">Loading documents...</div>';
    
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        
        if (response.ok) {
            const data = await response.json();
            displayDocuments(data.documents);
        } else {
            throw new Error('Failed to load documents');
        }
    } catch (error) {
        console.error('Load documents error:', error);
        documentsList.innerHTML = '<p class="placeholder">Failed to load documents</p>';
    }
}

function displayDocuments(documents) {
    if (!documents || documents.length === 0) {
        documentsList.innerHTML = '<p class="placeholder">No documents uploaded yet</p>';
        return;
    }
    
    const documentsHtml = documents.map(doc => `
        <div class="document-card">
            <div class="document-info">
                <h4>📄 ${doc.paper_id}</h4>
                <p>${doc.total_pages} pages • ${doc.pdf_path.split('/').pop()}</p>
            </div>
            <span class="result-score">Indexed</span>
        </div>
    `).join('');
    
    documentsList.innerHTML = documentsHtml;
}

async function checkApiHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            const health = await response.json();
            const modelStatus = health.model_loaded ? 'loaded' : 'ready';
            showStatus(`API connected • Model ${modelStatus}`, 'success');
        } else {
            throw new Error('API not responding');
        }
    } catch (error) {
        showStatus('API connection failed', 'error');
        console.error('Health check failed:', error);
    }
}

function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = `status-message ${type} show`;
    
    setTimeout(() => {
        statusMessage.classList.remove('show');
    }, 3000);
}

// Handle API URL for different environments
function getApiUrl() {
    // For local development
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:8000';
    }
    // For Colab or other environments, you might need to update this
    return 'http://localhost:8000';
}