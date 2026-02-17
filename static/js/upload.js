// WebSocket connection
let socket = null;
let currentUploads = new Map(); // Map<filename, {docId, progress, status}>

// Initialize Socket.IO
function initSocket() {
    socket = io();
    
    socket.on('connect', () => {
        console.log('Connected to server');
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
    });
    
    socket.on('processing_update', (data) => {
        if (data.doc_id) {
            // Find by doc_id
            for (const [fname, info] of currentUploads.entries()) {
                if (info.docId === data.doc_id) {
                    updateFileProgress(fname, data.stage, data.status, data.message);
                    break;
                }
            }
        } else if (data.filename) {
            // Fallback: find by filename
            if (currentUploads.has(data.filename)) {
                updateFileProgress(data.filename, data.stage, data.status, data.message);
            }
        }
    });
    
    socket.on('connected', (data) => {
        console.log('WebSocket connected:', data);
    });
    
    socket.on('subscribed', (data) => {
        console.log('Subscribed to document:', data);
    });
}

// Initialize timeline
function initTimeline() {
    const stages = ['upload', 'parsing', 'task_extraction', 'cleaning', 
                   'embeddings', 'similarity', 'cheating_detection', 'completed'];
    
    stages.forEach(stage => {
        const item = document.querySelector(`[data-stage="${stage}"]`);
        if (item) {
            item.classList.remove('active', 'completed', 'error');
            const statusEl = item.querySelector('.timeline-status');
            if (statusEl) {
                statusEl.textContent = 'Ожидание...';
            }
        }
    });
}

// Update timeline (for single file view)
function updateTimeline(stage, status, message) {
    const item = document.querySelector(`[data-stage="${stage}"]`);
    if (!item) return;
    
    const statusEl = item.querySelector('.timeline-status');
    if (statusEl) {
        statusEl.textContent = message || status;
    }
    
    item.classList.remove('active', 'completed', 'error');
    
    if (status === 'in_progress' || status === 'processing') {
        item.classList.add('active');
    } else if (status === 'completed') {
        item.classList.add('completed');
        const allItems = document.querySelectorAll('.timeline-item');
        let found = false;
        allItems.forEach(el => {
            if (el === item) {
                found = true;
            } else if (!found) {
                el.classList.add('completed');
                el.classList.remove('active');
            }
        });
    } else if (status === 'error') {
        item.classList.add('error');
    }
}

// Display selected files
function displaySelectedFiles(files) {
    const filesListSection = document.getElementById('filesListSection');
    const filesList = document.getElementById('selectedFilesList');
    
    if (files.length === 0) {
        filesListSection.style.display = 'none';
        return;
    }
    
    filesListSection.style.display = 'block';
    filesList.innerHTML = '';
    
    Array.from(files).forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.dataset.index = index;
        fileItem.innerHTML = `
            <span class="file-name">${file.name}</span>
            <span class="file-size">(${(file.size / 1024).toFixed(2)} KB)</span>
            <button class="remove-file-btn" data-index="${index}">×</button>
        `;
        filesList.appendChild(fileItem);
    });
    
    // Add remove handlers
    filesList.querySelectorAll('.remove-file-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const index = parseInt(btn.dataset.index);
            removeFileFromInput(index);
        });
    });
}

// Remove file from input
function removeFileFromInput(index) {
    const fileInput = document.getElementById('fileInput');
    const dt = new DataTransfer();
    const files = Array.from(fileInput.files);
    
    files.forEach((file, i) => {
        if (i !== index) {
            dt.items.add(file);
        }
    });
    
    fileInput.files = dt.files;
    displaySelectedFiles(fileInput.files);
}

