/**
 * RRO Run Page — JavaScript
 * Handles all interactivity for the Run page.
 */

const API_BASE = '';

// ── State variables (all form values stored here) ──
const state = {
    runMode: 'run_tests',          // 'run_tests' or 'config_and_execute'
    bugToRepro: null,              // { id, bug_code, bug_name } of selected bug
    selectedTests: [],             // array of test name strings chosen by user
    runOptionsMode: null,          // 'quick' or 'comprehensive'
    // Quick Run
    qrWorkflow: '',
    qrRunCount: '',
    // Comprehensive
    coWorkflow: '',
    coRunCount: '',
    coProvisionSetup: [],          // array of strings (each has ★ appended on display)
    coCheckout: false,
};

// All test names in the system (for duplicate check when adding custom test)
let allSystemTestNames = [];
// Tests belonging to the currently selected bug
let bugTests = [];
// All bugs in the system (for the Bug to Repro combobox)
let allBugs = [];

// ── Auth helpers ──
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

// ── Escape HTML to prevent XSS ──
function esc(str) {
    const d = document.createElement('div');
    d.textContent = str ?? '';
    return d.innerHTML;
}

// ── Toast ──
function showToast(msg, type = 'success') {
    const t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg;
    t.className = `toast show ${type}`;
    setTimeout(() => { t.className = 'toast'; }, 3500);
}

