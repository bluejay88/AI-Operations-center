const state = {
  registry: null,
  readiness: null,
  tasks: [],
  connections: [],
  factory: null,
  selectedReport: "hourly",
  stream: null,
};

const els = {
  summary: document.querySelector("#summary-strip"),
  machines: document.querySelector("#machine-grid"),
  factory: document.querySelector("#factory-grid"),
  factoryGates: document.querySelector("#factory-gates"),
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
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function taskCounts() {
  return state.tasks.reduce(
    (acc, task) => {
      acc[task.status] = (acc[task.status] || 0) + 1;
      return acc;
    },
    { queued: 0, running: 0, completed: 0 }
  );
}

function renderSummary() {
  const online = new Set((state.readiness?.machines || []).filter((machine) => machine.state === "online").map((machine) => machine.id));
  const machines = state.registry?.machines || [];
  const counts = taskCounts();
  const metrics = [
    ["Online", online.size, `${machines.length} machines registered`],
    ["Queued", counts.queued || 0, "waiting for workers"],
    ["Running", counts.running || 0, "active now"],
    ["Done", counts.completed || 0, "completed tasks"],
  ];

  els.summary.innerHTML = metrics
    .map(([label, value, hint]) => `<div class="metric"><strong>${value}</strong><span>${label} / ${hint}</span></div>`)
    .join("");
}

function renderMachines() {
  const readinessByMachine = Object.fromEntries((state.readiness?.machines || []).map((machine) => [machine.id, machine]));
  const tasksByMachine = state.tasks.reduce((acc, task) => {
    const bucket = (acc[task.machine_id] ||= { queued: 0, running: 0, completed: 0 });
    bucket[task.status] = (bucket[task.status] || 0) + 1;
    return acc;
  }, {});

  els.machines.innerHTML = (state.registry?.machines || [])
    .map((machine) => {
      const readiness = readinessByMachine[machine.id] || {};
      const stateLabel = readiness.state || "unknown";
      const isOnline = stateLabel === "online";
      const counts = tasksByMachine[machine.id] || {};
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
          <p>${escapeHtml(machine.responsibilities.slice(0, 4).join(", "))}</p>
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
          <ul>${machine.active_duties.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          <h4>Subagents</h4>
          <div class="tag-row">${machine.subagents.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
          <h4>Precheck Rubric</h4>
          <ul>${machine.precheck_rubric.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          <h4>Due Windows</h4>
          <dl class="due-list">${Object.entries(machine.due_windows).map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
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

async function loadReport(type = state.selectedReport) {
  state.selectedReport = type;
  const data = await api(`/reports/${type}`);
  els.report.textContent = data.report;
}

async function refresh() {
  const [registry, readiness, tasks, connections, factory] = await Promise.all([
    api("/registry"),
    api("/readiness.json"),
    api("/tasks"),
    api("/connections"),
    api("/factory"),
  ]);
  state.registry = registry;
  state.readiness = readiness;
  state.tasks = tasks.tasks;
  state.connections = connections.connections;
  state.factory = factory;
  renderSummary();
  renderMachines();
  renderFactory();
  renderAgents();
  renderTasks();
  await loadReport(state.selectedReport);
  els.lastRefresh.textContent = `Refreshed ${new Date().toLocaleTimeString()}`;
}

function applyRealtimePayload(payload) {
  state.readiness = payload.readiness;
  state.tasks = payload.tasks || [];
  state.connections = payload.connections || [];
  state.factory = payload.factory || state.factory;
  renderSummary();
  renderMachines();
  renderFactory();
  renderAgents();
  renderTasks();
  els.lastRefresh.textContent = `Live ${new Date().toLocaleTimeString()}`;
}

function startStream() {
  if (!window.EventSource) return;
  state.stream = new EventSource("/stream");
  state.stream.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    applyRealtimePayload(payload);
  };
  state.stream.onerror = () => {
    els.lastRefresh.textContent = "Live stream reconnecting";
  };
}

els.refresh.addEventListener("click", () => refresh().catch((error) => toast(error.message)));

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

refresh().catch((error) => toast(error.message));
startStream();
window.setInterval(() => refresh().catch(() => {}), 30000);
