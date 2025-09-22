# MindFull Horizon – Enhancement Implementation Guide

This guide contains ready-to-use code snippets, exact file locations, and integration steps for the four requested features:

- Profile Picture Upload
- Editable Profile Information
- Detailed Digital Detox Trends
- Customizable Goals Display

Follow the per-feature sections below. Each section includes:
- What you’ll add (routes, models, templates, JS)
- Where to put the code
- How to wire it into the existing app

Note: Filenames and paths use your repo structure under `MindFullHorizon/`.

---

## 1) Profile Picture Upload

### What you’ll add
- App config for uploads
- Secure image upload endpoint
- Display logic in `templates/profile.html`

### Where to add
- `app.py`: config + route
- `templates/profile.html`: upload form + dynamic image
- Create folder: `uploads/` (sibling to `static/`, auto-created by code)

### Code

Add to `app.py` (top-level imports, if not present):
```python
import os
from werkzeug.utils import secure_filename
```

Add to `app.py` after app creation/config:
```python
# Profile image uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
```

Add endpoint in `app.py` (near other profile/user routes):
```python
from flask import send_file

@app.route('/profile/photo', methods=['POST'])
def upload_profile_photo():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    file = request.files.get('photo')
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Invalid file type'}), 400

    # Use user-specific filename
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"user_{session['user_id']}.{ext}")
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(path)

    # Optionally store path in session or DB (simple session example):
    session['profile_photo'] = filename
    return jsonify({'success': True, 'filename': filename})

@app.route('/profile/photo/<filename>')
def serve_profile_photo(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(path):
        return send_file(path)
    # Fallback to placeholder
    return redirect(url_for('static', filename='images/user_placeholder.png'))
```

Update `templates/profile.html` – replace the placeholder `img` block with dynamic src and add an upload form under it:
```html
<!-- Profile picture -->
<img class="h-24 w-24 rounded-full object-cover border-4 border-purple-300 shadow-lg"
     src="{{ url_for('serve_profile_photo', filename=session.get('profile_photo', '')) if session.get('profile_photo') else url_for('static', filename='images/user_placeholder.png') }}"
     alt="Profile Picture">

<form id="photo-upload-form" class="mt-4" enctype="multipart/form-data">
  <label class="block text-sm font-medium text-gray-700 mb-1">Update Profile Picture</label>
  <input type="file" name="photo" accept="image/*" class="mb-2">
  <button type="submit" class="px-3 py-1 bg-purple-600 text-white rounded">Upload</button>
  <p id="photo-msg" class="text-sm mt-2"></p>
</form>

<script>
  document.getElementById('photo-upload-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);
    const btn = form.querySelector('button');
    const msg = document.getElementById('photo-msg');
    btn.disabled = true; btn.textContent = 'Uploading...';
    try {
      const res = await fetch('/profile/photo', { method: 'POST', body: data });
      const out = await res.json();
      if (out.success) {
        msg.textContent = 'Uploaded!'; msg.className = 'text-green-600 text-sm mt-2';
        // Reload to show new image (or swap src dynamically)
        location.reload();
      } else {
        msg.textContent = out.message || 'Upload failed'; msg.className = 'text-red-600 text-sm mt-2';
      }
    } catch(err) {
      msg.textContent = 'Network error'; msg.className = 'text-red-600 text-sm mt-2';
    } finally {
      btn.disabled = false; btn.textContent = 'Upload';
    }
  });
</script>
```

That’s it. The image stores under `uploads/` and is served via `/profile/photo/<filename>`.

---

## 2) Editable Profile Information

### What you’ll add
- A simple edit form for `name`, `institution`
- Endpoint to update current user

### Where to add
- `app.py`: `POST /profile/edit`
- `templates/profile.html`: small form near profile header

### Code

