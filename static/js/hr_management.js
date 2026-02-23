// HR Management JavaScript

let currentContestId = null;
let taskCounter = 0;

$(document).ready(function() {
    loadContests();
    
    $('#add-task-btn').on('click', addTask);
    $('#contest-form').on('submit', saveContest);
    $('#cancel-edit-btn').on('click', cancelEdit);
});

function showAlert(message, type = 'success') {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-error';
    const alert = $(`
        <div class="alert ${alertClass}">
            ${message}
        </div>
    `);
    
    $('#alert-container').html(alert);
    
    setTimeout(() => {
        alert.fadeOut(() => alert.remove());
    }, 5000);
}

function loadContests() {
    $.ajax({
        url: '/hr/contests',
        method: 'GET',
        success: function(response) {
            if (response.status === 'success') {
                renderContestsList(response.contests);
            }
        },
        error: function(xhr) {
            showAlert('Ошибка загрузки конкурсов', 'error');
        }
    });
}

function renderContestsList(contests) {
    const container = $('#contests-list-container');
    container.empty();
    
    if (contests.length === 0) {
        container.html('<p>Нет созданных конкурсов</p>');
        return;
    }
    
    contests.forEach(contest => {
        const item = $(`
            <div class="contest-item">
                <div class="contest-info">
                    <h4>${escapeHtml(contest.name)} ${contest.is_active ? '' : '(неактивен)'}</h4>
                    <p>${escapeHtml(contest.description || 'Без описания')}</p>
                    <p style="font-size: 12px; color: #999;">
                        Создан: ${new Date(contest.created_at).toLocaleString('ru-RU')}
                    </p>
                </div>
                <div class="contest-actions">
                    <button class="btn btn-primary btn-small" onclick="editContest(${contest.id})">
                        Редактировать
                    </button>
                    <button class="btn btn-danger btn-small" onclick="deleteContest(${contest.id})">
                        Удалить
                    </button>
                </div>
            </div>
        `);
        container.append(item);
    });
}

function addTask() {
    taskCounter++;
    const taskNumber = taskCounter;
    
    const taskCard = $(`
        <div class="task-card" data-task-number="${taskNumber}">
            <div class="task-header">
                <h3>Задание ${taskNumber}</h3>
                <button type="button" class="btn btn-danger btn-small remove-task-btn">
                    Удалить задание
                </button>
            </div>
            
            <div class="form-group">
                <label>Номер задания *</label>
                <input type="number" class="task-number-input" min="1" max="4" value="${taskNumber}" required>
            </div>
            
            <div class="form-group">
                <label>Текст задания *</label>
                <textarea class="task-text-input" required></textarea>
            </div>
            
            <div class="form-group">
                <label>Эталонный ответ</label>
                <textarea class="reference-answer-input"></textarea>
            </div>
            
            <h4>Критерии оценки</h4>
            <div class="criteria-container" data-task-id="${taskNumber}">
                <!-- Criteria will be added here -->
            </div>
            
            <button type="button" class="btn btn-secondary btn-small add-criterion-btn" data-task-id="${taskNumber}">
                + Добавить критерий
            </button>
        </div>
    `);
    
    $('#tasks-container').append(taskCard);
    
    // Bind events
    taskCard.find('.remove-task-btn').on('click', function() {
        taskCard.remove();
    });
    
    taskCard.find('.add-criterion-btn').on('click', function() {
        addCriterion(taskNumber);
    });
}

function addCriterion(taskNumber) {
    const criteriaContainer = $(`.criteria-container[data-task-id="${taskNumber}"]`);
    const criterionNumber = criteriaContainer.children().length + 1;
    
    const criterionItem = $(`
        <div class="criterion-item" data-criterion-number="${criterionNumber}">
            <div class="criterion-number">${criterionNumber}</div>
            <input type="number" class="criterion-number-input" value="${criterionNumber}" min="1" placeholder="№" style="width: 60px;">
            <textarea class="criterion-text-input" placeholder="Текст критерия *" required></textarea>
            <input type="number" class="weight-input" value="1.0" min="0" step="0.1" placeholder="Вес">
            <button type="button" class="btn btn-danger btn-small remove-criterion-btn">×</button>
        </div>
    `);
    
    criteriaContainer.append(criterionItem);
    
    criterionItem.find('.remove-criterion-btn').on('click', function() {
        criterionItem.remove();
        updateCriterionNumbers(taskNumber);
    });
}

function updateCriterionNumbers(taskNumber) {
    const criteriaContainer = $(`.criteria-container[data-task-id="${taskNumber}"]`);
    criteriaContainer.children().each(function(index) {
        const newNumber = index + 1;
        $(this).attr('data-criterion-number', newNumber);
        $(this).find('.criterion-number').text(newNumber);
        $(this).find('.criterion-number-input').val(newNumber);
    });
}

