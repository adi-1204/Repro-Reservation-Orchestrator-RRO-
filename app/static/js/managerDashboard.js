/**
 * RRO Manager Dashboard — JavaScript
 * ─────────────────────────────────────
 * Handles dynamic data loading, modal interactions, and workgroup management.
 * All data is fetched from / sent to backend APIs.
 * Falls back to local mock data when the backend is unavailable, so the
 * page works standalone for development and demo purposes.
 *
 * ┌──────────────────────────────────────────────────────────────────┐
 * │  API ENDPOINTS USED (configure API_BASE below)                  │
 * │                                                                  │
 * │  GET    /api/auth/me         → current logged-in user            │
 * │  GET    /api/stats           → dashboard stat counts             │
 * │  GET    /api/workgroups      → list manager's workgroups         │
 * │  POST   /api/workgroups      → create a new workgroup            │
 * │  PATCH  /api/workgroups/:id  → update a workgroup                │
 * │  DELETE /api/workgroups/:id  → delete a workgroup                │
 * │  GET    /api/engineers       → list registered engineers         │
 * └──────────────────────────────────────────────────────────────────┘
 */

/* =========================================
   Configuration — CHANGE THIS TO YOUR BACKEND URL
   ========================================= */
const API_BASE = ''; // Change this to your backend URL

/* =========================================
   State
   ========================================= */
let currentUser = null;
let workgroups = [];
let engineers = [];
let currentFilter = 'all';
let currentWorkgroupId = null;

function getAuthHeaders(headers = {}) {
    return window.RROAuth ? window.RROAuth.getAuthHeaders(headers) : headers;
}

function withAuthUrl(path) {
    return window.RROAuth ? window.RROAuth.appendAuthToken(path) : path;
}

/* =========================================
   DOM References
   ========================================= */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
    userName: $('#userName'),
    userAvatar: $('#userAvatar'),
    userRoleBadge: $('#userRoleBadge'),
    welcomeHeading: $('#welcomeHeading'),
    statTotal: $('#statTotal'),
    statActive: $('#statActive'),
    statCompleted: $('#statCompleted'),
    statEngineers: $('#statEngineers'),
    workgroupsList: $('#workgroupsList'),
    workgroupsLoading: $('#workgroupsLoading'),
    emptyState: $('#emptyState'),
    filterTabs: $('#filterTabs'),
    modalOverlay: $('#modalOverlay'),
    modalClose: $('#modalClose'),
    btnCancel: $('#btnCancel'),
    btnCreateWorkgroupTop: $('#btnCreateWorkgroupTop'),
    btnCreateWorkgroupBottom: $('#btnCreateWorkgroupBottom'),
    createWorkgroupForm: $('#createWorkgroupForm'),
    btnSubmit: $('#createWorkgroupForm .btn-submit'),
    workgroupId: $('#workgroupId'),
    workgroupName: $('#workgroupName'),
    releaseVersion: $('#releaseVersion'),
    markCompleted: $('#markCompleted'),
    engineersEmpty: $('#engineersEmpty'),
    engineersList: $('#engineersList'),
    profileDropdownTrigger: $('#profileDropdownTrigger'),
    profileDropdown: $('#profileDropdown'),
    profileEmail: $('#profileEmail'),
    btnLogout: $('#btnLogout'),
};

/* =========================================
   API Helper
   ========================================= */

/**
 * Generic fetch wrapper. Returns parsed JSON on success, null on failure.
 * Always logs errors to console for debugging.
 */
async function apiFetch(path, options = {}) {
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            headers: getAuthHeaders({ 'Content-Type': 'application/json', ...options.headers }),
            credentials: 'include',
            ...options,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
        return await res.json();
    } catch (err) {
        console.warn(`[API] ${options.method || 'GET'} ${path} → ${err.message}`);
        return null;
    }
}

/**
 * Fetch helper that preserves status code and backend error text.
 * Used by form mutations that need strict conflict handling.
 */
