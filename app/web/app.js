const state = {
  // ── 认证状态 ──
  currentUser: null,       // { user_id, username, role, nickname, token }
  TOKEN_KEY: "anti_fraud_token",

  // ── 原有状态 ──
  activeScenarioId: null,
  reportHistory: [],
  reportHistoryMeta: null,
  scenarioCatalog: [],
  knowledgeScams: [],
  knowledgeLaws: [],

  // ── AI 对话状态 ──
  aiChatHistory: [],       // [{role: "user"|"assistant", content: "..."}]
  aiIsThinking: false,
};


function byId(id) {
  return document.getElementById(id);
}

function safeText(value, fallback = "-") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function renderLines(lines) {
  if (!Array.isArray(lines) || lines.length === 0) {
    return "-";
  }
  return lines.map((line, i) => `${i + 1}. ${line}`).join("\n");
}

function setOutput(id, text, riskLevel) {
  const el = byId(id);
  if (!el) { return; }
  el.textContent = text;
  el.classList.remove("risk-low", "risk-medium", "risk-high", "risk-critical");
  if (riskLevel) {
    el.classList.add(`risk-${riskLevel}`);
  }
}

function setReportExportEnabled(enabled) {
  const csvBtn = byId("reports-export-csv");
  const jsonBtn = byId("reports-export-json");
  if (csvBtn) csvBtn.disabled = !enabled;
  if (jsonBtn) jsonBtn.disabled = !enabled;
}

function clearReportHistoryCache() {
  state.reportHistory = [];
  state.reportHistoryMeta = null;
  setReportExportEnabled(false);
}

function verdictLabel(verdict) {
  if (verdict === "high_risk") return "高风险";
  if (verdict === "suspicious") return "可疑";
  return "相对安全";
}

function sanitizeFilenamePart(value) {
  return safeText(value, "all")
    .replace(/[^a-zA-Z0-9_-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);
}

function toCsvCell(value) {
  const escaped = safeText(value, "").replace(/"/g, '""');
  return `"${escaped}"`;
}

function downloadTextFile(fileName, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}


// ══════════════════════════════════════
// ═══  认证模块 (Auth)
// ══════════════════════════════════════

function getStoredToken() {
  try { return localStorage.getItem(state.TOKEN_KEY); } catch { return null; }
}

function setStoredToken(token) {
  try { localStorage.setItem(state.TOKEN_KEY, token); } catch {}
}

function clearStoredToken() {
  try { localStorage.removeItem(state.TOKEN_KEY); } catch {}
}

function getAuthHeaders() {
  const headers = {};
  const token = state.currentUser?.token || getStoredToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function initAuth() {
  const token = getStoredToken();
  if (!token) {
    showAuthPanel();
    return;
  }

  // 用 token 验证是否还有效
  try {
    const data = await requestJson("/auth/me", { method: "GET", headers: {} }, true);
    state.currentUser = {
      user_id: data.user_id,
      username: data.username,
      role: data.role,
      nickname: data.nickname,
      token: token,
    };
    showAppMain();
  } catch (_e) {
    clearStoredToken();
    showAuthPanel();
  }
}

function showAuthPanel() {
  byId("auth-overlay").style.display = "flex";
  byId("app-main").style.display = "none";
  state.currentUser = null;
}

function showAppMain() {
  byId("auth-overlay").style.display = "none";
  byId("app-main").style.display = "";
  updateNavUI();
  autoFillUserIdFields();
}

function updateNavUI() {
  const u = state.currentUser;
  if (!u) return;

  const welcome = byId("nav-welcome");
  const badge = byId("nav-badge");

  welcome.textContent = `欢迎，${u.nickname || u.username}`;

  const levelMap = { student: "🎓 学生", general: "👤 用户" };
  badge.textContent = levelMap[u.role] || u.role;
}

function autoFillUserIdFields() {
  const u = state.currentUser;
  if (!u) return;
  const displayName = u.nickname || u.username || "";
  const fields = ["chat-user-id", "report-user-id", "scenario-user-id", "progress-user-id"];
  fields.forEach((id) => {
    const el = byId(id);
    if (el) { el.value = displayName; el.dataset.userId = String(u.user_id); }
  });
}

// ── Tab 切换 ──
function bindAuthTabs() {
  document.querySelectorAll(".auth-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetTab = tab.dataset.tab;

      // 更新 tab 按钮状态
      document.querySelectorAll(".auth-tab").forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      // 切换表单
      byId("login-form").style.display = targetTab === "login" ? "" : "none";
      byId("register-form").style.display = targetTab === "register" ? "" : "none";

      hideAuthError();
    });
  });

  // 注册表单中的"去登录/去注册"链接
  document.querySelectorAll("[data-switch-tab]").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const target = link.dataset.switchTab;
      document.querySelector(`.auth-tab[data-tab="${target}"]`).click();
    });
  });

  // 密码强度提示
  byId("reg-password").addEventListener("input", () => {
    const pwd = byId("reg-password").value;
    const strengthEl = byId("pwd-strength");
    let label = "", cls = "";
    if (pwd.length < 6) { label = "太短"; cls = "weak"; }
    else if (pwd.length < 8) { label = "弱"; cls = "weak"; }
    else if (/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(pwd)) { label = "强 ✓"; cls = "strong"; }
    else if (/(?=.*[a-zA-Z])(?=.*\d)/.test(pwd)) { label = "中"; cls = "medium"; }
    else { label = "弱"; cls = "weak"; }

    strengthEl.textContent = label;
    strengthEl.className = `pwd-strength ${cls}`;
  });
}

