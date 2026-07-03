from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
import uuid

integration_router = APIRouter()

# Mock databases for Learners and Webhooks
mock_learners_db: Dict[str, str] = {} # Map Rails user_id to Learner ID
mock_webhooks_db: Dict[str, str] = {} # Map webhook_id to webhook_url

class SyncPayload(BaseModel):
    user_id: str
    metadata: Dict[str, Any]

class WebhookRegisterPayload(BaseModel):
    webhook_url: str

@integration_router.post("/sync")
async def sync_learner(payload: SyncPayload):
    """
    Receives a JSON payload (user metadata from a Rails app) and syncs it with a Learner in our DB.
    Returns the mapped Learner ID.
    """
    rails_id = payload.user_id
    
    # If the user doesn't exist, create a new Learner ID mapping
    if rails_id not in mock_learners_db:
        mock_learners_db[rails_id] = str(uuid.uuid4())
        
    return {"learner_id": mock_learners_db[rails_id]}

@integration_router.post("/webhooks/register")
async def register_webhook(payload: WebhookRegisterPayload):
    """
    Receives a webhook_url and stores it in memory to trigger when a competence state is validated.
    """
    webhook_id = str(uuid.uuid4())
    mock_webhooks_db[webhook_id] = payload.webhook_url
    
    return {
        "message": "Webhook registered successfully",
        "webhook_id": webhook_id
    }
