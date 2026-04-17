/**
 * RRO Engineer Dashboard — JavaScript
 * ─────────────────────────────────────
 * Loads user + assigned workgroups via API and renders the dashboard dynamically.
 */

/* =========================================
   Configuration
   ========================================= */
const API_BASE = '';

/* =========================================
   State
   ========================================= */
let currentFilter = new URLSearchParams(window.location.search).get('filter') || 'all';

function getAuthHeaders(headers = {}) {
    return window.RROAuth ? window.RROAuth.getAuthHeaders(headers) : headers;
}

function withAuthUrl(path) {
    return window.RROAuth ? window.RROAuth.appendAuthToken(path) : path;
}

/* =========================================
   DOM References
   ========================================= */
const dom = {
    userAvatar: document.getElementById('userAvatar'),
    userName: document.getElementById('userName'),
    userRoleBadge: document.getElementById('userRoleBadge'),
    welcomeHeading: document.getElementById('welcomeHeading'),
    profileEmail: document.getElementById('profileEmail'),
    profileDropdown: document.getElementById('profileDropdown'),
    profileDropdownTrigger: document.getElementById('profileDropdownTrigger'),
    btnLogout: document.getElementById('btnLogout'),
    filterTabs: document.getElementById('filterTabs'),
    resultsCount: document.getElementById('resultsCount'),
    resultsPlural: document.getElementById('resultsPlural'),
    statTotal: document.getElementById('statTotal'),
    statActive: document.getElementById('statActive'),
    statCompleted: document.getElementById('statCompleted'),
    workgroupsList: document.getElementById('workgroupsList'),
    workgroupsLoading: document.getElementById('workgroupsLoading'),
    emptyState: document.getElementById('emptyState'),
    filterEmptyState: document.getElementById('filterEmptyState'),
};

/* =========================================
   API Helpers
   ========================================= */
async function apiFetch(path, options = {}) {
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            credentials: 'include',
            headers: getAuthHeaders({ 'Content-Type': 'application/json', ...options.headers }),
            ...options,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
        return await res.json();
    } catch (error) {
        console.warn(`[API] ${options.method || 'GET'} ${path} → ${error.message}`);
        return null;
    }
}

/* =========================================
   Renderers
   ========================================= */
function renderUserInfo(user) {
    if (!user) return;

    const fullName = user.fullName || user.name || 'Engineer';
    const nameParts = fullName.split(' ').filter(Boolean);
    const initials = nameParts.map((p) => p[0]).join('').slice(0, 2).toUpperCase();
    const firstName = nameParts[0] || fullName;

    dom.userAvatar.textContent = initials || '?';
    dom.userAvatar.classList.remove('loading-pulse');
    dom.userName.textContent = fullName;
    dom.userName.classList.remove('loading-text');
    dom.userRoleBadge.textContent = user.role || 'Engineer';
    dom.welcomeHeading.textContent = `Welcome, ${firstName}!`;
    dom.welcomeHeading.classList.remove('loading-text');
    if (dom.profileEmail) dom.profileEmail.textContent = user.email || '';
}

function renderStats(stats) {
    if (!stats) return;
    dom.statTotal.textContent = stats.total ?? 0;
    dom.statActive.textContent = stats.active ?? 0;
    dom.statCompleted.textContent = stats.completed ?? 0;
}

function renderWorkgroups(workgroups) {
    dom.workgroupsList.innerHTML = '';
    if (dom.workgroupsLoading) dom.workgroupsLoading.classList.add('hidden');

    const count = Array.isArray(workgroups) ? workgroups.length : 0;
    dom.resultsCount.textContent = count;
    dom.resultsPlural.textContent = count === 1 ? '' : 's';

    if (count === 0) {
        if (currentFilter === 'all') {
            dom.emptyState.classList.remove('hidden');
            if (dom.filterEmptyState) dom.filterEmptyState.classList.add('hidden');
        } else {
            dom.emptyState.classList.add('hidden');
            if (dom.filterEmptyState) dom.filterEmptyState.classList.remove('hidden');
        }
        return;
    }

    dom.emptyState.classList.add('hidden');
    if (dom.filterEmptyState) dom.filterEmptyState.classList.add('hidden');

    workgroups.forEach((wg) => {
        dom.workgroupsList.appendChild(createWorkgroupCard(wg));
    });
}

