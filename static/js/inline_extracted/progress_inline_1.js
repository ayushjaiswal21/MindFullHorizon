// Progress page: draws the mood and screening charts from the JSON block #progress-data (no Jinja in this file).
document.addEventListener('DOMContentLoaded', function () {
  if (!window.PT) return;
  var blob = document.getElementById('progress-data');
  var data = { mood: [], labels: [], gad7: [], phq9: [] };
  try { data = JSON.parse(blob.textContent); } catch (e) { /* keep empty data, both charts show their empty state */ }

  function short(iso) {
    var d = new Date(iso + 'T12:00:00');
    return isNaN(d) ? iso : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  }

  function empty(host, title, text) {
    host.textContent = '';
    var box = document.createElement('div');
    box.className = 'empty-state';
    var h = document.createElement('h3');
    h.textContent = title;
    var p = document.createElement('p');
    p.textContent = text;
    box.append(h, p);
    host.appendChild(box);
  }

  var moodHost = document.getElementById('moodChart');
  if (moodHost) {
    var mood = (data.mood || []).filter(function (m) { return typeof m.score === 'number'; });
    if (!mood.length) {
      empty(moodHost, 'No mood entries yet', 'Log how you feel today to start your history.');
    } else {
      PT.lineChart(moodHost, {
        labels: mood.map(function (m) { return short(m.date); }),
        series: [{ values: mood.map(function (m) { return m.score; }), cls: 'a' }],
        min: 1, max: 10, ticks: 3,
        label: 'Mood from 1 to 10 across ' + mood.length + ' entries'
      });
    }
  }

  var scoreHost = document.getElementById('assessmentChart');
  if (scoreHost) {
    var labels = data.labels || [];
    if (!labels.length) {
      empty(scoreHost, 'No screenings yet', 'Take a PHQ-9 or GAD-7 to see your scores here.');
    } else {
      PT.lineChart(scoreHost, {
        labels: labels.map(short),
        series: [{ values: data.phq9 || [], cls: 'a' }, { values: data.gad7 || [], cls: 'b' }],
        min: 0, max: 27, ticks: 3,
        label: 'PHQ-9 and GAD-7 scores across ' + labels.length + ' days'
      });
    }
  }
});
