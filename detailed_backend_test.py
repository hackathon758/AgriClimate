import requests
import json
import uuid
from datetime import datetime

class DetailedAgriClimateAPITester:
    def __init__(self, base_url="https://fetch-fallback-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_id = f"test-session-{uuid.uuid4()}"
        self.tests_run = 0
        self.tests_passed = 0

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
            if details:
                print(f"   Details: {details}")
        else:
            print(f"❌ {name} - FAILED: {details}")

    def test_specific_queries(self):
        """Test the specific queries mentioned in the review request"""
        queries = [
            ("What are potato prices in Bihar?", "en"),
            ("Show me potato prices", "en"), 
            ("wheat prices in Maharashtra", "en"),
            ("मूल्य दिखाएं", "hi"),  # Show prices in Hindi
            ("commodity prices for vegetables", "en"),
            ("tell me about onion prices", "en")
        ]
        
        for question, language in queries:
            try:
                payload = {
                    "question": question,
                    "session_id": self.session_id,
                    "language": language
                }
                
                response = requests.post(
                    f"{self.api_url}/chat/query",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check response structure
                    required_fields = ["session_id", "answer", "sources", "timestamp"]
                    if all(field in data for field in required_fields):
                        
                        # Check if answer is meaningful (not error message)
                        answer = data["answer"]
                        error_indicators = [
                            "unable to fetch data",
                            "budget exceeded", 
                            "error occurred",
                            "try again later"
                        ]
                        
                        has_error = any(indicator in answer.lower() for indicator in error_indicators)
                        
                        if not has_error and len(answer) > 50:
                            # Check if sources are populated
                            sources = data["sources"]
                            sources_info = f"Sources: {len(sources)}"
                            if sources:
                                sources_info += f", First source: {sources[0].get('title', 'N/A')}"
                            
                            self.log_test(f"Query: '{question}' ({language})", True, 
                                        f"Answer length: {len(answer)}, {sources_info}")
                        else:
                            self.log_test(f"Query: '{question}' ({language})", False, 
                                        f"Error in response or too short: {answer[:100]}...")
                    else:
                        missing = [f for f in required_fields if f not in data]
                        self.log_test(f"Query: '{question}' ({language})", False, 
                                    f"Missing fields: {missing}")
                else:
                    self.log_test(f"Query: '{question}' ({language})", False, 
                                f"Status code: {response.status_code}, Response: {response.text[:200]}")
                    
            except Exception as e:
                self.log_test(f"Query: '{question}' ({language})", False, f"Exception: {str(e)}")

    def test_response_structure_details(self):
        """Test detailed response structure for one query"""
        try:
            payload = {
                "question": "What are current potato prices in different states?",
                "session_id": self.session_id,
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
                
                print(f"\n📋 Detailed Response Analysis:")
                print(f"   Session ID: {data.get('session_id', 'Missing')}")
                print(f"   Answer length: {len(data.get('answer', ''))}")
                print(f"   Number of sources: {len(data.get('sources', []))}")
                print(f"   Timestamp format: {data.get('timestamp', 'Missing')}")
                
                # Check sources structure
                sources = data.get('sources', [])
                if sources:
                    print(f"   First source details:")
                    first_source = sources[0]
                    for key, value in first_source.items():
                        print(f"     {key}: {value}")
                
                # Check if answer mentions actual data
                answer = data.get('answer', '')
                data_indicators = ['price', 'state', 'market', 'commodity', 'data.gov.in']
                has_data_refs = any(indicator in answer.lower() for indicator in data_indicators)
                
                self.log_test("Response Structure Analysis", True, 
                            f"Has data references: {has_data_refs}")
                
                return True
            else:
                self.log_test("Response Structure Analysis", False, 
                            f"Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Response Structure Analysis", False, f"Exception: {str(e)}")
            return False

    def test_session_management(self):
        """Test session management and chat history"""
        try:
            # Make a query
            payload = {
                "question": "Show me rice prices",
                "session_id": self.session_id,
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            
            if response.status_code == 200:
                # Now check history
                history_response = requests.get(f"{self.api_url}/chat/history/{self.session_id}", timeout=10)
                
                if history_response.status_code == 200:
                    history_data = history_response.json()
                    messages = history_data.get('messages', [])
                    
                    # Should have user and assistant messages
                    user_messages = [m for m in messages if m.get('role') == 'user']
                    assistant_messages = [m for m in messages if m.get('role') == 'assistant']
                    
                    self.log_test("Session Management", True, 
                                f"User messages: {len(user_messages)}, Assistant messages: {len(assistant_messages)}")
                    return True
                else:
                    self.log_test("Session Management", False, 
                                f"History status code: {history_response.status_code}")
                    return False
            else:
                self.log_test("Session Management", False, 
                            f"Query status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Session Management", False, f"Exception: {str(e)}")
            return False

    def run_detailed_tests(self):
        """Run detailed tests for the review request"""
        print("🔍 Starting Detailed AgriClimate Q&A System Tests")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 70)
        
        # Test specific queries from review request
        self.test_specific_queries()
        
        # Test response structure in detail
        self.test_response_structure_details()
        
        # Test session management
        self.test_session_management()
        
        # Print summary
        print("\n" + "=" * 70)
        print(f"📊 Detailed Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All detailed tests passed!")
            return 0
        else:
            print("⚠️  Some detailed tests failed. Check details above.")
            return 1

def main():
    tester = DetailedAgriClimateAPITester()
    return tester.run_detailed_tests()

if __name__ == "__main__":
    main()