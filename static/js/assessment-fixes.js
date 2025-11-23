/* === saveAssessment helper (INSERTED BY SAFE PATCH) === */
async function saveAssessment(payload) {
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';
  try {
    const res = await fetch('/patient/api/save-assessment', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken || ''
      },
      body: JSON.stringify(payload)
    });

    const text = await res.text().catch(() => '');
    if (!res.ok) {
      console.error('saveAssessment failed', res.status, text);
      const errEl = document.getElementById('assessment-error');
      if (errEl) {
        errEl.textContent = 'Failed to save assessment. Try again later.';
        errEl.classList.remove('hidden');
      }
      throw new Error('Save failed: ' + res.status + ' ' + text);
    }

    try { return JSON.parse(text); } catch (e) { return text; }
  } catch (err) {
    console.error('saveAssessment error', err);
    const errEl = document.getElementById('assessment-error');
    if (errEl) {
      errEl.textContent = 'Failed to save assessment. Try again later.';
      errEl.classList.remove('hidden');
    }
    throw err;
  }
}
/* === end saveAssessment helper === */
// static/js/assessment-fixes.js
// Robust bindings and showQuestion() implementation

// mapping of human assessment types to keys used by the JS assessments object
const typeMap = {
  'GAD-7': 'GAD-7',
  'PHQ-9': 'PHQ-9',
  'gad-7': 'GAD-7',
  'phq-9': 'PHQ-9',
  'anxiety': 'GAD-7',     // optional friendly aliases
  'depression': 'PHQ-9'
};

// Quick global guard to stop anchor href="#" from jumping
document.addEventListener('click', function (e) {
  const a = e.target.closest && e.target.closest('a[href="#"]');
  if (a) {
    if (e.cancelable) e.preventDefault();
    e.stopPropagation();
    const btn = a.closest('.start-assessment-btn') || a.querySelector('.start-assessment-btn');
    if (btn) { btn.click(); }
    return;
  }
});

// Delegated handler: one place to catch all "start" clicks
document.addEventListener('click', function (e) {
  // find closest actionable element
  const startBtn = e.target.closest('.start-assessment-btn, #start-assessment-btn, .view-assessment-details-btn, .start-assessment-link');
  if (!startBtn) return;

  // Prevent default browser nav (href="#") and stop bubbling to global handlers
  if (e.cancelable) e.preventDefault();
  e.stopPropagation();

  // Avoid double initialization: guard
  if (window.__assessmentOpening) return;
  window.__assessmentOpening = true;

  try {
    const assessmentType = startBtn.dataset.assessmentType || startBtn.dataset.assessment || startBtn.getAttribute('data-assessment-type');
    const questionsUrl = startBtn.dataset.questionsUrl || startBtn.getAttribute('data-questions-url') || '/static/questions.json';
    openAssessmentModal({ assessmentType, questionsUrl });
  } finally {
    // release flag slightly later (in case open is async)
    setTimeout(() => { window.__assessmentOpening = false; }, 300);
  }
});

function openAssessmentModal(options) {
  const { assessmentType, questionsUrl } = options;
  if (typeof window.startAssessment === 'function') {
    const key = typeMap[assessmentType] || assessmentType;
    window.startAssessment(key);
  } else {
    console.error('startAssessment not available');
  }
}

