// static/js/assessment.js
(() => {
  if (window.__assessmentScriptInitialized) {
    console.warn('assessment.js: already initialized (duplicate include?)');
    const dbg = document.getElementById('assessment-debug-duplicate');
    if (dbg) dbg.textContent = 'Duplicate assessment script included';
    return;
  }
  window.__assessmentScriptInitialized = true;

  let modal = null, startBtn = null, closeBtn = null, questionsContainer = null;
  let questionsData = null;
  let modalOpen = false, loading = false;

  function debounce(fn, wait = 120) {
    let t = null;
    return (...args) => {
      if (t) clearTimeout(t);
      t = setTimeout(() => fn(...args), wait);
    };
  }

  function showModal() {
    if (!modal || modalOpen) return;
    modal.classList.remove('hidden');
    modal.classList.add('visible');
    modal.setAttribute('aria-hidden', 'false');
    modalOpen = true;
  }
  
  function hideModal() {
    if (!modal || !modalOpen) return;
    modal.classList.remove('visible');
    setTimeout(() => {
      if (!modal.classList.contains('visible')) {
        modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');
      }
    }, 220);
    modalOpen = false;
  }

  function safeAddListener(el, ev, handler) {
    if (!el) return;
    const flag = '__listener_' + ev;
    if (el.dataset[flag]) return;
    el.addEventListener(ev, handler);
    el.dataset[flag] = '1';
  }

  async function loadQuestions(url) {
    if (loading) return null;
    loading = true;
    try {
      const resp = await fetch(url, { credentials: 'same-origin' });
      if (!resp.ok) {
        const text = await resp.text();
        showError(`Failed to load questions: ${resp.status} ${resp.statusText}`);
        console.error('questions load failed', text);
        return null;
      }
      const json = await resp.json();
      questionsData = json;
      return json;
    } catch (err) {
      console.error('Error fetching questions', err);
      showError('Network error while loading questions. See console.');
      return null;
    } finally {
      loading = false;
    }
  }

  function showError(msg) {
    const err = document.getElementById('assessment-error');
    if (err) {
      err.classList.remove('hidden');
      err.textContent = msg;
    } else {
      alert(msg);
    }
  }

  function clearError() {
    const err = document.getElementById('assessment-error');
    if (err) {
      err.classList.add('hidden');
      err.textContent = '';
    }
  }

  function renderQuestionsFor(typeKey) {
    if (!questionsData) {
      showError('No questions loaded');
      return;
    }
    const all = questionsData || {};
    const setKey = typeKey in all ? typeKey : Object.keys(all)[0];
    const set = all[setKey];
    if (!set || !Array.isArray(set)) {
      showError('No question set for: ' + typeKey);
      return;
    }

    questionsContainer.innerHTML = '';
    set.forEach((q, idx) => {
      const qEl = document.createElement('div');
      qEl.className = 'assessment-question mb-4';
      const qText = document.createElement('p');
      qText.className = 'font-medium';
      qText.textContent = `${idx + 1}. ${q.question || q.text || 'Question'}`;
      qEl.appendChild(qText);

      if (Array.isArray(q.options) && q.options.length) {
        const optsWrap = document.createElement('div');
        q.options.forEach((opt, oidx) => {
          const id = `q_${idx}_opt_${oidx}`;
          const label = document.createElement('label');
          label.setAttribute('for', id);
          label.className = 'inline-flex items-center mr-3';
          const input = document.createElement('input');
          input.type = 'radio';
          input.name = `q_${idx}`;
          input.id = id;
          input.value = opt.value ?? opt;
          label.appendChild(input);
          label.appendChild(document.createTextNode(' ' + (opt.label ?? opt)));
          optsWrap.appendChild(label);
        });
        qEl.appendChild(optsWrap);
      } else {
        const txt = document.createElement('input');
        txt.type = 'text';
        txt.name = `q_${idx}`;
        txt.className = 'w-full border p-2';
        qEl.appendChild(txt);
      }
      questionsContainer.appendChild(qEl);
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    modal = document.getElementById('assessmentModal');
    startBtn = document.getElementById('start-assessment-btn');
    closeBtn = document.getElementById('assessment-close-btn');
    questionsContainer = document.getElementById('assessment-questions-container');

    if (!startBtn) {
      console.warn('Start assessment button not found (#start-assessment-btn).');
      return;
    }

    const questionsUrl = startBtn.dataset.questionsUrl || '/static/questions.json';

    safeAddListener(startBtn, 'click', debounce(async function (ev) {
      ev.preventDefault();
      clearError();
      if (!questionsData) {
        const loaded = await loadQuestions(questionsUrl);
        if (!loaded) return;
      }
      const assessmentTypeRaw = startBtn.dataset.assessment || startBtn.dataset.type || Object.keys(questionsData)[0];
      const keys = Object.keys(questionsData);
      let selectedKey = keys.find(k => k.toLowerCase() === (assessmentTypeRaw || '').toLowerCase()) || assessmentTypeRaw || keys[0];

      renderQuestionsFor(selectedKey);
      showModal();
    }, 120));

    safeAddListener(closeBtn, 'click', (e) => {
      e.preventDefault();
      hideModal();
    });

    safeAddListener(modal, 'click', (ev) => {
      if (ev.target === modal) hideModal();
    });

    safeAddListener(document, 'keydown', (ev) => {
      if (ev.key === 'Escape' && modalOpen) hideModal();
    });

    // Optional: wire cancel and submit if present
    const cancelBtn = document.getElementById('assessment-cancel-btn');
    if (cancelBtn) safeAddListener(cancelBtn, 'click', (e) => { e.preventDefault(); hideModal(); });

    const submitBtn = document.getElementById('assessment-submit-btn');
    if (submitBtn) safeAddListener(submitBtn, 'click', (e) => {
      e.preventDefault();
      // optional: collect answers and POST to API endpoint
      // implement as needed; for now just close modal
      hideModal();
    });
  });
})();
