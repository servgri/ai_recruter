// Initialize DataTable with all columns
let documentsTable = null;

function formatJsonField(data) {
    if (!data || data === '' || data === null) return '';
    try {
        const parsed = typeof data === 'string' ? JSON.parse(data) : data;
        if (parsed === null || parsed === undefined) return '';
        const jsonStr = JSON.stringify(parsed, null, 2);
        // Truncate if too long
        if (jsonStr.length > 200) {
            return `<span class="json-preview">${jsonStr.substring(0, 200)}...</span>
                    <span class="json-full" style="display:none">${jsonStr}</span>
                    <button class="toggle-json-btn" type="button">Показать</button>`;
        }
        return jsonStr;
    } catch {
        return String(data);
    }
}

function formatTextField(data, maxLength = 100) {
    if (!data) return '';
    const text = String(data);
    if (text.length <= maxLength) return text;
    // Escape HTML
    const escapedText = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const preview = escapedText.substring(0, maxLength);
    return `<span class="text-preview">${preview}...</span>
            <span class="text-full" style="display:none">${escapedText}</span>
            <button class="toggle-text-btn" type="button">Показать все</button>`;
}

function formatSimilarityPercentage(value) {
    if (value === null || value === undefined || value === '') return '-';
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(num)) return '-';
    return `${(num * 100).toFixed(1)}%`;
}

function formatMaxSimilarity(data) {
    if (!data) return '-';
    try {
        const parsed = typeof data === 'string' ? JSON.parse(data) : data;
        if (parsed && parsed.top_similar && parsed.top_similar.length > 0) {
            const top = parsed.top_similar[0];
            const percentage = (top.overall_similarity * 100).toFixed(1);
            const docId = top.doc_id;
            const filename = top.filename || 'Файл';
            return `<a href="/api/report/${docId}" target="_blank" title="${filename}">${percentage}%</a>`;
        }
        return '-';
    } catch {
        return '-';
    }
}

function formatMaxSimilarityWithSpoiler(data) {
    // Use simple format without spoiler
    return formatMaxSimilarity(data);
}

function formatCheatingPercentage(data) {
    if (!data) return '-';
    try {
        const parsed = typeof data === 'string' ? JSON.parse(data) : data;
        if (parsed && parsed.average_llm_likelihood !== undefined) {
            return `${(parsed.average_llm_likelihood * 100).toFixed(1)}%`;
        }
        if (parsed && parsed.content_llm_likelihood !== undefined) {
            return `${(parsed.content_llm_likelihood * 100).toFixed(1)}%`;
        }
        return '-';
    } catch {
        return '-';
    }
}

function formatMetricsSpoiler(data) {
    if (!data) return '-';
    try {
        const parsed = typeof data === 'string' ? JSON.parse(data) : data;
        if (!parsed) return '-';
        
        const metrics = [];
        if (parsed.average_llm_likelihood !== undefined) {
            metrics.push(`LLM вероятность: ${(parsed.average_llm_likelihood * 100).toFixed(1)}%`);
        }
        if (parsed.content && parsed.content.readability !== undefined) {
            metrics.push(`Читаемость: ${parsed.content.readability.toFixed(1)}`);
        }
        if (parsed.content && parsed.content.adjectives_count !== undefined) {
            metrics.push(`Прилагательных: ${parsed.content.adjectives_count}`);
        }
        if (parsed.content && parsed.content.adverbs_count !== undefined) {
            metrics.push(`Наречий: ${parsed.content.adverbs_count}`);
        }
        if (parsed.content && parsed.content.punctuation_errors) {
            const errors = parsed.content.punctuation_errors.total_errors || 0;
            metrics.push(`Ошибки пунктуации: ${errors}`);
        }
        
        if (metrics.length === 0) return '-';
        
        const metricsText = metrics.join(', ');
        return `<details class="metrics-spoiler">
                    <summary>Показать метрики</summary>
                    <div class="metrics-content">${metricsText}</div>
                </details>`;
    } catch {
        return '-';
    }
}

