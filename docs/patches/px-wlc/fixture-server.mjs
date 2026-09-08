// Local visual verification ONLY. Never deploy this fixture with the app.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
const port = Number(process.env.PX_FIXTURE_PORT || 4178);
const roots = {
  enabled: resolve(process.env.PX_ENABLED_DIST || "/tmp/px-wlc-enabled-dist"),
  disabled: resolve(
    process.env.PX_DISABLED_DIST || "/tmp/px-wlc-disabled-dist",
  ),
  baseline: resolve(
    process.env.PX_BASELINE_DIST || "/tmp/px-wlc-baseline-dist",
  ),
};
let mode = "enabled";
let approved = false;
let requestFails = false;
const settings = {
  instance_name: "LIBERATOR",
  header_tagline: "Empowering Families of Political Prisoners",
  primary_color: "#7d3e9b",
  typography_preset: "humanist",
  default_theme: "system",
  surface_style: "gradient",
  header_layout: "icon_name",
  logo_url: "",
  favicon_url: "",
};
const user = () => ({
  email: "px-test@example.test",
  name: "PX Test",
  approved,
  needs_onboarding: false,
  needs_user_type: false,
  user_type_id: null,
});
const requests = [];
const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  const json = (data, status = 200) => {
    res.writeHead(status, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    res.end(JSON.stringify(data));
  };
  if (url.pathname === "/__fixture") {
    if (url.searchParams.has("mode"))
      mode = Object.hasOwn(roots, url.searchParams.get("mode"))
        ? url.searchParams.get("mode")
        : mode;
    if (url.searchParams.has("approved"))
      approved = url.searchParams.get("approved") === "true";
    if (url.searchParams.has("fail"))
      requestFails = url.searchParams.get("fail") === "true";
    return json({ mode, approved, requestFails, requests });
  }
  if (url.pathname.startsWith("/api/")) {
    let body = "";
    for await (const chunk of req) body += chunk;
    requests.push({ method: req.method, path: url.pathname });
    const path = url.pathname.slice(4);
    if (path === "/settings/public") return json({ settings });
    if (path === "/instance/status")
      return json({
        initialized: true,
        setup_complete: true,
        ready_for_users: true,
      });
    if (path === "/auth/magic-link")
      return json(
        requestFails
          ? { detail: "Fixture: please try again." }
          : { success: true },
        requestFails ? 503 : 200,
      );
    if (path === "/auth/verify")
      return body.includes("expired")
        ? json({ detail: "This link has expired." }, 400)
        : json({ user: user() });
    if (path === "/auth/me") return json({ authenticated: true, user: user() });
    if (path === "/users/me/onboarding-status")
      return json({
        approved,
        needs_onboarding: false,
        needs_user_type: false,
        user_type_id: null,
      });
    if (path === "/user-types")
      return json({
        types: [
          {
            id: 1,
            name: "Member",
            description: "Fixture member",
            icon: "User",
          },
          {
            id: 2,
            name: "Supporter",
            description: "Fixture supporter",
            icon: "Users",
          },
        ],
      });
    if (path === "/user-fields")
      return json({
        fields: [
          {
            id: 1,
            field_name: "Preferred name",
            field_type: "text",
            required: true,
          },
        ],
      });
    if (path === "/query/sessions") return json({ sessions: [] });
    if (path === "/session-defaults") return json({});
    if (path === "/users" && req.method === "POST")
      return json({ success: true });
    if (path === "/auth/logout") return json({ success: true });
    return json({ detail: `Unmocked fixture route: ${path}` }, 404);
  }
  try {
    const root = roots[mode];
    const pathname = decodeURIComponent(url.pathname);
    const file = resolve(root, "." + pathname);
    if (!file.startsWith(root + sep) && file !== root) return json({}, 403);
    let data;
    let type = {
      ".html": "text/html",
      ".js": "text/javascript",
      ".css": "text/css",
      ".svg": "image/svg+xml",
    }[extname(file)];
    if (type) data = await readFile(file);
    else {
      data = await readFile(resolve(root, "index.html"));
      type = "text/html";
    }
    res.writeHead(200, { "Content-Type": type, "Cache-Control": "no-store" });
    res.end(data);
  } catch {
    json({ detail: "Fixture file missing" }, 404);
  }
});
server.listen(port, "127.0.0.1", () =>
  console.log(`PX fixture: http://127.0.0.1:${port} (${mode})`),
);
