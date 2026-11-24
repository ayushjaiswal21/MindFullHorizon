/* Calming audio page. Tracks come from POST /api/mood-audio; files are played from the /audio routes
   (which redirect to AUDIO_BASE_URL when it is set). Nothing plays until the person presses Play. */
(function () {
  'use strict';
  var root = document.getElementById('music-root');
  if (!root || window.__mfhMusic) return;
  window.__mfhMusic = true;

  var $ = function (id) { return document.getElementById(id); };
  var audio = $('mood-audio'), playerBox = $('player-container'), listBox = $('playlist-container'),
      listDiv = $('playlist'), nowWrap = $('now-playing'), nowLabel = $('now-playing-label'),
      note = $('music-note'), emptyBox = $('music-empty'), emptyText = $('music-empty-text'),
      typeSel = $('filter-type'), bwSel = $('filter-brainwave'), sortSel = $('sort-by'),
      minIn = $('min-freq'), maxIn = $('max-freq'), searchIn = $('search-text'), resetBtn = $('reset-filters'),
      playAll = $('play-all'), nextBtn = $('next-track'), clearBtn = $('clear-playlist'), filtersForm = $('filters');

  var STORE = 'moodMusicFilters';
  var allFiles = [], queue = [], current = -1, currentUrl = '';
  var toast = function (m, t) { if (window.WL) WL.toast(m, t); };
  var debounce = function (fn, ms) { return window.WL ? WL.debounce(fn, ms) : fn; };

  function td(text) { var c = document.createElement('td'); c.textContent = text; return c; }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }

  function readPrefs() {
    try {
      var p = JSON.parse(localStorage.getItem(STORE) || 'null');
      if (!p) return;
      if (p.type) typeSel.value = p.type;
      if (p.brainwave) bwSel.value = p.brainwave;
      if (p.sortBy) sortSel.value = p.sortBy;
      if (p.minFreq) minIn.value = p.minFreq;
      if (p.maxFreq) maxIn.value = p.maxFreq;
      if (p.search) searchIn.value = p.search;
    } catch (e) { /* storage unavailable: filters just start empty */ }
  }
  function savePrefs() {
    try {
      localStorage.setItem(STORE, JSON.stringify({ type: typeSel.value, brainwave: bwSel.value, sortBy: sortSel.value,
        minFreq: minIn.value, maxFreq: maxIn.value, search: searchIn.value }));
    } catch (e) { /* ignore */ }
  }

  function applyFilters() {
    var t = (typeSel.value || 'all').toLowerCase(), b = (bwSel.value || 'all').toLowerCase(), sort = sortSel.value || 'default';
    var min = parseFloat(minIn.value), max = parseFloat(maxIn.value);
    var q = (searchIn.value || '').trim().toLowerCase();
    var out = allFiles.filter(function (f) {
      if (t !== 'all' && (f.type || '').toLowerCase() !== t) return false;
      if (b !== 'all' && (f.brainwave || '').toLowerCase() !== b) return false;
      if (!isNaN(min) && f.frequency && f.frequency < min) return false;
      if (!isNaN(max) && f.frequency && f.frequency > max) return false;
      if (q && ((f.label || '') + ' ' + (f.filename || '')).toLowerCase().indexOf(q) < 0) return false;
      return true;
    });
    var typeOrder = { solfeggio: 0, isochronic: 1, pure: 2 };
    var bwOrder = { delta: 0, theta: 1, alpha: 2, beta: 3, gamma: 4 };
    if (sort === 'frequency_asc') out.sort(function (a, c) { return (a.frequency || 1000) - (c.frequency || 1000); });
    else if (sort === 'frequency_desc') out.sort(function (a, c) { return (c.frequency || 0) - (a.frequency || 0); });
    else if (sort === 'duration') out.sort(function (a, c) { return (typeOrder[a.type] === undefined ? 2 : typeOrder[a.type]) - (typeOrder[c.type] === undefined ? 2 : typeOrder[c.type]); });
    else if (sort === 'brainwave') out.sort(function (a, c) {
      var x = bwOrder[a.brainwave] === undefined ? 5 : bwOrder[a.brainwave], y = bwOrder[c.brainwave] === undefined ? 5 : bwOrder[c.brainwave];
      return x !== y ? x - y : (a.frequency || 0) - (c.frequency || 0);
    });
    else out.sort(function (a, c) { return (c.relevance_score || 0) - (a.relevance_score || 0); });
    return out;
  }

  function render() {
    savePrefs();
    queue = applyFilters();
    listDiv.textContent = '';
    if (!queue.length) {
      var p = document.createElement('p');
      p.className = 'muted';
      p.textContent = 'No tracks match these filters. Reset the filters to see all tracks for this mood.';
      listDiv.appendChild(p);
      return;
    }
    var wrap = document.createElement('div');
    wrap.className = 'table-wrap';
    var table = document.createElement('table');
    table.className = 'table';
    var thead = document.createElement('thead'), hr = document.createElement('tr');
    ['Track', 'Type', 'Band', 'Frequency', 'Length', ''].forEach(function (h, i) {
      var th = document.createElement('th');
      th.scope = 'col';
      if (i === 5) { var s = document.createElement('span'); s.className = 'mfh-visually-hidden'; s.textContent = 'Play'; th.appendChild(s); } else th.textContent = h;
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    var tbody = document.createElement('tbody');
    queue.forEach(function (f, i) {
      var tr = document.createElement('tr');
      tr.className = 'track-row';
      if (f.url === currentUrl) tr.setAttribute('aria-current', 'true');
      tr.append(td(f.label || f.filename), td(f.type ? cap(f.type) : 'Audio'), td(f.brainwave ? cap(f.brainwave) : 'n/a'),
        td(f.frequency ? f.frequency + ' Hz' : 'n/a'), td(f.length_hint === 'long' ? 'Long' : 'Short'));
      var cell = document.createElement('td');
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-secondary btn-sm';
      b.textContent = 'Play';
      b.setAttribute('aria-label', 'Play ' + (f.label || f.filename));
      b.addEventListener('click', function () { playAt(i); });
      cell.appendChild(b);
      tr.appendChild(cell);
      tbody.appendChild(tr);
    });
    table.append(thead, tbody);
    wrap.appendChild(table);
    listDiv.appendChild(wrap);
  }

  function playAt(i) {
    if (i < 0 || i >= queue.length) return;
    var item = queue[i];
    current = i;
    currentUrl = item.url;
    audio.src = item.url;
    nowLabel.textContent = item.label || item.filename;
    nowWrap.hidden = false;
    document.querySelectorAll('.track-row').forEach(function (r, idx) {
      if (idx === i) r.setAttribute('aria-current', 'true'); else r.removeAttribute('aria-current');
    });
    var pr = audio.play();
    if (pr && pr.catch) pr.catch(function () { toast('Could not start this track. Press play on the player.', 'error'); });
  }

  function showResults(has, message) {
    emptyBox.hidden = has;
    listBox.hidden = !has;
    playerBox.hidden = !has;
    if (!has && message) emptyText.textContent = message;
  }

  function loadMood(btn) {
    var mood = btn.getAttribute('data-mood');
    document.querySelectorAll('.mood-btn').forEach(function (b) { b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); });
    btn.setAttribute('aria-busy', 'true');
    note.textContent = 'Loading tracks for ' + mood + '.';
    var min = parseFloat(minIn.value), max = parseFloat(maxIn.value);
    fetch('/api/mood-audio', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.WL ? WL.csrf() : '' },
      body: JSON.stringify({ mood: mood, min_frequency: isNaN(min) ? null : min, max_frequency: isNaN(max) ? null : max,
        type: typeSel.value === 'all' ? null : typeSel.value, sort_by: sortSel.value || 'default' })
    }).then(function (res) { return res.json().catch(function () { return null; }).then(function (d) { return { ok: res.ok, d: d }; }); })
      .then(function (r) {
        if (r.ok && r.d && r.d.success && Array.isArray(r.d.files) && r.d.files.length) {
          allFiles = r.d.files;
          showResults(true);
          render();
          note.textContent = allFiles.length + (allFiles.length === 1 ? ' track' : ' tracks') + ' for ' + mood + '. Press Play on a track.';
        } else if (r.ok) {
          allFiles = [];
          showResults(false, 'There is no matching audio in this library for ' + mood + '. Try another mood, or use the breathing guide instead.');
          note.textContent = 'No tracks found for ' + mood + '.';
        } else {
          showResults(false, 'The track list could not be loaded. Check your connection and try again.');
          note.textContent = 'Could not load tracks.';
          toast('Could not load tracks. Try again.', 'error');
        }
      })
      .catch(function () {
        showResults(false, 'The track list could not be loaded. Check your connection and try again.');
        note.textContent = 'Could not load tracks.';
        toast('Could not load tracks. Try again.', 'error');
      })
      .then(function () { btn.removeAttribute('aria-busy'); });
  }

  document.querySelectorAll('#music-buttons .mood-btn').forEach(function (b) { b.addEventListener('click', function () { loadMood(b); }); });
  audio.addEventListener('ended', function () { if (current + 1 < queue.length) playAt(current + 1); });
  audio.addEventListener('error', function () { if (audio.getAttribute('src')) toast('This track could not be played.', 'error'); });
  playAll.addEventListener('click', function () { playAt(0); });
  nextBtn.addEventListener('click', function () { playAt(current + 1); });
  clearBtn.addEventListener('click', function () {
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    allFiles = []; queue = []; current = -1; currentUrl = '';
    nowWrap.hidden = true;
    listBox.hidden = true;
    playerBox.hidden = true;
    note.textContent = 'Choose a mood to list tracks. Nothing plays until you press Play.';
  });

  var onFilter = debounce(render, 250);
  [typeSel, bwSel, sortSel].forEach(function (c) { c.addEventListener('change', render); });
  [minIn, maxIn, searchIn].forEach(function (c) { c.addEventListener('input', onFilter); });
  resetBtn.addEventListener('click', function () {
    typeSel.value = 'all'; bwSel.value = 'all'; sortSel.value = 'default';
    minIn.value = ''; maxIn.value = ''; searchIn.value = '';
    try { localStorage.removeItem(STORE); } catch (e) { /* ignore */ }
    if (allFiles.length) render();
  });
  filtersForm.addEventListener('submit', function (e) { e.preventDefault(); });

  readPrefs();
})();