function initTable() {
    if (documentsTable) {
        documentsTable.destroy();
    }
    
    documentsTable = $('#documentsTable').DataTable({
        ajax: {
            url: '/api/documents',
            dataSrc: 'documents'
        },
        dom: 'lrtip', // Removed 'f' (filter) - no search box
        paging: true,
        pageLength: 25,
        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "Все"]],
        initComplete: function() {
            // Move DataTables controls to custom container above table
            const controlsContainer = $('.table-controls-datatables');
            if (controlsContainer.length) {
                // Move length menu
                const lengthWrapper = $('.dataTables_length');
                if (lengthWrapper.length) {
                    lengthWrapper.appendTo(controlsContainer);
                }
                // Filter removed - no search box
                // Move pagination
                const paginateWrapper = $('.dataTables_paginate');
                if (paginateWrapper.length) {
                    paginateWrapper.appendTo(controlsContainer);
                }
            }
        },
        columns: [
            {
                data: null,
                render: function(data, type, row) {
                    return `<input type="checkbox" class="row-checkbox" data-id="${row.id}">`;
                },
                orderable: false,
                width: '25px',
                className: 'text-center'
            },
            { 
                data: 'full_filename',
                render: function(data, type, row) {
                    const filename = data || row.filename || '-';
                    const tasksCount = row.tasks_count || '-';
                    const docId = row.id;
                    const approved = row.approved || 0;
                    const isBlocked = row.processing_status === 'error';
                    
                    // Approve button (only if not blocked)
                    let approveButton = '';
                    if (!isBlocked) {
                        const approveClass = approved ? 'approved-btn' : 'approve-btn';
                        const approveIcon = approved ? 'fa-check-circle' : 'fa-check';
                        approveButton = `<button class="${approveClass}" data-id="${docId}" title="${approved ? 'Одобрено' : 'Одобрить'}"><i class="fas ${approveIcon}"></i></button>`;
                    } else {
                        approveButton = `<button class="blocked-btn" data-id="${docId}" title="Заблокировано" disabled><i class="fas fa-times"></i></button>`;
                    }
                    
                    // Block/Unblock button
                    const blockClass = isBlocked ? 'unblock-btn' : 'block-btn';
                    const blockIcon = isBlocked ? 'fa-unlock' : 'fa-ban';
                    const blockTitle = isBlocked ? 'Разблокировать' : 'Заблокировать';
                    
                    return `<div style="text-align: center;">
                        <div style="margin-bottom: 5px;">
                            <button class="report-btn" data-id="${docId}" title="Открыть отчет"><i class="fas fa-file-alt"></i></button>
                            <button class="reprocess-btn" data-id="${docId}" title="Перепроверить"><i class="fas fa-redo"></i></button>
                            <button class="download-report-btn" data-id="${docId}" title="Загрузить отчет (PDF)"><i class="fas fa-download"></i></button>
                            ${approveButton}
                            <button class="${blockClass}" data-id="${docId}" title="${blockTitle}"><i class="fas ${blockIcon}"></i></button>
                            <button class="delete-btn" data-id="${docId}" title="Удалить"><i class="fas fa-trash"></i></button>
                        </div>
                        <strong><a href="/api/documents/${docId}/download" class="filename-link" title="Скачать оригинал">${filename}</a></strong> <small style="color: #666;">(Заданий: ${tasksCount})</small>
                    </div>`;
                },
                width: '150px',
                className: 'text-center'
            },
            { 
                data: 'created_at',
                render: function(data) {
                    if (!data) return '-';
                    const date = new Date(data);
                    if (isNaN(date.getTime())) return '-';
                    return date.toLocaleString('ru-RU', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                },
                width: '110px',
                className: 'text-center'
            },
            { 
                data: 'tasks_count',
                render: function(data) {
                    return data || '-';
                },
                width: '50px',
                visible: false,
                className: 'text-center'
            },
            { 
                data: 'task_1_score',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    if (data === null || data === undefined || data === '') return '-';
                    const score = parseFloat(data);
                    if (isNaN(score)) return '-';
                    return Math.round(score).toString();
                },
                width: '50px',
                className: 'text-center'
            },
            { 
                data: 'similarity_with_reference',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    if (!data) return '-';
                    try {
                        const parsed = typeof data === 'string' ? JSON.parse(data) : data;
                        return formatSimilarityPercentage(parsed.task_1);
                    } catch {
                        return '-';
                    }
                },
                width: '50px',
                className: 'text-center'
            },
            { 
                data: 'task_2_score',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    if (data === null || data === undefined || data === '') return '-';
                    const score = parseFloat(data);
                    if (isNaN(score)) return '-';
                    return Math.round(score).toString();
                },
                width: '50px',
                className: 'text-center'
            },
            { 
                data: 'similarity_with_reference',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    if (!data) return '-';
                    try {
                        const parsed = typeof data === 'string' ? JSON.parse(data) : data;
                        return formatSimilarityPercentage(parsed.task_2);
                    } catch {
                        return '-';
                    }
                },
                width: '50px',
                className: 'text-center'
            },
            { 
                data: 'task_3_score',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    if (data === null || data === undefined || data === '') return '-';
                    const score = parseFloat(data);
                    if (isNaN(score)) return '-';
                    return Math.round(score).toString();
                },
                width: '50px',
                className: 'text-center'
            },
            { 
                data: 'similarity_with_reference',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    if (!data) return '-';
                    try {
                        const parsed = typeof data === 'string' ? JSON.parse(data) : data;
                        return formatSimilarityPercentage(parsed.task_3);
                    } catch {
                        return '-';
                    }
                },
                width: '50px',
                className: 'text-center'
            },
            { 
                data: null,
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    
                    const originality = row.task_4_originality_score;
                    const logic = row.task_4_logic_score;
                    
                    if ((originality === null || originality === undefined || originality === '') &&
                        (logic === null || logic === undefined || logic === '')) {
                        return '-';
                    }
                    
                    const origVal = originality !== null && originality !== undefined && originality !== '' ? parseFloat(originality) : null;
                    const logicVal = logic !== null && logic !== undefined && logic !== '' ? parseFloat(logic) : null;
                    
                    if (origVal !== null && logicVal !== null) {
                        const avg = (origVal + logicVal) / 2;
                        return Math.round(avg) + '%';
                    } else if (origVal !== null) {
                        return Math.round(origVal) + '%';
                    } else if (logicVal !== null) {
                        return Math.round(logicVal) + '%';
                    }
                    
                    return '-';
                },
                width: '70px',
                className: 'text-center'
            },
            { 
                data: 'average_score_tasks_1_3',
                render: function(data, type, row) {
                    // For sorting: approved items first, then unapproved, then blocked at the end
                    if (type === 'sort' || type === 'type') {
                        const isBlocked = row.processing_status === 'error';
                        const approved = row.approved == 1 || row.approved === '1' || row.approved === true;
                        const score = parseFloat(data) || 0;
                        // Blocked items get negative value (lowest priority)
                        if (isBlocked) {
                            return -1000000 + score;
                        }
                        // Approved items get high value (1000000+score), unapproved get just score
                        // This ensures approved items come first when sorting descending
                        return approved ? (1000000 + score) : score;
                    }
                    // For display
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    if (data === null || data === undefined || data === '') return '-';
                    const score = parseFloat(data);
                    if (isNaN(score)) return '-';
                    return `<strong>${score.toFixed(1)}</strong>`;
                },
                width: '50px',
                className: 'text-center',
                type: 'num'
            },
            { 
                data: 'similarity_with_existing',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    return formatMaxSimilarityWithSpoiler(data);
                },
                width: '70px',
                className: 'text-center'
            },
            { 
                data: 'cheating_score',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    return formatCheatingPercentage(data);
                },
                width: '60px',
                className: 'text-center'
            }
        ],
        language: {
            url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/ru.json'
        },
        // Custom sorting: first by approved status (approved first), then by score descending
        order: [[11, 'desc']], // Sort by average_score_tasks_1_3 (column index 11, custom sort handles approved/unapproved)
        columnDefs: [
            {
                targets: '_all',
                searchable: false // Disable all column filtering
            }
        ],
        drawCallback: function(settings) {
            const api = this.api();
            
            // Get top N value
            const topN = parseInt(document.getElementById('topNInput')?.value || 10);
            
            // Get all visible rows data sorted by average_score_tasks_1_3 (no search filter)
            const allRows = api.rows({order: 'applied'}).nodes();
            
            // Get data for all rows and sort by score
            const rowsData = [];
            $(allRows).each(function() {
                const rowData = api.row(this).data();
                if (rowData) {
                    rowsData.push({
                        element: this,
                        data: rowData,
                        score: parseFloat(rowData.average_score_tasks_1_3) || 0,
                        approved: rowData.approved == 1 || rowData.approved === '1' || rowData.approved === true
                    });
                }
            });
            
            // Sort approved rows by score descending
            const approvedRows = rowsData
                .filter(item => item.approved && item.score > 0)
                .sort((a, b) => b.score - a.score);
            
            // Apply color classes
            rowsData.forEach((item) => {
                const $row = $(item.element);
                $row.removeClass('status-unread status-read status-top-n-approved status-winner status-blocked');
                
                const isBlocked = item.data.processing_status === 'error';
                
                // Check if blocked first
                if (isBlocked) {
                    $row.addClass('status-blocked');
                } else if (item.data.candidate_status === 'winner') {
                    // Check if winner (candidate_status === 'winner')
                    $row.addClass('status-winner');
                } else if (item.approved && item.score > 0) {
                    const rank = approvedRows.findIndex(r => r.data.id === item.data.id);
                    // Automatically highlight top N approved works with light green
                    if (rank >= 0 && rank < topN) {
                        $row.addClass('status-top-n-approved');
                    } else {
                        $row.addClass('status-read');
                    }
                } else {
                    $row.addClass('status-unread');
                }
            });
        },
        rowCallback: function(row, data) {
            // Color will be applied in drawCallback
        },
        pageLength: 25,
        scrollCollapse: true,
        autoWidth: false,
        searching: false // Disable global search
    });
    
    // Handle toggle text buttons
    $('#documentsTable').on('click', '.toggle-text-btn', function() {
        const btn = $(this);
        const preview = btn.siblings('.text-preview');
        const full = btn.siblings('.text-full');
        
        if (full.is(':visible')) {
            full.hide();
            preview.show();
            btn.text('Показать все');
        } else {
            preview.hide();
            full.show();
            btn.text('Скрыть');
        }
    });
    
    // Handle toggle JSON buttons
    $('#documentsTable').on('click', '.toggle-json-btn', function() {
        const btn = $(this);
        const preview = btn.siblings('.json-preview');
        const full = btn.siblings('.json-full');
        
        if (full.is(':visible')) {
            full.hide();
            preview.show();
            btn.text('Показать');
        } else {
            preview.hide();
            full.show();
            btn.text('Скрыть');
        }
    });
}

