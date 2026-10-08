let scanItems = [];

// ============================================
// 综合分析
// ============================================
async function analyze() {
    const box = document.getElementById('analyze-result');
    box.innerHTML = '<div class="analyze-empty">分析中，请稍候...</div>';
    try {
        const res = await fetch('/api/analyze');
        const data = await res.json();
        renderAnalyze(data);
    } catch (e) {
        box.innerHTML = `<div class="analyze-empty">分析失败: ${escapeHtml(e.message)}</div>`;
    }
}

function renderAnalyze(data) {
    // 更新顶部统计
    document.getElementById('stat-estimate').textContent = data.estimate.total_estimate_human;
    const ds = data.docker;
    if (ds && !ds.error) {
        document.getElementById('stat-containers').textContent =
            `${ds.summary.running} / ${ds.summary.running + ds.summary.stopped}`;
    }
    document.getElementById('stat-orphans').textContent = data.orphan_dirs.length;

    // 渲染分析结果
    let html = '';

    // 磁盘占用概览
    html += '<h3 class="sub-title">磁盘占用概览</h3>';
    html += '<table class="mini-table"><tr><th>路径</th><th>分类</th><th>大小</th><th>说明</th></tr>';
    data.disk_overview.forEach(d => {
        const catLabel = {
            protected: '🔒 系统保护',
            system_app: '📦 系统应用',
            app_runtime: '⚙️ 应用运行时',
            user_data: '📁 用户数据',
            docker_root: '🐳 Docker',
            cleanable: '🧹 可清理',
            unknown: '❓ 未知',
        }[d.category] || d.category;
        const rowClass = d.cleanable ? 'row-cleanable' : '';
        html += `<tr class="${rowClass}"><td class="path-cell">${escapeHtml(d.path)}</td><td>${catLabel}</td><td class="size-cell">${d.size_human}</td><td>${escapeHtml(d.description)}</td></tr>`;
    });
    html += '</table>';

    // Docker 概要
    if (ds && !ds.error) {
        html += '<h3 class="sub-title">Docker 状态</h3>';
        html += `<div class="chips">`;
        html += `<span class="chip chip-green">运行中: ${ds.summary.running}</span>`;
        html += `<span class="chip chip-orange">已停止: ${ds.summary.stopped}</span>`;
        html += `<span class="chip chip-red">未使用镜像: ${ds.summary.unused_images}</span>`;
        html += `<span class="chip chip-red">悬空卷: ${ds.summary.unused_volumes}</span>`;
        html += `</div>`;
    }

    // 孤儿目录
    if (data.orphan_dirs.length) {
        html += '<h3 class="sub-title">⚠️ 孤儿目录（无对应容器）</h3>';
        html += '<table class="mini-table"><tr><th>目录</th><th>大小</th><th>原因</th></tr>';
        data.orphan_dirs.forEach(o => {
            html += `<tr class="row-warn"><td class="path-cell">${escapeHtml(o.path)}</td><td class="size-cell">${o.size_human}</td><td>${escapeHtml(o.reason)}</td></tr>`;
        });
        html += '</table>';
    }

    // 汇总
    html += `<div class="estimate-box">`;
    html += `综合估算可释放：<strong>${data.estimate.total_estimate_human}</strong>`;
    html += `<span class="hint-text">（缓存 ${data.estimate.cleanable_cache_human} + 未使用镜像 ${data.estimate.unused_images_human} + 孤儿目录 ${data.estimate.orphan_dirs_human}）</span>`;
    html += `</div>`;

    document.getElementById('analyze-result').innerHTML = html;
}

// 选择的模块
function getSelectedModules() {
    return Array.from(document.querySelectorAll('.module-checkbox input:checked'))
        .map(cb => cb.value);
}

// 扫描
async function scan() {
    const hint = document.getElementById('scan-hint');
    hint.textContent = '扫描中...';
    try {
        const res = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ modules: getSelectedModules() })
        });
        const data = await res.json();
        scanItems = data.items;
        renderResults(data.items);
        document.getElementById('stat-count').textContent = data.count;
        document.getElementById('stat-size').textContent = data.total_size_human;
        document.getElementById('btn-preview').disabled = data.count === 0;
        document.getElementById('btn-apply').disabled = data.count === 0;
        hint.textContent = `扫描完成，发现 ${data.count} 项`;
    } catch (e) {
        hint.textContent = '扫描失败';
        showToast('扫描出错: ' + e.message, 'error');
    }
}

// 渲染结果表格
function renderResults(items) {
    const tbody = document.getElementById('result-body');
    if (!items.length) {
        tbody.innerHTML = '<tr class="empty-row"><td colspan="5">没有发现可清理项</td></tr>';
        return;
    }
    tbody.innerHTML = items.map((it, i) => `
        <tr>
            <td><input type="checkbox" class="row-check" data-idx="${i}" checked></td>
            <td>${it.item_type}</td>
            <td>${escapeHtml(it.item_name)}</td>
            <td class="size-cell">${humanSize(it.size_bytes)}</td>
            <td class="path-cell" title="${escapeHtml(it.path || '')}">${escapeHtml(it.description || it.path || '')}</td>
        </tr>
    `).join('');
}

// 清理（dry_run=true 为预览）
async function cleanup(dryRun) {
    const selected = scanItems.filter((_, i) => {
        const cb = document.querySelector(`.row-check[data-idx="${i}"]`);
        return cb && cb.checked;
    });
    if (!selected.length) {
        showToast('请先勾选要清理的项目', 'error');
        return;
    }
    if (!dryRun && !confirm(`确认删除 ${selected.length} 项？此操作不可恢复！`)) {
        return;
    }
    try {
        const res = await fetch('/api/cleanup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: selected, dry_run: dryRun })
        });
        const result = await res.json();
        const msg = dryRun
            ? `预览：将删除 ${result.deleted} 项，释放 ${result.freed_human}`
            : `已删除 ${result.deleted} 项，释放 ${result.freed_human}`;
        showToast(msg, dryRun ? 'success' : 'success');
        if (!dryRun) scan();
    } catch (e) {
        showToast('清理失败: ' + e.message, 'error');
    }
}

// 全选
document.addEventListener('change', (e) => {
    if (e.target.id === 'check-all') {
        document.querySelectorAll('.row-check').forEach(cb => cb.checked = e.target.checked);
    }
});

// 工具函数
function humanSize(bytes) {
    for (const u of ['B', 'KB', 'MB', 'GB', 'TB']) {
        if (bytes < 1024) return bytes.toFixed(1) + ' ' + u;
        bytes /= 1024;
    }
    return bytes.toFixed(1) + ' PB';
}
function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
}
function showToast(msg, type) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show ' + (type || '');
    setTimeout(() => t.classList.remove('show'), 3000);
}
