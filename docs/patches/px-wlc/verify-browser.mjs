// Run against fixture-server.mjs only. See README for isolated Playwright setup.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const require = createRequire(
  resolve(
    process.env.PX_BROWSER_TOOLS || "/tmp/px-wlc-browser-tools",
    "package.json",
  ),
);
const { chromium } = require("playwright");
const base = "http://127.0.0.1:4178";
const out = resolve("docs/patches/px-wlc/screenshots");
await mkdir(out, { recursive: true });
const fixture = async (query) =>
  (await fetch(`${base}/__fixture?${query}`)).json();
await fixture("mode=enabled&approved=false&fail=false");
const browser = await chromium.launch({
  executablePath: process.env.PX_BROWSER_EXECUTABLE,
  headless: true,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  colorScheme: "light",
  reducedMotion: "reduce",
});
const page = await context.newPage();
page.setDefaultTimeout(10000);
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const checks = [];
const check = (name) => {
  checks.push(name);
  console.log(`PASS ${name}`);
};
const shot = async (name) => {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(resolve)),
    );
  });
  await page.screenshot({
    path: resolve(out, `${name}.png`),
    fullPage: true,
    animations: "disabled",
  });
};
const noOverflow = async () =>
  assert.equal(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    true,
  );
const go = async (path) => {
  await page.goto(base + path);
  await page.waitForSelector(".px-brand, h1, h2");
};
try {
  await go("/");
  await page
    .getByRole("radio", { name: "English (English)", exact: true })
    .waitFor();
  await page.waitForFunction(() =>
    document.body.textContent.includes("Empowering Families"),
  );
  assert.equal(await page.title(), "PX");
  assert.equal(await page.locator(".px-welcome").count(), 1);
  await noOverflow();
  await page.keyboard.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement?.tagName), "A");
  check("Keyboard focus reaches PX link");
  await shot("after-language-desktop");
  await page
    .getByRole("radio", { name: "English (English)", exact: true })
    .click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.waitForURL("**/auth");
  await shot("after-signup-desktop");
  check("Fresh visitor language selection reaches existing signup");
  await page.reload();
  await page.waitForSelector('input[type="email"]');
  await go("/login");
  await page.waitForURL("**/auth");
  check(
    "Explicit language choice survives reload and skips language selection",
  );
  await page.getByRole("button", { name: "Log In", exact: true }).click();
  assert.equal(await page.locator('input[type="text"]').count(), 0);
  await page.getByRole("button", { name: "Sign Up", exact: true }).click();
  await page.locator('input[type="text"]').fill("PX Test");
  await page.locator('input[type="email"]').fill("px-test@example.test");
  await fixture("fail=true");
  await page
    .getByRole("button", { name: "Continue with Email", exact: true })
    .click();
  await page.getByText("Fixture: please try again.").waitFor();
  await fixture("fail=false");
  await page
    .getByRole("button", { name: "Continue with Email", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Check your email!", exact: true })
    .waitFor();
  await shot("after-email-sent");
  check(
    "Signup/login tabs, request failure, retry, and sent state (fixture only)",
  );
  await go("/verify?token=expired");
  await page.getByRole("heading", { name: /link expired/i }).waitFor();
  await shot("after-expired-link");
  await go("/verify?token=fixture-valid");
  await page.waitForURL("**/pending", { timeout: 15000 });
  await shot("after-pending");
  check("Expired link and valid link through pending approval");
  await fixture("approved=true");
  await page.reload();
  await page.waitForURL("**/chat");
  await page
    .getByRole("button", { name: "Toggle theme", exact: true })
    .waitFor();
  await shot("after-chat-light");
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click();
  await page.waitForFunction(
    () =>
      document.documentElement.classList.contains("dark") &&
      getComputedStyle(document.body)
        .getPropertyValue("--color-surface")
        .trim() === "#0b1e29",
  );
  await shot("after-chat-dark");
  check("Approved User reaches chat and theme toggle works");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await shot("after-settings-dark");
  check("Settings remains accessible");
  await go("/user-type");
  await page.getByRole("radio").first().click();
  await shot("after-user-type");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.waitForURL("**/profile");
  await page.getByRole("textbox").first().fill("PX Test");
  await shot("after-profile");
  await page.getByRole("button", { name: /continue|save|complete/i }).click();
  await page.waitForURL("**/chat");
  check("User Type and profile form remain usable through completion");
  await go("/auth");
  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow();
  await shot("after-signup-mobile-dark");
  await page.evaluate(() => {
    localStorage.setItem("enclave-theme", "light");
  });
  await page.reload();
  await page.waitForSelector('input[type="email"]');
  await noOverflow();
  await shot("after-signup-mobile-light");
  await page.evaluate(() => {
    localStorage.setItem("enclave_language", "ar");
    localStorage.setItem("enclave_language_explicit", "1");
  });
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dir === "rtl");
  await noOverflow();
  await shot("after-signup-mobile-rtl");
  check("Mobile light/dark and Arabic RTL fit without horizontal overflow");
  await page.evaluate(() => {
    localStorage.setItem("enclave_language", "en");
    localStorage.setItem("enclave_language_explicit", "1");
  });
  await go("/admin");
  await shot("after-admin-mobile");
  check("Admin entry still renders");
  const before = await page.evaluate(() => ({ ...localStorage }));
  const stored = JSON.parse(before.enclave_instance_config);
  assert.equal(stored.name, "PX");
  assert.equal(stored.primaryColor, "#7d3e9b");
  assert.equal(stored.faviconUrl, "");
  assert.equal(stored.typographyPreset, "humanist");
  for (const mode of ["disabled", "baseline"]) {
    await fixture(`mode=${mode}`);
    await go("/auth");
    assert.equal(await page.locator(".px-welcome").count(), 0);
    assert.equal(
      await page.locator("html").getAttribute("data-demo-brand"),
      null,
    );
    assert.equal(await page.title(), "PX");
    assert.equal(
      await page.locator('link[href="/demo-branding/px.svg"]').count(),
      0,
    );
    const after = await page.evaluate(() => ({ ...localStorage }));
    for (const key of [
      "enclave_instance_config",
      "enclave_user_email",
      "enclave_user_name",
      "enclave_user_approved",
      "enclave_language",
      "enclave_language_explicit",
      "enclave-theme",
    ])
      assert.equal(after[key], before[key], `${mode}: ${key}`);
    assert.equal(
      await page.evaluate(() =>
        document.body.style.getPropertyValue("--color-accent"),
      ),
      "",
    );
    assert.equal(
      await page.evaluate(() =>
        getComputedStyle(document.body)
          .getPropertyValue("--color-accent")
          .trim(),
      ),
      "#7d3e9b",
    );
    await shot(`rollback-${mode}-mobile`);
    check(
      `Same-browser ${mode} rollback preserves config, session markers, locale and theme`,
    );
  }
  assert.deepEqual(errors, []);
  check("No uncaught browser errors");
  const state = await fixture("mode=enabled");
  await writeFile(
    resolve(out, "../browser-results.json"),
    JSON.stringify(
      { checks, uncaughtErrors: errors, fixtureRequests: state.requests },
      null,
      2,
    ) + "\n",
  );
} finally {
  await browser.close();
}