function refreshTable() {
    if (documentsTable) {
        documentsTable.ajax.reload();
    } else {
        initTable();
    }
}

function exportToCsv() {
    if (!documentsTable) return;
    
    // Fetch all data from API
    fetch('/api/documents')
        .then(response => response.json())
        .then(result => {
            if (result.status !== 'success' || !result.documents) {
                alert('Ошибка получения данных');
                return;
            }
            
            const documents = result.documents;
            if (documents.length === 0) {
                alert('Нет данных для экспорта');
                return;
            }
            
            // Get all column names from first document
            const columns = Object.keys(documents[0]);
            const csvRows = [columns.join(',')];
            
            documents.forEach(doc => {
                const values = columns.map(col => {
                    const val = doc[col];
                    if (val === null || val === undefined) return '';
                    // Convert to string and escape quotes
                    const str = String(val).replace(/"/g, '""');
                    return `"${str}"`;
                });
                csvRows.push(values.join(','));
            });
            
            const csvContent = csvRows.join('\n');
            const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `report_${new Date().toISOString().split('T')[0]}.csv`;
            link.click();
        })
        .catch(error => {
            alert('Ошибка экспорта: ' + error.message);
        });
}

// Refresh button
document.getElementById('refreshBtn').addEventListener('click', () => {
    refreshTable();
});

// Export buttons
document.getElementById('exportFullDbBtn').addEventListener('click', () => {
    window.location.href = '/api/export/full-db';
});

document.getElementById('exportSummaryBtn').addEventListener('click', () => {
    exportSummaryToCsv();
});

// Report and Print buttons
$('#documentsTable').on('click', '.report-btn', function() {
    const docId = $(this).data('id');
    window.open(`/api/report/${docId}`, '_blank');
});

$('#documentsTable').on('click', '.print-btn', function() {
    const docId = $(this).data('id');
    const printWindow = window.open(`/api/report/${docId}`, '_blank');
    printWindow.onload = function() {
        printWindow.print();
    };
});

// Reprocess button
$('#documentsTable').on('click', '.reprocess-btn', function() {
    const docId = $(this).data('id');
    const btn = $(this);
    
    if (btn.prop('disabled')) {
        return;
    }
    
    if (!confirm(`Перепроверить документ #${docId}?`)) {
        return;
    }
    
    btn.prop('disabled', true);
    btn.html('<i class="fas fa-spinner fa-spin"></i>');
    
    fetch(`/api/reprocess/${docId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert('Перепроверка запущена');
            refreshTable();
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
            btn.prop('disabled', false);
            btn.html('<i class="fas fa-redo"></i>');
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
        btn.prop('disabled', false);
        btn.html('<i class="fas fa-redo"></i>');
    });
});

// Reprocess unprocessed button
document.getElementById('reprocessUnprocessedBtn').addEventListener('click', () => {
    const btn = document.getElementById('reprocessUnprocessedBtn');
    
    if (btn.disabled) {
        return;
    }
    
    // Get checked document IDs
    const checkedIds = $('.row-checkbox:checked').map(function() {
        return $(this).data('id');
    }).get();
    
    if (checkedIds.length === 0) {
        return;
    }
    
    // Check if any selected documents are blocked
    fetch('/api/documents')
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success' && result.documents) {
                const checkedDocs = result.documents.filter(doc => checkedIds.includes(doc.id));
                const blockedDocs = checkedDocs.filter(doc => doc.processing_status === 'error');
                
                if (blockedDocs.length > 0) {
                    alert('Нельзя обработать забаненные документы. Сначала разблокируйте их.');
                    return;
                }
                
                if (!confirm(`Обработать ${checkedIds.length} выбранных документов?`)) {
                    return;
                }
                
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                
                // Process each selected document individually
                let processedCount = 0;
                let errorCount = 0;
                const errors = [];
                
                const processNext = (index) => {
                    if (index >= checkedIds.length) {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fas fa-redo"></i>';
                        alert(`Обработка запущена для ${processedCount} документов${errorCount > 0 ? '. Ошибок: ' + errorCount : ''}`);
                        refreshTable();
                        return;
                    }
                    
                    const docId = checkedIds[index];
                    fetch(`/api/reprocess/${docId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    })
                    .then(response => response.json())
                    .then(result => {
                        if (result.status === 'success') {
                            processedCount++;
                        } else {
                            errorCount++;
                            errors.push({ doc_id: docId, error: result.error });
                        }
                        processNext(index + 1);
                    })
                    .catch(error => {
                        errorCount++;
                        errors.push({ doc_id: docId, error: error.message });
                        processNext(index + 1);
                    });
                };
                
                processNext(0);
            }
        })
        .catch(error => {
            console.error('Error checking documents:', error);
            alert('Ошибка при проверке документов: ' + error.message);
        });
});