function showAuthError(msg) {
  const el = byId("auth-error");
  el.textContent = msg;
  el.style.display = "";
}

function hideAuthError() {
  byId("auth-error").style.display = "none";
}

// ── 登录 ──
function bindLoginForm() {
  byId("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAuthError();

    const payload = {
      username: byId("login-username").value.trim(),
      password: byId("login-password").value,
    };

    const btn = byId("login-form").querySelector("button[type=submit]");
    btn.disabled = true;
    btn.textContent = "登录中...";

    try {
      const data = await requestJson("/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      }, false);

      state.currentUser = {
        user_id: data.user_id,
        username: data.username,
        role: data.role,
        nickname: data.nickname,
        token: data.access_token,
      };
      setStoredToken(data.access_token);
      showAppMain();
    } catch (err) {
      showAuthError(err.message || "登录失败，请检查用户名和密码");
    } finally {
      btn.disabled = false;
      btn.textContent = "登 录";
    }
  });
}

// ── 注册 ──
function bindRegisterForm() {
  byId("register-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    hideAuthError();

    const pwd = byId("reg-password").value;
    const confirmPwd = byId("reg-password-confirm").value;

    if (pwd !== confirmPwd) {
      showAuthError("两次输入的密码不一致");
      return;
    }

    const payload = {
      username: byId("reg-username").value.trim(),
      password: pwd,
      role: byId("reg-role").value,
      nickname: byId("reg-nickname").value.trim() || null,
    };

    const btn = byId("register-form").querySelector("button[type=submit]");
    btn.disabled = true;
    btn.textContent = "注册中...";

    try {
      const data = await requestJson("/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      }, false);

      state.currentUser = {
        user_id: data.user_id,
        username: data.username,
        role: data.role,
        nickname: data.nickname,
        token: data.access_token,
      };
      setStoredToken(data.access_token);
      showAppMain();
    } catch (err) {
      showAuthError(err.message || "注册失败，请稍后重试");
    } finally {
      btn.disabled = false;
      btn.textContent = "注 册";
    }
  });
}

// ── 登出 ──
function bindLogout() {
  byId("nav-logout").addEventListener("click", () => {
    clearStoredToken();
    showAuthPanel();
  });
}


// ══════════════════════════════════════
// ═══  AI 对话模块
// ══════════════════════════════════════