// Update file progress
function updateFileProgress(filename, stage, status, message) {
    const progressSection = document.getElementById('progressSection');
    if (!progressSection) return;
    
    progressSection.style.display = 'block';
    
    let progressItem = document.getElementById(`progress-${filename}`);
    if (!progressItem) {
        progressItem = document.createElement('div');
        progressItem.id = `progress-${filename}`;
        progressItem.className = 'file-progress-item';
        progressItem.innerHTML = `
            <div class="file-progress-header">
                <span class="file-progress-name">${filename}</span>
                <span class="file-progress-status">Ожидание...</span>
            </div>
            <div class="file-progress-bar">
                <div class="file-progress-fill" style="width: 0%"></div>
            </div>
            <div class="file-progress-stages"></div>
        `;
        document.getElementById('filesProgress').appendChild(progressItem);
    }
    
    const statusEl = progressItem.querySelector('.file-progress-status');
    const fillEl = progressItem.querySelector('.file-progress-fill');
    const stagesEl = progressItem.querySelector('.file-progress-stages');
    
    if (statusEl) {
        statusEl.textContent = message || stage || 'Обработка...';
    }
    
    // Update progress bar
    const stages = ['upload', 'parsing', 'task_extraction', 'cleaning', 
                   'embeddings', 'similarity', 'cheating_detection', 'completed'];
    const currentStageIndex = stages.indexOf(stage);
    if (currentStageIndex >= 0) {
        const progress = ((currentStageIndex + 1) / stages.length) * 100;
        if (fillEl) {
            fillEl.style.width = progress + '%';
        }
    }
    
    if (status === 'completed' && stage === 'completed') {
        if (fillEl) fillEl.style.width = '100%';
        if (statusEl) statusEl.textContent = 'Завершено';
        progressItem.classList.add('completed');
    } else if (status === 'error') {
        if (statusEl) statusEl.textContent = 'Ошибка: ' + (message || 'Неизвестная ошибка');
        progressItem.classList.add('error');
    }
}

// Upload form handler
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const statusDiv = document.getElementById('uploadStatus');
    const progressSection = document.getElementById('progressSection');
    
    if (!fileInput.files || fileInput.files.length === 0) {
        statusDiv.textContent = 'Пожалуйста, выберите файлы';
        statusDiv.className = 'status-message error';
        return;
    }
    
    const files = Array.from(fileInput.files);
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Загрузка...';
    statusDiv.textContent = `Загрузка ${files.length} файл(ов)...`;
    statusDiv.className = 'status-message info';
    
    // Show progress section
    progressSection.style.display = 'block';
    document.getElementById('filesProgress').innerHTML = '';
    
    // Clear current uploads
    currentUploads.clear();
    
    // Upload each file
    const uploadPromises = files.map(async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        
        currentUploads.set(file.name, { docId: null, progress: 0, status: 'uploading' });
        updateFileProgress(file.name, 'upload', 'in_progress', 'Загрузка...');
        
        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                const docId = data.doc_id;
                currentUploads.set(file.name, { docId, progress: 0, status: 'processing' });
                
                // Subscribe to updates
                if (socket && docId) {
                    socket.emit('subscribe', { doc_id: docId });
                }
                
                updateFileProgress(file.name, 'upload', 'completed', 'Загружен, обработка...');
                return { file: file.name, success: true, docId };
            } else {
                updateFileProgress(file.name, 'error', 'error', data.error || 'Ошибка загрузки');
                currentUploads.set(file.name, { docId: null, progress: 0, status: 'error' });
                return { file: file.name, success: false, error: data.error };
            }
        } catch (error) {
            updateFileProgress(file.name, 'error', 'error', error.message);
            currentUploads.set(file.name, { docId: null, progress: 0, status: 'error' });
            return { file: file.name, success: false, error: error.message };
        }
    });
    
    // Wait for all uploads
    const results = await Promise.all(uploadPromises);
    const successCount = results.filter(r => r.success).length;
    const errorCount = results.filter(r => !r.success).length;
    
    statusDiv.textContent = `Загружено: ${successCount}, Ошибок: ${errorCount}`;
    statusDiv.className = successCount > 0 ? 'status-message success' : 'status-message error';
    
    uploadBtn.disabled = false;
    uploadBtn.textContent = 'Загрузить и обработать';
    fileInput.value = '';
    displaySelectedFiles(fileInput.files);
    
    // Redirect to report page after delay if successful
    if (successCount > 0) {
        setTimeout(() => {
            window.location.href = '/report';
        }, 3000);
    }
});

// File input change handler
document.getElementById('fileInput').addEventListener('change', (e) => {
    displaySelectedFiles(e.target.files);
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
});
