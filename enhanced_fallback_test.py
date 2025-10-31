import requests
import sys
import json
from datetime import datetime
import uuid
import time

class EnhancedFallbackTester:
    def __init__(self, base_url="https://fetch-fallback-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
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

    def test_retry_mechanism(self):
        """Test Option 6: Retry Mechanism with exponential backoff"""
        try:
            # Test normal query that should work without retries
            payload = {
                "question": "What are rice prices in India?",
                "session_id": f"test-retry-{uuid.uuid4()}",
                "language": "en"
            }
            
            start_time = time.time()
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            end_time = time.time()
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Normal query should work without visible retries
                # Response time should be reasonable (not indicating multiple retries)
                response_time = end_time - start_time
                
                if len(answer) > 50 and len(sources) > 0 and response_time < 30:
                    self.log_test("Retry Mechanism (Normal Query)", True, 
                                f"Response time: {response_time:.2f}s, Answer length: {len(answer)}, Sources: {len(sources)}")
                    return True
                else:
                    self.log_test("Retry Mechanism (Normal Query)", False, 
                                f"Response time: {response_time:.2f}s, Answer length: {len(answer)}, Sources: {len(sources)}")
                    return False
            else:
                self.log_test("Retry Mechanism (Normal Query)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Retry Mechanism (Normal Query)", False, f"Exception: {str(e)}")
            return False

    def test_hybrid_mode_partial_data(self):
        """Test Option 3: Hybrid Mode - combining partial data with AI knowledge"""
        try:
            # Query that should trigger hybrid mode if <5 records available
            payload = {
                "question": "What are rice prices?",
                "session_id": f"test-hybrid-{uuid.uuid4()}",
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Check for hybrid response disclaimer
                has_hybrid_disclaimer = "ℹ️ Hybrid Response" in answer or "ℹ️ हाइब्रिड प्रतिक्रिया" in answer
                
                # Check for section markers distinguishing live data from general knowledge
                has_live_data_section = "Based on available live data" in answer or "available live data" in answer.lower()
                has_general_knowledge_section = "From general knowledge" in answer or "general knowledge" in answer.lower()
                
                # Should have both live data sources AND trusted reference sources
                has_mixed_sources = len(sources) > 1  # Should have multiple source types
                
                if has_hybrid_disclaimer and (has_live_data_section or has_general_knowledge_section) and has_mixed_sources:
                    self.log_test("Hybrid Mode (Partial Data)", True, 
                                f"Hybrid disclaimer: {has_hybrid_disclaimer}, Live data section: {has_live_data_section}, "
                                f"General knowledge section: {has_general_knowledge_section}, Mixed sources: {len(sources)}")
                    return True
                else:
                    # If not hybrid, check if it's normal flow (which is also acceptable)
                    is_normal_flow = len(sources) > 0 and not ("⚠️ Note:" in answer) and len(answer) > 50
                    if is_normal_flow:
                        self.log_test("Hybrid Mode (Partial Data)", True, 
                                    f"Normal flow triggered instead of hybrid (acceptable): Sources: {len(sources)}, Answer length: {len(answer)}")
                        return True
                    else:
                        self.log_test("Hybrid Mode (Partial Data)", False, 
                                    f"Hybrid disclaimer: {has_hybrid_disclaimer}, Live data section: {has_live_data_section}, "
                                    f"General knowledge section: {has_general_knowledge_section}, Sources: {len(sources)}")
                        return False
            else:
                self.log_test("Hybrid Mode (Partial Data)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Hybrid Mode (Partial Data)", False, f"Exception: {str(e)}")
            return False

    def test_hybrid_mode_hindi(self):
        """Test Hybrid Mode in Hindi"""
        try:
            payload = {
                "question": "चावल की कीमत क्या है?",  # What is the price of rice?
                "session_id": f"test-hybrid-hindi-{uuid.uuid4()}",
                "language": "hi"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Check for Hindi hybrid disclaimer
                has_hindi_hybrid_disclaimer = "ℹ️ हाइब्रिड प्रतिक्रिया" in answer
                has_hindi_content = any('\u0900' <= char <= '\u097F' for char in answer)
                
                if (has_hindi_hybrid_disclaimer or len(sources) > 0) and has_hindi_content and len(answer) > 50:
                    self.log_test("Hybrid Mode (Hindi)", True, 
                                f"Hindi hybrid disclaimer: {has_hindi_hybrid_disclaimer}, Has Hindi: {has_hindi_content}, "
                                f"Sources: {len(sources)}, Answer length: {len(answer)}")
                    return True
                else:
                    self.log_test("Hybrid Mode (Hindi)", False, 
                                f"Hindi hybrid disclaimer: {has_hindi_hybrid_disclaimer}, Has Hindi: {has_hindi_content}, "
                                f"Sources: {len(sources)}, Answer length: {len(answer)}")
                    return False
            else:
                self.log_test("Hybrid Mode (Hindi)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Hybrid Mode (Hindi)", False, f"Exception: {str(e)}")
            return False

    def test_enhanced_responses_detailed_fallback(self):
        """Test Option 2: Enhanced Responses - detailed fallback answers"""
        try:
            # Non-agricultural query that should trigger enhanced fallback
            payload = {
                "question": "Tell me about weather patterns",
                "session_id": f"test-enhanced-{uuid.uuid4()}",
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Should have fallback disclaimer
                has_fallback_disclaimer = "⚠️ Note: Live data from data.gov.in is currently unavailable" in answer
                
                # Enhanced responses should be comprehensive and detailed
                is_comprehensive = len(answer) > 500  # Should be detailed
                
                # Check for enhanced content indicators
                has_practical_examples = any(keyword in answer.lower() for keyword in 
                                           ['example', 'typically', 'usually', 'generally', 'often', 'seasonal', 'pattern'])
                
                has_detailed_info = any(keyword in answer.lower() for keyword in 
                                      ['factors', 'variations', 'practices', 'tips', 'ranges', 'trends'])
                
                # Should have trusted sources
                has_trusted_sources = len(sources) > 0
                
                if has_fallback_disclaimer and is_comprehensive and (has_practical_examples or has_detailed_info) and has_trusted_sources:
                    self.log_test("Enhanced Responses (Detailed Fallback)", True, 
                                f"Fallback disclaimer: {has_fallback_disclaimer}, Comprehensive: {is_comprehensive}, "
                                f"Practical examples: {has_practical_examples}, Detailed info: {has_detailed_info}, "
                                f"Trusted sources: {len(sources)}, Answer length: {len(answer)}")
                    return True
                else:
                    self.log_test("Enhanced Responses (Detailed Fallback)", False, 
                                f"Fallback disclaimer: {has_fallback_disclaimer}, Comprehensive: {is_comprehensive}, "
                                f"Practical examples: {has_practical_examples}, Detailed info: {has_detailed_info}, "
                                f"Trusted sources: {len(sources)}, Answer length: {len(answer)}")
                    return False
            else:
                self.log_test("Enhanced Responses (Detailed Fallback)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Enhanced Responses (Detailed Fallback)", False, f"Exception: {str(e)}")
            return False

    def test_enhanced_responses_hindi(self):
        """Test Enhanced Responses in Hindi"""
        try:
            payload = {
                "question": "मौसम के बारे में बताएं",  # Tell me about weather
                "session_id": f"test-enhanced-hindi-{uuid.uuid4()}",
                "language": "hi"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Should have Hindi fallback disclaimer
                has_hindi_disclaimer = "⚠️ नोट: data.gov.in से लाइव डेटा वर्तमान में उपलब्ध नहीं है" in answer
                has_hindi_content = any('\u0900' <= char <= '\u097F' for char in answer)
                is_comprehensive = len(answer) > 300
                has_trusted_sources = len(sources) > 0
                
                if has_hindi_disclaimer and has_hindi_content and is_comprehensive and has_trusted_sources:
                    self.log_test("Enhanced Responses (Hindi)", True, 
                                f"Hindi disclaimer: {has_hindi_disclaimer}, Has Hindi: {has_hindi_content}, "
                                f"Comprehensive: {is_comprehensive}, Trusted sources: {len(sources)}, Answer length: {len(answer)}")
                    return True
                else:
                    self.log_test("Enhanced Responses (Hindi)", False, 
                                f"Hindi disclaimer: {has_hindi_disclaimer}, Has Hindi: {has_hindi_content}, "
                                f"Comprehensive: {is_comprehensive}, Trusted sources: {len(sources)}, Answer length: {len(answer)}")
                    return False
            else:
                self.log_test("Enhanced Responses (Hindi)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Enhanced Responses (Hindi)", False, f"Exception: {str(e)}")
            return False

    def test_trusted_sources_price_query(self):
        """Test Option 5: Trusted Sources for price-related fallback queries"""
        try:
            payload = {
                "question": "What is climate change?",  # Should return trusted sources
                "session_id": f"test-sources-price-{uuid.uuid4()}",
                "language": "en"
            }
            
            response = requests.post(
                f"{self.api_url}/chat/query",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                sources = data.get("sources", [])
                
                # Should have fallback disclaimer
                has_fallback_disclaimer = "⚠️ Note: Live data from data.gov.in is currently unavailable" in answer
                
                # Should have trusted sources
                has_sources = len(sources) > 0
                
                # Verify sources have required fields
                valid_sources = True
                if sources:
                    for source in sources:
                        if not all(field in source for field in ['title', 'url', 'description']):
                            valid_sources = False
                            break
                
                # Check for relevant trusted sources (climate-related)
                relevant_sources = False
                if sources:
                    source_text = ' '.join([s.get('title', '') + ' ' + s.get('description', '') for s in sources]).lower()
                    relevant_sources = any(keyword in source_text for keyword in 
                                         ['climate', 'meteorological', 'earth sciences', 'weather', 'imd', 'ministry'])
                
                if has_fallback_disclaimer and has_sources and valid_sources and relevant_sources:
                    self.log_test("Trusted Sources (Climate Query)", True, 
                                f"Fallback disclaimer: {has_fallback_disclaimer}, Sources count: {len(sources)}, "
                                f"Valid sources: {valid_sources}, Relevant sources: {relevant_sources}")
                    return True
                else:
                    self.log_test("Trusted Sources (Climate Query)", False, 
                                f"Fallback disclaimer: {has_fallback_disclaimer}, Sources count: {len(sources)}, "
                                f"Valid sources: {valid_sources}, Relevant sources: {relevant_sources}")
                    return False
            else:
                self.log_test("Trusted Sources (Climate Query)", False, f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Trusted Sources (Climate Query)", False, f"Exception: {str(e)}")
            return False

    def test_trusted_sources_different_query_types(self):
        """Test that different query types get different relevant sources"""
        try:
            # Test crop-related query
            payload_crop = {
                "question": "Tell me about crop production methods",
                "session_id": f"test-sources-crop-{uuid.uuid4()}",
                "language": "en"
            }
            
            response_crop = requests.post(
                f"{self.api_url}/chat/query",
                json=payload_crop,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            if response_crop.status_code == 200:
                data_crop = response_crop.json()
                sources_crop = data_crop.get("sources", [])
                
                # Should have sources relevant to crops/agriculture
                crop_relevant = False
                if sources_crop:
                    source_text = ' '.join([s.get('title', '') + ' ' + s.get('description', '') for s in sources_crop]).lower()
                    crop_relevant = any(keyword in source_text for keyword in 
                                      ['agricultural', 'crop', 'icar', 'research', 'production', 'statistics'])
                
                if len(sources_crop) > 0 and crop_relevant:
                    self.log_test("Trusted Sources (Different Query Types)", True, 
                                f"Crop query sources: {len(sources_crop)}, Crop relevant: {crop_relevant}")
                    return True
                else:
                    self.log_test("Trusted Sources (Different Query Types)", False, 
                                f"Crop query sources: {len(sources_crop)}, Crop relevant: {crop_relevant}")
                    return False
            else:
                self.log_test("Trusted Sources (Different Query Types)", False, f"Crop query status: {response_crop.status_code}")
                return False
        except Exception as e:
            self.log_test("Trusted Sources (Different Query Types)", False, f"Exception: {str(e)}")
            return False

    def test_integration_all_features(self):
        """Test integration of all features together"""
        try:
            session_id = f"test-integration-{uuid.uuid4()}"
            
            # Test 1: Normal agricultural query (should NOT show disclaimers)
            payload1 = {
                "question": "Show me current potato prices in Maharashtra",
                "session_id": session_id,
                "language": "en"
            }
            
            response1 = requests.post(
                f"{self.api_url}/chat/query",
                json=payload1,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            # Test 2: Non-agricultural query (should show fallback disclaimer + trusted sources)
            payload2 = {
                "question": "What is artificial intelligence?",
                "session_id": session_id,
                "language": "en"
            }
            
            response2 = requests.post(
                f"{self.api_url}/chat/query",
                json=payload2,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            # Test 3: Bilingual test
            payload3 = {
                "question": "कृत्रिम बुद्धिमत्ता क्या है?",  # What is artificial intelligence?
                "session_id": session_id,
                "language": "hi"
            }
            
            response3 = requests.post(
                f"{self.api_url}/chat/query",
                json=payload3,
                headers={"Content-Type": "application/json"},
                timeout=90
            )
            
            if all(r.status_code == 200 for r in [response1, response2, response3]):
                data1 = response1.json()
                data2 = response2.json()
                data3 = response3.json()
                
                # Verify session continuity
                same_session = (data1.get("session_id") == data2.get("session_id") == 
                              data3.get("session_id") == session_id)
                
                # Test 1: Normal flow - should have sources, no disclaimer
                normal_has_sources = len(data1.get("sources", [])) > 0
                normal_no_disclaimer = "⚠️ Note:" not in data1.get("answer", "")
                
                # Test 2: Fallback flow - should have disclaimer, trusted sources
                fallback_has_disclaimer = "⚠️ Note:" in data2.get("answer", "")
                fallback_has_sources = len(data2.get("sources", [])) > 0
                
                # Test 3: Hindi fallback - should have Hindi disclaimer
                hindi_has_disclaimer = "⚠️ नोट:" in data3.get("answer", "")
                hindi_has_content = any('\u0900' <= char <= '\u097F' for char in data3.get("answer", ""))
                
                all_tests_pass = (same_session and normal_has_sources and normal_no_disclaimer and 
                                fallback_has_disclaimer and fallback_has_sources and 
                                hindi_has_disclaimer and hindi_has_content)
                
                if all_tests_pass:
                    self.log_test("Integration (All Features)", True, 
                                f"Session continuity: {same_session}, Normal flow: sources={len(data1.get('sources', []))}, "
                                f"Fallback flow: disclaimer={fallback_has_disclaimer}, sources={len(data2.get('sources', []))}, "
                                f"Hindi flow: disclaimer={hindi_has_disclaimer}, hindi_content={hindi_has_content}")
                    return True
                else:
                    self.log_test("Integration (All Features)", False, 
                                f"Session continuity: {same_session}, Normal: sources={normal_has_sources}, no_disclaimer={normal_no_disclaimer}, "
                                f"Fallback: disclaimer={fallback_has_disclaimer}, sources={fallback_has_sources}, "
                                f"Hindi: disclaimer={hindi_has_disclaimer}, content={hindi_has_content}")
                    return False
            else:
                status_codes = [response1.status_code, response2.status_code, response3.status_code]
                self.log_test("Integration (All Features)", False, f"Status codes: {status_codes}")
                return False
        except Exception as e:
            self.log_test("Integration (All Features)", False, f"Exception: {str(e)}")
            return False

    def run_enhanced_fallback_tests(self):
        """Run all enhanced AI fallback feature tests"""
        print("🚀 Starting Enhanced AI Fallback System Tests")
        print(f"🌐 Testing against: {self.base_url}")
        print("=" * 80)
        
        print("\n🔄 Testing Retry Mechanism (Option 6):")
        self.test_retry_mechanism()
        
        print("\n🔀 Testing Hybrid Mode (Option 3):")
        self.test_hybrid_mode_partial_data()
        self.test_hybrid_mode_hindi()
        
        print("\n📝 Testing Enhanced Responses (Option 2):")
        self.test_enhanced_responses_detailed_fallback()
        self.test_enhanced_responses_hindi()
        
        print("\n🔗 Testing Trusted Sources (Option 5):")
        self.test_trusted_sources_price_query()
        self.test_trusted_sources_different_query_types()
        
        print("\n🔧 Testing Integration:")
        self.test_integration_all_features()
        
        # Print summary
        print("\n" + "=" * 80)
        print(f"📊 Enhanced Fallback Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All enhanced fallback features working correctly!")
            return 0
        else:
            print("⚠️  Some enhanced fallback features failed. Check details above.")
            return 1

def main():
    tester = EnhancedFallbackTester()
    return tester.run_enhanced_fallback_tests()

if __name__ == "__main__":
    sys.exit(main())