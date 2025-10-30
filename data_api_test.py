#!/usr/bin/env python3
"""
Test data.gov.in API integration independently of LLM
"""
import requests
import json

def test_data_gov_api():
    """Test if data.gov.in API is working"""
    print("🔍 Testing data.gov.in API integration...")
    
    # Test the specific dataset mentioned in the code
    resource_id = "9ef84268-d588-465a-a308-a864a43d0070"
    api_key = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"
    
    url = f"https://api.data.gov.in/resource/{resource_id}"
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": 10
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        print(f"📡 API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            records = data.get("records", [])
            print(f"✅ Successfully fetched {len(records)} records")
            
            if records:
                print("📋 Sample record fields:")
                sample = records[0]
                for key in list(sample.keys())[:8]:  # Show first 8 fields
                    print(f"   - {key}: {sample.get(key, 'N/A')}")
                return True
            else:
                print("⚠️  No records found in response")
                return False
        else:
            print(f"❌ API request failed: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Exception occurred: {str(e)}")
        return False

def test_dataset_search():
    """Test the dataset search logic"""
    print("\n🔍 Testing dataset search logic...")
    
    # Import the search function from the backend
    import sys
    sys.path.append('/app/backend')
    
    try:
        from server import DataService
        
        # Test various queries
        test_queries = [
            "rice prices",
            "potato price trends", 
            "wheat prices in Maharashtra",
            "मूल्य दिखाएं",  # Show prices in Hindi
            "commodity prices today",
            "mandi prices for vegetables"
        ]
        
        data_service = DataService()
        
        for query in test_queries:
            print(f"\n📝 Testing query: '{query}'")
            # Use asyncio to run the async function
            import asyncio
            datasets = asyncio.run(data_service.search_datasets(query))
            print(f"   Found {len(datasets)} relevant datasets")
            
            for dataset in datasets:
                print(f"   - {dataset['title']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing dataset search: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Testing AgriClimate Data Integration (without LLM)")
    print("=" * 60)
    
    api_success = test_data_gov_api()
    search_success = test_dataset_search()
    
    print("\n" + "=" * 60)
    if api_success and search_success:
        print("✅ Data integration tests passed!")
        print("🔍 Issue is with LLM budget limit, not data fetching")
    else:
        print("❌ Data integration issues found")