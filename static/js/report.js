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
        dom: 'lfrtip',
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
                // Move filter
                const filterWrapper = $('.dataTables_filter');
                if (filterWrapper.length) {
                    filterWrapper.appendTo(controlsContainer);
                }
                // Move pagination
                const paginateWrapper = $('.dataTables_paginate');
                if (paginateWrapper.length) {
                    paginateWrapper.appendTo(controlsContainer);
                }
            }
            
            // Add individual column search inputs with operators for numeric columns
            this.api().columns().every(function(index) {
                const column = this;
                const header = $(column.header());
                
                // Skip if column is not orderable (like action buttons or checkboxes)
                if (!column.orderable() || index === 0) {
                    return;
                }
                
                // Determine if this is a numeric column (scores, percentages)
                const columnData = column.dataSrc();
                const isNumeric = columnData && (
                    columnData.includes('score') || 
                    columnData.includes('similarity') ||
                    columnData.includes('cheating') ||
                    columnData.includes('originality') ||
                    columnData.includes('logic') ||
                    columnData.includes('average')
                );
                
                if (isNumeric) {
                    // Create container for operator and input
                    const container = $('<div style="display: flex; gap: 4px; align-items: center;"></div>').appendTo(header);
                    
                    // Create operator select
                    const operatorSelect = $('<select style="padding: 4px; font-size: 11px; width: 50px;"><option value="=">=</option><option value=">">&gt;</option><option value="<">&lt;</option></select>')
                        .appendTo(container);
                    
                    // Create input element
                    const input = $('<input type="number" placeholder="Значение" step="0.1" style="width: 100%; padding: 4px; font-size: 12px;"/>')
                        .appendTo(container);
                    
                    // Custom search function
                    let searchFunction = null;
                    const performSearch = function() {
                        const operator = operatorSelect.val();
                        const value = input.val();
                        
                        // Remove old search function if exists
                        if (searchFunction) {
                            $.fn.dataTable.ext.search.pop();
                            searchFunction = null;
                        }
                        
                        if (!value) {
                            column.search('').draw();
                            return;
                        }
                        
                        // Create new search function
                        searchFunction = function(settings, data, dataIndex) {
                            if (settings.nTable.id !== 'documentsTable') {
                                return true;
                            }
                            
                            const cellValue = parseFloat(data[index]) || 0;
                            const searchValue = parseFloat(value);
                            
                            if (isNaN(searchValue)) {
                                return true;
                            }
                            
                            if (operator === '>') {
                                return cellValue > searchValue;
                            } else if (operator === '<') {
                                return cellValue < searchValue;
                            } else {
                                return Math.abs(cellValue - searchValue) < 0.01;
                            }
                        };
                        
                        // Add search function
                        $.fn.dataTable.ext.search.push(searchFunction);
                        column.draw();
                    };
                    
                    operatorSelect.on('change', performSearch);
                    input.on('keyup change', performSearch);
                } else {
                    // Create simple input element for text columns
                    const input = $('<input type="text" placeholder="Поиск..." style="width: 100%; padding: 4px; font-size: 12px;"/>')
                        .appendTo(header)
                        .on('keyup change', function() {
                            if (column.search() !== this.value) {
                                column.search(this.value).draw();
                            }
                        });
                }
            });
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
                    const approveClass = approved ? 'approved-btn' : 'approve-btn';
                    const approveIcon = approved ? 'fa-check-circle' : 'fa-check';
                    return `<div style="text-align: center;">
                        <div style="margin-bottom: 5px;">
                            <button class="report-btn" data-id="${docId}" title="Открыть отчет"><i class="fas fa-file-alt"></i></button>
                            <button class="reprocess-btn" data-id="${docId}" title="Перепроверить"><i class="fas fa-redo"></i></button>
                            <button class="download-report-btn" data-id="${docId}" title="Загрузить отчет (PDF)"><i class="fas fa-download"></i></button>
                            <button class="${approveClass}" data-id="${docId}" title="${approved ? 'Одобрено' : 'Одобрить'}"><i class="fas ${approveIcon}"></i></button>
                            <button class="delete-btn" data-id="${docId}" title="Удалить"><i class="fas fa-trash"></i></button>
                        </div>
                        <strong><a href="/api/documents/${docId}/download" class="filename-link" title="Скачать оригинал">${filename}</a></strong><br><small>Заданий: ${tasksCount}</small>
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
                    return score.toFixed(1);
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
                    return score.toFixed(1);
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
                    return score.toFixed(1);
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
                        return avg.toFixed(1) + '%';
                    } else if (origVal !== null) {
                        return origVal.toFixed(1) + '%';
                    } else if (logicVal !== null) {
                        return logicVal.toFixed(1) + '%';
                    }
                    
                    return '-';
                },
                width: '70px',
                className: 'text-center'
            },
            { 
                data: 'average_score_tasks_1_3',
                render: function(data, type, row) {
                    const status = row.processing_status;
                    if (status === 'processing') return '<i class="fas fa-spinner fa-spin"></i>';
                    if (status === 'error' || status === 'pending') return '-';
                    if (data === null || data === undefined || data === '') return '-';
                    const score = parseFloat(data);
                    if (isNaN(score)) return '-';
                    return `<strong>${score.toFixed(1)}</strong>`;
                },
                width: '50px',
                className: 'text-center'
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
                order: [[1, 'desc']],
        rowCallback: function(row, data) {
            // Highlight rows based on approval status
            if (data.approved === 0 || !data.approved) {
                $(row).addClass('not-approved-row');
            } else {
                $(row).addClass('approved-row');
            }
        },
        pageLength: 25,
        scrollCollapse: true,
        autoWidth: false,
        searching: true,
        columnDefs: [
            {
                targets: '_all',
                searchable: true
            }
        ]
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
    
    if (!confirm('Обработать все необработанные документы?')) {
        return;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    
    fetch('/api/reprocess-unprocessed', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            alert(`Запущена обработка ${result.count} документов${result.errors ? '. Ошибки: ' + result.errors.length : ''}`);
            refreshTable();
        } else {
            alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
        }
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-redo"></i>';
    })
    .catch(error => {
        alert('Ошибка: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-redo"></i>';
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
                    doc.task_1_score !== null && doc.task_1_score !== undefined ? parseFloat(doc.task_1_score).toFixed(1) : '-',
                    simRef.task_2 !== undefined ? (simRef.task_2 * 100).toFixed(1) + '%' : '-',
                    doc.task_2_score !== null && doc.task_2_score !== undefined ? parseFloat(doc.task_2_score).toFixed(1) : '-',
                    simRef.task_3 !== undefined ? (simRef.task_3 * 100).toFixed(1) + '%' : '-',
                    doc.task_3_score !== null && doc.task_3_score !== undefined ? parseFloat(doc.task_3_score).toFixed(1) : '-',
                    doc.average_score_tasks_1_3 !== null && doc.average_score_tasks_1_3 !== undefined ? parseFloat(doc.average_score_tasks_1_3).toFixed(1) : '-',
                    doc.task_4_logic_score !== null && doc.task_4_logic_score !== undefined ? parseFloat(doc.task_4_logic_score).toFixed(1) + '%' : '-',
                    doc.task_4_originality_score !== null && doc.task_4_originality_score !== undefined ? parseFloat(doc.task_4_originality_score).toFixed(1) + '%' : '-',
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
        $('#batchApproveBtn').show();
        $('#batchDeleteBtn').show();
    } else {
        $('#batchApproveBtn').hide();
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

// Approve button
$('#documentsTable').on('click', '.approve-btn', function() {
    const docId = $(this).data('id');
    const btn = $(this);
    
    fetch(`/api/documents/${docId}/approve`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            refreshTable();
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

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initTable();
});
