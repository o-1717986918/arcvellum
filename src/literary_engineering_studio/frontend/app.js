const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
const UI_VERSION = "0.2.0";
let dashboardTimer = null;
let dashboardStream = null;
let activityTimer = null;
let activityStream = null;
let libraryTimer = null;
let libraryStream = null;
let librarySnapshot = null;
let activitySnapshot = null;
let activeLibraryKind = "drafts";
let currentChoices = [];
let activityChoices = [];
let selectedLibraryItem = null;
let visibleLibraryItems = [];
let serverHealth = null;
let workerJobStream = null;
let workerJobTimer = null;
let currentProject = null;
let recentProjects = [];

const routeNames = {
  "scene-development": "场景开发",
  "longform-planning": "长篇规划",
  "source-ingest": "旧文导入",
  "style-engineering": "文风工程",
  "character-and-world-assets": "人物与世界资产",
  "review-and-audit": "审查与审计",
  "export-and-release": "导出与发布",
};

const sectionNames = {
  drafts: "正文草稿",
  characters: "人物设定",
  world: "世界观设定",
  scenes: "场景设定",
  branches: "推演分支",
  style: "文风挂载",
  reviews: "审查证据",
  word_budget: "字数预算",
  rhythm: "节奏衔接",
  canon_patches: "写回候选",
};

const sectionIcons = {
  drafts: "manuscript-page",
  characters: "character-dossier",
  world: "archive-folder",
  scenes: "dashboard-board",
  branches: "branch-cards",
  style: "style-card",
  reviews: "style-card",
  word_budget: "dashboard-board",
  rhythm: "branch-cards",
  canon_patches: "archive-folder",
};

function iconPath(name) {
  return `/ui/assets/editorial-icons/${name}.png`;
}

function sectionIcon(kind) {
  return iconPath(sectionIcons[kind] || "archive-folder");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let body = text;
  try { body = JSON.parse(text); } catch {}
  if (!response.ok) {
    throw new Error(typeof body === "object" ? body.detail || "请求失败" : body);
  }
  return body;
}

function formData(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  form.querySelectorAll("input[type=checkbox]").forEach((item) => {
    data[item.name] = item.checked;
  });
  return data;
}

function setSharedProjectRoot(value) {
  if (!value) return;
  $$("form:not(#openProjectForm) input[name=project_root]").forEach((item) => { item.value = value; });
  localStorage.setItem("lesCurrentProject", value);
}

function setSharedStyleLibraryRoot(value) {
  if (!value) return;
  $$("input[name=style_library_root]").forEach((item) => { item.value = value; });
}

function sharedProjectRoot() {
  return currentProject?.path || $("#dashboardForm")?.project_root.value || $("#activityForm")?.project_root.value || $("#libraryForm")?.project_root.value || $("#styleForm")?.project_root.value || "";
}

async function loadProjects() {
  const result = await api("/projects");
  recentProjects = result.projects || [];
  const preferred = result.current_project || localStorage.getItem("lesCurrentProject") || "";
  const selected = recentProjects.find((item) => item.path === preferred) || null;
  setCurrentProject(selected);
  renderRecentProjects();
  if (selected) await loadDirections();
}

function setCurrentProject(project) {
  currentProject = project || null;
  const name = $("#currentProjectName");
  const meta = $("#currentProjectMeta");
  if (!project) {
    name.textContent = "尚未选择";
    meta.textContent = "从项目中心创建或打开作品";
    return;
  }
  setSharedProjectRoot(project.path);
  name.textContent = project.title || "未命名作品";
  meta.textContent = `${workTypeName(project.work_type)} · 目标 ${formatTargetLength(project.target_length)}`;
}

function renderRecentProjects() {
  const container = $("#recentProjects");
  $("#projectCount").textContent = recentProjects.length ? `${recentProjects.length} 个可继续项目` : "还没有登记项目";
  container.classList.toggle("empty", !recentProjects.length);
  container.innerHTML = recentProjects.length
    ? recentProjects.map((project, index) => `
        <article class="recent-project-card ${currentProject?.path === project.path ? "active" : ""}">
          <div class="project-card-index">${String(index + 1).padStart(2, "0")}</div>
          <div>
            <span>${escapeHtml(workTypeName(project.work_type))}</span>
            <h3>${escapeHtml(project.title || "未命名作品")}</h3>
            <p>${escapeHtml(project.premise || project.genre || "项目已经建立，等待继续完善创作方向。")}</p>
          </div>
          <dl>
            <div><dt>目标规模</dt><dd>${escapeHtml(formatTargetLength(project.target_length))}</dd></div>
            <div><dt>当前阶段</dt><dd>${escapeHtml(projectStatusName(project.status))}</dd></div>
            <div><dt>创作指令</dt><dd>${Number(project.direction_count || 0)} 条</dd></div>
          </dl>
          <button class="open-recent-project ${currentProject?.path === project.path ? "primary" : ""}" data-project-index="${index}">${currentProject?.path === project.path ? "当前作品" : "继续创作"}</button>
        </article>
      `).join("")
    : "创建新作品，或打开一个已有文学工程项目。";
}

async function createProjectFromClient() {
  $("#projectFeedback").textContent = "正在建立作品结构与正式流程……";
  const data = formData($("#createProjectForm"));
  data.target_length = Number(data.target_length || 30000);
  const result = await api("/projects/create", { method: "POST", body: JSON.stringify(data) });
  await loadProjects();
  if (result.project) setCurrentProject(result.project);
  activateView("dashboard");
  await loadDashboard();
  await loadDirections();
  $("#projectFeedback").textContent = `《${result.project?.title || "新作品"}》已经建立，可以开始规划。`;
}

async function openProjectFromClient(projectRoot = "") {
  const value = projectRoot || $("#openProjectForm").project_root.value.trim();
  if (!value) throw new Error("请填写已有作品的项目目录。");
  $("#projectFeedback").textContent = "正在读取作品档案与流程状态……";
  const result = await api("/projects/open", { method: "POST", body: JSON.stringify({ project_root: value }) });
  setCurrentProject(result.project);
  await loadProjects();
  activateView("dashboard");
  await loadDashboard();
  await loadDirections();
  $("#projectFeedback").textContent = `已经打开《${result.project?.title || "当前作品"}》。`;
}

async function loadDirections() {
  const root = sharedProjectRoot();
  const thread = $("#directionThread");
  if (!root) {
    thread.classList.add("empty");
    thread.textContent = "选择项目后，你可以在这里持续补充剧情方向、人物偏好、节奏要求和需要回避的内容。";
    return;
  }
  const result = await api(`/projects/directions?project_root=${encodeURIComponent(root)}&limit=20`);
  const items = result.items || [];
  thread.classList.toggle("empty", !items.length);
  thread.innerHTML = items.length
    ? items.slice().reverse().map((item) => `
        <article class="direction-message">
          <span>你的创作方向 · ${escapeHtml(formatTime(item.recorded_at))}</span>
          <p>${escapeHtml(item.message).replace(/\n/g, "<br>")}</p>
        </article>
      `).join("")
    : "尚未追加创作方向。项目最初设定仍会进入任务上下文。";
}

async function submitDirection(goToWorker = false) {
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先在项目中心选择一个作品。");
  const field = $("#directionForm").message;
  const message = field.value.trim();
  if (!message) throw new Error("请先写下要补充的创作方向。");
  await api("/projects/directions", { method: "POST", body: JSON.stringify({ project_root: root, message }) });
  field.value = "";
  await loadDirections();
  await loadProjects();
  if (goToWorker) {
    activateView("activity");
    await loadActivity();
  }
}

function workTypeName(value) {
  return ({ novel: "长篇小说", screenplay: "剧本", "pseudo-record": "伪记录作品" })[value] || "文学项目";
}

function projectStatusName(value) {
  return ({ planning: "规划中", drafting: "创作中", review: "审查中", complete: "已完成" })[value] || value || "规划中";
}

function formatTargetLength(value) {
  const count = Number(value || 0);
  if (count >= 10000) return `${(count / 10000).toFixed(count % 10000 ? 1 : 0)} 万字`;
  return count ? `${count} 字` : "待规划";
}

async function loadHealth() {
  try {
    const health = await api("/health");
    serverHealth = health;
    const serverVersion = health.version || "unknown";
    const stale = serverVersion !== UI_VERSION;
    $("#healthDot").classList.add("ok");
    $("#healthText").textContent = stale
      ? `本地服务已连接，版本 ${serverVersion}，建议重启到 ${UI_VERSION}`
      : `Studio 已连接，版本 ${serverVersion}`;
  } catch {
    serverHealth = null;
    $("#healthDot").classList.remove("ok");
    $("#healthText").textContent = "API 未连接";
  }
}

async function loadRuntimes() {
  const result = await api("/runtime/adapters");
  const items = result.items || [];
  $("#runtimeCards").classList.toggle("empty", !items.length);
  $("#runtimeCards").innerHTML = items.length
    ? items.map((item) => `
        <article class="runtime-card ${item.available ? "ready" : "unavailable"}">
          <span>${escapeHtml(runtimeName(item.runtime))}</span>
          <b>${item.available ? "可用" : "暂不可用"}</b>
          <p>${escapeHtml(item.detail || item.executable || "未返回检测信息")}</p>
        </article>
      `).join("")
    : "没有发现可用的 Agent 运行时。";
}

function workerPayload() {
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前文学项目目录。");
  const data = formData($("#workerForm"));
  return {
    project_root: root,
    route: data.route || "scene-development",
    runtime: data.runtime || "host-agent",
  };
}

async function prepareWorkerTask() {
  renderWorkerStatus({ status: "preparing", message: "正在向文学工程 CLI 领取并打开下一项正式任务。" });
  const result = await api("/worker/prepare", { method: "POST", body: JSON.stringify(workerPayload()) });
  renderWorkerStatus(result);
  await loadActivity();
}

