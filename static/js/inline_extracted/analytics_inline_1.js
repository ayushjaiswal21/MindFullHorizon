// Charts for the provider analytics page. Data comes from the #analytics-data JSON block.
// The institution-wide "average wellness score" chart was removed: it averaged the
// LLM-generated digital-detox score across patients, which SYNTHESIS.md c2 bans from any
// aggregate (an unvalidated single-student estimate must not be rolled up into a group figure).
document.addEventListener('DOMContentLoaded', function () {
    const el = document.getElementById('analytics-data');
    if (!el || !window.MFHCharts) return;
    const d = JSON.parse(el.textContent);

    MFHCharts.make(document.getElementById('screenTimeChart'), d.labels,
        [{ label: 'Average daily screen time (hours)', data: d.screen_time }],
        { yMin: 0, yTitle: 'Hours' });
});
