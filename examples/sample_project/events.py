"""Event routing. Toy demo code, not real software.

A chain of pure equality checks on one key (event.type) — the kind of routing
chain that is safe to convert to a dispatch table, keeping the default branch.
"""


def handle_event(event):
    if event.type == "created":
        return on_created(event)
    elif event.type == "updated":
        return on_updated(event)
    elif event.type == "deleted":
        return on_deleted(event)
    elif event.type == "renewed":
        return on_renewed(event)
    elif event.type == "cancelled":
        return on_cancelled(event)
    elif event.type == "paused":
        return on_paused(event)
    elif event.type == "resumed":
        return on_resumed(event)
    elif event.type == "refunded":
        return on_refunded(event)
    else:
        return on_unknown(event)


def on_created(e): return ("created", e)
def on_updated(e): return ("updated", e)
def on_deleted(e): return ("deleted", e)
def on_renewed(e): return ("renewed", e)
def on_cancelled(e): return ("cancelled", e)
def on_paused(e): return ("paused", e)
def on_resumed(e): return ("resumed", e)
def on_refunded(e): return ("refunded", e)
def on_unknown(e): return ("unknown", e)
