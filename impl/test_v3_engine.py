import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/api"

def run_tests():
    print("--- 1. Generating JWT Token ---")
    resp = requests.post(f"{BASE_URL}/token", json={"username": "dev", "password": "dev"})
    if resp.status_code != 200:
        print("Failed to get token:", resp.text)
        return
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n--- 2. Seeding Database with v3.0 EOS-DSL ---")
    resp = requests.post(f"{BASE_URL}/seed", headers=headers)
    print("Seed Response:", resp.status_code, resp.json())
    
    print("\n--- 3. Creating a Test Learner ---")
    resp = requests.post(f"{BASE_URL}/learners", json={"name": "Alice Turing"}, headers=headers)
    learner = resp.json()
    learner_id = learner["id"]
    print("Learner Created:", learner)
    
    print("\n--- 4. Checking Initial Competences ---")
    resp = requests.get(f"{BASE_URL}/learners/{learner_id}/competences")
    print("Initial Competences:", resp.json())
    
    print("\n--- 5. Submitting Evidence (Low Confidence) ---")
    evidence_payload = {
        "learner_id": learner_id,
        "ku_id": "linear_algebra.matrix_definition.v1",
        "type": "explanation",
        "source_weight": 0.5,
        "reviewer_agreement": 0.8,
        "recency_factor": 1.0,
        "reviewers": []
    }
    resp = requests.post(f"{BASE_URL}/evidence", json=evidence_payload, headers=headers)
    print("Evidence Response:", resp.status_code, resp.json())
    
    print("\n--- 6. Submitting Evidence (High Confidence) ---")
    evidence_payload["source_weight"] = 0.9
    evidence_payload["reviewer_agreement"] = 1.0
    resp = requests.post(f"{BASE_URL}/evidence", json=evidence_payload, headers=headers)
    print("Evidence Response:", resp.status_code, resp.json())
    
    print("\n--- 7. Checking Final Competences (Effective Mastery & Decay) ---")
    resp = requests.get(f"{BASE_URL}/learners/{learner_id}/competences")
    print(json.dumps(resp.json(), indent=2))

if __name__ == "__main__":
    run_tests()