async function apiFetchDetailed(path, options = {}) {
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            headers: getAuthHeaders({ 'Content-Type': 'application/json', ...options.headers }),
            credentials: 'include',
            ...options,
        });

        let body = null;
        try {
            body = await res.json();
        } catch (parseErr) {
            body = null;
        }

        if (!res.ok) {
            return {
                ok: false,
                status: res.status,
                error: body && body.error ? body.error : `HTTP ${res.status} ${res.statusText}`,
            };
        }

        return { ok: true, status: res.status, data: body };
    } catch (err) {
        console.warn(`[API] ${options.method || 'GET'} ${path} → ${err.message}`);
        return { ok: false, status: 0, error: 'Unable to reach server. Please try again.' };
    }
}

/* =========================================
   Mock / Fallback Data
   (used when backend is not running)
   ========================================= */

function getMockUser() {
    return { id: 1, name: 'Rishi', fullName: 'Rishi N', email: 'rishi@rro.com', role: 'Manager' };
}

function computeLocalStats() {
    return {
        total: workgroups.length,
        active: workgroups.filter(w => !w.is_completed).length,
        completed: workgroups.filter(w => w.is_completed).length,
        engineers: engineers.length,
    };
}

/* =========================================
   Data Loaders — fetch from API, fallback to mock
   ========================================= */

/** GET /api/auth/me → populate user info in navbar + welcome heading */
async function loadCurrentUser() {
    const data = await apiFetch('/api/auth/me');
    currentUser = data || getMockUser();
    renderUserInfo();
}

/** GET /api/stats → populate the 4 stat cards */
async function loadStats() {
    const data = await apiFetch('/api/stats');
    if (data) renderStats(data);
    else renderStats(computeLocalStats());
}

/** GET /api/workgroups → populate workgroup cards */
async function loadWorkgroups(skipApiIfLocal = false) {
    dom.workgroupsLoading.classList.remove('hidden');
    dom.emptyState.classList.add('hidden');
    // Don't blank the UI if we're just refreshing local state
    if (!skipApiIfLocal) dom.workgroupsList.innerHTML = '';

    const data = await apiFetch('/api/workgroups');
    console.log('Workgroups loaded:', data);
    if (data && Array.isArray(data)) {
        workgroups = data;
    }

    dom.workgroupsLoading.classList.add('hidden');
    renderWorkgroups();
}

/** GET /api/engineers → populate engineer checkboxes in Create modal */
async function loadEngineers() {
    const data = await apiFetch('/api/engineers');
    if (data && Array.isArray(data)) {
        engineers = data;
    }
    renderEngineers();
}

/** Refresh all dynamic data (called after mutations) */
async function refreshAll() {
    await Promise.all([loadStats(), loadWorkgroups(), loadEngineers()]);
}

/* =========================================
   Renderers
   ========================================= */

function renderUserInfo() {
    if (!currentUser) return;

    // Remove loading states
    dom.userAvatar.classList.remove('loading-pulse');
    dom.userName.classList.remove('loading-text');

    const initials = currentUser.fullName
        ? currentUser.fullName.split(' ').map(n => n[0]).join('').toUpperCase()
        : currentUser.name[0].toUpperCase();

    dom.userAvatar.textContent = initials;
    dom.userName.textContent = currentUser.fullName || currentUser.name;
    dom.userRoleBadge.textContent = currentUser.role || 'Manager';
    dom.profileEmail.textContent = currentUser.email || 'manager@rro.com';
    dom.welcomeHeading.classList.remove('loading-text');
    dom.welcomeHeading.textContent = `Welcome back, ${currentUser.name}!`;
}

function renderStats(stats) {
    animateNumber(dom.statTotal, stats.total);
    animateNumber(dom.statActive, stats.active);
    animateNumber(dom.statCompleted, stats.completed);
    animateNumber(dom.statEngineers, stats.engineers);
}

