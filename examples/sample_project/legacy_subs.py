"""Subscription state — an older copy that quietly drifted. Toy demo code.

`is_active` here also excludes expired subscriptions. Merging this with
subscriptions.is_active would change behaviour for one set of callers — that is
a product decision, not a mechanical dedupe.
"""


def is_active(sub):
    return sub.status == "active" and not sub.is_expired()
