from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
STYLE = (ROOT / "dashboard" / "styles.css").read_text(encoding="utf-8")
MINI_DASHBOARD = (ROOT / "laptop_packages" / "shared" / "mini-dashboard.js").read_text(encoding="utf-8")


def test_main_dashboard_maps_each_node_card_to_its_mini_dashboard():
    assert '"dev-laptop": "/laptop-packages/dev-laptop/index.html"' in DASHBOARD
    assert '"research-laptop": "/laptop-packages/research-laptop/index.html"' in DASHBOARD
    assert '"business-laptop": "/laptop-packages/business-laptop/index.html"' in DASHBOARD
    assert "data-pet-dashboard-popout" in DASHBOARD
    assert "dashboard-popout" not in MINI_DASHBOARD


def test_button_requires_fresh_exact_online_readiness_and_nonstale_ssh():
    assert "function petNodeIsFullyOnline(readiness)" in DASHBOARD
    assert "Date.now() - state.readinessObservedAt < 45000" in DASHBOARD
    assert 'String(readiness.state || "unknown").toLowerCase() === "online"' in DASHBOARD
    assert '["ssh-22", "ssh-22-brain-to-laptop"].includes(connection.channel)' in DASHBOARD
    assert 'String(connection.status || "").toLowerCase() === "online"' in DASHBOARD
    assert "connection.is_stale !== true" in DASHBOARD
    assert 'pet.dashboardReady ? "" : "hidden disabled"' in DASHBOARD


def test_popout_reuses_named_window_and_reports_blocking_accessibly():
    assert "const dashboardOrigin = API_BASE || window.location.origin" in DASHBOARD
    assert 'new URL(dashboardPath, `${dashboardOrigin.replace(/\\/$/, "")}/`)' in DASHBOARD
    assert "state.petDashboardPopouts.get(machineId)" in DASHBOARD
    assert "window.open(target.href, windowName" in DASHBOARD
    assert "existing.focus()" in DASHBOARD
    assert "The browser blocked this pop-out." in DASHBOARD
    assert 'role="status" aria-live="polite"' in DASHBOARD
    assert ".pet-dashboard-popout" in STYLE