function animateNumber(el, target) {
    const duration = 500;
    const current = el.textContent;
    const start = (current === '—' || current === '') ? 0 : parseInt(current) || 0;
    if (start === target) { el.textContent = target; return; }
    const startTime = performance.now();
    function tick(now) {
        const progress = Math.min((now - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(start + (target - start) * eased);
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

function renderWorkgroups() {
    const filtered = filterWorkgroups(workgroups, currentFilter);
    dom.workgroupsList.innerHTML = '';

    // Update the workgroups count in the title
    const titleEl = document.querySelector('.workgroups-title');
    if (titleEl) {
        titleEl.textContent = `My Workgroups (${workgroups.length})`;
    }

    if (workgroups.length === 0) {
        dom.emptyState.classList.remove('hidden');
        const bottomAction = document.querySelector('.workgroups-bottom-action');
        if (bottomAction) bottomAction.style.display = '';
        return;
    }

    dom.emptyState.classList.add('hidden');
    const bottomAction = document.querySelector('.workgroups-bottom-action');
    if (bottomAction) bottomAction.style.display = 'none';

    const filterEmpty = document.getElementById('filterEmptyState');
    if (filtered.length === 0) {
        if (filterEmpty) filterEmpty.classList.remove('hidden');
        return;
    }
    if (filterEmpty) filterEmpty.classList.add('hidden');

    filtered.forEach(wg => {
        const card = document.createElement('div');
        card.className = 'workgroup-card';
        card.dataset.id = wg.id;

        const statusClass = wg.is_completed ? 'status-badge--completed' : 'status-badge--active';
        const statusDot = wg.is_completed ? '#16a34a' : '#7c3aed';
        const statusText = wg.is_completed ? 'Completed' : 'Active';

        // Build initials from workgroup name (first letter of first two words)
        const nameParts = wg.name.trim().split(/\s+/);
        const initials = nameParts.map(w => w[0]).join('').substring(0, 2).toLowerCase();

        // Format the creation date
        const createdDate = wg.created_at ? new Date(wg.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'N/A';

        // Engineer count
        const engineerCount = wg.engineers ? wg.engineers.length : 0;
        const engineerText = engineerCount === 0 ? 'No engineers assigned' : `${engineerCount} engineer${engineerCount > 1 ? 's' : ''} assigned`;

        // Manager name
        const managerName = currentUser ? (currentUser.fullName || currentUser.name) : 'Manager';

        card.innerHTML = `
      <div class="wg-card-top-bar"></div>
      <div class="wg-card-header">
        <div class="wg-card-header-left">
          <span class="wg-card-initials">${escapeHtml(initials)}</span>
          <h4 class="wg-card-name">${escapeHtml(wg.name)}</h4>
        </div>
        <div class="wg-card-header-right">
          <span class="status-badge ${statusClass}">
            <span class="status-dot" style="background:${statusDot}"></span>${statusText}
          </span>
          <button class="wg-card-menu-btn" data-id="${wg.id}" aria-label="More options">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="3" r="1.2" fill="#64748b"/>
              <circle cx="8" cy="8" r="1.2" fill="#64748b"/>
              <circle cx="8" cy="13" r="1.2" fill="#64748b"/>
            </svg>
          </button>
          <div class="wg-card-dropdown hidden" data-dropdown-id="${wg.id}">
            <button class="wg-dropdown-item" data-action="view" data-id="${wg.id}">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="2" stroke="#334155" stroke-width="1.2"/><path d="M1 8s3-5 7-5 7 5 7 5-3 5-7 5-7-5-7-5z" stroke="#334155" stroke-width="1.2"/></svg>
              View Bugs
            </button>
            <button class="wg-dropdown-item" data-action="edit" data-id="${wg.id}">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M11.5 1.5l3 3L5 14H2v-3L11.5 1.5z" stroke="#334155" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Edit Workgroup
            </button>
            <button class="wg-dropdown-item ${wg.is_completed ? 'wg-dropdown-item--amber' : 'wg-dropdown-item--green'}" data-action="markdone" data-id="${wg.id}">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke="${wg.is_completed ? '#f59e0b' : '#16a34a'}" stroke-width="1.2"/><path d="M5.5 8l2 2 3.5-4" stroke="${wg.is_completed ? '#f59e0b' : '#16a34a'}" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
              ${wg.is_completed ? 'Mark as Active' : 'Mark as Done'}
            </button>
            <button class="wg-dropdown-item wg-dropdown-item--red" data-action="delete" data-id="${wg.id}">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 4h12M5 4V3a1 1 0 011-1h4a1 1 0 011 1v1M6 7v5M10 7v5" stroke="#dc2626" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/><path d="M3 4l1 9a1 1 0 001 1h6a1 1 0 001-1l1-9" stroke="#dc2626" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
              Delete
            </button>
          </div>
        </div>
      </div>
      <div class="wg-card-manager">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="5" r="2.5" stroke="#94a3b8" stroke-width="1.1"/><path d="M2 13c0-2.8 2.2-5 5-5s5 2.2 5 5" stroke="#94a3b8" stroke-width="1.1" stroke-linecap="round"/></svg>
        ${escapeHtml(managerName)}
      </div>
      <div class="wg-card-release">
        <span class="wg-release-badge">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1l1.5 3h3.5l-2.5 2.5.8 3.5L7 8.5 3.7 10l.8-3.5L2 4h3.5L7 1z" stroke="#7c3aed" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/></svg>
          Release
        </span>
        <span class="wg-release-version">${escapeHtml(wg.release_version || 'N/A')}</span>
      </div>
      <div class="wg-card-engineers">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="5" cy="5" r="2" stroke="#94a3b8" stroke-width="1.1"/><path d="M1 13c0-2.2 1.8-4 4-4" stroke="#94a3b8" stroke-width="1.1" stroke-linecap="round"/><circle cx="9.5" cy="5.5" r="1.5" stroke="#94a3b8" stroke-width="1.1"/><path d="M13 13c0-1.7-1.3-3-3-3" stroke="#94a3b8" stroke-width="1.1" stroke-linecap="round"/></svg>
        ${escapeHtml(engineerText)}
      </div>
      <div class="wg-card-footer">
        <span class="wg-card-date">${createdDate}</span>
        <button class="wg-view-bugs-btn" data-id="${wg.id}">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="2" stroke="#7c3aed" stroke-width="1.1"/><path d="M1 7s2.5-4 6-4 6 4 6 4-2.5 4-6 4-6-4-6-4z" stroke="#7c3aed" stroke-width="1.1"/></svg>
          View Bugs
        </button>
      </div>
    `;
        dom.workgroupsList.appendChild(card);
    });

    // Attach event listeners for 3-dot menus
    attachCardMenuListeners();
}

function filterWorkgroups(list, filter) {
    if (filter === 'active') return list.filter(w => !w.is_completed);
    if (filter === 'completed') return list.filter(w => w.is_completed);
    return list;
}

/* =========================================
   Workgroup Card Menu (3-dot dropdown)
   ========================================= */

function attachCardMenuListeners() {
    // 3-dot menu buttons
    document.querySelectorAll('.wg-card-menu-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = btn.dataset.id;
            closeAllDropdowns();
            const dropdown = document.querySelector(`.wg-card-dropdown[data-dropdown-id="${id}"]`);
            if (dropdown) dropdown.classList.toggle('hidden');
        });
    });

    // Dropdown items
    document.querySelectorAll('.wg-dropdown-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            const action = item.dataset.action;
            const id = parseInt(item.dataset.id);
            closeAllDropdowns();

            if (action === 'delete') handleDeleteWorkgroup(id);
            else if (action === 'markdone') handleMarkDone(id);
            else if (action === 'edit') handleEditWorkgroup(id);
            else if (action === 'view') openWorkgroupDashboard(id);
        });
    });

    // View Bugs buttons at bottom of card
    document.querySelectorAll('.wg-view-bugs-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = parseInt(btn.dataset.id);
            openWorkgroupDashboard(id);
        });
    });
}

