/* 主 JavaScript 文件 */

// 平滑滚动
$(document).ready(function() {
    // 平滑滚动到锚点
    $('a[href^="#"]').on('click', function(e) {
        e.preventDefault();
        const target = $(this.getAttribute('href'));
        if (target.length) {
            $('html, body').stop().animate({
                scrollTop: target.offset().top - 80
            }, 800);
        }
    });

    // 导航栏透明效果
    $(window).scroll(function() {
        if ($(this).scrollTop() > 50) {
            $('.navbar').addClass('scrolled');
        } else {
            $('.navbar').removeClass('scrolled');
        }
    });

    // 表单验证
    $('form').on('submit', function(e) {
        const form = $(this)[0];
        if (!form.checkValidity()) {
            e.preventDefault();
            e.stopPropagation();
        }
        $(this).addClass('was-validated');
    });

    // 工具提示
    $('[data-bs-toggle="tooltip"]').tooltip();

    // 确认密码验证
    $('#confirm_password').on('input', function() {
        const password = $('#password').val();
        const confirmPassword = $(this).val();

        if (confirmPassword && password !== confirmPassword) {
            this.setCustomValidity('两次密码不一致');
        } else {
            this.setCustomValidity('');
        }
    });
});

// 复制到剪贴板
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('已复制到剪贴板', 'success');
    }, function() {
        showToast('复制失败', 'danger');
    });
}

// Toast 提示
function showToast(message, type = 'info') {
    const safeMessage = appEscapeHtml(message);
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${type === 'success' ? 'check' : 'info'}-circle me-2"></i>
                    ${safeMessage}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    // 创建 toast 容器（如果不存在）
    if (!$('#toastContainer').length) {
        $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3"></div>');
    }

    const $toast = $(toastHtml);
    $('#toastContainer').append($toast);

    const toast = new bootstrap.Toast($toast[0]);
    toast.show();

    // 自动移除
    $toast.on('hidden.bs.toast', function() {
        $(this).remove();
    });
}

// 格式化文件大小
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

// 格式化数字
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// 加载动画
function showLoading(element) {
    $(element).html(`
        <div class="text-center py-5">
            <div class="loading-spinner mx-auto"></div>
            <p class="text-muted mt-3">加载中...</p>
        </div>
    `);
}

// 空状态
function showEmpty(element, message = '暂无数据') {
    const safeMessage = appEscapeHtml(message);
    $(element).html(`
        <div class="text-center py-5 text-muted">
            <i class="fas fa-inbox fa-3x mb-3"></i>
            <p>${safeMessage}</p>
        </div>
    `);
}

// 错误状态
function showError(element, message = '加载失败') {
    const safeMessage = appEscapeHtml(message);
    $(element).html(`
        <div class="alert alert-danger">
            <i class="fas fa-exclamation-circle me-2"></i>
            ${safeMessage}
        </div>
    `);
}

function appEscapeHtml(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
