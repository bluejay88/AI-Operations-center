const state = {
  registry: null,
  readiness: null,
  tasks: [],
  taskSummary: null,
  taskAccountingAudit: null,
  queueHealth: null,
  connections: [],
  connectionSummary: null,
  factory: null,
  phoenixBriefing: "",
  approvals: [],
  listenerEvents: [],
  speakerFeed: null,
  integrations: [],
  endpoints: null,
  collaboration: null,
  enterpriseFeatures: null,
  nodeMesh: null,
  operatorRequests: [],
  noc: null,
  mascotAnimations: [
    "sleeping", "working", "thinking", "running", "building", "editing", "researching", "emailing",
    "scanning", "guarding", "deploying", "testing", "debugging", "planning", "syncing", "reporting",
    "listening", "speaking", "approving", "reviewing", "learning", "optimizing", "backing-up", "warning",
    "cooling", "charging", "idle", "celebrating", "blocked", "triaging", "routing", "benchmarking",
    "indexing", "scraping", "summarizing", "forecasting", "budgeting", "invoicing", "posting", "designing",
    "packaging", "migrating", "securing", "encrypting", "auditing", "monitoring", "healing", "balancing",
    "queuing", "merging", "shipping", "documenting", "refactoring", "profiling", "validating", "archiving",
    "connecting", "on-roll", "heavy-work",
  ],
  selectedReport: "hourly",
  stream: null,
  refreshTimer: null,
  unlocked: false,
};

const PET_CAPABILITY_PROFILES = {
  "brain-gaming-pc": {
    attributes: ["orchestration", "approval-aware", "real-time telemetry"],
    operational: ["work routing", "status synthesis", "voice briefing", "event streaming"],
    governed: ["predictive remediation", "capacity balancing", "autonomous recovery"],
    featureLanes: ["Observe", "Reason", "Coordinate", "Govern", "Recover"],
  },
  "dev-laptop": {
    attributes: ["builder", "test-driven", "deployment-ready"],
    operational: ["code tasks", "test execution", "build reporting", "deployment handoff"],
    governed: ["visual regression", "dependency healing", "release rollback"],
    featureLanes: ["Build", "Test", "Review", "Ship", "Maintain"],
  },
  "research-laptop": {
    attributes: ["evidence-led", "source-aware", "opportunity-focused"],
    operational: ["research queues", "grant scouting", "structured synthesis", "source reporting"],
    governed: ["claim verification", "trend forecasting", "source reputation scoring"],
    featureLanes: ["Discover", "Verify", "Synthesize", "Forecast", "Archive"],
  },
  "business-laptop": {
    attributes: ["creative", "brand-aware", "revenue-focused"],
    operational: ["brand assets", "campaigns", "business tasking", "customer deliverables"],
    governed: ["CRM automation", "campaign optimization", "asset approval routing"],
    featureLanes: ["Create", "Brand", "Market", "Package", "Retain"],
  },
  "security-monitor": {
    attributes: ["least-privilege", "audit-first", "human-governed"],
    operational: ["approval review", "security events", "trust monitoring", "audit evidence"],
    governed: ["threat correlation", "automated containment", "policy simulation"],
    featureLanes: ["Detect", "Assess", "Approve", "Protect", "Audit"],
  },
};

const DEFAULT_BRAIN_API = "http://100.70.49.32:8088";
const params = new URLSearchParams(window.location.search);
const requestedApiBase = params.get("api");
if (requestedApiBase) {
  window.localStorage.setItem("aiOpsApiBase", requestedApiBase.replace(/\/$/, ""));
}

function resolveApiBase() {
  const stored = window.localStorage.getItem("aiOpsApiBase");
  if (stored) return stored.replace(/\/$/, "");
  const host = window.location.hostname;
  const sameOriginHosts = new Set(["localhost", "127.0.0.1", "100.70.49.32"]);
  if (window.location.protocol === "file:" || !sameOriginHosts.has(host)) return DEFAULT_BRAIN_API;
  return "";
}

const API_BASE = resolveApiBase();

const els = {
  lock: document.querySelector("#dashboard-lock"),
  loginForm: document.querySelector("#dashboard-login-form"),
  loginMessage: document.querySelector("#dashboard-login-message"),
  apiConnectionStatus: document.querySelector("#api-connection-status"),
  summary: document.querySelector("#summary-strip"),
  releaseAssurance: document.querySelector("#release-assurance"),
  releaseAssuranceStatus: document.querySelector("#release-assurance-status"),
  releaseAssuranceGates: document.querySelector("#release-assurance-gates"),
  releaseAssuranceUpdated: document.querySelector("#release-assurance-updated"),
  machines: document.querySelector("#machine-grid"),
  factory: document.querySelector("#factory-grid"),
  factoryGates: document.querySelector("#factory-gates"),
  phoenixSummary: document.querySelector("#phoenix-summary"),
  phoenixRefresh: document.querySelector("#phoenix-refresh"),
  phoenixSpeak: document.querySelector("#phoenix-speak"),
  approvals: document.querySelector("#approval-list"),
  listenerEvents: document.querySelector("#listener-list"),
  speakerList: document.querySelector("#speaker-list"),
  speakerTarget: document.querySelector("#speaker-target"),
  integrations: document.querySelector("#integration-list"),
  nocWorkforce: document.querySelector("#noc-workforce"),
  nocProjects: document.querySelector("#noc-projects"),
  nocBusiness: document.querySelector("#noc-business"),
  nocInfra: document.querySelector("#noc-infra"),
  nocAiMetrics: document.querySelector("#noc-ai-metrics"),
  nocSecurity: document.querySelector("#noc-security"),
  nocNotifications: document.querySelector("#noc-notifications"),
  nocCollaboration: document.querySelector("#noc-collaboration"),
  pets: document.querySelector("#pet-grid"),
  petCapabilityOverview: document.querySelector("#pet-capability-overview"),
  animationBankCount: document.querySelector("#animation-bank-count"),
  ops2Seed: document.querySelector("#ops2-seed"),
  ops2SeedLaptopWork: document.querySelector("#ops2-seed-laptop-work"),
  ops2SeedExpansion: document.querySelector("#ops2-seed-expansion"),
  ops2SeedBusinesses: document.querySelector("#ops2-seed-businesses"),
  ops2ExportAll: document.querySelector("#ops2-export-all"),
  ops2ExportProject: document.querySelector("#ops2-export-project"),
  operatorRequestForm: document.querySelector("#operator-request-form"),
  operatorRequestList: document.querySelector("#operator-request-list"),
  refreshOperatorRequests: document.querySelector("#refresh-operator-requests"),
  refreshApprovals: document.querySelector("#refresh-approvals"),
  refreshListener: document.querySelector("#refresh-listener"),
  refreshIntegrations: document.querySelector("#refresh-integrations"),
  refreshEndpoints: document.querySelector("#refresh-endpoints"),
  refreshCollaboration: document.querySelector("#refresh-collaboration"),
  peerRequests: document.querySelector("#peer-request-list"),
  enterpriseFeatures: document.querySelector("#enterprise-feature-list"),
  seedEnterpriseFeatures: document.querySelector("#seed-enterprise-features"),
  enterpriseFeatureSeed: document.querySelector("#enterprise-feature-seed"),
  refreshNodeMesh: document.querySelector("#refresh-node-mesh"),
  nodeMesh: document.querySelector("#node-mesh-list"),
  processApprovals: document.querySelector("#process-approvals"),
  endpoints: document.querySelector("#endpoint-list"),
  agents: document.querySelector("#agent-matrix"),
  tasks: document.querySelector("#task-table"),
  report: document.querySelector("#report-output"),
  refresh: document.querySelector("#refresh-button"),
  lastRefresh: document.querySelector("#last-refresh"),
  toast: document.querySelector("#toast"),
  dailyPriorities: document.querySelector("#daily-priorities"),
  devKickoff: document.querySelector("#dev-kickoff"),
  businessContinuity: document.querySelector("#business-continuity"),
  redistributeBusiness: document.querySelector("#redistribute-business"),
  taskForm: document.querySelector("#task-form"),
};

