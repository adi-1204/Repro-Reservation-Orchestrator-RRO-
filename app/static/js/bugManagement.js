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
let bugOwnershipFilter = 'workgroup';
let activeWorkgroupId = null;

function getAuthHeaders(headers = {}) {
    return window.RROAuth ? window.RROAuth.getAuthHeaders(headers) : headers;
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
    profileDropdownTrigger: $('#profileDropdownTrigger'),
    profileDropdown: $('#profileDropdown'),
    profileEmail: $('#profileEmail'),
    btnLogout: $('#btnLogout'),
    statTotalBugs: $('#statTotalBugs'),
    statReproBugs: $('#statReproBugs'),
    statTestBugs: $('#statTestBugs'),
    statPendingActions: $('#statPendingActions'),
    reproBugsCount: $('#reproBugsCount'),
    testBugsCount: $('#testBugsCount'),
    reproBugsBody: $('#reproBugsBody'),
    testBugsBody: $('#testBugsBody'),
    searchInput: $('#searchInput'),
    searchDropdown: $('#searchDropdown'),
    ownershipFilter: $('#ownershipFilter'),
    filterWorkgroupBugs: $('#filterWorkgroupBugs'),
    filterMyBugs: $('#filterMyBugs')
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


/* ── Store original bug data for search filtering ── */
let allReproBugs = [];
let allTestBugs = [];

function getCurrentWorkgroupId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('workgroup_id');
}

function shouldShowEngineerOwnershipFilter() {
    return currentUser?.role === 'Engineer' && !!activeWorkgroupId;
}

function buildBugQueryParams(extraParams = {}) {
    const params = new URLSearchParams();

    if (activeWorkgroupId) {
        params.set('workgroup_id', activeWorkgroupId);
    }

    if (shouldShowEngineerOwnershipFilter() && bugOwnershipFilter === 'mine') {
        params.set('my_only', 'true');
    }

    Object.entries(extraParams).forEach(([key, value]) => {
        if (value !== null && value !== undefined && value !== '') {
            params.set(key, String(value));
        }
    });

    return params;
}

function updateOwnershipFilterUi() {
    if (!dom.ownershipFilter || !dom.filterWorkgroupBugs || !dom.filterMyBugs) return;

    const showFilter = shouldShowEngineerOwnershipFilter();
    dom.ownershipFilter.classList.toggle('hidden', !showFilter);

    dom.filterWorkgroupBugs.classList.toggle('active', bugOwnershipFilter === 'workgroup');
    dom.filterMyBugs.classList.toggle('active', bugOwnershipFilter === 'mine');
}

async function setBugOwnershipFilter(nextFilter) {
    if (bugOwnershipFilter === nextFilter) return;

    bugOwnershipFilter = nextFilter;
    updateOwnershipFilterUi();

    if (dom.searchInput) dom.searchInput.value = '';
    if (dom.searchDropdown) dom.searchDropdown.classList.add('hidden');

    await loadBugsData();
}

async function loadBugsData() {
    const params = buildBugQueryParams();
    const qs = params.toString();
    const apiPath = qs ? `/api/bugs?${qs}` : '/api/bugs';
    const statsPath = qs ? `/api/bugs/stats?${qs}` : '/api/bugs/stats';

    console.log('Loading bugs from:', apiPath);
    const data = await apiFetch(apiPath);
    console.log('Bugs data received:', data);

    const stats = await apiFetch(statsPath);
    console.log('Stats data received:', stats);

    if (stats) {
        renderStats(stats);
    }
    if (data) {
        allReproBugs = data.repro;
        allTestBugs = data.test;
        renderBugs(data.repro, data.test);
    }
}

/** Refresh all dynamic data (called after mutations) */
async function refreshAll() {
    await Promise.all([loadBugsData(), loadReservationsData()]);
}

async function loadReservationsData() {
    const reservationsBody = document.getElementById('reservationsBody');
    const reservationsCount = document.getElementById('reservationsCount');

    if (!reservationsBody) return;

    const reservationsParams = new URLSearchParams();
    if (activeWorkgroupId) reservationsParams.set('workgroup_id', activeWorkgroupId);
    const reservationsQs = reservationsParams.toString();
    const data = await apiFetch(reservationsQs ? `/api/reservations?${reservationsQs}` : '/api/reservations');
    const reservations = Array.isArray(data?.reservations) ? data.reservations : [];

    if (!reservations.length) {
        reservationsBody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#64748b;">No reservations yet</td></tr>';
        if (reservationsCount) reservationsCount.textContent = '0 reservations';
        return;
    }

    reservationsBody.innerHTML = reservations.map((r) => {
        const isByName = r.type === 'by_name';
        const modeLabel = isByName ? 'By Name' : 'By Config';
        const primary = isByName ? (r.bug_id || '—') : (r.resource_group || '—');
        const details = isByName
            ? ((r.stations || []).join(', ') || '—')
            : `Nodes: ${r.number_of_nodes ?? '—'}, PDs: ${r.number_of_pds ?? '—'}, Type: ${r.rc ? 'RC' : 'Non-RC'}${r.code_floor ? `, Floor: ${r.code_floor}` : ''}`;
        const createdAt = r.created_at ? new Date(r.created_at).toLocaleString() : '—';
        const detailsEscaped = escapeHtml(String(details));

        return `
            <tr>
                <td>${escapeHtml(String(modeLabel))}</td>
                <td>${escapeHtml(String(primary))}</td>
                <td class="reservation-details-cell" title="${detailsEscaped}">${detailsEscaped}</td>
                <td>${escapeHtml(String(createdAt))}</td>
            </tr>
        `;
    }).join('');

    if (reservationsCount) {
        const count = reservations.length;
        reservationsCount.textContent = `${count} ${count === 1 ? 'reservation' : 'reservations'}`;
    }
}

