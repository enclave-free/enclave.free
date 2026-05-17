# Safe Rendering Posture

Enclave Free Prototype renders ordinary UI text as React text nodes so user,
Admin, Document, Model Provider, and tool output is escaped by default.

Rich rendering is allowed only through explicit safe renderers:

- User messages render as plain text with preserved whitespace.
- Assistant messages render Markdown through the chat message renderer.
- Raw HTML embedded in Markdown is not rendered as HTML.
- Unsafe Markdown links such as `javascript:` URLs render as plain text rather
  than clickable anchors.
- Conversation Trace summaries, retrieval summaries, and tool summaries render
  as plain text.
- JSON, SQL, logs, and diagnostic output render inside code surfaces as text.

Do not add `dangerouslySetInnerHTML`, direct `innerHTML`, or a new Markdown/HTML
renderer unless it has its own sanitizer and representative XSS regression
tests.
