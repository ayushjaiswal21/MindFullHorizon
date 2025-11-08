// static/js/assessment-fixes.js
// Robust bindings and showQuestion() implementation
(function () {
  // mapping of human assessment types to keys used by the JS assessments object
  const typeMap = {
    'GAD-7': 'anxiety',
    'PHQ-9': 'depression',
    'gad-7': 'anxiety',
    'phq-9': 'depression'
  };

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

    if (window.currentQuestion === window.currentAssessment.questions.length - 1) {
      nextBtn.innerHTML = '<i class="fas fa-check mr-2"></i>Complete Assessment';
      nextBtn.onclick = completeAssessment;
      nextBtn.disabled = false;
    } else {
      nextBtn.innerHTML = 'Next <i class="fas fa-arrow-right ml-2"></i>';
      nextBtn.onclick = nextQuestion;
      nextBtn.disabled = false;
    }
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

    if (question.type === 'scale' && window.assessmentAnswers.standard[qIndex] === undefined) {
      alert('Please select an answer before continuing.');
      return;
    }

    if (qIndex < window.currentAssessment.questions.length - 1) {
      window.currentQuestion++;
      showQuestion();
    } else {
      showContextualQuestions();
    }
  }

  function showContextualQuestions() {
    window.currentAssessment.questions = window.currentAssessment.contextual_questions;
    window.currentQuestion = 0;
    showQuestion();
    const nextBtn = document.getElementById('nextBtn');
    nextBtn.innerHTML = '<i class="fas fa-check mr-2"></i>Complete Assessment';
    nextBtn.onclick = completeAssessment;
  }

  async function completeAssessment() {
    const payload = {
      assessment_type: window.currentAssessment.title,
      score: window.assessmentAnswers.standard.reduce((a, b) => a + b, 0),
      responses: window.assessmentAnswers.standard,
      contextual_responses: window.assessmentAnswers.contextual
    };

    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    try {
      const res = await fetch('/api/save-assessment', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify(payload)
      });
      const json = await res.json().catch(() => null);
      if (res.ok) {
        alert(json?.message || 'Assessment saved.');
        const modal = document.getElementById('assessmentModal');
        if (modal) modal.classList.add('hidden');
      } else {
        alert(json?.message || 'Failed to save assessment.');
        console.warn('Assessment save failed', res.status, json);
      }
    } catch (err) {
      console.error('Error saving assessment', err);
      alert('Network error saving assessment.');
    }
  }

  // startAssessment: called when user clicks card/button
  let allAssessments = {};

  async function loadQuestions() {
    if (Object.keys(allAssessments).length === 0) {
      try {
        const response = await fetch('/static/questions.json');
        if (!response.ok) {
          throw new Error('Failed to load assessment questions.');
        }
        allAssessments = await response.json();
      } catch (error) {
        console.error(error);
        // Handle error, maybe show a message to the user
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
        modal.classList.remove('hidden');
    }
    
    showQuestion();
  };

  // Attach handlers to cards/buttons and mood options
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.start-assessment-btn').forEach(card => {
      card.addEventListener('click', () => {
        const type = card.dataset.assessmentType || card.getAttribute('data-assessment-type') || 'GAD-7';
        const key = typeMap[type] || type.toLowerCase();
        if (typeof window.startAssessment === 'function') {
          window.startAssessment(key);
        } else {
          console.error('startAssessment not available');
        }
      });
    });

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
    const saveMoodBtn = document.getElementById('save-mood-btn');
    if (saveMoodBtn) {
      saveMoodBtn.addEventListener('click', async () => {
        const sel = document.querySelector('.mood-option.selected');
        if (!sel) {
          alert('Please select a mood first.');
          return;
        }
        const moodVal = sel.getAttribute('data-mood');
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        try {
          const res = await fetch('/api/save-mood', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ mood: moodVal })
          });
          const json = await res.json().catch(() => null);
          if (res.ok) {
            alert(json?.message || 'Mood saved.');
            saveMoodBtn.disabled = true;
          } else {
            alert(json?.message || 'Failed to save mood.');
            console.warn('save-mood', res.status, json);
          }
        } catch (err) {
          console.error('Error saving mood', err);
          alert('Network error while saving mood.');
        }
      });
    }

    // Close/open bindings
    const closeBtn = document.getElementById('closeAssessmentBtn');
    if (closeBtn) closeBtn.addEventListener('click', () => {
      const modal = document.getElementById('assessmentModal');
      if (modal) modal.classList.add('hidden');
    });
    const openBtn = document.getElementById('openAssessmentBtn');
    if (openBtn) openBtn.addEventListener('click', () => {
      window.startAssessment('anxiety');
    });
  });

})();
