/* ═══════════════════════════════════════════════════
   IP Blacklist Monitor - Frontend Logic
   Giao tiếp với Flask backend qua REST API + SSE
═══════════════════════════════════════════════════ */

// ─────────────────── State ───────────────────
const RISK_COLORS = { Safe: '#3fb950', Warning: '#d29922', Danger: '#f85149' };
let _results = {};          // { ip: resultObj }
let _selectedIp = null;
let _autoTimer  = null;
let _alertCountdown = 0;
let _alertTimer = null;
let _charts     = {};       // chart instances

// ─────────────────── Init ───────────────────
window.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  addLog('✅ Ứng dụng sẵn sàng. Nhập API Key và IP rồi bấm Kiểm tra.', 'success');
});

// ─────────────────── Config ───────────────────
async function loadConfig() {
  const r = await fetch('/api/config');
  const c = await r.json();
  document.getElementById('inp-api-key').value = c.api_key || '';
  document.getElementById('inp-ips').value = (c.ip_list || []).join('\n');
  const ivals = [1,5,10,30,60];
  const idx = ivals.indexOf(c.auto_interval_minutes);
  document.getElementById('sel-interval').selectedIndex = idx >= 0 ? idx : 2;

  // Email
  document.getElementById('smtp-host').value      = c.smtp_host || '';
  document.getElementById('smtp-port').value      = c.smtp_port || 587;
  document.getElementById('smtp-tls').checked     = c.smtp_use_tls !== false;
  document.getElementById('smtp-user').value      = c.smtp_username || '';
  document.getElementById('smtp-pass').value      = c.smtp_password || '';
  document.getElementById('smtp-recipient').value = c.smtp_recipient || '';
}

async function saveConfig() {
  const ips = document.getElementById('inp-ips').value
    .split('\n').map(s=>s.trim()).filter(Boolean);
  await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({
      api_key: document.getElementById('inp-api-key').value.trim(),
      ip_list: ips,
      auto_interval_minutes: parseInt(document.getElementById('sel-interval').value),
    })
  });
}

// ─────────────────── Toggle API Key ───────────────────
function toggleApiKey() {
  const inp = document.getElementById('inp-api-key');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

function addSampleIPs() {
  const samples = ['1.1.1.1','8.8.8.8','74.125.224.72'];
  const ta = document.getElementById('inp-ips');
  const existing = new Set(ta.value.split('\n').map(s=>s.trim()).filter(Boolean));
  const toAdd = samples.filter(ip => !existing.has(ip));
  if (toAdd.length) ta.value = [...existing, ...toAdd].join('\n');
}

// ─────────────────── CHECK ───────────────────
async function startCheck() {
  await saveConfig();
  const apiKey = document.getElementById('inp-api-key').value.trim();
  const ipList = document.getElementById('inp-ips').value
    .split('\n').map(s=>s.trim()).filter(Boolean);

  if (!apiKey) { addLog('⚠ Chưa nhập API Key!', 'error'); return; }
  if (!ipList.length) { addLog('⚠ Chưa nhập IP nào!', 'warning'); return; }

  const btn = document.getElementById('btn-check');
  btn.disabled = true;
  setChecking(`⏳ Đang kiểm tra 0/${ipList.length}...`);
  addLog(`▶ Bắt đầu kiểm tra ${ipList.length} IP`, 'info');

  // Start check on server
  const res = await fetch('/api/check', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ api_key: apiKey, ip_list: ipList }),
  });
  if (!res.ok) {
    const err = await res.json();
    addLog('✗ ' + err.error, 'error');
    btn.disabled = false; setChecking('');
    return;
  }

  // Listen to SSE stream
  let done = 0;
  const evtSrc = new EventSource('/api/check/stream');
  evtSrc.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.type === 'ping') return;
    if (ev.type === 'log') { addLog(ev.msg, ev.level); }
    if (ev.type === 'result') {
      done++;
      setChecking(`⏳ Đang kiểm tra ${done}/${ipList.length}...`);
      handleResult(ev.data);
    }
    if (ev.type === 'done') {
      evtSrc.close();
      btn.disabled = false;
      setChecking('');
      addLog(`✅ Hoàn thành lúc ${now()}`, 'success');
    }
  };
  evtSrc.onerror = () => {
    evtSrc.close();
    btn.disabled = false; setChecking('');
  };
}

