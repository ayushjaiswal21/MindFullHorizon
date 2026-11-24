// Shared by the analytics page and the wellness report. Chart.js is loaded only when a canvas needs it.
(function () {
    const CHART_URL = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js';
    const charts = [];
    let loading = null;

    function token(name, fallback) {
        const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return v || fallback;
    }

    // Series differ by colour, line dash and point shape, so meaning never rests on colour alone.
    function series(i) {
        const colours = [token('--primary', '#0F766E'), token('--info', '#175CD3'), token('--warning', '#B54708'), token('--danger', '#B42318')];
        const dashes = [[], [6, 4], [2, 3], [10, 4, 2, 4]];
        const points = ['circle', 'rect', 'triangle', 'rectRot'];
        return { borderColor: colours[i % 4], backgroundColor: colours[i % 4], borderDash: dashes[i % 4], pointStyle: points[i % 4] };
    }

    function loadChartJs() {
        if (window.Chart) return Promise.resolve();
        if (loading) return loading;
        loading = new Promise(function (resolve, reject) {
            const s = document.createElement('script');
            s.src = CHART_URL;
            s.crossOrigin = 'anonymous';
            s.referrerPolicy = 'no-referrer';
            const nonce = document.documentElement.dataset.nonce;
            if (nonce) s.nonce = nonce;
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
        return loading;
    }

    function applyTheme(chart) {
        const text = token('--text', '#14201C');
        const border = token('--border', '#D5DCD8');
        Object.values(chart.options.scales || {}).forEach(function (axis) {
            axis.ticks = Object.assign(axis.ticks || {}, { color: text });
            axis.grid = Object.assign(axis.grid || {}, { color: border });
            if (axis.title) axis.title.color = text;
        });
        chart.options.plugins.legend.labels.color = text;
        chart.data.datasets.forEach(function (d, i) {
            const s = series(i);
            Object.assign(d, s);
        });
    }

    // config.datasets: [{label, data, yAxisID?}]; options: {yMin, yMax, yTitle, xTitle, y1?}
    function make(canvas, labels, datasets, opts) {
        if (!canvas) return Promise.resolve(null);
        return loadChartJs().then(function () {
            const scales = {
                x: { title: { display: true, text: opts.xTitle || 'Date' } },
                y: { min: opts.yMin, max: opts.yMax, title: { display: true, text: opts.yTitle || '' } }
            };
            if (opts.y1) {
                scales.y1 = { position: 'right', min: opts.y1.min, max: opts.y1.max, title: { display: true, text: opts.y1.title }, grid: { drawOnChartArea: false } };
            }
            const chart = new window.Chart(canvas, {
                type: 'line',
                data: { labels: labels, datasets: datasets.map(function (d) { return Object.assign({ tension: 0, spanGaps: false, borderWidth: 2, pointRadius: 3 }, d); }) },
                options: {
                    animation: false,
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: scales,
                    plugins: { legend: { position: 'bottom', labels: {} } }
                }
            });
            applyTheme(chart);
            chart.update();
            charts.push(chart);
            return chart;
        }).catch(function () {
            const note = document.createElement('p');
            note.className = 'help';
            note.textContent = 'The chart could not load. The data table below has the same values.';
            canvas.replaceWith(note);
            return null;
        });
    }

    // Redraw with new token colours when the theme toggles.
    new MutationObserver(function () {
        charts.forEach(function (c) { applyTheme(c); c.update(); });
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] });

    window.MFHCharts = { make: make };
})();