async function runWorkerTask() {
  const payload = workerPayload();
  if (payload.runtime === "host-agent") {
    await prepareWorkerTask();
    return;
  }
  renderWorkerStatus({ status: "queued", message: `正在启动 ${runtimeName(payload.runtime)}。` });
  const job = await api("/worker/run", { method: "POST", body: JSON.stringify(payload) });
  watchWorkerJob(job.job_id);
}

function watchWorkerJob(jobId) {
  if (workerJobStream) workerJobStream.close();
  if (workerJobTimer) clearInterval(workerJobTimer);
  if (window.EventSource) {
    workerJobStream = new EventSource(`/worker/jobs/${encodeURIComponent(jobId)}/stream`);
    workerJobStream.addEventListener("worker", (event) => {
      const payload = JSON.parse(event.data);
      renderWorkerStatus(payload.result && Object.keys(payload.result).length ? payload.result : payload);
      if (!["queued", "running"].includes(payload.status)) {
        workerJobStream.close();
        workerJobStream = null;
        guarded(loadActivity);
        guarded(loadDashboard);
      }
    });
    workerJobStream.onerror = () => {
      workerJobStream?.close();
      workerJobStream = null;
      startWorkerJobPolling(jobId);
    };
    return;
  }
  startWorkerJobPolling(jobId);
}

function startWorkerJobPolling(jobId) {
  const poll = async () => {
    const payload = await api(`/worker/jobs/${encodeURIComponent(jobId)}`);
    renderWorkerStatus(payload.result && Object.keys(payload.result).length ? payload.result : payload);
    if (!["queued", "running"].includes(payload.status)) {
      clearInterval(workerJobTimer);
      workerJobTimer = null;
      await loadActivity();
      await loadDashboard();
    }
  };
  guarded(poll);
  workerJobTimer = setInterval(() => guarded(poll), 1500);
}

function renderWorkerStatus(payload) {
  const status = payload.status || "unknown";
  const copy = {
    preparing: "正在准备隔离任务",
    queued: "任务已进入执行队列",
    running: "Agent 正在执行当前任务",
    prepared: "隔离任务已经准备好",
    waiting_host_agent: "等待当前宿主 Agent 接管",
    waiting_human: "等待你的决定",
    complete: "任务已通过 CLI 验收",
    blocked_by_core_gate: "任务被正式门禁拦下",
    runtime_failed: "Agent 运行失败",
    failed: "执行失败",
    route_ready: "当前路线已经就绪",
  };
  const target = $("#workerStatus");
  target.className = `worker-status status-${escapeHtml(status)}`;
  target.innerHTML = `
    <b>${escapeHtml(copy[status] || friendlyMessage(status))}</b>
    <p>${escapeHtml(payload.message || payload.error || "正在等待进一步状态。")}</p>
    ${payload.task_id ? `<small>任务：${escapeHtml(shortTaskId(payload.task_id))}</small>` : ""}
    ${payload.workspace ? `<small>隔离工作区：${escapeHtml(shortPath(payload.workspace))}</small>` : ""}
  `;
}

function runtimeName(value) {
  const names = {
    "host-agent": "当前宿主 Agent",
    "claude-code": "Claude Code",
    "codex-cli": "Codex CLI",
  };
  return names[value] || value || "未知运行时";
}

async function loadDashboard() {
  const form = $("#dashboardForm");
  const root = form.project_root.value || $("#styleForm")?.project_root.value;
  if (!root) throw new Error("请先填写当前项目目录。");
  setSharedProjectRoot(root);
  $("#dashboardStatus").textContent = "正在刷新";
  const [result, library, activity] = await Promise.all([
    api(`/workflow/dashboard?project_root=${encodeURIComponent(root)}`),
    api(`/project/library?project_root=${encodeURIComponent(root)}`).catch((error) => ({ ok: false, error: error.message || String(error) })),
    loadActivitySnapshot(root).catch((error) => ({ ok: false, error: error.message || String(error) })),
  ]);
  if (library.ok !== false) librarySnapshot = library;
  if (activity.ok !== false) activitySnapshot = activity;
  renderDashboard(result, library, activity);
  return result;
}

function renderDashboard(result, library = null, activity = null) {
  const dashboard = result.dashboard || {};
  const summary = result.summary || dashboard.summary || {};
  const actions = result.next_actions || [];
  const routes = result.route_audits || [];
  const blocking = Number(summary.blocking_count || 0);
  const stateBlocked = Number(summary.state_blocked_count || 0);
  const pending = Number(summary.pending_task_count || 0);
  const missing = Number(summary.missing_expected_count || 0);
  const totalTrouble = blocking + stateBlocked + pending + missing;

  $("#dashboardHeadline").textContent = totalTrouble
    ? `项目还不能放心交付，优先处理 ${totalTrouble} 类阻塞信号。`
    : "项目状态很干净，可以进入下一步创作或发布检查。";
  $("#dashboardNarrative").textContent = dashboardNarrative({ blocking, stateBlocked, pending, missing, actions });
  $("#dashboardStatus").textContent = dashboard.generated_at ? `已刷新 ${formatTime(dashboard.generated_at)}` : "已刷新";

  const metrics = [
    ["已就绪路线", summary.ready_count ?? 0, "可以继续使用的正式流程"],
    ["流程门禁", blocking, "需要先修复的硬阻塞"],
    ["状态阻塞", stateBlocked, "状态机判断还没走完"],
    ["待办任务", pending, "需要平台 Agent 处理的 sidecar"],
    ["缺失产物", missing, "预期文件还没写齐"],
    ["下一步", summary.next_action_count ?? actions.length, "面板建议的行动数"],
  ];
  $("#dashboardSummary").innerHTML = metrics.map(([label, value, note]) => `
    <article class="metric ${Number(value) ? "attention" : ""}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(note)}</small>
    </article>
  `).join("");

  $("#dashboardRoutes").classList.toggle("empty", !routes.length);
  $("#dashboardRoutes").innerHTML = routes.length ? routes.map(renderRouteCard).join("") : "暂无流程数据";

  $("#dashboardNextActions").classList.toggle("empty", !actions.length);
  $("#dashboardNextActions").innerHTML = actions.length ? renderActionQueue(actions) : "目前没有新的下一步建议。";

  const events = result.recent_events || [];
  $("#dashboardEvents").classList.toggle("empty", !events.length);
  $("#dashboardEvents").innerHTML = events.length ? events.slice(-10).reverse().map(renderEvent).join("") : "暂无事件记录。";

  renderDashboardProse(library);
  renderDashboardActivity(activity);
  renderDashboardEvidence(result, { dashboard, summary, actions, routes, events });
}

function renderDashboardProse(library) {
  const target = $("#dashboardProse");
  if (!target) return;
  if (!library) {
    target.className = "completed-prose empty";
    target.innerHTML = "正在等待作品档案数据。";
    return;
  }
  if (library.ok === false) {
    target.className = "completed-prose empty";
    target.innerHTML = `作品正文暂时没有读到：${escapeHtml(library.error || "未知错误")}`;
    return;
  }
  const completed = library.completed_prose || {};
  const items = Array.isArray(completed.items) ? completed.items : [];
  if (!items.length) {
    target.className = "completed-prose empty";
    target.innerHTML = `
      <article class="completed-empty">
        <img src="${iconPath("manuscript-page")}" alt="" />
        <b>还没有已完成正文</b>
        <p>等候选稿通过正式审查并晋升，或章节导出/发布后，这里会自动出现正文预览。</p>
      </article>
    `;
    return;
  }
  const primary = items[0];
  const others = items.slice(1, 4);
  const metrics = primary.metrics || {};
  target.className = "completed-prose";
  target.innerHTML = `
    <article class="completed-main">
      <div class="completed-cover">
        <img class="completed-cover-icon" src="${iconPath("manuscript-page")}" alt="" />
        <span>正文</span>
        <b>${escapeHtml(metrics.chinese_content_chars || 0)}</b>
        <small>中文内容字数</small>
      </div>
      <div class="completed-reader">
        <div class="completed-kicker">${escapeHtml(primary.subtitle || "已完成正文")}</div>
        <h3>${escapeHtml(primary.title || "未命名正文")}</h3>
        <div class="completed-meta">
          ${renderBadges(primary.badges || [])}
          <span>${escapeHtml(shortPath(primary.path || ""))}</span>
        </div>
        <div class="completed-preview">${renderBodyPreview(primary.body || primary.excerpt || "")}</div>
        <button type="button" class="open-library-drafts">查看全部正文</button>
      </div>
    </article>
    ${others.length ? `
      <div class="completed-strip">
        ${others.map((item) => `
          <button type="button" class="completed-mini" data-prose-id="${escapeHtml(item.id)}">
            <span>${escapeHtml(item.subtitle || "正文")}</span>
            <b>${escapeHtml(item.title || item.id)}</b>
            <small>${escapeHtml((item.metrics || {}).chinese_content_chars || 0)} 字</small>
          </button>
        `).join("")}
      </div>
    ` : ""}
  `;
}

async function loadActivitySnapshot(root) {
  const result = await api(`/workflow/activity?project_root=${encodeURIComponent(root)}&limit=32`);
  const taskId = result.active_task?.task_id || "";
  if (taskId) {
    result.task_package = await api(`/workflow/task-package?project_root=${encodeURIComponent(root)}&task_id=${encodeURIComponent(taskId)}`).catch(() => null);
  }
  return result;
}

async function loadActivity() {
  const form = $("#activityForm");
  const root = form.project_root.value || $("#dashboardForm").project_root.value || $("#styleForm")?.project_root.value;
  if (!root) throw new Error("请先填写当前项目目录。");
  setSharedProjectRoot(root);
  $("#activityStatus").textContent = "正在刷新推进";
  const result = await loadActivitySnapshot(root);
  activitySnapshot = result;
  renderActivity(result);
  $("#activityStatus").textContent = result.generated_at ? `已刷新 ${formatTime(result.generated_at)}` : "已刷新";
  return result;
}

