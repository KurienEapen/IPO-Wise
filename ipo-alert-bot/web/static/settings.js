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

    document.getElementById('input-schedule-times').value = currentSettings.schedule_times || '10:00,12:30,15:30';

    updateStatusUI(isEnabled, currentSettings.last_check_status);
  } catch (err) {
    showToast('Failed to load settings', 'error');
  }
}

function updateStatusUI(isEnabled, lastStatus) {
  const pill = document.getElementById('master-status-pill');
  const text = document.getElementById('master-status-text');
  if (isEnabled) {
    pill.className = 'status-pill active';
    text.innerText = 'Bot Active';
  } else {
    pill.className = 'status-pill paused';
    text.innerText = 'Bot Paused';
  }

  if (lastStatus) {
    document.getElementById('last-check-status-label').innerText = lastStatus;
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
      showToast('Settings saved successfully', 'success');
      currentSettings = data.settings;
      updateStatusUI(isEnabled === '1', currentSettings.last_check_status);
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
