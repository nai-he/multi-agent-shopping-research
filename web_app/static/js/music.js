/* 音乐搜索 JavaScript */

$(document).ready(function() {
    // 表单提交
    $('#musicSearchForm').on('submit', function(e) {
        e.preventDefault();
        searchMusic();
    });

    // 平台选择器
    bindPlatformSelector();
    syncPlatformSelectionUI();
});

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

function searchMusic() {
    const query = $('#musicQuery').val().trim();
    const searchType = $('#searchType').val();
    const limit = parseInt($('#resultLimit').val(), 10) || 20;
    const platforms = getSelectedPlatforms();

    if (!query) {
        showAlert('请输入搜索关键词', 'warning');
        return;
    }

    if (platforms.length === 0) {
        showAlert('请至少选择一个平台', 'warning');
        return;
    }

    // 显示进度模态框
    $('#searchStatus').text('正在搜索音乐...');
    $('#searchDetail').text(`搜索类型：${getSearchTypeLabel(searchType)}`);
    $('#searchProgressModal').modal('show');

    // 提交搜索
    $.ajax({
        url: '/api/music/search',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            query: query,
            type: searchType,
            limit: limit,
            platforms: platforms
        }),
        success: function(response) {
            // 强制关闭模态框
            try {
                $('#searchProgressModal').modal('hide');
                $('.modal-backdrop').remove();
                $('body').removeClass('modal-open').css('padding-right', '');
                $('#searchProgressModal').hide();
            } catch(e) {
                console.error('Error closing modal:', e);
            }

            if (response.success) {
                displayResults(response.results, platforms);
                showAlert('搜索完成！', 'success');
            } else {
                showAlert(response.error || '搜索失败', 'danger');
            }
        },
        error: function(xhr) {
            // 强制关闭模态框
            try {
                $('#searchProgressModal').modal('hide');
                $('.modal-backdrop').remove();
                $('body').removeClass('modal-open').css('padding-right', '');
                $('#searchProgressModal').hide();
            } catch(e) {
                console.error('Error closing modal:', e);
            }

            const error = xhr.responseJSON ? xhr.responseJSON.error : '搜索失败';
            showAlert(error, 'danger');
        },
        complete: function() {
            // 确保最终清理
            setTimeout(function() {
                $('#searchProgressModal').modal('hide');
                $('.modal-backdrop').remove();
                $('body').removeClass('modal-open').css('padding-right', '');
            }, 100);
        }
    });
}

function displayResults(results, platforms) {
    const $resultsSection = $('#resultsSection');
    const $musicResults = $('#musicResults');

    let totalCount = 0;
    let html = '';

    platforms.forEach(function(platform) {
        const platformData = results[platform];
        if (!platformData || !platformData.items || platformData.items.length === 0) {
            return;
        }

        totalCount += platformData.items.length;
        const platformName = getPlatformName(platform);

        html += `
            <div class="platform-results mb-4">
                <h6 class="mb-3">
                    <i class="fas fa-music me-2"></i>
                    ${escapeHtml(platformName)} (${platformData.items.length} 条结果)
                </h6>
                <div class="list-group">
        `;

        platformData.items.forEach(function(item) {
            html += renderMusicItem(item, platform);
        });

        html += `
                </div>
            </div>
        `;
    });

    if (totalCount === 0) {
        html = `
            <div class="text-center py-5 text-muted">
                <i class="fas fa-inbox fa-3x mb-3"></i>
                <p>未找到相关结果</p>
            </div>
        `;
    }

    $('#resultCount').text(`${totalCount} 条结果`);
    $musicResults.html(html);
    $resultsSection.show();

    // 滚动到结果区域
    $('html, body').animate({
        scrollTop: $resultsSection.offset().top - 20
    }, 500);
}

