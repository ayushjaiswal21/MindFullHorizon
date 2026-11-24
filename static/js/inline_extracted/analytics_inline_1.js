// Charts for the provider analytics page. Data comes from the #analytics-data JSON block.
document.addEventListener('DOMContentLoaded', function () {
    const el = document.getElementById('analytics-data');
    if (!el || !window.MFHCharts) return;
    const d = JSON.parse(el.textContent);

    MFHCharts.make(document.getElementById('screenTimeChart'), d.labels,
        [{ label: 'Average daily screen time (hours)', data: d.screen_time }],
        { yMin: 0, yTitle: 'Hours' });

    // A wellness score of 0 means "no score that day" (real scores run 1 to 5), so leave a gap.
    MFHCharts.make(document.getElementById('wellnessChart'), d.labels,
        [{ label: 'Average wellness score (1 to 5)', data: d.wellness.map(function (v) { return v ? v : null; }) }],
        { yMin: 0, yMax: 5, yTitle: 'Score' });
});