function createAIBubble(role, content) {
  const wrapper = document.createElement("div");
  wrapper.className = `ai-msg-bubble ${role === "user" ? "ai-user" : "ai-assistant"}`;

  const avatar = document.createElement("div");
  avatar.className = "bubble-avatar";
  avatar.textContent = role === "user" ? "😊" : "🤖";

  const bubbleContent = document.createElement("div");
  bubbleContent.className = "bubble-content";
  // 支持简单换行渲染
  bubbleContent.innerHTML = content.replace(/\n/g, "<br>");

  wrapper.appendChild(avatar);
  wrapper.appendChild(bubbleContent);
  return wrapper;
}

function scrollAIChatToBottom() {
  const container = byId("ai-chat-messages");
  container.scrollTop = container.scrollHeight;
}

async function sendAIMessage() {
  const input = byId("ai-chat-input");
  const message = input.value.trim();
  if (!message || state.aiIsThinking) return;

  // 显示用户消息
  const container = byId("ai-chat-messages");
  container.appendChild(createAIBubble("user", message));
  state.aiChatHistory.push({ role: "user", content: message });

  // 清空输入框
  input.value = "";
  input.disabled = true;
  byId("ai-send-btn").disabled = true;
  state.aiIsThinking = true;

  // 显示思考指示器
  const statusEl = byId("ai-status");
  statusEl.style.display = "";
  statusEl.textContent = "🤖 AI 正在思考...";
  scrollAIChatToBottom();

  try {
    const data = await requestJson("/ai/chat", {
      method: "POST",
      body: JSON.stringify({
        message: message,
        history: state.aiChatHistory.slice(0, -1),  // 不包含刚加的这条
      }),
    });

    // 显示 AI 回复
    container.appendChild(createAIBubble("assistant", data.reply));
    state.aiChatHistory.push({ role: "assistant", content: data.reply });

    statusEl.style.display = "none";
  } catch (err) {
    container.appendChild(createAIBubble("assistant", `⚠️ ${err.message}`));
    statusEl.style.display = "none";
  } finally {
    input.disabled = false;
    byId("ai-send-btn").disabled = false;
    state.aiIsThinking = false;
    input.focus();
    scrollAIChatToBottom();
  }
}

function bindAIChatForm() {
  byId("ai-chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    await sendAIMessage();
  });
}


// ══════════════════════════════════════
// ═══  排行榜模块
// ══════════════════════════════════════

const RANK_ICONS = ["🥇", "🥈", "🥉"];

