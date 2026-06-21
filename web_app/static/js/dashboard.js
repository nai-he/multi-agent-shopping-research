/* 仪表盘 JavaScript */

let aiIntent = null; // 存储 AI 解析结果
let lastAnalyzedQuery = '';
let analyzeRequestSeq = 0;
let activeAnalyzeRequestId = 0;

$(document).ready(function() {
    // 加载统计信息
    loadStats();

    // 加载最近查询
    loadRecentQueries();

    // 表单提交
    $('#queryForm').on('submit', function(e) {
        e.preventDefault();
        submitQuery();
    });

    // AI 解析按钮
    $('#analyzeIntentBtn').on('click', function() {
        analyzeIntent();
    });

    $('#queryInput').on('input', function() {
        syncIntentWithQueryInput();
    });

    $('.region-option').on('click', function() {
        const location = $(this).data('location');
        selectRegion(location);

        const modalEl = document.getElementById('regionPickerModal');
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) {
            modal.hide();
        }
    });

    selectRegion($('#locationSelect').val());
    bindPlatformSelector();
    syncPlatformSelectionUI();

    // 定时刷新处理中的查询
    setInterval(refreshProcessingQueries, 5000);
});

function selectRegion(location) {
    const normalizedLocation = location || '';
    $('#locationSelect').val(normalizedLocation);
    $('#selectedLocationText').text(normalizedLocation || '全国');
    $('.region-option').removeClass('active');
    $(`.region-option[data-location="${normalizedLocation}"]`).addClass('active');
}

// 加载统计信息
function bindPlatformSelector() {
    $('.platform-label').attr({
        tabindex: '0',
        role: 'button'
    });

    $('.platform-label').on('click', function(e) {
        e.preventDefault();

        const targetId = $(this).attr('for');
        const $input = $(`#${targetId}`);
        if (!$input.length || $input.prop('disabled')) {
            return;
        }

        $input.prop('checked', !$input.prop('checked')).trigger('change');
    });

    $('.platform-label').on('keydown', function(e) {
        if (e.key !== 'Enter' && e.key !== ' ') {
            return;
        }

        e.preventDefault();
        $(this).trigger('click');
    });

    $('.platform-option input[type="checkbox"]').on('change', function() {
        syncPlatformSelectionUI();
    });
}

function syncPlatformSelectionUI() {
    $('.platform-option').each(function() {
        const $option = $(this);
        const $input = $option.find('input[type="checkbox"]');
        const isChecked = $input.prop('checked');

        $option.toggleClass('is-selected', isChecked);
        $option.find('.platform-label').attr('aria-pressed', isChecked ? 'true' : 'false');
    });
}

function getSelectedPlatforms() {
    const platforms = [];

    $('.platform-option input:checked').each(function() {
        platforms.push($(this).val());
    });

    return platforms;
}

function normalizeQueryInput(value) {
    return String(value || '').trim();
}

function clearIntentResult() {
    aiIntent = null;
    lastAnalyzedQuery = '';
    $('#intentResult').hide().empty();
}

function resetAnalyzeButton() {
    $('#analyzeIntentBtn')
        .prop('disabled', false)
        .html('<i class="fas fa-magic me-2"></i> AI 解析需求');
}

function syncIntentWithQueryInput() {
    const currentQuery = normalizeQueryInput($('#queryInput').val());

    if (!currentQuery) {
        clearIntentResult();
        if (activeAnalyzeRequestId) {
            activeAnalyzeRequestId = 0;
            resetAnalyzeButton();
        }
        return;
    }

    if (!lastAnalyzedQuery || currentQuery === lastAnalyzedQuery) {
        return;
    }

    clearIntentResult();
    if (activeAnalyzeRequestId) {
        activeAnalyzeRequestId = 0;
        resetAnalyzeButton();
    }
}

function loadStats() {
    $.ajax({
        url: '/api/stats',
        method: 'GET',
        success: function(data) {
            $('#totalQueries').text(data.total_queries);
            $('#completedQueries').text(data.completed_queries);
            $('#processingQueries').text(data.processing_queries);
            $('#failedQueries').text(data.failed_queries);
        },
        error: function() {
            console.error('加载统计信息失败');
        }
    });
}