/* =========================================
   Renderers
   ========================================= */

function renderUserInfo() {
    if (!currentUser) return;

    // Remove loading states
    if (dom.userAvatar) dom.userAvatar.classList.remove('loading-pulse');
    if (dom.userName) dom.userName.classList.remove('loading-text');

    const initials = currentUser.fullName
        ? currentUser.fullName.split(' ').map(n => n[0]).join('').toUpperCase()
        : currentUser.name[0].toUpperCase();

    if (dom.userAvatar) dom.userAvatar.textContent = initials;
    if (dom.userName) dom.userName.textContent = currentUser.fullName || currentUser.name;
    if (dom.userRoleBadge) dom.userRoleBadge.textContent = currentUser.role || 'Manager';
    if (dom.profileEmail) dom.profileEmail.textContent = currentUser.email || 'manager@rro.com';

    updateOwnershipFilterUi();
}

function renderStats(stats) {
    animateNumber(dom.statTotalBugs, stats.totalBugs);
    animateNumber(dom.statReproBugs, stats.reproBugs);
    animateNumber(dom.statTestBugs, stats.testBugs);
    animateNumber(dom.statPendingActions, stats.pendingActions);
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

function generateBadgesHtml(items, type) {
    if (!items || !items.length) return '';
    const badgeClass = type === 'test' ? 'badge--blue' : 'badge--yellow';

    // Display max 2 items
    const MAX_ITEMS = 2;
    const visibleItems = items.slice(0, MAX_ITEMS);
    const hiddenCount = items.length - MAX_ITEMS;

    let html = visibleItems.map(item => `<span class="badge ${badgeClass}">${escapeHtml(item)}</span>`).join('');

    if (hiddenCount > 0) {
        html += `<span class="badge badge--gray">+${hiddenCount}</span>`;
    }

    return html;
}

function generateBugsTableRows(bugs) {
    return bugs.map(bug => {
        const priorityClass = {
            'P0': 'priority-p0',
            'P1': 'priority-p1',
            'P2': 'priority-p2',
            'P3': 'priority-p3',
            'P4': 'priority-p4'
        }[bug.priority] || 'priority-p2';
        const bugNameFull = bug.bug_name || '—';

        const testsCount = Array.isArray(bug.tests) ? bug.tests.length : 0;
        const testsLabel = `${testsCount} ${testsCount === 1 ? 'test' : 'tests'}`;

        return `
        <tr class="bug-row"
            data-bug-id="${escapeHtml(bug.id)}"
            data-bug-name="${escapeHtml(bug.bug_name || '—')}"
            data-priority="${escapeHtml(bug.priority || 'P2')}"
            data-engineer-name="${escapeHtml(bug.engineer_name || 'Unassigned')}"
            data-expanded="false"
            onclick="toggleBugExpansion(this)"
            style="cursor: pointer;"
            onmouseenter="this.style.backgroundColor='#f1f5f9'"
            onmouseleave="this.style.backgroundColor=''">
            <td><span class="priority-badge ${priorityClass}">${escapeHtml(bug.priority || 'P2')}</span></td>
            <td>
                <div class="bug-id-main">${escapeHtml(bug.id)}</div>
            </td>
            <td>
                <div class="bug-build-main">${escapeHtml(bug.build || '—')}</div>
            </td>
            <td class="bug-name-cell" title="${escapeHtml(bugNameFull)}">${escapeHtml(bugNameFull)}</td>
            <td class="engineer-cell">${escapeHtml(bug.engineer_name || 'Unassigned')}</td>
            <td>
                <div class="tests-trigger">
                    <span class="tests-count-badge">${escapeHtml(testsLabel)}</span>
                    <svg class="expand-chevron" width="16" height="16" viewBox="0 0 16 16" fill="none">
                        <path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                    </svg>
                </div>
            </td>
        </tr>
    `;
    }).join('');
}

function getPriorityClass(priority) {
    return {
        'P0': 'priority-p0',
        'P1': 'priority-p1',
        'P2': 'priority-p2',
        'P3': 'priority-p3',
        'P4': 'priority-p4'
    }[priority] || 'priority-p2';
}

function getNodeConfigLabel(nodesValue) {
    if (nodesValue === null || nodesValue === undefined || nodesValue === '') {
        return '—';
    }
    return `N${escapeHtml(nodesValue)}`;
}

function buildTestsTableHtml(testsPayload) {
    const tests = testsPayload?.tests || [];
    const rowsHtml = tests.length
        ? tests.map(t => `
            <tr>
                <td>${escapeHtml(t?.test_name || '—')}</td>
                <td>${escapeHtml(t?.station_name || '—')}</td>
                <td>${escapeHtml(t?.configuration || '—')}</td>
            </tr>
        `).join('')
        : `
            <tr>
                <td>—</td>
                <td>—</td>
                <td>—</td>
                <td>—</td>
            </tr>
        `;

    return `
        <table class="sub-tests-table">
            <thead>
                <tr>
                    <th>Test</th>
                    <th>Station Name</th>
                    <th>Configuration</th>
                </tr>
            </thead>
            <tbody>
                ${rowsHtml}
            </tbody>
        </table>
    `;
}

function cleanAnalysisField(val) {
    if (!val) return null;
    // Strip leading "Answer:" prefix that the LLM adds
    let cleaned = val.replace(/^\s*Answer:\s*/i, '').trim();
    // Treat "not found in provided context" as absent
    if (/not found in provided context/i.test(cleaned)) return null;
    return cleaned || null;
}

function buildMlAnalysisSectionHtml(analysisPayload) {
    const hasRecord = analysisPayload?.analysis !== null && analysisPayload?.analysis !== undefined;
    const analysis = analysisPayload?.analysis || {};
    const pending  = 'Pending analysis...';
    const notFound = 'Not found in bug comments';

    return `
        <div class="ml-analysis-inner">
            <div class="ml-analysis-title">ML's Analysis</div>
            <ol class="ml-analysis-list">
                <li class="ml-analysis-item">
                    <span class="ml-analysis-label">Repro Actions:</span>
                    <span class="ml-analysis-value">${escapeHtml(cleanAnalysisField(analysis.repro_actions) || (hasRecord ? notFound : pending))}</span>
                </li>
                <li class="ml-analysis-item">
                    <span class="ml-analysis-label">Config Changes:</span>
                    <span class="ml-analysis-value">${escapeHtml(cleanAnalysisField(analysis.config_changes) || (hasRecord ? notFound : pending))}</span>
                </li>
                <li class="ml-analysis-item">
                    <span class="ml-analysis-label">Repro Readiness:</span>
                    <span class="ml-analysis-value">${escapeHtml(cleanAnalysisField(analysis.repro_readiness) || (hasRecord ? notFound : pending))}</span>
                </li>
                <li class="ml-analysis-item">
                    <span class="ml-analysis-label">Summary:</span>
                    <span class="ml-analysis-value">${escapeHtml(cleanAnalysisField(analysis.summary) || (hasRecord ? notFound : pending))}</span>
                </li>
            </ol>
        </div>
    `;
}

function generateExpansionHtml(bugId, testsPayload, analysisPayload) {
    return `
        <tr class="expansion-row" data-expansion-for="${escapeHtml(bugId)}">
            <td colspan="6">
                ${buildTestsTableHtml(testsPayload)}
                ${buildMlAnalysisSectionHtml(analysisPayload)}
            </td>
        </tr>
    `;
}

async function toggleBugExpansion(row) {
    const bugId = row.dataset.bugId;
    const testsTrigger = row.querySelector('.tests-trigger');
    const chevron = row.querySelector('.expand-chevron');

    if (row.dataset.expanded === 'true') {
        const existingRows = Array.from(row.parentElement.querySelectorAll('tr[data-expansion-for]'));
        existingRows
            .filter(expansionRow => expansionRow.dataset.expansionFor === bugId)
            .forEach(expansionRow => expansionRow.remove());

        row.dataset.expanded = 'false';
        if (testsTrigger) testsTrigger.classList.remove('open');
        if (chevron) chevron.classList.remove('open');
        return;
    }

    row.dataset.expanded = 'true';
    if (testsTrigger) testsTrigger.classList.add('open');
    if (chevron) chevron.classList.add('open');

    const [testsPayload, analysisPayload] = await Promise.all([
        apiFetch('/api/bugs/' + bugId + '/tests'),
        apiFetch('/api/bugs/' + bugId + '/analysis')
    ]);

    if (row.dataset.expanded !== 'true') {
        return;
    }

    const expansionHtml = generateExpansionHtml(bugId, testsPayload, analysisPayload);
    row.insertAdjacentHTML('afterend', expansionHtml);
}

function renderBugs(reproBugs, testBugs) {
    console.log('Rendering repro bugs:', reproBugs);
    console.log('Rendering test bugs:', testBugs);

    dom.reproBugsCount.textContent = `${reproBugs.length} bugs`;
    dom.testBugsCount.textContent = `${testBugs.length} bugs`;

    dom.reproBugsBody.innerHTML = generateBugsTableRows(reproBugs);
    dom.testBugsBody.innerHTML = generateBugsTableRows(testBugs);
}

/* =========================================
   Dynamic Search
   ========================================= */

let searchDebounceTimer = null;

function getSearchWorkgroupId() {
    return activeWorkgroupId;
}

/**
 * Highlight matched text within a string.
 */
function highlightMatch(text, query) {
    if (!query) return escapeHtml(text);
    const escaped = escapeHtml(text);
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return escaped.replace(regex, '<mark>$1</mark>');
}

/**
 * Get the CSS class for a suggestion type tag.
 */
function getTagClass(type) {
    switch (type) {
        case 'Bug ID': return 'search-dropdown-tag--bugid';
        case 'Engineer': return 'search-dropdown-tag--engineer';
        case 'Test': return 'search-dropdown-tag--test';
        case 'Station': return 'search-dropdown-tag--station';
        default: return '';
    }
}

/**
 * Render search suggestions in the dropdown.
 */
function renderSearchDropdown(suggestions, query) {
    if (!suggestions || suggestions.length === 0) {
        dom.searchDropdown.innerHTML = `
            <div class="search-dropdown-empty">
                <span>No results found for "<strong>${escapeHtml(query)}</strong>"</span>
            </div>`;
        dom.searchDropdown.classList.remove('hidden');
        return;
    }

    const html = suggestions.map(s => `
        <div class="search-dropdown-item"
             data-type="${escapeHtml(s.type)}"
             data-value="${escapeHtml(s.value)}"
             data-bugid="${escapeHtml(s.bug_id)}">
            <span class="search-dropdown-tag ${getTagClass(s.type)}">${escapeHtml(s.type)}</span>
            <span class="search-dropdown-value">${highlightMatch(s.value, query)}</span>
        </div>
    `).join('');

    dom.searchDropdown.innerHTML = html;
    dom.searchDropdown.classList.remove('hidden');

    // Attach click handlers
    dom.searchDropdown.querySelectorAll('.search-dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
            const type = item.dataset.type;
            const value = item.dataset.value;
            dom.searchInput.value = value;
            dom.searchDropdown.classList.add('hidden');
            filterBugsBySelection(type, value);
        });
    });
}