function closeAllDropdowns() {
    document.querySelectorAll('.wg-card-dropdown').forEach(d => d.classList.add('hidden'));
    dom.profileDropdown.classList.add('hidden');
}

function resetWorkgroupStatsUI() {
    document.querySelectorAll('.stat-count, .bug-count, .stats-number').forEach(el => {
        el.textContent = '0';
    });
}

function openWorkgroupDashboard(id) {
    currentWorkgroupId = id;
    resetWorkgroupStatsUI();
    window.location.href = withAuthUrl(`/bug_management?workgroup_id=${id}`);
}

// Close dropdowns on outside click
document.addEventListener('click', () => closeAllDropdowns());

/* =========================================
   Delete Workgroup — DELETE /api/workgroups/:id
   ========================================= */

async function handleDeleteWorkgroup(id) {
    if (!confirm('Are you sure you want to delete this workgroup? This cannot be undone.')) return;

    // Call backend API
    const result = await apiFetch(`/api/workgroups/${id}`, { method: 'DELETE' });

    // Remove from local state regardless (also works offline)
    workgroups = workgroups.filter(w => w.id !== id);

    renderWorkgroups();
    renderStats(computeLocalStats());
    if (result) loadStats(); // Only refresh from backend if backend is up
}

/* =========================================
   Mark as Done — PATCH /api/workgroups/:id
   ========================================= */