function handleResult(d) {
  _results[d.ip] = d;
  updateTableRow(d);
  // Alert popup nếu Danger/Warning
  if (!d.error && (d.risk_level === 'Danger' || d.risk_level === 'Warning')) {
    showAlert([d]);
  }
}

// ─────────────────── TABLE ───────────────────
function updateTableRow(d) {
  const tbody = document.getElementById('result-tbody');
  let tr = document.getElementById(`row-${d.ip.replace(/\./g,'_')}`);
  if (!tr) {
    tr = document.createElement('tr');
    tr.id = `row-${d.ip.replace(/\./g,'_')}`;
    tr.onclick = () => selectRow(d.ip, tr);
    tbody.appendChild(tr);
  }

  const rc = RISK_COLORS[d.risk_level] || '#e6edf3';
  const statusClass = d.total_listed === 0 ? 'status-clean' : 'status-dirty';
  const statusText  = d.error ? d.error.substring(0,40)
                    : (d.total_listed === 0 ? '✓ Sạch' : `⚠ Dính ${d.total_listed} BL`);
  const riskClass   = d.error ? 'risk-error'
                    : `risk-${d.risk_level.toLowerCase()}`;

  tr.innerHTML = `
    <td style="font-family:monospace;font-weight:600">${d.ip}</td>
    <td class="center">${d.error ? '—' : d.total_listed}</td>
    <td class="center">${d.error ? '—' : d.major_count}</td>
    <td class="center">${d.error ? '—' : d.other_count}</td>
    <td class="center ${riskClass}">${d.error ? 'Lỗi' : d.risk_level}</td>
    <td style="color:var(--muted);font-size:12px">${d.checked_at}</td>
    <td class="${statusClass}">${statusText}</td>
  `;

  if (_selectedIp === d.ip) showDetail(d.ip);
}

function selectRow(ip, tr) {
  document.querySelectorAll('#result-tbody tr').forEach(r=>r.classList.remove('selected'));
  tr.classList.add('selected');
  _selectedIp = ip;
  showDetail(ip);
}

function showDetail(ip) {
  const d = _results[ip];
  if (!d) return;
  const rc = RISK_COLORS[d.risk_level] || '#e6edf3';
  document.getElementById('lbl-detail-ip').innerHTML =
    `<b style="color:${rc}">${d.ip}</b> — Risk: <b>${d.risk_level}</b>`;

  const tbody = document.getElementById('bl-tbody');
  tbody.innerHTML = '';
  if (d.error) {
    tbody.innerHTML = `<tr><td style="color:var(--red)">LỖI</td><td colspan="2">${d.error}</td></tr>`;
  } else if (!d.blacklists.length) {
    tbody.innerHTML = `<tr><td style="color:var(--green)" colspan="3">✅ Không bị dính blacklist nào</td></tr>`;
  } else {
    d.blacklists.forEach(bl => {
      const badge = bl.is_major ? '🔴' : '🟡';
      const color = bl.is_major ? 'var(--red)' : 'var(--amber)';
      const link  = bl.url ? `<a href="${bl.url}" target="_blank" style="color:var(--blue);font-size:11px">${bl.url.substring(0,60)}...</a>` : '—';
      tbody.innerHTML += `<tr>
        <td style="color:${color}">${badge} ${bl.name}</td>
        <td style="font-family:monospace">${bl.info || '—'}</td>
        <td>${link}</td>
      </tr>`;
    });
  }

  // JSON tab
  document.getElementById('detail-json').textContent =
    d.raw_json ? JSON.stringify(d.raw_json, null, 2).substring(0, 8000) : (d.error || '—');
}