/**
 * Filter both repro and test bug tables based on the selected suggestion.
 */
function filterBugsBySelection(type, value) {
    const valueLower = value.toLowerCase();

    function bugMatches(bug) {
        switch (type) {
            case 'Bug ID':
                return bug.id.toLowerCase() === valueLower;
            case 'Engineer':
                return (bug.engineer_name || '').toLowerCase() === valueLower;
            case 'Test':
                return bug.tests.some(t => t.toLowerCase() === valueLower);
            case 'Station':
                return bug.stations.some(s => s.toLowerCase() === valueLower);
            default:
                return false;
        }
    }

    const filteredRepro = allReproBugs.filter(bugMatches);
    const filteredTest = allTestBugs.filter(bugMatches);
    renderBugs(filteredRepro, filteredTest);
}

/**
 * Reset tables to show all bugs.
 */
function resetBugTables() {
    renderBugs(allReproBugs, allTestBugs);
}

/**
 * Handle search input with debouncing.
 */
function handleSearchInput() {
    clearTimeout(searchDebounceTimer);
    const query = dom.searchInput.value.trim();

    if (!query) {
        dom.searchDropdown.classList.add('hidden');
        resetBugTables();
        return;
    }

    searchDebounceTimer = setTimeout(async () => {
        const params = buildBugQueryParams({ q: query });
        const apiPath = `/api/bugs/search?${params.toString()}`;

        const suggestions = await apiFetch(apiPath);
        if (suggestions !== null) {
            renderSearchDropdown(suggestions, query);
        }
    }, 250);
}

