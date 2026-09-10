const BASE_PATH = window.BASE_PATH || '';
let currentSettings = {};

document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
});

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

function updateGmpDisplay(val) {
  document.getElementById('gmp-display-val').innerText = `> ${val}%`;
}

function calculateNextRunFallback(timesStr) {
  if (!timesStr) return null;
  const times = timesStr.split(',').map(t => t.trim()).filter(Boolean);
  if (times.length === 0) return null;

  // Calculate in IST (UTC+5.5)
  const now = new Date();
  const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  const istNow = new Date(utc + (3600000 * 5.5));
  const currentMinutes = istNow.getHours() * 60 + istNow.getMinutes();

  let nextTodayMin = null;
  let nextTodayStr = null;
  let earliestTomorrowMin = null;
  let earliestTomorrowStr = null;

  for (const t of times) {
    let h = 0, m = 0;
    const match12 = t.match(/^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$/i);
    if (match12) {
      h = parseInt(match12[1], 10);
      m = match12[2] ? parseInt(match12[2], 10) : 0;
      if (match12[3].toLowerCase() === 'pm' && h !== 12) h += 12;
      if (match12[3].toLowerCase() === 'am' && h === 12) h = 0;
    } else {
      const parts = t.split(':');
      if (parts.length >= 2) {
        h = parseInt(parts[0], 10);
        m = parseInt(parts[1], 10);
      }
    }
    const tMin = h * 60 + m;
    if (tMin > currentMinutes) {
      if (nextTodayMin === null || tMin < nextTodayMin) {
        nextTodayMin = tMin;
        nextTodayStr = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
      }
    }
    if (earliestTomorrowMin === null || tMin < earliestTomorrowMin) {
      earliestTomorrowMin = tMin;
      earliestTomorrowStr = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }
  }

  if (nextTodayStr) {
    return `Today at ${nextTodayStr}`;
  } else if (earliestTomorrowStr) {
    return `Tomorrow at ${earliestTomorrowStr}`;
  }
  return null;
}

async function loadSettings() {
  try {
    const res = await fetch(`${BASE_PATH}/api/settings`);
    if (res.status === 401) {
      window.location.href = BASE_PATH ? `${BASE_PATH}/login` : '/login';
      return;
    }
    currentSettings = await res.json();

    const isEnabled = currentSettings.is_enabled === '1' || currentSettings.is_enabled === 'true';
    document.getElementById('input-is-enabled').checked = isEnabled;

    const enableSme = currentSettings.enable_sme_alerts !== '0' && currentSettings.enable_sme_alerts !== 'false';
    document.getElementById('input-enable-sme').checked = enableSme;

    document.getElementById('input-bot-token').value = currentSettings.bot_token || '';
    document.getElementById('input-chat-id').value = currentSettings.chat_id || '';
    
    const thresh = currentSettings.gmp_threshold || '15';
    document.getElementById('input-gmp-threshold').value = thresh;
    updateGmpDisplay(thresh);

    const scheduleTimes = currentSettings.schedule_times || '10:00, 12:30, 15:30';
    document.getElementById('input-schedule-times').value = scheduleTimes;

    // Direct schedule status fallback fetch if not in settings response
    if (!currentSettings.schedule_info) {
      try {
        const schedRes = await fetch(`${BASE_PATH}/api/schedule-status`);
        if (schedRes.ok) {
          currentSettings.schedule_info = await schedRes.json();
        }
      } catch (e) {
        console.warn('Direct schedule-status fetch error:', e);
      }
    }

    updateStatusUI(isEnabled, currentSettings.last_check_status, currentSettings.last_check_at, currentSettings.schedule_info, scheduleTimes);
  } catch (err) {
    showToast('Failed to load settings', 'error');
  }
}

