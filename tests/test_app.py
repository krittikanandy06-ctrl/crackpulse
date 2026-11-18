
import io
import app as crackpulse


def setup_function():
    crackpulse.app.config["TESTING"] = True


def test_homepage():
    client = crackpulse.app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_health_check():
    client = crackpulse.app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b"ok"


def test_missing_photo():
    client = crackpulse.app.test_client()
    response = client.post("/inspect")
    assert response.status_code == 200
    assert b"Choose a photo first" in response.data


def test_invalid_file_upload():
    client = crackpulse.app.test_client()

    response = client.post(
        "/inspect",
        data={
            "photo": (io.BytesIO(b"fake file"), "test.txt")
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 200
    assert b"Upload a photo" in response.data


def test_invalid_report_request():
    client = crackpulse.app.test_client()

    response = client.post(
        "/report",
        data={"kind": "wrong", "uid": "123"}
    )

    assert response.status_code == 400
