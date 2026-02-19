// WebSocket connection
let socket = null;
let currentDocId = null;

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
        updateTimeline(data.stage, data.status, data.message);
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

// Update timeline
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
        // Mark previous stages as completed
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

// Upload form handler
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    const uploadBtn = document.getElementById('uploadBtn');
    const statusDiv = document.getElementById('uploadStatus');
    const timelineSection = document.getElementById('timelineSection');
    
    if (!fileInput.files[0]) {
        statusDiv.textContent = 'Пожалуйста, выберите файл';
        statusDiv.className = 'status-message error';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Загрузка...';
    statusDiv.textContent = 'Загрузка файла...';
    statusDiv.className = 'status-message info';
    
    // Show timeline
    timelineSection.style.display = 'block';
    initTimeline();
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentDocId = data.doc_id;
            statusDiv.textContent = `Файл загружен. ID: ${data.doc_id}`;
            statusDiv.className = 'status-message success';
            
            // Subscribe to updates
            if (socket && currentDocId) {
                socket.emit('subscribe', { doc_id: currentDocId });
            }
            
            // Refresh table after a delay
            setTimeout(() => {
                refreshTable();
            }, 2000);
        } else {
            statusDiv.textContent = `Ошибка: ${data.error || 'Неизвестная ошибка'}`;
            statusDiv.className = 'status-message error';
        }
    } catch (error) {
        statusDiv.textContent = `Ошибка загрузки: ${error.message}`;
        statusDiv.className = 'status-message error';
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Загрузить и обработать';
        fileInput.value = '';
    }
});

// Initialize DataTable
let documentsTable = null;

function initTable() {
    if (documentsTable) {
        documentsTable.destroy();
    }
    
    documentsTable = $('#documentsTable').DataTable({
        ajax: {
            url: '/api/documents',
            dataSrc: 'documents'
        },
        columns: [
            { data: 'id' },
            { data: 'full_filename' },
            { data: 'type' },
            { data: 'tasks_count' },
            { 
                data: 'processing_status',
                render: function(data) {
                    return `<span class="status-badge ${data || 'pending'}">${data || 'pending'}</span>`;
                }
            },
            { data: 'cleaning_status' },
            { data: 'embedding_method' },
            { 
                data: 'created_at',
                render: function(data) {
                    if (!data) return '';
                    const date = new Date(data);
                    return date.toLocaleString('ru-RU');
                }
            },
            {
                data: 'id',
                render: function(data) {
                    return `<button class="view-btn" data-id="${data}">Просмотр</button>`;
                },
                orderable: false
            }
        ],
        language: {
            url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/ru.json'
        },
        order: [[0, 'desc']],
        pageLength: 25
    });
    
    // Handle view button click
    $('#documentsTable').on('click', '.view-btn', function() {
        const docId = $(this).data('id');
        viewDocument(docId);
    });
}

function refreshTable() {
    if (documentsTable) {
        documentsTable.ajax.reload();
    } else {
        initTable();
    }
}

function viewDocument(docId) {
    // TODO: Implement document view modal
    alert(`Просмотр документа ID: ${docId}`);
}

// Refresh button
document.getElementById('refreshBtn').addEventListener('click', () => {
    refreshTable();
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initSocket();
    initTable();
});