/* =========================================
   Event Listeners
   ========================================= */

function initEventListeners() {
    // Profile Dropdown
    dom.profileDropdownTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        closeAllDropdowns();
        dom.profileDropdown.classList.toggle('hidden');
    });

    // Logout
    dom.btnLogout.addEventListener('click', async () => {
        await apiFetch('/api/auth/logout', { method: 'POST' });
        if (window.RROAuth) window.RROAuth.clearToken();
        currentUser = null;
        window.location.href = '/';
    });

    // Section Collapse Toggles
    const bugHeaders = document.querySelectorAll('.bugs-header');
    bugHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const section = header.closest('.bugs-section');
            if (section) {
                section.classList.toggle('collapsed');
            }
        });
    });

    // ── Dynamic Search ──
    if (dom.searchInput) {
        dom.searchInput.addEventListener('input', handleSearchInput);

        // Close dropdown on Escape
        dom.searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                dom.searchDropdown.classList.add('hidden');
            }
        });
    }

    // Engineer bug ownership filter
    if (dom.filterWorkgroupBugs) {
        dom.filterWorkgroupBugs.addEventListener('click', () => {
            setBugOwnershipFilter('workgroup');
        });
    }

    if (dom.filterMyBugs) {
        dom.filterMyBugs.addEventListener('click', () => {
            setBugOwnershipFilter('mine');
        });
    }
}

function closeAllDropdowns() {
    dom.profileDropdown.classList.add('hidden');
    if (dom.searchDropdown) dom.searchDropdown.classList.add('hidden');
}

// Close dropdowns on outside click
document.addEventListener('click', (e) => {
    // Don't close search dropdown if clicking inside the search area
    const searchContainer = document.querySelector('.search-container');
    if (searchContainer && searchContainer.contains(e.target)) {
        dom.profileDropdown.classList.add('hidden');
        return;
    }
    closeAllDropdowns();
});

