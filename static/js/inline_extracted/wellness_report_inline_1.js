// Wellness report: charts, print and CSV export. Data comes from the #report-data JSON block.
document.addEventListener('DOMContentLoaded', function () {
    const el = document.getElementById('report-data');
    if (!el) return;
    const reportData = JSON.parse(el.textContent);

    const shortDate = s => new Date(s + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });

    if (window.MFHCharts) {
        // Mood of 0 means "no rating" (real ratings run 1 to 10), so leave a gap.
        MFHCharts.make(document.getElementById('mood-trends-chart'), (reportData.mood_labels || []).map(shortDate),
            [{ label: 'Mood (1 to 10)', data: (reportData.mood_data || []).map(v => v ? v : null) }],
            { yMin: 0, yMax: 10, yTitle: 'Mood' });

        MFHCharts.make(document.getElementById('mh-assessment-trends-chart'), (reportData.mh_labels || []).map(shortDate),
            [{ label: 'PHQ-9 score', data: reportData.phq9, spanGaps: true },
             { label: 'GAD-7 score', data: reportData.gad7, spanGaps: true }],
            { yMin: 0, yTitle: 'Score' });

        const logs = (reportData.wellness || []).slice().sort((a, b) => a.date < b.date ? -1 : 1);
        MFHCharts.make(document.getElementById('wellness-trends-chart'), logs.map(l => shortDate(l.date)),
            [{ label: 'Screen time (hours)', data: logs.map(l => l.screen_time_hours), yAxisID: 'y' },
             { label: 'Academic score (%)', data: logs.map(l => l.academic_score), yAxisID: 'y1' }],
            { yMin: 0, yTitle: 'Hours', y1: { min: 0, max: 100, title: 'Academic score (%)' } });
    }

    const printBtn = document.getElementById('print-report-btn');
    if (printBtn) printBtn.addEventListener('click', function () { window.print(); });

    // Long-format CSV: one row per value. Every field is quoted and spreadsheet formulas are neutralised.
    const cell = v => { v = String(v == null ? '' : v); if (/^[=+\-@]/.test(v)) v = "'" + v; return '"' + v.replace(/"/g, '""') + '"'; };
    function exportReport() {
        const rows = [['Date', 'Measure', 'Value']];
        (reportData.mood_labels || []).forEach((d, i) => { const v = reportData.mood_data[i]; if (v) rows.push([d, 'Mood (1 to 10)', v]); });
        (reportData.mh_labels || []).forEach((d, i) => {
            if (reportData.phq9[i] != null) rows.push([d, 'PHQ-9', reportData.phq9[i]]);
            if (reportData.gad7[i] != null) rows.push([d, 'GAD-7', reportData.gad7[i]]);
        });
        (reportData.wellness || []).forEach(l => {
            if (l.screen_time_hours != null) rows.push([l.date, 'Screen time (hours)', l.screen_time_hours]);
            if (l.academic_score != null) rows.push([l.date, 'Academic score (%)', l.academic_score]);
        });
        const csv = rows.map(r => r.map(cell).join(',')).join('\r\n');
        const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = 'wellness_report_' + reportData.patient_id + '_' + new Date().toISOString().slice(0, 10) + '.csv';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        if (window.MFH && typeof MFH.toast === 'function') MFH.toast('CSV downloaded.', 'success');
    }
    const exportBtn = document.getElementById('export-report-btn');
    if (exportBtn) exportBtn.addEventListener('click', exportReport);
});