function renderLeaderboard(data) {
  const container = byId("leaderboard-table");
  container.textContent = "";
  container.classList.remove("muted");

  if (!data.items || data.items.length === 0) {
    container.innerHTML = '<div class="muted">暂无排行数据</div>';
    return;
  }

  const table = document.createElement("table");
  table.className = "lb-table";

  // 表头
  const thead = document.createElement("thead");
  thead.innerHTML = `
    <tr>
      <th>排名</th>
      <th>用户</th>
      <th>角色</th>
      <th class="num">等级</th>
      <th class="num">积分</th>
      <th>勋章</th>
    </tr>`;
  table.appendChild(thead);

  const tbody = document.createElement("tbody");

  const currentUid = state.currentUser?.user_id;

  data.items.forEach((entry) => {
    const tr = document.createElement("tr");
    if (entry.user_id === currentUid) tr.className = "lb-me";

    const rankCell = entry.rank <= 3
      ? `<span class="rank-icon">${RANK_ICONS[entry.rank - 1]}</span>`
      : `<span class="rank-num">${entry.rank}</span>`;

    const badgesText = Array.isArray(entry.badges) && entry.badges.length > 0
      ? entry.badges.join(" · ")
      : "-";

    const roleLabel = entry.role === "student" ? "🎓 学生" : "👤 用户";

    tr.innerHTML = `
      <td>${rankCell}</td>
      <td>${safeText(entry.nickname || entry.username)}</td>
      <td>${roleLabel}</td>
      <td class="num">Lv.${entry.level}</td>
      <td class="num">${entry.points}</td>
      <td><span class="badge-tags">${badgesText}</span></td>`;
    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  container.appendChild(table);
}

async function fetchLeaderboard() {
  const container = byId("leaderboard-table");
  container.textContent = "加载中...";

  try {
    const data = await requestJson("/leaderboard?top=20", { method: "GET", headers: {} }, true);
    renderLeaderboard(data);
  } catch (err) {
    container.textContent = `加载失败：${err.message}`;
  }
}

function bindLeaderboardActions() {
  byId("leaderboard-refresh").addEventListener("click", fetchLeaderboard);
}


// ══════════════════════════════════════
// ═══  原有功能（保持不变）
// ══════════════════════════════════════

function renderReportHistory(data, filters) {
  const output = byId("reports-output");
  if (!output) { return; }

  output.textContent = "";
  output.classList.remove("muted", "risk-low", "risk-medium", "risk-high", "risk-critical");

  const summary = document.createElement("div");
  summary.className = "report-summary";
  summary.textContent = `用户: ${safeText(data.user_id)} | 返回条数: ${safeText(data.total)} | 时间范围: ${safeText(filters.startAt, "不限")} ~ ${safeText(filters.endAt, "不限")}`;
  output.appendChild(summary);

  const list = document.createElement("div");
  list.className = "report-list";

  data.items.forEach((item, index) => {
    const keywords = Array.isArray(item.matched_keywords) && item.matched_keywords.length > 0 ? item.matched_keywords.join(" / ") : "无";
    const row = document.createElement("div");
    row.className = `report-item verdict-${safeText(item.verdict, "safe")}`;
    row.textContent = `${index + 1}. ${safeText(item.created_at)} | ${verdictLabel(item.verdict)} | score=${safeText(item.score)} | keywords=${keywords}`;
    list.appendChild(row);
  });

  output.appendChild(list);
}

function renderKnowledgeDigest(scams, laws) {
  const output = byId("knowledge-output");
  if (!output) { return; }

  output.textContent = "";
  output.classList.remove("muted", "risk-low", "risk-medium", "risk-high", "risk-critical");

  const summary = document.createElement("div");
  summary.className = "knowledge-summary";
  summary.textContent = `已覆盖骗局类型 ${safeText(scams.length, 0)} 类，法规依据 ${safeText(laws.length, 0)} 条。建议每周至少完成 2 个关卡训练并复盘 1 次举报记录。`;
  output.appendChild(summary);

  const grid = document.createElement("div");
  grid.className = "knowledge-grid";

  const scamBlock = document.createElement("div");
  scamBlock.className = "knowledge-block";
  const scamTitle = document.createElement("h3");
  scamTitle.textContent = "高频骗局速记";
  scamBlock.appendChild(scamTitle);

  const scamList = document.createElement("ul");
  scamList.className = "knowledge-list";
  scams.slice(0, 7).forEach((item) => {
    const line = document.createElement("li");
    const firstFlag = Array.isArray(item.red_flags) && item.red_flags.length > 0 ? item.red_flags[0] : "保持核验";
    const firstPrevention = Array.isArray(item.prevention) && item.prevention.length > 0 ? item.prevention[0] : "先核验再操作";
    line.textContent = `${safeText(item.name)}: 红旗-${firstFlag}；应对-${firstPrevention}`;
    scamList.appendChild(line);
  });
  scamBlock.appendChild(scamList);

  const lawBlock = document.createElement("div");
  lawBlock.className = "knowledge-block";
  const lawTitle = document.createElement("h3");
  lawTitle.textContent = "法律与合规提醒";
  lawBlock.appendChild(lawTitle);

  const lawList = document.createElement("ul");
  lawList.className = "knowledge-list";
  laws.slice(0, 5).forEach((item) => {
    const highlight = Array.isArray(item.highlights) && item.highlights.length > 0 ? item.highlights[0] : "";
    const line = document.createElement("li");
    line.textContent = `${safeText(item.name)}: ${safeText(highlight)}`;
    lawList.appendChild(line);
  });
  lawBlock.appendChild(lawList);

  const checklistBlock = document.createElement("div");
  checklistBlock.className = "knowledge-block";
  const checklistTitle = document.createElement("h3");
  checklistTitle.textContent = "30秒风险自检清单 + AI诈骗识别";
  checklistBlock.appendChild(checklistTitle);

  const checklist = document.createElement("ul");
  checklist.className = "knowledge-list";
  [
    "是否要求 先转账/先缴费/先验证 ?",
    "是否催促限时处理并阻止你咨询他人？",
    "是否发送陌生链接、二维码或安装包？",
    "是否索要验证码、支付密码或屏幕共享？",
    "是否要求你脱离官方平台私下交易？",
    "视频通话中对方面部表情/声音是否有异常？（AI换脸检测）",
    "是否收到含自己面部的合成视频被勒索？（深度伪造识别）",
  ].forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    checklist.appendChild(li);
  });
  checklistBlock.appendChild(checklist);

  grid.appendChild(scamBlock);
  grid.appendChild(lawBlock);
  grid.appendChild(checklistBlock);
  output.appendChild(grid);
}

