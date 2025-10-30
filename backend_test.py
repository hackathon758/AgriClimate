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

    def test_normal_flow_data_available(self):
        """Test normal flow with data available - should return live data without fallback disclaimer"""
        try:
            payload = {
                "question": "What are potato prices in Bihar?",
                "session_id": f"test-normal-{uuid.uuid4()}",
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Should NOT contain fallback disclaimer
                has_disclaimer = "⚠️ Note: Live data from data.gov.in is currently unavailable" in answer
                has_sources = len(sources) > 0
                
                if not has_disclaimer and has_sources and len(answer) > 50:
                    self.log_test("Normal Flow (Data Available)", True, f"Answer length: {len(answer)}, Sources: {len(sources)}, No disclaimer: {not has_disclaimer}")
                    return True
                else:
                    self.log_test("Normal Flow (Data Available)", False, f"Has disclaimer: {has_disclaimer}, Sources: {len(sources)}, Answer length: {len(answer)}")
                    return False
            else:
                self.log_test("Normal Flow (Data Available)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Normal Flow (Data Available)", False, f"Exception: {str(e)}")
            return False

    def test_fallback_outside_domain(self):
        """Test fallback for query outside domain - should trigger AI fallback with disclaimer"""
        try:
            payload = {
                "question": "What is the weather forecast for tomorrow?",
                "session_id": f"test-fallback-{uuid.uuid4()}",
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Should contain fallback disclaimer and empty sources
                has_disclaimer = "⚠️ Note: Live data from data.gov.in is currently unavailable" in answer
                sources_empty = len(sources) == 0
                
                if has_disclaimer and sources_empty and len(answer) > 100:
                    self.log_test("Fallback (Outside Domain)", True, f"Has disclaimer: {has_disclaimer}, Empty sources: {sources_empty}, Answer length: {len(answer)}")
                    return True
                else:
                    self.log_test("Fallback (Outside Domain)", False, f"Has disclaimer: {has_disclaimer}, Sources: {len(sources)}, Answer length: {len(answer)}")
                    return False
            else:
                self.log_test("Fallback (Outside Domain)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Fallback (Outside Domain)", False, f"Exception: {str(e)}")
            return False

    def test_fallback_obscure_query(self):
        """Test fallback for obscure query - should trigger fallback with disclaimer"""
        try:
            payload = {
                "question": "Tell me about quantum physics",
                "session_id": f"test-obscure-{uuid.uuid4()}",
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Should contain fallback disclaimer and empty sources
                has_disclaimer = "⚠️ Note: Live data from data.gov.in is currently unavailable" in answer
                sources_empty = len(sources) == 0
                
                if has_disclaimer and sources_empty and len(answer) > 100:
                    self.log_test("Fallback (Obscure Query)", True, f"Has disclaimer: {has_disclaimer}, Empty sources: {sources_empty}, Answer length: {len(answer)}")
                    return True
                else:
                    self.log_test("Fallback (Obscure Query)", False, f"Has disclaimer: {has_disclaimer}, Sources: {len(sources)}, Answer length: {len(answer)}")
                    return False
            else:
                self.log_test("Fallback (Obscure Query)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Fallback (Obscure Query)", False, f"Exception: {str(e)}")
            return False

    def test_bilingual_fallback(self):
        """Test bilingual fallback in Hindi - should trigger fallback with Hindi disclaimer"""
        try:
            payload = {
                "question": "मौसम की जानकारी दें",  # Give weather information
                "session_id": f"test-hindi-fallback-{uuid.uuid4()}",
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
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Should contain Hindi fallback disclaimer and empty sources
                has_hindi_disclaimer = "⚠️ नोट: data.gov.in से लाइव डेटा वर्तमान में उपलब्ध नहीं है" in answer
                sources_empty = len(sources) == 0
                has_hindi = any('\u0900' <= char <= '\u097F' for char in answer)
                
                if has_hindi_disclaimer and sources_empty and has_hindi and len(answer) > 100:
                    self.log_test("Bilingual Fallback (Hindi)", True, f"Has Hindi disclaimer: {has_hindi_disclaimer}, Empty sources: {sources_empty}, Has Hindi: {has_hindi}, Answer length: {len(answer)}")
                    return True
                else:
                    self.log_test("Bilingual Fallback (Hindi)", False, f"Has Hindi disclaimer: {has_hindi_disclaimer}, Sources: {len(sources)}, Has Hindi: {has_hindi}, Answer length: {len(answer)}")
                    return False
            else:
                self.log_test("Bilingual Fallback (Hindi)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Bilingual Fallback (Hindi)", False, f"Exception: {str(e)}")
            return False

    def test_session_continuity(self):
        """Test session continuity - mix normal queries and fallback queries in same session"""
        try:
            session_id = f"test-continuity-{uuid.uuid4()}"
            
            # First query - normal (should have data)
            payload1 = {
                "question": "Show me potato prices",
                "session_id": session_id,
                "language": "en"
            }
            
            response1 = requests.post(
                f"{self.api_url}/chat/query",
                json=payload1,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            # Second query - fallback (should trigger fallback)
            payload2 = {
                "question": "What is artificial intelligence?",
                "session_id": session_id,
                "language": "en"
            }
            
            response2 = requests.post(
                f"{self.api_url}/chat/query",
                json=payload2,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response1.status_code == 200 and response2.status_code == 200:
                data1 = response1.json()
                data2 = response2.json()
                
                # Verify session IDs match
                same_session = data1.get("session_id") == data2.get("session_id") == session_id
                
                # First should have sources, second should not
                first_has_sources = len(data1.get("sources", [])) > 0
                second_no_sources = len(data2.get("sources", [])) == 0
                
                # Second should have disclaimer
                second_has_disclaimer = "⚠️ Note: Live data from data.gov.in is currently unavailable" in data2.get("answer", "")
                
                if same_session and first_has_sources and second_no_sources and second_has_disclaimer:
                    self.log_test("Session Continuity", True, f"Same session: {same_session}, First has sources: {first_has_sources}, Second fallback: {second_has_disclaimer}")
                    return True
                else:
                    self.log_test("Session Continuity", False, f"Same session: {same_session}, First sources: {len(data1.get('sources', []))}, Second sources: {len(data2.get('sources', []))}, Second disclaimer: {second_has_disclaimer}")
                    return False
            else:
                self.log_test("Session Continuity", False, f"Status codes: {response1.status_code}, {response2.status_code}")
                return False
        except Exception as e:
            self.log_test("Session Continuity", False, f"Exception: {str(e)}")
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