// ═══════════════════════════════════════════
// SECTION 1 — Run Mode radio buttons
// ═══════════════════════════════════════════
function initRunMode() {
    document.querySelectorAll('input[name="runMode"]').forEach(radio => {
        radio.addEventListener('change', () => {
            state.runMode = radio.value;
            console.log('[State] runMode =', state.runMode);
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
            <div class="run-dropdown-item" data-bug-id="${b.db_id}" data-bug-code="${esc(b.id)}" data-bug-name="${esc(b.bug_name || '')}">
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
        db_id: item.dataset.bugId,
        bug_code: item.dataset.bugCode,
        bug_name: item.dataset.bugName,
    };
    document.getElementById('bugReproInput').value = item.dataset.bugCode;
    document.getElementById('bugReproDropdown').classList.add('hidden');
    document.getElementById('errBugRepro').classList.add('hidden');
    console.log('[State] bugToRepro =', state.bugToRepro);

    // Reset selected tests since bug changed
    state.selectedTests = [];
    renderSelectedTags();
    // Load tests for this bug
    loadBugTests(item.dataset.bugId);
}

async function loadBugTests(dbId) {
    bugTests = [];
    const data = await apiFetch(`/api/bugs/${dbId}/tests`);
    if (data && Array.isArray(data.tests)) {
        bugTests = data.tests.map(t => t.test_name).filter(Boolean);
    }
    console.log('[State] bugTests for bug', dbId, '=', bugTests);
}

function initBugReproCombobox() {
    const input = document.getElementById('bugReproInput');
    const dd = document.getElementById('bugReproDropdown');

    input.addEventListener('input', () => {
        const q = input.value.trim();
        clearTimeout(bugDebounce);
        if (!q) { dd.classList.add('hidden'); return; }
        bugDebounce = setTimeout(() => {
            // Filter from already loaded allBugs
            const lower = q.toLowerCase();
            const filtered = allBugs.filter(b =>
                b.id.toLowerCase().includes(lower) ||
                (b.bug_name || '').toLowerCase().includes(lower)
            ).slice(0, 8);
            renderBugDropdown(filtered, q);
        }, 200);
    });

    input.addEventListener('focus', () => {
        const q = input.value.trim();
        if (q) input.dispatchEvent(new Event('input'));
    });

    // Clear selection if user clears the field
    input.addEventListener('change', () => {
        if (!input.value.trim()) {
            state.bugToRepro = null;
            bugTests = [];
            state.selectedTests = [];
            renderSelectedTags();
        }
    });

    // Close dropdown on outside click
    document.addEventListener('click', e => {
        if (!document.getElementById('bugReproCombobox').contains(e.target)) {
            dd.classList.add('hidden');
        }
    });
}

async function loadAllBugs() {
    const data = await apiFetch('/api/bugs');
    if (!data) return;
    allBugs = [...(data.repro || []), ...(data.test || [])];
    // Collect all test names for duplicate validation
    allSystemTestNames = [];
    allBugs.forEach(b => {
        if (Array.isArray(b.tests)) allSystemTestNames.push(...b.tests);
    });
    console.log('[State] allBugs loaded:', allBugs.length, 'bugs');
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
            console.log('[State] selectedTests =', state.selectedTests);
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

    // Offer "Add custom test" if query doesn't exactly match an existing test
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
    // Validation: bug must be selected first
    if (!state.bugToRepro) {
        showError('errNoBug');
        document.getElementById('testRunDropdown').classList.add('hidden');
        return;
    }

    // Duplicate check for custom additions
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
        console.log('[State] selectedTests =', state.selectedTests);
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
        if (!state.bugToRepro) {
            showError('errNoBug');
            return;
        }
        renderTestDropdown(bugTests, input.value.trim());
    });

    input.addEventListener('input', () => {
        if (!state.bugToRepro) {
            showError('errNoBug');
            return;
        }
        clearTimeout(testDebounce);
        testDebounce = setTimeout(() => {
            const q = input.value.trim().toLowerCase();
            const filtered = q
                ? bugTests.filter(t => t.toLowerCase().includes(q))
                : bugTests;
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
function initSliderToggle() {
    const track = document.getElementById('runSliderTrack');
    const btnQuick = document.getElementById('btnQuickRun');
    const btnComp = document.getElementById('btnComprehensive');
    const panelQuick = document.getElementById('panelQuickRun');
    const panelComp = document.getElementById('panelComprehensive');
    const hint = document.getElementById('sliderHint');

    // Move the white pill to sit exactly under whichever button is active.
    // We measure the button's real offsetLeft and offsetWidth so any
    // text length ("Quick Run" vs "Comprehensive Options") works correctly.
    function moveTrackTo(btn) {
        track.style.left  = btn.offsetLeft + 'px';
        track.style.width = btn.offsetWidth + 'px';
    }

    function setMode(mode) {
        state.runOptionsMode = mode;
        console.log('[State] runOptionsMode =', mode);

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
        hint.style.display = 'none';
    }

    // Use requestAnimationFrame so the buttons are fully painted before we
    // measure offsetWidth — measuring before first paint returns 0.
    requestAnimationFrame(() => setMode('quick'));

    btnQuick.addEventListener('click', () => setMode('quick'));
    btnComp.addEventListener('click', () => setMode('comprehensive'));
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
        // Allow only digits
        rcInput.value = rcInput.value.replace(/[^0-9]/g, '');
        state.qrRunCount = rcInput.value;
        document.getElementById('errQrRunCount').classList.add('hidden');
    });

    document.getElementById('btnQuickRunSubmit').addEventListener('click', async () => {
        // Validate run count
        const count = parseInt(state.qrRunCount, 10);
        if (!state.qrRunCount || isNaN(count) || count <= 0) {
            document.getElementById('errQrRunCount').classList.remove('hidden');
            return;
        }
        document.getElementById('errQrRunCount').classList.add('hidden');
        // Validate bug and tests
        if (!validateBugAndTests()) return;

        const payload = {
            runMode: state.runMode,
            bugToRepro: state.bugToRepro,
            selectedTests: state.selectedTests,
            runOptionsMode: 'quick',
            workflow: state.qrWorkflow,
            runCount: count,
        };
        await submitRun(payload);
    });
}

// ═══════════════════════════════════════════
// SECTION 4B — Comprehensive Options
// ═══════════════════════════════════════════
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

    // Provision Setup — add on Enter
    const provInput = document.getElementById('coProvisionSetup');
    provInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const val = provInput.value.trim();
            if (val && !state.coProvisionSetup.includes(val)) {
                state.coProvisionSetup.push(val);
                renderProvisionTags();
                console.log('[State] coProvisionSetup =', state.coProvisionSetup);
            }
            provInput.value = '';
        }
    });

    // Checkout toggle
    document.getElementById('coCheckout').addEventListener('change', e => {
        state.coCheckout = e.target.checked;
        console.log('[State] coCheckout =', state.coCheckout);
    });

    document.getElementById('btnComprehensiveSubmit').addEventListener('click', async () => {
        const count = parseInt(state.coRunCount, 10);
        if (!state.coRunCount || isNaN(count) || count <= 0) {
            document.getElementById('errCoRunCount').classList.remove('hidden');
            return;
        }
        document.getElementById('errCoRunCount').classList.add('hidden');
        // Validate bug and tests
        if (!validateBugAndTests()) return;

        const payload = {
            runMode: state.runMode,
            bugToRepro: state.bugToRepro,
            selectedTests: state.selectedTests,
            runOptionsMode: 'comprehensive',
            workflow: state.coWorkflow,
            runCount: count,
            provisionSetup: state.coProvisionSetup.map(v => v + ' ★'),
            doCheckout: state.coCheckout,
        };
        await submitRun(payload);
    });
}