/* =========================================
   Utilities
   ========================================= */

function escapeHtml(str) {
    if (str == null) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/* =========================================
   Init — runs on page load
   ========================================= */

async function init() {
    activeWorkgroupId = getCurrentWorkgroupId();
    initEventListeners();
    await loadCurrentUser();
    updateOwnershipFilterUi();
    await loadBugsData();
    await loadReservationsData();
}

document.addEventListener('DOMContentLoaded', init);

/* ── Toast Notification ── */
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => {
        toast.className = 'toast';
    }, 3000);
}

/* =========================================
   Reserve Station Modal — Refined
   ========================================= */

let reserveActiveTab = 'byName';
let allBugOptions = [];
let allStationOptions = [];
let selectedStations = [];

/* ── DOM Getters ── */
const reserveDom = {
    get overlay()          { return document.getElementById('reserveModalOverlay'); },
    get toggleSlider()     { return document.getElementById('reserveToggleSlider'); },
    get tabByName()        { return document.getElementById('tabByName'); },
    get tabByConfig()      { return document.getElementById('tabByConfig'); },
    get panelByName()      { return document.getElementById('panelByName'); },
    get panelByConfig()    { return document.getElementById('panelByConfig'); },
    get bugIdInput()       { return document.getElementById('reserveBugId'); },
    get bugIdDropdown()    { return document.getElementById('bugIdDropdown'); },
    get stationInput()     { return document.getElementById('reserveStationName'); },
    get stationDropdown()  { return document.getElementById('stationDropdown'); },
    get stationTags()      { return document.getElementById('stationTags'); },
    get stationDropdownGroup() { return document.getElementById('stationDropdownGroup'); },
    get specifyStation()   { return document.getElementById('reserveSpecifyStation'); },
    get specifyStationGroup()  { return document.getElementById('specifyStationGroup'); },
    get stationManual()    { return document.getElementById('reserveStationManual'); },
    get resourceGroup()    { return document.getElementById('reserveResourceGroup'); },
    get numNodes()         { return document.getElementById('reserveNumNodes'); },
    get codeFloor()        { return document.getElementById('reserveCodeFloor'); },
    get numPDs()           { return document.getElementById('reserveNumPDs'); },
};

/* ── Open / Close ── */
function openReserveModal() {
    populateReserveDropdowns();
    reserveDom.overlay.classList.add('open');
}

function closeReserveModal() {
    reserveDom.overlay.classList.remove('open');
    resetReserveForm();
}

function resetReserveForm() {
    switchReserveTab('byName');
    selectedStations = [];
    renderStationTags();

    // Clear any existing errors
    document.querySelectorAll('.field-error').forEach(el => el.classList.remove('visible'));
    document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));

    if (reserveDom.bugIdInput) reserveDom.bugIdInput.value = '';
    if (reserveDom.stationInput) reserveDom.stationInput.value = '';
    if (reserveDom.specifyStation) reserveDom.specifyStation.checked = false;
    if (reserveDom.stationManual) reserveDom.stationManual.value = '';
    if (reserveDom.specifyStationGroup) reserveDom.specifyStationGroup.classList.add('hidden');
    if (reserveDom.stationDropdownGroup) reserveDom.stationDropdownGroup.classList.remove('hidden');
    if (reserveDom.resourceGroup) reserveDom.resourceGroup.value = '';
    if (reserveDom.numNodes) reserveDom.numNodes.value = '';
    if (reserveDom.codeFloor) reserveDom.codeFloor.value = '';
    if (reserveDom.numPDs) reserveDom.numPDs.value = '';
    const rcNo = document.querySelector('input[name="reserveRC"][value="no"]');
    if (rcNo) rcNo.checked = true;
    // Close dropdowns
    reserveDom.bugIdDropdown?.classList.add('hidden');
    reserveDom.stationDropdown?.classList.add('hidden');
}

function clearByNameFormValues() {
    selectedStations = [];
    renderStationTags();

    if (reserveDom.bugIdInput) reserveDom.bugIdInput.value = '';
    if (reserveDom.stationInput) reserveDom.stationInput.value = '';
    if (reserveDom.specifyStation) reserveDom.specifyStation.checked = false;
    if (reserveDom.stationManual) reserveDom.stationManual.value = '';
    if (reserveDom.specifyStationGroup) reserveDom.specifyStationGroup.classList.add('hidden');
    if (reserveDom.stationDropdownGroup) reserveDom.stationDropdownGroup.classList.remove('hidden');
    reserveDom.bugIdDropdown?.classList.add('hidden');
    reserveDom.stationDropdown?.classList.add('hidden');
}

function clearByConfigFormValues() {
    if (reserveDom.resourceGroup) reserveDom.resourceGroup.value = '';
    if (reserveDom.numNodes) reserveDom.numNodes.value = '';
    if (reserveDom.codeFloor) reserveDom.codeFloor.value = '';
    if (reserveDom.numPDs) reserveDom.numPDs.value = '';
    const rcNo = document.querySelector('input[name="reserveRC"][value="no"]');
    if (rcNo) rcNo.checked = true;
}

