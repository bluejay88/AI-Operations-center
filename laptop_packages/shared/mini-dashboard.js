const params = new URLSearchParams(window.location.search);
const pageConfig = document.body?.dataset || {};
const config = {
  ...(window.LAPTOP_PACKAGE || {}),
  machineId: pageConfig.machineId || window.LAPTOP_PACKAGE?.machineId,
  role: pageConfig.role || window.LAPTOP_PACKAGE?.role,
  pet: pageConfig.pet || window.LAPTOP_PACKAGE?.pet,
  specialty: pageConfig.specialty || window.LAPTOP_PACKAGE?.specialty,
  brainHost: pageConfig.brainHost || window.LAPTOP_PACKAGE?.brainHost,
};
const state = {
  brainHost: normalizeHost(params.get("brain") || localStorage.getItem("aiops.brainHost") || config.brainHost || "100.70.49.32"),
  machineId: config.machineId || "unknown-laptop",
  pet: config.pet || "Node Companion",
  role: config.role || "Worker",
  specialty: config.specialty || "operations",
  messages: [],
  tasks: [],
  approvals: [],
  remoteOps: [],
  readiness: null,
  noc: null,
  lastHeartbeat: null,
  apiConnected: false,
  animationTick: 0,
  refreshInFlight: false,
  chatSending: false,
  chatHistory: (() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(`aiops.${config.machineId}.petChat`) || "[]");
      return Array.isArray(saved) ? saved : [];
    } catch {
      return [];
    }
  })(),
  completedSeen: Number(localStorage.getItem(`aiops.${config.machineId}.completedSeen`) || 0),
};

const PERSONALITIES = {
  "dev-laptop": {
    codename: "Byte",
    specialty: "build/test/debug",
    identity: "Lead software systems companion",
    traits: ["precise", "curious", "resilient", "evidence-led"],
    capabilityCategories: {
      Build: ["Web apps", "APIs", "automation", "integrations"],
      Quality: ["Unit tests", "debugging", "profiling", "code review"],
      Delivery: ["Packaging", "documentation", "deploy readiness", "rollback plans"],
    },
    phrases: ["Compiling the plan", "Checking the diff", "Running the rubric", "Packaging the fix"],
    animations: ["building", "testing", "debugging", "refactoring", "documenting", "shipping", "validating"],
  },
  "research-laptop": {
    codename: "Nova",
    specialty: "research/trends/deals",
    identity: "Research intelligence companion",
    traits: ["inquisitive", "skeptical", "methodical", "signal-aware"],
    capabilityCategories: {
      Discover: ["Grants", "market signals", "papers", "opportunity scans"],
      Verify: ["Source checks", "cross-referencing", "ranking", "risk flags"],
      Synthesize: ["Briefings", "datasets", "forecasts", "recommendations"],
    },
    phrases: ["Scanning sources", "Mining signals", "Cross-checking evidence", "Ranking opportunities"],
    animations: ["researching", "scraping", "summarizing", "forecasting", "indexing", "reporting", "validating"],
  },
  "business-laptop": {
    codename: "Prism",
    specialty: "creative/brand/campaigns",
    identity: "Creative node companion",
    traits: ["inventive", "polished", "campaign-aware", "outcome-focused"],
    capabilityCategories: {
      Create: ["Brand assets", "presentations", "layouts", "creative writing"],
      Market: ["Social content", "ad concepts", "funnels", "campaign planning"],
      Assure: ["Approval routing", "asset notes", "customer packaging", "handoffs"],
    },
    phrases: ["Polishing the concept", "Composing the campaign", "Preparing the brand kit", "Packaging a deliverable"],
    animations: ["designing", "editing", "posting", "planning", "reporting", "approving", "on-roll"],
  },
};

const SHIELD_PROFILE = {
  attributes: ["least-privilege", "audit-first", "human-governed"],
  operational: ["approval review", "security events", "trust monitoring", "audit evidence"],
  governed: ["threat correlation", "automated containment", "policy simulation"],
  featureLanes: ["Detect", "Assess", "Approve", "Protect", "Audit"],
};

const $ = (selector) => document.querySelector(selector);
const servedByBrainApi = /^https?:$/.test(window.location.protocol) && window.location.port === "8088";
const api = (path) => servedByBrainApi ? `${window.location.origin}${path}` : `http://${state.brainHost}:8088${path}`;

