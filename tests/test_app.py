import io

import app as crackpulse


def client():
    crackpulse.app.config["TESTING"] = True
    return crackpulse.app.test_client()


def test_homepage_opens():
    r = client().get("/")
    assert r.status_code == 200
    assert b"CrackPulse" in r.data


def test_health_check():
    r = client().get("/health")
    assert r.status_code == 200
    assert r.data == b"ok"


def test_inspect_without_photo():
    r = client().post("/inspect")
    assert r.status_code == 200
    assert b"Choose a photo first" in r.data


def test_inspect_rejects_text_file():
    r = client().post(
        "/inspect",
        data={"photo": (io.BytesIO(b"not an image"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    assert b"Upload a photo" in r.data


def test_vibration_without_video():
    r = client().post("/vibration")
    assert r.status_code == 200
    assert b"Choose a video first" in r.data


def test_vibration_rejects_text_file():
    r = client().post(
        "/vibration",
        data={"video": (io.BytesIO(b"not a video"), "notes.txt")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    assert b"Upload a video" in r.data


def test_report_bad_request():
    r = client().post("/report", data={"kind": "hack", "uid": "../etc"})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_report_missing_file():
    r = client().post("/report", data={"kind": "crack", "uid": "abcdef12"})
    assert r.status_code == 404
    assert r.get_json()["ok"] is False


def test_too_large_upload(monkeypatch):
    monkeypatch.setitem(crackpulse.app.config, "MAX_CONTENT_LENGTH", 10)
    r = client().post(
        "/inspect",
        data={"photo": (io.BytesIO(b"x" * 1000), "big.jpg")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 413
    assert b"too large" in r.data
    def test_security_headers():
    r = client().get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"


def test_marker_size_rejects_nan():
    with crackpulse.app.test_request_context(
        "/inspect", method="POST", data={"marker_mm": "nan"}
    ):
        assert crackpulse.get_marker_mm() == "50.0"