/* ── Sliding Toggle ── */
function switchReserveTab(tab) {
    const previousTab = reserveActiveTab;
    reserveActiveTab = tab;
    reserveDom.tabByName.classList.toggle('active', tab === 'byName');
    reserveDom.tabByConfig.classList.toggle('active', tab === 'byConfig');
    reserveDom.panelByName.classList.toggle('hidden', tab !== 'byName');
    reserveDom.panelByConfig.classList.toggle('hidden', tab !== 'byConfig');
    // Slide the indicator
    if (reserveDom.toggleSlider) {
        reserveDom.toggleSlider.classList.toggle('right', tab === 'byConfig');
    }

    if (previousTab !== tab) {
        if (tab === 'byConfig') {
            clearByNameFormValues();
        } else {
            clearByConfigFormValues();
        }
    }
}

/* ── Combobox: Bug ID (single select, type-ahead) ── */
function renderBugIdDropdown(filter = '') {
    const dropdown = reserveDom.bugIdDropdown;
    if (!dropdown) return;
    const filterLower = filter.toLowerCase();
    const filtered = allBugOptions.filter(b =>
        b.id.toLowerCase().includes(filterLower) ||
        (b.name || '').toLowerCase().includes(filterLower)
    );
    if (filtered.length === 0) {
        dropdown.innerHTML = '<div class="combobox-empty">No matching bugs</div>';
    } else {
        dropdown.innerHTML = filtered.map(b =>
            `<div class="combobox-option" data-value="${escapeHtml(b.id)}">${escapeHtml(b.id)} — ${escapeHtml(b.name || 'Unnamed')}</div>`
        ).join('');
    }
    dropdown.classList.remove('hidden');
    // click handlers
    dropdown.querySelectorAll('.combobox-option').forEach(opt => {
        opt.addEventListener('click', () => {
            reserveDom.bugIdInput.value = opt.dataset.value;
            dropdown.classList.add('hidden');
        });
    });
}

/* ── Combobox: Station Name (multi-select, up to 3) ── */
function renderStationDropdown(filter = '') {
    const dropdown = reserveDom.stationDropdown;
    if (!dropdown) return;
    const filterLower = filter.toLowerCase();
    const filtered = allStationOptions.filter(s =>
        s.toLowerCase().includes(filterLower)
    );
    if (filtered.length === 0) {
        dropdown.innerHTML = '<div class="combobox-empty">No matching stations</div>';
    } else {
        dropdown.innerHTML = filtered.map(s => {
            const isSelected = selectedStations.includes(s);
            const isDisabled = !isSelected && selectedStations.length >= 3;
            const classes = ['combobox-option'];
            if (isSelected) classes.push('selected');
            if (isDisabled) classes.push('disabled');
            return `<div class="${classes.join(' ')}" data-value="${escapeHtml(s)}">${escapeHtml(s)}</div>`;
        }).join('');
    }
    dropdown.classList.remove('hidden');
    dropdown.querySelectorAll('.combobox-option:not(.disabled)').forEach(opt => {
        opt.addEventListener('click', () => {
            const val = opt.dataset.value;
            if (selectedStations.includes(val)) {
                selectedStations = selectedStations.filter(s => s !== val);
            } else if (selectedStations.length < 3) {
                selectedStations.push(val);
            }
            renderStationTags();
            renderStationDropdown(reserveDom.stationInput?.value || '');
        });
    });
}

function renderStationTags() {
    const container = reserveDom.stationTags;
    if (!container) return;
    container.innerHTML = selectedStations.map(s =>
        `<span class="combobox-tag">${escapeHtml(s)}<button class="combobox-tag-remove" data-station="${escapeHtml(s)}" type="button">×</button></span>`
    ).join('');
    container.querySelectorAll('.combobox-tag-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            selectedStations = selectedStations.filter(s => s !== btn.dataset.station);
            renderStationTags();
            renderStationDropdown(reserveDom.stationInput?.value || '');
        });
    });
}

/* ── Populate Dropdowns ── */
async function populateReserveDropdowns() {
    // Bug IDs from API (Engineer's own bugs, scoped to workgroup if active)
    try {
        const bugsParams = new URLSearchParams();
        bugsParams.set('my_only', 'true');
        if (activeWorkgroupId) bugsParams.set('workgroup_id', activeWorkgroupId);
        const myBugsData = await apiFetch(`/api/bugs?${bugsParams.toString()}`);
        if (myBugsData) {
            allBugOptions = [...(myBugsData.repro || []), ...(myBugsData.test || [])].map(b => ({ id: b.id, name: b.bug_name }));
        } else {
            allBugOptions = [];
        }
    } catch(err) {
        console.error("Failed to load bugs for reservation:", err);
        allBugOptions = [];
    }

    // Stations from API
    try {
        const stationsData = await apiFetch('/api/stations');
        allStationOptions = stationsData?.stations || [];
    } catch(err) {
        console.error("Failed to load stations:", err);
        allStationOptions = [];
    }

    // Resource Group
    const rgSelect = reserveDom.resourceGroup;
    if (rgSelect) {
        rgSelect.innerHTML = '<option value="">Select a Resource Group...</option>';
        try {
            const wgData = await apiFetch('/api/engineer/workgroups');
            if (wgData && Array.isArray(wgData)) {
                // Ensure unique non-empty release versions
                const rgSet = new Set(wgData.map(w => w.release_version).filter(Boolean));
                rgSet.forEach(rg => {
                    const opt = document.createElement('option');
                    opt.value = rg;
                    opt.textContent = rg;
                    rgSelect.appendChild(opt);
                });
            }
        } catch(err) {
            console.error("Failed to load workgroups for reservation:", err);
        }
    }
}

