"""
Fix Verification Test

This test verifies that the fixes applied to the feedback and RAG endpoints work correctly.
It re-runs the same tests from the bug condition exploration to confirm they now pass.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from unittest.mock import patch, MagicMock
import json

client = TestClient(app)

def test_feedback_submission_now_handles_empty_response():
    """
    Verify that feedback submission now properly handles empty database responses.
    This test should PASS after the fix.
    """
    mock_user = {"id": 1, "role": "teacher", "name": "Test Teacher"}
    
    with patch('backend.routers.feedback.get_current_user', return_value=mock_user):
        with patch('backend.routers.feedback.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            
            # Test with empty response (the bug condition)
            mock_sb.table.return_value.insert.return_value.execute.return_value.data = []
            
            response = client.post("/api/feedback/", json={
                "category": "system",
                "message": "Test feedback message"
            })
            
            print(f"Fixed feedback submission - Status: {response.status_code}")
            print(f"Fixed feedback submission - Response: {response.text}")
            
            # After fix, this should return 500 with proper error message instead of crashing
            assert response.status_code == 500, f"Expected 500 error for empty response but got {response.status_code}"
            
            if response.status_code == 500:
                data = response.json()
                assert "Failed to create feedback entry" in data.get("detail", ""), "Expected proper error message"

def test_feedback_submission_works_with_valid_response():
    """
    Verify that feedback submission still works correctly with valid database responses.
    This test should PASS after the fix.
    """
    mock_user = {"id": 1, "role": "teacher", "name": "Test Teacher"}
    
    with patch('backend.routers.feedback.get_current_user', return_value=mock_user):
        with patch('backend.routers.feedback.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            
            # Test with valid response
            mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{
                "id": 1,
                "sender_id": 1,
                "category": "system",
                "message": "Test feedback message",
                "status": "pending"
            }]
            
            response = client.post("/api/feedback/", json={
                "category": "system",
                "message": "Test feedback message"
            })
            
            print(f"Valid feedback submission - Status: {response.status_code}")
            print(f"Valid feedback submission - Response: {response.text}")
            
            # After fix, this should work correctly
            assert response.status_code == 200, f"Expected 200 success but got {response.status_code}"
            
            if response.status_code == 200:
                data = response.json()
                assert "message" in data, "Response missing 'message' field"
                assert "feedback" in data, "Response missing 'feedback' field"
                assert data["message"] == "Feedback submitted successfully"

def test_student_feedback_submission_now_handles_empty_response():
    """
    Verify that student feedback submission now properly handles empty database responses.
    This test should PASS after the fix.
    """
    mock_user = {"id": 1, "role": "student", "name": "Test Student"}
    
    with patch('backend.routers.student_feedback.get_current_user', return_value=mock_user):
        with patch('backend.routers.student_feedback.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            
            # Test with empty response (the bug condition)
            mock_sb.table.return_value.insert.return_value.execute.return_value.data = []
            
            response = client.post("/api/student-feedback", json={
                "message": "Test student feedback message",
                "is_anonymous": True
            })
            
            print(f"Fixed student feedback submission - Status: {response.status_code}")
            print(f"Fixed student feedback submission - Response: {response.text}")
            
            # After fix, this should still work by falling back to the original row data
            assert response.status_code == 200, f"Expected 200 success but got {response.status_code}"
            
            if response.status_code == 200:
                data = response.json()
                assert "message" in data, "Response missing 'message' field"
                assert "feedback" in data, "Response missing 'feedback' field"
                assert data["message"] == "Feedback sent successfully"

def test_all_list_endpoints_return_lists():
    """
    Verify that all GET endpoints return lists, never None or {}.
    This test should PASS after the fix.
    """
    # Test feedback list
    mock_teacher = {"id": 1, "role": "teacher", "name": "Test Teacher"}
    with patch('backend.routers.feedback.get_current_user', return_value=mock_teacher):
        with patch('backend.routers.feedback.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = None
            
            response = client.get("/api/feedback/mine")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list), f"Feedback list should be list but got {type(data)}"
            assert data == [], f"Empty feedback list should be [] but got {data}"
    
    # Test student feedback list
    mock_admin = {"id": 1, "role": "admin", "name": "Test Admin"}
    with patch('backend.routers.student_feedback.get_current_user', return_value=mock_admin):
        with patch('backend.routers.student_feedback.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value.data = None
            
            response = client.get("/api/student-feedback")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list), f"Student feedback list should be list but got {type(data)}"
            assert data == [], f"Empty student feedback list should be [] but got {data}"
    
    # Test RAG search history
    mock_student = {"id": 1, "role": "student", "name": "Test Student"}
    with patch('backend.routers.rag.get_current_user', return_value=mock_student):
        with patch('backend.routers.rag.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            mock_query = MagicMock()
            mock_sb.table.return_value.select.return_value = mock_query
            mock_query.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = None
            
            response = client.get("/api/rag/search-history")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list), f"Search history should be list but got {type(data)}"
            assert data == [], f"Empty search history should be [] but got {data}"

if __name__ == "__main__":
    print("Running fix verification tests...")
    print("These tests verify that the fixes work correctly.")
    pytest.main([__file__, "-v", "-s"])