function exportSummaryToCsv() {
    fetch('/api/documents')
        .then(response => response.json())
        .then(result => {
            if (result.status !== 'success' || !result.documents) {
                alert('Ошибка получения данных');
                return;
            }
            
            const documents = result.documents;
            if (documents.length === 0) {
                alert('Нет данных для экспорта');
                return;
            }
            
            // Summary columns: filename, tasks_count, similarity percentages, scores, max similarity, cheating %
            const csvRows = [];
            csvRows.push(['Файл', 'Кол-во заданий', 
                         'Схожесть с эталоном: Задание 1', 'Балл: Задание 1',
                         'Схожесть с эталоном: Задание 2', 'Балл: Задание 2',
                         'Схожесть с эталоном: Задание 3', 'Балл: Задание 3',
                         'Среднее 1-3', 'Логичность: Задание 4', 'Оригинальность: Задание 4',
                         'Макс. схожесть с другими', '% вероятности читерства'].join(','));
            
            documents.forEach(doc => {
                let simRef = {};
                try {
                    simRef = typeof doc.similarity_with_reference === 'string' 
                        ? JSON.parse(doc.similarity_with_reference) 
                        : doc.similarity_with_reference || {};
                } catch {}
                
                let simExisting = {};
                try {
                    simExisting = typeof doc.similarity_with_existing === 'string'
                        ? JSON.parse(doc.similarity_with_existing)
                        : doc.similarity_with_existing || {};
                } catch {}
                
                let cheating = {};
                try {
                    cheating = typeof doc.cheating_score === 'string'
                        ? JSON.parse(doc.cheating_score)
                        : doc.cheating_score || {};
                } catch {}
                
                const maxSim = simExisting.top_similar && simExisting.top_similar.length > 0
                    ? (simExisting.top_similar[0].overall_similarity * 100).toFixed(1) + '%'
                    : '-';
                
                const cheatingPct = cheating.average_llm_likelihood !== undefined
                    ? (cheating.average_llm_likelihood * 100).toFixed(1) + '%'
                    : '-';
                
                const values = [
                    doc.full_filename || doc.filename || '',
                    doc.tasks_count || '',
                    simRef.task_1 !== undefined ? (simRef.task_1 * 100).toFixed(1) + '%' : '-',
                    doc.task_1_score !== null && doc.task_1_score !== undefined ? Math.round(parseFloat(doc.task_1_score)).toString() : '-',
                    simRef.task_2 !== undefined ? (simRef.task_2 * 100).toFixed(1) + '%' : '-',
                    doc.task_2_score !== null && doc.task_2_score !== undefined ? Math.round(parseFloat(doc.task_2_score)).toString() : '-',
                    simRef.task_3 !== undefined ? (simRef.task_3 * 100).toFixed(1) + '%' : '-',
                    doc.task_3_score !== null && doc.task_3_score !== undefined ? Math.round(parseFloat(doc.task_3_score)).toString() : '-',
                    doc.average_score_tasks_1_3 !== null && doc.average_score_tasks_1_3 !== undefined ? parseFloat(doc.average_score_tasks_1_3).toFixed(1) : '-', // Средняя оценка - до десятых
                    doc.task_4_logic_score !== null && doc.task_4_logic_score !== undefined ? Math.round(parseFloat(doc.task_4_logic_score)).toString() + '%' : '-',
                    doc.task_4_originality_score !== null && doc.task_4_originality_score !== undefined ? Math.round(parseFloat(doc.task_4_originality_score)).toString() + '%' : '-',
                    maxSim,
                    cheatingPct
                ].map(v => `"${String(v).replace(/"/g, '""')}"`);
                
                csvRows.push(values.join(','));
            });
            
            const csvContent = csvRows.join('\n');
            const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `summary_report_${new Date().toISOString().split('T')[0]}.csv`;
            link.click();
        })
        .catch(error => {
            alert('Ошибка экспорта: ' + error.message);
        });
}