function saveContest(e) {
    e.preventDefault();
    
    const contestId = $('#contest-id').val();
    const name = $('#contest-name').val().trim();
    const description = $('#contest-description').val().trim();
    const isActive = $('#contest-active').is(':checked') ? 1 : 0;
    
    if (!name) {
        showAlert('Название конкурса обязательно', 'error');
        return;
    }
    
    // Collect tasks data
    const tasks = {};
    $('.task-card').each(function() {
        const taskNumber = parseInt($(this).find('.task-number-input').val());
        const taskText = $(this).find('.task-text-input').val().trim();
        const referenceAnswer = $(this).find('.reference-answer-input').val().trim();
        
        if (!taskNumber || taskNumber < 1 || taskNumber > 4) {
            showAlert('Номер задания должен быть от 1 до 4', 'error');
            return false;
        }
        
        if (!taskText) {
            showAlert('Текст задания обязателен', 'error');
            return false;
        }
        
        // Collect criteria
        const criteria = [];
        $(this).find('.criterion-item').each(function() {
            const criterionNumber = parseInt($(this).find('.criterion-number-input').val());
            const criterionText = $(this).find('.criterion-text-input').val().trim();
            const weight = parseFloat($(this).find('.weight-input').val()) || 1.0;
            
            if (criterionNumber && criterionText) {
                criteria.push({
                    criterion_number: criterionNumber,
                    criterion_text: criterionText,
                    weight: weight
                });
            }
        });
        
        tasks[taskNumber] = {
            task_text: taskText,
            reference_answer: referenceAnswer,
            criteria: criteria
        };
    });
    
    const data = {
        name: name,
        description: description,
        is_active: isActive,
        tasks: tasks
    };
    
    let url, method;
    if (contestId) {
        url = `/hr/contests/${contestId}/save-all`;
        method = 'POST';
    } else {
        // First create contest, then save tasks
        $.ajax({
            url: '/hr/contests',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                name: name,
                description: description,
                is_active: isActive
            }),
            success: function(response) {
                if (response.status === 'success') {
                    const newContestId = response.contest_id;
                    saveContestTasks(newContestId, tasks);
                } else {
                    showAlert('Ошибка создания конкурса: ' + (response.error || 'Неизвестная ошибка'), 'error');
                }
            },
            error: function(xhr) {
                const error = xhr.responseJSON?.error || 'Ошибка создания конкурса';
                showAlert(error, 'error');
            }
        });
        return;
    }
    
    // Update existing contest
    $.ajax({
        url: url,
        method: method,
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            if (response.status === 'success') {
                showAlert('Конкурс успешно сохранен', 'success');
                resetForm();
                loadContests();
            } else {
                showAlert('Ошибка сохранения: ' + (response.error || 'Неизвестная ошибка'), 'error');
            }
        },
        error: function(xhr) {
            const error = xhr.responseJSON?.error || 'Ошибка сохранения конкурса';
            showAlert(error, 'error');
        }
    });
}

function saveContestTasks(contestId, tasks) {
    // Save each task
    const taskPromises = [];
    
    for (const [taskNumber, taskData] of Object.entries(tasks)) {
        const taskPromise = $.ajax({
            url: `/hr/contests/${contestId}/tasks`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                task_number: parseInt(taskNumber),
                task_text: taskData.task_text,
                reference_answer: taskData.reference_answer || ''
            })
        });
        taskPromises.push(taskPromise);
        
        // Save criteria for this task
        if (taskData.criteria && taskData.criteria.length > 0) {
            taskData.criteria.forEach(criterion => {
                const critPromise = $.ajax({
                    url: `/hr/contests/${contestId}/tasks/${taskNumber}/criteria`,
                    method: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(criterion)
                });
                taskPromises.push(critPromise);
            });
        }
    }
    
    Promise.all(taskPromises).then(() => {
        showAlert('Конкурс успешно создан', 'success');
        resetForm();
        loadContests();
    }).catch(function(error) {
        showAlert('Ошибка сохранения заданий: ' + (error.responseJSON?.error || 'Неизвестная ошибка'), 'error');
    });
}

function editContest(contestId) {
    currentContestId = contestId;
    
    $.ajax({
        url: `/hr/contests/${contestId}`,
        method: 'GET',
        success: function(response) {
            if (response.status === 'success') {
                const contest = response.contest;
                loadContestIntoForm(contest);
                $('#form-title').text('Редактировать конкурс');
                $('#cancel-edit-btn').show();
                $('html, body').animate({ scrollTop: 0 }, 500);
            } else {
                showAlert('Ошибка загрузки конкурса', 'error');
            }
        },
        error: function(xhr) {
            showAlert('Ошибка загрузки конкурса', 'error');
        }
    });
}