function updateStatusUI(isEnabled, lastStatus, lastCheckAt, scheduleInfo, scheduleTimesStr) {
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

  const lastStatusLabel = document.getElementById('last-check-status-label');
  if (lastStatusLabel) {
    lastStatusLabel.innerText = lastStatus || 'Idle';
  }

  const lastAtLabel = document.getElementById('last-check-at-label');
  if (lastAtLabel) {
    lastAtLabel.innerText = lastCheckAt ? `${lastCheckAt} IST` : 'None';
  }

  const nextLabel = document.getElementById('next-check-time-label');
  if (nextLabel) {
    if (!isEnabled) {
      nextLabel.innerText = 'Paused (Bot Paused)';
      nextLabel.style.color = '#f59e0b';
    } else if (scheduleInfo && scheduleInfo.next_fire_time) {
      nextLabel.innerText = `${scheduleInfo.next_fire_time} IST`;
      nextLabel.style.color = '#34d399';
    } else {
      const fallback = calculateNextRunFallback(scheduleTimesStr || currentSettings.schedule_times);
      if (fallback) {
        nextLabel.innerText = `${fallback} IST`;
        nextLabel.style.color = '#34d399';
      } else {
        nextLabel.innerText = 'Active (Checking schedule...)';
        nextLabel.style.color = '#34d399';
      }
    }
  }
}

async function saveSettings() {
  const isEnabled = document.getElementById('input-is-enabled').checked ? '1' : '0';
  const enableSme = document.getElementById('input-enable-sme').checked ? '1' : '0';
  const token = document.getElementById('input-bot-token').value.trim();
  const chatId = document.getElementById('input-chat-id').value.trim();
  const threshold = document.getElementById('input-gmp-threshold').value;
  const scheduleTimes = document.getElementById('input-schedule-times').value.trim();

  try {
    const res = await fetch(`${BASE_PATH}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        is_enabled: isEnabled,
        enable_sme_alerts: enableSme,
        bot_token: token,
        chat_id: chatId,
        gmp_threshold: threshold,
        schedule_times: scheduleTimes
      })
    });
    const data = await res.json();
    if (res.ok) {
      showToast('Settings saved & schedule updated successfully', 'success');
      currentSettings = data.settings;
      updateStatusUI(isEnabled === '1', currentSettings.last_check_status, currentSettings.last_check_at, currentSettings.schedule_info);
    } else {
      showToast(data.detail || 'Error saving settings', 'error');
    }
  } catch (err) {
    showToast('Network error while saving settings', 'error');
  }
}

async function testTelegramConnection() {
  const token = document.getElementById('input-bot-token').value.trim();
  const chatId = document.getElementById('input-chat-id').value.trim();

  if (!token || !chatId) {
    showToast('Please enter both Bot Token and Chat/Channel ID first', 'error');
    return;
  }

  showToast('Connecting to Telegram...', 'info');
  try {
    const res = await fetch(`${BASE_PATH}/api/test-telegram`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bot_token: token, chat_id: chatId })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
    } else {
      showToast(data.detail || 'Telegram test failed', 'error');
    }
  } catch (err) {
    showToast('Failed to reach server for test', 'error');
  }
}

async function runCheckNow() {
  showToast('Executing IPO check...', 'info');
  try {
    const res = await fetch(`${BASE_PATH}/api/trigger-check`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      loadSettings();
    } else {
      showToast(data.detail || 'Error running check', 'error');
    }
  } catch (err) {
    showToast('Failed to trigger check', 'error');
  }
}

async function changeAdminPassword() {
  const currInput = document.getElementById('input-curr-pw');
  const newInput = document.getElementById('input-new-pw');
  const curr = currInput.value.trim();
  const next = newInput.value.trim();

  if (!curr) {
    showToast('Please enter your current password', 'error');
    return;
  }
  if (!next || next.length < 4) {
    showToast('New password must be at least 4 characters', 'error');
    return;
  }

  try {
    const res = await fetch(`${BASE_PATH}/api/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: curr, new_password: next })
    });
    const data = await res.json();
    if (res.ok) {
      showToast('Admin password updated successfully', 'success');
      currInput.value = '';
      newInput.value = '';
    } else {
      showToast(data.detail || 'Failed to update password', 'error');
    }
  } catch (err) {
    showToast('Network error while updating password', 'error');
  }
}
