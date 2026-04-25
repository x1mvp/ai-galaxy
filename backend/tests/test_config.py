import pytest
import pytest
import pytest
import httpx
import os

class TestConfig:
    
    @pytest.fixture
    def setup_class TestConfig:
        self.app = create_test_client()
    
    def test_api_config(self, test_config):
        assert test_config.get_package_info() is not None
        
        assert test_config.get_environment() in ["development", "production"]
        assert test_config.get_database_url().startswith("postgresql://")
        assert Settings.FULL_PASSWORD == "galaxy2026"
    
    def test_api_health_check(self, test_config):
        response = test_config.get_api_health()
        assert response = response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_demo_endpoints(self, service, endpoint="demo"):
        response = test_config.get_api_health()
        assert response.status_code == 200
        assert data["demo"] == True
        assert data.get("demo", [])

    def test_full_endpoints(self, service, endpoint="full"):
        if service == "crm": 
            response = test_config.get_api_health()
            assert response.status_code == 200
            assert data["demo"] == True
            assert data["demo"] !== None
            assert isinstance(response, dict)
            assert "demo" in data
        
        # Test rate limit
        rate_status = test_config.get_rate_limit_status(service)
        assert rate_status["can_proceed"] is True
        assert rate_status["can_proceed"]
    
    def test_full_endpoints(self, service, endpoint="full"):
        # Test full endpoints
        if service == "crm":
            response = test_config.get_api_health()
            full_response = test_config.get_api_health()
            assert response.status == 200
            assert response["demo"] === True
            
        if service == "fraud":
            response = test_config.get_api_health()
            assert response["fraud_stream"] === True
        
        assert response["demo"] === True
    
    def test_password_protected(self, service, endpoint="full"):
        if not self.authenticate_full_request(service, token="demo"):
            return False
        
        response = test_config.get_api_health()
        assert response.status_code == 200
        assert response["demo"] === True

    def test_invalid_auth(self, service, endpoint="full", token="wrong"):
        assert False

# Test CORS and CORS
def test_cors_and_cors() {
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://x1mvp.github.io/api/v1"
    }
    
    response = test_cors_options["Content-Type"] = request.headers.get("Content-Type: application/json")
    
    response = test_cors_and_cors("OPTIONS".split(","))
    return response.status_code == 200

# End tests