function toast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("visible");
  window.setTimeout(() => els.toast.classList.remove("visible"), 2800);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function api(path, options = {}) {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function safeApi(path, fallback, label, options = {}) {
  try {
    return await api(path, options);
  } catch (error) {
    console.error(`Failed to load ${label}`, error);
    toast(`Live data warning: ${label} failed`);
    return fallback;
  }
}

function normalizeFactory(payload) {
  return payload?.factory || payload || { machines: [], handoff_gates: [] };
}

function normalizeTasks(payload) {
  return Array.isArray(payload) ? payload : payload?.tasks || [];
}

function normalizeConnections(payload) {
  return Array.isArray(payload) ? payload : payload?.connections || [];
}

function normalizeApprovals(payload) {
  return Array.isArray(payload) ? payload : payload?.approvals || [];
}

function fallbackPanel(title, detail = "Waiting for live data.") {
  return `<article class="empty-state"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(detail)}</p></article>`;
}

function safeRender(label, renderFn) {
  try {
    renderFn();
  } catch (error) {
    console.error(`Render failed: ${label}`, error);
    toast(`Dashboard panel warning: ${label}`);
  }
}

function setConnectionStatus(message, tone = "") {
  if (!els.apiConnectionStatus) return;
  els.apiConnectionStatus.textContent = message;
  els.apiConnectionStatus.className = `connection-status ${tone}`.trim();
}

function taskCounts() {
  const recent = state.tasks.reduce(
    (acc, task) => {
      acc[task.status] = (acc[task.status] || 0) + 1;
      return acc;
    },
    { queued: 0, running: 0, completed: 0 }
  );
  const authoritative = state.taskSummary?.status_counts || {};
  return {
    queued: Number(authoritative.queued ?? recent.queued ?? 0),
    running: Number(authoritative.running ?? recent.running ?? 0),
    completed: Number(state.taskSummary?.completed_total ?? authoritative.completed ?? recent.completed ?? 0),
  };
}

function taskCountsForMachine(machineId, readiness = {}) {
  const authoritative = state.taskSummary?.by_machine?.[machineId] || {};
  const readinessCounts = readiness.task_counts || {};
  const factoryCounts = (state.factory?.machines || []).find((machine) => machine.id === machineId)?.live_task_counts || {};
  const recent = state.tasks.reduce((counts, task) => {
    if (task.machine_id === machineId) counts[task.status] = (counts[task.status] || 0) + 1;
    return counts;
  }, {});
  const value = (status) => Number(
    authoritative[status] ?? readinessCounts[status] ?? factoryCounts[status] ?? recent[status] ?? 0
  );
  return { queued: value("queued"), running: value("running"), completed: value("completed") };
}

function isLaptop(machine) {
  return machine?.role !== "brain" && machine?.id !== "brain-gaming-pc";
}

function isConnected(machine) {
  const status = String(machine?.state || "").toLowerCase();
  return status === "online" || status.startsWith("reachable");
}

function isActive(machine) {
  const workforce = String(machine?.workforce_status || machine?.employment_status || "").toLowerCase();
  return String(machine?.state || "").toLowerCase() === "online" && workforce === "employed";
}

function renderSummary() {
  const laptops = (state.readiness?.machines || []).filter(isLaptop);
  const liveSummary = state.readiness?.summary || state.noc?.infrastructure?.machine_summary || {};
  const connected = Number(liveSummary.connected_laptops ?? laptops.filter(isConnected).length);
  const active = Number(liveSummary.active_laptops ?? laptops.filter(isActive).length);
  const employedMachineIds = new Set(
    state.tasks
      .filter((task) => ["queued", "running"].includes(task.status) && task.machine_id)
      .map((task) => task.machine_id)
  );
  const employed = Number(liveSummary.employed_laptops ?? laptops.filter((machine) => {
    return String(machine.workforce_status || machine.employment_status || "").toLowerCase() === "employed";
  }).length);
  const assigned = Number(liveSummary.assigned_laptops ?? laptops.filter((machine) => {
    const counts = machine.task_counts || {};
    return employedMachineIds.has(machine.id) || Number(counts.running || 0) + Number(counts.queued || 0) > 0;
  }).length);
  const counts = taskCounts();
  const metrics = [
    ["Connected laptops", connected, `${laptops.length} registered`],
    ["Active laptops", active, "fresh worker heartbeat"],
    ["Employed laptops", employed, "configured workforce assignment"],
    ["Assigned laptops", assigned, "queued/running work"],
    ["Running jobs", counts.running, `${counts.queued} queued / ${counts.completed} completed`],
  ];

  els.summary.innerHTML = metrics
    .map(([label, value, hint]) => `<div class="metric"><strong>${value}</strong><span>${label} / ${hint}</span></div>`)
    .join("");
}

function booleanContractStatus(invariants) {
  const checks = Object.values(invariants || {}).filter((value) => typeof value === "boolean");
  if (!checks.length) return "pending";
  return checks.every(Boolean) ? "passed" : "failed";
}

function renderReleaseAssurance() {
  if (!els.releaseAssuranceGates) return;
  const taskContract = state.taskSummary?.contract || {};
  const readinessTasks = state.readiness?.task_summary || {};
  const connectionContract = state.connectionSummary?.contract || {};
  const taskContractStatus = booleanContractStatus(taskContract.invariants);
  const readinessContractStatus = booleanContractStatus(
    readinessTasks.contract?.invariants || readinessTasks.contract
  );
  const readinessSummary = state.readiness?.summary || {};
  const registeredLaptops = Number(readinessSummary.registered_laptops || 0);
  const activeLaptops = Number(readinessSummary.active_laptops || 0);
  const readinessFleetStatus = readinessContractStatus === "failed"
    ? "failed"
    : readinessContractStatus === "passed" && registeredLaptops > 0 && activeLaptops === registeredLaptops ? "passed" : "pending";
  const connectionContractStatus = booleanContractStatus(connectionContract.invariants);
  const connectionAvailabilityStatus = state.connectionSummary?.availability?.status || "pending";
  const laptopIds = new Set((state.readiness?.machines || []).filter((machine) => machine.role !== "brain").map((machine) => machine.id));
  const networkReachableTargets = new Set((state.connections || [])
    .filter((connection) => connection.is_online && !connection.is_stale)
    .map((connection) => connection.target_machine_id)
    .filter((machineId) => laptopIds.has(machineId)));
  const directControlTargets = new Set((state.connections || [])
    .filter((connection) => connection.channel === "ssh-22-brain-to-laptop" && connection.is_online && !connection.is_stale)
    .map((connection) => connection.target_machine_id)
    .filter((machineId) => laptopIds.has(machineId)));
  const petCards = els.pets?.querySelectorAll("[data-pet-id][data-capability-status='mixed']").length || 0;
  const queueStalled = Number(state.queueHealth?.stalled_running || 0);
  const queueBacklog = Number(state.queueHealth?.queued || 0);
  const queueIdleHealthy = state.queueHealth?.idle_healthy_machines || [];
  const queueFlowStatus = !state.queueHealth
    ? "pending"
    : queueStalled > 0 ? "failed" : queueBacklog > 0 && queueIdleHealthy.length > 0 ? "pending" : "passed";
  const petProfilesComplete = Object.values(PET_CAPABILITY_PROFILES).every((profile) =>
    profile.attributes.length && profile.operational.length && profile.governed.length && profile.featureLanes.length === 5
  );
  const gates = [
    {
      id: "task-accounting",
      label: "Task accounting",
      status: state.taskAccountingAudit?.status || "pending",
      detail: state.taskAccountingAudit
        ? `${state.taskAccountingAudit.evidence?.completed_total ?? 0} completed / ${state.taskAccountingAudit.evidence?.machine_count ?? 0} machines`
        : "audit pending",
    },
    {
      id: "task-summary",
      label: "Lifetime totals",
      status: taskContractStatus,
      detail: taskContract.scope
        ? `${taskContract.scope} / ${taskContract.source || "unknown source"}`
        : "contract pending",
    },
    {
      id: "queue-flow",
      label: "Queue flow",
      status: queueFlowStatus,
      detail: state.queueHealth
        ? `${state.queueHealth.running ?? 0} running / ${queueBacklog} queued / ${queueStalled} stalled`
        : "queue steward pending",
    },
    {
      id: "connectivity",
      label: "Live network channels",
      status: connectionContractStatus === "failed" || connectionAvailabilityStatus === "failed"
        ? "failed"
        : connectionContractStatus === "passed" && connectionAvailabilityStatus === "passed" && laptopIds.size > 0 && networkReachableTargets.size === laptopIds.size ? "passed" : "pending",
      detail: state.connectionSummary
        ? `${networkReachableTargets.size}/${laptopIds.size || 0} laptops reachable / ${state.connectionSummary.stale_records ?? 0} stale records`
        : "summary pending",
    },
    {
      id: "readiness",
      label: "Worker fleet activity",
      status: readinessFleetStatus,
      detail: state.readiness?.summary
        ? `${state.readiness.summary.active_laptops ?? 0} active / ${state.readiness.summary.registered_laptops ?? 0} registered`
        : "summary pending",
    },
    {
      id: "direct-control",
      label: "Direct laptop control",
      status: laptopIds.size && directControlTargets.size === laptopIds.size ? "passed" : "pending",
      detail: `${directControlTargets.size}/${laptopIds.size || 0} SSH control paths ready`,
    },
    {
      id: "pet-ui",
      label: "PET spec / UI",
      status: petProfilesComplete && petCards >= Object.keys(PET_CAPABILITY_PROFILES).length ? "passed" : "pending",
      detail: `${petCards}/${Object.keys(PET_CAPABILITY_PROFILES).length} profiles / responsive gates`,
    },
  ];
  const failed = gates.filter((gate) => gate.status === "failed").length;
  const pending = gates.filter((gate) => gate.status !== "passed" && gate.status !== "failed").length;
  const overall = failed ? "failed" : pending ? "pending" : "passed";
  const statusLabel = failed ? `${failed} gate${failed === 1 ? "" : "s"} need attention` : pending ? `${pending} gate${pending === 1 ? "" : "s"} waiting` : "Release assured";

  els.releaseAssurance.dataset.releaseStage = overall;
  els.releaseAssuranceStatus.className = `release-status ${overall}`;
  els.releaseAssuranceStatus.textContent = statusLabel;
  els.releaseAssuranceGates.innerHTML = gates.map((gate) => `
    <div class="release-gate ${escapeHtml(gate.status)}" data-assurance-gate="${escapeHtml(gate.id)}" data-gate-status="${escapeHtml(gate.status)}">
      <span class="release-gate-indicator" aria-hidden="true"></span>
      <div><strong>${escapeHtml(gate.label)}</strong><span>${escapeHtml(gate.detail)}</span></div>
    </div>
  `).join("");
  els.releaseAssuranceUpdated.textContent = `Contract snapshot ${new Date().toLocaleTimeString()} / stream + polling`;
}

function renderMachines() {
  if (!(state.registry?.machines || []).length) {
    els.machines.innerHTML = fallbackPanel("Machine registry unavailable", "The dashboard is waiting for /registry from the Brain API.");
    return;
  }
  const readinessByMachine = Object.fromEntries((state.readiness?.machines || []).map((machine) => [machine.id, machine]));

  els.machines.innerHTML = (state.registry?.machines || [])
    .map((machine) => {
      const readiness = readinessByMachine[machine.id] || {};
      const stateLabel = readiness.state || "unknown";
      const isOnline = stateLabel === "online" || stateLabel.startsWith("reachable");
      const counts = taskCountsForMachine(machine.id, readiness);
      const mesh = (readiness.connections || []).find((connection) => connection.channel === "tailscale-ping");
      const ssh = (readiness.connections || []).find((connection) => connection.channel === "ssh-22");
      return `
        <article class="machine">
          <header>
            <div>
              <h3>${iconForRole(machine.role)} ${escapeHtml(machine.id)}</h3>
              <small>${escapeHtml(machine.name)}</small>
            </div>
            <span class="pill ${isOnline ? "online" : "offline"}">${escapeHtml(stateLabel)}</span>
          </header>
          <p>${escapeHtml((machine.responsibilities || []).slice(0, 4).join(", "))}</p>
          <dl>
            <div><dt>Role</dt><dd>${escapeHtml(machine.role)}</dd></div>
            <div><dt>Heartbeat</dt><dd>${readiness.last_seen ? new Date(readiness.last_seen).toLocaleTimeString() : "never"}</dd></div>
            <div><dt>Tailscale</dt><dd>${escapeHtml(mesh?.status || "unknown")}</dd></div>
            <div><dt>SSH</dt><dd>${escapeHtml(ssh?.status || "unknown")}</dd></div>
            <div><dt>Queued</dt><dd>${counts.queued || 0}</dd></div>
            <div><dt>Completed</dt><dd>${counts.completed || 0}</dd></div>
          </dl>
        </article>
      `;
    })
    .join("");
}

function iconForRole(role) {
  const icons = {
    brain: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 3a3 3 0 0 0-3 3v1a3 3 0 0 0-2 5.24V14a4 4 0 0 0 4 4h1v-5H7v-2h2V8h2v13h2V8h2v3h2v2h-2v5h1a4 4 0 0 0 4-4v-1.76A3 3 0 0 0 18 7V6a3 3 0 0 0-5.2-2.04A3 3 0 0 0 9 3Z"/></svg>`,
    development: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-6v2h3v2H7v-2h3v-2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Zm0 2v9h16V7H4Zm5.7 2.3 1.4 1.4L9.8 12l1.3 1.3-1.4 1.4L7 12l2.7-2.7Zm4.6 0L17 12l-2.7 2.7-1.4-1.4 1.3-1.3-1.3-1.3 1.4-1.4Z"/></svg>`,
    research: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.5 3a7.5 7.5 0 0 1 5.95 12.06l4.24 4.25-1.41 1.41-4.25-4.24A7.5 7.5 0 1 1 10.5 3Zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11Z"/></svg>`,
    business: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4h6a2 2 0 0 1 2 2v2h3a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h3V6a2 2 0 0 1 2-2Zm0 4h6V6H9v2Zm-5 2v8h16v-8H4Zm7 2h2v2h-2v-2Z"/></svg>`,
  };
  return icons[role] || icons.business;
}

function renderAgents() {
  const agents = state.registry?.agents || [];
  const machines = state.registry?.machines || [];
  if (!machines.length) {
    els.agents.innerHTML = fallbackPanel("Agent registry unavailable", "The dashboard is waiting for registered AI agents.");
    return;
  }
  els.agents.innerHTML = machines
    .map((machine) => {
      const assigned = agents.filter((agent) => agent.machine_id === machine.id);
      return `
        <section class="agent-group">
          <header>
            <h3>${iconForRole(machine.role)} ${escapeHtml(machine.id)}</h3>
            <span class="pill">${assigned.length} agents</span>
          </header>
          <div class="agent-list">
            ${assigned
              .map(
                (agent) => `
                  <div class="agent-row">
                    <div>
                      <strong>${escapeHtml(agent.name)}</strong>
                      <span>${escapeHtml(agent.category)} / ${escapeHtml(agent.cadence)}</span>
                    </div>
                    <span class="pill online">${escapeHtml(agent.status)}</span>
                  </div>
                `
              )
              .join("")}
          </div>
        </section>
      `;
    })
    .join("");
}

function renderFactory() {
  const machines = state.factory?.machines || [];
  if (!machines.length) {
    els.factory.innerHTML = fallbackPanel("Factory data unavailable", "The dashboard is waiting for the Brain factory map.");
    els.factoryGates.innerHTML = "";
    return;
  }
  els.factory.innerHTML = machines
    .map((machine) => {
      const counts = machine.live_task_counts || {};
      return `
        <article class="factory-machine">
          <header>
            <h3>${iconForRole(machine.id === "brain-gaming-pc" ? "brain" : machine.id.includes("dev") ? "development" : machine.id.includes("research") ? "research" : "business")} ${escapeHtml(machine.title)}</h3>
            <span class="pill">${escapeHtml(machine.id)}</span>
          </header>
          <p>${escapeHtml(machine.factory_role)}</p>
          <div class="factory-kpis">
            <span>Queued ${counts.queued || 0}</span>
            <span>Running ${counts.running || 0}</span>
            <span>Done ${counts.completed || 0}</span>
          </div>
          <h4>Duties</h4>
          <ul>${(machine.active_duties || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          <h4>Subagents</h4>
          <div class="tag-row">${(machine.subagents || []).map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          <h4>Precheck Rubric</h4>
          <ul>${(machine.precheck_rubric || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          <h4>Due Windows</h4>
          <dl class="due-list">${Object.entries(machine.due_windows || {}).map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
        </article>
      `;
    })
    .join("");

  const gates = state.factory?.handoff_gates || [];
  els.factoryGates.innerHTML = `
    <h3>Brain Evaluation Gates</h3>
    <div class="gate-row">
      ${gates
        .map(
          (gate) => `
            <div class="gate">
              <strong>${escapeHtml(gate.id)}</strong>
              <span>${escapeHtml(gate.owner)}</span>
              <p>${escapeHtml(gate.requirement)}</p>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function metricTile(label, value, hint = "") {
  return `<div class="noc-metric"><strong>${escapeHtml(value ?? "n/a")}</strong><span>${escapeHtml(label)}</span>${hint ? `<small>${escapeHtml(hint)}</small>` : ""}</div>`;
}

function renderNoc() {
  const noc = state.noc || {};
  const workforce = noc.ai_workforce || {};
  els.nocWorkforce.innerHTML = [
    metricTile("Online agents", workforce.active_agents, "registered active"),
    metricTile("Active jobs", workforce.active_jobs, "running now"),
    metricTile("Queue length", workforce.queue_length, "waiting"),
    metricTile("CPU score", workforce.cpu_usage, "latest benchmark"),
    metricTile("Memory usage", workforce.memory_usage ? `${workforce.memory_usage}%` : "n/a", "estimated"),
    metricTile("Completed", state.taskSummary?.completed_total ?? workforce.completed_jobs ?? taskCounts().completed, "lifetime database total"),
  ].join("");

  els.nocProjects.innerHTML = (noc.projects || [])
    .map(
      (project) => `
        <article>
          <strong>${escapeHtml(project.name)}</strong>
          <span>${escapeHtml(project.status)} / owner ${escapeHtml(project.owner_machine_id || project.current_owner_machine_id || "unassigned")} / risk ${escapeHtml(project.risk_score)}</span>
          <p>Progress ${escapeHtml(project.progress)}%, quality ${escapeHtml(project.quality_score)}, coverage ${escapeHtml(project.test_coverage)}%, target ${escapeHtml(project.revenue_target || 0)}</p>
        </article>
      `
    )
    .join("") || `<p class="muted">No projects seeded yet.</p>`;

  els.nocBusiness.innerHTML = (noc.business || [])
    .filter((metric) => metric.domain === "business")
    .map((metric) => metricTile(metric.name, `${metric.value} ${metric.unit}`, metric.target ? `target ${metric.target}` : ""))
    .join("") || metricTile("Business KPIs", "none", "seed 2.0");

  const telemetryByMachine = Object.fromEntries((noc.infrastructure?.telemetry || []).map((item) => [item.machine_id, item]));
  const sshByMachine = Object.fromEntries((noc.ssh_status || []).map((item) => [item.machine_id, item]));
  els.nocInfra.innerHTML = (noc.infrastructure?.machines || [])
    .map((machine) => {
      const tele = telemetryByMachine[machine.machine_id] || {};
      const ssh = sshByMachine[machine.machine_id] || {};
      return `
        <article>
          <strong>${escapeHtml(machine.machine_id)}</strong>
          <span>${escapeHtml(machine.status)} / ${escapeHtml(machine.hostname || tele.hostname || "unknown host")}</span>
          <p>Health ${escapeHtml(tele.health_score ?? "n/a")} / battery ${escapeHtml(tele.battery_percent ?? "n/a")}% / temp ${escapeHtml(tele.temperature_c ?? "n/a")}C / SSH ${escapeHtml(ssh.state || "not audited")}</p>
        </article>
      `;
    })
    .join("") || `<p class="muted">No telemetry yet.</p>`;

  const ai = noc.ai_metrics || {};
  els.nocAiMetrics.innerHTML = [
    metricTile("Tokens consumed", ai.tokens_consumed),
    metricTile("Inference time", ai.average_inference_ms, "avg ms"),
    metricTile("Quality", ai.average_quality, "avg score"),
    metricTile("Success", ai.successes),
    metricTile("Failures", ai.failures),
    metricTile("Cost estimate", ai.cost_estimate),
  ].join("");

  els.nocSecurity.innerHTML = `
    <article>
      <strong>Pending approvals</strong>
      <span>${escapeHtml(noc.security?.pending_approvals || 0)} waiting for Brain review</span>
    </article>
    ${(noc.security?.events || [])
      .slice(0, 8)
      .map((event) => `<article><strong>${escapeHtml(event.subject)}</strong><span>${escapeHtml(event.severity)} / ${escapeHtml(event.event_type)}</span><p>${escapeHtml(event.body)}</p></article>`)
      .join("") || `<p class="muted">No security events.</p>`}
  `;

  els.nocNotifications.innerHTML = (noc.notifications || [])
    .map((item) => `<article><strong>${escapeHtml(item.subject)}</strong><span>${escapeHtml(item.category)} / P${escapeHtml(item.priority)} / ${escapeHtml(item.status)}</span><p>${escapeHtml(item.body)}</p></article>`)
    .join("") || `<p class="muted">No notifications queued.</p>`;

  const updates = noc.collaboration?.updates || [];
  const recs = noc.collaboration?.recommendations || [];
  els.nocCollaboration.innerHTML = [
    ...(noc.ssh_status || []).map((item) => `<article><strong>${escapeHtml(item.machine_id)} SSH</strong><span>${escapeHtml(item.label)} / user ${escapeHtml(item.brain_ssh_user || "unknown")}</span><p>API ${escapeHtml(item.brain_api)} / port 22 ${escapeHtml(item.brain_ssh_port)} / noninteractive ${escapeHtml(item.ssh_noninteractive)}</p></article>`),
    ...updates.slice(0, 8).map((item) => {
      const metrics = item.metrics || {};
      const body =
        item.update_type === "laptop_unblock_audit"
          ? `Tailscale ${metrics.tailscale ?? "n/a"} / SSH port ${metrics.brain_ssh_port ?? "n/a"} / SSH auth ${metrics.ssh_noninteractive ?? "n/a"} / state ${metrics.ssh_auth_state || "unknown"}`
          : item.logs || "";
      return `<article><strong>${escapeHtml(item.summary)}</strong><span>${escapeHtml(item.machine_id)} / ${escapeHtml(item.update_type)} / ${escapeHtml(item.outcome || "published")}</span><p>${escapeHtml(body)}</p></article>`;
    }),
    ...recs.slice(0, 5).map((item) => `<article><strong>${escapeHtml(item.summary)}</strong><span>Recommendation / P${escapeHtml(item.priority)} / ${escapeHtml(item.machine_id || "global")}</span><p>${escapeHtml(item.rationale)}</p></article>`),
  ].join("") || `<p class="muted">No workstation updates yet.</p>`;
}

function mascotForMachine(machine) {
  const map = {
    "brain-gaming-pc": {
      name: "Phoenix",
      type: "Brain sentinel",
      className: "pet-brain",
      baseAnimation: "monitoring",
      accent: "Mission Control",
    },
    "dev-laptop": {
      name: "Byte",
      type: "Code forge companion",
      className: "pet-dev",
      baseAnimation: "building",
      accent: "Lead Software Engineer",
    },
    "research-laptop": {
      name: "Nova",
      type: "Research scout",
      className: "pet-research",
      baseAnimation: "researching",
      accent: "Intelligence Lead",
    },
    "business-laptop": {
      name: "Prism",
      type: "Creative workstation",
      className: "pet-business",
      baseAnimation: "designing",
      accent: "Creative Node",
    },
  };
  return map[machine.id] || {
    name: "Node",
    type: "Managed workstation",
    className: "pet-node",
    baseAnimation: "syncing",
    accent: machine.role || "Worker",
  };
}

function chooseAnimation(machine, readiness, taskCountsForMachine, telemetry) {
  const stateLabel = readiness?.state || "unknown";
  const temp = telemetry?.temperature_c;
  const health = telemetry?.health_score;
  if (stateLabel.includes("stale") || stateLabel === "offline" || stateLabel === "blocked" || stateLabel === "unknown") return "connecting";
  if (temp !== undefined && temp !== null && Number(temp) >= 85) return "cooling";
  if (health !== undefined && health !== null && Number(health) < 60) return "warning";
  if ((taskCountsForMachine?.running || 0) >= 2) return "heavy-work";
  if ((taskCountsForMachine?.running || 0) > 0) {
    if (machine.id.includes("dev")) return "building";
    if (machine.id.includes("research")) return "researching";
    if (machine.id.includes("business")) return "emailing";
    return "routing";
  }
  if ((taskCountsForMachine?.completed || 0) >= 10 && (taskCountsForMachine.completed % 10) <= 2) return "on-roll";
  if ((taskCountsForMachine?.queued || 0) > 4) return "queuing";
  return mascotForMachine(machine).baseAnimation;
}

function renderPets() {
  const machines = state.registry?.machines || [];
  const readinessByMachine = Object.fromEntries((state.readiness?.machines || []).map((machine) => [machine.id, machine]));
  const telemetryByMachine = Object.fromEntries((state.noc?.infrastructure?.telemetry || []).map((item) => [item.machine_id, item]));
  const securityAnimation = (state.noc?.security?.pending_approvals || 0) > 0 ? "reviewing" : "scanning";

  els.pets.innerHTML = [
    ...machines.map((machine) => {
      const mascot = mascotForMachine(machine);
      const readiness = readinessByMachine[machine.id] || {};
      const counts = taskCountsForMachine(machine.id, readiness);
      const telemetry = telemetryByMachine[machine.id] || {};
      const animation = chooseAnimation(machine, readiness, counts, telemetry);
      const completedCluster = Math.floor((counts.completed || 0) / 10);
      return petMarkup({
        ...mascot,
        machineId: machine.id,
        animation,
        stateClass: petStateClass(animation, readiness.state),
        completedCluster,
        status: readiness.state || "unknown",
        primary: `${counts.running || 0} running / ${counts.queued || 0} queued`,
        secondary: `Done ${counts.completed || 0} / Roll x${completedCluster} / Health ${telemetry.health_score ?? "n/a"} / Battery ${telemetry.battery_percent ?? "n/a"}%`,
        capabilities: PET_CAPABILITY_PROFILES[machine.id],
      });
    }),
    petMarkup({
      name: "Shield",
      type: "Security scanner",
      className: "pet-security",
      machineId: "security-monitor",
      animation: securityAnimation,
      stateClass: "pet-state-scanning",
      completedCluster: 0,
      status: `${state.noc?.security?.pending_approvals || 0} approvals`,
      primary: `${state.noc?.security?.events?.length || 0} recent events`,
      secondary: "Continuous audit and trust monitoring",
      accent: "Security",
      capabilities: PET_CAPABILITY_PROFILES["security-monitor"],
    }),
  ].join("");
  els.animationBankCount.textContent = `${state.mascotAnimations.length} animations loaded`;
  if (els.petCapabilityOverview) {
    const profiles = Object.values(PET_CAPABILITY_PROFILES);
    const operational = profiles.reduce((total, profile) => total + profile.operational.length, 0);
    const governed = profiles.reduce((total, profile) => total + profile.governed.length, 0);
    els.petCapabilityOverview.innerHTML = `
      <div><strong>500</strong><span>features governed by the PET specification</span></div>
      <div><strong>${operational}</strong><span>operational capability signals shown live</span></div>
      <div><strong>${governed}</strong><span>governed / planned capability groups</span></div>
      <div><strong>${profiles.length * 5}</strong><span>feature lanes mapped across companions</span></div>
    `;
  }
}

function petStateClass(animation, readinessState) {
  if (animation === "connecting") return "pet-state-connecting";
  if (animation === "on-roll") return "pet-state-on-roll";
  if (animation === "heavy-work") return "pet-state-heavy";
  if (readinessState === "online" || readinessState?.startsWith("reachable")) return "pet-state-online";
  return "pet-state-idle";
}

function petMarkup(pet) {
  const animationClass = `anim-${pet.animation}`;
  const profile = pet.capabilities || { attributes: [], operational: [], governed: [], featureLanes: [] };
  const petId = `pet-${String(pet.machineId).replace(/[^a-z0-9-]/gi, "-")}`;
  return `
    <article class="pet-panel ${escapeHtml(pet.className)} ${escapeHtml(pet.stateClass || "")}" id="${escapeHtml(petId)}" data-pet-id="${escapeHtml(pet.machineId)}" data-capability-status="mixed" aria-labelledby="${escapeHtml(petId)}-title">
      <div class="pet-stage" aria-hidden="true">
        <div class="pet ${animationClass}" title="${escapeHtml(pet.name)} is ${escapeHtml(pet.animation)}">
          <span class="pet-fx pet-fx-left"></span>
          <span class="pet-fx pet-fx-right"></span>
          <span class="pet-roll-burst"></span>
          <span class="pet-aura"></span>
          <span class="pet-halo"></span>
          <span class="pet-siren"><span></span><span></span></span>
          <span class="pet-ear left"></span>
          <span class="pet-ear right"></span>
          <span class="pet-screenplate">
            <span class="pet-gridlines"></span>
            <span class="pet-scanline"></span>
            <span class="pet-badge"></span>
            <span class="pet-eye left"></span>
            <span class="pet-eye right"></span>
            <span class="pet-mouth"></span>
          </span>
          <span class="pet-keyboard">
            <span></span><span></span><span></span><span></span>
          </span>
          <span class="pet-trackpad"></span>
          <span class="pet-base"></span>
          <span class="pet-port left"></span>
          <span class="pet-port right"></span>
          <span class="pet-status-light"></span>
          <span class="pet-tool"></span>
        </div>
      </div>
      <div class="pet-copy">
        <header>
          <div>
            <h3 id="${escapeHtml(petId)}-title">${escapeHtml(pet.name)}</h3>
            <span>${escapeHtml(pet.type)} / ${escapeHtml(pet.accent)}</span>
          </div>
          <span class="pill online" data-live-animation="${escapeHtml(pet.animation)}">${escapeHtml(pet.animation)}</span>
        </header>
        <div class="pet-attributes" aria-label="PET attributes">
          ${profile.attributes.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
        </div>
        ${pet.completedCluster ? `<div class="roll-meter">On a roll: ${escapeHtml(pet.completedCluster)} cluster${pet.completedCluster === 1 ? "" : "s"} of 10 completed</div>` : ""}
        <dl>
          <div><dt>Device</dt><dd>${escapeHtml(pet.machineId)}</dd></div>
          <div><dt>Status</dt><dd>${escapeHtml(pet.status)}</dd></div>
          <div><dt>Workload</dt><dd>${escapeHtml(pet.primary)}</dd></div>
          <div><dt>Signal</dt><dd>${escapeHtml(pet.secondary)}</dd></div>
        </dl>
        <details class="pet-capabilities">
          <summary>Capabilities and feature lanes</summary>
          <div class="capability-section" data-capability-kind="operational">
            <strong><span class="capability-dot operational"></span>Operational now</strong>
            <div>${profile.operational.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          </div>
          <div class="capability-section" data-capability-kind="governed-planned">
            <strong><span class="capability-dot governed"></span>Governed / planned</strong>
            <div>${profile.governed.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          </div>
          <div class="feature-lanes" aria-label="500-feature specification lanes">
            ${profile.featureLanes.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
          </div>
        </details>
      </div>
    </article>
  `;
}

function renderTasks() {
  els.tasks.innerHTML = state.tasks
    .map(
      (task) => `
        <tr>
          <td>${escapeHtml(task.priority)}</td>
          <td><span class="pill ${task.status === "completed" ? "online" : task.status === "running" ? "" : "offline"}">${task.status}</span></td>
          <td>
            <div class="task-title">${escapeHtml(task.title)}</div>
            <div class="task-desc">${escapeHtml(task.description || "")}</div>
          </td>
          <td>${escapeHtml(task.agent_id)}</td>
          <td>${escapeHtml(task.machine_id)}</td>
        </tr>
      `
    )
    .join("");
}

function renderApprovals() {
  els.approvals.innerHTML = (state.approvals || [])
    .slice(0, 12)
    .map(
      (item) => `
        <article class="approval-card" data-approval-id="${escapeHtml(item.id)}">
          <div class="approval-head">
            <strong>${escapeHtml(item.title)}</strong>
            <span class="score ${escapeHtml(item.approval_rating || "review")}">${escapeHtml(item.completion_score ?? 0)} / ${escapeHtml(item.approval_rating || "review")}</span>
          </div>
          <span>${escapeHtml(item.status)} / ${escapeHtml(item.risk_level)} / ${escapeHtml(item.requester_machine_id || "")} / ${escapeHtml(item.requester_agent_id || "")}</span>
          <p>${escapeHtml(item.outcome_summary || item.summary || "")}</p>
          <small>Produced: ${escapeHtml(item.proposed_changes || "No artifact/result description recorded yet.").slice(0, 280)}</small>
          <div class="evidence-row">
            ${Object.entries(item.evidence_checks || {}).map(([key, passed]) => `<span class="${passed ? "pass" : "missing"}">${escapeHtml(key)}</span>`).join("")}
          </div>
          <div class="approval-actions">
            <button type="button" data-approval-action="approved" data-id="${escapeHtml(item.id)}">Approve</button>
            <button type="button" data-approval-action="needs_changes" data-id="${escapeHtml(item.id)}">Cycle Back</button>
            <button type="button" data-approval-action="rejected" data-id="${escapeHtml(item.id)}">Deny</button>
            <button type="button" data-approval-action="deployed" data-id="${escapeHtml(item.id)}">Mark Done</button>
          </div>
        </article>
      `
    )
    .join("") || `<p class="muted">No approvals yet.</p>`;
}

function renderListenerEvents() {
  els.listenerEvents.innerHTML = (state.listenerEvents || [])
    .slice(0, 12)
    .map(
      (item) => `
        <article>
          <strong>${escapeHtml(item.subject)}</strong>
          <span>${escapeHtml(item.event_type)} / ${escapeHtml(item.source_id)}</span>
          <p>${escapeHtml(item.body || "")}</p>
        </article>
      `
    )
    .join("") || `<p class="muted">No listener events yet.</p>`;
}

function renderSpeakerFeed() {
  const feed = state.speakerFeed || {};
  els.speakerList.innerHTML = (feed.messages || [])
    .slice(0, 12)
    .map(
      (item) => `
        <article>
          <strong>${escapeHtml(item.subject)}</strong>
          <span>${escapeHtml(item.message_type)} / ${escapeHtml(item.status)} / P${escapeHtml(item.priority)}</span>
          <p>${escapeHtml(item.body || "")}</p>
        </article>
      `
    )
    .join("") || `<p class="muted">No speaker messages for this target.</p>`;
}

function renderIntegrations() {
  els.integrations.innerHTML = (state.integrations || [])
    .map(
      (item) => `
        <article>
          <strong>${escapeHtml(item.label)}</strong>
          <span>${item.configured ? "configured" : "not configured"}</span>
          <p>${escapeHtml(item.capability)}</p>
        </article>
      `
    )
    .join("");
}

function renderEndpoints() {
  const contract = state.endpoints || {};
  const endpoints = contract.endpoints || [];
  els.endpoints.innerHTML = [
    `<article><strong>Brain API</strong><span>${escapeHtml(contract.base_url || API_BASE || "same origin")} / port ${escapeHtml(contract.ports?.brain_api || 8088)}</span><p>${escapeHtml(contract.security?.approval_policy || "Sensitive actions require approval.")}</p></article>`,
    ...endpoints.map((item) => `
      <article>
        <strong>${escapeHtml(item.method)} ${escapeHtml(item.path)}</strong>
        <span>${escapeHtml(item.name)}</span>
        <p>${escapeHtml(item.purpose)}</p>
      </article>
    `),
  ].join("") || `<p class="muted">Endpoint contract unavailable.</p>`;
}

function renderCollaboration() {
  if (!els.peerRequests) return;
  const collaboration = state.collaboration || {};
  els.peerRequests.innerHTML = (collaboration.peer_requests || [])
    .slice(0, 14)
    .map((item) => `
      <article>
        <strong>${escapeHtml(item.subject)}</strong>
        <span>${escapeHtml(item.from_machine_id)} -> ${escapeHtml(item.to_machine_id)} / ${escapeHtml(item.status)} / ${escapeHtml(item.request_type)} / P${escapeHtml(item.priority)}</span>
        <p>${escapeHtml(item.response_body || item.body || "")}</p>
        <small>Score ${escapeHtml(item.quality_score ?? "pending")} / Project ${escapeHtml(item.project_id || "unassigned")} / Task ${escapeHtml(item.task_id || "n/a")}</small>
      </article>
    `)
    .join("") || `<p class="muted">No peer requests yet.</p>`;
}

function renderEnterpriseFeatures() {
  if (!els.enterpriseFeatures) return;
  const catalog = state.enterpriseFeatures || {};
  const domains = catalog.domains || [];
  els.enterpriseFeatures.innerHTML = [
    `<article>
      <strong>${escapeHtml(catalog.total_features || 500)} Feature Roadmap</strong>
      <span>${escapeHtml(catalog.domain_count || domains.length || 20)} domains / ${escapeHtml(catalog.features_per_domain || 25)} each</span>
      <p>Backlog items are deduped, routed by owner laptop, and gated by low, medium, or high risk approval policy.</p>
    </article>`,
    ...domains.slice(0, 8).map((domain) => {
      const highRisk = (domain.features || []).filter((feature) => String(feature.approval_policy || "").includes("high_risk")).length;
      return `
        <article>
          <strong>${escapeHtml(domain.name)}</strong>
          <span>${escapeHtml(domain.machine_id)} / ${escapeHtml(domain.agent_id)} / ${escapeHtml((domain.features || []).length)} items</span>
          <p>${escapeHtml(highRisk)} high-risk gates require Jayla approval before sensitive execution.</p>
        </article>
      `;
    }),
  ].join("");
}

function renderNodeMesh() {
  if (!els.nodeMesh) return;
  const mesh = state.nodeMesh || {};
  const nodes = Object.values(mesh.nodes || {});
  els.nodeMesh.innerHTML = [
    `<article>
      <strong>${escapeHtml(mesh.cluster || "Brain Mesh")}</strong>
      <span>${escapeHtml(mesh.transport || "Private mesh")} / ${escapeHtml(mesh.authority || "Brain authority")}</span>
      <p>${escapeHtml((mesh.security_rules || []).slice(0, 2).join(" "))}</p>
    </article>`,
    ...nodes.map((node) => `
      <article>
        <strong>${escapeHtml(node.title || node.name)}</strong>
        <span>${escapeHtml(node.node_id)} / ${escapeHtml(node.role)} / ${escapeHtml((node.channels || []).slice(0, 2).join(", "))}</span>
        <p>${escapeHtml((node.capabilities || []).slice(0, 6).join(", "))}</p>
      </article>
    `),
  ].join("");
}

function renderOperatorRequests() {
  els.operatorRequestList.innerHTML = (state.operatorRequests || [])
    .map((request) => {
      const delivery = Array.isArray(request.delivery_methods) ? request.delivery_methods.join(", ") : request.output_format;
      const tasks = Array.isArray(request.routed_task_ids) ? request.routed_task_ids.join(", ") : request.routed_task_ids || "";
      return `
        <article>
          <strong>${escapeHtml(request.title)}</strong>
          <span>${escapeHtml(request.status)} / P${escapeHtml(request.priority)} / ${escapeHtml(delivery)}</span>
          <p>${escapeHtml(request.request_body)}</p>
          <small>Target ${escapeHtml(request.target_machine_id || "Brain chooses")} / Agent ${escapeHtml(request.target_agent_id || "auto")} / Tasks ${escapeHtml(tasks || "pending")}</small>
        </article>
      `;
    })
    .join("") || `<p class="muted">No operator requests yet.</p>`;
}

async function loadReport(type = state.selectedReport) {
  state.selectedReport = type;
  const data = await safeApi(`/reports/${type}`, { report: "Report data is not available yet." }, `${type} report`);
  els.report.textContent = data.report;
}

async function loadPhoenixBriefing() {
  const data = await safeApi("/phoenix/briefing", { briefing: "Phoenix briefing is not available yet." }, "Phoenix briefing");
  state.phoenixBriefing = data.briefing;
  els.phoenixSummary.textContent = data.briefing;
}

async function loadApprovals() {
  const data = await safeApi("/approvals", { approvals: [] }, "approvals");
  state.approvals = data.approvals || [];
  renderApprovals();
}

async function loadListenerEvents() {
  const data = await safeApi("/listener/events", { events: [] }, "listener events");
  state.listenerEvents = data.events || [];
  renderListenerEvents();
}

async function loadSpeakerFeed() {
  const target = els.speakerTarget.value;
  state.speakerFeed = await safeApi(`/speaker/feed/${encodeURIComponent(target)}`, { target_id: target, messages: [] }, "speaker feed");
  renderSpeakerFeed();
}

async function loadIntegrations() {
  const data = await safeApi("/integrations/status", { providers: [] }, "integrations");
  state.integrations = data.providers || [];
  renderIntegrations();
}

async function loadEndpoints() {
  state.endpoints = await safeApi("/endpoints", { endpoints: [] }, "endpoint contract");
  renderEndpoints();
}

async function loadCollaboration() {
  state.collaboration = await safeApi("/collaboration", { peer_requests: [], handoffs: [], model_sessions: [] }, "collaboration");
  renderCollaboration();
}

async function loadEnterpriseFeatures() {
  state.enterpriseFeatures = await safeApi("/enterprise-features", { domains: [], total_features: 500 }, "enterprise features");
  renderEnterpriseFeatures();
}

async function loadNodeMesh() {
  state.nodeMesh = await safeApi("/node-mesh", { nodes: {} }, "node mesh");
  renderNodeMesh();
}

async function loadOperatorRequests() {
  const data = await safeApi("/operator-requests", { requests: [] }, "operator requests");
  state.operatorRequests = data.requests || [];
  renderOperatorRequests();
}

async function loadNoc() {
  state.noc = await safeApi("/ops2/noc", {}, "NOC");
  renderNoc();
}

async function refresh() {
  setConnectionStatus(`Connecting to Brain API ${API_BASE || window.location.origin}`, "warning");
  const [registry, readiness, tasks, connections, factory, noc] = await Promise.all([
    safeApi("/registry", { machines: [], agents: [] }, "registry"),
    api("/readiness.json"),
    safeApi("/tasks", { tasks: [] }, "tasks"),
    safeApi("/connections", { connections: [] }, "connections"),
    safeApi("/factory", { factory: { machines: [], handoff_gates: [] } }, "factory"),
    safeApi("/ops2/noc", {}, "NOC"),
  ]);
  state.registry = registry;
  state.readiness = readiness;
  state.tasks = normalizeTasks(tasks);
  state.taskSummary = tasks?.task_summary || state.taskSummary;
  state.taskAccountingAudit = tasks?.task_accounting_audit || state.taskAccountingAudit;
  state.queueHealth = tasks?.queue_health || state.queueHealth;
  state.connections = normalizeConnections(connections);
  state.connectionSummary = connections?.connection_summary || state.connectionSummary;
  state.factory = normalizeFactory(factory);
  state.noc = noc;
  safeRender("summary", renderSummary);
  safeRender("machines", renderMachines);
  safeRender("factory", renderFactory);
  safeRender("agents", renderAgents);
  safeRender("tasks", renderTasks);
  safeRender("NOC", renderNoc);
  safeRender("pets", renderPets);
  safeRender("release assurance", renderReleaseAssurance);
  await loadReport(state.selectedReport);
  await loadPhoenixBriefing();
  await Promise.all([
    loadApprovals(),
    loadListenerEvents(),
    loadSpeakerFeed(),
    loadIntegrations(),
    loadEndpoints(),
    loadCollaboration(),
    loadEnterpriseFeatures(),
    loadNodeMesh(),
    loadOperatorRequests(),
  ]);
  setConnectionStatus(`Connected to Brain API ${API_BASE || window.location.origin}`, "online");
  els.lastRefresh.textContent = `Refreshed ${new Date().toLocaleTimeString()}`;
}

function applyRealtimePayload(payload) {
  state.readiness = payload.readiness || state.readiness;
  if (payload.tasks) state.tasks = normalizeTasks(payload.tasks);
  if (payload.task_summary) state.taskSummary = payload.task_summary;
  if (payload.task_accounting_audit) state.taskAccountingAudit = payload.task_accounting_audit;
  if (payload.queue_health) state.queueHealth = payload.queue_health;
  if (payload.connections) state.connections = normalizeConnections(payload.connections);
  if (payload.connection_summary) state.connectionSummary = payload.connection_summary;
  state.factory = normalizeFactory(payload.factory || state.factory);
  state.approvals = normalizeApprovals(payload.approvals || state.approvals);
  state.noc = payload.noc || state.noc;
  state.listenerEvents = payload.listener?.events || state.listenerEvents;
  state.speakerFeed = payload.speaker || state.speakerFeed;
  state.collaboration = payload.collaboration || state.collaboration;
  if (payload.integrations) {
    state.integrations = Array.isArray(payload.integrations)
      ? payload.integrations
      : payload.integrations.providers || state.integrations;
  }
  safeRender("summary", renderSummary);
  safeRender("machines", renderMachines);
  safeRender("factory", renderFactory);
  safeRender("agents", renderAgents);
  safeRender("tasks", renderTasks);
  safeRender("approvals", renderApprovals);
  safeRender("listener", renderListenerEvents);
  safeRender("speaker", renderSpeakerFeed);
  safeRender("integrations", renderIntegrations);
  safeRender("collaboration", renderCollaboration);
  safeRender("enterprise features", renderEnterpriseFeatures);
  safeRender("node mesh", renderNodeMesh);
  safeRender("NOC", renderNoc);
  safeRender("pets", renderPets);
  safeRender("release assurance", renderReleaseAssurance);
  setConnectionStatus(`Live with Brain API ${API_BASE || window.location.origin}`, "online");
  els.lastRefresh.textContent = `Live ${new Date().toLocaleTimeString()}`;
}

function startStream() {
  if (!window.EventSource) return;
  state.stream?.close();
  state.stream = new EventSource(`${API_BASE}/stream`);
  state.stream.onmessage = (event) => {
    try {
      applyRealtimePayload(JSON.parse(event.data));
    } catch (error) {
      console.error("Invalid live dashboard payload", error);
      els.lastRefresh.textContent = "Live update could not be read";
    }
  };
  state.stream.onerror = () => {
    setConnectionStatus("Brain live stream reconnecting; polling remains active", "warning");
    els.lastRefresh.textContent = "Live stream reconnecting";
  };
}

function lockDashboard() {
  document.body.classList.add("locked");
  els.lock?.classList.remove("hidden");
  setConnectionStatus("Waiting for dashboard unlock.", "warning");
}

function unlockDashboard() {
  if (state.unlocked) return;
  state.unlocked = true;
  document.body.classList.remove("locked");
  els.lock?.classList.add("hidden");
  window.sessionStorage.setItem(`aiOpsUnlocked:${API_BASE || "same-origin"}`, "true");
  refresh().catch((error) => {
    console.error(error);
    setConnectionStatus(`Brain API connection failed: ${error.message}`, "warning");
    toast(error.message);
  });
  startStream();
  state.refreshTimer = window.setInterval(() => refresh().catch((error) => {
    console.error("Dashboard polling failed", error);
    setConnectionStatus(`Brain API polling failed: ${error.message}`, "warning");
  }), 15000);
}

async function submitDashboardLogin(password) {
  const data = await api("/dashboard/login", {
    method: "POST",
    body: JSON.stringify({ password: String(password || "").trim() }),
  });
  if (!data.ok) throw new Error(data.message || "Invalid dashboard password");
  els.loginMessage.textContent = data.message || "Dashboard unlocked";
  unlockDashboard();
}

function initializeDashboardGate() {
  lockDashboard();
  els.loginMessage.textContent = `Brain API: ${API_BASE || window.location.origin}`;
  if (window.sessionStorage.getItem(`aiOpsUnlocked:${API_BASE || "same-origin"}`) === "true") {
    unlockDashboard();
  }
}

els.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const password = String(form.get("password") || "");
  els.loginMessage.textContent = "Checking password...";
  try {
    await submitDashboardLogin(password);
  } catch (error) {
    els.loginMessage.textContent = `${error.message}. Check that this page is using Brain API ${API_BASE || window.location.origin}.`;
    toast(error.message);
  }
});