function renderDashboardActivity(activity) {
  const target = $("#dashboardActivity");
  if (!target) return;
  if (!activity || activity.ok === false) {
    target.innerHTML = `
      <article class="task-beacon mini empty">
        <span>当前任务</span>
        <b>暂时没有读取到推进现场</b>
        <p>${escapeHtml(activity?.error || "刷新后会显示平台 Agent 当前最应处理的正式任务。")}</p>
      </article>
    `;
    return;
  }
  target.innerHTML = renderTaskBeacon(activity.active_task || {}, { mini: true });
}

function renderActivity(result) {
  const active = result.active_task || {};
  const lanes = Array.isArray(result.route_lanes) ? result.route_lanes : [];
  const timeline = Array.isArray(result.timeline) ? result.timeline : [];
  activityChoices = Array.isArray(result.waiting_choices) ? result.waiting_choices : [];

  $("#activityBeacon").innerHTML = renderTaskBeacon(active);
  $("#activityLanes").classList.toggle("empty", !lanes.length);
  $("#activityLanes").innerHTML = lanes.length ? lanes.map(renderRouteLane).join("") : "暂无路线活动。";
  $("#activityTimeline").classList.toggle("empty", !timeline.length);
  $("#activityTimeline").innerHTML = timeline.length ? timeline.slice().reverse().map(renderTimelineEvent).join("") : "暂无推进记录。";
  renderActivityPackage(result.task_package, active);
  renderActivityChoices(activityChoices);
}

function renderTaskBeacon(active, options = {}) {
  const stage = active.stage || "ready";
  const steps = Array.isArray(active.progress_steps) ? active.progress_steps : [];
  const sourceCount = Array.isArray(active.source_paths) ? active.source_paths.length : 0;
  const outputCount = Array.isArray(active.expected_outputs) ? active.expected_outputs.length : 0;
  const elapsed = Number(active.elapsed_seconds || 0);
  const elapsedText = elapsed ? humanDuration(elapsed) : "刚刚";
  return `
    <article class="task-beacon ${escapeHtml(stageClass(stage, active.risk))} ${options.mini ? "mini" : ""}">
      <div class="beacon-head">
        <span>${escapeHtml(active.stage_label || "当前任务")}</span>
        <small>${escapeHtml(active.route_label || routeName(active.route))}</small>
      </div>
      <b>${escapeHtml(friendlyHeadline(active.headline || "项目等待下一轮创作方向"))}</b>
      <p>${escapeHtml(friendlyMessage(active.suggested_action || "按正式状态机继续推进。"))}</p>
      <div class="beacon-meta">
        <span>${escapeHtml(active.target ? friendlyTarget(active.target) : "项目整体")}</span>
        <span>${escapeHtml(active.current_step ? friendlyStep(active.current_step) : "ready")}</span>
        <span>${escapeHtml(elapsedText)}</span>
        <span>${sourceCount} 份资料 / ${outputCount} 个产物</span>
      </div>
      ${steps.length ? `
        <div class="beacon-steps" aria-label="任务阶段">
          ${steps.map((step) => `<span class="${escapeHtml(step.state || "todo")}">${escapeHtml(step.label || step.key)}</span>`).join("")}
        </div>
      ` : ""}
    </article>
  `;
}

function renderRouteLane(lane) {
  return `
    <article class="route-lane ${escapeHtml(lane.status || "ready")} ${lane.active ? "active" : ""}">
      <div class="lane-label">
        <b>${escapeHtml(lane.label || routeName(lane.route))}</b>
        <span>${escapeHtml(laneStatusLabel(lane.status))}</span>
      </div>
      <div class="lane-track"><i style="--lane-fill:${laneFill(lane)}%"></i></div>
      <p>${escapeHtml(friendlyMessage(lane.message || ""))}</p>
      <footer>
        <span>阻塞 ${escapeHtml(lane.blocking_count || 0)}</span>
        <span>待办 ${escapeHtml(lane.pending_task_count || 0)}</span>
        <span>选择 ${escapeHtml(lane.waiting_choice_count || 0)}</span>
      </footer>
    </article>
  `;
}

function renderTimelineEvent(event) {
  return `
    <article class="timeline-event ${escapeHtml(event.event_type || "")}">
      <time>${escapeHtml(formatTime(event.created_at || ""))}</time>
      <div>
        <b>${escapeHtml(event.label || eventLabel(event.event_type))}</b>
        <p>${escapeHtml(friendlyMessage(event.summary || ""))}</p>
        <footer>
          <span>${escapeHtml(routeName(event.route))}</span>
          ${event.target ? `<span>${escapeHtml(friendlyTarget(event.target))}</span>` : ""}
          ${event.task_id ? `<span>${escapeHtml(shortTaskId(event.task_id))}</span>` : ""}
        </footer>
      </div>
    </article>
  `;
}

function renderActivityPackage(pkg, active) {
  const target = $("#activityPackage");
  if (!target) return;
  if (!pkg || !pkg.sections) {
    const outputs = Array.isArray(active.expected_outputs) ? active.expected_outputs : [];
    const sources = Array.isArray(active.source_paths) ? active.source_paths : [];
    target.classList.toggle("empty", !active.task_id);
    target.innerHTML = active.task_id ? `
      <article class="package-summary">
        <h3>${escapeHtml(active.task_id)}</h3>
        <p>${escapeHtml(friendlyMessage(active.suggested_action || "按任务包执行。"))}</p>
        ${renderPackageList("需要看的资料", sources)}
        ${renderPackageList("要交付的东西", outputs)}
      </article>
    ` : "还没有活跃任务包。领取并打开任务后，这里会显示必读资料、预期产物和禁止捷径。";
    return;
  }
  const sections = pkg.sections || {};
  target.classList.remove("empty");
  target.innerHTML = `
    <article class="package-summary">
      <span>${escapeHtml(pkg.task?.route_label || routeName(pkg.task?.route))}</span>
      <h3>${escapeHtml(friendlyHeadline(pkg.task?.headline || pkg.task_id || "任务包"))}</h3>
      <p>${escapeHtml(friendlyHeadline(friendlyMessage(sections.purpose || "这是当前正式任务的执行包。")))}</p>
      <div class="package-grid">
        ${renderPackageList("需要看的资料", sections.required_reading)}
        ${renderPackageList("来源文件", sections.source_paths)}
        ${renderPackageList("要交付的东西", sections.expected_outputs)}
        ${renderPackageList("禁止捷径", sections.forbidden_shortcuts)}
      </div>
      <details class="raw-drawer">
        <summary>查看执行命令证据</summary>
        <div class="command-stack">
          ${sections.command ? `<code>${escapeHtml(sections.command)}</code>` : ""}
          ${sections.submission_command ? `<code>${escapeHtml(sections.submission_command)}</code>` : ""}
          ${sections.completion_command ? `<code>${escapeHtml(sections.completion_command)}</code>` : ""}
        </div>
      </details>
    </article>
  `;
}

function renderPackageList(title, items = []) {
  const values = (Array.isArray(items) ? items : []).filter(Boolean).slice(0, 8);
  return `
    <section class="package-list">
      <b>${escapeHtml(title)}</b>
      ${values.length ? `<ul>${values.map((item) => `<li>${escapeHtml(friendlyPackageItem(title, item))}</li>`).join("")}</ul>` : "<p>暂无。</p>"}
    </section>
  `;
}

function renderActivityChoices(choices) {
  const target = $("#activityChoices");
  if (!target) return;
  target.classList.toggle("empty", !choices.length);
  if (!choices.length) {
    target.innerHTML = "暂无等待用户选择的节点。正式流程需要你决定时，这里会出现分支卡、审批卡或扩纲方向卡。";
    return;
  }
  target.innerHTML = choices.slice(0, 4).map((choice, index) => `
    <article class="choice-card" data-choice-index="${index}">
      <span>${escapeHtml(routeName(choice.route))}</span>
      <h3>${escapeHtml(choice.title || "等待选择")}</h3>
      <p>${escapeHtml(choice.summary || choice.next_action || "请选择一个方向。")}</p>
      <div class="choice-options">
        ${(choice.options || []).map((option) => `
          <button type="button" class="activity-choice-option" data-selected="${escapeHtml(option.id)}">
            <b>${escapeHtml(option.label || option.id)}</b>
            <small>${escapeHtml(option.summary || "")}</small>
          </button>
        `).join("")}
      </div>
      <textarea class="choice-rationale" rows="3" placeholder="可选：写下你为什么这样选，平台 Agent 后续会读取这条理由。"></textarea>
    </article>
  `).join("");
}

