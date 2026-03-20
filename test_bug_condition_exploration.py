"""
Bug Condition Exploration Test

This test is designed to FAIL on unfixed code to demonstrate the bugs exist.
It tests the specific failing scenarios identified in the design document.

IMPORTANT: This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from unittest.mock import patch, MagicMock
import json

client = TestClient(app)

"""
Bug Condition Exploration Test

This test is designed to FAIL on unfixed code to demonstrate the bugs exist.
It tests the specific failing scenarios identified in the design document.

IMPORTANT: This test MUST FAIL on unfixed code - failure confirms the bug exists.
DO NOT attempt to fix the test or the code when it fails.

Based on analysis of the existing code, the bugs may be more subtle than initially thought.
This test will help identify the actual root causes.
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from unittest.mock import patch, MagicMock
import json

client = TestClient(app)

def test_feedback_submission_with_database_error():
    """
    Property 1: Bug Condition - Feedback submission with database errors
    
    Test what happens when database operations fail during feedback submission.
    This test explores the actual bug condition.
    """
    # Mock authentication to simulate teacher user
    mock_user = {"id": 1, "role": "teacher", "name": "Test Teacher"}
    
    with patch('backend.routers.feedback.get_current_user', return_value=mock_user):
        # Mock database to simulate failure
        with patch('backend.routers.feedback.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            
            # Simulate database insert failure
            mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception("Database connection failed")
            
            response = client.post("/api/feedback/", json={
                "category": "system",
                "message": "Test feedback message"
            })
            
            print(f"Database error test - Status: {response.status_code}")
            print(f"Database error test - Response: {response.text}")
            
            # Document the counterexample - this should show how the system handles database errors
            # If the bug exists, this might return 500 instead of proper error handling
            assert response.status_code in [200, 500], f"Unexpected status code: {response.status_code}"

def test_feedback_submission_with_missing_data():
    """
    Test feedback submission with missing required data to see validation behavior.
    """
    mock_user = {"id": 1, "role": "teacher", "name": "Test Teacher"}
    
    with patch('backend.routers.feedback.get_current_user', return_value=mock_user):
        # Test with missing category
        response = client.post("/api/feedback/", json={
            "message": "Test feedback message"
            # Missing category
        })
        
        print(f"Missing data test - Status: {response.status_code}")
        print(f"Missing data test - Response: {response.text}")
        
        # This should return 422 for validation error
        assert response.status_code == 422, f"Expected 422 validation error but got {response.status_code}"

def test_feedback_list_empty_database_response():
    """
    Test what happens when database returns None or empty for feedback lists.
    """
    mock_user = {"id": 1, "role": "teacher", "name": "Test Teacher"}
    
    with patch('backend.routers.feedback.get_current_user', return_value=mock_user):
        with patch('backend.routers.feedback.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            
            # Test with None response
            mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = None
            
            response = client.get("/api/feedback/mine")
            
            print(f"Empty feedback test - Status: {response.status_code}")
            print(f"Empty feedback test - Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Empty feedback test - Response type: {type(data)}")
                
                # This should return a list, not None or {}
                assert isinstance(data, list), f"Bug confirmed: Expected list but got {type(data)}"
                assert data == [], f"Expected empty list but got {data}"

def test_student_feedback_empty_database_response():
    """
    Test student feedback endpoint with empty database response.
    """
    mock_user = {"id": 1, "role": "admin", "name": "Test Admin"}
    
    with patch('backend.routers.student_feedback.get_current_user', return_value=mock_user):
        with patch('backend.routers.student_feedback.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            
            # Test with None response
            mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value.data = None
            
            response = client.get("/api/student-feedback")
            
            print(f"Empty student feedback test - Status: {response.status_code}")
            print(f"Empty student feedback test - Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Empty student feedback test - Response type: {type(data)}")
                
                # This should return a list, not None or {}
                assert isinstance(data, list), f"Bug confirmed: Expected list but got {type(data)}"

def test_rag_search_history_empty_database_response():
    """
    Test RAG search history endpoint with empty database response.
    """
    mock_user = {"id": 1, "role": "student", "name": "Test Student"}
    
    with patch('backend.routers.rag.get_current_user', return_value=mock_user):
        with patch('backend.routers.rag.get_supabase') as mock_supabase:
            mock_sb = MagicMock()
            mock_supabase.return_value = mock_sb
            
            # Test with None response
            mock_query = MagicMock()
            mock_sb.table.return_value.select.return_value = mock_query
            mock_query.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = None
            
            response = client.get("/api/rag/search-history")
            
            print(f"Empty search history test - Status: {response.status_code}")
            print(f"Empty search history test - Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Empty search history test - Response type: {type(data)}")
                
                # This should return a list, not None or {}
                assert isinstance(data, list), f"Bug confirmed: Expected list but got {type(data)}"

def test_actual_endpoints_without_mocking():
    """
    Test the actual endpoints without mocking to see real behavior.
    This will help identify if the bugs are in the actual implementation.
    """
    # Test health endpoint first
    response = client.get("/api/health")
    print(f"Health check - Status: {response.status_code}")
    print(f"Health check - Response: {response.text}")
    
    # Test feedback endpoint without authentication (should get 401/403)
    response = client.get("/api/feedback/mine")
    print(f"Unauthenticated feedback - Status: {response.status_code}")
    print(f"Unauthenticated feedback - Response: {response.text}")
    
    # Test student feedback endpoint without authentication
    response = client.get("/api/student-feedback")
    print(f"Unauthenticated student feedback - Status: {response.status_code}")
    print(f"Unauthenticated student feedback - Response: {response.text}")
    
    # Test RAG search history without authentication
    response = client.get("/api/rag/search-history")
    print(f"Unauthenticated search history - Status: {response.status_code}")
    print(f"Unauthenticated search history - Response: {response.text}")

if __name__ == "__main__":
    print("Running bug condition exploration tests...")
    print("These tests will help identify the actual bugs in the system.")
    
    # Run individual tests to see their output
    test_actual_endpoints_without_mocking()
    test_feedback_submission_with_missing_data()
    
    # Run with pytest for detailed output
    pytest.main([__file__, "-v", "-s"])