async function handleMarkDone(id) {
    const wg = workgroups.find(w => w.id === id);
    if (!wg) return;

    const newStatus = !wg.is_completed;

    // Call backend API
    const result = await apiFetch(`/api/workgroups/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_completed: newStatus }),
    });
    // Update local state
    wg.is_completed = newStatus;

    renderWorkgroups();
    renderStats(computeLocalStats());
    if (result) loadStats();
}

/* =========================================
   Edit Workgroup — opens modal and populates form
   ========================================= */

function handleEditWorkgroup(id) {
    const wg = workgroups.find(w => w.id === id);
    if (!wg) return;

    // Change modal texts for Edit mode
    document.querySelector('.modal-title').textContent = 'Edit Workgroup';
    document.querySelector('.modal-subtitle').textContent = 'Update details for this workgroup';
    dom.btnSubmit.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2l2 4h4l-3 3 1 4-4-2-4 2 1-4-3-3h4l2-4z" stroke="#fff" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        Save Changes
    `;

    // Populate form payload
    dom.workgroupId.value = wg.id;
    dom.workgroupName.value = wg.name;
    dom.releaseVersion.value = wg.release_version || '';
    dom.markCompleted.checked = !!wg.is_completed;

    // Check previously assigned engineers
    const assignedIds = wg.engineers ? wg.engineers.map(e => e.id.toString()) : [];
    Array.from($$('#engineersList input')).forEach(cb => {
        cb.checked = assignedIds.includes(cb.value);
    });

    dom.modalOverlay.classList.add('open');
    document.body.style.overflow = 'hidden';
    updateStepIndicators();
}

/* =========================================
   Modal Helpers
   ========================================= */

function openModal() {
    // Set texts for Create mode
    document.querySelector('.modal-title').textContent = 'Create Workgroup';
    document.querySelector('.modal-subtitle').textContent = 'Set up a new workgroup for your team';
    dom.btnSubmit.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M8 2l2 4h4l-3 3 1 4-4-2-4 2 1-4-3-3h4l2-4z" stroke="#fff" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        Done — Create Workgroup
    `;

    dom.modalOverlay.classList.add('open');
    resetForm();
    document.body.style.overflow = 'hidden';
    dom.workgroupName.focus();
}

function closeModal() {
    dom.modalOverlay.classList.remove('open');
    document.body.style.overflow = '';
}

function resetForm() {
    dom.createWorkgroupForm.reset();
    dom.workgroupId.value = '';
    dom.markCompleted.checked = false;
    $$('.step').forEach(s => s.classList.remove('active'));
    document.querySelector('.step[data-step="1"]').classList.add('active');

    // Reset filled classes
    $$('.form-label.filled').forEach(l => l.classList.remove('filled'));
}

/* =========================================
   Create / Edit Workgroup — POST/PATCH /api/workgroups
   ========================================= */

async function handleCreateWorkgroup(e) {
    e.preventDefault();

    const editId = dom.workgroupId.value;
    const name = dom.workgroupName.value.trim();
    const releaseVersion = dom.releaseVersion.value.trim();
    const isCompleted = dom.markCompleted.checked;

    // Clear previous errors
    const errorBanner = document.getElementById('formErrorBanner');
    const errorText = document.getElementById('formErrorText');
    dom.workgroupName.classList.remove('input-error');
    dom.releaseVersion.classList.remove('input-error');

    // Validate required fields
    if (!name) {
        errorText.textContent = 'Please enter a workgroup name.';
        errorBanner.classList.remove('hidden');
        dom.workgroupName.classList.add('input-error');
        dom.workgroupName.focus();
        return;
    }
    if (!releaseVersion) {
        errorText.textContent = 'Please enter a release version.';
        errorBanner.classList.remove('hidden');
        dom.releaseVersion.classList.add('input-error');
        dom.releaseVersion.focus();
        return;
    }

    errorBanner.classList.add('hidden');

    const selectedEngineers = Array.from($$('#engineersList input:checked')).map(cb => parseInt(cb.value));

    const payload = {
        name,
        release_version: releaseVersion,
        is_completed: isCompleted,
        engineer_ids: selectedEngineers,
    };

    let resultData = null;

    const showMutationError = (message) => {
        errorText.textContent = message;
        errorBanner.classList.remove('hidden');
    };

    if (editId) {
        // Edit mode (PATCH)
        const result = await apiFetchDetailed(`/api/workgroups/${editId}`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
        });

        if (result.ok) {
            resultData = result.data;
            const index = workgroups.findIndex(w => w.id === parseInt(editId));
            if (index !== -1) workgroups[index] = result.data;
        } else {
            showMutationError(result.error || 'Unable to update workgroup.');
            if ((result.status === 409 || result.status === 400) && /name/i.test(result.error || '')) {
                dom.workgroupName.classList.add('input-error');
                dom.workgroupName.focus();
            }
            return;
        }
    } else {
        // Create mode (POST)
        const result = await apiFetchDetailed('/api/workgroups', {
            method: 'POST',
            body: JSON.stringify(payload),
        });

        if (result.ok) {
            resultData = result.data;
            workgroups.push(result.data);
        } else {
            showMutationError(result.error || 'Unable to create workgroup.');
            if ((result.status === 409 || result.status === 400) && /name/i.test(result.error || '')) {
                dom.workgroupName.classList.add('input-error');
                dom.workgroupName.focus();
            }
            return;
        }
    }

    closeModal();
    renderWorkgroups();
    renderStats(computeLocalStats());
    if (resultData) loadStats();
}

/* =========================================
   Create Workgroup — POST /api/workgroups
   ========================================= */

function updateStepIndicators() {
    const hasName = dom.workgroupName.value.trim().length > 0;
    const hasRelease = dom.releaseVersion.value.trim().length > 0;
    const hasEngineers = document.querySelectorAll('#engineersList input:checked').length > 0;
    const steps = $$('.step');

    steps[0].classList.toggle('active', hasName);
    steps[1].classList.toggle('active', hasRelease);
    steps[2].classList.toggle('active', hasEngineers);

    // Toggle filled state for input label icons
    const nameLabel = dom.workgroupName.previousElementSibling;
    if (nameLabel && nameLabel.classList.contains('form-label')) {
        nameLabel.classList.toggle('filled', hasName);
    }

    const releaseLabel = dom.releaseVersion.previousElementSibling;
    if (releaseLabel && releaseLabel.classList.contains('form-label')) {
        releaseLabel.classList.toggle('filled', hasRelease);
    }

    // Toggle filled state for engineers label icon
    const engineersLabel = document.querySelector('.form-label--engineers');
    if (engineersLabel) {
        engineersLabel.classList.toggle('filled', hasEngineers);
    }
}

/* =========================================
   Utilities
   ========================================= */

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function renderEngineers() {
    const searchBox = document.getElementById('engineersSearch');
    if (engineers.length === 0) {
        dom.engineersEmpty.style.display = '';
        dom.engineersList.style.display = 'none';
        if (searchBox) searchBox.style.display = 'none';
        return;
    }
    dom.engineersEmpty.style.display = 'none';
    dom.engineersList.style.display = '';
    if (searchBox) searchBox.style.display = '';
    dom.engineersList.innerHTML = engineers.map(eng => `
    <div class="engineer-item" data-name="${escapeHtml(eng.name.toLowerCase())}" data-email="${escapeHtml(eng.email.toLowerCase())}">
      <input type="checkbox" id="eng-${eng.id}" value="${eng.id}" />
      <label for="eng-${eng.id}">${escapeHtml(eng.name)} — ${escapeHtml(eng.email)}</label>
    </div>
  `).join('');

    // Reset search input
    const searchInput = document.getElementById('engineerSearchInput');
    if (searchInput) searchInput.value = '';
}

function filterEngineersSearch(query) {
    const items = document.querySelectorAll('#engineersList .engineer-item');
    const q = query.toLowerCase().trim();
    let visibleCount = 0;
    items.forEach(item => {
        const name = item.dataset.name || '';
        const email = item.dataset.email || '';
        const matches = !q || name.includes(q) || email.includes(q);
        item.style.display = matches ? '' : 'none';
        if (matches) visibleCount++;
    });
    // Show a "no results" message if nothing matches
    let noResult = document.getElementById('engineerSearchNoResult');
    if (visibleCount === 0 && q) {
        if (!noResult) {
            noResult = document.createElement('p');
            noResult.id = 'engineerSearchNoResult';
            noResult.className = 'engineer-search-no-result';
            noResult.textContent = 'No engineers match your search.';
            dom.engineersList.appendChild(noResult);
        }
        noResult.style.display = '';
    } else if (noResult) {
        noResult.style.display = 'none';
    }
}

/* =========================================
   Event Listeners
   ========================================= */

function initEventListeners() {
    // Open modal
    dom.btnCreateWorkgroupTop.addEventListener('click', openModal);
    dom.btnCreateWorkgroupBottom.addEventListener('click', openModal);

    // Profile Dropdown
    dom.profileDropdownTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        closeAllDropdowns();
        dom.profileDropdown.classList.toggle('hidden');
    });

    // Logout
    dom.btnLogout.addEventListener('click', async () => {
        await apiFetch('/api/auth/logout', { method: 'POST', credentials: "include"});
        if (window.RROAuth) window.RROAuth.clearToken();
        window.location.href = "/";
    });

    // Close modal
    dom.modalClose.addEventListener('click', closeModal);
    dom.btnCancel.addEventListener('click', closeModal);
    dom.modalOverlay.addEventListener('click', (e) => {
        if (e.target === dom.modalOverlay) closeModal();
    });

    // ESC to close
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && dom.modalOverlay.classList.contains('open')) closeModal();
    });

    // Form submit
    dom.createWorkgroupForm.addEventListener('submit', handleCreateWorkgroup);

    // Step indicator live update + clear validation errors on input
    dom.workgroupName.addEventListener('input', () => {
        updateStepIndicators();
        dom.workgroupName.classList.remove('input-error');
        const banner = document.getElementById('formErrorBanner');
        if (banner) banner.classList.add('hidden');
    });
    dom.releaseVersion.addEventListener('input', () => {
        updateStepIndicators();
        dom.releaseVersion.classList.remove('input-error');
        const banner = document.getElementById('formErrorBanner');
        if (banner) banner.classList.add('hidden');
    });

    // Filter tabs
    dom.filterTabs.addEventListener('click', (e) => {
        if (!e.target.classList.contains('tab')) return;
        $$('.tab').forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        currentFilter = e.target.dataset.filter;
        renderWorkgroups();
    });
    
    // Update step indicators when engineers are checked/unchecked
    dom.engineersList.addEventListener('change', (e) => {
        if (e.target.type === 'checkbox') {
            updateStepIndicators();
        }
    });

    // Engineer search — dynamic filtering
    const engineerSearchInput = document.getElementById('engineerSearchInput');
    if (engineerSearchInput) {
        engineerSearchInput.addEventListener('input', (e) => {
            filterEngineersSearch(e.target.value);
        });
    }
}

/* =========================================
   Init — runs on page load
   ========================================= */

async function init() {
    initEventListeners();
    await loadCurrentUser();
    await Promise.all([loadStats(), loadWorkgroups(), loadEngineers()]);
}

document.addEventListener('DOMContentLoaded', init);