function recommendScenarioPractice() {
  const output = byId("knowledge-output");
  if (!output) { return; }

  if (!Array.isArray(state.scenarioCatalog) || state.scenarioCatalog.length === 0) {
    setOutput("knowledge-output", "暂无可推荐关卡，请先刷新关卡列表。", "medium");
    return;
  }

  const scenario = state.scenarioCatalog[Math.floor(Math.random() * state.scenarioCatalog.length)];
  const matchedScam = Array.isArray(state.knowledgeScams)
    ? state.knowledgeScams.find((item) => item.type === scenario.scam_type)
    : null;

  const scenarioSelect = byId("scenario-select");
  if (scenarioSelect) scenarioSelect.value = scenario.id;

  const tip = matchedScam && Array.isArray(matchedScam.prevention) && matchedScam.prevention.length > 0
    ? matchedScam.prevention[0]
    : "先核验身份和平台，再进行任何付款。";

  const msg = `本次推荐: ${safeText(scenario.id)} | ${safeText(scenario.title)}。建议先记住这条防范动作: ${tip}`;
  setOutput("scenario-stage", msg, "medium");
}

async function refreshKnowledgeDigest() {
  setOutput("knowledge-output", "正在加载知识速览...");

  try {
    const [scams, laws] = await Promise.all([
      requestJson("/knowledge/scams", { method: "GET", headers: {} }),
      requestJson("/knowledge/laws", { method: "GET", headers: {} }),
    ]);
    state.knowledgeScams = Array.isArray(scams) ? scams : [];
    state.knowledgeLaws = Array.isArray(laws) ? laws : [];
    renderKnowledgeDigest(state.knowledgeScams, state.knowledgeLaws);
  } catch (error) {
    setOutput("knowledge-output", `知识速览加载失败: ${error.message}`);
  }
}

/**
 * 统一请求方法 — 自动附带认证头
 * @param {string} url
 * @param {object} options - fetch options
 * @param {boolean} requireAuth - 是否必须带 token（默认 false）
 */
async function requestJson(url, options = {}, requireAuth = false) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = response.headers.get("Content-Type") || "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    // 如果是 401 且有 stored token，清除并跳登录
    if (response.status === 401) {
      clearStoredToken();
      // 不在这里直接跳转，让调用者处理
    }
    const message = typeof body === "string" ? body : safeText(body.detail, "请求失败");
    throw new Error(`${response.status} ${message}`);
  }

  return body;
}

async function loadHealth() {
  const indicator = byId("health-indicator");
  try {
    const data = await requestJson("/health", { method: "GET", headers: {} });
    indicator.textContent = `系统状态: ${safeText(data.status)} | 服务: ${safeText(data.service)}`;
  } catch (error) {
    indicator.textContent = `系统状态检测失败: ${error.message}`;
  }
}