In `app.py`:
```python
@app.route('/profile/edit', methods=['POST'])
def edit_profile():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authorized'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    payload = request.get_json(silent=True) or {}
    new_name = payload.get('name')
    new_institution = payload.get('institution')

    if new_name:
        user.name = new_name.strip()[:100]
    if new_institution is not None:
        user.institution = (new_institution or '').strip()[:100]

    db.session.commit()
    return jsonify({'success': True, 'message': 'Profile updated'})
```

In `templates/profile.html`, below the header info, add a compact edit UI:
```html
<div class="mt-4">
  <button id="edit-toggle" class="text-sm text-blue-700 underline">Edit Profile</button>
  <form id="edit-form" class="mt-3 hidden">
    <div class="grid md:grid-cols-2 gap-3">
      <div>
        <label class="block text-sm">Name</label>
        <input id="edit-name" class="w-full border px-2 py-1 rounded" value="{{ user.name }}">
      </div>
      <div>
        <label class="block text-sm">Institution</label>
        <input id="edit-institution" class="w-full border px-2 py-1 rounded" value="{{ user.institution or '' }}">
      </div>
    </div>
    <div class="mt-3">
      <button type="submit" class="px-3 py-1 bg-blue-600 text-white rounded">Save</button>
      <span id="edit-msg" class="text-sm ml-2"></span>
    </div>
  </form>
</div>

<script>
  const tgl = document.getElementById('edit-toggle');
  const frm = document.getElementById('edit-form');
  const msg = document.getElementById('edit-msg');
  tgl?.addEventListener('click', () => frm.classList.toggle('hidden'));
  frm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    msg.textContent = '';
    const body = {
      name: document.getElementById('edit-name').value,
      institution: document.getElementById('edit-institution').value
    };
    const res = await fetch('/profile/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const out = await res.json();
    if (out.success) { msg.textContent = 'Saved'; msg.className = 'text-green-600 text-sm ml-2'; location.reload(); }
    else { msg.textContent = out.message || 'Failed'; msg.className = 'text-red-600 text-sm ml-2'; }
  });
</script>
```

---

## 3) Detailed Digital Detox Trends

### What you’ll add
- Trends API that computes 7/30 day averages, moving average, streaks
- Additional charts on `templates/digital_detox.html`

### Where to add
- `app.py`: `GET /api/digital-detox-trends`
- `templates/digital_detox.html`: new canvases + JS

### Code

In `app.py` (helper and route):
```python
from datetime import timedelta

@app.route('/api/digital-detox-trends')
def digital_detox_trends():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not authorized'}), 401
    logs = DigitalDetoxLog.query.filter_by(user_id=session['user_id']).order_by(DigitalDetoxLog.date.asc()).all()
    if not logs:
        return jsonify({'success': True, 'data': { 'series': [], 'avg7': 0, 'avg30': 0, 'streak': 0 }})

    series = [{ 'date': l.date.isoformat(), 'hours': float(l.screen_time_hours or 0), 'academic': l.academic_score or 0 } for l in logs]

    def avg_of_last(days):
        cutoff = (logs[-1].date) - timedelta(days=days-1)
        vals = [float(l.screen_time_hours or 0) for l in logs if l.date >= cutoff]
        return round(sum(vals) / len(vals), 2) if vals else 0

    # moving average (7-day)
    ma7 = []
    for i in range(len(series)):
        window = series[max(0, i-6):i+1]
        if window:
            ma7.append(round(sum(x['hours'] for x in window) / len(window), 2))
        else:
            ma7.append(series[i]['hours'])

    # simple decreasing streak (days where hours decreased vs previous day)
    streak = 0
    for i in range(1, len(series)):
        if series[i]['hours'] <= series[i-1]['hours']:
            streak += 1
        else:
            streak = 0

    return jsonify({
        'success': True,
        'data': {
            'series': series,
            'moving_avg_7d': ma7,
            'avg7': avg_of_last(7),
            'avg30': avg_of_last(30),
            'streak_decreasing_days': streak
        }
    })
```