function renderDashboardEvidence(result, { dashboard, summary, actions, routes, events }) {
  const routeState = dashboard.route_state?.summary || {};
  const taskStatus = dashboard.agent_task_status?.summary || {};
  const paths = result.paths || {};
  const frontend = dashboard.frontend || {};
  const rules = Array.isArray(result.rules) ? result.rules : Array.isArray(dashboard.rules) ? dashboard.rules : [];
  const blockedRoutes = routes.filter((route) => Number(route.blocking_count || 0) > 0);
  const warningRoutes = routes.filter((route) => Number(route.warning_count || 0) > 0);
  const pendingTasks =
    Number(taskStatus.pending_count || 0) +
    Number(taskStatus.partial_count || 0) +
    Number(taskStatus.unknown_count || 0);

  const routeSummary = blockedRoutes.length
    ? blockedRoutes.slice(0, 3).map((route) => `${routeName(route.route)}：${route.blocking_count} 个硬阻塞`).join("；")
    : warningRoutes.length
      ? warningRoutes.slice(0, 3).map((route) => `${routeName(route.route)}：${route.warning_count} 个提醒`).join("；")
      : "全部路线暂未发现硬阻塞。";

  const outputItems = [
    ["人读总控报告", paths.markdown],
    ["机器索引", paths.json || frontend.json],
    ["网页快照", paths.html || frontend.html],
    ["状态机摘要", dashboard.route_state?.path],
    ["平台任务摘要", dashboard.agent_task_status?.path],
  ].filter(([, value]) => value);
  const versionStale = serverHealth?.version && serverHealth.version !== UI_VERSION;

  $("#dashboardEvidence").innerHTML = [
    evidenceCard(
      "版本一致性",
      versionStale ? "服务进程可能偏旧" : "前端与服务版本正常",
      evidenceText(versionStale ? `当前页面是 ${UI_VERSION}，本地服务报告 ${serverHealth.version}。建议重启服务后再判断接口问题。` : `当前页面版本 ${UI_VERSION}；服务版本 ${serverHealth?.version || "未知"}。`),
      versionStale ? ["建议重启", "防误判"] : ["已连接"]
    ),
    evidenceCard(
      "状态机读数",
      `${Number(routeState.ready_count || summary.ready_count || 0)} 条路线就绪`,
      evidenceText(`状态机另发现 ${Number(routeState.blocked_count || summary.state_blocked_count || 0)} 处阻塞，下一步动作 ${actions.length} 条。`),
      ["来自 workflow-state", formatTime(dashboard.generated_at || "")]
    ),
    evidenceCard(
      "平台任务读数",
      pendingTasks ? `${pendingTasks} 个任务待处理` : "平台任务已清爽",
      evidenceText(`共扫描 ${Number(taskStatus.task_count || summary.sidecar_task_count || 0)} 个 sidecar；缺失预期产物 ${Number(taskStatus.missing_expected_count || summary.missing_expected_count || 0)} 个。`),
      ["来自 agent-task-status"]
    ),
    evidenceCard(
      "路线审计读数",
      `${Number(summary.blocking_count || 0)} 个硬门禁`,
      evidenceText(routeSummary),
      [`覆盖 ${routes.length} 条正式路线`]
    ),
    evidenceCard(
      "输出与索引",
      "报告、网页和机器索引都保留",
      evidenceList(outputItems.map(([label, value]) => `${label}：${shortPath(value)}`)),
      ["可追溯", "证据卡展示"]
    ),
    evidenceCard(
      "使用边界",
      "这里只读，不替代执行",
      evidenceList(rules.length ? rules.map(friendlyRule).slice(0, 3) : ["正式推进仍由平台 Agent 通过 CLI 状态机完成。"]),
      ["防跳步", "防误操作"]
    ),
    evidenceCard(
      "最近活动",
      events.length ? `${events.length} 条事件已纳入观察` : "还没有事件记录",
      evidenceText(events.length ? "事件已整理在左侧“最近推进记录”，用于判断平台 Agent 是否真的完成了提交与验收。" : "项目还没有可展示的 task event；开始正式路线后这里会自动出现。"),
      ["来自 task events"]
    ),
  ].join("");
}

function evidenceCard(title, value, detailHtml, tags = []) {
  return `
    <article class="evidence-card">
      <span class="evidence-title">${escapeHtml(title)}</span>
      <strong>${escapeHtml(value)}</strong>
      <div class="evidence-detail">${detailHtml}</div>
      <footer>${tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join("")}</footer>
    </article>
  `;
}

function evidenceText(value) {
  return `<p>${escapeHtml(value)}</p>`;
}