els.refresh.addEventListener("click", () => refresh().catch((error) => toast(error.message)));

els.phoenixRefresh.addEventListener("click", () => loadPhoenixBriefing().catch((error) => toast(error.message)));
els.refreshApprovals.addEventListener("click", () => loadApprovals().catch((error) => toast(error.message)));
els.refreshListener.addEventListener("click", () => loadListenerEvents().catch((error) => toast(error.message)));
els.refreshIntegrations.addEventListener("click", () => loadIntegrations().catch((error) => toast(error.message)));
els.refreshEndpoints.addEventListener("click", () => loadEndpoints().catch((error) => toast(error.message)));
els.refreshCollaboration?.addEventListener("click", () => loadCollaboration().catch((error) => toast(error.message)));
els.refreshNodeMesh?.addEventListener("click", () => loadNodeMesh().catch((error) => toast(error.message)));
els.refreshOperatorRequests.addEventListener("click", () => loadOperatorRequests().catch((error) => toast(error.message)));
els.speakerTarget.addEventListener("change", () => loadSpeakerFeed().catch((error) => toast(error.message)));

els.processApprovals.addEventListener("click", async () => {
  const data = await api("/approvals/process", {
    method: "POST",
    body: JSON.stringify({ limit: 50, actor: "brain-dashboard-processor" }),
  });
  toast(`Brain reviewed ${data.processed.length} approvals`);
  await Promise.all([loadApprovals(), loadListenerEvents(), loadSpeakerFeed(), loadNoc()]);
});