// Checkbox handlers
$('#selectAllCheckbox').on('change', function() {
    const checked = $(this).is(':checked');
    $('.row-checkbox').prop('checked', checked);
    updateBatchButtons();
});

$(document).on('change', '.row-checkbox', function() {
    updateBatchButtons();
    // Update select all checkbox state
    const totalRows = $('.row-checkbox').length;
    const checkedRows = $('.row-checkbox:checked').length;
    $('#selectAllCheckbox').prop('checked', totalRows === checkedRows && totalRows > 0);
});

function updateBatchButtons() {
    const checkedCount = $('.row-checkbox:checked').length;
    if (checkedCount > 0) {
        // Get data for checked rows
        const checkedIds = $('.row-checkbox:checked').map(function() {
            return $(this).data('id');
        }).get();
        
        // Fetch data for checked rows to determine their states
        fetch('/api/documents')
            .then(response => response.json())
            .then(result => {
                if (result.status === 'success' && result.documents) {
                    const checkedDocs = result.documents.filter(doc => checkedIds.includes(doc.id));
                    
                    // Count approved/unapproved
                    const approvedCount = checkedDocs.filter(doc => doc.approved == 1 || doc.approved === '1' || doc.approved === true).length;
                    const unapprovedCount = checkedDocs.length - approvedCount;
                    
                    // Count blocked/unblocked
                    const blockedCount = checkedDocs.filter(doc => doc.processing_status === 'error').length;
                    const unblockedCount = checkedDocs.length - blockedCount;
                    
                    // Count unprocessed (pending or error status, but not blocked)
                    const unprocessedCount = checkedDocs.filter(doc => 
                        (doc.processing_status === 'pending' || doc.processing_status === 'error') && 
                        doc.processing_status !== 'error' || !checkedDocs.some(d => d.id === doc.id && d.processing_status === 'error')
                    ).length;
                    
                    // Show/hide approve buttons
                    if (unapprovedCount > 0) {
                        $('#batchApproveBtn').show();
                    } else {
                        $('#batchApproveBtn').hide();
                    }
                    
                    if (approvedCount > 0) {
                        $('#batchUnapproveBtn').show();
                    } else {
                        $('#batchUnapproveBtn').hide();
                    }
                    
                    // Show/hide block buttons
                    if (unblockedCount > 0) {
                        $('#batchBlockBtn').show();
                    } else {
                        $('#batchBlockBtn').hide();
                    }
                    
                    if (blockedCount > 0) {
                        $('#batchUnblockBtn').show();
                    } else {
                        $('#batchUnblockBtn').hide();
                    }
                    
                    // Show/hide reprocess button - only if multiple selected and none are blocked
                    if (checkedCount > 1 && blockedCount === 0) {
                        // Show button if at least one document is unprocessed (pending or error status, but not blocked)
                        const hasUnprocessed = checkedDocs.some(doc => 
                            doc.processing_status === 'pending' || doc.processing_status === 'processing'
                        );
                        if (hasUnprocessed) {
                            $('#reprocessUnprocessedBtn').show();
                        } else {
                            $('#reprocessUnprocessedBtn').hide();
                        }
                    } else {
                        $('#reprocessUnprocessedBtn').hide();
                    }
                    
                    // Always show delete button
                    $('#batchDeleteBtn').show();
                }
            })
            .catch(error => {
                console.error('Error updating batch buttons:', error);
                // Fallback: show all buttons
                $('#batchApproveBtn').show();
                $('#batchUnapproveBtn').show();
                $('#batchBlockBtn').show();
                $('#batchUnblockBtn').show();
                $('#batchDeleteBtn').show();
            });
    } else {
        $('#batchApproveBtn').hide();
        $('#batchUnapproveBtn').hide();
        $('#batchBlockBtn').hide();
        $('#batchUnblockBtn').hide();
        $('#batchDeleteBtn').hide();
    }
}