// 加载最近查询
function loadRecentQueries() {
    $.ajax({
        url: '/api/history?per_page=5',
        method: 'GET',
        success: function(data) {
            renderQueries(data.items);
        },
        error: function() {
            $('#recentQueries').html(`
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    加载失败
                </div>
            `);
        }
    });
}

// 渲染查询列表
function renderQueries(queries) {
    if (queries.length === 0) {
        $('#recentQueries').html(`
            <div class="text-center py-5 text-muted">
                <i class="fas fa-inbox fa-3x mb-3"></i>
                <p>暂无查询记录</p>
            </div>
        `);
        return;
    }

    let html = '<div class="list-group">';
    queries.forEach(function(query) {
        const statusBadge = getStatusBadge(query.status);
        const platforms = query.platforms.map(p => getPlatformName(p)).join(', ');
        const time = formatTime(query.created_at);
        const queryText = escapeHtml(query.query);
        const platformText = escapeHtml(platforms);

        html += `
            <a href="/result/${query.id}" class="list-group-item list-group-item-action">
                <div class="d-flex w-100 justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1 fw-bold">
                            <i class="fas fa-search me-2"></i>${queryText}
                        </h6>
                        <p class="mb-1 text-muted small">
                            <i class="fas fa-store me-1"></i>${platformText}
                            ${query.products_count > 0 ? `<i class="fas fa-box ms-3 me-1"></i>${query.products_count} 个商品` : ''}
                        </p>
                    </div>
                    <div class="text-end">
                        ${statusBadge}
                        <p class="mb-0 text-muted small mt-2">${time}</p>
                    </div>
                </div>
            </a>
        `;
    });
    html += '</div>';

    $('#recentQueries').html(html);
}

// 提交查询
function submitQuery() {
    const query = normalizeQueryInput($('#queryInput').val());
    const location = $('#locationSelect').val() || '';
    const locationLabel = getLocationLabel(location);
    const sampleCount = Math.max(1, Math.min(parseInt($('#sampleCountInput').val(), 10) || 50, 500));
    const sortOrder = $('#sortOrderSelect').val() || 'none';
    const platforms = getSelectedPlatforms();

    if (!query) {
        showAlert('请描述你想买的商品', 'warning');
        return;
    }

    if (platforms.length === 0) {
        showAlert('请至少选择一个平台', 'warning');
        return;
    }

    // 携带 AI 解析结果
    const payload = {
        query: query,
        platforms: platforms,
        location: location,
        sample_count: sampleCount,
        sort_order: sortOrder
    };

    if (aiIntent && query === lastAnalyzedQuery) {
        payload.search_keywords = aiIntent.search_keywords || [];
        payload.category = aiIntent.category || '';
        payload.sub_category = aiIntent.sub_category || '';
        payload.budget_min = aiIntent.budget_min;
        payload.budget_max = aiIntent.budget_max;
    }

    // 显示进度模态框
    const progressModal = new bootstrap.Modal(document.getElementById('progressModal'));
    $('#progressStatus').text('正在抓取商品数据...');
    $('#progressDetail').text(`地区：${locationLabel}，目标随机抓取 ${sampleCount} 条`);
    if (aiIntent && aiIntent.category) {
        $('#progressDetail').text(`品类：${aiIntent.category} | 地区：${locationLabel}，目标随机抓取 ${sampleCount} 条`);
    }
    progressModal.show();

    // 提交查询
    $.ajax({
        url: '/api/query',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(payload),
        success: function(response) {
            if (response.success) {
                // 开始轮询查询状态
                pollQueryStatus(response.query_id, progressModal);
            }
        },
        error: function(xhr) {
            progressModal.hide();
            const error = xhr.responseJSON ? xhr.responseJSON.error : '提交失败';
            showAlert(error, 'danger');
        }
    });
}