function normalizeHost(value) {
  return String(value || "")
    .trim()
    .replace(/^https?:\/\//, "")
    .split("/")[0]
    .split(":")[0]
    .replace(/\\+$/, "");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[char]));
}

async function getJson(path) {
  const res = await fetch(api(path), { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function postJson(path, payload) {
  const res = await fetch(api(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function setBrainHost() {
  const value = normalizeHost($("#brain-host").value);
  if (!value) return;
  state.brainHost = value;
  localStorage.setItem("aiops.brainHost", value);
  refreshAll();
}

function currentMachine() {
  return (state.readiness?.machines || []).find((machine) => machine.id === state.machineId) || {};
}

function workloadTotals() {
  const counts = currentMachine().task_counts || {};
  const visible = state.tasks.reduce((totals, task) => {
    if (Object.hasOwn(totals, task.status)) totals[task.status] += 1;
    return totals;
  }, { queued: 0, running: 0, completed: 0 });
  const value = (key) => {
    const canonical = Number(counts[key]);
    return Number.isFinite(canonical) && canonical >= 0 ? canonical : visible[key];
  };
  return { queued: value("queued"), running: value("running"), completed: value("completed") };
}

function petVariant() {
  const moods = ["focused", "curious", "alert", "steady", "fast", "deep", "bright", "quiet", "scanning", "charging"];
  const personality = PERSONALITIES[state.machineId] || PERSONALITIES["dev-laptop"];
  const tasks = ["working", "thinking", "building", "editing", "researching", "emailing", "testing", "shipping", "guarding", "reporting", ...personality.animations];
  const intensities = ["low", "medium", "high", "turbo", "recovery"];
  const active = state.tasks.filter((task) => ["running", "queued"].includes(task.status)).length;
  const pulse = state.animationTick % 50;
  const mood = moods[(pulse + active + state.messages.length) % moods.length];
  const task = active > 0 ? tasks[(pulse + active) % tasks.length] : "thinking";
  const intensity = intensities[(pulse + Math.min(active, 9)) % intensities.length];
  return { mood, task, intensity, totalVariants: moods.length * tasks.length * intensities.length * 2 };
}

const TASK_MOTION_RULES = [
  [/deploy|release|publish|ship/i, "shipping"],
  [/test|audit|rubric|verify|validat/i, "testing"],
  [/debug|repair|fix|incident|error/i, "debugging"],
  [/research|source|market|grant|trend|scan/i, "researching"],
  [/design|brand|creative|campaign|asset/i, "designing"],
  [/report|brief|summary|document/i, "reporting"],
  [/connect|ssh|network|diagnostic|pulse/i, "connecting"],
  [/build|implement|develop|code/i, "building"],
];

function taskDrivenAnimation(personality, running) {
  const activeTask = state.tasks.find((task) => task.status === "running");
  const taskText = `${activeTask?.title || ""} ${activeTask?.description || ""}`;
  const matched = TASK_MOTION_RULES.find(([pattern]) => pattern.test(taskText));
  if (matched) return matched[1];
  return running ? personality.animations[0] : "monitoring";
}

function ensurePetMotionRig(stage, pet) {
  if (!stage || !pet) return;
  if (!pet.querySelector(".pet-signal-orbit")) {
    pet.insertAdjacentHTML("afterbegin", `
      <span class="pet-signal-orbit"><i></i><i></i><i></i></span>
      <span class="pet-work-stream"><i></i><i></i><i></i></span>
      <span class="pet-task-flare"></span>`);
  }
  if (!stage.querySelector(".pet-readout")) {
    const readout = document.createElement("div");
    readout.className = "pet-readout";
    readout.setAttribute("role", "status");
    readout.setAttribute("aria-live", "polite");
    readout.setAttribute("aria-atomic", "true");
    const name = pet.querySelector(".pet-name");
    const status = pet.querySelector(".pet-status");
    if (name) readout.append(name);
    if (status) readout.append(status);
    stage.append(readout);
  }
}

function mountShield() {
  const host = $(".shield-row");
  if (!host || host.dataset.upgraded === "true") return;
  host.dataset.upgraded = "true";
  host.innerHTML = `
    <div class="mini-shield-stage pet-stage pet-security pet-state-scanning" data-task="scanning" data-workload="calm" data-signal="limited">
      <div class="pet anim-scanning" aria-hidden="true">
        <span class="pet-fx pet-fx-left"></span><span class="pet-fx pet-fx-right"></span>
        <span class="pet-roll-burst"></span><span class="pet-aura"></span><span class="pet-halo"></span><span class="pet-siren"></span>
        <span class="pet-ear left"></span><span class="pet-ear right"></span>
        <span class="pet-screenplate"><span class="pet-gridlines"></span><span class="pet-scanline"></span><span class="pet-badge"></span><span class="pet-eye left"></span><span class="pet-eye right"></span><span class="pet-mouth"></span></span>
        <span class="pet-keyboard"><span></span><span></span><span></span><span></span></span><span class="pet-trackpad"></span>
        <span class="pet-base"></span><span class="pet-port left"></span><span class="pet-port right"></span><span class="pet-status-light"></span><span class="pet-tool"></span>
        <div class="pet-name">Shield</div><div class="pet-status">Continuous audit</div>
      </div>
    </div>
    <div class="mini-shield-profile">
      <div class="mini-shield-heading"><div><p class="eyebrow">Security PET</p><h2>Shield</h2></div><span id="shield-state" class="security-state">Scanning</span></div>
      <p>Protects this node with the same Brain-governed security operations as Mission Control.</p>
      <div class="shield-traits">${SHIELD_PROFILE.attributes.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>
      <dl><div><dt>Database</dt><dd id="db-state">checking</dd></div><div><dt>Security events</dt><dd id="shield-event-count">0</dd></div></dl>
      <details><summary>Protection operations</summary>
        <strong>Operational</strong><p>${SHIELD_PROFILE.operational.map(escapeHtml).join(" · ")}</p>
        <strong>Governed</strong><p>${SHIELD_PROFILE.governed.map(escapeHtml).join(" · ")}</p>
        <strong>Lanes</strong><p>${SHIELD_PROFILE.featureLanes.map(escapeHtml).join(" · ")}</p>
      </details>
    </div>`;
  const stage = $(".mini-shield-stage");
  ensurePetMotionRig(stage, stage?.querySelector(".pet"));
}

function mountConversation() {
  const workspace = $(".workspace");
  const feedGrid = $(".feed-grid");
  if (!workspace || !feedGrid || $("#pet-conversation")) return;
  const personality = PERSONALITIES[state.machineId] || PERSONALITIES["dev-laptop"];
  const section = document.createElement("section");
  section.id = "pet-conversation";
  section.className = "panel panel-pad pet-conversation";
  section.setAttribute("data-audit", "pet-conversation");
  section.innerHTML = `
    <div class="conversation-heading"><div><p class="eyebrow">PET conversation</p><h2>Talk with ${escapeHtml(personality.codename)}</h2></div><span id="pet-chat-state" role="status">Ready</span></div>
    <p class="muted">Audited Brain/model conversation. Advice may be generated immediately; protected actions still require approval.</p>
    <div id="pet-chat-log" class="pet-chat-log" role="log" aria-live="off" aria-label="PET conversation transcript"></div>
    <form id="pet-chat-form" class="pet-chat-form">
      <label for="pet-chat-input">Message</label>
      <textarea id="pet-chat-input" name="message" rows="3" maxlength="4000" placeholder="Ask ${escapeHtml(personality.codename)} a question or request an explanation." required></textarea>
      <div class="pet-chat-actions"><button id="pet-chat-send" type="submit">Send to PET</button><button id="pet-chat-speak" type="button">Speak latest reply</button><button id="pet-chat-clear" type="button">Clear transcript</button></div>
    </form>`;
  workspace.insertBefore(section, feedGrid);
  renderChat();
}

function saveChat() {
  state.chatHistory = state.chatHistory.slice(-20);
  sessionStorage.setItem(`aiops.${state.machineId}.petChat`, JSON.stringify(state.chatHistory));
}

function chatTime(timestamp) {
  const value = Number(timestamp);
  if (!Number.isFinite(value) || value <= 0) return "Earlier this session";
  return new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function renderChat() {
  const log = $("#pet-chat-log");
  if (!log) return;
  log.innerHTML = state.chatHistory.map((entry, index) => `
    <article class="pet-chat-message ${entry.role === "user" ? "from-user" : "from-pet"}" ${entry.role === "pet" && index === state.chatHistory.length - 1 ? 'role="status" aria-live="polite"' : ""}>
      <header class="pet-chat-message-head">
        <span class="pet-chat-avatar" aria-hidden="true">${entry.role === "user" ? "YOU" : escapeHtml(String(entry.name || state.pet).slice(0, 3).toUpperCase())}</span>
        <span><strong>${entry.role === "user" ? "You" : escapeHtml(entry.name || state.pet)}</strong><time>${escapeHtml(chatTime(entry.timestamp))}</time></span>
        ${entry.role === "pet" ? `<button class="pet-chat-message-action" type="button" data-chat-speak="${escapeHtml(entry.text)}" aria-label="Speak this reply">Speak</button>` : ""}
      </header>
      <p>${escapeHtml(entry.text)}</p>
    </article>`).join("") || "<p class=\"muted\">No messages yet. Your PET is listening.</p>";
  log.scrollTop = log.scrollHeight;
}

function speakText(text) {
  if (!("speechSynthesis" in window) || !text) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.pitch = 1.05;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

async function sendPetChat(event) {
  event.preventDefault();
  if (state.chatSending) return;
  const input = $("#pet-chat-input");
  const message = String(input?.value || "").trim();
  if (!message) return;
  const personality = PERSONALITIES[state.machineId] || PERSONALITIES["dev-laptop"];
  state.chatHistory.push({ role: "user", text: message, name: "You", timestamp: Date.now() });
  input.value = "";
  state.chatSending = true;
  $("#pet-chat-send").disabled = true;
  $("#pet-chat-state").textContent = `${personality.codename} is thinking`;
  saveChat();
  renderChat();
  try {
    const response = await postJson("/models/query", {
      purpose: `Governed PET conversation with ${personality.codename}`,
      prompt: `You are ${personality.codename}, the ${personality.identity} for ${state.machineId}. Reply conversationally and concisely to the user. Explain status and safe next steps. Never claim an action ran unless the supplied system evidence proves it. Protected, financial, destructive, credential, public-send, or remote-control actions require Brain/Jayla approval. User message: ${message}`,
      requester: state.machineId,
      target_id: state.machineId,
      priority: 65,
      auto_create_tasks: false,
      require_approval: false,
      options: { max_tokens: 420, interaction: "pet_chat", pet: personality.codename },
    });
    const reply = String(response.synthesized_response || "I recorded your message, but no model response was available.").trim();
    state.chatHistory.push({ role: "pet", text: reply, name: personality.codename, timestamp: Date.now() });
    $("#pet-chat-state").textContent = response.risk_level ? `Ready · ${response.risk_level} risk` : "Ready";
  } catch (error) {
    state.chatHistory.push({ role: "pet", text: `I could not reach the Brain model workflow: ${error.message}`, name: personality.codename, timestamp: Date.now() });
    $("#pet-chat-state").textContent = "Connection attention";
  } finally {
    state.chatSending = false;
    $("#pet-chat-send").disabled = false;
    saveChat();
    renderChat();
  }
}

function renderPet() {
  const variant = petVariant();
  const personality = PERSONALITIES[state.machineId] || PERSONALITIES["dev-laptop"];
  const totals = workloadTotals();
  const runningCount = totals.running;
  const running = runningCount > 0;
  const queued = totals.queued;
  const completed = totals.completed;
  const roll = completed >= state.completedSeen + 10;
  if (roll) {
    state.completedSeen = completed;
    localStorage.setItem(`aiops.${state.machineId}.completedSeen`, String(completed));
  }
  const stage = $(".top-strip .pet-stage");
  const pet = stage?.querySelector(".pet");
  ensurePetMotionRig(stage, pet);
  const machineState = String(currentMachine().state || "unknown").toLowerCase();
  const workerOnline = ["active", "online", "connected", "ready"].includes(machineState);
  const workerReachable = workerOnline || machineState.startsWith("reachable");
  const sshOnline = (currentMachine().connections || []).some((connection) =>
    ["ssh-22", "ssh-22-brain-to-laptop"].includes(connection.channel) && String(connection.status).toLowerCase() === "online");
  const stateClass = !state.apiConnected ? "pet-state-connecting" : !workerReachable ? "pet-state-idle" : roll ? "pet-state-on-roll" : running ? "pet-state-heavy" : "pet-state-online";
  const animation = !state.apiConnected ? "connecting" : !workerReachable ? "idle" : roll ? "on-roll" : running ? taskDrivenAnimation(personality, running) : queued ? "queuing" : "monitoring";
  const workload = runningCount >= 3 || queued >= 8 ? "critical" : runningCount >= 1 || queued >= 3 ? "busy" : queued ? "ready" : "calm";
  stage.dataset.mood = variant.mood;
  stage.dataset.task = animation;
  stage.dataset.intensity = variant.intensity;
  stage.dataset.offline = !state.apiConnected || !workerReachable;
  stage.dataset.roll = roll ? "true" : "false";
  stage.dataset.workload = workload;
  stage.dataset.signal = !state.apiConnected ? "lost" : sshOnline ? "strong" : workerReachable ? "limited" : "lost";
  stage.style.setProperty("--queue-load", String(Math.min(1, queued / 10)));
  stage.style.setProperty("--run-load", String(Math.min(1, runningCount / 4)));
  stage.classList.remove("pet-state-online", "pet-state-connecting", "pet-state-heavy", "pet-state-on-roll", "pet-state-idle");
  stage.classList.add(stateClass);
  if (pet) {
    pet.className = pet.className
      .split(/\s+/)
      .filter((name) => name && !name.startsWith("anim-"))
      .concat(`anim-${animation}`)
      .join(" ");
  }
  const phrase = personality.phrases[(completed + queued + runningCount) % personality.phrases.length];
  stage.querySelector(".pet-name").textContent = personality.codename || state.pet;
  stage.querySelector(".pet-status").textContent = running ? `${runningCount} active / ${phrase}` : queued ? `${queued} queued / ${phrase}` : `${personality.specialty} ready`;
  $(".variant-count").textContent = `${variant.totalVariants}+ state combinations`;
}

function renderMetrics() {
  const machine = currentMachine();
  const { queued, running, completed } = workloadTotals();
  $("#metric-queue").textContent = queued;
  $("#metric-running").textContent = running;
  $("#metric-done").textContent = completed;
  const machineState = String(machine.state || "checking");
  $("#metric-health").textContent = machineState;
  $("#metric-latency").textContent = machine.latest_benchmark?.brain_latency_ms ? `${Number(machine.latest_benchmark.brain_latency_ms).toFixed(0)} ms` : "--";
  $("#metric-ssh").textContent = (machine.connections || []).some((conn) => ["ssh-22", "ssh-22-brain-to-laptop"].includes(conn.channel) && conn.status === "online") ? "ready" : "review";
}

function renderCapabilityProfile() {
  const personality = PERSONALITIES[state.machineId] || PERSONALITIES["dev-laptop"];
  const target = $("#capability-profile");
  if (!target) return;
  target.innerHTML = `
    <div class="pet-identity-copy">
      <span class="eyebrow">PET identity</span>
      <h2>${escapeHtml(personality.codename)}</h2>
      <p>${escapeHtml(personality.identity)}</p>
      <div class="trait-list">${personality.traits.map((trait) => `<span>${escapeHtml(trait)}</span>`).join("")}</div>
    </div>
    <div class="capability-functions">
      <span class="eyebrow">Operational functions</span>
      <div class="capability-groups" data-audit="operational-capabilities">
        ${Object.entries(personality.capabilityCategories).map(([category, functions]) => `
          <section class="capability-group">
            <h3>${escapeHtml(category)}</h3>
            <ul>${functions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
          </section>
        `).join("")}
      </div>
    </div>`;
}

function renderTasks() {
  const rows = state.tasks.slice(0, 14).map((task) => `
    <tr>
      <td>${escapeHtml(task.id)}</td>
      <td>${escapeHtml(task.title)}</td>
      <td>${escapeHtml(task.agent_id)}</td>
      <td><span class="pill ${escapeHtml(task.status)}">${escapeHtml(task.status)}</span></td>
      <td>${escapeHtml(task.priority)}</td>
    </tr>
  `).join("");
  $("#task-body").innerHTML = rows || `<tr><td colspan="5">No assigned tasks visible yet.</td></tr>`;
}

function renderMessages() {
  $("#message-list").innerHTML = state.messages.slice(0, 9).map((message) => `
    <article>
      <h3>${escapeHtml(message.subject)}</h3>
      <p>${escapeHtml(message.body).slice(0, 260)}</p>
      <small>${escapeHtml(message.message_type)} | priority ${escapeHtml(message.priority)}</small>
    </article>
  `).join("") || "<p class=\"muted\">No Brain messages yet.</p>";
}

function renderApprovals() {
  const relevant = state.approvals.filter((item) => item.requester_machine_id === state.machineId || item.status === "pending");
  $("#approval-list").innerHTML = relevant.slice(0, 8).map((item) => `
    <article>
      <h3>#${escapeHtml(item.id)} ${escapeHtml(item.title)}</h3>
      <p>${escapeHtml(item.status)} | ${escapeHtml(item.risk_level)}</p>
      <small>${escapeHtml(item.audit_feedback || item.summary).slice(0, 220)}</small>
    </article>
  `).join("") || "<p class=\"muted\">No approvals waiting.</p>";
}

function renderRemoteOps() {
  const relevant = state.remoteOps.filter((item) => item.machine_id === state.machineId);
  $("#remote-list").innerHTML = relevant.slice(0, 8).map((item) => `
    <article>
      <h3>${escapeHtml(item.operation_type)}</h3>
      <p>${escapeHtml(item.status)} | ${escapeHtml(item.approval_policy)}</p>
      <small>${escapeHtml(item.command_summary).slice(0, 220)}</small>
    </article>
  `).join("") || "<p class=\"muted\">No remote operations queued.</p>";
}

function renderSecurity() {
  const health = state.noc?.infrastructure?.database_health || "checking";
  const approvals = state.noc?.security?.pending_approvals ?? 0;
  const events = state.noc?.security?.events?.length ?? 0;
  $("#shield-state").textContent = approvals > 0 ? `${approvals} approvals need review` : "Shield scanning";
  $("#db-state").textContent = health;
  $("#shield-event-count").textContent = events;
  const stage = $(".mini-shield-stage");
  if (stage) {
    stage.dataset.alert = approvals > 0 ? "review" : "scan";
    stage.dataset.task = approvals > 0 ? "approving" : "scanning";
    stage.dataset.workload = approvals >= 5 ? "critical" : approvals > 0 ? "busy" : "calm";
    stage.dataset.signal = state.apiConnected ? "strong" : "lost";
    const pet = stage.querySelector(".pet");
    if (pet) pet.className = `pet anim-${approvals > 0 ? "approving" : "scanning"}`;
    stage.querySelector(".pet-status").textContent = approvals > 0 ? `${approvals} approvals` : "Continuous audit";
  }
}

function renderHeartbeat(ok, detail = "") {
  state.apiConnected = ok;
  if (ok) state.lastHeartbeat = new Date();
  $("#heartbeat-state").textContent = ok ? "Brain API online" : "API attention";
  $("#heartbeat-state").className = ok ? "live-dot" : "live-dot attention";
  $("#heartbeat-detail").textContent = ok
    ? `Last pulse ${state.lastHeartbeat.toLocaleTimeString()}${detail ? ` · ${detail}` : ""}`
    : detail || "Brain API is not responding.";
  if (ok) {
    $("#heartbeat-detail").textContent = `Dashboard connected ${state.lastHeartbeat.toLocaleTimeString()}${detail ? ` · ${detail}` : ""}`;
  }
}

async function publishDashboardPresence() {
  const payload = {
    machine_id: state.machineId,
    device_name: state.role,
    hostname: location.hostname || state.machineId,
    current_ai_model: "AI Ops Node Console",
    active_projects: ["AI Operations Center"],
    current_tasks: state.tasks.slice(0, 5).map((task) => task.id),
    metadata: {
      package: "node-console",
      pet: state.pet,
      specialty: state.specialty,
      source: "browser-dashboard",
      observation_kind: "dashboard_presence",
    },
  };
  await postJson("/ops2/device-telemetry", payload);
}

async function requestRemoteOperation(operationType, summary) {
  const response = await postJson("/remote-ops", {
    machine_id: state.machineId,
    requested_by: `${state.machineId}/mini-dashboard`,
    operation_type: operationType,
    command_summary: summary,
    priority: operationType === "open_mini_dashboard" ? 72 : 88,
    metadata: { requested_from: "mini-dashboard", pet: state.pet, approval_expected: operationType !== "open_mini_dashboard" },
  });
  await postJson("/listener/events", {
    source_type: "machine",
    source_id: state.machineId,
    event_type: "workload_update",
    subject: `${state.machineId} requested ${operationType}`,
    body: summary,
    priority: 74,
    metadata: { machine_id: state.machineId, operation_type: operationType, response },
  });
  await refreshAll();
}

async function refreshAll() {
  if (state.refreshInFlight) return;
  state.refreshInFlight = true;
  $("#brain-host").value = state.brainHost;
  try {
    const [presence, ...results] = await Promise.allSettled([
      publishDashboardPresence(),
      getJson("/tasks"),
      getJson(`/speaker/feed/${state.machineId}`),
      getJson("/ops2/noc"),
      getJson("/readiness.json"),
      getJson("/approvals"),
      getJson("/remote-ops"),
    ]);
    const values = results.map((result) => result.status === "fulfilled" ? result.value : null);
    const [tasks, speaker, noc, readiness, approvals, remoteOps] = values;
    if (tasks) state.tasks = (tasks.tasks || []).filter((task) => task.machine_id === state.machineId);
    if (speaker) state.messages = speaker.messages || [];
    if (noc) state.noc = noc;
    if (readiness) state.readiness = readiness;
    if (approvals) state.approvals = approvals.approvals || [];
    if (remoteOps) state.remoteOps = remoteOps.requests || [];
    const available = results.filter((result) => result.status === "fulfilled").length;
    if (!available) throw results.find((result) => result.status === "rejected")?.reason || new Error("Brain API is not responding.");
    const unavailable = results.length - available;
    const presenceNote = presence.status === "rejected" ? " · presence observation unavailable" : "";
    renderHeartbeat(true, `${unavailable ? `${unavailable} feed${unavailable === 1 ? "" : "s"} unavailable` : "all feeds current"}${presenceNote}`);
  } catch (error) {
    renderHeartbeat(false, error.message);
  } finally {
    state.refreshInFlight = false;
  }
  state.animationTick += 1;
  renderPet();
  renderMetrics();
  renderTasks();
  renderMessages();
  renderApprovals();
  renderRemoteOps();
  renderSecurity();
}

function speakUpdate() {
  speakText(`${state.pet} report. ${$("#heartbeat-state").textContent}. ${$(".top-strip .pet-status").textContent}. ${$("#shield-state").textContent}.`);
}

function bindControls() {
  $("#save-brain").addEventListener("click", setBrainHost);
  $("#refresh").addEventListener("click", refreshAll);
  $("#speak").addEventListener("click", speakUpdate);
  $("#request-browser").addEventListener("click", () => requestRemoteOperation("remote_browser_view", "Request Brain/Jayla approval to view or control this laptop browser for troubleshooting and approved workflow support."));
  $("#request-files").addEventListener("click", () => requestRemoteOperation("remote_file_browse", "Request Brain/Jayla approval to browse this laptop project files for diagnostics, sync, and approved implementation work."));
  $("#request-dashboard").addEventListener("click", () => requestRemoteOperation("open_mini_dashboard", "Open or refresh the AI Operations Center Node Console on this laptop screen."));
  $("#pet-chat-form").addEventListener("submit", sendPetChat);
  $("#pet-chat-log").addEventListener("click", (event) => {
    const button = event.target.closest("[data-chat-speak]");
    if (button) speakText(button.dataset.chatSpeak);
  });
  $("#pet-chat-speak").addEventListener("click", () => speakText([...state.chatHistory].reverse().find((entry) => entry.role === "pet")?.text));
  $("#pet-chat-clear").addEventListener("click", () => { state.chatHistory = []; saveChat(); renderChat(); $("#pet-chat-state").textContent = "Ready"; });
}

window.addEventListener("DOMContentLoaded", () => {
  mountShield();
  mountConversation();
  document.body.dataset.machineId = state.machineId;
  document.body.dataset.auditReady = "true";
  const auditHooks = [
    [".side-rail", "node-connectivity"],
    [".top-strip .panel-pad", "realtime-totals"],
    [".top-strip .pet-stage", "pet-identity"],
    [".mini-shield-stage", "security-pet"],
    [".control-grid", "permission-gated-actions"],
    ["#task-body", "task-feed"],
    [".feed-grid", "brain-feeds"],
    ["#capability-profile", "pet-capabilities"],
  ];
  auditHooks.forEach(([selector, name]) => $(selector)?.setAttribute("data-audit", name));
  $(".machine-name").textContent = state.machineId;
  $(".machine-role").textContent = state.role;
  $(".specialty").textContent = state.specialty;
  $("#brain-host").value = state.brainHost;
  bindControls();
  renderCapabilityProfile();
  refreshAll();
  setInterval(refreshAll, 5000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refreshAll();
  });
  setInterval(() => {
    state.animationTick += 1;
    renderPet();
  }, 1200);
});