In `templates/digital_detox.html`, add new canvases under the existing charts and extend the JS:
```html
<div class="card p-6 mb-8">
  <h3 class="text-xl font-semibold text-gray-800 mb-4 flex items-center">
    <i class="fas fa-wave-square text-teal-600 mr-3"></i>7-Day Moving Average
  </h3>
  <div class="chart-container">
    <canvas id="ma7-chart"></canvas>
  </div>
  <div class="mt-3 text-sm text-gray-600" id="trend-stats"></div>
</div>
```

Append to the bottom of the existing `<script>` in this file:
```javascript
async function loadTrends() {
  const res = await fetch('/api/digital-detox-trends');
  const out = await res.json();
  if (!out.success) return;
  const data = out.data;
  const ctx = document.getElementById('ma7-chart').getContext('2d');
  const labels = data.series.map(x => formatDate(x.date));
  const ma = data.moving_avg_7d;
  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Daily Hours', data: data.series.map(x => x.hours), borderColor: '#94a3b8', tension: 0.3 },
        { label: 'MA (7d)', data: ma, borderColor: '#14b8a6', backgroundColor: 'rgba(20,184,166,0.15)', fill: true, tension: 0.3 }
      ]
    },
    options: { responsive: true, maintainAspectRatio: false }
  });
  const stats = document.getElementById('trend-stats');
  stats.innerHTML = `Avg 7d: <b>${data.avg7}h</b> • Avg 30d: <b>${data.avg30}h</b> • Decreasing streak: <b>${data.streak_decreasing_days}</b> days`;
}

// Call after existing initializers
setTimeout(loadTrends, 250);
```

---

## 4) Customizable Goals Display

### What you’ll add
- Client-side filters: status, category, priority, sort
- Optional server-side support via query params on `/api/goals`
- Grid/List toggle

### Where to add
- `templates/goals.html`: filter toolbar + JS changes
- `app.py`: enhance `/api/goals` to accept optional query params (non-breaking)

### Code

In `templates/goals.html`, add a filter bar above the goals grid:
```html
<div class="mb-4 grid grid-cols-1 md:grid-cols-5 gap-3">
  <select id="filter-status" class="border rounded px-2 py-1">
    <option value="">All Statuses</option>
    <option value="active">Active</option>
    <option value="completed">Completed</option>
    <option value="paused">Paused</option>
  </select>
  <select id="filter-category" class="border rounded px-2 py-1">
    <option value="">All Categories</option>
    <option value="mental_health">Mental Health</option>
    <option value="physical_health">Physical Health</option>
    <option value="digital_wellness">Digital Wellness</option>
    <option value="academic">Academic</option>
    <option value="social">Social</option>
    <option value="general">General</option>
  </select>
  <select id="filter-priority" class="border rounded px-2 py-1">
    <option value="">Any Priority</option>
    <option value="high">High</option>
    <option value="medium">Medium</option>
    <option value="low">Low</option>
  </select>
  <select id="sort-by" class="border rounded px-2 py-1">
    <option value="created_at_desc">Sort: Newest</option>
    <option value="created_at_asc">Oldest</option>
    <option value="priority">Priority</option>
    <option value="status">Status</option>
    <option value="target_date">Target Date</option>
  </select>
  <div class="flex items-center">
    <label class="mr-2 text-sm">List</label>
    <input type="checkbox" id="toggle-view" class="toggle-class">
    <label class="ml-2 text-sm">Grid</label>
  </div>
</div>
```

Replace `loadGoals()` in the same file with a filter-aware version:
```javascript
function loadGoals() {
  const status = document.getElementById('filter-status').value;
  const category = document.getElementById('filter-category').value;
  const priority = document.getElementById('filter-priority').value;
  const sort = document.getElementById('sort-by').value;
  const params = new URLSearchParams({ status, category, priority, sort });
  fetch('/api/goals?' + params.toString())
    .then(r => r.json())
    .then(d => d.success ? displayGoals(d.goals) : showMessage('Error loading goals', 'error'))
    .catch(() => showMessage('Error loading goals', 'error'));
}

['filter-status','filter-category','filter-priority','sort-by','toggle-view']
  .forEach(id => document.getElementById(id)?.addEventListener('change', loadGoals));
```

