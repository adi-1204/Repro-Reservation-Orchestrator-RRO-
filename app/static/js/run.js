/**
 * RRO Run Page — JavaScript
 * Handles all interactivity for the Run page.
 */

const API_BASE = '';

// ── State variables (all form values stored here) ──
const state = {
    runMode: 'run_tests',
    bugToRepro: null,
    selectedTests: [],
    selectedStation: '',
    runOptionsMode: null,
    qrWorkflow: '',
    qrRunCount: '',
    coWorkflow: '',
    coRunCount: '',
    coProvisionSetup: [],   // stores raw values (without ★)
    coCheckout: false,
};

let allSystemTestNames = [];
let allStationOptions = [];
let stationOptions = [];
let bugTests = [];
let allBugs = [];
let runHistory = [];
let completedReservationStations = []; // Track stations from completed reservations

function getAuthHeaders(h = {}) {
    return window.RROAuth ? window.RROAuth.getAuthHeaders(h) : h;
}

async function apiFetch(path, options = {}) {
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            headers: getAuthHeaders({ 'Content-Type': 'application/json', ...options.headers }),
            credentials: 'include',
            ...options,
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.warn(`[API] ${path}`, e.message);
        return null;
    }
}

function esc(str) {
    const d = document.createElement('div');
    d.textContent = str ?? '';
    return d.innerHTML;
}

function showToast(msg, type = 'success') {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.className = `toast show ${type}`;
    setTimeout(() => { t.className = 'toast'; }, 3500);
}

function formatDateTime(value) {
    if (!value) return '—';
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return '—';
    return dt.toLocaleString();
}

function statusBadgeClass(status) {
    const value = String(status || '').toLowerCase();
    if (value === 'running') return 'run-status-badge run-status-badge--running';
    if (value === 'completed') return 'run-status-badge run-status-badge--completed';
    if (value === 'failed') return 'run-status-badge run-status-badge--failed';
    return 'run-status-badge run-status-badge--queued';
}