// ─────────────────── DETAIL TABS ───────────────────
function switchDetail(name, btn) {
  document.querySelectorAll('.dtab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.detail-content').forEach(c => c.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById(`dtab-${name}`).classList.add('active');
}

// ─────────────────── AUTO SCHEDULER ───────────────────
function startAuto() {
  const mins = parseInt(document.getElementById('sel-interval').value);
  document.getElementById('btn-auto-start').disabled = true;
  document.getElementById('btn-auto-stop').disabled  = false;
  document.getElementById('auto-status').textContent = '▶ Đang chạy tự động';
  document.getElementById('auto-status').style.color = 'var(--green)';
  addLog(`⏱ Auto check bật, chu kỳ: ${mins} phút`, 'info');

  const run = () => {
    addLog(`🔄 Auto check kích hoạt lúc ${now()}`, 'info');
    startCheck();
    updateNextRun();
  };
  _autoTimer = setInterval(run, mins * 60 * 1000);
  updateNextRun();
}

function stopAuto() {
  clearInterval(_autoTimer); _autoTimer = null;
  document.getElementById('btn-auto-start').disabled = false;
  document.getElementById('btn-auto-stop').disabled  = true;
  document.getElementById('auto-status').textContent = '⏹ Đã dừng';
  document.getElementById('auto-status').style.color = 'var(--muted)';
  document.getElementById('lbl-next').textContent = 'Lần tiếp: —';
  addLog('⏹ Auto check đã dừng.', 'warning');
}

function updateNextRun() {
  const mins = parseInt(document.getElementById('sel-interval').value);
  const next = new Date(Date.now() + mins * 60 * 1000);
  document.getElementById('lbl-last').textContent = `Lần cuối: ${now()}`;
  document.getElementById('lbl-next').textContent = `Lần tiếp: ${fmtDate(next)}`;
}

// ─────────────────── TABS ───────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector(`.tab-btn[onclick*="${name}"]`).classList.add('active');
  document.getElementById(`tab-${name}`).classList.add('active');
  if (name === 'charts') drawCharts();
}

// ─────────────────── CHARTS ───────────────────
const chartDefaults = {
  color: '#e6edf3',
  plugins: { legend: { labels: { color: '#8b949e' } } },
  scales: {
    x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
    y: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
  }
};

async function drawCharts() {
  drawBarChart();
  drawPieChart();
  await loadLineIPs();
}

function drawBarChart() {
  const data = Object.values(_results).filter(d => !d.error);
  const labels = data.map(d => d.ip);
  const vals   = data.map(d => d.total_listed);
  const colors = data.map(d => RISK_COLORS[d.risk_level] || '#8b949e');

  if (_charts.bar) _charts.bar.destroy();
  const ctx = document.getElementById('chart-bar').getContext('2d');
  _charts.bar = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ data: vals, backgroundColor: colors, borderRadius: 4 }] },
    options: {
      ...chartDefaults,
      plugins: { legend: { display: false } },
      scales: chartDefaults.scales,
    }
  });
}

async function drawPieChart() {
  const r = await fetch('/api/risk-summary');
  const s = await r.json();
  const labels = Object.keys(s).filter(k => s[k] > 0);
  const vals   = labels.map(k => s[k]);
  const colors = labels.map(k => RISK_COLORS[k] || '#8b949e');

  if (_charts.pie) _charts.pie.destroy();
  const ctx = document.getElementById('chart-pie').getContext('2d');
  _charts.pie = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: vals, backgroundColor: colors, borderWidth: 2, borderColor: '#0d1117' }] },
    options: {
      plugins: { legend: { labels: { color: '#8b949e' } } },
      cutout: '55%',
    }
  });
}

async function loadLineIPs() {
  const sel = document.getElementById('sel-chart-ip');
  const curr = sel.value;
  sel.innerHTML = '';
  const ips = Object.keys(_results);
  ips.forEach(ip => {
    const opt = document.createElement('option');
    opt.value = opt.textContent = ip;
    sel.appendChild(opt);
  });
  if (curr && ips.includes(curr)) sel.value = curr;
  await drawLineChart();
}

async function drawLineChart() {
  const ip = document.getElementById('sel-chart-ip').value;
  if (!ip) return;
  const r = await fetch(`/api/history/${encodeURIComponent(ip)}`);
  const rows = await r.json();

  const labels = rows.map(r => r.checked_at.substring(0,16).replace('T',' '));
  const vals   = rows.map(r => r.total_listed);

  if (_charts.line) _charts.line.destroy();
  const ctx = document.getElementById('chart-line').getContext('2d');
  _charts.line = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: [{
      data: vals,
      borderColor: '#58a6ff', backgroundColor: 'rgba(88,166,255,.1)',
      pointBackgroundColor: '#58a6ff',
      fill: true, tension: 0.3,
    }]},
    options: { ...chartDefaults, plugins: { legend: { display: false } } },
  });
}

