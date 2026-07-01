# Enclave Demo Deployment Handoff

This is the short guide for trying an already-created Enclave instance.

You should receive two things separately:

- Demo URL: `[DEMO_URL]`
- Admin Nostr key: sent privately, not in this document

Keep the admin Nostr key in a password manager. Do not paste it into chat, email threads, support tickets, or the Enclave admin assistant. The key is the admin credential for this demo instance.

Because this demo instance is already initiated, use the exact admin Nostr key you were given. A different Nostr key will not have admin access.

## Fast Path

1. Open `[DEMO_URL]/admin`.
2. Sign in with the admin Nostr key through your browser extension.
3. Open **Guided Setup**.
4. Answer the setup questions in one message.
5. Upload a few documents.
6. Add a few curated resources.
7. Test as a user.
8. Ask the admin assistant what is still missing.

## 1. Sign In As Admin

1. Install or open a NIP-07 Nostr browser extension, such as Alby or nos2x.
2. Import the admin Nostr key you were given.
3. Open `[DEMO_URL]/admin`.
4. Click **Connect with Nostr**.
5. Approve the signature request in the browser extension.

The private key stays in the extension. Enclave only asks the extension to sign a login event.

![Admin Nostr sign-in](assets/demo-deployment-handoff/admin-nostr-signin.png)

## 2. Run Guided Setup

After admin sign-in, go to **Guided Setup** from the admin dashboard.

The first screen is a setup chat. You can answer everything in one message. Use this template:

```text
1. Name:
2. Description:
3. Assistant name:
4. Accent color:
5. Theme:
6. Default language:
7. Tagline:
8. New users: let them in right away OR approve each person
9. User types:
```

Example:

```text
1. Name: Example Org Help Desk
2. Description: Private demo space for testing the org support assistant.
3. Assistant name: Guide
4. Accent color: blue
5. Theme: dark
6. Default language: English
7. Tagline: Ask for help, resources, and next steps.
8. New users: approve each person
9. User types: Staff and Member
```

When Enclave proposes changes, read the summary and click **Apply** if it looks right.

![Guided setup chat](assets/demo-deployment-handoff/guided-setup.png)

Then continue through:

- **Upload Docs**: add PDFs, guides, policies, FAQs, or other source material.
- **Curated Resources**: add trusted referrals, contacts, links, and services.
- **Finish & start testing**: try the demo as a user before inviting anyone else.

## 3. Try The User Flow

Use a different browser profile or an incognito window for the user side.

1. Open `[DEMO_URL]`.
2. Choose the user sign-up or login flow.
3. Enter a name and email.
4. Click **Continue with Email**.
5. Open the magic link email and click the link.

Users do not need a Nostr key. They sign in with email magic links.

![User email sign-up](assets/demo-deployment-handoff/user-email-signup.png)

If you chose **approve each person** during setup, approve the user from **Admin Dashboard -> User Settings** before they can fully use the instance.

## 4. Use The Admin Assistant

The admin assistant is for setup help, review, and configuration changes.

From the admin dashboard, open **Admin Assistant**, or use the assistant drawer on the right side of admin pages.

Good things to ask:

```text
What is still missing before this demo is ready for users?
```

```text
Review my current setup and tell me the next 3 things to configure.
```

```text
Set the assistant name to Guide and make the default language English.
```

```text
Create user types for Staff and Member, and ask Members what kind of help they need.
```

```text
What documents have been uploaded, and which user types can access them?
```

When the assistant suggests a configuration change, Enclave should show a change review before anything is applied. Read it, then click **Apply** only if it matches what you want.

Leave **Share secret env vars** off unless you are debugging deployment settings and understand that secrets may be shared with the assistant for that session.

![Admin dashboard and assistant](assets/demo-deployment-handoff/admin-dashboard-assistant.png)

## 5. What Each Admin Tile Is For

- **Admin Assistant**: ask setup questions and request configuration changes.
- **Guided Setup**: first-run flow for identity, docs, resources, and testing.
- **Test User Session**: simulate a user conversation and review saved beta logs.
- **Instance Settings**: name, branding, theme, public identity.
- **User Settings**: user types, onboarding questions, approvals.
- **Agent Settings**: assistant behavior, prompts, model behavior, document defaults.
- **Document Upload**: add documents to the knowledge base.
- **Resource Directory**: add trusted referrals and links the assistant can recommend.
- **Deployment Settings**: runtime config, health, readiness.
- **Database Explorer**: read-only inspection for admins.
- **Diagnostics**: smoke checks when something seems broken.

## 6. Tiny Troubleshooting

- Admin sign-in fails: confirm the browser extension has the exact admin key for this instance.
- No Nostr prompt appears: unlock the extension, refresh the page, and click **Connect with Nostr** again.
- Magic link does not arrive: check spam, then ask an admin to verify email settings in **Deployment Settings**.
- User is stuck waiting: check **User Settings** and approve the user if approvals are enabled.

That is enough for a first demo. Everything else can be refined later from the admin dashboard.
