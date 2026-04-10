/* ═══════════════════════════════════════════════════════
   Vocabulary Assessment Tool - Frontend Application
   ═══════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────
let currentUser = null;
let currentPage = 'home';
let assessState = {
  sessionId: null,
  answered: 0,
  total: 0,
  currentWord: null,
  result: null,
};
let learnState = { dueWords: [], currentIdx: 0 };
let adminState = { userPage: 1, wordPage: 1, recordPage: 1 };

// ── Init ───────────────────────────────────────────────────
(async function init() {
  await checkAuth();
  loadHomeStats();
  navigate('home');
})();

// ── Auth ───────────────────────────────────────────────────
async function checkAuth() {
  const res = await api('/api/auth/me');
  if (res.user) {
    currentUser = res.user;
    renderNavUser();
  }
}

function renderNavUser() {
  const container = document.getElementById('nav-user');
  const navLearn = document.getElementById('nav-learn');
  const navDash = document.getElementById('nav-dashboard');
  const navAdmin = document.getElementById('nav-admin');
  const anonTip = document.getElementById('anon-tip');

  if (currentUser) {
    container.innerHTML = `
      <span class="nav-username">👤 ${esc(currentUser.username)}</span>
      <button class="btn btn-outline btn-sm" onclick="doLogout()">退出</button>`;
    navLearn.classList.remove('hidden');
    navDash.classList.remove('hidden');
    if (anonTip) anonTip.classList.add('hidden');
    if (currentUser.is_admin) navAdmin.classList.remove('hidden');
  } else {
    container.innerHTML = `
      <button class="btn btn-outline btn-sm" onclick="navigate('login')">登录</button>
      <button class="btn btn-primary btn-sm" onclick="navigate('register')">注册</button>`;
    navLearn.classList.add('hidden');
    navDash.classList.add('hidden');
    navAdmin.classList.add('hidden');
    if (anonTip) anonTip.classList.remove('hidden');
  }
  const btnSave = document.getElementById('btn-save-result');
  if (btnSave) btnSave.style.display = currentUser ? 'inline-flex' : 'none';
}

async function doLogin() {
  const id = document.getElementById('login-id').value.trim();
  const pwd = document.getElementById('login-pwd').value;
  const err = document.getElementById('login-err');
  err.classList.add('hidden');
  const res = await api('/api/auth/login', 'POST', { identifier: id, password: pwd });
  if (res.error) { err.textContent = res.error; err.classList.remove('hidden'); return; }
  currentUser = res.user;
  renderNavUser();
  toast('登录成功，欢迎 ' + res.user.username);
  navigate('home');
}

async function doRegister() {
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const pwd = document.getElementById('reg-pwd').value;
  const err = document.getElementById('reg-err');
  err.classList.add('hidden');
  const res = await api('/api/auth/register', 'POST', { username: name, email, password: pwd });
  if (res.error) { err.textContent = res.error; err.classList.remove('hidden'); return; }
  currentUser = res.user;
  renderNavUser();
  toast('注册成功！');
  navigate('home');
}

async function doLogout() {
  await api('/api/auth/logout', 'POST');
  currentUser = null;
  renderNavUser();
  toast('已退出登录');
  navigate('home');
}

// ── Navigation ─────────────────────────────────────────────
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const el = document.getElementById('page-' + page);
  if (!el) return;
  el.classList.add('active');
  currentPage = page;
  window.scrollTo(0, 0);

  if (page === 'dashboard') loadDashboard();
  if (page === 'learn') loadLearnPage();
  if (page === 'admin') { loadAdminStats(); adminTab('overview'); }
}

function scrollToHow() {
  document.getElementById('how-section')?.scrollIntoView({ behavior: 'smooth' });
}

// ── Home ───────────────────────────────────────────────────
async function loadHomeStats() {
  const res = await api('/api/admin/stats').catch(() => null);
  if (res && res.total_tests !== undefined) {
    document.getElementById('h-total-tests').textContent = res.total_tests.toLocaleString();
  }
}

function startQuickAssess(level) {
  document.querySelector(`input[name=level][value=${level}]`).checked = true;
  navigate('assess');
}

// ── Assessment ─────────────────────────────────────────────
async function startAssessment() {
  const level = document.querySelector('input[name=level]:checked').value;
  const algo = document.querySelector('input[name=algo]:checked').value;
  const maxQ = parseInt(document.getElementById('q-count').value);

  const res = await api('/api/assess/start', 'POST', { level, algo, max_q: maxQ });
  if (res.error) { toast('错误：' + res.error); return; }

  assessState = {
    sessionId: res.session_id,
    answered: 0,
    total: res.total,
    currentWord: res.question,
    result: null,
  };

  document.getElementById('test-q-total').textContent = res.total;
  document.getElementById('test-algo-badge').textContent = algo === 'irt' ? 'IRT自适应' : '二分搜索';
  renderQuestion(res.question, 0, res.total);
  navigate('testing');
}

function renderQuestion(q, answered, total) {
  document.getElementById('test-q-num').textContent = answered + 1;
  document.getElementById('progress-fill').style.width = (answered / total * 100) + '%';
  document.getElementById('word-display').textContent = q.word;
  document.getElementById('word-phonetic').textContent = q.phonetic || '';

  const container = document.getElementById('choices');
  const feedback = document.getElementById('answer-feedback');
  feedback.classList.add('hidden');
  feedback.className = 'answer-feedback hidden';
  container.innerHTML = '';

  q.choices.forEach(c => {
    const btn = document.createElement('button');
    btn.className = 'choice-btn';
    btn.textContent = c.meaning;
    btn.onclick = () => submitAnswer(c.meaning, q);
    container.appendChild(btn);
  });
}

async function submitAnswer(chosenMeaning, question) {
  // Disable all buttons
  document.querySelectorAll('.choice-btn').forEach(b => b.disabled = true);

  const res = await api('/api/assess/answer', 'POST', {
    session_id: assessState.sessionId,
    chosen_meaning: chosenMeaning,
  });

  // Highlight correct/wrong
  const correct = res.correct;
  document.querySelectorAll('.choice-btn').forEach(b => {
    if (b.textContent === question.meaning) b.classList.add('correct');
    else if (b.textContent === chosenMeaning && !correct) b.classList.add('wrong');
  });

  const feedback = document.getElementById('answer-feedback');
  feedback.classList.remove('hidden');
  if (correct) {
    feedback.className = 'answer-feedback correct';
    feedback.textContent = '✓ 正确！';
  } else {
    feedback.className = 'answer-feedback wrong';
    feedback.textContent = `✗ 正确答案：${question.meaning}`;
  }

  if (res.done) {
    assessState.result = res.result;
    setTimeout(() => showResult(res.result), 900);
  } else {
    assessState.currentWord = res.question;
    setTimeout(() => renderQuestion(res.question, res.answered, res.total), 900);
  }
}

// ── Result ─────────────────────────────────────────────────
function showResult(result) {
  navigate('result');
  const emojis = { '小学': '🌱', '初中': '📖', '高中': '🎓', '大学及以上': '🏆' };
  document.getElementById('result-emoji').textContent = emojis[result.estimated_level] || '🎉';
  document.getElementById('result-score').textContent = result.score.toLocaleString();
  document.getElementById('result-level-badge').textContent = result.estimated_level + '水平';
  document.getElementById('r-accuracy').textContent = Math.round(result.accuracy * 100) + '%';
  document.getElementById('r-correct').textContent = result.correct;
  document.getElementById('r-total').textContent = result.answered;
  document.getElementById('r-algo').textContent = result.algo === 'irt' ? 'IRT' : '二分';

  const detailList = document.getElementById('result-details');
  detailList.innerHTML = '';
  (result.details || []).forEach(d => {
    const div = document.createElement('div');
    div.className = 'detail-item';
    div.innerHTML = `<span class="di-icon">${d.correct ? '✅' : '❌'}</span>
      <span class="di-word">${esc(d.word)}</span>
      <span class="di-meaning">${esc(d.meaning)}</span>`;
    detailList.appendChild(div);
  });

  const btnSave = document.getElementById('btn-save-result');
  if (btnSave) btnSave.style.display = currentUser ? 'inline-flex' : 'none';
}

function shareResult() {
  if (!assessState.result) return;
  const r = assessState.result;
  const text = `我在京师词汇测评中的成绩：\n预估词汇量：${r.score} 词\n词汇等级：${r.estimated_level}\n正确率：${Math.round(r.accuracy*100)}%\n\n来挑战我吧！`;
  navigator.clipboard.writeText(text).then(() => toast('分享文字已复制！'));
}

// ── Dashboard ──────────────────────────────────────────────
async function loadDashboard() {
  if (!currentUser) { navigate('login'); return; }
  const stats = await api('/api/user/stats');
  if (stats.total_tests !== undefined) {
    document.getElementById('dash-total-tests').querySelector('.ds-v').textContent = stats.total_tests;
    document.getElementById('dash-best-score').querySelector('.ds-v').textContent = stats.best_score.toLocaleString();
    document.getElementById('dash-avg-acc').querySelector('.ds-v').textContent = Math.round(stats.avg_accuracy * 100) + '%';
    drawTrendChart(stats.trend);
  }
  loadHistory(1);
}

async function loadHistory(page) {
  const res = await api(`/api/user/history?page=${page}&per_page=10`);
  const list = document.getElementById('history-list');
  list.innerHTML = '';
  (res.records || []).forEach(r => {
    const levelNames = { primary: '小学', middle: '初中', high: '高中', all: '全部' };
    const div = document.createElement('div');
    div.className = 'history-item';
    div.innerHTML = `
      <div class="hi-score">${r.score}</div>
      <div>
        <div style="font-weight:600">${levelNames[r.level] || r.level} · ${r.algo === 'irt' ? 'IRT算法' : '二分算法'}</div>
        <div class="hi-info">${r.correct}/${r.total} 正确 · ${Math.round(r.accuracy*100)}% · ${fmtDate(r.created_at)}</div>
      </div>
      <span class="hi-badge">${r.estimated_level}</span>`;
    list.appendChild(div);
  });
  if (!res.records?.length) list.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:24px">暂无记录，去做测评吧！</p>';
  renderPagination('history-pagination', page, Math.ceil((res.total || 0) / 10), loadHistory);
}

function drawTrendChart(trend) {
  const canvas = document.getElementById('trend-chart');
  if (!canvas || !trend?.length) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const pad = { t: 20, b: 40, l: 50, r: 20 };
  ctx.clearRect(0, 0, W, H);

  if (trend.length < 2) {
    ctx.fillStyle = '#64748b';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('测评次数不足，继续加油！', W/2, H/2);
    return;
  }

  const scores = trend.map(t => t.score);
  const maxS = Math.max(...scores, 100);
  const minS = Math.min(...scores, 0);
  const scaleX = i => pad.l + i * (W - pad.l - pad.r) / (trend.length - 1);
  const scaleY = v => pad.t + (1 - (v - minS) / (maxS - minS + 1)) * (H - pad.t - pad.b);

  // Grid lines
  ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + i * (H - pad.t - pad.b) / 4;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(W - pad.r, y); ctx.stroke();
    ctx.fillStyle = '#94a3b8'; ctx.font = '11px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText(Math.round(maxS - i * (maxS - minS) / 4), pad.l - 4, y + 4);
  }

  // Fill
  const grad = ctx.createLinearGradient(0, pad.t, 0, H - pad.b);
  grad.addColorStop(0, 'rgba(79,70,229,.3)');
  grad.addColorStop(1, 'rgba(79,70,229,.02)');
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.moveTo(scaleX(0), H - pad.b);
  trend.forEach((t, i) => ctx.lineTo(scaleX(i), scaleY(t.score)));
  ctx.lineTo(scaleX(trend.length - 1), H - pad.b);
  ctx.closePath(); ctx.fill();

  // Line
  ctx.strokeStyle = '#4f46e5'; ctx.lineWidth = 2.5;
  ctx.beginPath();
  trend.forEach((t, i) => i === 0 ? ctx.moveTo(scaleX(i), scaleY(t.score)) : ctx.lineTo(scaleX(i), scaleY(t.score)));
  ctx.stroke();

  // Points
  trend.forEach((t, i) => {
    ctx.fillStyle = '#4f46e5';
    ctx.beginPath(); ctx.arc(scaleX(i), scaleY(t.score), 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#64748b'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(t.date, scaleX(i), H - pad.b + 16);
  });
}

// ── Learn (Spaced Repetition) ─────────────────────────────
async function loadLearnPage() {
  if (!currentUser) {
    document.getElementById('learn-login-tip').classList.remove('hidden');
    document.getElementById('learn-card').classList.add('hidden');
    document.getElementById('learn-empty').classList.add('hidden');
    document.getElementById('learn-due-count').classList.add('hidden');
    return;
  }
  document.getElementById('learn-login-tip').classList.add('hidden');
  const res = await api('/api/user/learning/due');
  learnState.dueWords = res || [];
  learnState.currentIdx = 0;
  const banner = document.getElementById('learn-due-count');
  banner.classList.remove('hidden');
  banner.textContent = `今日待复习：${learnState.dueWords.length} 个单词`;
  showLearnCard();
}

function showLearnCard() {
  const card = document.getElementById('learn-card');
  const empty = document.getElementById('learn-empty');
  if (learnState.currentIdx >= learnState.dueWords.length) {
    card.classList.add('hidden');
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  card.classList.remove('hidden');
  const w = learnState.dueWords[learnState.currentIdx];
  document.getElementById('lc-word').textContent = w.word;
  document.getElementById('lc-phonetic').textContent = w.phonetic || '';
  document.getElementById('lc-meaning').textContent = w.meaning;
  document.getElementById('lc-meaning').classList.add('hidden');
  document.getElementById('lc-buttons').classList.add('hidden');
  document.getElementById('lc-reveal-btn').classList.remove('hidden');
}

function revealLearnCard() {
  document.getElementById('lc-meaning').classList.remove('hidden');
  document.getElementById('lc-buttons').classList.remove('hidden');
  document.getElementById('lc-reveal-btn').classList.add('hidden');
}

async function submitReview(quality) {
  const w = learnState.dueWords[learnState.currentIdx];
  await api('/api/user/learning/review', 'POST', { record_id: w.id, quality });
  learnState.currentIdx++;
  showLearnCard();
}

// ── Admin ──────────────────────────────────────────────────
function adminTab(tab) {
  document.querySelectorAll('.admin-panel').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('admin-' + tab).classList.remove('hidden');
  event.target.classList.add('active');

  if (tab === 'overview') loadAdminStats();
  if (tab === 'users') loadAdminUsers();
  if (tab === 'words') loadAdminWords();
  if (tab === 'records') loadAdminRecords();
}

async function loadAdminStats() {
  const res = await api('/api/admin/stats');
  if (res.error) return;
  document.getElementById('as-users').textContent = res.total_users;
  document.getElementById('as-tests').textContent = res.total_tests;
  document.getElementById('as-words').textContent = res.total_words;
  const tbody = document.getElementById('admin-recent-body');
  tbody.innerHTML = (res.recent_tests || []).map(r => `
    <tr><td>${r.id}</td><td>${r.user_id || '匿名'}</td><td>${levelLabel(r.level)}</td>
    <td>${r.algo}</td><td>${r.score}</td><td>${Math.round(r.accuracy*100)}%</td>
    <td>${fmtDate(r.created_at)}</td></tr>`).join('');
}

async function loadAdminUsers(page = adminState.userPage) {
  adminState.userPage = page;
  const q = document.getElementById('user-search')?.value || '';
  const res = await api(`/api/admin/users?page=${page}&per_page=15&q=${encodeURIComponent(q)}`);
  if (res.error) return;
  const tbody = document.getElementById('admin-users-body');
  tbody.innerHTML = (res.users || []).map(u => `
    <tr>
      <td>${u.id}</td>
      <td>${esc(u.username)}</td>
      <td>${esc(u.email)}</td>
      <td><span class="${u.is_admin ? 'badge-admin' : 'badge-user'}">${u.is_admin ? '管理员' : '普通用户'}</span></td>
      <td>${u.test_count}</td>
      <td>${fmtDate(u.created_at)}</td>
      <td class="actions">
        <button class="btn btn-sm btn-outline" onclick="toggleAdmin(${u.id},${u.is_admin})">${u.is_admin ? '降级' : '升级管理员'}</button>
        <button class="btn btn-sm btn-danger" onclick="deleteUser(${u.id})">删除</button>
      </td>
    </tr>`).join('');
  renderPagination('admin-users-pagination', page, Math.ceil(res.total / 15), p => loadAdminUsers(p));
}

async function toggleAdmin(uid, isAdmin) {
  if (!confirm(`确认${isAdmin ? '降级' : '升级为管理员'}？`)) return;
  const res = await api(`/api/admin/users/${uid}`, 'PUT', { is_admin: !isAdmin });
  if (res.error) { toast(res.error); return; }
  toast('已更新');
  loadAdminUsers();
}

async function deleteUser(uid) {
  if (!confirm('确认删除该用户？此操作不可撤销。')) return;
  const res = await api(`/api/admin/users/${uid}`, 'DELETE');
  if (res.error) { toast(res.error); return; }
  toast('已删除');
  loadAdminUsers();
}

async function loadAdminWords(page = adminState.wordPage) {
  adminState.wordPage = page;
  const level = document.getElementById('word-level-filter')?.value || '';
  const q = document.getElementById('word-search')?.value || '';
  const res = await api(`/api/admin/wordbank?page=${page}&per_page=20&level=${level}&q=${encodeURIComponent(q)}`);
  if (res.error) return;
  const tbody = document.getElementById('admin-words-body');
  tbody.innerHTML = (res.words || []).map(w => `
    <tr>
      <td>${w.id}</td>
      <td><strong>${esc(w.word)}</strong></td>
      <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(w.meaning)}">${esc(w.meaning)}</td>
      <td>${esc(w.phonetic || '')}</td>
      <td>${levelLabel(w.level)}</td>
      <td>${w.freq_rank}</td>
      <td><span class="toggle-enabled" onclick="toggleWord(${w.id},${w.enabled})">${w.enabled ? '✅' : '❌'}</span></td>
      <td class="actions">
        <button class="btn btn-sm btn-outline" onclick="editWord(${w.id})">编辑</button>
        <button class="btn btn-sm btn-danger" onclick="deleteWord(${w.id})">删除</button>
      </td>
    </tr>`).join('');
  renderPagination('admin-words-pagination', page, Math.ceil(res.total / 20), p => loadAdminWords(p));
}

async function toggleWord(wid, enabled) {
  await api(`/api/admin/wordbank/${wid}`, 'PUT', { enabled: !enabled });
  loadAdminWords();
}

function showAddWordModal() {
  openModal('添加词汇', `
    <div class="modal-body-section">
      <div class="form-group"><label>词汇</label><input class="form-input" id="mw-word" placeholder="英文单词"></div>
      <div class="form-group"><label>释义</label><input class="form-input" id="mw-meaning" placeholder="中文释义"></div>
      <div class="form-group"><label>音标</label><input class="form-input" id="mw-phonetic" placeholder="/fəˈnetɪk/"></div>
      <div class="form-group"><label>词库</label>
        <select class="form-input" id="mw-level">
          <option value="primary">小学</option>
          <option value="middle">初中</option>
          <option value="high">高中</option>
        </select>
      </div>
      <button class="btn btn-primary btn-full" onclick="submitAddWord()">添加</button>
    </div>`);
}

async function submitAddWord() {
  const word = document.getElementById('mw-word').value.trim();
  const meaning = document.getElementById('mw-meaning').value.trim();
  const phonetic = document.getElementById('mw-phonetic').value.trim();
  const level = document.getElementById('mw-level').value;
  const res = await api('/api/admin/wordbank', 'POST', { word, meaning, phonetic, level });
  if (res.error) { toast(res.error); return; }
  toast('添加成功');
  closeModal();
  loadAdminWords();
}

function editWord(wid) {
  // Find word from current table
  openModal('编辑词汇', `
    <div class="modal-body-section">
      <div class="form-group"><label>释义</label><input class="form-input" id="ew-meaning" placeholder="中文释义"></div>
      <div class="form-group"><label>音标</label><input class="form-input" id="ew-phonetic" placeholder="/fəˈnetɪk/"></div>
      <div class="form-group"><label>状态</label>
        <select class="form-input" id="ew-enabled"><option value="true">启用</option><option value="false">禁用</option></select>
      </div>
      <button class="btn btn-primary btn-full" onclick="submitEditWord(${wid})">保存</button>
    </div>`);
}

async function submitEditWord(wid) {
  const meaning = document.getElementById('ew-meaning').value.trim();
  const phonetic = document.getElementById('ew-phonetic').value.trim();
  const enabled = document.getElementById('ew-enabled').value === 'true';
  const data = {};
  if (meaning) data.meaning = meaning;
  if (phonetic) data.phonetic = phonetic;
  data.enabled = enabled;
  const res = await api(`/api/admin/wordbank/${wid}`, 'PUT', data);
  if (res.error) { toast(res.error); return; }
  toast('已更新');
  closeModal();
  loadAdminWords();
}

async function deleteWord(wid) {
  if (!confirm('确认删除该词汇？')) return;
  const res = await api(`/api/admin/wordbank/${wid}`, 'DELETE');
  if (res.error) { toast(res.error); return; }
  toast('已删除');
  loadAdminWords();
}

async function loadAdminRecords(page = adminState.recordPage) {
  adminState.recordPage = page;
  const res = await api(`/api/admin/records?page=${page}&per_page=20`);
  if (res.error) return;
  const tbody = document.getElementById('admin-records-body');
  tbody.innerHTML = (res.records || []).map(r => `
    <tr><td>${r.id}</td><td>${r.user_id || '匿名'}</td><td>${levelLabel(r.level)}</td>
    <td>${r.algo}</td><td>${r.score}</td><td>${Math.round(r.accuracy*100)}%</td>
    <td>${r.estimated_level || '-'}</td><td>${fmtDate(r.created_at)}</td></tr>`).join('');
  renderPagination('admin-records-pagination', page, Math.ceil(res.total / 20), p => loadAdminRecords(p));
}

async function adminSeedWords() {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '导入中...';
  const res = await api('/api/admin/wordbank/seed', 'POST');
  toast(res.message || res.error || '完成');
  btn.disabled = false;
  btn.textContent = '📥 导入词库到数据库';
  loadAdminStats();
}

// ── Utilities ──────────────────────────────────────────────
async function api(url, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (body) opts.body = JSON.stringify(body);
  try {
    const res = await fetch(url, opts);
    return res.json();
  } catch (e) {
    return { error: '网络错误' };
  }
}

function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function levelLabel(key) {
  return { primary: '小学', middle: '初中', high: '高中', all: '全部' }[key] || key;
}

function toast(msg, duration = 2500) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add('hidden'), duration);
}

function openModal(title, bodyHtml) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHtml;
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

function renderPagination(containerId, current, totalPages, handler) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (totalPages <= 1) { container.innerHTML = ''; return; }
  let html = '';
  for (let i = 1; i <= Math.min(totalPages, 10); i++) {
    html += `<button class="page-btn${i===current?' active':''}" onclick="(${handler})(${i})">${i}</button>`;
  }
  container.innerHTML = html;
}
