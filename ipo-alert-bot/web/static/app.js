// State
const BASE_PATH = window.BASE_PATH || '';
let currentSettings = {};
let allIpos = [];
let currentStatusFilter = 'high-gmp';
let currentBoardFilter = 'mainboard';
let hideClosedAndPast = false;
let currentTab = 'market';

// Initialization
document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  loadIpos();
  loadMuted();
  loadLogs();
});

// Toast notification helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tab Switching
function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.tab-btn').forEach((btn, idx) => {
    btn.classList.remove('active');
  });
  event.target.classList.add('active');

  document.getElementById('tab-market').style.display = tabId === 'market' ? 'block' : 'none';
  document.getElementById('tab-muted').style.display = tabId === 'muted' ? 'block' : 'none';
  document.getElementById('tab-logs').style.display = tabId === 'logs' ? 'block' : 'none';

  if (tabId === 'muted') loadMuted();
  if (tabId === 'logs') loadLogs();
}

function refreshCurrentTab() {
  if (currentTab === 'market') loadIpos(true);
  else if (currentTab === 'muted') loadMuted();
  else if (currentTab === 'logs') loadLogs();
}

// Settings & Status
async function loadSettings() {
  try {
    const res = await fetch(`${BASE_PATH}/api/settings`);
    if (res.status === 401) {
      window.location.href = BASE_PATH ? `${BASE_PATH}/login` : '/login';
      return;
    }
    currentSettings = await res.json();

    const isEnabled = currentSettings.is_enabled === '1' || currentSettings.is_enabled === 'true';
    updateStatusUI(isEnabled, currentSettings.last_check_status);

    const scheduleStat = document.getElementById('stat-schedule-text');
    if (scheduleStat && currentSettings.schedule_times) {
      const times = currentSettings.schedule_times.split(',').map(t => t.trim()).filter(Boolean);
      const nextTime = currentSettings.schedule_info?.next_fire_time;
      scheduleStat.innerText = times.length > 0 ? `${times.length}x Daily` : 'Manual';
      if (nextTime) {
        scheduleStat.title = `Next scheduled check: ${nextTime} IST`;
      }
    }
  } catch (err) {
    console.error('Failed to load settings', err);
  }
}

function updateStatusUI(isEnabled, lastStatus) {
  const pill = document.getElementById('master-status-pill');
  const text = document.getElementById('master-status-text');
  if (pill && text) {
    if (isEnabled) {
      pill.className = 'status-pill active';
      text.innerText = 'Bot Active';
    } else {
      pill.className = 'status-pill paused';
      text.innerText = 'Bot Paused';
    }
  }

  const lastCheckLabel = document.getElementById('last-check-status-label');
  if (lastCheckLabel && lastStatus) {
    lastCheckLabel.innerText = lastStatus;
  }
}

async function runCheckNow() {
  showToast('Executing IPO check & dispatch...', 'info');
  try {
    const res = await fetch(`${BASE_PATH}/api/trigger-check`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      loadSettings();
      loadLogs();
      loadIpos(true);
    } else {
      showToast(data.detail || 'Error running check', 'error');
    }
  } catch (err) {
    showToast('Failed to trigger check', 'error');
  }
}

// Sorting State
let sortColumn = 'gmp';
let sortDirection = 'desc';