(function () {
  // Prevent multiple bindings if the file loads twice
  if (window.__assessmentFixesInit) {
    console.warn('assessment-fixes.js already initialized');
    return;
  }
  window.__assessmentFixesInit = true;
  console.log('assessment-fixes.js initialized');

  function lockBodyScroll() {
    document.documentElement.style.scrollBehavior = 'auto';
    document.body.classList.add('modal-open');
  }
  function unlockBodyScroll() {
    document.body.classList.remove('modal-open');
    document.documentElement.style.scrollBehavior = '';
  }

  // Modal helper functions
  function showModal() {
    const modal = document.getElementById("assessmentModal");
    if (!modal || modal.classList.contains("visible")) return;

    lockBodyScroll();
    modal.style.display = "flex";
    requestAnimationFrame(() => {
      modal.classList.add("visible");
      modal.classList.remove("hidden");
      const first = modal.querySelector('input, button, [tabindex]:not([tabindex="-1"])');
      if (first) first.focus({ preventScroll: true });
    });
  }

  function hideModal() {
    const modal = document.getElementById("assessmentModal");
    if (!modal || !modal.classList.contains("visible")) return;

    unlockBodyScroll();
    modal.classList.remove("visible");
    modal.classList.add("hidden");

    setTimeout(() => {
      if (!modal.classList.contains("visible")) {
        modal.style.display = "none";
      }
    }, 200); // smooth transition end
  }

  // safe references for global variables (if original code uses them)
  window.currentAssessment = window.currentAssessment || null;
  window.currentQuestion = window.currentQuestion || 0;
  window.assessmentAnswers = window.assessmentAnswers || [];

  // showQuestion replacement targeting assessment-question-container
  function showQuestion() {
    const container = document.getElementById('assessment-question-container');
    const progressEl = document.getElementById('assessment-progress');
    const questionEl = document.getElementById('assessment-question');
    const optionsEl = document.getElementById('assessment-options');

    if (!container || !progressEl || !questionEl || !optionsEl || !window.currentAssessment) {
      console.error('Assessment: required DOM elements missing or currentAssessment is null.');
      return;
    }

    container.classList.remove('hidden');

    const qIndex = window.currentQuestion;
    const question = window.currentAssessment.questions[qIndex];

    progressEl.textContent = `Question ${qIndex + 1} of ${window.currentAssessment.questions.length}`;
    questionEl.textContent = question.text;

    optionsEl.innerHTML = '';

    if (question.type === 'scale') {
      question.options.forEach((opt, index) => {
        const label = document.createElement('label');
        label.className = 'flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50';
        const input = document.createElement('input');
        input.type = 'radio';
        input.name = 'assessment-answer';
        input.value = index;
        input.className = 'mr-3';
        if ((window.assessmentAnswers.standard[qIndex] || null) === index) {
          input.checked = true;
        }
        input.addEventListener('change', () => {
          selectAnswer(index);
        });
        const span = document.createElement('span');
        span.className = 'text-gray-700';
        span.textContent = opt;
        label.appendChild(input);
        label.appendChild(span);
        optionsEl.appendChild(label);
      });
    } else if (question.type === 'multiple-choice') {
      question.options.forEach((opt) => {
        const label = document.createElement('label');
        label.className = 'flex items-center p-3 border rounded-lg cursor-pointer hover:bg-gray-50';
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.name = 'assessment-answer';
        input.value = opt;
        input.className = 'mr-3';
        if (window.assessmentAnswers.contextual[question.id]?.includes(opt)) {
          input.checked = true;
        }
        input.addEventListener('change', () => {
          selectAnswer(opt, true);
        });
        const span = document.createElement('span');
        span.className = 'text-gray-700';
        span.textContent = opt;
        label.appendChild(input);
        label.appendChild(span);
        optionsEl.appendChild(label);
      });
    } else if (question.type === 'open-ended') {
      const textarea = document.createElement('textarea');
      textarea.name = 'assessment-answer';
      textarea.className = 'w-full p-2 border rounded-lg';
      textarea.rows = 4;
      textarea.placeholder = 'Your thoughts...';
      textarea.value = window.assessmentAnswers.contextual[question.id] || '';
      textarea.addEventListener('input', (e) => {
        selectAnswer(e.target.value);
      });
      optionsEl.appendChild(textarea);
    }

    // ensure nav exists and is wired
    let nav = document.getElementById('assessment-nav');
    if (!nav) {
      const navArea = document.getElementById('assessment-nav-area') || container.parentElement;
      nav = document.createElement('div');
      nav.id = 'assessment-nav';
      nav.className = 'flex justify-between mt-6';
      nav.innerHTML = `<button id="prevBtn" class="btn btn-outline">Previous</button><button id="nextBtn" class="btn btn-primary">Next</button>`;
      navArea.appendChild(nav);
      document.getElementById('prevBtn').addEventListener('click', previousQuestion);
      document.getElementById('nextBtn').addEventListener('click', nextQuestion);
    }

    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');

    prevBtn.disabled = window.currentQuestion === 0;

    // Check if we're in contextual questions mode
    const isContextualMode = window.currentAssessment.contextual_questions &&
      window.currentAssessment.questions === window.currentAssessment.contextual_questions;

    if (isContextualMode) {
      // We're in contextual questions mode
      if (window.currentQuestion === window.currentAssessment.questions.length - 1) {
        // Last contextual question - show complete button
        nextBtn.innerHTML = '<i class="fas fa-check mr-2"></i>Complete Assessment';
        nextBtn.onclick = completeAssessment;
      } else {
        // More contextual questions available
        nextBtn.innerHTML = 'Next <i class="fas fa-arrow-right ml-2"></i>';
        nextBtn.onclick = nextQuestion;
      }
    } else {
      // We're in standard questions mode
      const hasContextualQuestions = window.currentAssessment.contextual_questions &&
        window.currentAssessment.contextual_questions.length > 0;

      if (window.currentQuestion === window.currentAssessment.questions.length - 1) {
        // Last standard question
        if (hasContextualQuestions) {
          // Has contextual questions - show next button to move to contextual
          nextBtn.innerHTML = 'Next <i class="fas fa-arrow-right ml-2"></i>';
          nextBtn.onclick = nextQuestion;
        } else {
          // No contextual questions - show complete button
          nextBtn.innerHTML = '<i class="fas fa-check mr-2"></i>Complete Assessment';
          nextBtn.onclick = completeAssessment;
        }
      } else {
        // More standard questions available
        nextBtn.innerHTML = 'Next <i class="fas fa-arrow-right ml-2"></i>';
        nextBtn.onclick = nextQuestion;
      }
    }
    nextBtn.disabled = false;
  }

  // fallback selectAnswer / next / prev / complete functions if not defined
  function selectAnswer(value, isCheckbox = false) {
    const qIndex = window.currentQuestion;
    const question = window.currentAssessment.questions[qIndex];

    if (question.type === 'scale') {
      window.assessmentAnswers.standard[qIndex] = value;
    } else if (question.type === 'multiple-choice') {
      if (!window.assessmentAnswers.contextual[question.id]) {
        window.assessmentAnswers.contextual[question.id] = [];
      }
      const answers = window.assessmentAnswers.contextual[question.id];
      if (isCheckbox) {
        const index = answers.indexOf(value);
        if (index > -1) {
          answers.splice(index, 1);
        } else {
          answers.push(value);
        }
      }
    } else if (question.type === 'open-ended') {
      window.assessmentAnswers.contextual[question.id] = value;
    }
  }

  function previousQuestion() {
    if (window.currentQuestion > 0) {
      window.currentQuestion--;
      showQuestion();
    }
  }

  function nextQuestion() {
    const qIndex = window.currentQuestion;
    const question = window.currentAssessment.questions[qIndex];

    // Validate answer for scale questions
    if (question.type === 'scale' && window.assessmentAnswers.standard[qIndex] === undefined) {
      alert('Please select an answer before continuing.');
      return;
    }

    // Check if this is the last standard question and we have contextual questions
    const isLastStandardQuestion = qIndex === window.currentAssessment.questions.length - 1;
    const hasContextualQuestions = window.currentAssessment.contextual_questions &&
      window.currentAssessment.contextual_questions.length > 0;
    const isContextualMode = window.currentAssessment.questions === window.currentAssessment.contextual_questions;

    if (isLastStandardQuestion && hasContextualQuestions && !isContextualMode) {
      // Move to contextual questions
      showContextualQuestions();
    } else if (qIndex < window.currentAssessment.questions.length - 1) {
      // Move to next question
      window.currentQuestion++;
      showQuestion();
    } else {
      // No more questions, complete assessment
      completeAssessment();
    }
  }

  function showContextualQuestions() {
    // Store the original questions so we can restore them if needed
    if (!window.originalQuestions) {
      window.originalQuestions = window.currentAssessment.questions;
    }

    // Switch to contextual questions
    window.currentAssessment.questions = window.currentAssessment.contextual_questions;
    window.currentQuestion = 0;
    showQuestion();

    // Update the button to show completion
    const nextBtn = document.getElementById('nextBtn');
    if (nextBtn) {
      nextBtn.innerHTML = '<i class="fas fa-check mr-2"></i>Complete Assessment';
      nextBtn.onclick = completeAssessment;
    }
  }

  async function completeAssessment() {
    if (window.__assessmentSaving) return;
    window.__assessmentSaving = true;
    try {
      // Validate last contextual question if we're in contextual mode
      const qIndex = window.currentQuestion;
      const question = window.currentAssessment.questions[qIndex];

      if (question.type === 'multiple-choice' && (!window.assessmentAnswers.contextual[question.id] || window.assessmentAnswers.contextual[question.id].length === 0)) {
        alert('Please select at least one answer before completing.');
        window.__assessmentSaving = false;
        return;
      }

      if (question.type === 'open-ended' && (!window.assessmentAnswers.contextual[question.id] || window.assessmentAnswers.contextual[question.id].trim() === '')) {
        alert('Please provide a response before completing.');
        window.__assessmentSaving = false;
        return;
      }

      const payload = {
        assessment_type: window.currentAssessment.title,
        score: window.assessmentAnswers.standard.reduce((a, b) => a + b, 0),
        responses: window.assessmentAnswers.standard,
        contextual_responses: window.assessmentAnswers.contextual
      };

      const json = await saveAssessment(payload);
      alert(json?.message || 'Assessment saved.');
      const modal = document.getElementById('assessmentModal');
      if (modal) hideModal(modal);

      // Dynamically update AI insights if available
      if (json.success && json.ai_insights) {
        const insights = json.ai_insights;

        // Update Summary
        const summaryEl = document.getElementById('aiSummary');
        if (summaryEl && insights.summary) {
          summaryEl.textContent = insights.summary;
        }

        // Update Recommendations
        const recsEl = document.getElementById('aiRecommendations');
        if (recsEl && insights.recommendations && Array.isArray(insights.recommendations)) {
          recsEl.innerHTML = insights.recommendations.map(rec =>
            `<li class="flex items-start"><i class="fas fa-check-circle text-green-500 mt-1 mr-2"></i><span>${rec}</span></li>`
          ).join('');
        }

        // Update Resources
        const resEl = document.getElementById('aiResources');
        if (resEl && insights.resources && Array.isArray(insights.resources)) {
          resEl.innerHTML = insights.resources.map(res =>
            `<li class="flex items-start"><i class="fas fa-external-link-alt text-blue-500 mt-1 mr-2"></i><span>${res}</span></li>`
          ).join('');
        }

        // Show the container
        const contentEl = document.getElementById('aiInsightsContent');
        if (contentEl) {
          contentEl.classList.remove('hidden');
          // Scroll to insights
          contentEl.scrollIntoView({ behavior: 'smooth' });
        }
      } else {
        // If no insights returned immediately, maybe reload or show a message
        if (confirm('Assessment saved. Reload page to see updated history?')) {
          window.location.reload();
        }
      }
    } catch (err) {
      // Error is handled by saveAssessment
    } finally {
      setTimeout(() => { window.__assessmentSaving = false; }, 300);
    }
  }

  // startAssessment: called when user clicks card/button
  let allAssessments = {};

  // Load assessment questions with error handling
  async function loadQuestions() {
    if (Object.keys(allAssessments).length === 0) {
      try {
        const response = await fetch('/static/questions.json');
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        allAssessments = await response.json();
        console.log('Loaded assessments:', Object.keys(allAssessments));
      } catch (error) {
        console.error('Error loading assessment questions:', error);
        const errEl = document.getElementById('assessment-error');
        if (errEl) {
          errEl.classList.remove('hidden');
          const errorMessage = errEl.querySelector('p');
          if (errorMessage) {
            errorMessage.textContent = 'Could not load assessment questions. Please check your connection.';
          }
        } else {
          alert('Could not load assessment questions. See console for details.');
        }
      }
    }
  }


  window.startAssessment = async function (typeKey) {
    await loadQuestions();

    const assessmentData = allAssessments[typeKey];
    if (!assessmentData) {
      console.error(`Assessment type "${typeKey}" not found.`);
      return;
    }

    window.currentAssessment = assessmentData;
    window.currentQuestion = 0;
    window.assessmentAnswers = {
      standard: [],
      contextual: {}
    };

    const modal = document.getElementById('assessmentModal');
    const title = document.getElementById('assessmentTitle');

    if (title && window.currentAssessment) {
      title.textContent = window.currentAssessment.title;
    }

    if (modal) {
      showModal(modal);
    }

    showQuestion();
  };



  // Attach handlers to cards/buttons and mood options
  document.addEventListener('DOMContentLoaded', function () {
    // Mood options binding
    document.querySelectorAll('.mood-option').forEach(opt => {
      opt.addEventListener('click', () => {
        // visual
        document.querySelectorAll('.mood-option').forEach(o => o.classList.remove('selected'));
        opt.classList.add('selected');
        const btn = document.getElementById('save-mood-btn');
        if (btn) btn.disabled = false;
        // call selectMood if present
        const m = opt.getAttribute('data-mood');
        if (typeof window.selectMood === 'function') {
          try { window.selectMood(parseInt(m, 10)); } catch (e) { console.warn(e); }
        }
      });
    });

    // Save mood click handler (if not already implemented)
    /* === MOOD SAVE: unified handler (INSERTED) === */
    if (typeof document !== 'undefined') {
      const saveMoodBtn = document.getElementById('save-mood-btn');
      if (saveMoodBtn) {
        saveMoodBtn.addEventListener('click', async () => {
          const sel = document.querySelector('.mood-option.selected');
          if (!sel) {
            alert('Please select a mood first.');
            return;
          }
          const moodVal = sel.getAttribute('data-mood');

          const csrfMeta = document.querySelector('meta[name="csrf-token"]');
          const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

          try {
            const res = await fetch('/api/mood', {
              method: 'POST',
              credentials: 'same-origin',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || ''
              },
              body: JSON.stringify({ value: Number(moodVal) })
            });

            const text = await res.text().catch(() => null);
            let json;
            try { json = JSON.parse(text); } catch (e) { json = { raw: text }; }

            if (res.ok) {
              alert(json?.message || 'Mood saved.');
              saveMoodBtn.disabled = true;
              if (typeof window._debugMoods === 'function') window._debugMoods();
            } else {
              console.warn('save-mood failed', res.status, json);
              alert(json?.message || 'Failed to save mood.');
            }
          } catch (err) {
            console.error('Error saving mood', err);
            alert('Network error while saving mood.');
          }
        });
      }
    }
    /* === END MOOD SAVE === */

    // Close/open bindings
    const closeBtn = document.getElementById('closeAssessmentBtn');
    if (closeBtn) closeBtn.addEventListener('click', () => {
      const modal = document.getElementById('assessmentModal');
      if (modal) hideModal(modal);
    });
    const openBtn = document.getElementById('openAssessmentBtn');
    if (openBtn) openBtn.addEventListener('click', () => {
      window.startAssessment('anxiety');
    });

    // Event listener for closing the assessment modal
    document.querySelectorAll('.close-assessment-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const modal = document.getElementById('assessmentModal');
        if (modal) hideModal(modal);
      });
    });

    // Define viewAssessmentDetails on the window object
    if (typeof window.viewAssessmentDetails !== 'function') {
      window.viewAssessmentDetails = function (assessmentId) {
        // Placeholder logic for viewing assessment details.
        // This could be implemented to fetch details and show another modal.
        alert(`Viewing details for assessment ID: ${assessmentId}`);
      };
    }
  });

})();