function bindChatForm() {
  const form = byId("chat-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      user_id: Number(byId("chat-user-id").dataset.userId) || 0,
      message: byId("chat-message").value.trim(),
      channel: "web",
      emotion: byId("chat-emotion").value || null,
      user_profile: {
        role: byId("chat-role").value,
        risk_tolerance: byId("chat-risk-tolerance").value,
      },
    };

    setOutput("chat-output", "正在研判中...");

    try {
      const data = await requestJson("/chat", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      const text = [
        `意图: ${safeText(data.intent)}`,
        `风险等级: ${safeText(data.risk_level)}`,
        `风险分: ${safeText(data.risk_score)}`,
        `匹配骗局: ${Array.isArray(data.matched_scams) && data.matched_scams.length > 0 ? data.matched_scams.join(" / ") : "未命中"}`,
        "",
        `回复:\n${safeText(data.reply)}`,
        "",
        `劝阻话术:\n${renderLines(data.intervention_script)}`,
        "",
        `建议:\n${renderLines(data.recommendations)}`,
        "",
        `奖励: +${safeText(data.points_gained, 0)} 分 | 总分: ${safeText(data.total_points, 0)} | 勋章: ${Array.isArray(data.badges) && data.badges.length > 0 ? data.badges.join(" / ") : "无"}`,
      ].join("\n");

      setOutput("chat-output", text, data.risk_level);
    } catch (error) {
      setOutput("chat-output", `研判失败: ${error.message}`);
    }
  });
}

function bindReportForm() {
  const form = byId("report-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      user_id: Number(byId("report-user-id").dataset.userId) || 0,
      url: byId("report-url").value.trim() || null,
      content: byId("report-content").value.trim() || null,
      channel: "web",
    };

    setOutput("report-output", "正在分析举报内容...");

    try {
      const data = await requestJson("/report", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      const text = [
        `举报单号: ${safeText(data.report_id)}`,
        `判定: ${safeText(data.verdict)}`,
        `风险分: ${safeText(data.risk_score)}`,
        `命中关键词: ${Array.isArray(data.matched_keywords) && data.matched_keywords.length > 0 ? data.matched_keywords.join(" / ") : "无"}`,
        "",
        `判定原因:\n${renderLines(data.reasons)}`,
        "",
        `URL特征:\n${renderLines(data.url_flags)}`,
        "",
        `建议:\n${renderLines(data.recommendations)}`,
      ].join("\n");

      const riskLevel = data.verdict === "high_risk" ? "critical" : data.verdict === "suspicious" ? "medium" : "low";
      setOutput("report-output", text, riskLevel);
    } catch (error) {
      setOutput("report-output", `举报分析失败: ${error.message}`);
    }
  });
}

async function refreshScenarios() {
  const select = byId("scenario-select");
  select.innerHTML = "";

  try {
    const items = await requestJson("/scenarios", { method: "GET", headers: {} });
    state.scenarioCatalog = Array.isArray(items) ? items : [];

    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = `${item.id} | ${item.title} | ${item.scam_type}`;
      select.appendChild(option);
    });

    if (items.length === 0) {
      const empty = document.createElement("option");
      empty.value = ""; empty.textContent = "暂无关卡";
      select.appendChild(empty);
    }
  } catch (error) {
    state.scenarioCatalog = [];
    const fail = document.createElement("option");
    fail.value = ""; fail.textContent = `加载失败: ${error.message}`;
    select.appendChild(fail);
  }
}

function renderScenarioStep(data) {
  const stage = byId("scenario-stage");
  stage.classList.remove("muted"); stage.textContent = "";

  const header = document.createElement("div");
  header.textContent = `关卡: ${safeText(data.scenario_id)} | 步骤: ${safeText(data.step_index)} | 结束: ${data.finished ? "是" : "否"}`;
  stage.appendChild(header);

  const feedback = document.createElement("pre");
  feedback.textContent = `反馈: ${safeText(data.feedback)}\n奖励: +${safeText(data.points_gained)} | 总分: ${safeText(data.total_points)}\n勋章: ${Array.isArray(data.badges) && data.badges.length > 0 ? data.badges.join(" / ") : "无"}`;
  stage.appendChild(feedback);

  if (!data.finished && data.next_prompt) {
    const prompt = document.createElement("pre");
    prompt.textContent = `下一题: ${data.next_prompt}`;
    stage.appendChild(prompt);

    const list = document.createElement("div"); list.className = "option-list";
    data.next_options.forEach((optionText, index) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "option-btn";
      button.textContent = `${index}. ${optionText}`;
      button.addEventListener("click", () => answerScenario(index));
      list.appendChild(button);
    });
    stage.appendChild(list);
  } else if (data.finished) {
    const done = document.createElement("pre");
    done.textContent = "闯关完成，已发放完成奖励。可重新选择关卡继续训练。";
    stage.appendChild(done);
    state.activeScenarioId = null;
  }
}