// Live IPO Market Explorer
async function loadIpos(force = false) {
  const tbody = document.getElementById('ipos-table-body');
  try {
    const res = await fetch(`${BASE_PATH}/api/ipos?force=${force}`);
    const data = await res.json();
    allIpos = data.ipos || [];

    // Calculate quick stats
    const openCount = allIpos.filter(i => i.is_open).length;
    const thresh = parseFloat(currentSettings.gmp_threshold || 15.0);
    const highGmpCount = allIpos.filter(i => i.is_open && i.gmp_percent >= thresh).length;

    document.getElementById('stat-open-count').innerText = openCount;
    document.getElementById('stat-high-gmp-count').innerText = highGmpCount;

    updateFilterCounts();
    updateFilterUI();
    renderIposTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Failed to load live IPO data.</td></tr>`;
  }
}

function isClosedOrPast(ipo) {
  const st = (ipo.status || '').toUpperCase();
  return st === 'CLOSED' || st === 'LISTED_PAST' || st.includes('PAST');
}

function isClosingToday(ipo) {
  return Boolean(ipo && (ipo.is_closing_today || (ipo.status || '').toUpperCase() === 'CLOSING_TODAY'));
}

function matchesStatus(ipo, statusFilter, thresh) {
  if (statusFilter === 'all') return true;
  if (statusFilter === 'open') return Boolean(ipo.is_open);
  if (statusFilter === 'closing') return isClosingToday(ipo);
  if (statusFilter === 'high-gmp') return Boolean(ipo.is_open && ipo.gmp_percent >= thresh);
  return true;
}

function matchesBoard(ipo, boardFilter) {
  const isSme = (ipo.category || '').toUpperCase() === 'SME';
  if (boardFilter === 'all') return true;
  if (boardFilter === 'mainboard') return !isSme;
  if (boardFilter === 'sme') return isSme;
  return true;
}

function updateHideClosedUI() {
  const btn = document.getElementById('btn-hide-closed');
  const icon = document.getElementById('hide-closed-icon');
  const text = document.getElementById('hide-closed-text');
  const count = document.getElementById('hide-closed-count');
  if (!btn) return;

  const closedPastTotal = allIpos.filter(isClosedOrPast).length;

  if (hideClosedAndPast) {
    btn.classList.add('active');
    if (icon) icon.innerText = '🚫';
    if (text) text.innerText = 'Hiding Closed / Listed Past';
    if (count) count.innerText = `${closedPastTotal} hidden`;
  } else {
    btn.classList.remove('active');
    if (icon) icon.innerText = '👁️';
    if (text) text.innerText = 'Hide Closed / Listed Past';
    if (count) count.innerText = closedPastTotal;
  }
}

function toggleHideClosed() {
  hideClosedAndPast = !hideClosedAndPast;
  updateHideClosedUI();
  renderIposTable();
}

function updateFilterCounts() {
  const thresh = parseFloat(currentSettings.gmp_threshold || 15.0);
  
  // Status counts
  const countAll = allIpos.length;
  const countOpen = allIpos.filter(i => i.is_open).length;
  const countClosing = allIpos.filter(isClosingToday).length;
  const countHighGmp = allIpos.filter(i => i.is_open && i.gmp_percent >= thresh).length;

  const elAll = document.getElementById('count-all');
  if (elAll) elAll.innerText = countAll;
  const elOpen = document.getElementById('count-open');
  if (elOpen) elOpen.innerText = countOpen;
  const elClosing = document.getElementById('count-closing');
  if (elClosing) elClosing.innerText = countClosing;
  const elHigh = document.getElementById('count-high-gmp');
  if (elHigh) elHigh.innerText = countHighGmp;

  // Board counts scoped to active status filter pool
  const statusPool = allIpos.filter(i => matchesStatus(i, currentStatusFilter, thresh));
  const countBoardAll = statusPool.length;
  const countMain = statusPool.filter(i => (i.category || '').toUpperCase() !== 'SME').length;
  const countSme = statusPool.filter(i => (i.category || '').toUpperCase() === 'SME').length;

  const elBoardAll = document.getElementById('count-board-all');
  if (elBoardAll) elBoardAll.innerText = countBoardAll;
  const elMain = document.getElementById('count-main');
  if (elMain) elMain.innerText = countMain;
  const elSme = document.getElementById('count-sme');
  if (elSme) elSme.innerText = countSme;

  updateHideClosedUI();
}

function updateFilterUI() {
  // Highlight active status pill
  document.querySelectorAll('#status-pills-bar .filter-btn').forEach(b => b.classList.remove('active'));
  const statusBtnMap = {
    'all': 'filter-btn-all',
    'open': 'filter-btn-open',
    'closing': 'filter-btn-closing',
    'high-gmp': 'filter-btn-high-gmp'
  };
  const activeStatusBtn = document.getElementById(statusBtnMap[currentStatusFilter]);
  if (activeStatusBtn) activeStatusBtn.classList.add('active');

  // Highlight active board pill
  document.querySelectorAll('#board-pills-bar .filter-btn').forEach(b => b.classList.remove('active'));
  const boardBtnMap = {
    'all': 'filter-btn-board-all',
    'mainboard': 'filter-btn-main',
    'sme': 'filter-btn-sme'
  };
  const activeBoardBtn = document.getElementById(boardBtnMap[currentBoardFilter]);
  if (activeBoardBtn) activeBoardBtn.classList.add('active');
}

function setStatusFilter(status) {
  currentStatusFilter = status;
  updateFilterUI();
  updateFilterCounts();
  renderIposTable();
}

function setBoardFilter(board) {
  currentBoardFilter = board;
  updateFilterUI();
  renderIposTable();
}

function setTableFilter(filter) {
  if (['all', 'open', 'closing', 'high-gmp'].includes(filter)) {
    setStatusFilter(filter);
  } else if (['mainboard', 'sme'].includes(filter)) {
    setBoardFilter(filter);
  }
}

function parseDateForSort(displayVal, isoVal) {
  if (isoVal && isoVal.length >= 8) {
    const t = Date.parse(isoVal);
    if (!isNaN(t)) return t;
  }
  if (!displayVal || displayVal === 'TBA' || displayVal === '-') {
    return 0;
  }
  const clean = String(displayVal).replace(/[^\w-]/g, '').trim();
  const parts = clean.split('-');
  if (parts.length >= 2) {
    const day = parseInt(parts[0], 10);
    const monthNames = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"];
    const monthIdx = monthNames.indexOf(parts[1].toLowerCase().slice(0, 3));
    if (!isNaN(day) && monthIdx !== -1) {
      const year = parts[2] ? parseInt(parts[2], 10) : new Date().getFullYear();
      return new Date(year, monthIdx, day).getTime();
    }
  }
  const fallback = Date.parse(displayVal);
  return isNaN(fallback) ? 0 : fallback;
}

function updateSortHeaders() {
  const sortCols = [
    { id: 'name', thId: 'th-name', iconId: 'sort-icon-name' },
    { id: 'start_date', thId: 'th-start-date', iconId: 'sort-icon-start-date' },
    { id: 'end_date', thId: 'th-end-date', iconId: 'sort-icon-end-date' },
    { id: 'gmp', thId: 'th-gmp', iconId: 'sort-icon-gmp' },
    { id: 'demand', thId: 'th-demand', iconId: 'sort-icon-demand' },
    { id: 'order', thId: 'th-order', iconId: 'sort-icon-order' }
  ];

  sortCols.forEach(c => {
    const th = document.getElementById(c.thId);
    const icon = document.getElementById(c.iconId);
    if (!th || !icon) return;
    
    if (c.id === sortColumn) {
      th.classList.add('active-sort');
      icon.innerText = (sortDirection === 'asc' ? '▲' : '▼');
    } else {
      th.classList.remove('active-sort');
      icon.innerText = '↕';
    }
  });

  const select = document.getElementById('mobile-sort-select');
  if (select) {
    const targetVal = `${sortColumn}_${sortDirection}`;
    for (let opt of select.options) {
      if (opt.value === targetVal) {
        select.value = targetVal;
        break;
      }
    }
  }
}

function handleSort(col) {
  if (sortColumn === col) {
    sortDirection = (sortDirection === 'asc' ? 'desc' : 'asc');
  } else {
    sortColumn = col;
    sortDirection = (col === 'name' ? 'asc' : 'desc');
  }

  updateSortHeaders();
  renderIposTable();
}

function handleMobileSortChange(val) {
  const parts = val.split('_');
  const dir = parts.pop();
  const col = parts.join('_');
  sortColumn = col;
  sortDirection = dir;

  updateSortHeaders();
  renderIposTable();
}

function renderIposTable() {
  const tbody = document.getElementById('ipos-table-body');
  const thresh = parseFloat(currentSettings.gmp_threshold || 15.0);

  // 1. Status Filter
  let filtered = allIpos.filter(i => matchesStatus(i, currentStatusFilter, thresh));

  // 2. Board Filter
  filtered = filtered.filter(i => matchesBoard(i, currentBoardFilter));

  // 3. Layered Filter: Hide Closed & Past Listed IPOs
  let hiddenInView = 0;
  if (hideClosedAndPast) {
    const beforeCount = filtered.length;
    filtered = filtered.filter(i => !isClosedOrPast(i));
    hiddenInView = beforeCount - filtered.length;
  }

  const statusLabels = {
    'all': 'All Statuses',
    'open': 'Open',
    'closing': 'Ending Today',
    'high-gmp': 'High GMP (>15%)'
  };
  const boardLabels = {
    'all': 'All Boards',
    'mainboard': 'Mainboard',
    'sme': 'SME'
  };
  const filterDesc = `${statusLabels[currentStatusFilter] || currentStatusFilter} > ${boardLabels[currentBoardFilter] || currentBoardFilter}`;

  // Update feedback text
  const feedbackEl = document.getElementById('filter-feedback-text');
  if (feedbackEl) {
    const colLabel = sortColumn.replace('_', ' ').toUpperCase();
    const extraNote = hideClosedAndPast
      ? ` • <span style="color: #fca5a5; font-weight: 600;">🚫 ${hiddenInView} Closed / Past Listed hidden</span>`
      : '';
    feedbackEl.innerHTML = `Showing <b>${filtered.length}</b> IPOs (${filterDesc} • Sorted by <b>${colLabel}</b> ${sortDirection.toUpperCase()})${extraNote}`;
  }

  const cardsContainer = document.getElementById('ipos-cards-container');

  if (filtered.length === 0) {
    const reason = hideClosedAndPast ? ` (Closed &amp; Past Listed are hidden)` : '';
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No IPOs match the current filters: <b>${filterDesc}</b>${reason}.</td></tr>`;
    if (cardsContainer) {
      cardsContainer.innerHTML = `<div class="empty-state">No IPOs match the current filters: <b>${filterDesc}</b>${reason}.</div>`;
    }
    return;
  }

  // 2. Sort
  filtered = [...filtered].sort((a, b) => {
    let res = 0;
    if (sortColumn === 'name') {
      res = (a.name || '').localeCompare(b.name || '');
    } else if (sortColumn === 'gmp') {
      res = (a.gmp_percent || 0) - (b.gmp_percent || 0);
    } else if (sortColumn === 'start_date') {
      const tA = parseDateForSort(a.start_date, a.start_date_sort);
      const tB = parseDateForSort(b.start_date, b.start_date_sort);
      res = tA - tB;
    } else if (sortColumn === 'end_date') {
      const tA = parseDateForSort(a.end_date, a.end_date_sort);
      const tB = parseDateForSort(b.end_date, b.end_date_sort);
      res = tA - tB;
    } else if (sortColumn === 'demand') {
      const getNum = (str) => {
        const m = (str || '').match(/[\d\.]+/);
        return m ? parseFloat(m[0]) : 0;
      };
      res = getNum(a.total_sub) - getNum(b.total_sub);
    } else if (sortColumn === 'order') {
      const amtA = (a.cutoff_price || 0) * (a.lot_size || 0);
      const amtB = (b.cutoff_price || 0) * (b.lot_size || 0);
      res = amtA - amtB;
    }
    return sortDirection === 'asc' ? res : -res;
  });

  // Render Desktop Table Rows
  tbody.innerHTML = filtered.map(ipo => {
    const isSme = (ipo.category || '').toUpperCase() === 'SME';
    const catBadge = isSme ? `<span class="badge badge-sme">SME</span>` : `<span class="badge badge-main">Main</span>`;
    
    let statusBadge = `<span class="badge badge-closed">${ipo.status}</span>`;
    if (isClosingToday(ipo)) {
      statusBadge = `<span class="badge badge-closing-today">⏳ CLOSES TODAY</span>`;
    } else if (ipo.is_open) {
      statusBadge = `<span class="badge badge-open">🟢 OPEN</span>`;
    } else if (ipo.status === 'UPCOMING') {
      statusBadge = `<span class="badge badge-upcoming">UPCOMING</span>`;
    }

    const gmpHighlight = ipo.gmp_percent >= thresh ? 'badge-gmp-high' : '';
    const gmpPill = `<span class="badge ${gmpHighlight}">${ipo.gmp_val} (+${ipo.gmp_percent}%)</span>`;

    const safeName = (ipo.name || '').replace(/'/g, "\\'");
    const muteAction = ipo.is_muted
      ? `<button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" onclick="unmute('${safeName}')">Unmute</button>`
      : `<button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" onclick="quickMute('${safeName}', 'APPLIED')">Mute</button>`;

    return `
      <tr>
        <td>
          <div style="font-weight: 600; color: var(--text-main); font-size: 14px;">${ipo.name}</div>
          <div style="display: flex; gap: 6px; margin-top: 4px;">
            ${catBadge}
            ${statusBadge}
          </div>
        </td>
        <td>
          <div style="font-weight: 500; font-size: 13px; color: var(--text-main);">${ipo.start_date || '-'}</div>
        </td>
        <td>
          <div style="font-weight: 500; font-size: 13px; color: var(--text-main);">${ipo.end_date || '-'}</div>
        </td>
        <td>
          ${gmpPill}
        </td>
        <td>
          <div style="font-size: 12px;"><b>Total:</b> ${ipo.total_sub}</div>
          <div style="font-size: 11px; color: var(--text-muted); margin-top: 3px; line-height: 1.45;">
            <div>sHNI: <b>${ipo.shni_sub || ipo.hni_sub || '-'}</b> • bHNI: <b>${ipo.bhni_sub || '-'}</b></div>
            <div>Retail: <b>${ipo.retail_sub || '-'}</b> • QIB: <b>${ipo.qib_sub || '-'}</b></div>
          </div>
        </td>
        <td>
          <div style="font-size: 12px;"><b>Price:</b> ${ipo.price}</div>
          <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 2px;"><b>Retail:</b> ${ipo.retail_min_order}</div>
          <div style="font-size: 11.5px; color: var(--text-muted);"><b>sHNI:</b> ${ipo.shni_min_order || ipo.hni_min_order || '-'}</div>
        </td>
        <td>
          <div style="display: flex; gap: 6px; align-items: center;">
            <button type="button" class="btn btn-remind" onclick="openReminder('${safeName}')" title="Set calendar reminder for closing date">⏰ Remind</button>
            ${muteAction}
          </div>
        </td>
      </tr>
    `;
  }).join('');

  // Render Mobile Cards View (Zero horizontal scroll needed!)
  if (cardsContainer) {
    cardsContainer.innerHTML = filtered.map(ipo => {
      const isSme = (ipo.category || '').toUpperCase() === 'SME';
      const catBadge = isSme ? `<span class="badge badge-sme">SME</span>` : `<span class="badge badge-main">Main</span>`;
      
      let statusBadge = `<span class="badge badge-closed">${ipo.status}</span>`;
      if (isClosingToday(ipo)) {
        statusBadge = `<span class="badge badge-closing-today">⏳ CLOSES TODAY</span>`;
      } else if (ipo.is_open) {
        statusBadge = `<span class="badge badge-open">🟢 OPEN</span>`;
      } else if (ipo.status === 'UPCOMING') {
        statusBadge = `<span class="badge badge-upcoming">UPCOMING</span>`;
      }

      const isHighGmp = ipo.gmp_percent >= thresh;
      const gmpHighlight = isHighGmp ? 'badge-gmp-high' : '';
      const gmpPill = `<span class="badge ${gmpHighlight}">${ipo.gmp_val} (+${ipo.gmp_percent}%)</span>`;

      const safeName = (ipo.name || '').replace(/'/g, "\\'");
      const muteAction = ipo.is_muted
        ? `<button class="btn btn-secondary" style="padding: 5px 10px; font-size: 11.5px;" onclick="unmute('${safeName}')">Unmute</button>`
        : `<button class="btn btn-secondary" style="padding: 5px 10px; font-size: 11.5px;" onclick="quickMute('${safeName}', 'APPLIED')">Mute</button>`;

      return `
        <div class="ipo-mobile-card ${isHighGmp ? 'card-high-gmp' : ''}">
          <div class="ipo-card-header">
            <div class="ipo-card-title-group">
              <div class="ipo-card-name">${ipo.name}</div>
              <div class="ipo-card-badges">
                ${catBadge}
                ${statusBadge}
              </div>
            </div>
            <div class="ipo-card-actions-group">
              <button type="button" class="btn btn-remind" onclick="openReminder('${safeName}')" title="Set calendar reminder for closing date">⏰ Remind</button>
              ${muteAction}
            </div>
          </div>

          <div class="ipo-card-metrics-grid">
            <div class="metric-box">
              <span class="metric-label">EST. GMP</span>
              <div class="metric-val">${gmpPill}</div>
            </div>
            <div class="metric-box">
              <span class="metric-label">OFFER DATES</span>
              <div class="metric-val date-range">
                <div><span class="date-tag">Opens:</span> <b>${ipo.start_date || '-'}</b></div>
                <div><span class="date-tag">Closes:</span> <b>${ipo.end_date || '-'}</b></div>
              </div>
            </div>
          </div>

          <div class="ipo-card-details-section">
            <div class="detail-col">
              <span class="detail-col-title">📊 Subscription Demand</span>
              <div class="detail-col-primary">Total: <b>${ipo.total_sub}</b></div>
              <div class="detail-col-sub" style="line-height: 1.45; margin-top: 3px;">
                <div>sHNI: <b>${ipo.shni_sub || ipo.hni_sub || '-'}</b> • bHNI: <b>${ipo.bhni_sub || '-'}</b></div>
                <div>Retail: <b>${ipo.retail_sub || '-'}</b> • QIB: <b>${ipo.qib_sub || '-'}</b></div>
              </div>
            </div>
            <div class="detail-col">
              <span class="detail-col-title">💰 Price &amp; Order</span>
              <div class="detail-col-primary"><b>${ipo.price}</b></div>
              <div class="detail-col-sub" style="margin-top: 3px;">
                <div>Retail: <b>${ipo.retail_min_order}</b></div>
                ${(ipo.shni_min_order || ipo.hni_min_order) ? `<div>sHNI: <b>${ipo.shni_min_order || ipo.hni_min_order}</b></div>` : ''}
              </div>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }
}

// Muted IPOs Handling
async function loadMuted() {
  const tbody = document.getElementById('muted-table-body');
  const cardsContainer = document.getElementById('muted-cards-container');
  try {
    const res = await fetch(`${BASE_PATH}/api/muted`);
    const list = await res.json();

    document.getElementById('stat-muted-count').innerText = list.length;
    document.getElementById('muted-tab-count').innerText = list.length;

    if (list.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" class="empty-state">No IPOs are currently muted.</td></tr>`;
      if (cardsContainer) {
        cardsContainer.innerHTML = `<div class="empty-state">No IPOs are currently muted.</div>`;
      }
      return;
    }

    // Desktop table rows
    tbody.innerHTML = list.map(item => `
      <tr>
        <td><b>${item.ipo_name}</b></td>
        <td><span class="badge ${item.action === 'APPLIED' ? 'badge-open' : 'badge-closed'}">${item.action}</span></td>
        <td style="color: var(--text-muted);">${item.created_at}</td>
        <td>
          <button class="btn btn-danger-outline" onclick="unmute('${item.ipo_name}')">
            🔓 Unmute
          </button>
        </td>
      </tr>
    `).join('');

    // Mobile cards
    if (cardsContainer) {
      cardsContainer.innerHTML = list.map(item => `
        <div class="muted-mobile-card">
          <div class="muted-card-info">
            <div class="muted-card-title">${item.ipo_name}</div>
            <div class="muted-card-meta">Muted at: ${item.created_at}</div>
          </div>
          <div class="muted-card-actions">
            <span class="badge ${item.action === 'APPLIED' ? 'badge-open' : 'badge-closed'}">${item.action}</span>
            <button class="btn btn-danger-outline btn-sm" onclick="unmute('${item.ipo_name}')">
              🔓 Unmute
            </button>
          </div>
        </div>
      `).join('');
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty-state">Error loading muted items.</td></tr>`;
    if (cardsContainer) {
      cardsContainer.innerHTML = `<div class="empty-state">Error loading muted items.</div>`;
    }
  }
}

async function quickMute(name, action = 'APPLIED') {
  try {
    const res = await fetch(`${BASE_PATH}/api/mute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, action })
    });
    if (res.ok) {
      showToast(`Muted alerts for ${name}`, 'success');
      loadIpos(false);
      loadMuted();
    }
  } catch (err) {
    showToast('Failed to mute IPO', 'error');
  }
}

async function manualMute() {
  const input = document.getElementById('manual-mute-name');
  const name = input.value.trim();
  if (!name) return;

  await quickMute(name, 'IGNORED');
  input.value = '';
}

async function unmute(name) {
  try {
    const res = await fetch(`${BASE_PATH}/api/unmute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    if (res.ok) {
      showToast(`Unmuted ${name}`, 'success');
      loadIpos(false);
      loadMuted();
    }
  } catch (err) {
    showToast('Failed to unmute IPO', 'error');
  }
}

// Alert Logs
async function loadLogs() {
  const tbody = document.getElementById('logs-table-body');
  const cardsContainer = document.getElementById('logs-cards-container');
  try {
    const res = await fetch(`${BASE_PATH}/api/logs?limit=30`);
    const logs = await res.json();

    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No alerts recorded yet.</td></tr>`;
      if (cardsContainer) {
        cardsContainer.innerHTML = `<div class="empty-state">No alerts recorded yet.</div>`;
      }
      return;
    }

    // Desktop table rows
    tbody.innerHTML = logs.map(l => {
      let statusClass = 'badge-open';
      if (l.status === 'MUTED_SKIPPED') statusClass = 'badge-closed';
      if (l.status === 'FAILED') statusClass = 'badge-muted';
      if (l.status === 'DRY_RUN') statusClass = 'badge-upcoming';

      return `
        <tr>
          <td style="font-size: 12px; color: var(--text-dim);">${l.sent_at}</td>
          <td><b>${l.ipo_name}</b></td>
          <td><span class="badge">${l.gmp_val} (+${l.gmp_percent}%)</span></td>
          <td style="font-size: 12px;">Total: ${l.total_sub}</td>
          <td><span class="badge ${statusClass}">${l.status}</span></td>
          <td style="font-size: 12px; color: var(--text-muted);">${l.details || '-'}</td>
        </tr>
      `;
    }).join('');

    // Mobile cards
    if (cardsContainer) {
      cardsContainer.innerHTML = logs.map(l => {
        let statusClass = 'badge-open';
        if (l.status === 'MUTED_SKIPPED') statusClass = 'badge-closed';
        if (l.status === 'FAILED') statusClass = 'badge-muted';
        if (l.status === 'DRY_RUN') statusClass = 'badge-upcoming';

        return `
          <div class="log-mobile-card">
            <div class="log-card-header">
              <div class="log-card-name">${l.ipo_name}</div>
              <span class="badge ${statusClass}">${l.status}</span>
            </div>
            <div class="log-card-body">
              <span class="badge">${l.gmp_val} (+${l.gmp_percent}%)</span>
              <span class="log-card-sub">Total Sub: <b>${l.total_sub}</b></span>
            </div>
            <div class="log-card-footer">
              <span>🕒 ${l.sent_at}</span>
              <span>${l.details || ''}</span>
            </div>
          </div>
        `;
      }).join('');
    }
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-state">Error loading logs.</td></tr>`;
    if (cardsContainer) {
      cardsContainer.innerHTML = `<div class="empty-state">Error loading logs.</div>`;
    }
  }
}

// ==========================================================================
// IPO Closing Day Calendar Reminder System
// ==========================================================================
let selectedReminderIpo = null;

function openReminder(ipoName) {
  const ipo = allIpos.find(i => i.name === ipoName);
  if (!ipo) return;

  const ts = parseDateForSort(ipo.end_date, ipo.end_date_sort);
  if (!ts || ts === 0 || !ipo.end_date || ipo.end_date === 'TBA' || ipo.end_date === '-') {
    showToast(`Closing date for "${ipo.name}" is not yet announced (TBA).`, 'info');
    return;
  }

  selectedReminderIpo = ipo;

  const modal = document.getElementById('reminder-modal');
  const title = document.getElementById('remind-modal-title');
  const sub = document.getElementById('remind-modal-subtitle');
  const dateEl = document.getElementById('remind-modal-date');
  const gmpEl = document.getElementById('remind-modal-gmp');

  if (title) title.innerText = ipo.name;
  if (sub) sub.innerText = `${(ipo.category || 'Mainboard').toUpperCase()} • Price: ${ipo.price || '-'}`;
  if (dateEl) dateEl.innerText = ipo.end_date || 'TBA';
  if (gmpEl) gmpEl.innerText = `${ipo.gmp_val} (+${ipo.gmp_percent}%)`;

  if (modal) {
    modal.style.display = 'flex';
  }
}

function closeReminderModal() {
  const modal = document.getElementById('reminder-modal');
  if (modal) modal.style.display = 'none';
  selectedReminderIpo = null;
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeReminderModal();
});

function getReminderCalendarData(ipo) {
  const ts = parseDateForSort(ipo.end_date, ipo.end_date_sort);
  const d = new Date(ts);
  const year = d.getFullYear();
  const month = d.getMonth();
  const day = d.getDate();

  // 10:00 AM IST on Closing Date = 04:30 UTC
  const startUtc = new Date(Date.UTC(year, month, day, 4, 30, 0));
  // 17:00 (5 PM) IST Bidding Cutoff = 11:30 UTC
  const endUtc = new Date(Date.UTC(year, month, day, 11, 30, 0));

  const pad = n => String(n).padStart(2, '0');
  const fmt = dt => `${dt.getUTCFullYear()}${pad(dt.getUTCMonth() + 1)}${pad(dt.getUTCDate())}T${pad(dt.getUTCHours())}${pad(dt.getUTCMinutes())}${pad(dt.getUTCSeconds())}Z`;

  const title = `⏰ Last Day to Apply: ${ipo.name} (Closes 5 PM)`;
  const description = 
    `IPO: ${ipo.name}\n` +
    `Closing Date: Today (Cutoff at 5:00 PM IST)\n` +
    `Current GMP: ${ipo.gmp_val} (+${ipo.gmp_percent}%)\n` +
    `Retail Min Order: ${ipo.retail_min_order}\n` +
    `sHNI Min Order: ${ipo.shni_min_order || ipo.hni_min_order || '-'}\n` +
    `Subscription: Total ${ipo.total_sub} (sHNI: ${ipo.shni_sub || '-'}, bHNI: ${ipo.bhni_sub || '-'}, Retail: ${ipo.retail_sub || '-'})\n\n` +
    `Important: Complete your bid and authorize the UPI mandate before 5:00 PM IST!`;

  return {
    title,
    description,
    startGcal: fmt(startUtc),
    endGcal: fmt(endUtc),
    dtStamp: fmt(new Date()),
    fileName: `ipo-closing-${(ipo.name || 'ipo').replace(/[^a-zA-Z0-9]/g, '-').toLowerCase()}`
  };
}

function triggerGoogleCalendar() {
  if (!selectedReminderIpo) return;
  const data = getReminderCalendarData(selectedReminderIpo);
  const url = `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(data.title)}&dates=${data.startGcal}/${data.endGcal}&details=${encodeURIComponent(data.description)}&location=${encodeURIComponent('Stock Broker App / BSE / NSE')}`;
  window.open(url, '_blank');
  closeReminderModal();
  showToast('Opening Google Calendar...', 'success');
}

function triggerIcsCalendar() {
  if (!selectedReminderIpo) return;
  const data = getReminderCalendarData(selectedReminderIpo);

  const icsContent = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//IPO Wise//IPO Alert Bot//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:ipo-${Date.now()}@ipowise`,
    `DTSTAMP:${data.dtStamp}`,
    `DTSTART:${data.startGcal}`,
    `DTEND:${data.endGcal}`,
    `SUMMARY:${data.title.replace(/,/g, '\\,')}`,
    `DESCRIPTION:${data.description.replace(/\n/g, '\\n').replace(/,/g, '\\,')}`,
    'LOCATION:Stock Broker App / BSE / NSE',
    'STATUS:CONFIRMED',
    'BEGIN:VALARM',
    'TRIGGER:-PT15M',
    'ACTION:DISPLAY',
    'DESCRIPTION:IPO bidding closes today at 5:00 PM IST!',
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR'
  ].join('\r\n');

  const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${data.fileName}.ics`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  closeReminderModal();
  showToast('Downloaded calendar alert (.ics)!', 'success');
}
