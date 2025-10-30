import requests
import sys
import json
from datetime import datetime
import uuid

class AgriClimateAPITester:
    def __init__(self, base_url="https://data-fallback.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "status": "PASSED" if success else "FAILED",
            "details": details
        })

    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "operational":
                    self.log_test("Health Check", True, f"Status: {data}")
                    return True
                else:
                    self.log_test("Health Check", False, f"Invalid response: {data}")
                    return False
            else:
                self.log_test("Health Check", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Health Check", False, f"Exception: {str(e)}")
            return False

    def test_root_endpoint(self):
        """Test /api/ root endpoint"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    self.log_test("Root Endpoint", True, f"Message: {data['message']}")
                    return True
                else:
                    self.log_test("Root Endpoint", False, f"No message in response: {data}")
                    return False
            else:
                self.log_test("Root Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Root Endpoint", False, f"Exception: {str(e)}")
            return False

    def test_datasets_endpoint(self):
        """Test /api/datasets endpoint"""
        try:
            response = requests.get(f"{self.api_url}/datasets", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "datasets" in data and "total" in data:
                    self.log_test("Datasets Endpoint", True, f"Found {data['total']} datasets")
                    return True
                else:
                    self.log_test("Datasets Endpoint", False, f"Invalid response structure: {data}")
                    return False
            else:
                self.log_test("Datasets Endpoint", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Datasets Endpoint", False, f"Exception: {str(e)}")
            return False

    def test_chat_query_english(self):
        """Test /api/chat/query with English question"""
        try:
            self.session_id = f"test-session-{uuid.uuid4()}"
            
            payload = {
                "question": "What are the top rice producing states in India?",
                "session_id": self.session_id,
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60  # Longer timeout for LLM processing
            )
            
            if response.status_code == 200:
                data = response.json()
                required_fields = ["session_id", "answer", "sources", "timestamp"]
                
                if all(field in data for field in required_fields):
                    if data["answer"] and len(data["answer"]) > 10:
                        self.log_test("Chat Query (English)", True, f"Answer length: {len(data['answer'])}, Sources: {len(data['sources'])}")
                        return True
                    else:
                        self.log_test("Chat Query (English)", False, f"Empty or too short answer: {data['answer']}")
                        return False
                else:
                    missing = [f for f in required_fields if f not in data]
                    self.log_test("Chat Query (English)", False, f"Missing fields: {missing}")
                    return False
            else:
                self.log_test("Chat Query (English)", False, f"Status code: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            self.log_test("Chat Query (English)", False, f"Exception: {str(e)}")
            return False

    def test_chat_query_hindi(self):
        """Test /api/chat/query with Hindi question"""
        try:
            payload = {
                "question": "भारत में सर्वाधिक चावल उत्पादक राज्य कौन से हैं?",
                "session_id": self.session_id,
                "language": "hi"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["answer"] and len(data["answer"]) > 10:
                    # Check if response contains Hindi characters
                    has_hindi = any('\u0900' <= char <= '\u097F' for char in data["answer"])
                    self.log_test("Chat Query (Hindi)", True, f"Answer length: {len(data['answer'])}, Has Hindi: {has_hindi}")
                    return True
                else:
                    self.log_test("Chat Query (Hindi)", False, f"Empty or too short answer: {data['answer']}")
                    return False
            else:
                self.log_test("Chat Query (Hindi)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Chat Query (Hindi)", False, f"Exception: {str(e)}")
            return False

    def test_chat_history(self):
        """Test /api/chat/history/{session_id} endpoint"""
        if not self.session_id:
            self.log_test("Chat History", False, "No session ID available")
            return False
            
        try:
            response = requests.get(f"{self.api_url}/chat/history/{self.session_id}", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "session_id" in data and "messages" in data:
                    if len(data["messages"]) >= 2:  # Should have user + assistant messages
                        self.log_test("Chat History", True, f"Found {len(data['messages'])} messages")
                        return True
                    else:
                        self.log_test("Chat History", False, f"Expected at least 2 messages, got {len(data['messages'])}")
                        return False
                else:
                    self.log_test("Chat History", False, f"Invalid response structure: {data}")
                    return False
            else:
                self.log_test("Chat History", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Chat History", False, f"Exception: {str(e)}")
            return False

    def test_error_handling(self):
        """Test error handling with invalid requests"""
        try:
            # Test with empty question
            payload = {
                "question": "",
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            # Should handle gracefully (either 400 or 200 with error message)
            if response.status_code in [200, 400, 422]:
                self.log_test("Error Handling (Empty Question)", True, f"Status: {response.status_code}")
                return True
            else:
                self.log_test("Error Handling (Empty Question)", False, f"Unexpected status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Error Handling (Empty Question)", False, f"Exception: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting AgriClimate Q&A System Backend Tests")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 60)
        
        # Basic connectivity tests
        self.test_health_endpoint()
        self.test_root_endpoint()
        self.test_datasets_endpoint()
        
        # Core functionality tests
        self.test_chat_query_english()
        self.test_chat_query_hindi()
        self.test_chat_history()
        
        # Error handling tests
        self.test_error_handling()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed. Check details above.")
            return 1

def main():
    tester = AgriClimateAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())