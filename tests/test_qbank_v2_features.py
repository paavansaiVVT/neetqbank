from datetime import datetime
import pytest

def test_get_activity_feed(client):
    headers = {"X-Internal-API-Key": "test-key"}
    
    # Initial activities from seeded data
    response = client.get("/v2/qbank/activity", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert data["items"][0]["activity_type"] in ["generated", "published"]
    
    # Verify structure
    item = data["items"][0]
    assert "user_name" in item
    assert "target_type" in item

def test_get_token_usage(client):
    headers = {"X-Internal-API-Key": "test-key"}
    
    response = client.get("/v2/qbank/usage?days=7", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    # Verify aggregation
    assert data["total_input_tokens"] > 0
    assert data["total_cost"] >= 0
    assert len(data["daily_usage"]) > 0
    assert data["period_days"] == 7

def test_get_review_queue(client):
    headers = {"X-Internal-API-Key": "test-key"}
    
    response = client.get("/v2/qbank/queue?priority=urgent", headers=headers)
    assert response.status_code == 200
    data = response.json()
    
    # Should get items from seeded job
    # Note: seeded items might not be urgent depending on creation time
    # but structure should be correct
    assert isinstance(data["items"], list)
    
    # Test without priority filter
    response = client.get("/v2/qbank/queue", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) > 0

def test_comments_workflow(client):
    headers = {"X-Internal-API-Key": "test-key"}
    item_id = 1
    
    # 1. Add comment
    payload = {"content": "Test comment"}
    response = client.post(f"/v2/qbank/items/{item_id}/comments", json=payload, headers=headers)
    assert response.status_code == 201
    comment = response.json()
    assert comment["content"] == "Test comment"
    assert comment["user_name"] == "Admin User"
    
    # 2. Add reply
    reply_payload = {"content": "Test reply", "parent_id": comment["id"]}
    response = client.post(f"/v2/qbank/items/{item_id}/comments", json=reply_payload, headers=headers)
    assert response.status_code == 201
    
    # 3. Get comments
    response = client.get(f"/v2/qbank/items/{item_id}/comments", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    
def test_search_questions(client):
    headers = {"X-Internal-API-Key": "test-key"}
    
    # Search by text
    response = client.get("/v2/qbank/items/search?query=unit", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert "unit" in data["items"][0]["question"].lower() or "unit" in data["items"][0]["explanation"].lower()
    
    # Search by filter
    response = client.get("/v2/qbank/items/search?query=unit&subject=Physics", headers=headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) > 0
    
    # Search no results
    response = client.get("/v2/qbank/items/search?query=nonexistentxyz", headers=headers)
    assert response.status_code == 200
    assert data["total"] == 0 or len(response.json()["items"]) == 0
