import inspect
import unittest

from tools import sentry_m5_live


class _State:
    def __init__(self, state: str, camera_state: str):
        self.state = state
        self.camera_state = camera_state


class _Store:
    def __init__(self, states, open_session: bool = False):
        self.states = iter(states)
        self.current = None
        self.open_session = open_session

    def current_state(self, room_id):
        try:
            self.current = next(self.states)
        except StopIteration:
            pass
        return self.current

    def sessions(self, room_id, limit=20):
        return [{"status": "open"}] if self.open_session else []


class M5LiveHarnessTests(unittest.TestCase):
    def test_empty_baseline_requires_online_empty_and_no_open_session(self):
        self.assertTrue(sentry_m5_live._empty_baseline_ready(_Store([_State("empty", "online")])))
        self.assertFalse(sentry_m5_live._empty_baseline_ready(_Store([_State("occupied", "online")])))
        self.assertFalse(sentry_m5_live._empty_baseline_ready(_Store([_State("empty", "degraded")])))
        self.assertFalse(sentry_m5_live._empty_baseline_ready(_Store([_State("empty", "online")], open_session=True)))

    def test_baseline_must_remain_stable_and_resets_on_bad_state(self):
        clock = [0.0]
        store = _Store([
            _State("empty", "online"),
            _State("occupied", "online"),
            _State("empty", "online"),
            _State("empty", "online"),
            _State("empty", "online"),
            _State("empty", "online"),
        ])
        ok, stable_at, error = sentry_m5_live._wait_for_stable_empty_baseline(
            store,
            stable_seconds=0.5,
            timeout_seconds=3.0,
            service_alive=lambda: True,
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
            monotonic=lambda: clock[0],
        )
        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertEqual(stable_at, 0.5)

    def test_perception_starts_before_operator_entry_protocol(self):
        source = inspect.getsource(sentry_m5_live.run_live)
        self.assertLess(source.index("service_thread.start()"), source.index("operator_input("))
        self.assertLess(source.index("baseline_completed_at"), source.index("PRIMARY_USER_ENTER_NOW"))


if __name__ == "__main__":
    unittest.main()