function renderMusicItem(item, platform) {
    const title = escapeHtml(item.name || item.title || '未知');
    const artist = escapeHtml(item.artist || item.singer || '未知歌手');
    const album = escapeHtml(item.album || '');
    const duration = formatDuration(item.duration || 0);
    const cover = item.cover || item.pic || '';
    const url = escapeHtml(item.url || '#');
    const songId = item.id || '';

    // 根据平台确定 provider 名称
    const providerMap = {
        'qq': 'netease',       // QQ 音乐也使用网易云 API 数据
        'netease': 'netease'
    };
    const provider = providerMap[platform] || 'netease';

    return `
        <div class="list-group-item music-item">
            <div class="d-flex align-items-center">
                ${cover ? `<img src="${escapeHtml(cover)}" alt="封面" class="music-cover me-3">` : '<div class="music-cover-placeholder me-3"><i class="fas fa-music"></i></div>'}
                <div class="flex-grow-1">
                    <h6 class="mb-1 music-title">${title}</h6>
                    <p class="mb-1 text-muted small">
                        <i class="fas fa-user me-1"></i>${artist}
                        ${album ? `<span class="ms-3"><i class="fas fa-compact-disc me-1"></i>${album}</span>` : ''}
                        ${duration ? `<span class="ms-3"><i class="fas fa-clock me-1"></i>${duration}</span>` : ''}
                    </p>
                </div>
                <div class="btn-group ms-3" role="group">
                    ${url && url !== '#' ? `
                    <a href="${url}" target="_blank" class="btn btn-sm btn-outline-primary">
                        <i class="fas fa-external-link-alt me-1"></i>打开
                    </a>
                    ` : ''}
                    ${songId ? `
                    <button class="btn btn-sm btn-outline-success" onclick="downloadMusic('${provider}', '${escapeHtml(songId)}', '${escapeHtml(title)}')">
                        <i class="fas fa-download me-1"></i>下载
                    </button>
                    <button class="btn btn-sm btn-outline-info" onclick="downloadLyrics('${escapeHtml(songId)}', '${escapeHtml(title)}', '${escapeHtml(artist)}')">
                        <i class="fas fa-file-alt me-1"></i>歌词
                    </button>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function formatDuration(seconds) {
    if (!seconds || seconds <= 0) return '';
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function getPlatformName(platform) {
    const names = {
        'qq': 'QQ 音乐',
        'netease': '网易云音乐'
    };
    return names[platform] || platform;
}

function getSearchTypeLabel(type) {
    const labels = {
        'song': '歌曲',
        'artist': '歌手',
        'album': '专辑',
        'playlist': '歌单'
    };
    return labels[type] || type;
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

function downloadMusic(provider, songId, songName) {
    // 显示下载提示
    showAlert('正在准备下载，请稍候...', 'info');

    $.ajax({
        url: '/api/music/download',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            provider: provider,
            songId: songId,
            query: songName
        }),
        success: function(response) {
            if (response.success && response.download_url) {
                // 直接下载文件
                window.location.href = response.download_url;
                showAlert('下载成功！文件已保存到浏览器下载目录', 'success');
            } else {
                showAlert(response.error || '下载失败', 'danger');
            }
        },
        error: function(xhr) {
            const error = xhr.responseJSON ? xhr.responseJSON.error : '下载失败';
            showAlert(error, 'danger');
        }
    });
}

function downloadLyrics(songId, title, artist) {
    showAlert('正在获取歌词...', 'info');

    $.ajax({
        url: `/api/music/lyrics/${songId}`,
        method: 'GET',
        success: function(response) {
            if (response.success) {
                // 组装 LRC 歌词文件内容
                let lrcContent = `[ti:${title}]\n[ar:${artist}]\n\n`;
                lrcContent += response.lyric;
                if (response.tlyric) {
                    lrcContent += '\n\n' + response.tlyric;
                }

                const blob = new Blob([lrcContent], { type: 'text/plain;charset=utf-8' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = `${title} - ${artist}.txt`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(link.href);

                showAlert('歌词下载成功！', 'success');
            } else {
                showAlert(response.error || '暂无歌词', 'warning');
            }
        },
        error: function(xhr) {
            const error = xhr.responseJSON ? xhr.responseJSON.error : '歌词获取失败';
            showAlert(error, 'danger');
        }
    });
}