/* ── Numbers Only Input Enforcement ── */
function enforceNumbersOnly(input) {
    input.addEventListener('input', () => {
        input.value = input.value.replace(/[^0-9]/g, '');
    });
    input.addEventListener('keydown', (e) => {
        // Allow: backspace, delete, tab, escape, enter, arrows
        if ([8, 9, 13, 27, 46, 37, 38, 39, 40].includes(e.keyCode)) return;
        // Allow Ctrl+A/C/V/X
        if ((e.ctrlKey || e.metaKey) && [65, 67, 86, 88].includes(e.keyCode)) return;
        // Block non-digits
        if (e.key && !/^[0-9]$/.test(e.key)) e.preventDefault();
    });
}

/* ── Submit Handler ── */
async function handleReserveSubmit() {
    // Clear previous errors
    document.querySelectorAll('.field-error').forEach(el => el.classList.remove('visible'));
    document.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
    
    let isValid = true;
    let payload;

    if (reserveActiveTab === 'byName') {
        const bugId = reserveDom.bugIdInput?.value?.trim();
        const specifyMode = reserveDom.specifyStation?.checked;
        let stations;

        if (specifyMode) {
            const manual = reserveDom.stationManual?.value?.trim();
            stations = manual ? manual.split(',').map(s => s.trim()).filter(Boolean) : [];
        } else {
            stations = [...selectedStations];
        }

        if (!bugId) {
            document.getElementById('errBugId').textContent = 'Please enter or select a Bug ID';
            document.getElementById('errBugId').classList.add('visible');
            document.getElementById('bugIdCombobox')?.classList.add('input-error');
            isValid = false;
        } else {
            const bugExists = allBugOptions.some(b => b.id.toString() === bugId || b.name === bugId);
            if (!bugExists) {
                document.getElementById('errBugId').textContent = 'Invalid Bug ID. Please check and select a valid bug assigned to you.';
                document.getElementById('errBugId').classList.add('visible');
                document.getElementById('bugIdCombobox')?.classList.add('input-error');
                isValid = false;
            }
        }
        
        if (stations.length === 0) {
            if (specifyMode) {
                document.getElementById('errStationManual').textContent = 'Please enter at least one station name';
                document.getElementById('errStationManual').classList.add('visible');
                reserveDom.stationManual?.classList.add('input-error');
            } else {
                document.getElementById('errStation').textContent = 'Please select at least one station';
                document.getElementById('errStation').classList.add('visible');
                document.getElementById('stationCombobox')?.classList.add('input-error');
            }
            isValid = false;
        }

        if (!isValid) return;

        payload = {
            type: 'by_name',
            bug_id: bugId,
            stations: stations,
            specify_station: specifyMode || false,
        };
    } else {
        const resourceGroup = reserveDom.resourceGroup?.value;
        const numNodes = reserveDom.numNodes?.value?.trim();
        const rcValue = document.querySelector('input[name="reserveRC"]:checked')?.value;

        if (!resourceGroup) {
            document.getElementById('errResourceGroup')?.classList.add('visible');
            reserveDom.resourceGroup?.classList.add('input-error');
            isValid = false;
        }
        
        if (!numNodes) {
            document.getElementById('errNumNodes')?.classList.add('visible');
            reserveDom.numNodes?.classList.add('input-error');
            isValid = false;
        }

        const numPDs = reserveDom.numPDs?.value?.trim();
        if (!numPDs) {
            document.getElementById('errNumPDs')?.classList.add('visible');
            reserveDom.numPDs?.classList.add('input-error');
            isValid = false;
        }

        if (!isValid) return;

        payload = {
            type: 'by_config',
            resource_group: resourceGroup,
            number_of_nodes: parseInt(numNodes, 10),
            code_floor: reserveDom.codeFloor?.value?.trim() || null,
            number_of_pds: parseInt(numPDs, 10),
            rc: rcValue === 'yes',
        };
    }

    // Remove global error if present
    const existingGlobalErr = document.getElementById('errReserveGlobal');
    if (existingGlobalErr) existingGlobalErr.classList.remove('visible');

    try {
        const response = await fetch('/api/reservations', {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            credentials: 'include',
            body: JSON.stringify(payload),
        });
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            const errMsg = errData.error || `HTTP ${response.status} ${response.statusText}`;
            throw new Error(errMsg);
        }

        const result = await response.json();
        showToast('Reservation submitted successfully!', 'success');
        closeReserveModal();
        await loadReservationsData();
        // Scroll reservations table into view so engineer sees the update
        document.getElementById('reservationsBody')?.closest('table')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (err) {
        console.error("Reserve submit failed", err);
        let globalErr = document.getElementById('errReserveGlobal');
        if (!globalErr) {
            globalErr = document.createElement('div');
            globalErr.id = 'errReserveGlobal';
            globalErr.className = 'field-error';
            globalErr.style.textAlign = 'center';
            globalErr.style.marginBottom = '10px';
            globalErr.style.marginTop = '10px';
            document.querySelector('.modal-footer').parentNode.insertBefore(globalErr, document.querySelector('.modal-footer'));
        }
        globalErr.textContent = err.message || 'Failed to submit reservation.';
        globalErr.classList.add('visible');
    }
}

