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
  collaboration: null,
  capabilityContracts: null,
  deviceCapabilityReceipts: [],
  readiness: null,
  readinessAvailable: false,
  readinessObservedAt: 0,
  noc: null,
  lastHeartbeat: null,
  apiConnected: false,
  animationTick: 0,
  refreshInFlight: false,
  chatSending: false,
  chatAbortController: null,
  chatRequestId: null,
  recognition: null,
  isListening: false,
  isSpeaking: false,
  microphonePermission: "unknown",
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

const MACHINE_PET_IDS = {
  "dev-laptop": "development-pet",
  "research-laptop": "research-pet",
  "business-laptop": "creative-pet",
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

async function postJson(path, payload, options = {}) {
  const res = await fetch(api(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options.signal,
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
  section.setAttribute("data-feature-ids", "PET-03-01 PET-03-03 PET-03-04 PET-03-08 PET-03-10");
  section.innerHTML = `
    <div class="conversation-heading"><div><p class="eyebrow">PET conversation</p><h2>Talk with ${escapeHtml(personality.codename)}</h2></div><span id="pet-chat-state" role="status">Ready</span></div>
    <p class="muted">Audited Brain/model conversation. Advice may be generated immediately; protected actions still require approval.</p>
    <div class="pet-conversation-meta" aria-label="Conversation capabilities">
      <span id="pet-chat-context">Session context · 0 messages</span>
      <span id="pet-voice-support">Checking browser voice support</span>
      <span id="pet-interruption-scope">Interruption · explicit controls; no automatic barge-in</span>
    </div>
    <p class="pet-voice-privacy"><strong>Voice privacy:</strong> Dictation starts only when you press Start dictation. Your browser or operating-system speech provider may process audio; this app does not intentionally store raw audio. Review the transcript before sending.</p>
    <div class="pet-action-help" aria-label="PET action commands">
      <strong>Governed actions</strong>
      <span>Use an explicit command; ${escapeHtml(personality.codename)} will show a confirmation before contacting the Brain or requesting a device capability.</span>
      <div>
        <button type="button" data-pet-command="/open ">Open URL</button>
        <button type="button" data-pet-command="/music play ">Play music</button>
        <button type="button" data-pet-command="/device ">Use device model</button>
        <button type="button" data-pet-command="/brain ">Message Brain</button>
      </div>
    </div>
    <div id="pet-chat-log" class="pet-chat-log" role="log" aria-live="off" aria-label="PET conversation transcript"></div>
    <form id="pet-chat-form" class="pet-chat-form">
      <label for="pet-chat-input">Message</label>
      <textarea id="pet-chat-input" name="message" rows="3" maxlength="4000" placeholder="Ask ${escapeHtml(personality.codename)} a question or request an explanation." required></textarea>
      <p id="pet-dictation-preview" class="pet-dictation-preview" hidden></p>
      <div class="pet-chat-actions">
        <button id="pet-chat-send" type="submit">Send to PET</button>
        <button id="pet-chat-dictate" type="button" aria-pressed="false">Start dictation</button>
        <button id="pet-chat-speak" type="button">Speak latest reply</button>
        <button id="pet-chat-stop" type="button" disabled>Stop voice</button>
        <button id="pet-chat-cancel" type="button" disabled>Cancel response</button>
        <button id="pet-chat-clear" type="button">Clear transcript</button>
      </div>
    </form>
    <p id="pet-chat-announcer" class="sr-only" role="status" aria-live="polite" aria-atomic="true"></p>`;
  workspace.insertBefore(section, feedGrid);
  renderChat();
  renderVoiceSupport();
}

function mountDeviceTools() {
  const workspace = $(".workspace");
  const feedGrid = $(".feed-grid");
  if (!workspace || !feedGrid || $("#pet-device-tools")) return;
  const personality = PERSONALITIES[state.machineId] || PERSONALITIES["dev-laptop"];
  const section = document.createElement("section");
  section.id = "pet-device-tools";
  section.className = "panel panel-pad pet-device-tools";
  section.setAttribute("data-audit", "governed-device-capabilities");
  section.innerHTML = `
    <div class="device-tools-heading"><div><p class="eyebrow">Machine-targeted tools</p><h2>${escapeHtml(personality.codename)} device controls</h2></div><span class="device-governance">Governed requests only</span></div>
    <p class="muted">These controls submit work to ${escapeHtml(state.machineId)}. Queued or approved is not the same as completed; only a device receipt can confirm execution.</p>
    <dl class="device-readiness" aria-label="Device capability readiness">
      <div><dt>Governed API</dt><dd id="device-api-ready">checking</dd></div>
      <div><dt>Node worker</dt><dd id="device-worker-ready">checking</dd></div>
      <div><dt>Browser executor</dt><dd id="device-browser-ready">unverified</dd></div>
      <div><dt>Music executor</dt><dd id="device-music-ready">unverified</dd></div>
      <div><dt>Hosted model</dt><dd id="device-model-ready">not reported</dd></div>
    </dl>
    <div class="device-tool-grid">
      <form id="device-browser-form" class="device-tool" novalidate>
        <h3>Open a URL locally</h3>
        <label for="device-browser-url">HTTP(S) URL</label>
        <input id="device-browser-url" type="url" inputmode="url" maxlength="2048" placeholder="https://example.com" required>
        <p id="device-url-validation" class="device-tool-note">Only HTTP(S), without embedded credentials. Approval is required.</p>
        <button type="submit">Request open URL</button>
      </form>
      <section class="device-tool" aria-labelledby="device-music-title">
        <h3 id="device-music-title">Local music session</h3>
        <label for="device-music-id">Local media ID for Play</label>
        <input id="device-music-id" maxlength="128" pattern="[A-Za-z0-9][A-Za-z0-9._:-]{0,127}" placeholder="focus-playlist">
        <p class="device-tool-note">Play requires a safe library ID—not a path or URL. No playback is claimed until the node reports completion.</p>
        <div class="device-music-actions"><button type="button" data-music-action="play">Request play</button><button type="button" data-music-action="pause">Request pause</button><button type="button" data-music-action="stop">Request stop</button></div>
      </section>
      <form id="device-model-form" class="device-tool">
        <h3>Chat with this device's model</h3>
        <label for="device-model-prompt">Local-model prompt</label>
        <textarea id="device-model-prompt" rows="3" maxlength="4000" placeholder="Ask the model hosted on this laptop…" required></textarea>
        <p class="device-tool-note">Queues the device-hosted model executor for this machine. No cloud route is requested.</p>
        <button type="submit">Queue local-model chat</button>
      </form>
    </div>
    <div id="device-action-receipt" class="device-action-receipt" role="status" aria-live="polite"><strong>No request submitted.</strong><span>Choose an explicit action above.</span></div>`;
  workspace.insertBefore(section, feedGrid);
}

function validateDeviceUrl(rawValue) {
  const value = String(rawValue || "").trim();
  if (!value || value.length > 2048 || /[\u0000-\u001f\u007f]/.test(value)) return { allowed: false, reason: "Enter a valid URL up to 2,048 characters." };
  let parsed;
  try { parsed = new URL(value); } catch { return { allowed: false, reason: "The URL could not be parsed." }; }
  const allowedSchemes = new Set((state.capabilityContracts?.browser?.allowed_schemes || ["https"]).map((scheme) => `${scheme}:`));
  if (!allowedSchemes.has(parsed.protocol)) return { allowed: false, reason: `Denied: allowed schemes are ${[...allowedSchemes].join(", ")}.` };
  if (parsed.username || parsed.password) return { allowed: false, reason: "Denied: URLs cannot contain embedded credentials." };
  if (!parsed.hostname) return { allowed: false, reason: "Denied: a destination host is required." };
  if (parsed.hash) return { allowed: false, reason: "Denied: URL fragments are not accepted by the governed contract." };
  const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
  if (host === "localhost" || host.endsWith(".local") || /^(?:10\.|127\.|169\.254\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)/.test(host)) return { allowed: false, reason: "Denied: local and private network targets are not allowed." };
  const allowedDomains = state.capabilityContracts?.browser?.allowed_domains || [];
  if (allowedDomains.length && !allowedDomains.some((domain) => host === domain || host.endsWith(`.${domain}`))) return { allowed: false, reason: "Denied: destination is outside the configured domain allowlist." };
  return { allowed: true, url: parsed.href, reason: "Validated HTTP(S) destination; Brain approval is still required." };
}

function showDeviceReceipt(title, detail, tone = "pending") {
  const receipt = $("#device-action-receipt");
  if (!receipt) return;
  receipt.dataset.tone = tone;
  receipt.innerHTML = `<strong>${escapeHtml(title)}</strong><span>${escapeHtml(detail)}</span>`;
}

function latestDeviceOperation(operationTypes) {
  return state.deviceCapabilityReceipts.find((item) => operationTypes.includes(item.capability_type));
}

function executorTruth(operationTypes) {
  const operation = latestDeviceOperation(operationTypes);
  if (!operation) return "unverified";
  if (operation.machine_receipt_id) return `machine receipt ${operation.machine_receipt_id}`;
  return `${operation.status} · request ${String(operation.request_id || "").slice(0, 8)}`;
}

function renderDeviceTools() {
  if (!$("#pet-device-tools")) return;
  const machine = currentMachine();
  const machineState = String(machine.state || "unknown").toLowerCase();
  $("#device-api-ready").textContent = state.apiConnected ? "request path online" : "offline";
  $("#device-worker-ready").textContent = machineState;
  $("#device-browser-ready").textContent = executorTruth(["browser_navigation"]);
  $("#device-music-ready").textContent = executorTruth(["music_playback"]);
  const reportedModel = String(machine.current_ai_model || machine.metadata?.current_ai_model || "").trim();
  const modelRequest = latestDeviceOperation(["device_model_chat"]);
  $("#device-model-ready").textContent = reportedModel || (modelRequest ? `${modelRequest.status} · request ${modelRequest.request_id.slice(0, 8)}` : state.capabilityContracts ? "contract ready; executor unverified" : "not reported");
}

async function submitMachineCapability(capabilityType, payload) {
  const petId = MACHINE_PET_IDS[state.machineId];
  if (!petId) throw new Error(`No governed PET identity is configured for ${state.machineId}.`);
  const receipt = await postJson("/pet-machine-capabilities/requests", {
    machine_id: state.machineId,
    pet_id: petId,
    capability_type: capabilityType,
    payload,
    requester: `${state.machineId}/mini-dashboard`,
    priority: capabilityType === "browser_navigation" ? 88 : 70,
  });
  state.deviceCapabilityReceipts.unshift(receipt);
  state.deviceCapabilityReceipts = state.deviceCapabilityReceipts.slice(0, 12);
  renderDeviceTools();
  return receipt;
}

async function submitBrowserUrl(event) {
  event.preventDefault();
  const input = $("#device-browser-url");
  const validation = validateDeviceUrl(input?.value);
  $("#device-url-validation").textContent = validation.reason;
  if (!validation.allowed) {
    showDeviceReceipt("URL request denied locally", validation.reason, "blocked");
    return;
  }
  showDeviceReceipt("Submitting browser request", "Waiting for a governed API receipt; the browser has not been opened.");
  try {
    const receipt = await submitMachineCapability("browser_navigation", { url: validation.url });
    showDeviceReceipt(`Browser request ${receipt.request_id}: ${receipt.status}`, `Approval #${receipt.approval_request_id || "required"}; success=${receipt.success_claimed}. Await a machine receipt.`, "pending");
  } catch (error) {
    showDeviceReceipt("Browser request failed", error.message, "blocked");
  }
}

async function submitMusicAction(action) {
  showDeviceReceipt(`Submitting music ${action}`, "Waiting for the governed API; no playback state is assumed.");
  try {
    const mediaId = String($("#device-music-id")?.value || "").trim();
    if (action === "play" && !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(mediaId)) throw new Error("Play requires a safe local media ID; paths and URLs are not accepted.");
    const payload = { command: action, ...(mediaId ? { media_id: mediaId } : {}) };
    const receipt = await submitMachineCapability("music_playback", payload);
    showDeviceReceipt(`Music ${action} request ${receipt.request_id}: ${receipt.status}`, `Approval #${receipt.approval_request_id || "required"}; success=${receipt.success_claimed}. Await a machine receipt.`, "pending");
  } catch (error) {
    showDeviceReceipt(`Music ${action} request failed`, error.message, "blocked");
  }
}

async function submitDeviceModelChat(event) {
  event.preventDefault();
  const input = $("#device-model-prompt");
  const prompt = String(input?.value || "").trim();
  if (!prompt) return;
  showDeviceReceipt("Queuing local-model session", "Targeting this machine with Ollama only; no response is claimed yet.");
  try {
    const receipt = await submitMachineCapability("device_model_chat", { prompt, model_id: "device-default" });
    input.value = "";
    showDeviceReceipt(`Local-model request ${receipt.request_id}: ${receipt.status}`, `Speaker #${receipt.speaker_message_id}; success=${receipt.success_claimed}. Await the laptop's model response and machine receipt.`, "pending");
  } catch (error) {
    showDeviceReceipt("Local-model session failed", error.message, "blocked");
  }
}

function saveChat() {
  state.chatHistory = state.chatHistory.slice(-30);
  sessionStorage.setItem(`aiops.${state.machineId}.petChat`, JSON.stringify(state.chatHistory));
}

function announceConversation(message) {
  const announcer = $("#pet-chat-announcer");
  if (announcer) announcer.textContent = message;
}

function recognitionConstructor() {
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

function renderVoiceSupport() {
  const voice = $("#pet-voice-support");
  const dictate = $("#pet-chat-dictate");
  const speak = $("#pet-chat-speak");
  const secureContext = window.isSecureContext === true;
  const permissionReady = state.microphonePermission !== "denied";
  const canListen = Boolean(recognitionConstructor()) && secureContext && permissionReady;
  const canSpeak = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  const dictationState = !secureContext ? "secure context required" : state.microphonePermission === "denied" ? "microphone denied" : canListen ? `dictation ready (${state.microphonePermission})` : "dictation unavailable";
  if (voice) voice.textContent = `Voice · ${dictationState} · ${canSpeak ? "playback ready" : "playback unavailable"}`;
  if (dictate) {
    dictate.disabled = !canListen;
    dictate.title = canListen ? "Transcribe microphone input into the message field" : !secureContext ? "Dictation requires a secure HTTPS browser context" : state.microphonePermission === "denied" ? "Microphone permission is denied; update browser site permissions or type instead" : "Speech recognition is not supported by this browser";
  }
  if (speak) {
    speak.disabled = !canSpeak;
    speak.title = canSpeak ? "Read the latest PET reply aloud" : "Speech playback is not supported by this browser";
  }
}

async function updateMicrophoneReadiness() {
  if (!window.isSecureContext) {
    state.microphonePermission = "unavailable";
    renderVoiceSupport();
    return;
  }
  if (!navigator.permissions?.query) {
    state.microphonePermission = "unknown";
    renderVoiceSupport();
    return;
  }
  try {
    const permission = await navigator.permissions.query({ name: "microphone" });
    state.microphonePermission = permission.state;
    permission.onchange = () => {
      state.microphonePermission = permission.state;
      renderVoiceSupport();
      announceConversation(`Microphone permission is now ${permission.state}.`);
    };
  } catch {
    state.microphonePermission = "unknown";
  }
  renderVoiceSupport();
}

function createModelRequestId() {
  const values = new Uint32Array(4);
  if (!window.crypto?.getRandomValues) throw new Error("Secure request identifiers are unavailable in this browser.");
  window.crypto.getRandomValues(values);
  return `pet_${Array.from(values, (value) => value.toString(16).padStart(8, "0")).join("")}`;
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
      ${entry.kind === "action-proposal" && entry.actionStatus === "proposed" ? `
        <div class="pet-chat-action-card" aria-label="Governed action proposal">
          <strong>Governed action proposal</strong>
          <dl><div><dt>Target</dt><dd>${escapeHtml(entry.actionTarget || state.machineId)}</dd></div><div><dt>Action</dt><dd>${escapeHtml(entry.actionType || "request")}</dd></div><div><dt>Approval</dt><dd>Awaiting your confirmation</dd></div></dl>
        </div>
        <div class="pet-chat-action-confirm" aria-label="Confirm governed action">
          <button type="button" data-chat-action-confirm="${escapeHtml(entry.actionId)}">Confirm request</button>
          <button type="button" data-chat-action-cancel="${escapeHtml(entry.actionId)}">Cancel</button>
        </div>` : ""}
    </article>`).join("") || "<p class=\"muted\">No messages yet. Your PET is listening.</p>";
  log.scrollTop = log.scrollHeight;
  const context = $("#pet-chat-context");
  if (context) context.textContent = `Session context · ${state.chatHistory.length} message${state.chatHistory.length === 1 ? "" : "s"}`;
}

function detectPetConversationAction(message) {
  const value = String(message || "").trim();
  const rules = [
    { pattern: /^\/open\s+(.+)$/i, type: "browser_navigation", label: (match) => `Open ${match[1]} on this node through the governed browser capability.` },
    { pattern: /^\/(?:music)\s+(play|pause|stop)(?:\s+(.+))?$/i, type: "music_playback", label: (match) => `${match[1].toLowerCase()} the node's local music session${match[2] ? ` using media ID ${match[2]}` : ""}.` },
    { pattern: /^\/(?:device|local-model)\s+(.+)$/i, type: "device_model_chat", label: () => "Send this prompt to the model hosted on this node." },
    { pattern: /^\/brain\s+(.+)$/i, type: "brain_message", target: "Brain listener bus", label: () => "Publish this message to the Brain listener bus." },
    { pattern: /^(?:open|navigate to|browse to)\s+(https?:\/\/\S+)$/i, type: "browser_navigation", label: (match) => `Open ${match[1]} on this node through the governed browser capability.` },
    { pattern: /^(play|pause|stop)\s+music(?:\s+([A-Za-z0-9][A-Za-z0-9._:-]{0,127}))?$/i, type: "music_playback", label: (match) => `${match[1].toLowerCase()} the node's local music session${match[2] ? ` using media ID ${match[2]}` : ""}.` },
    { pattern: /^(?:message|tell|send to)\s+(?:the\s+)?brain\s*[:,-]?\s+(.+)$/i, type: "brain_message", target: "Brain listener bus", label: () => "Publish this message to the Brain listener bus." },
  ];
  for (const rule of rules) {
    const match = value.match(rule.pattern);
    if (match) return { message: value, summary: rule.label(match), type: rule.type, target: rule.target || state.machineId };
  }
  const lower = value.toLowerCase();
  const asksForBrowser = /(?:open|launch|use|test).{0,40}(?:web )?browser|(?:go|navigate|browse).{0,20}(?:youtube(?:\.com)?|https?:\/\/)/i.test(value);
  const asksForPlayback = /(?:play|listen to|put on)\s+.+/i.test(value);
  if (asksForBrowser && asksForPlayback) {
    return {
      message: value,
      type: "multi_action",
      target: state.machineId,
      summary: "Propose governed browser navigation or search, plus local music control only if the Brain resolves an approved local media ID. Browser navigation does not prove YouTube playback.",
    };
  }
  if (asksForBrowser) return { message: value, type: "browser_navigation", target: state.machineId, summary: "Propose governed browser navigation. Opening a page does not prove media playback." };
  if (/(?:what|which|list|show|tell me).{0,35}music.{0,25}(?:available|library|catalog|have)|music.{0,20}(?:available|library|catalog)/i.test(value)) {
    return { message: value, type: "music_catalog", target: state.machineId, summary: "Ask the governed node workflow to report which local music IDs are available; no playback is requested." };
  }
  if (/(?:send|submit|make|create|forward).{0,35}(?:request|message).{0,30}(?:to|over to)\s+(?:the\s+)?brain/i.test(lower)) {
    return { message: value, type: "brain_message", target: "Brain listener bus", summary: "Propose publishing this request to the Brain listener bus." };
  }
  return null;
}

function conversationActionReceipt(response) {
  const summary = String(response?.summary || "The governed action request was recorded.").trim();
  const status = String(response?.status || "recorded").trim();
  const capabilityReceipts = Array.isArray(response?.capability_requests) ? response.capability_requests : [];
  const capabilityDetails = capabilityReceipts.map((receipt) => {
    const requestId = receipt?.request_id || receipt?.id || "pending";
    const approval = receipt?.approval_request_id ? `, approval #${receipt.approval_request_id}` : "";
    return `${receipt?.capability_type || response?.action_type || "capability"} request ${requestId}: ${receipt?.status || status}${approval}`;
  });
  const brainMessage = response?.brain_message;
  const brainDetail = brainMessage ? `Brain message ${brainMessage.id || brainMessage.event_id || brainMessage.listener_event_id || "recorded"}.` : "";
  const truth = response?.success_claimed === true
    ? "The endpoint reported completion."
    : "No device execution is claimed until an authoritative machine receipt reports completion.";
  return [summary, `Status: ${status}.`, ...capabilityDetails, brainDetail, truth].filter(Boolean).join(" ");
}

async function requestPetModelReply(message, personality) {
  let requestId;
  try {
    requestId = createModelRequestId();
  } catch (error) {
    state.chatHistory.push({ role: "pet", text: error.message, name: personality.codename, timestamp: Date.now() });
    return;
  }
  state.chatSending = true;
  state.chatAbortController = new AbortController();
  state.chatRequestId = requestId;
  $("#pet-chat-send").disabled = true;
  $("#pet-chat-cancel").disabled = false;
  $("#pet-chat-state").textContent = `${personality.codename} is thinking`;
  try {
    const conversationHistory = state.chatHistory.slice(-11, -1).map((entry) => ({
      role: entry.role,
      content: String(entry.text || "").slice(0, 800),
    }));
    const response = await postJson("/models/query", {
      purpose: `Governed PET conversation with ${personality.codename}`,
      prompt: `Protected, financial, destructive, credential, or external-control requests are advisory only and must not create work automatically. User message: ${message}`,
      requester: state.machineId,
      target_id: state.machineId,
      priority: 65,
      auto_create_tasks: false,
      require_approval: false,
      options: { max_tokens: 420, interaction: "pet_chat", pet: personality.codename, conversation_history: conversationHistory },
      request_id: requestId,
    }, { signal: state.chatAbortController.signal });
    const reply = String(response.synthesized_response || "I recorded your message, but no model response was available.").trim();
    state.chatHistory.push({ role: "pet", text: reply, name: personality.codename, timestamp: Date.now() });
    $("#pet-chat-state").textContent = response.risk_level ? `Ready · ${response.risk_level} risk` : "Ready";
  } catch (error) {
    if (error.name === "AbortError") {
      $("#pet-chat-state").textContent = "Response cancelled · context kept";
    } else {
      state.chatHistory.push({ role: "pet", text: `I could not reach the Brain model workflow: ${error.message}`, name: personality.codename, timestamp: Date.now() });
      $("#pet-chat-state").textContent = "Connection attention";
    }
  } finally {
    state.chatSending = false;
    state.chatAbortController = null;
    state.chatRequestId = null;
    $("#pet-chat-send").disabled = false;
    $("#pet-chat-cancel").disabled = true;
    saveChat();
    renderChat();
  }
}

async function submitPetConversationAction(actionId) {
  const entry = state.chatHistory.find((item) => item.actionId === actionId && item.actionStatus === "proposed");
  if (!entry || state.chatSending) return;
  const personality = PERSONALITIES[state.machineId] || PERSONALITIES["dev-laptop"];
  const petId = MACHINE_PET_IDS[state.machineId];
  if (!petId) {
    entry.actionStatus = "failed";
    entry.text = `Action blocked: no governed PET identity is configured for ${state.machineId}.`;
    renderChat();
    return;
  }
  entry.actionStatus = "submitting";
  entry.text = "Submitting the confirmed action to the Brain governance workflow. No execution is claimed yet.";
  state.chatSending = true;
  $("#pet-chat-send").disabled = true;
  $("#pet-chat-state").textContent = "Submitting governed action";
  saveChat();
  renderChat();
  try {
    const response = await postJson(`/pet-action-proposals/${encodeURIComponent(entry.proposalId)}/confirm`, {
      confirmed_by: `${state.machineId}/mini-dashboard-chat`,
    });
    if (response?.handled === false) {
      entry.actionStatus = "not-handled";
      entry.text = "No governed action matched that request, so I am treating it as a normal PET question.";
      state.chatSending = false;
      saveChat();
      renderChat();
      await requestPetModelReply(entry.actionMessage, personality);
      return;
    }
    entry.actionStatus = "submitted";
    entry.text = conversationActionReceipt(response);
    $("#pet-chat-state").textContent = `${response?.action_type || "Action"} · ${response?.status || "recorded"}`;
    announceConversation(entry.text);
    await refreshAll();
  } catch (error) {
    entry.actionStatus = "failed";
    entry.text = `The governed action request failed before a receipt was returned: ${error.message}`;
    $("#pet-chat-state").textContent = "Action request attention";
  } finally {
    state.chatSending = false;
    $("#pet-chat-send").disabled = false;
    saveChat();
    renderChat();
  }
}

async function requestPetActionProposal(message, personality, detectedAction) {
  const petId = MACHINE_PET_IDS[state.machineId];
  if (!petId) {
    state.chatHistory.push({ role: "pet", text: `Action blocked: no governed PET identity is configured for ${state.machineId}.`, name: personality.codename, timestamp: Date.now() });
    saveChat();
    renderChat();
    return;
  }
  state.chatSending = true;
  $("#pet-chat-send").disabled = true;
  $("#pet-chat-state").textContent = "Preparing governed action proposal";
  try {
    const response = await postJson("/pet-action-proposals", {
      machine_id: state.machineId,
      pet_id: petId,
      message,
      requester: `${state.machineId}/mini-dashboard-chat`,
      priority: 82,
    });
    if (response?.handled === false) {
      state.chatSending = false;
      await requestPetModelReply(message, personality);
      return;
    }
    if (!response?.proposal_id) throw new Error("The Brain did not return a proposal identifier.");
    state.chatHistory.push({
      role: "pet",
      kind: "action-proposal",
      actionId: String(response.proposal_id),
      proposalId: String(response.proposal_id),
      actionMessage: message,
      actionTarget: detectedAction.target,
      actionType: response.action_type || detectedAction.type,
      actionStatus: "proposed",
      text: `${response.summary || detectedAction.summary} Confirm to submit the normalized action, or cancel. Nothing has been sent yet. This is a proposal only; no capability request or Brain message has been issued.`,
      name: personality.codename,
      timestamp: Date.now(),
    });
    $("#pet-chat-state").textContent = "Action confirmation required";
  } catch (error) {
    state.chatHistory.push({ role: "pet", text: `I could not prepare the governed action proposal: ${error.message}`, name: personality.codename, timestamp: Date.now() });
    $("#pet-chat-state").textContent = "Action proposal attention";
  } finally {
    state.chatSending = false;
    $("#pet-chat-send").disabled = false;
    saveChat();
    renderChat();
  }
}

function cancelPetConversationAction(actionId) {
  const entry = state.chatHistory.find((item) => item.actionId === actionId && item.actionStatus === "proposed");
  if (!entry) return;
  entry.actionStatus = "cancelled";
  entry.text = "Action cancelled. Nothing was submitted to the Brain or node.";
  $("#pet-chat-state").textContent = "Action cancelled · ready";
  saveChat();
  renderChat();
  announceConversation(entry.text);
}

function speakText(text) {
  if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window) || !text) {
    announceConversation("Speech playback is unavailable in this browser.");
    return;
  }
  stopVoice("Previous playback interrupted.", false);
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.pitch = 1.05;
  utterance.onstart = () => {
    state.isSpeaking = true;
    $("#pet-chat-stop").disabled = false;
    $("#pet-chat-state").textContent = "Speaking";
    announceConversation("PET reply playback started.");
  };
  utterance.onend = () => {
    state.isSpeaking = false;
    $("#pet-chat-stop").disabled = !state.isListening;
    $("#pet-chat-state").textContent = "Ready";
    announceConversation("PET reply playback finished.");
  };
  utterance.onerror = () => {
    state.isSpeaking = false;
    $("#pet-chat-stop").disabled = !state.isListening;
    $("#pet-chat-state").textContent = "Voice attention";
    announceConversation("Speech playback stopped unexpectedly.");
  };
  window.speechSynthesis.speak(utterance);
}

function stopVoice(message = "Voice interaction stopped.", shouldAnnounce = true) {
  if (state.recognition) {
    try { state.recognition.stop(); } catch { /* already stopped */ }
  }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
  const wasActive = state.isListening || state.isSpeaking;
  state.isListening = false;
  state.isSpeaking = false;
  state.recognition = null;
  const dictate = $("#pet-chat-dictate");
  if (dictate) {
    dictate.setAttribute("aria-pressed", "false");
    dictate.textContent = "Start dictation";
  }
  if ($("#pet-chat-stop")) $("#pet-chat-stop").disabled = true;
  if (wasActive && $("#pet-chat-state")) $("#pet-chat-state").textContent = "Interrupted · ready";
  if (shouldAnnounce && wasActive) announceConversation(message);
}

function startDictation() {
  const Recognition = recognitionConstructor();
  if (!Recognition) {
    announceConversation("Dictation is unavailable. Type your message instead.");
    return;
  }
  if (state.isListening) {
    stopVoice("Dictation stopped. Your transcript remains in the message field.");
    return;
  }
  stopVoice("Playback interrupted for dictation.", false);
  const recognition = new Recognition();
  const input = $("#pet-chat-input");
  const preview = $("#pet-dictation-preview");
  const original = String(input?.value || "").trim();
  const recognizedSegments = [];
  recognition.lang = document.documentElement.lang || navigator.language || "en-US";
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.onstart = () => {
    state.recognition = recognition;
    state.isListening = true;
    $("#pet-chat-dictate").setAttribute("aria-pressed", "true");
    $("#pet-chat-dictate").textContent = "Stop dictation";
    $("#pet-chat-stop").disabled = false;
    $("#pet-chat-state").textContent = "Listening";
    if (preview) { preview.hidden = false; preview.textContent = "Listening…"; }
    announceConversation("Dictation started. Speak now.");
  };
  recognition.onresult = (event) => {
    for (let index = event.resultIndex; index < event.results.length; index += 1) recognizedSegments[index] = event.results[index][0].transcript;
    const transcript = recognizedSegments.join(" ").replace(/\s+/g, " ").trim();
    if (input) input.value = [original, transcript.trim()].filter(Boolean).join(original ? " " : "");
    if (preview) preview.textContent = transcript.trim() || "Listening…";
  };
  recognition.onerror = (event) => {
    const denied = ["not-allowed", "service-not-allowed"].includes(event.error);
    stopVoice("", false);
    $("#pet-chat-state").textContent = denied ? "Microphone permission needed" : "Dictation attention";
    announceConversation(denied ? "Microphone access was not granted. Type your message instead." : `Dictation stopped: ${event.error || "unknown error"}.`);
  };
  recognition.onend = () => {
    state.isListening = false;
    state.recognition = null;
    $("#pet-chat-dictate").setAttribute("aria-pressed", "false");
    $("#pet-chat-dictate").textContent = "Start dictation";
    $("#pet-chat-stop").disabled = !state.isSpeaking;
    if (preview) preview.hidden = true;
    if ($("#pet-chat-state").textContent === "Listening") $("#pet-chat-state").textContent = "Transcript ready";
    announceConversation("Dictation ended. Review the transcript before sending.");
  };
  try { recognition.start(); } catch {
    announceConversation("Dictation could not start. Type your message instead.");
  }
}

async function cancelPetResponse() {
  if (!state.chatAbortController) return;
  const requestId = state.chatRequestId;
  const stopRequest = requestId
    ? postJson(`/models/query/${encodeURIComponent(requestId)}/cancel`, {}).catch(() => null)
    : Promise.resolve(null);
  state.chatAbortController.abort();
  const stopReceipt = await stopRequest;
  const serverScope = stopReceipt?.cancellation_requested ? "Request-scoped stop sent; provider completion is not guaranteed." : "Browser wait dismissed; upstream completion is unknown.";
  $("#pet-chat-state").textContent = "Response dismissed · context kept";
  announceConversation(`${serverScope} Your conversation context is preserved.`);
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
  const pendingAction = [...state.chatHistory].reverse().find((entry) => entry.kind === "action-proposal" && entry.actionStatus === "proposed");
  if (pendingAction && /^(?:yes|confirm|approve|do it|proceed)$/i.test(message)) {
    saveChat();
    renderChat();
    await submitPetConversationAction(pendingAction.actionId);
    return;
  }
  if (pendingAction && /^(?:no|cancel|never mind|nevermind)$/i.test(message)) {
    cancelPetConversationAction(pendingAction.actionId);
    return;
  }
  const action = detectPetConversationAction(message);
  if (action) {
    saveChat();
    renderChat();
    await requestPetActionProposal(message, personality, action);
    return;
  }
  saveChat();
  renderChat();
  await requestPetModelReply(message, personality);
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

async function requestRemoteOperation(operationType, summary, metadata = {}) {
  const response = await postJson("/remote-ops", {
    machine_id: state.machineId,
    requested_by: `${state.machineId}/mini-dashboard`,
    operation_type: operationType,
    command_summary: summary,
    priority: operationType === "open_mini_dashboard" ? 72 : 88,
    metadata: { requested_from: "mini-dashboard", pet: state.pet, approval_expected: operationType !== "open_mini_dashboard", ...metadata },
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
  return response;
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
      getJson("/collaboration"),
      getJson("/pet-machine-capabilities/contracts"),
    ]);
    const values = results.map((result) => result.status === "fulfilled" ? result.value : null);
    const [tasks, speaker, noc, readiness, approvals, remoteOps, collaboration, capabilityContracts] = values;
    if (tasks) state.tasks = (tasks.tasks || []).filter((task) => task.machine_id === state.machineId);
    if (speaker) state.messages = speaker.messages || [];
    if (noc) state.noc = noc;
    state.readinessAvailable = Boolean(readiness);
    if (readiness) {
      state.readiness = readiness;
      state.readinessObservedAt = Date.now();
    }
    if (approvals) state.approvals = approvals.approvals || [];
    if (remoteOps) state.remoteOps = remoteOps.requests || [];
    if (collaboration) state.collaboration = collaboration;
    if (capabilityContracts) state.capabilityContracts = capabilityContracts;
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
  renderDeviceTools();
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
    const confirm = event.target.closest("[data-chat-action-confirm]");
    if (confirm) { submitPetConversationAction(confirm.dataset.chatActionConfirm); return; }
    const cancel = event.target.closest("[data-chat-action-cancel]");
    if (cancel) { cancelPetConversationAction(cancel.dataset.chatActionCancel); return; }
    const button = event.target.closest("[data-chat-speak]");
    if (button) speakText(button.dataset.chatSpeak);
  });
  document.querySelectorAll("[data-pet-command]").forEach((button) => button.addEventListener("click", () => {
    const input = $("#pet-chat-input");
    input.value = button.dataset.petCommand;
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    announceConversation(`${button.textContent} command inserted. Complete it, then send to review the action proposal.`);
  }));
  $("#pet-chat-speak").addEventListener("click", () => speakText([...state.chatHistory].reverse().find((entry) => entry.role === "pet")?.text));
  $("#pet-chat-dictate").addEventListener("click", startDictation);
  $("#pet-chat-stop").addEventListener("click", () => stopVoice());
  $("#pet-chat-cancel").addEventListener("click", cancelPetResponse);
  $("#pet-chat-clear").addEventListener("click", () => { stopVoice("", false); cancelPetResponse(); state.chatHistory = []; saveChat(); renderChat(); $("#pet-chat-state").textContent = "Ready"; announceConversation("Conversation transcript and session context cleared."); });
  $("#pet-chat-input").addEventListener("keydown", (event) => {
    if (event.key === "Escape") { stopVoice(); cancelPetResponse(); }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") $("#pet-chat-form").requestSubmit();
  });
  $("#device-browser-form").addEventListener("submit", submitBrowserUrl);
  $("#device-model-form").addEventListener("submit", submitDeviceModelChat);
  document.querySelectorAll("[data-music-action]").forEach((button) => button.addEventListener("click", () => submitMusicAction(button.dataset.musicAction)));
}

window.addEventListener("DOMContentLoaded", () => {
  mountShield();
  mountConversation();
  mountDeviceTools();
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
  updateMicrophoneReadiness();
  renderCapabilityProfile();
  refreshAll();
  setInterval(refreshAll, 5000);
  window.addEventListener("pagehide", () => stopVoice("", false));
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refreshAll();
  });
  setInterval(() => {
    state.animationTick += 1;
    renderPet();
  }, 1200);
});