function evidenceList(items) {
  return `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function dashboardNarrative({ blocking, stateBlocked, pending, missing, actions }) {
  if (pending) return `还有 ${pending} 个平台 Agent 任务没有处理完。先打开“下一步建议”，按顺序完成任务，再刷新这里。`;
  if (blocking) return `有 ${blocking} 个正式门禁没有通过。它们通常涉及审查、文风、字数预算、角色资产或导出准备。`;
  if (stateBlocked) return `状态机发现 ${stateBlocked} 处流程还没走完。建议从第一条下一步建议开始补齐。`;
  if (missing) return `有 ${missing} 个预期产物缺失。先生成缺失的报告、候选稿、审查或发布文件。`;
  if (actions.length) return "项目没有明显硬阻塞，但仍有一些建议动作可以提升完整度。";
  return "当前没有阻塞信号。可以继续写作、审查下一章，或准备导出发布。";
}

function renderRouteCard(route) {
  const blocking = Number(route.blocking_count || 0);
  const warnings = Number(route.warning_count || 0);
  const pending = Number(route.pending_task_count || 0);
  const status = blocking ? "需处理" : warnings || pending ? "需留意" : "正常";
  const top = Array.isArray(route.top_blocking_gates) ? route.top_blocking_gates[0] : null;
  return `
    <article class="route-card ${blocking ? "blocked" : warnings || pending ? "warn" : "pass"}">
      <div>
        <b>${escapeHtml(routeName(route.route))}</b>
        <span>${escapeHtml(status)}</span>
      </div>
      <p>${escapeHtml(top ? friendlyMessage(top.message) : routeReadyText(route.route))}</p>
      <footer>
        <span>阻塞 ${blocking}</span>
        <span>提醒 ${warnings}</span>
        <span>待办 ${pending}</span>
      </footer>
    </article>
  `;
}

function renderActionQueue(actions) {
  const visible = actions.slice(0, 12);
  const groups = groupActions(visible);
  const lead = visible[0] || {};
  return `
    <article class="action-lead">
      <span>现在先看这里</span>
      <b>${escapeHtml(actionCategory(lead).label)}</b>
      <p>${escapeHtml(friendlyMessage(lead.next_action || "按正式状态机继续领取下一项任务。"))}</p>
      <small>${escapeHtml(routeName(lead.route))} · ${escapeHtml(lead.target ? friendlyTarget(lead.target) : "项目整体")}</small>
    </article>
    <div class="action-clusters">
      ${groups.map((group) => `
        <article class="action-cluster ${escapeHtml(group.key)}">
          <b>${escapeHtml(group.label)}</b>
          <span>${group.items.length} 项</span>
          <p>${escapeHtml(group.hint)}</p>
        </article>
      `).join("")}
    </div>
    ${visible.slice(0, 8).map(renderActionCard).join("")}
  `;
}

function groupActions(actions) {
  const byKey = new Map();
  actions.forEach((action) => {
    const category = actionCategory(action);
    const existing = byKey.get(category.key) || { ...category, items: [] };
    existing.items.push(action);
    byKey.set(category.key, existing);
  });
  return Array.from(byKey.values()).sort((a, b) => actionPriority(a.key) - actionPriority(b.key));
}

function actionCategory(action) {
  const text = `${action.route || ""} ${action.target || ""} ${action.next_action || ""}`.toLowerCase();
  if (text.includes("review") || text.includes("审查") || text.includes("audit")) {
    return { key: "review", label: "先补审查证据", hint: "这类问题会挡住晋升、导出和发布。" };
  }
  if (text.includes("style") || text.includes("文风")) {
    return { key: "style", label: "先确认文风", hint: "文风不稳，后面的正文会越写越偏。" };
  }
  if (text.includes("word") || text.includes("budget") || text.includes("字数")) {
    return { key: "budget", label: "先核对字数预算", hint: "长篇规模必须先有场景库存支撑。" };
  }
  if (text.includes("canon") || text.includes("世界") || text.includes("writeback")) {
    return { key: "canon", label: "先处理世界观写回", hint: "耐久设定不能只留在草稿里。" };
  }
  if (text.includes("agent") || text.includes("sidecar") || text.includes("任务")) {
    return { key: "task", label: "先完成平台任务", hint: "未处理的任务包会让正式路线停住。" };
  }
  return { key: "flow", label: "先补流程产物", hint: "按任务包补齐缺失文件，再刷新总控。" };
}

function actionPriority(key) {
  return { task: 0, review: 1, canon: 2, style: 3, budget: 4, flow: 5 }[key] ?? 9;
}

function renderActionCard(action, index) {
  return `
    <article class="action-item">
      <div class="action-index">${String(index + 1).padStart(2, "0")}</div>
      <div>
        <b>${escapeHtml(routeName(action.route))}</b>
        <span>${escapeHtml(action.target ? friendlyTarget(action.target) : "项目整体")}</span>
        <p>${escapeHtml(friendlyMessage(action.next_action || ""))}</p>
      </div>
    </article>
  `;
}

function renderEvent(event) {
  return `
    <article class="event-item">
      <b>${escapeHtml(eventLabel(event.event_type || event.type || "event"))}</b>
      <span>${escapeHtml(formatTime(event.created_at || event.timestamp || ""))}</span>
      <p>${escapeHtml(friendlyTarget(event.task_id || event.route || "项目事件"))}</p>
    </article>
  `;
}

async function loadLibrary() {
  const form = $("#libraryForm");
  const root = form.project_root.value || $("#dashboardForm").project_root.value || $("#styleForm")?.project_root.value;
  if (!root) throw new Error("请先填写当前项目目录。");
  setSharedProjectRoot(root);
  $("#libraryStatus").textContent = "正在整理作品档案";
  const result = await api(`/project/library?project_root=${encodeURIComponent(root)}`);
  librarySnapshot = result;
  activeLibraryKind = form.section.value || activeLibraryKind;
  renderLibrary(result);
  await loadChoices(root);
  $("#libraryStatus").textContent = result.generated_at ? `已整理 ${formatTime(result.generated_at)}` : "已整理";
  return result;
}

function renderLibrary(result) {
  const project = result.project || {};
  const counts = result.counts || {};
  const sections = result.sections || {};
  const projectBadges = Array.isArray(project.badges) ? project.badges.filter(Boolean) : [];
  $("#librarySummary").innerHTML = `
    <article class="library-cover">
      <div class="cover-stamp"><img src="${iconPath("archive-folder")}" alt="" /></div>
      <div>
        <span class="eyebrow light">当前项目</span>
        <h3>${escapeHtml(project.title || "未命名作品")}</h3>
        <p>${escapeHtml(project.excerpt || "还没有项目简介。")}</p>
        <footer>${projectBadges.map((badge) => `<span>${escapeHtml(badge)}</span>`).join("")}</footer>
      </div>
    </article>
    <article class="library-stat"><img src="${sectionIcon("drafts")}" alt="" /><b>${escapeHtml(counts.drafts || 0)}</b><span>正文与候选</span></article>
    <article class="library-stat"><img src="${sectionIcon("characters")}" alt="" /><b>${escapeHtml(counts.characters || 0)}</b><span>人物档案</span></article>
    <article class="library-stat"><img src="${sectionIcon("scenes")}" alt="" /><b>${escapeHtml(counts.scenes || 0)}</b><span>场景设定</span></article>
    <article class="library-stat"><img src="${sectionIcon("branches")}" alt="" /><b>${escapeHtml(counts.branches || 0)}</b><span>分支推演</span></article>
  `;

  $("#libraryTabs").innerHTML = Object.entries(sectionNames).map(([key, label]) => {
    const count = counts[key] || 0;
    return `<button type="button" data-kind="${key}" class="${key === activeLibraryKind ? "active" : ""}">${escapeHtml(label)}<span>${escapeHtml(count)}</span></button>`;
  }).join("");
  const rawItems = Array.isArray(sections[activeLibraryKind]) ? sections[activeLibraryKind] : [];
  const items = filterLibraryItems(rawItems);
  renderLibraryList(items, rawItems.length);
  if (items.length) selectLibraryItem(items[0], { keepList: true });
  else renderLibraryEmpty();
}

function renderLibraryList(items, total = items.length) {
  visibleLibraryItems = items;
  $("#libraryList").classList.toggle("empty", !items.length);
  $("#libraryList").innerHTML = items.length ? `
    <div class="library-result-bar">
      <span>显示 ${items.length} / ${total}</span>
      <small>${escapeHtml(libraryFilterSummary())}</small>
    </div>
    ${items.map((item, index) => `
    <button type="button" class="library-item ${selectedLibraryItem?.id === item.id ? "active" : ""}" data-index="${index}">
      <span>${escapeHtml(item.subtitle || sectionNames[item.kind] || "档案")}</span>
      <b>${escapeHtml(item.title || item.id)}</b>
      <p>${escapeHtml(item.excerpt || "暂无摘要。")}</p>
      <footer>${renderBadges(item.badges)}</footer>
    </button>
  `).join("")}` : "这个分类下没有匹配内容。可以清空搜索或切换状态筛选。";
}

function filterLibraryItems(items) {
  const form = $("#libraryForm");
  const query = String(form?.query?.value || "").trim().toLowerCase();
  const status = String(form?.status_filter?.value || "all");
  const dedupe = form?.dedupe ? form.dedupe.checked : true;
  let result = Array.isArray(items) ? items.slice() : [];
  if (status !== "all") {
    result = result.filter((item) => statusMatches(item, status));
  }
  if (query) {
    result = result.filter((item) => librarySearchText(item).includes(query));
  }
  if (dedupe) {
    result = dedupeLibraryItems(result);
  }
  return result;
}

function statusMatches(item, status) {
  const value = String(item?.status || "").toLowerCase();
  const subtitle = String(item?.subtitle || "").toLowerCase();
  const badges = (item?.badges || []).join(" ").toLowerCase();
  if (status === "promoted") return ["promoted", "chapter", "exported", "published"].includes(value) || subtitle.includes("已晋升") || subtitle.includes("正式");
  if (status === "candidate") return value.includes("candidate") || subtitle.includes("候选") || badges.includes("候选");
  if (status === "waiting_user_choice") return value.includes("waiting") || value.includes("approval") || badges.includes("等待");
  if (status === "needs_review") return value.includes("review") || value.includes("needs") || value.includes("unknown") || badges.includes("审查");
  if (status === "formal") return value === "formal" || subtitle.includes("正式") || badges.includes("正式");
  if (status === "ready") return ["ready", "pass", "selected", "major"].includes(value) || badges.includes("可使用");
  return true;
}

function librarySearchText(item) {
  const parts = [
    item?.id,
    item?.title,
    item?.subtitle,
    item?.status,
    item?.excerpt,
    item?.path,
    ...(item?.badges || []),
    ...(item?.key_points || []),
    ...(item?.facts || []).flatMap((fact) => [fact.label, fact.value]),
    ...(item?.options || []).flatMap((option) => [option.label, option.summary, option.risk]),
  ];
  return parts.filter((part) => part !== undefined && part !== null).join(" ").toLowerCase();
}

function dedupeLibraryItems(items) {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    const title = String(item?.title || "").replace(/\s+/g, "");
    const excerpt = String(item?.excerpt || "").replace(/\s+/g, "").slice(0, 80);
    const key = `${item?.kind || activeLibraryKind}:${title}:${excerpt}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

function libraryFilterSummary() {
  const form = $("#libraryForm");
  const pieces = [];
  if (form?.query?.value) pieces.push(`搜索“${form.query.value}”`);
  if (form?.status_filter?.value && form.status_filter.value !== "all") pieces.push(form.status_filter.selectedOptions[0]?.textContent || "状态筛选");
  if (form?.dedupe?.checked) pieces.push("已合并相似条目");
  return pieces.join(" / ") || "未启用筛选";
}

function renderLibraryEmpty() {
  selectedLibraryItem = null;
  visibleLibraryItems = [];
  $("#libraryDetail").className = "library-detail empty";
  $("#libraryDetail").innerHTML = `
    <article class="detail-empty">
      <img src="${sectionIcon(activeLibraryKind)}" alt="" />
      <b>这个分类暂时没有内容</b>
      <p>刷新项目或切换其他档案分类后，可以在这里查看正文、设定、推演和审查摘要。</p>
    </article>
  `;
}

function selectLibraryItem(item, selectOptions = {}) {
  selectedLibraryItem = item;
  if (!selectOptions.keepList) {
    renderLibraryList(visibleLibraryItems.length ? visibleLibraryItems : filterLibraryItems(librarySnapshot?.sections?.[activeLibraryKind] || []));
  }
  const body = item.body ? renderBody(item.body) : `<p>${escapeHtml(item.excerpt || "暂无正文或详情。")}</p>`;
  const facts = Array.isArray(item.facts) ? item.facts : [];
  const metrics = item.metrics || {};
  const keyPoints = creativeKeyPoints(item);
  const branchOptions = Array.isArray(item.options) && item.options.length ? `
    <div class="branch-options">
      ${item.options.map((option) => `
        <article class="${option.selected ? "selected" : ""}">
          <b>${escapeHtml(option.label || option.id)}</b>
          <p>${escapeHtml(option.summary || "暂无说明。")}</p>
          ${option.risk ? `<small>${escapeHtml(option.risk)}</small>` : ""}
        </article>
      `).join("")}
    </div>
  ` : "";
  $("#libraryDetail").className = "library-detail";
  $("#libraryDetail").innerHTML = `
    <article class="detail-head">
      <img class="detail-icon" src="${sectionIcon(item.kind || activeLibraryKind)}" alt="" />
      <div>
        <span>${escapeHtml(item.subtitle || sectionNames[item.kind] || "档案")}</span>
        <h3>${escapeHtml(item.title || item.id)}</h3>
        <footer>${renderBadges(item.badges)}</footer>
      </div>
    </article>
    ${item.user_note ? `<aside class="user-note">你的备注：${escapeHtml(item.user_note)}</aside>` : ""}
    ${Object.keys(metrics).length ? renderMetricStrip(metrics) : ""}
    ${keyPoints.length ? `
      <section class="key-points">
        <div>
          <span>影响创作的关键点</span>
          <small>平台 Agent 后续写作和审查应优先读取这些点</small>
        </div>
        <ul>${keyPoints.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>
      </section>
    ` : ""}
    ${facts.length ? `<div class="fact-grid">${facts.map(renderFact).join("")}</div>` : ""}
    ${branchOptions}
    <div class="reader-body">${body}</div>
  `;
  const editForm = $("#editForm");
  editForm.target_type.value = item.kind || "";
  editForm.target_id.value = item.id || "";
  editForm.querySelector("[name=value]").value = "";
  $("#editStatus").textContent = `正在标注：${item.title || item.id}`;
}

function renderBadges(badges = []) {
  return (Array.isArray(badges) ? badges : []).filter(Boolean).slice(0, 5).map((badge) => `<span>${escapeHtml(badge)}</span>`).join("");
}

function renderFact(fact) {
  return `
    <article class="fact-card">
      <span>${escapeHtml(fact.label || "信息")}</span>
      <b>${escapeHtml(fact.value ?? "未填写")}</b>
    </article>
  `;
}

function creativeKeyPoints(item) {
  const points = Array.isArray(item.key_points) ? item.key_points.slice() : [];
  if (!points.length && Array.isArray(item.facts)) {
    points.push(...item.facts
      .filter((fact) => fact && fact.value && !["未填写", "未设置", "0"].includes(String(fact.value)))
      .slice(0, 4)
      .map((fact) => `${fact.label}：${fact.value}`));
  }
  if (!points.length && item.excerpt) points.push(item.excerpt);
  const seen = new Set();
  return points
    .map((point) => String(point || "").trim())
    .filter((point) => {
      if (!point || seen.has(point)) return false;
      seen.add(point);
      return true;
    })
    .slice(0, 5);
}

function renderMetricStrip(metrics) {
  const items = [
    ["中文内容字数", metrics.chinese_content_chars],
    ["机器字符", metrics.machine_nonspace_chars],
    ["目标字数", metrics.target_chinese_content_chars],
  ].filter(([, value]) => value !== undefined && value !== "");
  return `<div class="mini-metrics">${items.map(([label, value]) => `<span><b>${escapeHtml(value)}</b>${escapeHtml(label)}</span>`).join("")}</div>`;
}

function renderBody(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .filter((part) => part.trim())
    .slice(0, 30)
    .map((part) => `<p>${escapeHtml(part.trim()).replace(/\n/g, "<br />")}</p>`)
    .join("");
}

function renderBodyPreview(text) {
  return String(text || "")
    .split(/\n{2,}/)
    .filter((part) => part.trim())
    .slice(0, 5)
    .map((part) => `<p>${escapeHtml(part.trim()).replace(/\n/g, "<br />")}</p>`)
    .join("") || "<p>正文为空或只有工程说明。</p>";
}

async function loadChoices(root = "") {
  const projectRoot = root || sharedProjectRoot();
  if (!projectRoot) return;
  const result = await api(`/workflow/current-choice?project_root=${encodeURIComponent(projectRoot)}`);
  currentChoices = result.choices || [];
  renderChoices(currentChoices, result.recent_choices || []);
}

function renderChoices(choices, recent = []) {
  const list = $("#choiceList");
  const recentUnique = uniqueRecentChoices(recent);
  list.classList.toggle("empty", !choices.length && !recentUnique.length);
  if (!choices.length && !recentUnique.length) {
    list.innerHTML = "暂无等待用户选择的节点。正式流程需要你决定时，这里会出现分支卡、审批卡或扩纲方向卡。";
    return;
  }
  const choiceCards = choices.map((choice, index) => `
    <article class="choice-card" data-choice-index="${index}">
      <span>${escapeHtml(routeName(choice.route))}</span>
      <h3>${escapeHtml(choice.title || "等待选择")}</h3>
      <p>${escapeHtml(choice.summary || choice.next_action || "请选择一个方向。")}</p>
      ${choice.recommended ? `<div class="choice-recommended">建议关注：${escapeHtml(choice.recommended)}</div>` : ""}
      <div class="choice-options">
        ${(choice.options || []).map((option) => `
          <button type="button" class="choice-option" data-selected="${escapeHtml(option.id)}">
            <b>${escapeHtml(option.label || option.id)}</b>
            <small>${escapeHtml(option.summary || "")}</small>
          </button>
        `).join("")}
      </div>
      <textarea class="choice-rationale" rows="3" placeholder="可选：写下你为什么这样选，平台 Agent 后续会读取这条理由。"></textarea>
    </article>
  `).join("");
  const recentCards = recentUnique.length ? `
    <div class="recent-choice">
      <b>最近决定</b>
      ${recentUnique.slice(0, 4).map((item) => `
        <p>
          <strong>${escapeHtml(decisionTypeLabel(item.decision_type || "选择"))}</strong>
          <span>${escapeHtml(item.selected || item.decision || "已记录")}</span>
        </p>
      `).join("")}
    </div>
  ` : "";
  list.innerHTML = choiceCards + recentCards;
}

function uniqueRecentChoices(recent = []) {
  const seen = new Set();
  return (Array.isArray(recent) ? recent : [])
    .slice()
    .reverse()
    .filter((item) => {
      const key = `${item.decision_type || ""}:${JSON.stringify(item.target || {})}:${item.selected || item.decision || ""}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function decisionTypeLabel(value) {
  const labels = {
    branch_selection: "分支选择",
    style_mount: "文风挂载",
    asset_approval: "资产审批",
    release_approval: "发布审批",
    canon_patch_approval: "Canon 写回审批",
    word_budget_direction: "字数方向",
    revision_direction: "修订方向",
    state_patch_confirmation: "状态确认",
  };
  return labels[value] || friendlyMessage(value || "选择");
}

async function submitHumanChoice(choice, selected, rationale) {
  const result = await recordHumanChoice(choice, selected, rationale);
  $("#libraryStatus").textContent = result.materialized ? `已记录选择，并写入 ${shortPath(result.materialized)}` : "已记录选择。";
  await loadLibrary();
}

async function submitActivityChoice(choice, selected, rationale) {
  const result = await recordHumanChoice(choice, selected, rationale);
  $("#activityStatus").textContent = result.materialized ? `已记录选择，并写入 ${shortPath(result.materialized)}` : "已记录选择。";
  await loadActivity();
}

async function recordHumanChoice(choice, selected, rationale) {
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const payload = {
    project_root: root,
    choice_id: choice.choice_id,
    route: choice.route,
    task_id: choice.task_id || "",
    decision_type: choice.decision_type,
    target: choice.target || {},
    options: choice.options || [],
    selected,
    rationale,
    actor: "user-ui",
    materialize: true,
  };
  return api("/workflow/human-choice", { method: "POST", body: JSON.stringify(payload) });
}

async function saveDisplayField(event) {
  event.preventDefault();
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const data = formData($("#editForm"));
  const payload = {
    project_root: root,
    target_type: data.target_type,
    target_id: data.target_id,
    field: data.field,
    value: data.value,
    actor: "user-ui",
  };
  await api("/project/display-field", { method: "PATCH", body: JSON.stringify(payload) });
  $("#editStatus").textContent = "标注已保存。正式剧情改动仍需候选、审查和审批。";
  await loadLibrary();
}

async function saveUiNote(event) {
  event.preventDefault();
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const data = formData($("#editForm"));
  const payload = {
    project_root: root,
    target_type: data.target_type,
    target_id: data.target_id,
    note: data.value,
    actor: "user-ui",
  };
  await api("/project/ui-note", { method: "POST", body: JSON.stringify(payload) });
  $("#editStatus").textContent = "备注已追加。平台 Agent 可把它作为后续创作意图读取。";
  $("#editForm").querySelector("[name=value]").value = "";
  await loadLibrary();
}

function toggleLibraryPoll() {
  const button = $("#toggleLibraryPoll");
  if (libraryTimer || libraryStream) {
    stopLibraryObservation();
    button.textContent = "观察档案变化";
    $("#libraryStatus").textContent = "已停止观察";
    return;
  }
  startLibraryObservation();
}

function stopLibraryObservation() {
  if (libraryStream) {
    libraryStream.close();
    libraryStream = null;
  }
  if (libraryTimer) {
    clearInterval(libraryTimer);
    libraryTimer = null;
  }
}

function startLibraryObservation() {
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const button = $("#toggleLibraryPoll");
  stopLibraryObservation();
  if (window.EventSource) {
    const url = `/project/library/stream?project_root=${encodeURIComponent(root)}&interval_seconds=6`;
    libraryStream = new EventSource(url);
    libraryStream.addEventListener("library", (event) => {
      const result = JSON.parse(event.data);
      librarySnapshot = result;
      renderLibrary(result);
      loadChoices(root).catch(() => {});
      $("#libraryStatus").textContent = result.generated_at ? `实时更新 ${formatTime(result.generated_at)}` : "实时更新中";
    });
    libraryStream.onerror = () => {
      stopLibraryObservation();
      startLibraryPolling();
      $("#libraryStatus").textContent = "流式连接中断，已切换为安全轮询。";
    };
    button.textContent = "停止观察";
    $("#libraryStatus").textContent = "正在建立流式连接";
    return;
  }
  startLibraryPolling();
}

function startLibraryPolling() {
  const button = $("#toggleLibraryPoll");
  guarded(loadLibrary);
  libraryTimer = setInterval(() => guarded(loadLibrary), 6000);
  button.textContent = "停止观察";
}

async function loadStyleStatus() {
  const data = formData($("#styleForm"));
  const root = data.project_root || $("#dashboardForm").project_root.value;
  if (!root) throw new Error("请先填写当前项目目录。");
  setSharedProjectRoot(root);
  $("#styleStatusText").textContent = "正在检查";
  const result = await api(`/style-lab/mounts?project_root=${encodeURIComponent(root)}`);
  renderStyleStatus(result);
  await loadStyleLibrary(data.style_library_root || "");
}

function renderStyleStatus(result) {
  const active = result.active_style_skill || {};
  const ready = active.readiness?.ready;
  $("#styleStatusText").textContent = "已检查";
  if (!active.style_id) {
    $("#styleStatus").className = "style-status empty";
    $("#styleStatus").innerHTML = `
      <img class="style-empty-icon" src="${iconPath("style-card")}" alt="" />
      <b>还没有挂载文风</b>
      <p>正式长篇创作前，建议先完成文风学习并挂载 Style Skill。</p>
    `;
    return;
  }
  $("#styleStatus").className = `style-status ${ready ? "pass" : "warn"}`;
  $("#styleStatus").innerHTML = `
    <div class="style-name">${escapeHtml(active.style_id)}</div>
    <div class="key-state ${ready ? "pass" : "warn"}">${ready ? "可用于正式生成" : "还需要补齐评测或提示词质量"}</div>
    <p>文风会作为表达层最高优先级约束进入场景生成、修订和审查。</p>
  `;
}

async function loadStyleLibrary(styleRoot = "") {
  const query = styleRoot ? `?style_library_root=${encodeURIComponent(styleRoot)}` : "";
  const result = await api(`/style-lab/library${query}`);
  renderStyleLibrary(result.style_skills || {});
}

function renderStyleLibrary(styleSkills) {
  const items = styleSkills.items || [];
  const list = $("#styleLibrary");
  list.classList.toggle("empty", !items.length);
  if (!items.length) {
    list.innerHTML = "暂未发现可挂载文风。可以先通过文风学习流程生成 Style Skill。";
    return;
  }
  list.innerHTML = items.map((item) => `
    <article class="style-skill-card">
      <div>
        <span>${escapeHtml(item.author || item.author_id || "未知作家")}</span>
        <b>${escapeHtml(item.style_id)}</b>
        <p>${escapeHtml(item.mode || "文风技能")}</p>
      </div>
      <button type="button" class="mount-style" data-style-id="${escapeHtml(item.style_id)}">挂载</button>
    </article>
  `).join("");
}

async function mountStyle(styleId) {
  const data = formData($("#styleForm"));
  const root = data.project_root || sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const styleLibraryRoot = data.style_library_root || "";
  await api("/workflow/human-choice", {
    method: "POST",
    body: JSON.stringify({
      project_root: root,
      route: "style-engineering",
      decision_type: "style_mount",
      target: { style_id: styleId },
      selected: styleId,
      rationale: "用户在前端文风库中选择挂载此文风。",
      actor: "user-ui",
      materialize: false,
    }),
  });
  const mounted = await api("/style-lab/mount", {
    method: "POST",
    body: JSON.stringify({
      project_root: root,
      style_library_root: styleLibraryRoot,
      style_id: styleId,
      allow_unreviewed: false,
    }),
  });
  renderStyleStatus(mounted);
  $("#styleStatusText").textContent = `已挂载 ${styleId}`;
  if ($("#libraryForm").project_root.value) guarded(loadLibrary);
}

function toggleDashboardPoll() {
  const button = $("#toggleDashboardPoll");
  if (dashboardTimer || dashboardStream) {
    stopDashboardObservation();
    button.textContent = "观察项目变化";
    $("#dashboardStatus").textContent = "已停止观察";
    return;
  }
  startDashboardObservation();
}

function stopDashboardObservation() {
  if (dashboardStream) {
    dashboardStream.close();
    dashboardStream = null;
  }
  if (dashboardTimer) {
    clearInterval(dashboardTimer);
    dashboardTimer = null;
  }
}

function startDashboardObservation() {
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const button = $("#toggleDashboardPoll");
  const seconds = Math.max(3, Math.min(60, Number($("#dashboardForm").refresh_seconds.value) || 8));
  stopDashboardObservation();
  if (window.EventSource) {
    const url = `/workflow/dashboard/stream?project_root=${encodeURIComponent(root)}&interval_seconds=${seconds}`;
    dashboardStream = new EventSource(url);
    dashboardStream.addEventListener("dashboard", async (event) => {
      const result = JSON.parse(event.data);
      const [library, activity] = await Promise.all([
        api(`/project/library?project_root=${encodeURIComponent(root)}`).catch((error) => ({ ok: false, error: error.message || String(error) })),
        loadActivitySnapshot(root).catch((error) => ({ ok: false, error: error.message || String(error) })),
      ]);
      if (library.ok !== false) librarySnapshot = library;
      if (activity.ok !== false) activitySnapshot = activity;
      renderDashboard(result, library, activity);
      $("#dashboardStatus").textContent = result.dashboard?.generated_at ? `实时更新 ${formatTime(result.dashboard.generated_at)}` : "实时更新中";
    });
    dashboardStream.onerror = () => {
      stopDashboardObservation();
      startDashboardPolling(seconds);
      $("#dashboardStatus").textContent = "流式连接中断，已切换为安全轮询。";
    };
    button.textContent = "停止观察";
    $("#dashboardStatus").textContent = "正在建立流式连接";
    return;
  }
  startDashboardPolling(seconds);
}

function startDashboardPolling(seconds) {
  const button = $("#toggleDashboardPoll");
  guarded(loadDashboard);
  dashboardTimer = setInterval(() => guarded(loadDashboard), seconds * 1000);
  button.textContent = "停止观察";
}

function toggleActivityPoll() {
  const button = $("#toggleActivityPoll");
  if (activityTimer || activityStream) {
    stopActivityObservation();
    button.textContent = "观察推进";
    $("#activityStatus").textContent = "已停止观察";
    return;
  }
  startActivityObservation();
}

function stopActivityObservation() {
  if (activityStream) {
    activityStream.close();
    activityStream = null;
  }
  if (activityTimer) {
    clearInterval(activityTimer);
    activityTimer = null;
  }
}

function startActivityObservation() {
  const root = sharedProjectRoot();
  if (!root) throw new Error("请先填写当前项目目录。");
  const button = $("#toggleActivityPoll");
  stopActivityObservation();
  if (window.EventSource) {
    const url = `/workflow/activity/stream?project_root=${encodeURIComponent(root)}&interval_seconds=4`;
    activityStream = new EventSource(url);
    activityStream.addEventListener("activity", (event) => {
      const result = JSON.parse(event.data);
      activitySnapshot = result;
      renderActivity(result);
      const taskId = result.active_task?.task_id || "";
      if (taskId) {
        api(`/workflow/task-package?project_root=${encodeURIComponent(root)}&task_id=${encodeURIComponent(taskId)}`)
          .then((pkg) => {
            result.task_package = pkg;
            renderActivityPackage(pkg, result.active_task || {});
          })
          .catch(() => {});
      }
      $("#activityStatus").textContent = result.generated_at ? `实时更新 ${formatTime(result.generated_at)}` : "实时更新中";
    });
    activityStream.onerror = () => {
      stopActivityObservation();
      startActivityPolling();
      $("#activityStatus").textContent = "流式连接中断，已切换为安全轮询。";
    };
    button.textContent = "停止观察";
    $("#activityStatus").textContent = "正在建立流式连接";
    return;
  }
  startActivityPolling();
}

function startActivityPolling() {
  const button = $("#toggleActivityPoll");
  guarded(loadActivity);
  const seconds = Math.max(3, Math.min(60, Number($("#activityForm").refresh_seconds.value) || 4));
  activityTimer = setInterval(() => guarded(loadActivity), seconds * 1000);
  button.textContent = "停止观察";
}

function routeName(route) {
  return routeNames[route] || route || "项目流程";
}

function friendlyTarget(value) {
  return String(value)
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\bscene\b/gi, "场景")
    .replace(/\bchapter\b/gi, "章节")
    .replace(/\blongform\b/gi, "长篇规划")
    .trim();
}

function friendlyMessage(value) {
  let text = String(value || "需要继续处理。");
  text = text.replace(/\.agent_tasks\.md/g, "平台 Agent 任务");
  text = text.replace(/\.agent_completion\.json/g, "任务完成标记");
  text = text.replace(/\.json/g, "记录");
  text = text.replace(/\.md/g, "报告");
  text = text.replace(/_/g, " ");
  text = text.replace(/route-audit/gi, "路线审计");
  text = text.replace(/sidecar/gi, "平台任务");
  text = text.replace(/workflow/g, "工作流");
  text = text.replace(/candidate/g, "候选稿");
  text = text.replace(/promotion/g, "晋升");
  text = text.replace(/review/g, "审查");
  return text;
}

function friendlyHeadline(value) {
  let text = friendlyMessage(value);
  const replacements = [
    [/roleplay agent task/gi, "角色推演任务"],
    [/branch agent task/gi, "分支研判任务"],
    [/composition agent task/gi, "编剧态任务"],
    [/generation agent task/gi, "正文生成任务"],
    [/agent review task/gi, "正式审查任务"],
    [/state agent task/gi, "人物状态演化任务"],
    [/canon agent task/gi, "世界观写回任务"],
    [/budget agent task/gi, "字数预算细化任务"],
    [/scene inventory agent task/gi, "场景库存规划任务"],
    [/chapter obligation agent task/gi, "章节义务规划任务"],
    [/extraction agent task/gi, "旧文反推任务"],
    [/style prompt agent task/gi, "文风提示词生成任务"],
    [/asset creation agent task/gi, "资产创建任务"],
    [/asset review agent task/gi, "资产审查执行"],
    [/canon review agent task/gi, "Canon 审查执行"],
    [/committee agent task/gi, "多视角审查执行"],
  ];
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

function friendlyPackageItem(title, item) {
  const text = String(item || "");
  if (title === "禁止捷径") {
    if (/hand-write same-named formal files/i.test(text)) return "不要手写同名正式产物来绕过 CLI 命令。";
    if (/debug\/bypass flags/i.test(text)) return "不要使用调试或绕审参数，正式流程必须走完门禁。";
    if (/task-submit and task-complete/i.test(text)) return "写出产物不等于完成，必须先提交，再由 CLI 验收。";
    if (/subagents draft|subagents.*creative body text/i.test(text)) return "不要让 subagent 起草、修订、润色、扩写或定稿正文。";
    if (/API keys|provider secrets/i.test(text)) return "不要把 API Key 或模型密钥写进作品项目。";
    return friendlyHeadline(text);
  }
  if (title === "需要看的资料") return friendlyReference(text);
  return shortPath(text);
}

function friendlyReference(value) {
  const text = String(value || "");
  const labels = {
    "SKILL.md": "Skill 操作宪法",
    "AGENTS.md": "正式运行纪律",
    "agentread.yaml": "Agent 读取入口",
    "references/agent-run-protocol.md": "平台 Agent 执行规范",
    "references/cli-run-protocol.md": "CLI 状态机规范",
    "references/punctuation-standard.md": "中文标点与行文规范",
  };
  return labels[text] || shortPath(text);
}

function friendlyStep(value) {
  const text = String(value || "").replace(/[-_]/g, " ").trim();
  const labels = {
    "context packet": "上下文包",
    "context trace": "上下文来源核验",
    "roleplay simulation": "角色推演",
    "roleplay agent task": "角色推演任务",
    "branch manifest": "分支清单",
    "branch simulation": "分支推演",
    "branch agent task": "分支研判任务",
    "branch selection": "分支选择",
    composition: "编剧态",
    "composition json": "编剧态方案",
    "composition agent task": "编剧态任务",
    "scene word budget contract": "场景字数契约",
    "reader experience contract": "读者体验契约",
    "candidate generation provenance": "正文生成来源",
    "prose candidate": "正文候选",
    "generation agent task": "正文生成任务",
    "agent review": "正式审查",
    "agent review task": "正式审查任务",
    "candidate review": "正文审查",
    promotion: "正文晋升",
    "promotion manifest": "晋升清单",
    "promoted draft": "正式草稿",
    "static review": "静态审查",
    "state evolve": "状态演化",
    "state patch json": "状态补丁",
    "state agent task": "人物状态演化任务",
    "canon writeback": "Canon 写回",
    "canon patch json": "Canon 补丁",
    "canon agent task": "世界观写回任务",
    "route audit": "路线审计",
    "word budget file": "字数预算",
    "budget agent task": "字数预算细化任务",
    "budget review": "预算审查",
    "scene inventory agent task": "场景库存规划任务",
    "chapter obligation agent task": "章节义务规划任务",
    "source manifest": "来源清单",
    "extraction agent task": "旧文反推任务",
    "extraction review": "旧文反推审查",
    "style profile": "文风画像",
    "style prompt task file": "文风提示词任务",
    "style prompt agent task": "文风提示词生成任务",
    "style prompt quality": "文风质量审查",
    "style eval readiness": "文风评估准备",
    "asset intake": "资产接收",
    "asset creation agent task": "资产创建任务",
    "asset review task file": "资产审查任务",
    "asset review agent task": "资产审查执行",
    "asset review pass": "资产审查通过",
    "asset approval": "资产审批",
    "asset promotion": "资产晋升",
    "canon lint file": "Canon 本地检查",
    "canon review task file": "Canon 审查任务",
    "canon review agent task": "Canon 审查执行",
    "canon review pass": "Canon 审查通过",
    "longform audit file": "长篇全局审计",
    "committee task file": "多视角审查任务",
    "committee agent task": "多视角审查执行",
    "committee pass": "多视角审查通过",
    "chapter workspace": "章节汇编",
    "export package": "导出包",
    "release approval": "发布审批",
    "publish release": "发布",
  };
  return labels[text] || friendlyMessage(text);
}

function stageClass(stage, risk = "") {
  if (risk === "blocking" || stage === "blocked") return "blocked";
  if (stage === "waiting_user") return "waiting-user";
  if (stage === "waiting_gate") return "waiting-gate";
  if (stage === "completed" || stage === "ready") return "complete";
  if (risk === "stale") return "stale";
  return "active";
}

function laneStatusLabel(status) {
  const labels = {
    blocked: "卡住",
    waiting_user: "待你决定",
    pending: "进行中",
    warning: "需留意",
    ready: "正常",
  };
  return labels[status] || "观察中";
}

function laneFill(lane) {
  if (lane.status === "blocked") return 34;
  if (lane.status === "waiting_user") return 52;
  if (lane.status === "pending") return 64;
  if (lane.status === "warning") return 76;
  return 100;
}

function humanDuration(seconds) {
  const value = Number(seconds || 0);
  if (value < 60) return "刚刚";
  if (value < 3600) return `${Math.floor(value / 60)} 分钟前`;
  if (value < 86400) return `${Math.floor(value / 3600)} 小时前`;
  return `${Math.floor(value / 86400)} 天前`;
}

function shortTaskId(value) {
  const text = String(value || "");
  if (text.length <= 34) return text;
  return `${text.slice(0, 16)}...${text.slice(-14)}`;
}

function friendlyRule(value) {
  const text = String(value || "");
  if (text.includes("read-only")) return "总控面板只读，不能绕过任务领取、提交和完成确认。";
  if (text.includes("platform agent")) return "创作与审查判断仍由平台 Agent 执行，本页只聚合正式证据。";
  if (text.includes("blocking message")) return "出现阻塞时，阻塞说明就是下一条修复任务。";
  return friendlyMessage(text);
}

function routeReadyText(route) {
  const copy = {
    "scene-development": "场景开发证据完整，可以继续推进下一场。",
    "longform-planning": "长篇规划没有发现硬阻塞。",
    "source-ingest": "旧文导入链路暂时正常。",
    "style-engineering": "文风工程没有发现硬阻塞。",
    "character-and-world-assets": "人物与世界资产链路暂时正常。",
    "review-and-audit": "审查与审计链路暂时正常。",
    "export-and-release": "导出与发布链路暂时正常。",
  };
  return copy[route] || "这条流程暂时没有硬阻塞。";
}

function eventLabel(value) {
  const labels = {
    task_issued: "已派发任务",
    task_opened: "已打开任务",
    task_submitted: "已提交产物",
    task_completed: "已完成任务",
    task_blocked: "任务被拦截",
    workflow_state_refreshed: "状态已刷新",
    workflow_advanced: "工作流已推进",
    issued: "已派发任务",
    opened: "已打开任务",
    submitted: "已提交产物",
    completed: "已完成任务",
    invalid: "记录异常",
  };
  return labels[value] || "项目事件";
}

function shortPath(value) {
  const text = String(value || "");
  if (text.length <= 54) return text;
  return `...${text.slice(-51)}`;
}

function formatTime(value) {
  if (!value) return "未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function toast(message) {
  $("#dashboardStatus").textContent = message;
}

function activateView(view) {
  $$(".nav button").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  $$(".view").forEach((item) => item.classList.toggle("active", item.id === `view-${view}`));
}

async function openLibraryDrafts() {
  activeLibraryKind = "drafts";
  if ($("#libraryForm")) $("#libraryForm").section.value = "drafts";
  activateView("library");
  await loadLibrary();
}

function bind() {
  $$(".nav button").forEach((button) => {
    button.addEventListener("click", () => {
      activateView(button.dataset.view);
      if (button.dataset.view === "projects") guarded(loadProjects);
      if (button.dataset.view === "dashboard" && sharedProjectRoot()) {
        guarded(loadDashboard);
        guarded(loadDirections);
      }
      if (button.dataset.view === "activity" && sharedProjectRoot()) guarded(loadActivity);
      if (button.dataset.view === "library" && sharedProjectRoot()) guarded(loadLibrary);
      if (button.dataset.view === "style" && sharedProjectRoot()) guarded(loadStyleStatus);
    });
  });
  $("#switchProject").addEventListener("click", () => activateView("projects"));
  $("#refreshProjects").addEventListener("click", () => guarded(loadProjects));
  $("#createProjectForm").addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(createProjectFromClient);
  });
  $("#openProjectForm").addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(() => openProjectFromClient());
  });
  $("#recentProjects").addEventListener("click", (event) => {
    const button = event.target.closest(".open-recent-project");
    if (!button) return;
    const project = recentProjects[Number(button.dataset.projectIndex)];
    if (project) guarded(() => openProjectFromClient(project.path));
  });
  $("#directionForm").addEventListener("submit", (event) => {
    event.preventDefault();
    guarded(() => submitDirection(false));
  });
  $("#saveAndExecute").addEventListener("click", () => guarded(() => submitDirection(true)));
  $("#refreshDashboard").addEventListener("click", () => guarded(loadDashboard));
  $("#toggleDashboardPoll").addEventListener("click", () => toggleDashboardPoll());
  $("#refreshActivity").addEventListener("click", () => guarded(loadActivity));
  $("#toggleActivityPoll").addEventListener("click", () => guarded(toggleActivityPoll));
  $("#detectRuntimes").addEventListener("click", () => guarded(loadRuntimes));
  $("#prepareWorkerTask").addEventListener("click", () => guarded(prepareWorkerTask));
  $("#runWorkerTask").addEventListener("click", () => guarded(runWorkerTask));
  $("#dashboardProse").addEventListener("click", (event) => {
    if (event.target.closest(".open-library-drafts") || event.target.closest(".completed-mini")) {
      guarded(openLibraryDrafts);
    }
  });
  $("#refreshLibrary").addEventListener("click", () => guarded(loadLibrary));
  $("#toggleLibraryPoll").addEventListener("click", () => guarded(toggleLibraryPoll));
  $("#libraryForm").section.addEventListener("change", (event) => {
    activeLibraryKind = event.target.value;
    if (librarySnapshot) renderLibrary(librarySnapshot);
  });
  $("#libraryForm").query.addEventListener("input", () => {
    if (librarySnapshot) renderLibrary(librarySnapshot);
  });
  $("#libraryForm").status_filter.addEventListener("change", () => {
    if (librarySnapshot) renderLibrary(librarySnapshot);
  });
  $("#libraryForm").dedupe.addEventListener("change", () => {
    if (librarySnapshot) renderLibrary(librarySnapshot);
  });
  $("#libraryTabs").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-kind]");
    if (!button) return;
    activeLibraryKind = button.dataset.kind;
    $("#libraryForm").section.value = activeLibraryKind;
    if (librarySnapshot) renderLibrary(librarySnapshot);
  });
  $("#libraryList").addEventListener("click", (event) => {
    const button = event.target.closest(".library-item");
    if (!button || !librarySnapshot) return;
    const items = visibleLibraryItems;
    const item = items[Number(button.dataset.index)];
    if (item) selectLibraryItem(item);
  });
  $("#choiceList").addEventListener("click", (event) => {
    const button = event.target.closest(".choice-option");
    if (!button) return;
    const card = button.closest(".choice-card");
    const choice = currentChoices[Number(card.dataset.choiceIndex)];
    if (!choice) return;
    const rationale = card.querySelector(".choice-rationale")?.value || "";
    guarded(() => submitHumanChoice(choice, button.dataset.selected, rationale));
  });
  $("#activityChoices").addEventListener("click", (event) => {
    const button = event.target.closest(".activity-choice-option");
    if (!button) return;
    const card = button.closest(".choice-card");
    const choice = activityChoices[Number(card.dataset.choiceIndex)];
    if (!choice) return;
    const rationale = card.querySelector(".choice-rationale")?.value || "";
    guarded(() => submitActivityChoice(choice, button.dataset.selected, rationale));
  });
  $("#saveDisplayField").addEventListener("click", (event) => guarded(() => saveDisplayField(event)));
  $("#saveUiNote").addEventListener("click", (event) => guarded(() => saveUiNote(event)));
  $("#loadStyleStatus").addEventListener("click", () => guarded(loadStyleStatus));
  $("#styleLibrary").addEventListener("click", (event) => {
    const button = event.target.closest(".mount-style");
    if (!button) return;
    guarded(() => mountStyle(button.dataset.styleId));
  });
}

async function guarded(fn) {
  try {
    await fn();
  } catch (error) {
    $("#dashboardStatus").textContent = error.message || String(error);
    if ($("#projectFeedback")) $("#projectFeedback").textContent = error.message || String(error);
  }
}

bind();
loadHealth();
guarded(loadRuntimes);
guarded(loadProjects);
