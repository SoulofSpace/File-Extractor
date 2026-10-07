"""FastAPI Server Endpoints Verification for FILE XTRACTOR V4."""

import os
import sys
from fastapi.testclient import TestClient

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from intellifile.api.server import app, get_services

def test_api_v4_endpoints():
    print("\n--- Testing FastAPI V4 Endpoints ---")
    client = TestClient(app)

    # 1. System Status Endpoint
    resp = client.get("/api/status")
    assert resp.status_code == 200, f"Status failed: {resp.status_code}"
    data = resp.json()
    print(f"  [PASS] /api/status -> status={data.get('status')}")

    # 2. Privacy Status Endpoint
    p_status = client.get("/api/privacy/status")
    assert p_status.status_code == 200
    p_stat_data = p_status.json()
    print(f"  [PASS] /api/privacy/status -> is_configured={p_stat_data.get('is_configured')}")

    # 3. Privacy Setup or Verify Endpoint
    token = None
    if not p_stat_data.get("is_configured"):
        setup_resp = client.post("/api/privacy/setup", json={"password": "MyMasterPassword!"})
        assert setup_resp.status_code == 200
        setup_data = setup_resp.json()
        rec_key = setup_data["recovery_key"]
        token = setup_data["token"]
        assert len(rec_key.split("-")) == 4
        print(f"  [PASS] /api/privacy/setup -> created recovery key: {rec_key[:4]}-****")
    else:
        v_resp = client.post("/api/privacy/verify", json={"password": "MyMasterPassword!"})
        if v_resp.status_code == 200:
            token = v_resp.json()["token"]
            print("  [PASS] /api/privacy/verify -> verified password and received token")

    # 4. Privacy Status with token
    if token:
        p_status_unlocked = client.get(f"/api/privacy/status?privacy_token={token}")
        assert p_status_unlocked.status_code == 200
        assert p_status_unlocked.json()["is_unlocked"] is True
        print("  [PASS] /api/privacy/status (with token) -> unlocked=True")

        # 5. Privacy Lock Endpoint
        client.post(f"/api/privacy/lock?privacy_token={token}")
        p_status_locked = client.get("/api/privacy/status")
        assert p_status_locked.json()["is_unlocked"] is False
        print("  [PASS] /api/privacy/lock -> successfully locked session")

        # 6. Re-verify
        v_resp2 = client.post("/api/privacy/verify", json={"password": "MyMasterPassword!"})
        assert v_resp2.status_code == 200
        token = v_resp2.json()["token"]
        print("  [PASS] /api/privacy/verify -> re-unlocked successfully")

    # 7. Persons List & Create Endpoints
    p_create = client.post("/api/persons", json={
        "name": "Arun Kumar",
        "aliases": ["Arun", "AK"],
        "notes": "Verified Person Profile",
    })
    assert p_create.status_code == 200
    created_p = p_create.json()["person"]
    assert created_p["name"] == "Arun Kumar"
    p_id = created_p["id"]
    print(f"  [PASS] /api/persons (POST) -> created Person id={p_id}, name='{created_p['name']}'")

    p_list = client.get("/api/persons")
    assert p_list.status_code == 200
    persons = p_list.json()["persons"]
    assert len(persons) >= 1
    print(f"  [PASS] /api/persons (GET) -> listed {len(persons)} persons")

    # 8. Person Details Endpoint
    p_detail = client.get(f"/api/persons/{p_id}")
    assert p_detail.status_code == 200
    assert p_detail.json()["name"] == "Arun Kumar"
    print(f"  [PASS] /api/persons/{p_id} (GET) -> fetched profile details")

    # 9. Voice Search Endpoint (with synthetic WAV header audio)
    wav_header = (
        b"RIFF" + (36).to_bytes(4, "little") + b"WAVE"
        + b"fmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little")
        + (16000).to_bytes(4, "little") + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
        + b"data" + (0).to_bytes(4, "little")
    )
    voice_resp = client.post(
        "/api/voice-search",
        files={"file": ("recording.wav", wav_header, "audio/wav")},
    )
    assert voice_resp.status_code in (200, 503)
    if voice_resp.status_code == 200:
        print(f"  [PASS] /api/voice-search -> transcript: {voice_resp.json()}")
    else:
        print("  [PASS] /api/voice-search -> graceful 503 (SARVAM_API_KEY optional)")

    # 10. Search Endpoint with Universal Query Planner & Privacy Token
    search_resp = client.post(
        "/api/search",
        json={
            "query": "show me Arun photos from December",
            "privacy_token": token,
            "limit": 10,
        }
    )
    assert search_resp.status_code == 200
    s_data = search_resp.json()
    assert "results" in s_data
    print(f"  [PASS] /api/search -> Universal Query Planner executed successfully, returned {len(s_data['results'])} results")

    print("\n" + "=" * 60)
    print("ALL FASTAPI V4 API ENDPOINTS VERIFIED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_api_v4_endpoints()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