async function startScenario() {
  const userId = Number(byId("scenario-user-id").dataset.userId) || 0;
  const scenarioId = byId("scenario-select").value;

  if (!userId || !scenarioId) {
    setOutput("scenario-stage", "请填写用户ID并选择关卡。");
    return;
  }

  setOutput("scenario-stage", "正在开始关卡...");

  try {
    const data = await requestJson("/scenarios/start", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, scenario_id: scenarioId }),
    });

    state.activeScenarioId = data.scenario_id;

    const stage = byId("scenario-stage");
    stage.classList.remove("muted"); stage.textContent = "";

    const intro = document.createElement("pre");
    intro.textContent = `关卡: ${data.scenario_id} | ${data.title}\n步骤: ${data.step_index}\n题目: ${data.prompt}`;
    stage.appendChild(intro);

    const list = document.createElement("div"); list.className = "option-list";
    data.options.forEach((optionText, index) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "option-btn";
      button.textContent = `${index}. ${optionText}`;
      button.addEventListener("click", () => answerScenario(index));
      list.appendChild(button);
    });
    stage.appendChild(list);
  } catch (error) {
    setOutput("scenario-stage", `开始失败: ${error.message}`);
  }
}

async function answerScenario(optionIndex) {
  const userId = Number(byId("scenario-user-id").dataset.userId) || 0;
  if (!userId || !state.activeScenarioId) {
    setOutput("scenario-stage", "请先开始关卡。"); return;
  }

  setOutput("scenario-stage", "正在提交答案...");

  try {
    const data = await requestJson("/scenarios/answer", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, option_index: optionIndex }),
    });
    renderScenarioStep(data);
  } catch (error) {
    setOutput("scenario-stage", `答题失败: ${error.message}`);
  }
}

async function fetchProgress() {
  const userId = Number(byId("progress-user-id").dataset.userId) || 0;
  if (!userId) { setOutput("progress-output", "请输入用户ID"); return; }

  setOutput("progress-output", "正在查询...");

  try {
    const data = await requestJson(`/users/${encodeURIComponent(userId)}/progress`, {
      method: "GET", headers: {},
    });

    const text = [
      `用户: ${safeText(data.user_id)}`,
      `等级: Lv.${safeText(data.level)}`,
      `积分: ${safeText(data.points)}`,
      `勋章: ${Array.isArray(data.badges) && data.badges.length > 0 ? data.badges.join(" / ") : "无"}`,
      `已提交举报: ${safeText(data.reports_submitted)}`,
      `已完成关卡: ${safeText(data.scenarios_completed)}`,
    ].join("\n");

    setOutput("progress-output", text, "low");
  } catch (error) {
    setOutput("progress-output", `查询失败: ${error.message}`);
  }
}

