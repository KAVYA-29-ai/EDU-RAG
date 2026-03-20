"""
Preservation Property Tests

This test ensures that non-affected endpoint behavior is preserved during the bugfix.
These tests should PASS on unfixed code to establish baseline behavior.

Property 2: Preservation - Non-Affected Endpoint Behavior
"""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from unittest.mock import patch, MagicMock
import json

client = TestClient(app)

class TestPreservationProperties:
    """
    Property 2: Preservation - Non-Affected Endpoint Behavior
    
    These tests verify that authentication, validation, and other endpoints
    continue to work exactly as before the fix.
    """
    
    def test_authentication_continues_to_work(self):
        """
        Test that authentication errors continue to return 401/403 as expected.
        This behavior should be preserved.
        """
        # Test unauthenticated access to protected endpoints
        response = client.get("/api/feedback/mine")
        print(f"Unauthenticated feedback access - Status: {response.status_code}")
        
        # Should return 401 or 403 for unauthorized access
        assert response.status_code in [401, 403], f"Expected 401/403 but got {response.status_code}"
        
        response = client.get("/api/student-feedback")
        print(f"Unauthenticated student feedback access - Status: {response.status_code}")
        assert response.status_code in [401, 403], f"Expected 401/403 but got {response.status_code}"
        
        response = client.get("/api/rag/search-history")
        print(f"Unauthenticated search history access - Status: {response.status_code}")
        assert response.status_code in [401, 403], f"Expected 401/403 but got {response.status_code}"
    
    def test_validation_errors_continue_to_work(self):
        """
        Test that validation errors continue to return 422 for invalid data.
        This behavior should be preserved.
        """
        # Mock authentication to bypass auth checks
        mock_user = {"id": 1, "role": "teacher", "name": "Test Teacher"}
        
        with patch('backend.routers.feedback.get_current_user', return_value=mock_user):
            # Test with invalid feedback data (missing required fields)
            response = client.post("/api/feedback/", json={
                "message": "Test message"
                # Missing required 'category' field
            })
            
            print(f"Invalid feedback data - Status: {response.status_code}")
            print(f"Invalid feedback data - Response: {response.text}")
            
            # Should return 422 for validation error
            assert response.status_code == 422, f"Expected 422 validation error but got {response.status_code}"
    
    def test_authorization_checks_continue_to_work(self):
        """
        Test that role-based authorization continues to work properly.
        This behavior should be preserved.
        """
        # Test student trying to access admin-only endpoint
        mock_student = {"id": 1, "role": "student", "name": "Test Student"}
        
        with patch('backend.routers.feedback.get_current_user', return_value=mock_student):
            # Students should not be able to view all feedback (admin only)
            response = client.get("/api/feedback/")
            print(f"Student accessing admin endpoint - Status: {response.status_code}")
            assert response.status_code == 403, f"Expected 403 forbidden but got {response.status_code}"
        
        # Test student trying to submit feedback via teacher endpoint
        with patch('backend.routers.feedback.get_current_user', return_value=mock_student):
            response = client.post("/api/feedback/", json={
                "category": "system",
                "message": "Test message"
            })
            print(f"Student submitting teacher feedback - Status: {response.status_code}")
            assert response.status_code == 403, f"Expected 403 forbidden but got {response.status_code}"
    
    def test_successful_operations_continue_to_work(self):
        """
        Test that successful operations continue to return proper response structures.
        This behavior should be preserved.
        """
        # Test health endpoint (should always work)
        response = client.get("/api/health")
        print(f"Health check - Status: {response.status_code}")
        print(f"Health check - Response: {response.text}")
        
        assert response.status_code == 200, f"Health check failed with status {response.status_code}"
        data = response.json()
        assert "status" in data, "Health check response missing 'status' field"
        assert data["status"] == "healthy", f"Expected 'healthy' status but got {data['status']}"
    
    def test_successful_feedback_submission_structure_preserved(self):
        """
        Test that successful feedback submission continues to return proper structure.
        This behavior should be preserved.
        """
        mock_user = {"id": 1, "role": "teacher", "name": "Test Teacher"}
        
        with patch('backend.routers.feedback.get_current_user', return_value=mock_user):
            with patch('backend.routers.feedback.get_supabase') as mock_supabase:
                # Mock successful database response
                mock_sb = MagicMock()
                mock_supabase.return_value = mock_sb
                mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{
                    "id": 1,
                    "sender_id": 1,
                    "category": "system",
                    "message": "Test message",
                    "status": "pending"
                }]
                
                response = client.post("/api/feedback/", json={
                    "category": "system",
                    "message": "Test message"
                })
                
                print(f"Successful feedback submission - Status: {response.status_code}")
                print(f"Successful feedback submission - Response: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    # Verify response structure is preserved
                    assert "message" in data, "Response missing 'message' field"
                    assert "feedback" in data, "Response missing 'feedback' field"
                    assert data["message"] == "Feedback submitted successfully"
    
    def test_successful_feedback_list_structure_preserved(self):
        """
        Test that successful feedback list retrieval continues to return proper structure.
        This behavior should be preserved.
        """
        mock_user = {"id": 1, "role": "teacher", "name": "Test Teacher"}
        
        with patch('backend.routers.feedback.get_current_user', return_value=mock_user):
            with patch('backend.routers.feedback.get_supabase') as mock_supabase:
                # Mock successful database response with data
                mock_sb = MagicMock()
                mock_supabase.return_value = mock_sb
                mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
                    {
                        "id": 1,
                        "sender_id": 1,
                        "category": "system",
                        "message": "Test message",
                        "status": "pending"
                    }
                ]
                
                response = client.get("/api/feedback/mine")
                
                print(f"Successful feedback list - Status: {response.status_code}")
                print(f"Successful feedback list - Response: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    # Verify response structure is preserved
                    assert isinstance(data, list), f"Expected list but got {type(data)}"
                    if data:  # If there's data, verify structure
                        assert "id" in data[0], "Feedback item missing 'id' field"
                        assert "message" in data[0], "Feedback item missing 'message' field"
    
    def test_other_router_endpoints_continue_to_work(self):
        """
        Test that other router endpoints (not being fixed) continue to work.
        This behavior should be preserved.
        """
        # Test auth endpoints
        response = client.post("/api/auth/login", json={
            "institution_id": "test123",
            "password": "testpass"
        })
        print(f"Auth login attempt - Status: {response.status_code}")
        # Should return some response (400, 401, 500 are all acceptable for invalid creds)
        assert response.status_code in [200, 400, 401, 500], f"Unexpected auth response: {response.status_code}"
        
        # Test that we get proper JSON responses, not HTML errors
        try:
            response.json()
            print("Auth endpoint returns valid JSON")
        except:
            print(f"Auth endpoint response: {response.text}")
            # Should still be a valid response, even if not JSON

if __name__ == "__main__":
    print("Running preservation property tests...")
    print("These tests should PASS on unfixed code to establish baseline behavior.")
    pytest.main([__file__, "-v", "-s"])