function loadContestIntoForm(contest) {
    $('#contest-id').val(contest.id);
    $('#contest-name').val(contest.name);
    $('#contest-description').val(contest.description || '');
    $('#contest-active').prop('checked', contest.is_active === 1);
    
    // Clear tasks
    $('#tasks-container').empty();
    taskCounter = 0;
    
    // Load tasks
    if (contest.tasks) {
        for (const [taskNumber, task] of Object.entries(contest.tasks)) {
            taskCounter++;
            const taskCard = createTaskCardFromData(parseInt(taskNumber), task);
            $('#tasks-container').append(taskCard);
        }
    }
}

function createTaskCardFromData(taskNumber, taskData) {
    const taskCard = $(`
        <div class="task-card" data-task-number="${taskNumber}">
            <div class="task-header">
                <h3>Задание ${taskNumber}</h3>
                <button type="button" class="btn btn-danger btn-small remove-task-btn">
                    Удалить задание
                </button>
            </div>
            
            <div class="form-group">
                <label>Номер задания *</label>
                <input type="number" class="task-number-input" min="1" max="4" value="${taskNumber}" required>
            </div>
            
            <div class="form-group">
                <label>Текст задания *</label>
                <textarea class="task-text-input" required>${escapeHtml(taskData.task_text || '')}</textarea>
            </div>
            
            <div class="form-group">
                <label>Эталонный ответ</label>
                <textarea class="reference-answer-input">${escapeHtml(taskData.reference_answer || '')}</textarea>
            </div>
            
            <h4>Критерии оценки</h4>
            <div class="criteria-container" data-task-id="${taskNumber}">
                <!-- Criteria will be added here -->
            </div>
            
            <button type="button" class="btn btn-secondary btn-small add-criterion-btn" data-task-id="${taskNumber}">
                + Добавить критерий
            </button>
        </div>
    `);
    
    // Load criteria
    if (taskData.criteria && taskData.criteria.length > 0) {
        const criteriaContainer = taskCard.find('.criteria-container');
        taskData.criteria.forEach(criterion => {
            const criterionItem = $(`
                <div class="criterion-item" data-criterion-number="${criterion.criterion_number}">
                    <div class="criterion-number">${criterion.criterion_number}</div>
                    <input type="number" class="criterion-number-input" value="${criterion.criterion_number}" min="1" placeholder="№" style="width: 60px;">
                    <textarea class="criterion-text-input" placeholder="Текст критерия *" required>${escapeHtml(criterion.criterion_text || '')}</textarea>
                    <input type="number" class="weight-input" value="${criterion.weight || 1.0}" min="0" step="0.1" placeholder="Вес">
                    <button type="button" class="btn btn-danger btn-small remove-criterion-btn">×</button>
                </div>
            `);
            criteriaContainer.append(criterionItem);
        });
    }
    
    // Bind events
    taskCard.find('.remove-task-btn').on('click', function() {
        taskCard.remove();
    });
    
    taskCard.find('.add-criterion-btn').on('click', function() {
        addCriterion(taskNumber);
    });
    
    taskCard.find('.remove-criterion-btn').on('click', function() {
        $(this).closest('.criterion-item').remove();
        updateCriterionNumbers(taskNumber);
    });
    
    return taskCard;
}

function deleteContest(contestId) {
    if (!confirm('Вы уверены, что хотите удалить этот конкурс? Все задания и критерии также будут удалены.')) {
        return;
    }
    
    $.ajax({
        url: `/hr/contests/${contestId}`,
        method: 'DELETE',
        success: function(response) {
            if (response.status === 'success') {
                showAlert('Конкурс успешно удален', 'success');
                loadContests();
                if (currentContestId === contestId) {
                    resetForm();
                }
            } else {
                showAlert('Ошибка удаления: ' + (response.error || 'Неизвестная ошибка'), 'error');
            }
        },
        error: function(xhr) {
            const error = xhr.responseJSON?.error || 'Ошибка удаления конкурса';
            showAlert(error, 'error');
        }
    });
}

function cancelEdit() {
    resetForm();
}

function resetForm() {
    currentContestId = null;
    $('#contest-form')[0].reset();
    $('#contest-id').val('');
    $('#tasks-container').empty();
    taskCounter = 0;
    $('#form-title').text('Создать новый конкурс');
    $('#cancel-edit-btn').hide();
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