function createWorkgroupCard(wg) {
    const card = document.createElement('div');
    card.className = 'workgroup-card';

    const isCompleted = wg.is_completed === 'Completed';
    const statusClass = isCompleted ? 'status-badge--completed' : 'status-badge--active';
    const statusText = wg.is_completed;

    const nameParts = wg.name.trim().split(/\s+/);
    const initials = nameParts.map(w => w[0]).join('').substring(0, 2).toLowerCase();

    const managerName = `${wg.manager?.first_name || ''} ${wg.manager?.last_name || ''}`.trim() || 'Manager';

    const engineerCount = wg.engineers ? wg.engineers.length : 0;
    const engineerText = engineerCount === 0 ? 'No engineers assigned' : `${engineerCount} engineer${engineerCount > 1 ? 's' : ''} assigned`;

    const bugManagementHref = withAuthUrl(`/engineer/bug_management?workgroup_id=${encodeURIComponent(wg.id)}`);

    card.innerHTML = `
        <div class="wg-card-top-bar"></div>
        <div class="wg-card-header">
            <div class="wg-card-header-left">
                <span class="wg-card-initials">${escapeHtml(initials)}</span>
                <h3 class="wg-card-name">${escapeHtml(wg.name)}</h3>
            </div>
            <div class="wg-card-header-right">
                <span class="status-badge ${statusClass}">
                    <span class="status-dot"></span>${escapeHtml(statusText)}
                </span>
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
            <button class="wg-details-btn" data-wg-id="${encodeURIComponent(wg.id)}">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5.5" stroke="#64748b" stroke-width="1.1"/><path d="M7 6.5v3M7 4.5v.5" stroke="#64748b" stroke-width="1.1" stroke-linecap="round"/></svg>
                Details
            </button>
            <a href="${bugManagementHref}" class="wg-view-bugs-btn">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="2" stroke="#7c3aed" stroke-width="1.1"/><path d="M1 7s2.5-4 6-4 6 4 6 4-2.5 4-6 4-6-4-6-4z" stroke="#7c3aed" stroke-width="1.1"/></svg>
                View Bugs
            </a>
        </div>
    `;

    // Attach Details button listener after innerHTML is set
    card.querySelector('.wg-details-btn').addEventListener('click', () => openDetailsModal(wg));

    return card;
}

function updateFilterUI(filter) {
    const buttons = dom.filterTabs.querySelectorAll('button.tab[data-filter]');
    buttons.forEach((btn) => {
        if (btn.dataset.filter === filter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

function escapeHtml(str) {
    return String(str || '').replace(/[&<>"]+/g, (match) => {
        const esc = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
        };
        return esc[match] || match;
    });
}

/* =========================================
   Data Loaders
   ========================================= */

async function loadCurrentUser() {
    const data = await apiFetch('/api/auth/me');
    if (data) {
        renderUserInfo(data);
    }
}

async function loadStats() {
    const data = await apiFetch('/api/engineer/stats');
    if (data) {
        renderStats(data);
    }
}

async function loadWorkgroups(filter = 'all') {
    updateFilterUI(filter);
    currentFilter = filter;

    const data = await apiFetch(`/api/engineer/workgroups?filter=${encodeURIComponent(filter)}`);
    if (Array.isArray(data)) {
        renderWorkgroups(data);
    } else {
        renderWorkgroups([]);
    }
}

/* =========================================
   Event Handlers
   ========================================= */

function handleFilterClick(event) {
    const el = event.target.closest('button.tab[data-filter]');
    if (!el) return;
    event.preventDefault();
    const filter = el.dataset.filter;
    if (!filter) return;
    const url = new URL(window.location.href);
    url.searchParams.set('filter', filter);
    window.history.replaceState({}, '', url);
    loadWorkgroups(filter);
}

/* =========================================
   Initialize
   ========================================= */

function init() {
    dom.filterTabs.addEventListener('click', handleFilterClick);

    // Details modal close handlers
    const overlay = document.getElementById('wgDetailsOverlay');
    if (overlay) {
        document.getElementById('wgDetailsClose')?.addEventListener('click', closeDetailsModal);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) closeDetailsModal(); });
        document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDetailsModal(); });
    }

    // Profile dropdown toggle
    if (dom.profileDropdownTrigger && dom.profileDropdown) {
        dom.profileDropdownTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            dom.profileDropdown.classList.toggle('hidden');
        });
        document.addEventListener('click', () => {
            dom.profileDropdown.classList.add('hidden');
        });
    }

    if (dom.btnLogout) {
        dom.btnLogout.addEventListener('click', async () => {
            await apiFetch('/api/auth/logout', { method: 'POST' });
            if (window.RROAuth) window.RROAuth.clearToken();
            window.location.href = '/';
        });
    }

    loadCurrentUser();
    loadStats();
    loadWorkgroups(currentFilter);
}

