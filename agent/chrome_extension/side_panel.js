// Side panel logic. Runs in the extension's own origin, so every request
// to the local Flask app needs its full URL (relative paths would resolve
// against the extension itself, not localhost:5000).
const API_BASE = 'http://localhost:5000';

const log = document.getElementById('log');
const form = document.getElementById('chat-form');
const input = document.getElementById('message');
const sendBtn = document.getElementById('send-btn');
const statusEl = document.getElementById('status');

function addMessage(role, html) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = html;
  log.appendChild(div);
  div.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.innerText = text;
  return d.innerHTML;
}

async function checkStatus() {
  try {
    const res = await fetch(`${API_BASE}/agent/api/config`);
    if (!res.ok) throw new Error('bad status');
    const data = await res.json();
    const provider = data.translator?.configured_provider || 'rule_based';
    const aiActive = data.translator?.ai_backend_available;
    statusEl.textContent = `Connected — translator: ${provider}${aiActive ? '' : ' (using rule-based fallback)'}`;
    statusEl.classList.remove('offline');
  } catch (err) {
    statusEl.textContent = 'Not connected — make sure "python app.py" is running on localhost:5000';
    statusEl.classList.add('offline');
  }
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  addMessage('user', `<p>${escapeHtml(message)}</p>`);
  input.value = '';
  sendBtn.disabled = true;
  addMessage('agent', '<p><em>Working on it&hellip;</em></p>');
  const thinking = log.lastElementChild;

  try {
    const res = await fetch(`${API_BASE}/agent/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    const data = await res.json();
    thinking.remove();
    if (data.success) {
      addMessage('agent', data.reply.html);
    } else {
      addMessage('agent', `<p>Error: ${escapeHtml(data.error || 'unknown error')}</p>`);
    }
  } catch (err) {
    thinking.remove();
    addMessage('agent', `<p>Request failed: ${escapeHtml(String(err))}. Is "python app.py" running?</p>`);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

checkStatus();
