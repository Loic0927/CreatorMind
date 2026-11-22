from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.services.tracked_items import load_tracked_items


def test_bulk_loader_reads_snapshots_and_comments_once_then_groups_in_memory():
    now = datetime(2026, 11, 22, tzinfo=UTC)

    class Repository:
        def __init__(self):
            self.snapshot_calls = []
            self.comment_calls = []

        def tracked(self, user_id, active_only=True):
            assert (user_id, active_only) == ("u", False)
            return [SimpleNamespace(id="t1", media_id="m1"), SimpleNamespace(id="t2", media_id="m2")]

        def media_for_account(self, account_id):
            assert account_id == "account"
            return [SimpleNamespace(id="m1"), SimpleNamespace(id="m2")]

        def snapshots(self, media_ids):
            self.snapshot_calls.append(media_ids)
            return [
                SimpleNamespace(media_id="m1", captured_at=now - timedelta(hours=2)),
                SimpleNamespace(media_id="m1", captured_at=now),
                SimpleNamespace(media_id="m2", captured_at=now - timedelta(hours=1)),
            ]

        def comments(self, user_id, tracked_post_id):
            self.comment_calls.append((user_id, tracked_post_id))
            return [SimpleNamespace(tracked_post_id="t2", text="Comment")]

    repository = Repository()
    items, comments = load_tracked_items(
        "u",
        account=SimpleNamespace(id="account"),
        active_only=False,
        include_comments=True,
        repository=repository,
    )

    assert repository.snapshot_calls == [["m1", "m2"]]
    assert repository.comment_calls == [("u", None)]
    assert [item["latest"].captured_at for item in items] == [now, now - timedelta(hours=1)]
    assert comments == {"t2": [SimpleNamespace(tracked_post_id="t2", text="Comment")]}
