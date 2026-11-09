from fastapi.testclient import TestClient
from services.api.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AgentFlow API"
    assert data["version"] == "0.1.0"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "AgentFlow API"


def test_resume_upload_and_confirmation_flow():
    resume_payload = {
        "raw_text": "Alex Developer\nSenior Full Stack Developer at OpenTech\nSkills: Python, React, PostgreSQL",
        "user_id": "usr_alex_01"
    }
    # 1. Upload resume
    upload_res = client.post("/api/v1/profile/upload-resume", data=resume_payload)
    assert upload_res.status_code == 201
    upload_data = upload_res.json()

    profile_id = upload_data["profile_id"]
    workflow_id = upload_data["workflow_id"]
    assert profile_id.startswith("prof_")
    assert workflow_id.startswith("wf_")
    assert upload_data["profile"]["full_name"] == "Alex Developer"
    assert not upload_data["profile"]["is_profile_confirmed"]

    # 2. Retrieve profile
    get_res = client.get(f"/api/v1/profile/{profile_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == profile_id

    # 3. Confirm profile (human approval gate)
    confirm_payload = {
        "user_feedback": "All facts approved.",
        "confirmed_fields": {"work_authorization": "Citizen"}
    }
    confirm_res = client.post(f"/api/v1/profile/{profile_id}/confirm", json=confirm_payload)
    assert confirm_res.status_code == 200
    confirmed_data = confirm_res.json()
    assert confirmed_data["is_profile_confirmed"] is True
    assert confirmed_data["work_authorization"] == "Citizen"

