(() => {
  const script = document.currentScript;
  if (!script) return;
  const api = (script.dataset.api || new URL("/api", script.src).origin + "/api").replace(/\/$/, "");
  const project = encodeURIComponent(script.dataset.project || "demo");
  const button = document.createElement("button");
  button.textContent = "Share feedback";
  button.setAttribute("aria-label", "Share product feedback");
  Object.assign(button.style, { position: "fixed", right: "24px", bottom: "24px", zIndex: 2147483000, border: 0, borderRadius: "999px", padding: "13px 19px", background: "#223b32", color: "white", font: "600 14px system-ui", cursor: "pointer", boxShadow: "0 8px 28px #183a2c33" });
  const panel = document.createElement("form");
  panel.hidden = true;
  Object.assign(panel.style, { position: "fixed", right: "24px", bottom: "82px", zIndex: 2147483000, width: "min(340px, calc(100vw - 48px))", padding: "20px", borderRadius: "18px", background: "#fff", color: "#26332d", boxShadow: "0 14px 48px #183a2c29", font: "14px system-ui", boxSizing: "border-box" });
  panel.innerHTML = '<label style="display:block;font-weight:650;font-size:18px;margin-bottom:8px">What could be better?</label><textarea required minlength="3" maxlength="5000" rows="5" placeholder="Tell us what happened…" style="box-sizing:border-box;width:100%;resize:vertical;border:1px solid #dbe2dc;border-radius:10px;padding:11px;font:inherit"></textarea><label style="display:block;margin:12px 0 8px">Category <select style="margin-left:8px;padding:6px;border:1px solid #dbe2dc;border-radius:8px"><option value="general">General</option><option value="bug">Bug</option><option value="feature">Feature idea</option><option value="usability">Usability</option></select></label><label style="display:flex;gap:8px;align-items:center;font-size:12px;color:#64716a"><input type="checkbox"> Include this page path</label><p role="status" style="min-height:18px;color:#64716a;font-size:12px"></p><button type="submit" style="width:100%;border:0;border-radius:9px;padding:11px;background:#31634d;color:white;font:600 14px system-ui;cursor:pointer">Send feedback</button>';
  document.body.append(button, panel);
  button.addEventListener("click", () => { panel.hidden = !panel.hidden; });
  panel.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = panel.querySelector('button[type="submit"]');
    const status = panel.querySelector('[role="status"]');
    if (submit.disabled) return;
    submit.disabled = true;
    submit.textContent = "Sending…";
    status.textContent = "";
    const keyName = `feedbackflow:${project}:submission`;
    let externalKey = sessionStorage.getItem(keyName);
    if (!externalKey || sessionStorage.getItem(`${keyName}:sent`)) {
      // A fresh key per new submission; retries of a failed send reuse it so the server can deduplicate.
      externalKey = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
      sessionStorage.setItem(keyName, externalKey);
      sessionStorage.removeItem(`${keyName}:sent`);
    }
    try {
      const response = await fetch(`${api}/public/${project}/feedback`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: panel.querySelector("textarea").value, category: panel.querySelector("select").value, page_path: panel.querySelector("input[type=checkbox]").checked ? window.location.pathname : null, external_key: externalKey }) });
      if (response.status === 429) throw new Error("You're sending feedback quickly — please wait a moment and try again.");
      if (!response.ok) throw new Error("We couldn't send that yet. Please try again.");
      sessionStorage.setItem(`${keyName}:sent`, "1");
      status.textContent = "Thanks — your feedback was received.";
      panel.reset();
      setTimeout(() => { panel.hidden = true; }, 1400);
    } catch (error) {
      status.textContent = error.message || "Network error. Please try again.";
    } finally {
      submit.disabled = false;
      submit.textContent = "Send feedback";
    }
  });
})();
