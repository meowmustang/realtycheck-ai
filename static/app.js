// static/app.js 

// INTEGRITY LOADING POPUP

const quotes = [
  "“Integrity is doing the right thing, even when no one is watching.” – C.S. Lewis",
  "“Real integrity is doing the right thing, knowing that nobody’s going to know whether you did it or not.” – Oprah Winfrey",
  "“Wisdom is knowing the right path to take… Integrity is taking it.” – M.H. McKee",
  "“Integrity is choosing your thoughts and actions based on values, not personal gain.” – Unknown",
  "“The time is always right to do what is right.” – Martin Luther King Jr.",
  "“You are what you do, not what you say you’ll do.” – Carl Jung"
];

let quoteInterval = null;

function showLoadingPopup() {
  const popup = document.getElementById("loadingPopup");
  const text = document.getElementById("loadingText");
  popup.style.display = "flex";

  let i = 0;
  text.innerText = quotes[i];
  quoteInterval = setInterval(() => {
    i = (i + 1) % quotes.length;
    text.innerText = quotes[i];
  }, 5000);
}

function hideLoadingPopup() {
  const popup = document.getElementById("loadingPopup");
  popup.style.display = "none";
  clearInterval(quoteInterval);
}


document.addEventListener('DOMContentLoaded', () => {
  const $ = (id) => document.getElementById(id);

  // ---- UI helpers
  function setMeter(score) {
    const pct = Math.max(0, Math.min(10, Number(score) || 0)) * 10;
    $('meterBar').style.width = pct + '%';
    $('meterVal').innerText = `${Math.max(0, Math.min(10, Number(score) || 0))} / 10`;
  }

  // ---- Actions
  async function genScenario() {
    const name = $('name').value.trim();
    const role = $('role').value.trim();
    if (!name || !role) { alert('Please enter your name and role.'); return; }

    const res = await fetch('/generate_scenario', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name, role })
    });
    const data = await res.json();

    window.__scenario = data;
    $('greet').innerText = `Hi ${name}! IntegriBot has prepared a scenario for the ${role} role.`;
    $('scenarioText').innerText = data.scenario || 'No scenario generated.';
    $('scenarioCard').style.display = 'block';
    $('resultCard').style.display = 'none';
    $('lbCard').style.display = 'none';
    $('response').value = "";
  }

  async function submitResponse() {
    const role = $('role').value.trim();
    const response_text = $('response').value.trim();
    if (!response_text) { alert('Please type your response.'); return; }

    const payload = {
      role,
      scenario: (window.__scenario && window.__scenario.scenario) || '',
      response_text
    };

    const res = await fetch('/evaluate', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    $('feedback').innerText = data.feedback || '(No feedback)';
    $('criteria').innerText = data.criteria ? `Criteria: ${data.criteria}` : '';
    setMeter(data.score ?? 0);
    $('resultCard').style.display = 'block';
  }

  async function saveScore() {
    const name = $('name').value.trim();
    const role = $('role').value.trim();
    const consent = $('consent').checked;
    const scoreText = $('meterVal').innerText || '0 / 10';
    const score = parseInt(scoreText, 10) || 0;

    if (!consent) { alert('Please check the consent box to appear on the leaderboard.'); return; }
    if (!name || !role) { alert('Name and role required.'); return; }

    const safeName = `${name.split(/\s+/)[0]}`; // or use initials if you prefer
    const res = await fetch('/submit_score', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name: safeName, role, score, consent: true })
    });
    const data = await res.json();
    if (data.ok) {
      loadLeaderboard();
    } else {
      alert('Could not save score. Try again.');
    }
  }

  async function loadLeaderboard() {
    const res = await fetch('/leaderboard');
    const data = await res.json();
    const list = data.items || [];
    const container = $('lbList');
    container.innerHTML = '';
    list.forEach((row, i) => {
      const div = document.createElement('div');
      div.className = 'row';
      div.innerHTML = `
        <div>${i + 1}.</div>
        <div>
          <div class="name">${row.name || 'Anon'}</div>
          <div class="role">${row.role || ''}</div>
        </div>
        <div class="score">${row.score ?? '-'}/10</div>
      `;
      container.appendChild(div);
    });
    $('lbCard').style.display = 'block';
  }

  function clearAll() {
    // inputs
    $('name').value = '';
    $('role').value = '';
    $('response').value = '';
    $('consent').checked = false;

    // sections
    $('scenarioCard').style.display = 'none';
    $('resultCard').style.display = 'none';
    $('lbCard').style.display = 'none'; // hides panel only; server leaderboard is untouched

    // meter & messages
    setMeter(0);
    $('feedback').innerText = '';
    $('criteria').innerText = '';
    $('greet').innerText = '';

    // memory
    window.__scenario = null;

    // UX
    window.scrollTo({ top: 0, behavior: 'smooth' });
    $('name').focus();
  }

  // ---- Event bindings (single place)
  $('genBtn').addEventListener('click', genScenario);
  $('submitBtn').addEventListener('click', submitResponse);
  $('againBtn')?.addEventListener('click', genScenario);
  $('saveBtn')?.addEventListener('click', saveScore);
  $('lbBtn').addEventListener('click', loadLeaderboard);
  $('lbClose').addEventListener('click', () => { $('lbCard').style.display = 'none'; });
  $('clearBtn').addEventListener('click', (e) => { e.preventDefault(); clearAll(); });
});
