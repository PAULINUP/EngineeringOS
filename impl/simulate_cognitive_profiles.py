import asyncio
import httpx
import json
import random
import time

API_BASE = "http://localhost:8000/api"
TOTAL_SIMULATIONS = 1000

# Cognitive Profiles
# We'll randomly select a profile for each iteration
PROFILES = ["fast_sponge", "slow_amnesic", "erratic", "malicious_hacker"]

# Sample KUs from the curriculum
SAMPLE_KUS = [
    "ku:ce:11106", # Engenharia de Software
    "ku:ce:10666", # Calculo I
    "ku:ce:1446",  # Sistemas Operacionais
    "ku:ce:1985",  # Inteligencia Artificial
    "invalid_ku_123" # Edge case
]

async def run_simulation():
    print(f"Starting {TOTAL_SIMULATIONS} cognitive simulations...")
    errors = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Seed Curriculum
        print("Seeding database...")
        try:
            await client.post(f"{API_BASE}/seed-curriculum")
        except Exception as e:
            print(f"Seed failed: {e}")
            return
            
        # 2. Create a test learner
        print("Creating test learner...")
        learner_res = await client.post(f"{API_BASE}/learners", json={"name": "Swarm Test Subject"})
        if learner_res.status_code != 200:
            print(f"Learner creation failed: {learner_res.text}")
            return
        learner_id = learner_res.json()["id"]
        
        # 3. Generate 1000 Payloads
        payloads = []
        for i in range(TOTAL_SIMULATIONS):
            profile = random.choice(PROFILES)
            ku_id = random.choice(SAMPLE_KUS)
            
            if profile == "fast_sponge":
                payload = {
                    "learner_id": learner_id,
                    "ku_id": ku_id,
                    "type": "solution",
                    "source_weight": 0.9,
                    "reviewer_agreement": 1.0,
                    "recency_factor": 1.0,
                    "reviewers": [{"reviewer_id": "auto", "reviewer_type": "ai", "verdict": "accept"}]
                }
            elif profile == "slow_amnesic":
                payload = {
                    "learner_id": learner_id,
                    "ku_id": ku_id,
                    "type": "explanation",
                    "source_weight": 0.3,
                    "reviewer_agreement": 0.6,
                    "recency_factor": 0.4,
                    "reviewers": [{"reviewer_id": "auto", "reviewer_type": "ai", "verdict": "accept"}]
                }
            elif profile == "erratic":
                payload = {
                    "learner_id": learner_id,
                    "ku_id": ku_id,
                    "type": "decision",
                    "source_weight": random.uniform(0.1, 1.0),
                    "reviewer_agreement": random.uniform(0.0, 1.0),
                    "recency_factor": random.uniform(0.1, 1.5), # Out of bounds
                    "reviewers": [] # Empty reviewers
                }
            else: # malicious_hacker
                payload = {
                    "learner_id": learner_id,
                    "ku_id": ku_id if ku_id != "invalid_ku_123" else "ku:ce:11106' OR '1'='1",
                    "type": "DROP TABLE learners;",
                    "source_weight": 9999.9, # Overflow
                    "reviewer_agreement": -1.0, # Negative
                    "recency_factor": 0.0,
                    "reviewers": "NOT_A_LIST" # Type mismatch
                }
                
            payloads.append((i, payload))
            
        print("Blasting API with 1000 concurrent evidence submissions...")
        
        # We will batch them to avoid overwhelming local OS socket limits
        batch_size = 50
        
        start_time = time.time()
        for i in range(0, len(payloads), batch_size):
            batch = payloads[i:i+batch_size]
            
            async def send_req(idx, pl):
                try:
                    res = await client.post(f"{API_BASE}/evidence", json=pl)
                    if res.status_code >= 500:
                        return {"index": idx, "status": res.status_code, "error": res.text, "payload": pl}
                    elif res.status_code in (404, 422):
                        # Defensive success, do not treat as error
                        pass
                except Exception as e:
                    return {"index": idx, "status": "Exception", "error": str(e), "payload": pl}
                return None
                
            tasks = [send_req(idx, pl) for idx, pl in batch]
            results = await asyncio.gather(*tasks)
            
            for r in results:
                if r:
                    errors.append(r)
                    
            print(f"Processed {min(i+batch_size, TOTAL_SIMULATIONS)} / {TOTAL_SIMULATIONS}")
            
        end_time = time.time()
        
    print(f"Simulation completed in {end_time - start_time:.2f} seconds.")
    print(f"Total Errors Encountered: {len(errors)}")
    
    with open("simulation_errors.json", "w") as f:
        json.dump(errors, f, indent=2)
        
    if len(errors) == 0:
        print("SUCCESS! 0 Errors encountered.")
    else:
        print("Wrote errors to simulation_errors.json")

if __name__ == "__main__":
    asyncio.run(run_simulation())