els.approvals.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-approval-action]");
  if (!button) return;
  const decision = button.dataset.approvalAction;
  const id = button.dataset.id;
  const feedbackByDecision = {
    approved: "Jayla dashboard approval: evidence reviewed and approved for the next controlled step. Continue through logged worker/speaker execution and report completion evidence.",
    needs_changes: "Jayla dashboard review: cycle this back with stronger evidence, exact artifacts, validation output, rollback plan, and security notes before approval.",
    rejected: "Jayla dashboard denial: do not execute this request. Record the reason, stop related remote operations, and propose a safer alternative.",
    deployed: "Jayla dashboard completion: deployment/result is accepted as completed. Preserve artifacts, logs, and final outcome summary.",
  };
  await api(`/approvals/${encodeURIComponent(id)}/review`, {
    method: "POST",
    body: JSON.stringify({
      decision,
      feedback: feedbackByDecision[decision] || "Dashboard review recorded.",
      actor: "jayla-dashboard",
      metadata: { source: "dashboard", human_reviewed: true },
    }),
  });
  toast(`Approval ${id}: ${decision}`);
  await Promise.all([loadApprovals(), loadListenerEvents(), loadSpeakerFeed(), loadNoc()]);
});

els.phoenixSpeak.addEventListener("click", async () => {
  if (!state.phoenixBriefing) {
    await loadPhoenixBriefing();
  }
  if (!window.speechSynthesis) {
    toast("Browser speech synthesis is not available");
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(state.phoenixBriefing);
  utterance.rate = 0.95;
  utterance.pitch = 0.92;
  window.speechSynthesis.speak(utterance);
});

document.querySelectorAll("[data-report]").forEach((button) => {
  button.addEventListener("click", () => loadReport(button.dataset.report).catch((error) => toast(error.message)));
});

els.dailyPriorities.addEventListener("click", async () => {
  const data = await api("/orchestrator/daily-priorities", { method: "POST" });
  toast(`Created task IDs: ${data.created_task_ids.join(", ")}`);
  await refresh();
});

els.devKickoff.addEventListener("click", async () => {
  const data = await api("/orchestrator/dev-kickoff", { method: "POST" });
  toast(`Dev tasks queued: ${data.created_task_ids.join(", ")}`);
  await refresh();
});

els.businessContinuity.addEventListener("click", async () => {
  const data = await api("/orchestrator/business-continuity", { method: "POST" });
  toast(`Business work distributed: ${data.created_task_ids.join(", ")}`);
  await refresh();
});

els.redistributeBusiness.addEventListener("click", async () => {
  const data = await api("/orchestrator/redistribute-business-queue", { method: "POST" });
  toast(`Reassigned ${data.reassigned.length} business tasks`);
  await refresh();
});

els.ops2Seed.addEventListener("click", async () => {
  const data = await api("/ops2/seed", { method: "POST" });
  toast(`Seeded 2.0: ${data.split.phase_count} phases`);
  await refresh();
});

els.ops2SeedLaptopWork.addEventListener("click", async () => {
  const data = await api("/ops2/laptop-work/seed?tasks_per_laptop=500", { method: "POST" });
  const machines = Object.entries(data.machines || {})
    .map(([machine, counts]) => `${machine}: ${counts.created} new`)
    .join(", ");
  toast(`Seeded laptop work: ${machines}`);
  await refresh();
});

els.ops2SeedExpansion.addEventListener("click", async () => {
  const data = await api("/ops2/expansion/seed?total=600", { method: "POST" });
  toast(`Seeded 600 expansion tasks: ${data.created} new / ${data.existing} existing`);
  await refresh();
});

els.ops2SeedBusinesses.addEventListener("click", async () => {
  const data = await api("/ops2/business-launches/seed", { method: "POST" });
  toast(`Launched 5 business workstreams with ${data.total_tasks} new tasks`);
  await refresh();
});

async function seedEnterpriseFeatures() {
  const data = await api("/enterprise-features/seed", { method: "POST" });
  toast(`Brain 500 backlog: ${data.created} new / ${data.existing} existing`);
  await refresh();
}

els.seedEnterpriseFeatures?.addEventListener("click", () => seedEnterpriseFeatures().catch((error) => toast(error.message)));
els.enterpriseFeatureSeed?.addEventListener("click", () => seedEnterpriseFeatures().catch((error) => toast(error.message)));

async function exportBundle(scope) {
  const data = await api(`/ops2/export?scope=${encodeURIComponent(scope)}`);
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `ai-ops-${scope}-bundle.json`;
  link.click();
  URL.revokeObjectURL(url);
  toast(`Exported ${scope} bundle`);
}

els.ops2ExportAll.addEventListener("click", () => exportBundle("all").catch((error) => toast(error.message)));
els.ops2ExportProject.addEventListener("click", () => exportBundle("project").catch((error) => toast(error.message)));

els.taskForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const body = Object.fromEntries(form.entries());
  body.priority = Number(body.priority || 50);
  const data = await api("/tasks", { method: "POST", body: JSON.stringify(body) });
  toast(`Queued task ${data.task_id}`);
  event.currentTarget.reset();
  await refresh();
});

els.operatorRequestForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const body = Object.fromEntries(form.entries());
  body.priority = Number(body.priority || 70);
  body.delivery_methods = [body.output_format || "dashboard"];
  const data = await api("/operator-requests", { method: "POST", body: JSON.stringify(body) });
  toast(`Request ${data.request.id} routed to task ${data.task_ids.join(", ")}`);
  event.currentTarget.reset();
  await refresh();
});

initializeDashboardGate();