// 轮询查询状态
function pollQueryStatus(queryId, modal) {
    const intervalId = setInterval(function() {
        $.ajax({
            url: `/api/query/${queryId}`,
            method: 'GET',
            success: function(data) {
                updateProgress(data.status);

                if (data.status === 'completed') {
                    clearInterval(intervalId);
                    modal.hide();
                    showAlert('分析完成！', 'success');
                    setTimeout(function() {
                        window.location.href = `/result/${queryId}`;
                    }, 1000);
                } else if (data.status === 'failed') {
                    clearInterval(intervalId);
                    modal.hide();
                    showAlert('分析失败，正在打开详情页…', 'danger');
                    setTimeout(function() {
                        window.location.href = `/result/${queryId}`;
                    }, 800);
                }
            },
            error: function() {
                clearInterval(intervalId);
                modal.hide();
                showAlert('查询状态获取失败', 'danger');
            }
        });
    }, 2000);
}

// 更新进度显示
function updateProgress(status) {
    const statusTexts = {
        'pending': '任务排队中...',
        'processing': '正在分析数据...',
        'completed': '分析完成！',
        'failed': '分析失败'
    };

    $('#progressStatus').text(statusTexts[status] || '处理中...');
}

// 刷新处理中的查询
function refreshProcessingQueries() {
    // 只有在仪表盘页面才刷新
    if ($('#recentQueries').length) {
        loadRecentQueries();
        loadStats();
    }
}

// 获取状态徽章
function getStatusBadge(status) {
    const badges = {
        'pending': '<span class="badge badge-pending">等待中</span>',
        'processing': '<span class="badge badge-processing pulse">处理中</span>',
        'completed': '<span class="badge badge-completed">已完成</span>',
        'failed': '<span class="badge badge-failed">失败</span>'
    };
    return badges[status] || '<span class="badge bg-secondary">未知</span>';
}

// 获取平台名称
function getPlatformName(platform) {
    const names = {
        'xianyu': '闲鱼',
        'taobao': '淘宝',
        'jd': '京东',
        'pdd': '拼多多'
    };
    return names[platform] || platform;
}