/* =========================================
   Workgroup Details Modal
   ========================================= */
function openDetailsModal(wg) {
    const overlay = document.getElementById('wgDetailsOverlay');
    if (!overlay) return;

    const isCompleted = wg.is_completed === 'Completed';
    const statusClass = isCompleted ? 'status-badge--completed' : 'status-badge--active';
    const managerName = `${wg.manager?.first_name || ''} ${wg.manager?.last_name || ''}`.trim() || 'Manager';

    // Engineers list
    const engineers = Array.isArray(wg.engineers) && wg.engineers.length > 0
        ? wg.engineers.map(e => {
            const name = `${e.first_name || ''} ${e.last_name || ''}`.trim() || e.email || 'Unknown';
            const initials = name.split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase();
            return `
                <div class="wg-detail-engineer-item">
                    <span class="wg-detail-engineer-avatar">${escapeHtml(initials)}</span>
                    <span class="wg-detail-engineer-name">${escapeHtml(name)}</span>
                </div>`;
          }).join('')
        : '<p class="wg-detail-no-engineers">No engineers assigned.</p>';

    document.getElementById('wgDetailName').textContent = wg.name || 'N/A';
    document.getElementById('wgDetailStatus').className = `status-badge ${statusClass}`;
    document.getElementById('wgDetailStatus').innerHTML =
        `<span class="status-dot"></span>${escapeHtml(wg.is_completed)}`;
    document.getElementById('wgDetailVersion').textContent = wg.release_version || 'N/A';
    document.getElementById('wgDetailManager').textContent = managerName;
    document.getElementById('wgDetailEngineers').innerHTML = engineers;

    overlay.classList.add('open');
}

function closeDetailsModal() {
    const overlay = document.getElementById('wgDetailsOverlay');
    if (overlay) overlay.classList.remove('open');
}

window.addEventListener('DOMContentLoaded', init);

/* =========================================
   Feature: Dynamic Search & Autocomplete
   ========================================= */
(function () {
    const searchInput = document.getElementById('workgroupSearch');
    const workgroupsList = document.getElementById('workgroupsList');
    const suggestionsBox = document.getElementById('searchSuggestions');
    const resultsCount = document.getElementById('resultsCount');
    const resultsPlural = document.getElementById('resultsPlural');

    if (!searchInput || !workgroupsList || !suggestionsBox) return;

    function getWorkgroupNames() {
        return Array.from(workgroupsList.children).map(card => {
            const h3 = card.querySelector('h3');
            return h3 ? h3.textContent : '';
        }).filter(Boolean);
    }

    function filterCards(query) {
        const cards = workgroupsList.children;
        let visibleCount = 0;
        const lowerQuery = query.toLowerCase().trim();

        for (const card of cards) {
            const title = card.querySelector('h3').textContent.toLowerCase();
            if (title.includes(lowerQuery)) {
                card.classList.remove('hidden');
                visibleCount++;
            } else {
                card.classList.add('hidden');
            }
        }

        if (resultsCount) resultsCount.textContent = visibleCount;
        if (resultsPlural) resultsPlural.textContent = visibleCount === 1 ? '' : 's';
    }

    function showSuggestions(query) {
        const names = getWorkgroupNames();
        const lowerQuery = query.toLowerCase().trim();

        if (!lowerQuery) {
            suggestionsBox.innerHTML = '';
            suggestionsBox.classList.add('hidden');
            return;
        }

        const matches = names.filter(name => name.toLowerCase().includes(lowerQuery));

        if (matches.length > 0) {
            suggestionsBox.innerHTML = matches.map(name => `
                <div class="search-suggestion-item">
                    ${escapeHtml(name)}
                </div>
            `).join('');
            suggestionsBox.classList.remove('hidden');
        } else {
            suggestionsBox.innerHTML = '';
            suggestionsBox.classList.add('hidden');
        }
    }

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value;
        filterCards(query);
        showSuggestions(query);
    });

    suggestionsBox.addEventListener('click', (e) => {
        const item = e.target.closest('div');
        if (!item) return;

        const selectedName = item.textContent.trim();
        searchInput.value = selectedName;
        suggestionsBox.classList.add('hidden');
        filterCards(selectedName);
    });

    // Close suggestions on blur or outside click
    document.addEventListener('click', (e) => {
        if (!searchInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
            suggestionsBox.classList.add('hidden');
        }
    });

    // MutationObserver to fix search when tabs change
    const observer = new MutationObserver(() => {
        filterCards(searchInput.value);
    });
    observer.observe(workgroupsList, { childList: true });
})();

