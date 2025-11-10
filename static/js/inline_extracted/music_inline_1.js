
async function fetchMoodMap() {
  try {
    const res = await fetch('/api/mood-music');
    const data = await res.json();
    return data.moods || {};
  } catch (e) {
    console.error('Failed to fetch mood map', e);
    return {};
  }
}

async function init() {
  const audio = document.getElementById('mood-audio');
  const playlistContainer = document.getElementById('playlist-container');
  const playlistDiv = document.getElementById('playlist');
  const nowPlayingWrap = document.getElementById('now-playing');
  const nowPlayingLabel = document.getElementById('now-playing-label');
  const playAllBtn = document.getElementById('play-all');
  const nextBtn = document.getElementById('next-track');
  const clearBtn = document.getElementById('clear-playlist');
  const controls = document.getElementById('player-controls');

  // Filters
  const typeSel = document.getElementById('filter-type');
  const brainwaveSel = document.getElementById('filter-brainwave');
  const sortSel = document.getElementById('sort-by');
  const minFreqInput = document.getElementById('min-freq');
  const maxFreqInput = document.getElementById('max-freq');
  const searchInput = document.getElementById('search-text');
  const resetBtn = document.getElementById('reset-filters');

  // State
  let allFiles = [];
  let queue = [];
  let currentIndex = -1;

  function setVisible(el, show) { el.style.display = show ? 'block' : 'none'; }

  // Load filter preferences from localStorage
  function loadFilterPreferences() {
    try {
      const saved = localStorage.getItem('moodMusicFilters');
      if (saved) {
        const prefs = JSON.parse(saved);
        if (prefs.type) typeSel.value = prefs.type;
        if (prefs.brainwave) brainwaveSel.value = prefs.brainwave;
        if (prefs.sortBy) sortSel.value = prefs.sortBy;
        if (prefs.minFreq !== undefined) minFreqInput.value = prefs.minFreq;
        if (prefs.maxFreq !== undefined) maxFreqInput.value = prefs.maxFreq;
        if (prefs.search) searchInput.value = prefs.search;
      }
    } catch (e) {
      console.debug('Failed to load filter preferences', e);
    }
  }

  // Save filter preferences to localStorage
  function saveFilterPreferences() {
    try {
      const prefs = {
        type: typeSel.value,
        brainwave: brainwaveSel.value,
        sortBy: sortSel.value,
        minFreq: minFreqInput.value,
        maxFreq: maxFreqInput.value,
        search: searchInput.value
      };
      localStorage.setItem('moodMusicFilters', JSON.stringify(prefs));
    } catch (e) {
      console.debug('Failed to save filter preferences', e);
    }
  }

  // Reset all filters to default
  function resetFilters() {
    typeSel.value = 'all';
    brainwaveSel.value = 'all';
    sortSel.value = 'default';
    minFreqInput.value = '';
    maxFreqInput.value = '';
    searchInput.value = '';
    localStorage.removeItem('moodMusicFilters');
    if (allFiles && allFiles.length > 0) {
      const filtered = applyFilters();
      renderPlaylist(filtered);
    }
  }

  function applyFilters() {
    const typeVal = (typeSel.value || 'all').toLowerCase();
    const bwVal = (brainwaveSel.value || 'all').toLowerCase();
    const sortVal = sortSel.value || 'default';
    const minFreq = parseFloat(minFreqInput.value) || null;
    const maxFreq = parseFloat(maxFreqInput.value) || null;
    const q = (searchInput.value || '').trim().toLowerCase();
    
    let filtered = (allFiles || []).filter(f => {
      if (typeVal !== 'all' && (f.type || '').toLowerCase() !== typeVal) return false;
      if (bwVal !== 'all' && (f.brainwave || '').toLowerCase() !== bwVal) return false;
      if (minFreq !== null && f.frequency && f.frequency < minFreq) return false;
      if (maxFreq !== null && f.frequency && f.frequency > maxFreq) return false;
      if (q) {
        const hay = ((f.label || '') + ' ' + (f.filename || '')).toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    
    // Apply sorting
    if (sortVal === 'relevance') {
      filtered.sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));
    } else if (sortVal === 'frequency_asc') {
      filtered.sort((a, b) => (a.frequency || 1000) - (b.frequency || 1000));
    } else if (sortVal === 'frequency_desc') {
      filtered.sort((a, b) => (b.frequency || 0) - (a.frequency || 0));
    } else if (sortVal === 'duration') {
      const typeOrder = { solfeggio: 0, isochronic: 1, pure: 2 };
      filtered.sort((a, b) => (typeOrder[a.type] || 2) - (typeOrder[b.type] || 2));
    } else if (sortVal === 'brainwave') {
      const bwOrder = { delta: 0, theta: 1, alpha: 2, beta: 3, gamma: 4 };
      filtered.sort((a, b) => {
        const aOrder = bwOrder[a.brainwave] !== undefined ? bwOrder[a.brainwave] : 5;
        const bOrder = bwOrder[b.brainwave] !== undefined ? bwOrder[b.brainwave] : 5;
        if (aOrder !== bOrder) return aOrder - bOrder;
        return (a.frequency || 0) - (b.frequency || 0);
      });
    }
    
    saveFilterPreferences();
    return filtered;
  }

  function renderPlaylist(files) {
    queue = files.slice();
    playlistDiv.innerHTML = '';
    if (!files.length) {
      playlistDiv.innerHTML = '<div style="padding:10px; color:#64748b;">No tracks match the current filters.</div>';
      setVisible(playlistContainer, true);
      setVisible(controls, false);
      return;
    }

    files.forEach((file, idx) => {
      const card = document.createElement('div');
      card.style.border = '1px solid #e2e8f0';
      card.style.borderRadius = '12px';
      card.style.padding = '10px';
      card.style.background = '#fff';
      const title = document.createElement('div');
      title.style.fontWeight = '600';
      title.style.color = '#1f2937';
      title.textContent = file.label || file.filename;
      const meta = document.createElement('div');
      meta.style.fontSize = '0.9rem';
      meta.style.color = '#64748b';
      const lengthHint = file.length_hint === 'long' ? '⏱️ Long' : 'Short';
      const typeLabel = file.type ? file.type.charAt(0).toUpperCase() + file.type.slice(1) : 'Audio';
      const brainwaveLabel = file.brainwave ? ` • ${file.brainwave.charAt(0).toUpperCase() + file.brainwave.slice(1)}` : '';
      const freqLabel = file.frequency ? ` • ${file.frequency} Hz` : '';
      const relevanceLabel = file.relevance_score > 0 ? ` • ⭐${file.relevance_score}` : '';
      meta.textContent = `${typeLabel} • ${lengthHint}${brainwaveLabel}${freqLabel}${relevanceLabel}`;
      const actions = document.createElement('div');
      actions.style.marginTop = '8px';
      const playBtn = document.createElement('button');
      playBtn.className = 'mood-btn';
      playBtn.style.padding = '6px 12px';
      playBtn.textContent = 'Play';
      playBtn.addEventListener('click', () => playAt(idx));
      actions.appendChild(playBtn);
      card.appendChild(title);
      card.appendChild(meta);
      card.appendChild(actions);
      playlistDiv.appendChild(card);
    });
    setVisible(playlistContainer, files.length > 0);
    setVisible(controls, files.length > 0);
  }

  async function playAt(i) {
    if (i < 0 || i >= queue.length) return;
    currentIndex = i;
    const item = queue[i];
    audio.src = item.url;
    setVisible(audio, true);
    nowPlayingLabel.textContent = item.label || item.filename;
    setVisible(nowPlayingWrap, true);
    try { await audio.play(); } catch (err) { console.debug('Autoplay prevented', err); }
  }

  audio.addEventListener('ended', () => {
    if (currentIndex + 1 < queue.length) {
      playAt(currentIndex + 1);
    }
  });

  playAllBtn.addEventListener('click', () => { if (queue.length) playAt(0); });
  nextBtn.addEventListener('click', () => { if (currentIndex + 1 < queue.length) playAt(currentIndex + 1); });
  clearBtn.addEventListener('click', () => {
    queue = [];
    currentIndex = -1;
    setVisible(playlistContainer, false);
    setVisible(controls, false);
    setVisible(audio, false);
    setVisible(nowPlayingWrap, false);
  });

  function onFilterChange() {
    const filtered = applyFilters();
    renderPlaylist(filtered);
  }
  
  // Add event listeners for all filters
  typeSel.addEventListener('change', onFilterChange);
  brainwaveSel.addEventListener('change', onFilterChange);
  sortSel.addEventListener('change', onFilterChange);
  minFreqInput.addEventListener('input', onFilterChange);
  maxFreqInput.addEventListener('input', onFilterChange);
  searchInput.addEventListener('input', onFilterChange);
  resetBtn.addEventListener('click', resetFilters);
  
  // Load saved preferences on initialization
  loadFilterPreferences();

  document.querySelectorAll('#music-buttons .mood-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const mood = btn.getAttribute('data-mood');

      // CSRF token for POSTs
      const csrfMeta = document.querySelector('meta[name=\"csrf-token\"]');
      const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

      try {
        // Load local files (preferred)
        // Get current filter settings
        const minFreq = parseFloat(minFreqInput.value) || null;
        const maxFreq = parseFloat(maxFreqInput.value) || null;
        const filterType = typeSel.value === 'all' ? null : typeSel.value;
        const sortBy = sortSel.value || 'default';
        
        const res = await fetch('/api/mood-audio', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(csrfToken && { 'X-CSRFToken': csrfToken })
          },
          body: JSON.stringify({ 
            mood, 
            min_frequency: minFreq,
            max_frequency: maxFreq,
            type: filterType,
            sort_by: sortBy
          })
        });
        const data = await res.json();
        if (data && data.success && Array.isArray(data.files) && data.files.length > 0) {
          allFiles = data.files;
          const filtered = applyFilters();
          renderPlaylist(filtered);
          // Auto-start with first long track if available in filtered list
          const firstLong = filtered.findIndex(f => f.length_hint === 'long');
          const startIdx = firstLong >= 0 ? firstLong : 0;
          if (filtered.length) { await playAt(startIdx); }
          return;
        }

        // Fallback: curated search
        const mapRes = await fetch('/api/mood-music');
        const mapJson = await mapRes.json();
        const moods = mapJson.moods || {};
        const entry = moods[mood] || {};
        const query = entry.query || ('binaural beats ' + mood);
        const url = 'https://www.youtube.com/results?search_query=' + encodeURIComponent(query);
        try { window.open(url, '_blank', 'noopener'); } catch (_) { window.location.href = url; }

        // Log selection (best-effort)
        try { await fetch('/api/log-mood-selection', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(csrfToken && { 'X-CSRFToken': csrfToken }) },
          body: JSON.stringify({ mood, query, video: null })
        }); } catch (_) {}

      } catch (e) {
        console.error('Play mood failed', e);
        alert('Failed to load mood playlist.');
      }
    });
  });
}

document.addEventListener('DOMContentLoaded', init);
