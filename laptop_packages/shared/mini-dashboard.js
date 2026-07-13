const params = new URLSearchParams(window.location.search);
const config = window.LAPTOP_PACKAGE || {};
const state = {
  brainHost: params.get("brain") || localStorage.getItem("aiops.brainHost") || config.brainHost || "100.70.49.32",
  machineId: config.machineId || "unknown-laptop",
  pet: config.pet || "Mini Phoenix",
  role: config.role || "Worker",
  messages: [],
  tasks: [],
  noc: null,
  lastHeartbeat: null,
  animationTick: 0,
};

const $ = (selector) => document.querySelector(selector);
const api = (path) => `http://${state.brainHost}:8088${path}`;

function setBrainHost() {
  const value = $("#brain-host").value.trim();
  if (!value) return;
  state.brainHost = value;
  localStorage.setItem("aiops.brainHost", value);
  refreshAll();
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

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[char]));
}

function petVariant() {
  const moods = ["focused", "curious", "alert", "steady", "fast", "deep", "bright", "quiet", "scanning", "charging"];
  const tasks = ["working", "thinking", "building", "editing", "researching", "emailing", "testing", "shipping", "guarding", "reporting"];
  const intensities = ["low", "medium", "high", "turbo", "recovery"];
  const pulse = state.animationTick % 20;
  const taskCount = state.tasks.filter((task) => task.status === "running" || task.status === "queued").length;
  const mood = moods[(pulse + taskCount) % moods.length];
  const task = tasks[(pulse + state.messages.length) % tasks.length];
  const intensity = intensities[(pulse + Math.min(taskCount, 9)) % intensities.length];
  return { mood, task, intensity, totalVariants: moods.length * tasks.length * intensities.length * 2 };
}

function renderPet() {
  const variant = petVariant();
  const running = state.tasks.some((task) => task.status === "running");
  const queued = state.tasks.filter((task) => task.status === "queued").length;
  $(".pet-shell").dataset.mood = variant.mood;
  $(".pet-shell").dataset.task = variant.task;
  $(".pet-name").textContent = state.pet;
  $(".pet-status").textContent = running ? `${variant.task} now` : queued ? `${queued} queued` : "standing by";
  $(".variant-count").textContent = `${variant.totalVariants}+ motion combinations`;
}

function renderTasks() {
  const rows = state.tasks.slice(0, 12).map((task) => `
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
  $("#message-list").innerHTML = state.messages.slice(0, 10).map((message) => `
    <article>
      <strong>${escapeHtml(message.subject)}</strong>
      <p>${escapeHtml(message.body).slice(0, 280)}</p>
      <small>${escapeHtml(message.message_type)} | priority ${escapeHtml(message.priority)}</small>
    </article>
  `).join("") || "<p>No Brain messages yet.</p>";
}

function renderSecurity() {
  const health = state.noc?.infrastructure?.database_health || "checking";
  const approvals = state.noc?.security?.pending_approvals ?? 0;
  $("#shield-state").textContent = approvals > 0 ? `${approvals} approvals need review` : "Shield scanning";
  $("#db-state").textContent = health;
  $(".shield-pet").dataset.alert = approvals > 0 ? "review" : "scan";
}

function renderHeartbeat(ok, detail = "") {
  state.lastHeartbeat = new Date();
  $("#heartbeat-state").textContent = ok ? "online" : "attention";
  $("#heartbeat-detail").textContent = ok ? `Last pulse ${state.lastHeartbeat.toLocaleTimeString()}` : detail;
}

async function publishHeartbeat() {
  const payload = {
    machine_id: state.machineId,
    device_name: state.role,
    hostname: location.hostname || state.machineId,
    network_status: "online",
    tailscale_status: "expected",
    current_ai_model: "Mini Phoenix package",
    active_projects: ["AI Operations Center"],
    current_tasks: state.tasks.slice(0, 5).map((task) => task.id),
    health_score: 85,
    metadata: { package: "mini-dashboard", pet: state.pet, source: "browser-dashboard" },
  };
  await postJson("/ops2/device-telemetry", payload);
  await postJson("/listener/events", {
    source_type: "machine",
    source_id: state.machineId,
    event_type: "workload_update",
    subject: `${state.machineId} Mini Phoenix heartbeat`,
    body: `${state.pet} is online, displaying task state, Shield status, and speaker feed.`,
    priority: 55,
    metadata: { package: "mini-dashboard", pet: state.pet },
  });
}

async function refreshAll() {
  $("#brain-host").value = state.brainHost;
  try {
    const [tasks, speaker, noc] = await Promise.all([
      getJson("/tasks"),
      getJson(`/speaker/feed/${state.machineId}`),
      getJson("/ops2/noc"),
    ]);
    state.tasks = (tasks.tasks || []).filter((task) => task.machine_id === state.machineId);
    state.messages = speaker.messages || [];
    state.noc = noc;
    await publishHeartbeat();
    renderHeartbeat(true);
  } catch (error) {
    renderHeartbeat(false, error.message);
  }
  state.animationTick += 1;
  renderPet();
  renderTasks();
  renderMessages();
  renderSecurity();
}

function speakUpdate() {
  const text = `${state.pet} report. ${$("#heartbeat-state").textContent}. ${$(".pet-status").textContent}. ${$("#shield-state").textContent}.`;
  if (!("speechSynthesis" in window)) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.pitch = 1.05;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

window.addEventListener("DOMContentLoaded", () => {
  $(".machine-name").textContent = state.machineId;
  $(".machine-role").textContent = state.role;
  $("#brain-host").value = state.brainHost;
  $("#save-brain").addEventListener("click", setBrainHost);
  $("#refresh").addEventListener("click", refreshAll);
  $("#speak").addEventListener("click", speakUpdate);
  refreshAll();
  setInterval(refreshAll, 10000);
  setInterval(() => {
    state.animationTick += 1;
    renderPet();
  }, 1300);
});
