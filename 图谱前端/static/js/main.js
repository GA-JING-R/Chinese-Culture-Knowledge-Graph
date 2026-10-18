/* ==========================================================================
   汉文化知识图谱 · 前端交互脚本
   依赖：ECharts 5（本地 static/vendor/echarts.min.js）
   说明：所有节点与关系均来自后端接口，页面内不硬编码任何数据。
   ========================================================================== */
(function () {
    'use strict';

    /* ----------------------------- 常量 ----------------------------- */

    // 节点分类（与后端 labels(n) 一一对应）
    const CATEGORY = {
        Person:   { label: '人物', color: '#b0392e' },
        Dynasty:  { label: '朝代', color: '#2e5c6e' },
        Work:     { label: '著作', color: '#a8761f' },
        Location: { label: '地点', color: '#4a7c59' }
    };
    const FALLBACK_CAT = { label: '其他', color: '#8d8375' };

    // 关系类型的中文显示名
    const REL_TEXT = {
        LIVED_IN:   '生活于',
        BORN_IN:    '出生于',
        CREATED:    '创作',
        FRIEND_OF:  '友人',
        TEACHER_OF: '师从',
        FATHER_OF:  '父子'
    };

    const COLOR = {
        paper:    '#f7f2e8',
        ink:      '#2b261f',
        ink3:     '#8d8375',
        cinnabar: '#b0392e',
        edge:     '#c3b49a',
        edgeHot:  '#b0392e'
    };

    /* ----------------------------- 状态 ----------------------------- */

    const state = {
        chart: null,
        nodes: [],
        links: [],
        hidden: new Set(),      // 被隐藏的分类
        selected: null,         // 当前选中的节点名
        pathNodes: new Set(),   // 路径查询命中的节点
        pathEdges: new Set(),   // 路径查询命中的关系（source→target）
        showEdgeLabel: true,
        zoom: 1
    };

    /* ----------------------------- 工具 ----------------------------- */

    const $ = (sel, root) => (root || document).querySelector(sel);
    const $$ = (sel, root) => Array.prototype.slice.call((root || document).querySelectorAll(sel));

    function escapeHtml(value) {
        return String(value === null || value === undefined ? '' : value)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    const categoryOf = label => CATEGORY[label] || FALLBACK_CAT;
    const relText = type => REL_TEXT[type] || type;

    /* 把数据库的原始报错翻译成看得懂的话 */
    function friendlyDbError(message) {
        const text = String(message || '');
        if (/Cannot open connection|ConnectionUnavailable|Connection refused|fail to connect/i.test(text)) {
            return '无法连接到 Neo4j 数据库（bolt://localhost:7687），请确认数据库已经启动。';
        }
        if (/authentication|Unauthorized|credential/i.test(text)) {
            return '数据库账号或密码不正确，请检查 neo4j_db.py 中的连接配置。';
        }
        return text || '未知错误';
    }

    let toastTimer = null;
    function toast(message) {
        const el = $('#toast');
        if (!el) return;
        el.textContent = message;
        el.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => el.classList.remove('show'), 2200);
    }

    function setLoading(on, text) {
        const box = $('#loading');
        if (!box) return;
        if (text) $('#loadingText').textContent = text;
        box.classList.toggle('hide', !on);
    }

    function showBanner(message) {
        const bar = $('#banner');
        if (!bar) return;
        if (message) {
            $('#bannerText').innerHTML = message;
            bar.classList.add('show');
        } else {
            bar.classList.remove('show');
        }
    }

    async function fetchJSON(url, options) {
        const resp = await fetch(url, options);
        if (!resp.ok) {
            // 后端返回的 503 / 500 里通常带有可读的说明，优先展示它
            let detail = '';
            try {
                const body = await resp.json();
                detail = (body && (body.error || body.message)) || '';
            } catch (e) { /* 响应体不是 JSON，忽略 */ }
            throw new Error(detail || ('HTTP ' + resp.status));
        }
        return resp.json();
    }

    /* ----------------------------- 顶栏统计 ----------------------------- */

    function renderStats(stats) {
        const map = {
            statNodes: stats.total_nodes,
            statRels: stats.total_relations,
            statPersons: stats.persons,
            statDynasties: stats.dynasties,
            statWorks: stats.works,
            statLocations: stats.locations
        };
        Object.keys(map).forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = (map[id] === undefined ? '—' : map[id]);
        });
    }

    /* ----------------------------- 分类过滤 ----------------------------- */

    function renderLegend() {
        const box = $('#legendList');
        if (!box) return;

        const counts = {};
        state.nodes.forEach(n => { counts[n.label] = (counts[n.label] || 0) + 1; });

        const order = Object.keys(CATEGORY).filter(k => counts[k]);
        Object.keys(counts).forEach(k => { if (order.indexOf(k) < 0) order.push(k); });

        box.innerHTML = order.map(key => {
            const cat = categoryOf(key);
            const off = state.hidden.has(key) ? ' off' : '';
            return '<button class="legend-item' + off + '" type="button" data-cat="' + escapeHtml(key) + '">' +
                   '<i class="legend-dot" style="background:' + cat.color + '"></i>' +
                   '<span class="legend-label">' + escapeHtml(cat.label) + '</span>' +
                   '<span class="legend-count">' + counts[key] + '</span>' +
                   '</button>';
        }).join('');
    }

    function toggleCategory(key) {
        if (state.hidden.has(key)) state.hidden.delete(key);
        else state.hidden.add(key);
        renderLegend();
        renderGraph();
    }

    /* ----------------------------- 图谱渲染 ----------------------------- */

    function buildOption() {
        const visible = state.nodes.filter(n => !state.hidden.has(n.label));
        const visibleNames = new Set(visible.map(n => n.name));

        const nodes = visible.map(n => {
            const cat = categoryOf(n.label);
            const degree = n.degree || 0;
            const onPath = state.pathNodes.has(n.name);
            const isSelected = state.selected === n.name;

            return {
                name: n.name,
                category: n.label,
                degree: degree,
                symbolSize: 16 + Math.min(degree, 6) * 5,
                itemStyle: {
                    color: cat.color,
                    borderColor: (onPath || isSelected) ? COLOR.cinnabar : '#fdfaf4',
                    borderWidth: (onPath || isSelected) ? 3 : 1.5,
                    shadowBlur: 8,
                    shadowColor: 'rgba(70,55,35,.2)'
                },
                label: {
                    show: true,
                    position: 'bottom',
                    distance: 5,
                    fontSize: 12,
                    fontWeight: isSelected ? 700 : 600,
                    color: isSelected ? COLOR.cinnabar : COLOR.ink,
                    textBorderColor: COLOR.paper,
                    textBorderWidth: 3
                }
            };
        });

        const links = state.links
            .filter(l => visibleNames.has(l.source) && visibleNames.has(l.target))
            .map(l => {
                const onPath = state.pathEdges.has(l.source + '→' + l.target);
                return {
                    source: l.source,
                    target: l.target,
                    relation: l.relation,
                    sourceType: l.source_type,
                    targetType: l.target_type,
                    lineStyle: {
                        color: onPath ? COLOR.edgeHot : COLOR.edge,
                        width: onPath ? 2.8 : 1.3,
                        curveness: 0.12,
                        opacity: onPath ? 0.95 : 0.85
                    }
                };
            });

        return {
            backgroundColor: 'transparent',
            textStyle: { fontFamily: '"Microsoft YaHei", "PingFang SC", sans-serif' },
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(43,38,31,.93)',
                borderColor: '#b0392e',
                borderWidth: 1,
                padding: [8, 12],
                textStyle: { color: '#f4ecdd', fontSize: 12 },
                extraCssText: 'border-radius:5px;box-shadow:0 6px 20px rgba(0,0,0,.25);',
                formatter: params => {
                    if (params.dataType === 'edge') {
                        const d = params.data;
                        return '<b>' + escapeHtml(d.source) + '</b> —' +
                               escapeHtml(relText(d.relation)) + '→ <b>' + escapeHtml(d.target) + '</b>';
                    }
                    const d = params.data;
                    const cat = categoryOf(d.category);
                    return '<b style="color:#f0d9a8">' + escapeHtml(d.name) + '</b>' +
                           '<br>类型：' + escapeHtml(cat.label) +
                           '<br>关联：' + d.degree + ' 条';
                }
            },
            series: [{
                type: 'graph',
                layout: 'force',
                force: {
                    repulsion: 340,
                    edgeLength: [95, 175],
                    gravity: 0.09,
                    friction: 0.12,
                    layoutAnimation: true
                },
                roam: true,
                draggable: true,
                zoom: state.zoom,
                data: nodes,
                links: links,
                edgeSymbol: ['none', 'arrow'],
                edgeSymbolSize: [0, 7],
                edgeLabel: {
                    show: state.showEdgeLabel,
                    formatter: p => relText(p.data.relation),
                    fontSize: 10,
                    color: '#7d7263',
                    backgroundColor: 'rgba(253,250,244,.9)',
                    padding: [2, 5],
                    borderRadius: 3
                },
                labelLayout: { hideOverlap: true },
                emphasis: {
                    focus: 'adjacency',
                    scale: 1.15,
                    label: { fontSize: 13, fontWeight: 700, color: COLOR.cinnabar },
                    lineStyle: { width: 2.6, color: COLOR.edgeHot, opacity: 0.95 }
                },
                blur: {
                    itemStyle: { opacity: 0.22 },
                    label: { opacity: 0.25 },
                    lineStyle: { opacity: 0.08 },
                    edgeLabel: { opacity: 0 }
                },
                animation: true,
                animationDuration: 700,
                animationEasingUpdate: 'cubicOut'
            }]
        };
    }

    function renderGraph() {
        if (!state.chart) return;
        state.chart.setOption(buildOption(), { notMerge: true });
    }

    /* ----------------------------- 数据加载 ----------------------------- */

    async function loadGraph() {
        setLoading(true, '正在读取图谱…');
        try {
            const data = await fetchJSON('/api/graph');
            state.nodes = data.nodes || [];
            state.links = data.links || [];

            if (!state.nodes.length) {
                showBanner('<strong>知识图谱为空</strong>：数据库中没有节点数据。');
                setLoading(false);
                return;
            }

            renderLegend();
            renderGraph();
            fillNodeOptions();

            try {
                renderStats(await fetchJSON('/api/statistics'));
            } catch (err) { /* 统计失败不影响图谱 */ }

            setLoading(false);
        } catch (err) {
            setLoading(false);
            showBanner('<strong>无法读取图谱数据</strong>：' +
                       escapeHtml(friendlyDbError(err.message)));
        }
    }

    function fillNodeOptions() {
        const list = $('#nodeOptions');
        if (!list) return;
        list.innerHTML = state.nodes
            .map(n => '<option value="' + escapeHtml(n.name) + '"></option>')
            .join('');
    }

    async function checkStatus() {
        try {
            const s = await fetchJSON('/api/status');
            if (!s || s.status !== 'success') {
                showBanner('<strong>数据库连接异常</strong>：' +
                           escapeHtml(friendlyDbError(s && s.message)) +
                           ' 图谱相关功能暂时不可用。');
            }
        } catch (err) {
            showBanner('<strong>后端服务未响应</strong>：请确认 Flask 应用正在运行。');
        }
    }

    /* ----------------------------- 搜索 ----------------------------- */

    let searchTimer = null;
    function onSearchInput() {
        const keyword = $('#searchInput').value.trim();
        const box = $('#searchResults');
        clearTimeout(searchTimer);

        if (!keyword) { box.innerHTML = ''; return; }

        searchTimer = setTimeout(async () => {
            try {
                const list = await fetchJSON('/api/search?q=' + encodeURIComponent(keyword));
                if (!list.length) {
                    box.innerHTML = '<p class="empty-tip">未找到匹配的节点</p>';
                    return;
                }
                box.innerHTML = list.map(n =>
                    '<div class="result-item" data-node="' + escapeHtml(n.name) + '">' +
                    '<span class="name">' + escapeHtml(n.name) + '</span>' +
                    '<span class="tag">' + escapeHtml(categoryOf(n.label).label) + '</span>' +
                    '</div>'
                ).join('');
            } catch (err) {
                box.innerHTML = '<p class="empty-tip">搜索失败，请稍后再试</p>';
            }
        }, 220);
    }

    /* ----------------------------- 节点详情 ----------------------------- */

    async function loadNodeDetail(name) {
        state.selected = name;
        renderGraph();

        const box = $('#nodeDetail');
        box.innerHTML = '<p class="empty-tip">正在读取「' + escapeHtml(name) + '」…</p>';

        try {
            const data = await fetchJSON('/api/node/' + encodeURIComponent(name));
            if (!data || !data.name) {
                box.innerHTML = '<p class="empty-tip">未找到该节点</p>';
                return;
            }

            const cat = categoryOf(data.label);
            const relations = (data.relations || []).filter(r => r && r.neighbor);

            let html = '<div class="detail-head">' +
                       '<span class="detail-name">' + escapeHtml(data.name) + '</span>' +
                       '<span class="detail-badge" style="background:' + cat.color + '">' +
                       escapeHtml(cat.label) + '</span></div>' +
                       '<div class="detail-meta">关联关系 ' + relations.length + ' 条</div>';

            if (relations.length) {
                html += relations.map(r =>
                    '<div class="rel-row" data-node="' + escapeHtml(r.neighbor) + '">' +
                    '<span class="rel-type">' + escapeHtml(relText(r.relation)) + '</span>' +
                    '<span class="rel-arrow">→</span>' +
                    '<span class="rel-target">' + escapeHtml(r.neighbor) + '</span>' +
                    '</div>'
                ).join('');
            } else {
                html += '<p class="empty-tip">暂无可跳转的关联节点</p>';
            }

            box.innerHTML = html;

            if (data.label === 'Person') loadRecommendations(name);
            else $('#recommendList').innerHTML =
                '<p class="empty-tip">仅人物节点提供相似推荐</p>';
        } catch (err) {
            box.innerHTML = '<p class="empty-tip">读取失败，请检查后端服务</p>';
        }
    }

    async function loadRecommendations(personName) {
        const box = $('#recommendList');
        box.innerHTML = '<p class="empty-tip">正在计算相似人物…</p>';
        try {
            const list = await fetchJSON('/api/recommend/' + encodeURIComponent(personName));
            if (!list.length) {
                box.innerHTML = '<p class="empty-tip">暂无相似人物推荐</p>';
                return;
            }
            box.innerHTML = list.map(rec =>
                '<div class="rec-card" data-node="' + escapeHtml(rec.name) + '">' +
                '<div class="rec-name">' + escapeHtml(rec.name) + '</div>' +
                '<div class="rec-reason">' + escapeHtml(rec.reason) + '</div>' +
                '</div>'
            ).join('');
        } catch (err) {
            box.innerHTML = '<p class="empty-tip">推荐服务不可用</p>';
        }
    }

    /* ----------------------------- 路径查询 ----------------------------- */

    async function doPathQuery() {
        const source = $('#pathSource').value.trim();
        const target = $('#pathTarget').value.trim();
        const box = $('#pathResult');

        if (!source || !target) {
            box.innerHTML = '<p class="empty-tip">请填写起点与终点</p>';
            return;
        }

        box.innerHTML = '<p class="empty-tip">正在查找…</p>';
        try {
            const data = await fetchJSON('/api/path?source=' + encodeURIComponent(source) +
                                         '&target=' + encodeURIComponent(target));

            if (!data || !data.path_nodes || !data.path_nodes.length) {
                state.pathNodes.clear();
                state.pathEdges.clear();
                renderGraph();
                box.innerHTML = '<p class="empty-tip">两个节点之间没有连通路径</p>';
                return;
            }

            const nodes = data.path_nodes;
            const rels = data.path_relations || [];
            state.pathNodes = new Set(nodes);
            state.pathEdges = new Set();
            for (let i = 0; i < nodes.length - 1; i++) {
                state.pathEdges.add(nodes[i] + '→' + nodes[i + 1]);
                state.pathEdges.add(nodes[i + 1] + '→' + nodes[i]);
            }
            renderGraph();

            let html = '<div class="path-chain">';
            nodes.forEach((n, i) => {
                html += '<span class="path-node on">' + escapeHtml(n) + '</span>';
                if (i < nodes.length - 1) {
                    const rel = rels[i] ? '<span class="path-rel">' + escapeHtml(relText(rels[i])) + '</span>' : '';
                    html += '<span class="path-sep">→' + rel + '</span>';
                }
            });
            html += '</div><div style="margin-top:8px;color:var(--ink-3);font-size:11.5px;">共 ' +
                    (nodes.length - 1) + ' 跳</div>';
            box.innerHTML = html;
            toast('已在图中标出该路径');
        } catch (err) {
            box.innerHTML = '<p class="empty-tip">查询失败，请检查后端服务</p>';
        }
    }

    /* ----------------------------- 智能问答 ----------------------------- */

    function appendQa(role, html, extraClass) {
        const log = $('#qaLog');
        const div = document.createElement('div');
        div.className = 'qa-msg ' + role + (extraClass ? ' ' + extraClass : '');
        div.innerHTML = html;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
        return div;
    }

    async function doAsk(question) {
        const input = $('#qaInput');
        const q = (question === undefined ? input.value : question).trim();
        if (!q) { toast('请先输入一个问题'); return; }

        appendQa('ask', escapeHtml(q));
        if (question === undefined) input.value = '';
        const pending = appendQa('reply', '正在思考…', 'pending');

        try {
            const data = await fetchJSON('/api/qa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: q })
            });

            pending.classList.remove('pending');
            let html = escapeHtml(data.answer || '（没有返回答案）');
            if (data.entity) {
                html += '<br><span class="qa-entity">识别到「' + escapeHtml(data.entity) +
                        '」· 意图：' + escapeHtml(data.intent || '—') + '</span>';
            }
            pending.innerHTML = html;
        } catch (err) {
            pending.classList.remove('pending');
            pending.classList.add('error');
            pending.textContent = '问答服务暂时不可用，请检查后端。';
        }
    }

    /* ----------------------------- 工具栏动作 ----------------------------- */

    function setZoom(next) {
        state.zoom = Math.min(4, Math.max(0.2, next));
        if (state.chart) state.chart.setOption({ series: [{ zoom: state.zoom }] });
    }

    function resetView() {
        state.zoom = 1;
        state.selected = null;
        state.pathNodes.clear();
        state.pathEdges.clear();
        renderGraph();
        toast('视图已重置');
    }

    function exportPng() {
        if (!state.chart) return;
        try {
            const url = state.chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: COLOR.paper });
            const a = document.createElement('a');
            a.href = url;
            a.download = '汉文化知识图谱.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            toast('图片已导出');
        } catch (err) {
            toast('导出失败');
        }
    }

    /* ----------------------------- 事件绑定 ----------------------------- */

    function bindEvents() {
        // 侧栏抽屉（窄屏）
        const sidebar = $('#sidebar');
        const mask = $('#mask');
        const closeDrawer = () => { sidebar.classList.remove('open'); mask.classList.remove('show'); };
        $('#sidebarToggle').addEventListener('click', () => {
            sidebar.classList.toggle('open');
            mask.classList.toggle('show', sidebar.classList.contains('open'));
        });
        mask.addEventListener('click', closeDrawer);

        // 搜索
        $('#searchInput').addEventListener('input', onSearchInput);
        $('#searchResults').addEventListener('click', e => {
            const item = e.target.closest('[data-node]');
            if (!item) return;
            const name = item.getAttribute('data-node');
            $('#searchInput').value = name;
            $('#searchResults').innerHTML = '';
            loadNodeDetail(name);
            if (window.innerWidth <= 900) closeDrawer();
        });

        // 详情内的关联跳转
        $('#nodeDetail').addEventListener('click', e => {
            const row = e.target.closest('[data-node]');
            if (row) loadNodeDetail(row.getAttribute('data-node'));
        });

        // 分类过滤
        $('#legendList').addEventListener('click', e => {
            const item = e.target.closest('[data-cat]');
            if (item) toggleCategory(item.getAttribute('data-cat'));
        });

        // 推荐跳转
        $('#recommendList').addEventListener('click', e => {
            const card = e.target.closest('[data-node]');
            if (card) loadNodeDetail(card.getAttribute('data-node'));
        });

        // 问答
        $('#qaBtn').addEventListener('click', () => doAsk());
        $('#qaInput').addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); doAsk(); }
        });
        $('#qaSamples').addEventListener('click', e => {
            const btn = e.target.closest('[data-q]');
            if (btn) doAsk(btn.getAttribute('data-q'));
        });

        // 路径查询
        $('#searchPathBtn').addEventListener('click', doPathQuery);
        ['#pathSource', '#pathTarget'].forEach(sel => {
            $(sel).addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); doPathQuery(); } });
        });
        $('#clearPathBtn').addEventListener('click', () => {
            state.pathNodes.clear();
            state.pathEdges.clear();
            $('#pathResult').innerHTML = '<p class="empty-tip">填写两个节点名，查看它们之间的最短路径</p>';
            renderGraph();
        });

        // 工具栏
        $('#tZoomIn').addEventListener('click', () => setZoom(state.zoom * 1.2));
        $('#tZoomOut').addEventListener('click', () => setZoom(state.zoom / 1.2));
        $('#tReset').addEventListener('click', resetView);
        $('#tFit').addEventListener('click', () => { state.chart && state.chart.resize(); setZoom(1); });
        $('#tEdgeLabel').addEventListener('click', function () {
            state.showEdgeLabel = !state.showEdgeLabel;
            this.classList.toggle('on', state.showEdgeLabel);
            renderGraph();
        });
        $('#tExport').addEventListener('click', exportPng);

        // 图内交互
        state.chart.on('click', params => {
            if (params.dataType === 'node') {
                loadNodeDetail(params.name);
            } else {
                state.selected = null;
                renderGraph();
            }
        });

        // 滚轮缩放后同步缩放值
        state.chart.on('graphRoam', e => { if (e.zoom) state.zoom = e.zoom; });

        // 窗口尺寸变化
        let resizeTimer = null;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => { state.chart && state.chart.resize(); }, 160);
        });

        // Esc 取消选中
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') { state.selected = null; renderGraph(); }
        });
    }

    /* ----------------------------- 初始化 ----------------------------- */

    function init() {
        if (!window.echarts) {
            setLoading(false);
            showBanner('<strong>图表库未加载</strong>：static/vendor/echarts.min.js 缺失，且无法从网络获取。');
            return;
        }

        state.chart = echarts.init($('#chart'), null, { renderer: 'canvas' });
        bindEvents();

        $('#tEdgeLabel').classList.toggle('on', state.showEdgeLabel);

        checkStatus();
        loadGraph();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