Make `displayGoals()` support list view:
```javascript
function displayGoals(goals) {
  const listView = document.getElementById('toggle-view').checked; // true => list
  const container = document.getElementById('goals-container');
  const emptyState = document.getElementById('empty-state');
  if (goals.length === 0) { container.innerHTML=''; emptyState.classList.remove('hidden'); return; }
  emptyState.classList.add('hidden');

  if (listView) {
    container.className = 'space-y-3';
    container.innerHTML = goals.map(goal => `
      <div class="bg-white rounded-lg shadow p-4 flex justify-between items-center">
        <div>
          <div class="font-semibold">${goal.title}</div>
          <div class="text-xs text-gray-500">${goal.category} • ${goal.priority} • ${goal.status}</div>
        </div>
        <div class="flex items-center space-x-3">
          ${goal.target_value ? `<div class="text-xs text-gray-600">${Math.round(goal.progress_percentage)}%</div>` : ''}
          <button onclick="showProgressModal(${goal.id}, ${goal.current_value}, '${goal.status}')" class="text-green-600"><i class="fas fa-chart-line"></i></button>
          <button onclick="deleteGoal(${goal.id})" class="text-red-600"><i class="fas fa-trash"></i></button>
        </div>
      </div>
    `).join('');
  } else {
    container.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6';
    // Original grid card rendering (existing code) can remain as-is
    container.innerHTML = goals.map(goal => `...original card markup...`).join('');
  }
}
```

Server: optionally extend `/api/goals` in `app.py`:
```python
@app.route('/api/goals', methods=['GET', 'POST'])
def goals_api():
    if request.method == 'GET':
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Not authorized'}), 401
        q = Goal.query.filter_by(user_id=session['user_id'])
        status = request.args.get('status')
        category = request.args.get('category')
        priority = request.args.get('priority')
        sort = request.args.get('sort', 'created_at_desc')
        if status: q = q.filter_by(status=status)
        if category: q = q.filter_by(category=category)
        if priority: q = q.filter_by(priority=priority)
        if sort == 'created_at_asc': q = q.order_by(Goal.created_at.asc())
        elif sort == 'priority': q = q.order_by(Goal.priority.desc())
        elif sort == 'status': q = q.order_by(Goal.status.asc())
        elif sort == 'target_date': q = q.order_by(Goal.target_date.asc())
        else: q = q.order_by(Goal.created_at.desc())
        goals = q.all()
        return jsonify({'success': True, 'goals': [
          {
            'id': g.id,
            'title': g.title,
            'description': g.description,
            'category': g.category,
            'target_value': g.target_value,
            'current_value': g.current_value,
            'unit': g.unit,
            'status': g.status,
            'priority': g.priority,
            'target_date': g.target_date.isoformat() if g.target_date else None,
            'created_at': g.created_at.strftime('%Y-%m-%d'),
            'progress_percentage': g.progress_percentage
          } for g in goals
        ]})
    # POST handling remains your existing implementation
```

---

## How to test

- Profile Picture Upload
  - Go to `Profile` page (`/profile`). Upload a small JPEG/PNG. Image should refresh.
- Editable Profile
  - On `Profile` page, click Edit Profile. Change `Name/Institution` and Save. Page should reload with new values.
- Digital Detox Trends
  - Open `Digital Detox` page. Ensure you have some logs. New “7-Day Moving Average” chart and stats should render.
- Customizable Goals Display
  - Open `Goals` page. Use filters and sort. Toggle list/grid view.

If any route names differ in your `app.py`, adapt the endpoints accordingly, but these snippets align with your current structure in `templates/` and `models.py`.