// Batch approve
$('#batchApproveBtn').on('click', function() {
    const checkedIds = $('.row-checkbox:checked').map(function() {
        return $(this).data('id');
    }).get();
    
    if (checkedIds.length === 0) {
        alert('Выберите документы для одобрения');
        return;
    }
    
    if (!confirm(`Одобрить ${checkedIds.length} документ(ов)?`)) {
        return;
    }
    
    fetch('/api/documents/batch-approve', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ doc_ids: checkedIds })
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert(`Одобрено ${result.count} документ(ов)`);
            refreshTable();
            // Redraw to update row colors
            if (documentsTable) {
                setTimeout(() => documentsTable.draw(), 100);
            }
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    });
});

// Batch block
$('#batchBlockBtn').on('click', function() {
    const checkedIds = $('.row-checkbox:checked').map(function() {
        return $(this).data('id');
    }).get();
    
    if (checkedIds.length === 0) {
        alert('Выберите документы для блокировки');
        return;
    }
    
    if (!confirm(`Заблокировать ${checkedIds.length} документ(ов)?`)) {
        return;
    }
    
    fetch('/api/documents/batch-block', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ doc_ids: checkedIds })
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert(`Заблокировано ${result.count} документ(ов)`);
            refreshTable();
            // Redraw to update row colors
            if (documentsTable) {
                setTimeout(() => documentsTable.draw(), 100);
            }
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    });
});

// Batch unapprove
$('#batchUnapproveBtn').on('click', function() {
    const checkedIds = $('.row-checkbox:checked').map(function() {
        return $(this).data('id');
    }).get();
    
    if (checkedIds.length === 0) {
        alert('Выберите документы для отмены одобрения');
        return;
    }
    
    if (!confirm(`Отменить одобрение ${checkedIds.length} документ(ов)?`)) {
        return;
    }
    
    fetch('/api/documents/batch-unapprove', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ doc_ids: checkedIds })
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert(`Отменено одобрение ${result.count} документ(ов)`);
            refreshTable();
            // Redraw to update row colors
            if (documentsTable) {
                setTimeout(() => documentsTable.draw(), 100);
            }
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    });
});

// Batch delete
$('#batchDeleteBtn').on('click', function() {
    const checkedIds = $('.row-checkbox:checked').map(function() {
        return $(this).data('id');
    }).get();
    
    if (checkedIds.length === 0) {
        alert('Выберите документы для удаления');
        return;
    }
    
    if (!confirm(`Удалить ${checkedIds.length} документ(ов)? Это действие нельзя отменить!`)) {
        return;
    }
    
    fetch('/api/documents/batch-delete', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ doc_ids: checkedIds })
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert(`Удалено ${result.count} документ(ов)`);
            refreshTable();
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    });
});

// Approve/Unapprove button
$('#documentsTable').on('click', '.approve-btn, .approved-btn', function() {
    const docId = $(this).data('id');
    const btn = $(this);
    const isApproved = btn.hasClass('approved-btn');
    
    const endpoint = isApproved ? `/api/documents/${docId}/unapprove` : `/api/documents/${docId}/approve`;
    const action = isApproved ? 'отмены одобрения' : 'одобрения';
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            refreshTable();
            // Redraw to update row colors
            if (documentsTable) {
                setTimeout(() => documentsTable.draw(), 100);
            }
        } else {
            alert('Ошибка ' + action + ': ' + (result.error || 'Неизвестная ошибка'));
        }
    })
    .catch(error => {
        alert('Ошибка ' + action + ': ' + error.message);
    });
});