/* ── Show Reserve Button (Engineer only) ── */
function showReserveButtonIfEngineer() {
    const isEngineerPage = window.location.pathname.includes('/engineer/bug_management');
    if (currentUser?.role === 'Engineer' || isEngineerPage) {
        const btn = document.getElementById('btnReserveStation');
        if (btn) {
            btn.hidden = false;
            btn.style.removeProperty('display');
            btn.style.setProperty('display', 'inline-flex', 'important');
            btn.style.setProperty('visibility', 'visible', 'important');
            btn.style.setProperty('opacity', '1', 'important');
        }
    }
}

/* ── Wire Up Events ── */
document.addEventListener('DOMContentLoaded', () => {
    showReserveButtonIfEngineer();
    setTimeout(showReserveButtonIfEngineer, 300);

    // Open / Close
    document.getElementById('btnReserveStation')?.addEventListener('click', openReserveModal);
    document.getElementById('reserveModalClose')?.addEventListener('click', closeReserveModal);
    document.getElementById('reserveBtnCancel')?.addEventListener('click', closeReserveModal);
    document.getElementById('reserveModalOverlay')?.addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeReserveModal();
    });

    // Sliding toggle
    document.getElementById('tabByName')?.addEventListener('click', () => switchReserveTab('byName'));
    document.getElementById('tabByConfig')?.addEventListener('click', () => switchReserveTab('byConfig'));

    // Bug ID combobox
    const bugInput = document.getElementById('reserveBugId');
    if (bugInput) {
        bugInput.addEventListener('focus', () => renderBugIdDropdown(bugInput.value));
        bugInput.addEventListener('input', () => renderBugIdDropdown(bugInput.value));
    }

    // Station combobox
    const stationInput = document.getElementById('reserveStationName');
    if (stationInput) {
        stationInput.addEventListener('focus', () => renderStationDropdown(stationInput.value));
        stationInput.addEventListener('input', () => renderStationDropdown(stationInput.value));
    }

    // Close combobox dropdowns on outside click
    document.addEventListener('click', (e) => {
        const bugCb = document.getElementById('bugIdCombobox');
        const staCb = document.getElementById('stationCombobox');
        if (bugCb && !bugCb.contains(e.target)) {
            document.getElementById('bugIdDropdown')?.classList.add('hidden');
        }
        if (staCb && !staCb.contains(e.target)) {
            document.getElementById('stationDropdown')?.classList.add('hidden');
        }
    });

    // Specify Station toggle
    const specifyChk = document.getElementById('reserveSpecifyStation');
    if (specifyChk) {
        specifyChk.addEventListener('change', () => {
            const dropdownGroup = document.getElementById('stationDropdownGroup');
            const manualGroup = document.getElementById('specifyStationGroup');
            if (specifyChk.checked) {
                selectedStations = [];
                renderStationTags();
                if (reserveDom.stationInput) reserveDom.stationInput.value = '';
                document.getElementById('errStation')?.classList.remove('visible');
                document.getElementById('stationCombobox')?.classList.remove('input-error');
                dropdownGroup?.classList.add('hidden');
                manualGroup?.classList.remove('hidden');
            } else {
                if (reserveDom.stationManual) reserveDom.stationManual.value = '';
                document.getElementById('errStationManual')?.classList.remove('visible');
                reserveDom.stationManual?.classList.remove('input-error');
                dropdownGroup?.classList.remove('hidden');
                manualGroup?.classList.add('hidden');
            }
        });
    }

    // Numbers-only inputs
    const numNodesInput = document.getElementById('reserveNumNodes');
    const numPDsInput = document.getElementById('reserveNumPDs');
    if (numNodesInput) enforceNumbersOnly(numNodesInput);
    if (numPDsInput) enforceNumbersOnly(numPDsInput);

    // Submit
    document.getElementById('reserveBtnSubmit')?.addEventListener('click', handleReserveSubmit);
});

// Patch loadCurrentUser to show Reserve button for engineers
const _originalLoadCurrentUser = loadCurrentUser;
loadCurrentUser = async function() {
    await _originalLoadCurrentUser();
    showReserveButtonIfEngineer();
};

window.addEventListener('load', () => {
    showReserveButtonIfEngineer();
    setTimeout(showReserveButtonIfEngineer, 600);
});
