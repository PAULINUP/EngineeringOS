import asyncio
import aiohttp
import time
import random
import uuid

API_BASE_URL = "http://127.0.0.1:8000/api"
TOTAL_USERS = 10000
BATCH_SIZE = 500

# KU IDs that we know are in the database after seeding
AVAILABLE_KUS = [
    "linear_algebra.matrix_definition.v1",
    "linear_algebra.dot_product.v1",
    "linear_algebra.matrix_multiplication.v1",
    "linear_algebra.eigenvalues.v1",
    "calculus.partial_derivatives.v1",
    "ml.gradient_descent.v1"
]

async def create_learner(session, i):
    name = f"Stress Test Learner {i}"
    async with session.post(f"{API_BASE_URL}/learners", json={"name": name}) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data["id"]
        return None

async def submit_evidence(session, learner_id):
    # Simulate a cognitive profile: random KU, random confidence
    ku_id = random.choice(AVAILABLE_KUS)
    source_weight = random.uniform(0.3, 0.99)
    reviewer_agreement = random.uniform(0.5, 1.0)
    payload = {
        "learner_id": learner_id,
        "ku_id": ku_id,
        "type": "simulation",
        "source_weight": source_weight,
        "reviewer_agreement": reviewer_agreement,
        "recency_factor": 1.0,
        "reviewers": []
    }
    async with session.post(f"{API_BASE_URL}/evidence", json=payload) as resp:
        return resp.status == 200

async def worker(session, i):
    # Create the learner
    learner_id = await create_learner(session, i)
    if not learner_id:
        return False
        
    # Submit 3 random evidences for this learner
    success = True
    for _ in range(3):
        res = await submit_evidence(session, learner_id)
        if not res:
            success = False
    return success

async def run_stress_test():
    print(f"Starting Mega Stress Test with {TOTAL_USERS} simulated learners...")
    start_time = time.time()
    
    # Optional: Seed the database first if not already seeded. 
    # For now, we assume it's seeded or we can just send the seed request.
    
    async with aiohttp.ClientSession() as session:
        # 1. Get Token (assume dev mode returns any valid format)
        async with session.post(f"{API_BASE_URL}/token", json={"username": "dev", "password": "dev"}) as resp:
            if resp.status != 200:
                print("Failed to get token!")
            else:
                token_data = await resp.json()
                token = token_data.get("access_token")
                session.headers.update({"Authorization": f"Bearer {token}"})
                
        # We process in batches to avoid overwhelming the OS socket limits
        successful_users = 0
        for i in range(0, TOTAL_USERS, BATCH_SIZE):
            batch_start = time.time()
            tasks = []
            for j in range(i, min(i + BATCH_SIZE, TOTAL_USERS)):
                tasks.append(worker(session, j))
                
            results = await asyncio.gather(*tasks)
            successful_users += sum(1 for r in results if r)
            
            batch_end = time.time()
            print(f"Batch {i//BATCH_SIZE + 1} completed: {min(i + BATCH_SIZE, TOTAL_USERS)}/{TOTAL_USERS} users processed (Batch Time: {batch_end - batch_start:.2f}s)")
            
    end_time = time.time()
    print("\n--- STRESS TEST RESULTS ---")
    print(f"Total Users Simulated: {TOTAL_USERS}")
    print(f"Total Successful Users (Created + 3 Evidences): {successful_users}")
    print(f"Total Time Elapsed: {end_time - start_time:.2f} seconds")
    print(f"Average Time per User: {(end_time - start_time) / TOTAL_USERS:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_stress_test())