// Block/Unblock button
$('#documentsTable').on('click', '.block-btn, .unblock-btn', function() {
    const docId = $(this).data('id');
    const isBlocked = $(this).hasClass('unblock-btn');
    const action = isBlocked ? 'разблокировать' : 'заблокировать';
    const endpoint = isBlocked ? `/api/documents/${docId}/unblock` : `/api/documents/${docId}/block`;
    
    if (!confirm(`${isBlocked ? 'Разблокировать' : 'Заблокировать'} документ #${docId}?`)) {
        return;
    }
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert(`Документ ${isBlocked ? 'разблокирован' : 'заблокирован'}`);
            refreshTable();
            // Redraw to update row colors
            if (documentsTable) {
                setTimeout(() => documentsTable.draw(), 100);
            }
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    });
});

// Delete button
$('#documentsTable').on('click', '.delete-btn', function() {
    const docId = $(this).data('id');
    
    if (!confirm(`Удалить документ #${docId}? Это действие нельзя отменить!`)) {
        return;
    }
    
    fetch(`/api/documents/${docId}/delete`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert('Документ удален');
            refreshTable();
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
    });
});

// Download report button
$('#documentsTable').on('click', '.download-report-btn', function() {
    const docId = $(this).data('id');
    window.open(`/api/report/${docId}/export-pdf`, '_blank');
});

// Chart instances
let statusChart = null;
let scoreChart = null;
let timelineChart = null;

