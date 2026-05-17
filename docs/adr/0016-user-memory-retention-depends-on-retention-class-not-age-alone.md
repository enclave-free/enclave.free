# User Memory Retention Depends On Retention Class, Not Age Alone

Scheduled User Memory retention must not delete active Admin-confirmed User Memory merely because it is old. User Memory needs an explicit retention class so ambient capture can default to expirable, Admin-confirmed memory can default to durable, and superseded memory can become eligible after its retention window. This favors preserving operator-confirmed personalization and subject context over a simpler age-only cleanup rule, while still allowing low-risk ambient memory to age out.