function renderProvisionTags() {
    const container = document.getElementById('provisionTags');
    container.innerHTML = state.coProvisionSetup.map(v => `
        <span class="run-provision-tag">
            ${esc(v)} ★
            <button class="run-provision-remove" data-val="${esc(v)}" type="button">×</button>
        </span>
    `).join('');
    container.querySelectorAll('.run-provision-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            state.coProvisionSetup = state.coProvisionSetup.filter(x => x !== btn.dataset.val);
            renderProvisionTags();
            console.log('[State] coProvisionSetup =', state.coProvisionSetup);
        });
    });
}

// ═══════════════════════════════════════════
// Validation helper — checks bug + tests before submit
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
    return ok;
}

// ═══════════════════════════════════════════
// Submit run — POST /api/run/submit
// Logs the JSON payload and resets the page
// ═══════════════════════════════════════════
async function submitRun(payload) {
    console.log('[Run] Submitting payload:', JSON.stringify(payload, null, 2));

    const data = await apiFetch('/api/run/submit', {
        method: 'POST',
        body: JSON.stringify(payload),
    });

    if (!data) {
        showToast('Could not reach the server. Check console.', 'error');
        return;
    }

    // Log what the server echoed back
    console.log('[Run] Server response:', JSON.stringify(data, null, 2));

    // Reset the entire page back to its initial state
    resetPage();
    showToast('Run submitted successfully!');
}

// ═══════════════════════════════════════════
// Reset page to initial state after submit
// ═══════════════════════════════════════════
function resetPage() {
    // Section 1 — run mode back to default
    state.runMode = 'run_tests';
    document.getElementById('radio-run-tests').checked = true;

    // Section 2 — clear bug selection and tests
    state.bugToRepro = null;
    bugTests = [];
    state.selectedTests = [];
    document.getElementById('bugReproInput').value = '';
    document.getElementById('bugReproDropdown').classList.add('hidden');
    document.getElementById('errBugRepro').classList.add('hidden');
    renderSelectedTags();
    document.getElementById('testRunInput').value = '';
    document.getElementById('testRunDropdown').classList.add('hidden');
    hideAllTestErrors();

    // Section 3 — reset slider back to Quick Run
    // Re-call initSliderToggle logic by clicking the Quick Run button
    document.getElementById('btnQuickRun').click();

    // Section 4A — clear Quick Run fields
    state.qrWorkflow = '';
    state.qrRunCount = '';
    document.getElementById('qrWorkflow').value = '';
    document.getElementById('qrRunCount').value = '';
    document.getElementById('errQrRunCount').classList.add('hidden');

    // Section 4B — clear Comprehensive fields
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

    // Scroll back to top of page
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ═══════════════════════════════════════════
// Navbar: user info + logout
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

    initRunMode();
    initBugReproCombobox();
    initTestRunCombobox();
    initSliderToggle();
    initQuickRun();
    initComprehensive();
});