// ─────────────────── LOG ───────────────────
function addLog(msg, level = 'info') {
  const box = document.getElementById('log-box');
  const ts  = now();
  const p   = document.createElement('p');
  p.innerHTML = `<span style="color:var(--muted)">[${ts}]</span> <span class="log-${level}">${msg}</span>`;
  box.appendChild(p);
  box.scrollTop = box.scrollHeight;
  // Max 500 lines
  while (box.children.length > 500) box.removeChild(box.firstChild);
}

function setChecking(txt) {
  document.getElementById('lbl-checking').textContent = txt;
}

function exportLog() {
  const box = document.getElementById('log-box');
  const txt = [...box.querySelectorAll('p')].map(p => p.textContent).join('\n');
  download('blacklist_log.txt', txt, 'text/plain');
}

// ─────────────────── EXPORT ───────────────────
function exportCSV()  { window.location = '/api/export/csv'; }
function exportJSON() { window.location = '/api/export/json'; }

// ─────────────────── EMAIL MODAL ───────────────────
function openEmailModal() {
  document.getElementById('email-modal').classList.add('open');
}
function closeEmailModal(e) {
  if (!e || e.target.id === 'email-modal' || e.currentTarget?.tagName === 'BUTTON') {
    document.getElementById('email-modal').classList.remove('open');
  }
}

async function saveEmailConfig() {
  const cfg = getEmailCfg();
  await fetch('/api/config', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify(cfg),
  });
  addLog('✅ Đã lưu cấu hình email.', 'success');
  closeEmailModal();
}

async function testEmail() {
  const btn = document.getElementById('btn-test-email');
  btn.disabled = true; btn.textContent = 'Đang gửi...';
  const r = await fetch('/api/email/test', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify(getEmailCfg()),
  });
  const d = await r.json();
  btn.disabled = false; btn.textContent = '📧 Gửi mail test';
  if (d.ok) { alert('✅ Gửi email test thành công!'); }
  else       { alert('❌ Thất bại:\n' + d.error); }
}

function getEmailCfg() {
  return {
    smtp_host:      document.getElementById('smtp-host').value.trim(),
    smtp_port:      parseInt(document.getElementById('smtp-port').value),
    smtp_use_tls:   document.getElementById('smtp-tls').checked,
    smtp_username:  document.getElementById('smtp-user').value.trim(),
    smtp_password:  document.getElementById('smtp-pass').value,
    smtp_recipient: document.getElementById('smtp-recipient').value.trim(),
  };
}

// ─────────────────── ALERT POPUP ───────────────────
function showAlert(results) {
  const popup = document.getElementById('alert-popup');
  document.getElementById('alert-sub').textContent = `${results.length} IP cần xử lý ngay`;
  const body = document.getElementById('alert-body');
  body.innerHTML = results.map(d => `
    <div class="alert-item">
      <span style="font-family:monospace;font-weight:700">${d.ip}</span>
      <span style="color:${RISK_COLORS[d.risk_level]||'#e6edf3'};font-weight:700">${d.risk_level}</span>
      <span style="color:var(--muted)">${d.total_listed} BL</span>
    </div>`).join('');

  popup.classList.remove('hidden');
  _alertCountdown = 60;
  clearInterval(_alertTimer);
  _alertTimer = setInterval(() => {
    _alertCountdown--;
    document.getElementById('alert-countdown').textContent = `Tự đóng sau ${_alertCountdown}s`;
    if (_alertCountdown <= 0) closeAlert();
  }, 1000);
}

function closeAlert() {
  clearInterval(_alertTimer);
  document.getElementById('alert-popup').classList.add('hidden');
}

// ─────────────────── UTILS ───────────────────
function now() {
  return new Date().toLocaleTimeString('vi-VN', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
function fmtDate(d) {
  return d.toLocaleTimeString('vi-VN', {hour:'2-digit',minute:'2-digit',second:'2-digit'}) +
         ' ' + d.toLocaleDateString('vi-VN');
}
function download(filename, content, type) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([content], {type}));
  a.download = filename; a.click();
}