function renderRunHistory() {
    const tbody = document.getElementById('runHistoryBody');
    if (!tbody) return;

    if (!runHistory.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="13" class="run-history-empty">No run records found yet.</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = runHistory.map(run => {
        const stationName = run.station_name || 'No station';
        const isComprehensive = String(run.run_type || '').toLowerCase() === 'comprehensive';
        const provisionSetup = isComprehensive ? (run.provision_setup || '—') : '—';
        const doCheckout = isComprehensive ? (run.do_checkout_update ? 'Yes' : 'No') : '—';
        const bugName = run.bug_name || '—';
        const testName = run.test_name || '—';

        return `
        <tr>
            <td>#${esc(run.id)}</td>
            <td>${esc(run.bug_id || '—')}</td>
            <td class="run-history-ellipsis" title="${esc(bugName)}">${esc(bugName)}</td>
            <td class="run-history-ellipsis" title="${esc(testName)}">${esc(testName)}</td>
            <td class="run-history-ellipsis" title="${esc(stationName)}">${esc(stationName)}</td>
            <td class="run-history-ellipsis" title="${esc(provisionSetup)}">${esc(provisionSetup)}</td>
            <td>${esc(doCheckout)}</td>
            <td>${esc(run.workflow || '—')}</td>
            <td>${esc(run.run_mode || '—')}</td>
            <td>${esc(run.run_type || '—')}</td>
            <td>${esc(run.run_count ?? '—')}</td>
            <td><span class="${statusBadgeClass(run.status)}">${esc(run.status || 'queued')}</span></td>
            <td>${esc(formatDateTime(run.submitted_at))}</td>
        </tr>
    `;
    }).join('');
}

async function loadRunHistory() {
    const tbody = document.getElementById('runHistoryBody');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="13" class="run-history-empty">Loading run history...</td>
            </tr>
        `;
    }

    const data = await apiFetch('/api/runs');
    runHistory = data?.runs || [];
    renderRunHistory();
}

// ═══════════════════════════════════════════
// SECTION 1 — Run Mode radio buttons
// ═══════════════════════════════════════════
function initRunMode() {
    document.querySelectorAll('input[name="runMode"]').forEach(radio => {
        radio.addEventListener('change', () => {
            state.runMode = radio.value;
        });
    });
}

// ═══════════════════════════════════════════
// SECTION 2 — Bug to Repro combobox
// ═══════════════════════════════════════════

let bugDebounce = null;

function renderBugDropdown(filtered, query) {
    const dd = document.getElementById('bugReproDropdown');
    if (!filtered.length) {
        dd.innerHTML = `<div class="run-dropdown-empty">No bugs found for "${esc(query)}"</div>`;
    } else {
        dd.innerHTML = filtered.map(b => `
            <div class="run-dropdown-item" data-bug-id="${esc(b.id)}" data-bug-name="${esc(b.bug_name || '')}">
                <span><strong>${esc(b.id)}</strong> — ${esc(b.bug_name || 'Unnamed')}</span>
            </div>
        `).join('');
        dd.querySelectorAll('.run-dropdown-item').forEach(item => {
            item.addEventListener('click', () => selectBug(item));
        });
    }
    dd.classList.remove('hidden');
}

function selectBug(item) {
    state.bugToRepro = {
        bug_id: item.dataset.bugId,
        bug_name: item.dataset.bugName,
    };
    document.getElementById('bugReproInput').value = item.dataset.bugId;
    document.getElementById('bugReproDropdown').classList.add('hidden');
    document.getElementById('errBugRepro').classList.add('hidden');

    state.selectedTests = [];
    state.selectedStation = '';
    stationOptions = [];
    completedReservationStations = [];
    renderSelectedTags();
    renderSelectedStationTags();
    
    // Reset station input state
    const stationInput = document.getElementById('stationRunInput');
    if (stationInput) {
        stationInput.value = '';
        stationInput.disabled = false;
        stationInput.placeholder = 'Type or select a station...';
    }
    
    loadBugTests(item.dataset.bugId);
}

async function loadBugTests(bugCode) {
    bugTests = [];
    stationOptions = [];
    completedReservationStations = [];

    const data = await apiFetch(`/api/bugs/${bugCode}/tests`);

    if (data && Array.isArray(data.tests)) {
        // All tests
        bugTests = data.tests.map(t => t.test_name).filter(Boolean);
    }

    // ✅ Load stations from completed reservations for this bug
    try {
        const reservationData = await apiFetch(`/api/bugs/${bugCode}/reservation-stations`);
        if (reservationData && reservationData.has_completed_reservation) {
            // Use ONLY stations from completed reservations
            completedReservationStations = reservationData.stations || [];
            stationOptions = [...completedReservationStations].sort();
            console.log(`[Run] Loaded ${stationOptions.length} stations from completed reservations for bug ${bugCode}`);
        } else {
            console.log(`[Run] No completed reservations for bug ${bugCode} - no stations available`);
        }
    } catch (err) {
        console.error(`[Run] Failed to load reservation stations for bug ${bugCode}:`, err);
    }
}

function initBugReproCombobox() {
    const input = document.getElementById('bugReproInput');
    const dd = document.getElementById('bugReproDropdown');
    const combo = document.getElementById('bugReproCombobox');

    input.addEventListener('input', () => {
        const q = input.value.trim();
        clearTimeout(bugDebounce);
        bugDebounce = setTimeout(() => {
            const lower = q.toLowerCase();
            const filtered = q
                ? allBugs.filter(b =>
                    b.id.toLowerCase().includes(lower) ||
                    (b.bug_name || '').toLowerCase().includes(lower)
                ).slice(0, 8)
                : allBugs.slice(0, 8);
            renderBugDropdown(filtered, q);
        }, 200);
    });

    input.addEventListener('focus', () => {
        const q = input.value.trim();
        const lower = q.toLowerCase();
        const filtered = q
            ? allBugs.filter(b =>
                b.id.toLowerCase().includes(lower) ||
                (b.bug_name || '').toLowerCase().includes(lower)
            ).slice(0, 8)
            : allBugs.slice(0, 8);
        renderBugDropdown(filtered, q);
    });

    combo.addEventListener('click', () => {
        const q = input.value.trim();
        const lower = q.toLowerCase();
        const filtered = q
            ? allBugs.filter(b =>
                b.id.toLowerCase().includes(lower) ||
                (b.bug_name || '').toLowerCase().includes(lower)
            ).slice(0, 8)
            : allBugs.slice(0, 8);
        renderBugDropdown(filtered, q);
    });

    input.addEventListener('change', () => {
        if (!input.value.trim()) {
            state.bugToRepro = null;
            bugTests = [];
            stationOptions = [];
            state.selectedTests = [];
            state.selectedStation = '';
            renderSelectedTags();
            renderSelectedStationTags();
        }
    });

    document.addEventListener('click', e => {
        if (!document.getElementById('bugReproCombobox').contains(e.target)) {
            dd.classList.add('hidden');
        }
    });
}

async function loadAllBugs() {
    const data = await apiFetch('/api/bugs?my_only=true');
    if (!data) return;
    allBugs = (data.repro || []);
    allSystemTestNames = [];
    allBugs.forEach(b => {
        if (Array.isArray(b.tests)) allSystemTestNames.push(...b.tests);
    });
}

async function loadAllStations() {
    const data = await apiFetch('/api/stations');
    allStationOptions = Array.isArray(data?.stations) ? data.stations : [];
}

// ═══════════════════════════════════════════
// SECTION 2 — Choose Test to Run combobox
// ═══════════════════════════════════════════

let testDebounce = null;

function renderSelectedTags() {
    const container = document.getElementById('selectedTestTags');
    container.innerHTML = state.selectedTests.map(t => `
        <span class="run-tag">
            ${esc(t)}
            <button class="run-tag-remove" data-test="${esc(t)}" type="button">×</button>
        </span>
    `).join('');
    container.querySelectorAll('.run-tag-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            state.selectedTests = state.selectedTests.filter(x => x !== btn.dataset.test);
            renderSelectedTags();
        });
    });
}

function renderTestDropdown(filtered, query) {
    const dd = document.getElementById('testRunDropdown');
    let html = '';

    filtered.forEach(name => {
        const isSelected = state.selectedTests.includes(name);
        html += `
            <div class="run-dropdown-item ${isSelected ? 'selected' : ''}" data-test="${esc(name)}">
                ${esc(name)}
                ${isSelected ? '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7l4 4 6-6" stroke="#7c3aed" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}
            </div>`;
    });

    const exactMatch = filtered.some(n => n.toLowerCase() === query.toLowerCase());
    if (query && !exactMatch) {
        html += `
            <div class="run-dropdown-item run-dropdown-item--add" data-test="${esc(query)}" data-custom="true">
                + Add &ldquo;${esc(query)}&rdquo; as new test
            </div>`;
    }

    if (!html) {
        html = `<div class="run-dropdown-empty">No tests found</div>`;
    }

    dd.innerHTML = html;
    dd.querySelectorAll('.run-dropdown-item').forEach(item => {
        item.addEventListener('click', () => addTest(item.dataset.test, item.dataset.custom === 'true'));
    });
    dd.classList.remove('hidden');
}

function addTest(testName, isCustom) {
    if (!state.bugToRepro) {
        showError('errNoBug');
        document.getElementById('testRunDropdown').classList.add('hidden');
        return;
    }

    if (isCustom) {
        const lower = testName.toLowerCase();
        if (allSystemTestNames.map(x => x.toLowerCase()).includes(lower)) {
            showError('errTestDuplicate');
            return;
        }
    }

    if (!state.selectedTests.includes(testName)) {
        state.selectedTests.push(testName);
        renderSelectedTags();
    }
    document.getElementById('testRunInput').value = '';
    document.getElementById('testRunDropdown').classList.add('hidden');
    hideAllTestErrors();
}

function showError(id) {
    hideAllTestErrors();
    document.getElementById(id).classList.remove('hidden');
    setTimeout(() => document.getElementById(id).classList.add('hidden'), 3500);
}

function hideAllTestErrors() {
    ['errTestRun', 'errTestDuplicate', 'errNoBug'].forEach(id =>
        document.getElementById(id).classList.add('hidden')
    );
}

function initTestRunCombobox() {
    const input = document.getElementById('testRunInput');
    const dd = document.getElementById('testRunDropdown');

    input.addEventListener('focus', () => {
        if (!state.bugToRepro) { showError('errNoBug'); return; }
        renderTestDropdown(bugTests, input.value.trim());
    });

    input.addEventListener('input', () => {
        if (!state.bugToRepro) { showError('errNoBug'); return; }
        clearTimeout(testDebounce);
        testDebounce = setTimeout(() => {
            const q = input.value.trim().toLowerCase();
            const filtered = q ? bugTests.filter(t => t.toLowerCase().includes(q)) : bugTests;
            renderTestDropdown(filtered, input.value.trim());
        }, 150);
    });

    document.addEventListener('click', e => {
        if (!document.getElementById('testRunCombobox').contains(e.target)) {
            dd.classList.add('hidden');
        }
    });
}

// ═══════════════════════════════════════════
// SECTION 3 — Slider toggle
// ═══════════════════════════════════════════
let stationDebounce = null;

function getStationOptionsForRun() {
    return stationOptions.length ? stationOptions : allStationOptions;
}

function hideAllStationErrors() {
    ['errStationRun', 'errStationNoBug'].forEach(id =>
        document.getElementById(id)?.classList.add('hidden')
    );
}

function showStationError(id) {
    hideAllStationErrors();
    document.getElementById(id)?.classList.remove('hidden');
    setTimeout(() => document.getElementById(id)?.classList.add('hidden'), 3500);
}

function renderSelectedStationTags() {
    const input = document.getElementById('stationRunInput');
    if (input) input.value = state.selectedStation;
}

function renderStationDropdown(query = '') {
    const dd = document.getElementById('stationRunDropdown');
    const input = document.getElementById('stationRunInput');
    if (!dd || !input) return;

    // If no stations from completed reservations, hide dropdown and disable input
    if (!stationOptions.length) {
        dd.classList.add('hidden');
        input.placeholder = 'No completed reservations for this bug';
        input.disabled = true;
        return;
    }

    // Enable input if stations are available
    input.disabled = false;
    input.placeholder = 'Type or select a station...';

    const q = query.trim().toLowerCase();
    const options = getStationOptionsForRun();
    const filtered = (q ? options.filter(s => s.toLowerCase().includes(q)) : options).slice(0, 30);

    dd.innerHTML = filtered.map(station => {
        const isSelected = state.selectedStation === station;
        return `
            <div class="run-dropdown-item ${isSelected ? 'selected' : ''}" data-station="${esc(station)}">
                <span>${esc(station)}</span>
                ${isSelected ? '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2 7l4 4 6-6" stroke="#7c3aed" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>' : ''}
            </div>
        `;
    }).join('');

    dd.querySelectorAll('.run-dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
            const station = item.dataset.station;
            if (!station) return;

            state.selectedStation = station;

            document.getElementById('stationRunInput').value = station;
            hideAllStationErrors();
            renderSelectedStationTags();
            dd.classList.add('hidden');
        });
    });

    dd.classList.remove('hidden');
}

function initStationRunCombobox() {
    const input = document.getElementById('stationRunInput');
    const dd = document.getElementById('stationRunDropdown');
    const combo = document.getElementById('stationRunCombobox');
    if (!input || !dd || !combo) return;

    input.addEventListener('focus', () => {
        if (!state.bugToRepro) { showStationError('errStationNoBug'); return; }
        renderStationDropdown(input.value);
    });

    input.addEventListener('input', () => {
        if (!state.bugToRepro) { showStationError('errStationNoBug'); return; }
        state.selectedStation = '';
        clearTimeout(stationDebounce);
        stationDebounce = setTimeout(() => renderStationDropdown(input.value), 150);
    });

    combo.addEventListener('click', () => {
        if (!state.bugToRepro) { showStationError('errStationNoBug'); return; }
        renderStationDropdown(input.value);
    });

    document.addEventListener('click', e => {
        if (!combo.contains(e.target)) {
            dd.classList.add('hidden');
        }
    });
}

function initSliderToggle() {
    const track = document.getElementById('runSliderTrack');
    const btnQuick = document.getElementById('btnQuickRun');
    const btnComp = document.getElementById('btnComprehensive');
    const panelQuick = document.getElementById('quick-run-fields');
    const panelComp = document.getElementById('comprehensive-fields');

    function moveTrackTo(btn) {
        track.style.left  = btn.offsetLeft + 'px';
        track.style.width = btn.offsetWidth + 'px';
    }

    function clearTabContainer(containerEl) {
        if (!containerEl) return;

        containerEl.querySelectorAll('input, select, textarea').forEach(el => {
            const tag = el.tagName.toLowerCase();
            const inputType = (el.type || '').toLowerCase();

            if (tag === 'select') {
                el.selectedIndex = 0;
                return;
            }

            if (tag === 'input' && (inputType === 'checkbox' || inputType === 'radio')) {
                el.checked = false;
                return;
            }

            // Covers text, number, and any free-text field variants.
            if (tag === 'textarea' || tag === 'input') {
                el.value = '';
            }
        });
    }

    function clearLeavingTab(mode) {
        if (mode === 'quick') {
            clearTabContainer(panelQuick);
            state.qrWorkflow = '';
            state.qrRunCount = '';
            document.getElementById('errQrRunCount').classList.add('hidden');
            return;
        }

        clearTabContainer(panelComp);
        state.coWorkflow = '';
        state.coRunCount = '';
        state.coCheckout = false;
        state.coProvisionSetup = [];
        document.getElementById('errCoRunCount').classList.add('hidden');
        document.getElementById('errProvisionFormat').classList.add('hidden');
        renderProvisionTags();
    }

    function setMode(mode) {
        const leavingMode = state.runOptionsMode;

        if (leavingMode && leavingMode !== mode) {
            clearLeavingTab(leavingMode);
        }

        state.runOptionsMode = mode;
        if (mode === 'quick') {
            btnQuick.classList.add('active');
            btnComp.classList.remove('active');
            panelQuick.classList.remove('hidden');
            panelComp.classList.add('hidden');
            moveTrackTo(btnQuick);
        } else {
            btnComp.classList.add('active');
            btnQuick.classList.remove('active');
            panelComp.classList.remove('hidden');
            panelQuick.classList.add('hidden');
            moveTrackTo(btnComp);
        }
    }

    requestAnimationFrame(() => setMode('quick'));
    btnQuick.addEventListener('click', () => setMode('quick'));
    btnComp.addEventListener('click', () => setMode('comprehensive'));
}

function getActiveRunContainer() {
    if (state.runOptionsMode === 'comprehensive') {
        return document.getElementById('comprehensive-fields');
    }
    return document.getElementById('quick-run-fields');
}

function getActiveRunFields() {
    const isQuick = state.runOptionsMode === 'quick';
    const container = getActiveRunContainer();

    const workflowInput = container.querySelector('input[id$="Workflow"]');
    const runCountInput = container.querySelector('input[id$="RunCount"]');

    const runCount = parseInt((runCountInput?.value || '').trim(), 10);
    if (!runCountInput || !runCountInput.value.trim() || Number.isNaN(runCount) || runCount <= 0) {
        document.getElementById(isQuick ? 'errQrRunCount' : 'errCoRunCount').classList.remove('hidden');
        return null;
    }

    document.getElementById(isQuick ? 'errQrRunCount' : 'errCoRunCount').classList.add('hidden');

    if (!isQuick) {
        const pendingProvisionInput = (container.querySelector('#coProvisionSetup')?.value || '').trim();
        if (pendingProvisionInput) {
            const ok = tryAddProvision(pendingProvisionInput);
            if (!ok) return null;
        }
    }

    const provisionSetup = isQuick ? '' : state.coProvisionSetup.join(',');
    const doCheckoutUpdate = isQuick ? false : Boolean(container.querySelector('#coCheckout')?.checked);

    return {
        run_type: isQuick ? 'quick' : 'comprehensive',
        workflow: workflowInput?.value?.trim() || '',
        run_count: runCount,
        provision_setup: provisionSetup,
        do_checkout_update: doCheckoutUpdate,
    };
}

function buildRunPayloadFromActiveTab() {
    const activeFields = getActiveRunFields();
    if (!activeFields) return null;

    return {
        bug_id: String(state.bugToRepro.bug_id || '').trim(),
        run_mode: state.runMode,
        test_name: state.selectedTests,
        station_name: state.selectedStation,
        run_type: activeFields.run_type,
        workflow: activeFields.workflow,
        run_count: activeFields.run_count,
        provision_setup: activeFields.provision_setup,
        do_checkout_update: activeFields.do_checkout_update,
    };
}

async function handleRunSubmit() {
    if (!validateSelections()) return;
    const sameBugStation = runHistory.some(r =>
        r.bug_id === state.bugToRepro?.bug_id &&
        r.station_name === state.selectedStation
    );
    if (sameBugStation) {
        showToast('A run for this bug on this station already exists.', 'error');
        return;
    }
    if (!validateBugAndTests()) return;

    const payload = buildRunPayloadFromActiveTab();
    if (!payload) return;

    await submitRun(payload);
}

// ═══════════════════════════════════════════
// SECTION 4A — Quick Run
// ═══════════════════════════════════════════
function initQuickRun() {
    document.getElementById('qrWorkflow').addEventListener('input', e => {
        state.qrWorkflow = e.target.value;
    });

    const rcInput = document.getElementById('qrRunCount');
    rcInput.addEventListener('input', () => {
        rcInput.value = rcInput.value.replace(/[^0-9]/g, '');
        state.qrRunCount = rcInput.value;
        document.getElementById('errQrRunCount').classList.add('hidden');
    });

    document.getElementById('btnQuickRunSubmit').addEventListener('click', handleRunSubmit);
}

// ═══════════════════════════════════════════
// SECTION 4B — Comprehensive Options
// ═══════════════════════════════════════════

/**
 * Provision setup validation:
 * - The raw value entered by the user must end with '.star'
 * - If it does → add the value directly to the table without any changes
 * - If it doesn't → show an error, do not add the item
 */
function tryAddProvision(rawVal) {
    const val = rawVal.trim();
    if (!val) return true;

    const errEl = document.getElementById('errProvisionFormat');

    // Check: value must end with .star
    if (!val.endsWith('.star')) {
        errEl.classList.remove('hidden');
        setTimeout(() => errEl.classList.add('hidden'), 3500);
        return false;
    }

    errEl.classList.add('hidden');

    // Add the value directly without any changes
    if (!state.coProvisionSetup.includes(val)) {
        state.coProvisionSetup.push(val);
        renderProvisionTags();
    }

    document.getElementById('coProvisionSetup').value = '';
    return true;
}

function initComprehensive() {
    document.getElementById('coWorkflow').addEventListener('input', e => {
        state.coWorkflow = e.target.value;
    });

    const rcInput = document.getElementById('coRunCount');
    rcInput.addEventListener('input', () => {
        rcInput.value = rcInput.value.replace(/[^0-9]/g, '');
        state.coRunCount = rcInput.value;
        document.getElementById('errCoRunCount').classList.add('hidden');
    });

    // Provision Setup — validate and add on Enter
    const provInput = document.getElementById('coProvisionSetup');
    provInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            tryAddProvision(provInput.value);
        }
    });

    document.getElementById('coCheckout').addEventListener('change', e => {
        state.coCheckout = e.target.checked;
    });

    document.getElementById('btnComprehensiveSubmit').addEventListener('click', handleRunSubmit);
}

function renderProvisionTags() {
    const container = document.getElementById('provisionTags');
    container.innerHTML = state.coProvisionSetup.map(v => `
        <span class="run-provision-tag">
            ${esc(v)}
            <button class="run-provision-remove" data-val="${esc(v)}" type="button">×</button>
        </span>
    `).join('');
    container.querySelectorAll('.run-provision-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            state.coProvisionSetup = state.coProvisionSetup.filter(x => x !== btn.dataset.val);
            renderProvisionTags();
        });
    });
}

// ═══════════════════════════════════════════
// Validation
// ═══════════════════════════════════════════
function validateBugAndTests() {
    let ok = true;
    if (!state.bugToRepro) {
        document.getElementById('errBugRepro').classList.remove('hidden');
        ok = false;
    }
    if (state.selectedTests.length === 0) {
        document.getElementById('errTestRun').classList.remove('hidden');
        ok = false;
    }
    if (!state.selectedStation) {
        document.getElementById('errStationRun').classList.remove('hidden');
        ok = false;
    }
    return ok;
}

function validateSelections() {
    const bug = state.bugToRepro?.bug_id;
    const station = state.selectedStation;
    const tests = state.selectedTests;

    // Case 1: Station == Test
    if (tests.map(t => t.toLowerCase()).includes(station.toLowerCase())) {
        showToast("Station and Test cannot be the same", "error");
        return false;
    }

    // Case 2: Bug == Station
    if (bug === station) {
        showToast("Bug and Station cannot be the same", "error");
        return false;
    }

    return true;
}

// ═══════════════════════════════════════════
// Submit run
// ═══════════════════════════════════════════
async function submitRun(payload) {
    try {
        const response = await fetch(`${API_BASE}/api/runs`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            credentials: 'include',
            body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            const msg = data.error || data.message || `Run submit failed (HTTP ${response.status})`;
            showToast(msg, 'error');
            return;
        }

        await loadRunHistory();
        resetPage();
        showToast(data.message || 'Run submitted successfully!', 'success');
    } catch (err) {
        console.warn('[Run] submit failed', err);
        showToast('Could not reach the server. Please try again.', 'error');
    }
}

// ═══════════════════════════════════════════
// Reset page
// ═══════════════════════════════════════════
function resetPage() {
    state.runMode = 'run_tests';
    document.getElementById('radio-run-tests').checked = true;

    state.bugToRepro = null;
    bugTests = [];
    stationOptions = [];
    state.selectedTests = [];
    state.selectedStation = '';
    document.getElementById('bugReproInput').value = '';
    document.getElementById('bugReproDropdown').classList.add('hidden');
    document.getElementById('errBugRepro').classList.add('hidden');
    renderSelectedTags();
    renderSelectedStationTags();
    document.getElementById('testRunInput').value = '';
    document.getElementById('testRunDropdown').classList.add('hidden');
    document.getElementById('stationRunInput').value = '';
    document.getElementById('stationRunDropdown').classList.add('hidden');
    hideAllTestErrors();
    hideAllStationErrors();

    document.getElementById('btnQuickRun').click();

    state.qrWorkflow = '';
    state.qrRunCount = '';
    document.getElementById('qrWorkflow').value = '';
    document.getElementById('qrRunCount').value = '';
    document.getElementById('errQrRunCount').classList.add('hidden');

    state.coWorkflow = '';
    state.coRunCount = '';
    state.coProvisionSetup = [];
    state.coCheckout = false;
    document.getElementById('coWorkflow').value = '';
    document.getElementById('coRunCount').value = '';
    document.getElementById('coProvisionSetup').value = '';
    document.getElementById('coCheckout').checked = false;
    document.getElementById('errCoRunCount').classList.add('hidden');
    renderProvisionTags();

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ═══════════════════════════════════════════
// Navbar
// ═══════════════════════════════════════════
async function initNavbar() {
    const data = await apiFetch('/api/auth/me');
    if (data) {
        const initials = (data.fullName || data.name || '?')
            .split(' ').map(p => p[0]).join('').slice(0, 2).toUpperCase();
        document.getElementById('userAvatar').textContent = initials;
        document.getElementById('userAvatar').classList.remove('loading-pulse');
        document.getElementById('userName').textContent = data.fullName || data.name;
        document.getElementById('userName').classList.remove('loading-text');
        document.getElementById('userRoleBadge').textContent = data.role || 'Engineer';
        document.getElementById('profileEmail').textContent = data.email || '';
    }

    const trigger = document.getElementById('profileDropdownTrigger');
    const dropdown = document.getElementById('profileDropdown');
    trigger.addEventListener('click', e => {
        e.stopPropagation();
        dropdown.classList.toggle('hidden');
    });
    document.addEventListener('click', () => dropdown.classList.add('hidden'));

    document.getElementById('btnLogout').addEventListener('click', async () => {
        await apiFetch('/api/auth/logout', { method: 'POST' });
        if (window.RROAuth) window.RROAuth.clearToken();
        window.location.href = '/';
    });
}

// ═══════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════
window.addEventListener('DOMContentLoaded', async () => {
    await initNavbar();
    await loadAllBugs();
    await loadAllStations();
    await loadRunHistory();

    initRunMode();
    initBugReproCombobox();
    initTestRunCombobox();
    initStationRunCombobox();
    initSliderToggle();
    initQuickRun();
    initComprehensive();
});