// Initialize charts
function initCharts() {
    fetch('/api/statistics')
        .then(response => response.json())
        .then(result => {
            if (result.status !== 'success') {
                console.error('Error loading statistics:', result.error);
                return;
            }
            
            const data = result;
            
            // Status Chart (Pie) - не одобренные, одобренные, заблокированные
            const statusCtx = document.getElementById('statusChart');
            if (statusCtx && Chart) {
                if (statusChart) statusChart.destroy();
                
                const pieData = data.pie_chart || {};
                const unread = pieData.unread || 0;
                const approved = pieData.approved || 0;
                const blocked = pieData.blocked || 0;
                
                statusChart = new Chart(statusCtx, {
                    type: 'pie',
                    data: {
                        labels: ['Не одобренные', 'Одобренные', 'Заблокированные'],
                        datasets: [{
                            data: [unread, approved, blocked],
                            backgroundColor: [
                                '#64b5f6', // светло-синий (не одобренные)
                                '#1e3a8a', // темно-синий (одобренные)
                                '#9c27b0'  // фиолетовый (забаненные)
                            ],
                            borderColor: '#ffffff',
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        layout: {
                            padding: 20
                        },
                        plugins: {
                            legend: {
                                display: false
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                        return `${label}: ${value} (${percentage}%)`;
                                    }
                                }
                            }
                        }
                    }
                });
            }
            
            // Score Chart (Bar)
            const scoreCtx = document.getElementById('scoreChart');
            if (scoreCtx && Chart) {
                if (scoreChart) scoreChart.destroy();
                scoreChart = new Chart(scoreCtx, {
                    type: 'bar',
                    data: {
                        labels: ['0-2', '2-4', '4-6', '6-8', '8-10'],
                        datasets: [{
                            label: 'Количество работ',
                            data: [
                                data.score_distribution['0-2'] || 0,
                                data.score_distribution['2-4'] || 0,
                                data.score_distribution['4-6'] || 0,
                                data.score_distribution['6-8'] || 0,
                                data.score_distribution['8-10'] || 0
                            ],
                            backgroundColor: '#1e3a8a',
                            borderColor: '#1e40af',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    color: '#000000',
                                    stepSize: 1
                                },
                                grid: {
                                    color: '#dee2e6'
                                }
                            },
                            x: {
                                ticks: {
                                    color: '#000000'
                                },
                                grid: {
                                    color: '#dee2e6'
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
            }
            
            // Timeline Chart (Line)
            const timelineCtx = document.getElementById('timelineChart');
            if (timelineCtx && Chart) {
                if (timelineChart) timelineChart.destroy();
                timelineChart = new Chart(timelineCtx, {
                    type: 'line',
                    data: {
                        labels: data.timeline.labels || [],
                        datasets: [{
                            label: 'Загружено работ',
                            data: data.timeline.values || [],
                            borderColor: '#1e3a8a',
                            backgroundColor: 'rgba(30, 58, 138, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    color: '#e2e8f0',
                                    stepSize: 1
                                },
                                grid: {
                                    color: '#334155'
                                }
                            },
                            x: {
                                ticks: {
                                    color: '#e2e8f0'
                                },
                                grid: {
                                    color: '#334155'
                                }
                            }
                        },
                        plugins: {
                            legend: {
                                display: false
                            }
                        }
                    }
                });
            }
        })
        .catch(error => {
            console.error('Error loading statistics:', error);
        });
}

// Check for winners and show/hide send messages button
function checkWinners() {
    fetch('/api/documents')
        .then(response => response.json())
        .then(result => {
            if (result.status === 'success' && result.documents) {
                const winners = result.documents.filter(doc => doc.candidate_status === 'winner');
                const sendBtn = document.getElementById('sendMessagesBtn');
                const completeBtn = document.getElementById('completeCompetitionBtn');
                const startBtn = document.getElementById('startCompetitionBtn');
                
                // Show/hide complete/start buttons based on competition status
                if (winners.length > 0) {
                    // Competition is completed
                    if (completeBtn) completeBtn.style.display = 'none';
                    if (startBtn) startBtn.style.display = 'inline-flex';
                } else {
                    // Competition is not completed
                    if (completeBtn) completeBtn.style.display = 'inline-flex';
                    if (startBtn) startBtn.style.display = 'none';
                }
                
                // Handle send messages button
                if (sendBtn) {
                    if (winners.length > 0) {
                        sendBtn.style.display = 'inline-flex';
                        // Check if messages already sent
                        const allSent = winners.every(w => w.messages_sent);
                        if (allSent) {
                            // Remove text, keep only icon
                            sendBtn.innerHTML = '<i class="fas fa-check-circle"></i>';
                            sendBtn.disabled = true;
                            sendBtn.classList.add('messages-sent');
                        } else {
                            // Reset to initial state
                            sendBtn.innerHTML = '<i class="fas fa-envelope"></i>';
                            sendBtn.disabled = false;
                            sendBtn.classList.remove('messages-sent');
                        }
                    } else {
                        // No winners - hide button and reset to initial state
                        sendBtn.style.display = 'none';
                        sendBtn.innerHTML = '<i class="fas fa-envelope"></i>';
                        sendBtn.disabled = false;
                        sendBtn.classList.remove('messages-sent');
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error checking winners:', error);
        });
}

// Complete competition handler
document.getElementById('completeCompetitionBtn')?.addEventListener('click', function() {
    const topN = parseInt(document.getElementById('topNInput').value) || 10;
    
    if (topN < 1) {
        alert('Топ N должно быть больше 0');
        return;
    }
    
    // Check if there are enough approved works
    fetch('/api/statistics')
        .then(response => response.json())
        .then(result => {
            if (result.status !== 'success') {
                alert('Ошибка получения статистики');
                return;
            }
            
            const approvedCount = result.pie_chart?.approved || 0;
            
            if (approvedCount < topN) {
                const message = `Недостаточно одобренных работ! Одобрено: ${approvedCount}, требуется: ${topN}.\n\nПродолжить завершение конкурса?`;
                if (!confirm(message)) {
                    return;
                }
            } else {
                if (!confirm(`Завершить конкурс и выбрать топ-${topN} победителей?`)) {
                    return;
                }
            }
            
            const btn = this;
            btn.disabled = true;
            const originalHTML = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            
            fetch('/api/competition/complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ top_n: topN })
            })
            .then(response => response.json())
            .then(result => {
                if (result.status === 'success') {
                    alert(`Конкурс завершен! Выбрано ${result.winners_count} победителей.`);
                    refreshTable();
                    initCharts();
                    checkWinners();
                    // Trigger redraw to update row colors
                    if (documentsTable) {
                        setTimeout(() => documentsTable.draw(), 100);
                    }
                } else {
                    alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
                }
                btn.disabled = false;
                btn.innerHTML = originalHTML;
            })
            .catch(error => {
                alert('Ошибка: ' + error.message);
                btn.disabled = false;
                btn.innerHTML = originalHTML;
            });
        })
        .catch(error => {
            alert('Ошибка получения статистики: ' + error.message);
        });
});

// Send messages handler
document.getElementById('sendMessagesBtn')?.addEventListener('click', function() {
    const btn = this;
    
    if (btn.disabled) {
        return;
    }
    
    if (!confirm('Отправить сообщения всем победителям?')) {
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';
    
    fetch('/api/winners/send-messages', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            // Remove text, keep only icon
            btn.innerHTML = '<i class="fas fa-check-circle"></i>';
            btn.classList.add('messages-sent');
            alert('Сообщения отправлены победителям!');
            refreshTable();
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-envelope"></i>';
        }
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-envelope"></i>';
    });
});

// Start competition handler
document.getElementById('startCompetitionBtn')?.addEventListener('click', function() {
    if (!confirm('Начать новый конкурс? Это сбросит статусы победителей и выделения строк.')) {
        return;
    }
    
    const btn = this;
    btn.disabled = true;
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    fetch('/api/competition/start', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert(`Конкурс начат! Сброшено ${result.reset_count} документ(ов).`);
            refreshTable();
            initCharts();
            checkWinners();
            // Trigger redraw to reset row colors
            if (documentsTable) {
                setTimeout(() => documentsTable.draw(), 100);
            }
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
        }
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    });
});

// Listen for top N input changes to update row colors
document.getElementById('topNInput')?.addEventListener('change', function() {
    if (documentsTable) {
        documentsTable.draw();
    }
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initTable();
    initCharts();
    checkWinners();
    
    // Refresh charts when table is refreshed
    const originalRefresh = refreshTable;
    refreshTable = function() {
        originalRefresh();
        setTimeout(() => {
            initCharts();
            checkWinners();
            // Redraw table to update row colors
            if (documentsTable) {
                documentsTable.draw();
            }
        }, 500);
    };
});