// 格式化时间
function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    const now = new Date();
    const diff = now - date;

    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes} 分钟前`;
    if (hours < 24) return `${hours} 小时前`;
    if (days < 7) return `${days} 天前`;

    return date.toLocaleDateString('zh-CN');
}

function getLocationLabel(location) {
    return location || '全国';
}

// AI 解析用户意图
function analyzeIntent() {
    const userInput = normalizeQueryInput($('#queryInput').val());

    if (!userInput || userInput.length < 2) {
        showAlert('请先输入你想买的商品描述', 'warning');
        return;
    }

    const requestId = ++analyzeRequestSeq;
    activeAnalyzeRequestId = requestId;
    const btn = $('#analyzeIntentBtn');
    btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin me-2"></i> AI 正在理解你的需求...');

    $.ajax({
        url: '/api/analyze-intent',
        method: 'POST',
        timeout: 45000,
        contentType: 'application/json',
        data: JSON.stringify({ query: userInput }),
        success: function(response) {
            if (requestId !== activeAnalyzeRequestId) {
                return;
            }

            if (normalizeQueryInput($('#queryInput').val()) !== userInput) {
                activeAnalyzeRequestId = 0;
                clearIntentResult();
                resetAnalyzeButton();
                return;
            }

            if (response.success) {
                aiIntent = response.intent;
                lastAnalyzedQuery = userInput;
                renderIntentResult(aiIntent);
            } else {
                showAlert(response.error || '解析失败', 'danger');
            }
        },
        error: function(xhr, textStatus) {
            if (requestId !== activeAnalyzeRequestId) {
                return;
            }

            const error = textStatus === 'timeout'
                ? 'AI 解析超时，请稍后重试'
                : (xhr.responseJSON ? xhr.responseJSON.error : 'AI 解析失败，请重试');
            showAlert(error, 'danger');
        },
        complete: function() {
            if (requestId === activeAnalyzeRequestId) {
                activeAnalyzeRequestId = 0;
                resetAnalyzeButton();
            }
        }
    });
}

// 渲染 AI 解析结果
function renderIntentResult(intent) {
    var tagsHtml = '';

    if (intent.category) {
        tagsHtml += `<span class="intent-tag category"><span class="tag-icon">📂</span> ${escapeHtml(intent.category)}</span>`;
    }
    if (intent.brand) {
        tagsHtml += `<span class="intent-tag brand"><span class="tag-icon">🏷</span> ${escapeHtml(intent.brand)}</span>`;
    }
    if (intent.product_line) {
        tagsHtml += `<span class="intent-tag brand"><span class="tag-icon">📱</span> ${escapeHtml(intent.product_line)}</span>`;
    }
    if (intent.sub_category && intent.sub_category !== intent.category) {
        tagsHtml += `<span class="intent-tag category"><span class="tag-icon">📂</span> ${escapeHtml(intent.sub_category)}</span>`;
    }
    if (intent.budget_min || intent.budget_max) {
        var budgetText = '¥';
        if (intent.budget_min) budgetText += intent.budget_min;
        budgetText += ' ~ ';
        if (intent.budget_max) budgetText += '¥' + intent.budget_max;
        if (!intent.budget_min) budgetText = '≤ ¥' + intent.budget_max;
        if (!intent.budget_max) budgetText = '≥ ¥' + intent.budget_min;
        tagsHtml += `<span class="intent-tag budget"><span class="tag-icon">💰</span> ${budgetText}</span>`;
    }
    if (intent.use_case) {
        tagsHtml += `<span class="intent-tag pref"><span class="tag-icon">🎯</span> ${escapeHtml(intent.use_case)}</span>`;
    }
    if (intent.condition && intent.condition !== '不限') {
        tagsHtml += `<span class="intent-tag condition"><span class="tag-icon">📦</span> ${escapeHtml(intent.condition)}</span>`;
    }
    if (intent.key_specs) {
        Object.keys(intent.key_specs).forEach(function(key) {
            tagsHtml += `<span class="intent-tag spec"><span class="tag-icon">⚙</span> ${escapeHtml(key)}: ${escapeHtml(intent.key_specs[key])}</span>`;
        });
    }
    if (intent.preferences && intent.preferences.length) {
        intent.preferences.forEach(function(p) {
            tagsHtml += `<span class="intent-tag pref"><span class="tag-icon">✅</span> ${escapeHtml(p)}</span>`;
        });
    }
    if (intent.exclude && intent.exclude.length) {
        intent.exclude.forEach(function(e) {
            tagsHtml += `<span class="intent-tag exclude"><span class="tag-icon">🚫</span> ${escapeHtml(e)}</span>`;
        });
    }

    var keywordsHtml = '';
    if (intent.search_keywords && intent.search_keywords.length) {
        keywordsHtml = '<div class="intent-keywords-row"><small class="text-muted fw-bold">🔑 AI 搜索关键词：</small><div class="intent-tags" style="margin-top: 0.4rem;">';
        intent.search_keywords.forEach(function(kw) {
            keywordsHtml += `<span class="intent-tag keyword">${escapeHtml(kw)}</span>`;
        });
        keywordsHtml += '</div></div>';
    }

    var confidenceClass = (intent.confidence || 0) >= 0.8 ? 'high' : 'medium';
    var confidenceText = (intent.confidence || 0) >= 0.8 ? '高置信度' : '中等置信度';

    var ambiguityHtml = '';
    if (intent.ambiguity_note) {
        ambiguityHtml = `<div class="intent-ambiguity"><i class="fas fa-info-circle me-1"></i> ${escapeHtml(intent.ambiguity_note)}</div>`;
    }

    var profileHtml = '';
    if (intent.user_profile_hint) {
        profileHtml = `<div class="intent-profile"><i class="fas fa-user-tag me-1"></i> ${escapeHtml(intent.user_profile_hint)}</div>`;
    }

    $('#intentResult').html(`
        <div class="intent-header">
            <span class="intent-header-title"><i class="fas fa-robot me-1"></i> AI 解析结果</span>
            <span class="intent-confidence ${confidenceClass}">${confidenceText} ${Math.round((intent.confidence || 0) * 100)}%</span>
        </div>
        <div class="intent-tags">${tagsHtml}</div>
        ${keywordsHtml}
        ${ambiguityHtml}
        ${profileHtml}
    `).slideDown(300);
}
function showAlert(message, type) {
    const safeMessage = escapeHtml(message);
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>
            ${safeMessage}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    $('.container').first().prepend(alertHtml);

    // 3秒后自动关闭
    setTimeout(function() {
        $('.alert').alert('close');
    }, 3000);
}

function escapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