async function fetchReportHistory() {
  const userId = Number(byId("progress-user-id").dataset.userId) || 0;
  const limitRaw = byId("reports-limit").value;
  const limitNum = Number.parseInt(limitRaw, 10);
  const limit = Number.isNaN(limitNum) ? 5 : Math.max(1, Math.min(20, limitNum));
  const startAt = byId("reports-start-at").value.trim();
  const endAt = byId("reports-end-at").value.trim();

  if (!userId) { clearReportHistoryCache(); setOutput("reports-output", "请输入用户ID"); return; }

  if (startAt && endAt && startAt > endAt) {
    clearReportHistoryCache(); setOutput("reports-output", "开始时间不能晚于结束时间"); return;
  }

  setOutput("reports-output", "正在查询历史举报...");

  try {
    const params = new URLSearchParams({ limit: String(limit) });
    if (startAt) params.set("start_at", startAt);
    if (endAt) params.set("end_at", endAt);

    const data = await requestJson(`/users/${encodeURIComponent(userId)}/reports?${params.toString()}`, {
      method: "GET", headers: {},
    });

    if (!Array.isArray(data.items) || data.items.length === 0) {
      clearReportHistoryCache();
      setOutput("reports-output", `用户 ${safeText(data.user_id)} 在 ${safeText(startAt, "不限")} ~ ${safeText(endAt, "不限")} 范围内暂无历史举报`, "low");
      return;
    }

    state.reportHistory = data.items;
    state.reportHistoryMeta = {
      userId: safeText(data.user_id), startAt, endAt, fetchedAt: new Date().toISOString(),
    };
    setReportExportEnabled(true);
    renderReportHistory(data, { startAt, endAt });
  } catch (error) {
    clearReportHistoryCache();
    setOutput("reports-output", `查询历史举报失败: ${error.message}`);
  }
}

function exportReportHistoryAsCsv() {
  if (!state.reportHistoryMeta || state.reportHistory.length === 0) {
    setOutput("reports-output", "暂无可导出的历史举报记录，请先查询。", "low");
    return;
  }
  const header = ["report_id", "user_id", "created_at", "verdict", "score", "matched_keywords"];
  const rows = state.reportHistory.map((item) => [
    safeText(item.report_id), safeText(item.user_id), safeText(item.created_at),
    safeText(item.verdict), safeText(item.score),
    Array.isArray(item.matched_keywords) ? item.matched_keywords.join("|") : "",
  ]);
  const csv = [header.map(toCsvCell).join(","), ...rows.map((row) => row.map(toCsvCell).join(","))].join("\n");
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const fileName = `reports_${sanitizeFilenamePart(state.reportHistoryMeta.userId)}_${timestamp}.csv`;
  downloadTextFile(fileName, `\uFEFF${csv}`, "text/csv;charset=utf-8");
}

function exportReportHistoryAsJson() {
  if (!state.reportHistoryMeta || state.reportHistory.length === 0) {
    setOutput("reports-output", "暂无可导出的历史举报记录，请先查询。", "low");
    return;
  }
  const payload = { meta: state.reportHistoryMeta, items: state.reportHistory };
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const fileName = `reports_${sanitizeFilenamePart(state.reportHistoryMeta.userId)}_${timestamp}.json`;
  downloadTextFile(fileName, JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
}

function bindScenarioActions() {
  byId("scenario-refresh").addEventListener("click", refreshScenarios);
  byId("scenario-start").addEventListener("click", startScenario);
}

function bindProgressAction() {
  byId("progress-fetch").addEventListener("click", fetchProgress);
  byId("reports-fetch").addEventListener("click", fetchReportHistory);
  byId("reports-export-csv").addEventListener("click", exportReportHistoryAsCsv);
  byId("reports-export-json").addEventListener("click", exportReportHistoryAsJson);
}

function bindKnowledgeAction() {
  byId("knowledge-refresh").addEventListener("click", refreshKnowledgeDigest);
  byId("knowledge-random-scenario").addEventListener("click", recommendScenarioPractice);
}

// ═══ 启动入口 ═══
async function bootstrap() {
  // 先初始化认证状态
  await initAuth();

  // 绑定所有事件处理器（无论登录与否都绑定）
  bindAuthTabs();
  bindLoginForm();
  bindRegisterForm();
  bindLogout();
  bindAIChatForm();
  bindLeaderboardActions();
  bindChatForm();
  bindReportForm();
  bindScenarioActions();
  bindProgressAction();
  bindKnowledgeAction();
  clearReportHistoryCache();

  // 如果已登录，并行加载所有数据
  if (state.currentUser) {
    await Promise.all([
      loadHealth(),
      refreshScenarios(),
      refreshKnowledgeDigest(),
      fetchLeaderboard(),
    ]);
  }
}

bootstrap();
