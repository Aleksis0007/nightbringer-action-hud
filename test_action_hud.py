"""Run with Python on Windows; never starts live input polling or calls League."""
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import action_hud as hud


def main():
    region = {"left": -100, "top": 100, "width": 32, "height": 32}
    valid = {"attack_move_key": "a", "q_region": region}
    assert hud.validate_settings(valid) == valid
    for config in ({}, {**valid, "attack_move_key": "aa"},
                   {**valid, "q_region": {**region, "width": 0}},
                   {**valid, "q_region": {**region, "left": True}}):
        try:
            hud.validate_settings(config)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid settings were accepted")

    # Simulate cursor readings, not real desktop input; invalid calibration
    # must leave a previously valid configuration untouched.
    with tempfile.TemporaryDirectory() as tmp:
        settings = Path(tmp) / "settings.json"
        positions = iter([(-100, 100), (-68, 132)])

        def cursor(point):
            point._obj.x, point._obj.y = next(positions)
            return 1

        with patch("builtins.input", return_value=""), patch("builtins.print"), \
             patch.object(hud.time, "sleep"), \
             patch.object(hud.ctypes.windll.user32, "GetCursorPos", side_effect=cursor):
            assert hud.calibrate(settings) == valid
            assert json.loads(settings.read_text()) == valid
            positions = iter([(100, 100), (50, 50)])
            try:
                hud.calibrate(settings)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid calibration was saved")
            assert json.loads(settings.read_text()) == valid

    hud.load_templates()
    assert len(hud.templates) == 5
    for name, frame, icon in hud.templates:
        with patch.object(hud, "grab_q_gray", return_value=frame):
            assert hud.classify_q_from_screen() == (name, icon)

    guard = hud.InputCommandGuard()
    guard.arm_attack_move(10)
    assert guard.consume_attack_click(11)
    assert not guard.consume_attack_click(11.1)
    guard.arm_attack_move(20)
    assert not guard.consume_attack_click(21.6)
    assert guard.accept_q("Infernum", 1)
    assert not guard.accept_q("Infernum", 1.1)
    assert guard.accept_q("Calibrum", 1.2)

    # The MSS constructor must execute in the actual input worker thread.
    created_in = []

    class StopWorker(Exception):
        pass

    def run_worker():
        try:
            hud.input_loop()
        except StopWorker:
            pass

    with patch.object(hud.mss, "mss", side_effect=lambda: created_in.append(threading.get_ident())), \
         patch.object(hud, "is_pressed", side_effect=StopWorker):
        worker = threading.Thread(target=run_worker)
        worker.start()
        worker.join(2)
        assert not worker.is_alive() and created_in == [worker.ident]

    with hud.app.test_client() as client:
        assert client.get("/hud").status_code == 200
        assert client.get("/health").json["templates"] == 5
        for path in ["/static/moontrail2.css", "/static/moontrail2.js", *hud.ICON_URLS.values()]:
            assert client.get(path).status_code == 200, path
        for path in ("/test/cast", "/test/kill", "/static/settings.json", "/static/../action_hud.py"):
            assert client.get(path).status_code == 404, path
        response = client.get("/events", buffered=False)
        events = iter(response.response)
        assert json.loads(next(events).decode().split("data: ")[1])["items"] == []
        hud.add_action("Q", hud.ICON_URLS["q_infernum"], "weapon-infernum")
        assert json.loads(next(events).decode().split("data: ")[1])["items"][0]["label"] == "Q"
        with hud.state_changed:
            hud.history[-1]["time"] -= hud.ACTION_TTL + 1
        assert json.loads(next(events).decode().split("data: ")[1])["items"] == []
        response.close()
    print("PASS: settings, calibration, templates, command guards, capture thread, routes, SSE, expiry")


if __name__ == "__main__":
    main()
