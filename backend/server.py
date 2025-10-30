from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
import httpx
import pandas as pd
import io
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Models
class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str  # 'user' or 'assistant'
    content: str
    sources: Optional[List[Dict[str, str]]] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    language: str = "en"  # en or hi

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[Dict[str, str]]
    timestamp: str

class DatasetInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    source: str
    url: str
    ministry: str
    last_updated: Optional[str] = None

# Data.gov.in API Configuration
DATA_GOV_API = "https://api.data.gov.in/resource"
DATA_GOV_KEY = "579b464db66ec23bdd000001cdd3946e44ce4aad7209ff7b23ac571b"  # Public demo key

# Agriculture & Climate Datasets from data.gov.in
KNOWN_DATASETS = [
    {
        "resource_id": "9ef84268-d588-465a-a308-a864a43d0070",
        "title": "State-wise Agricultural Production",
        "ministry": "Ministry of Agriculture & Farmers Welfare",
        "description": "State and crop-wise agricultural production data"
    },
    {
        "resource_id": "696a1b36-a7d6-406a-9cd3-06d3e55de3e0",
        "title": "Rainfall Statistics",
        "ministry": "India Meteorological Department",
        "description": "State-wise rainfall data and patterns"
    },
    {
        "resource_id": "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69",
        "title": "Crop Yield Data",
        "ministry": "Ministry of Agriculture & Farmers Welfare",
        "description": "Crop-wise yield statistics across states"
    }
]

class DataService:
    """Service to fetch and process data from data.gov.in"""
    
    @staticmethod
    async def fetch_dataset(resource_id: str, filters: Dict = None, limit: int = 100) -> List[Dict]:
        """Fetch data from data.gov.in API"""
        try:
            params = {
                "api-key": DATA_GOV_KEY,
                "format": "json",
                "limit": limit
            }
            if filters:
                params["filters"] = filters
                
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{DATA_GOV_API}/{resource_id}",
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("records", [])
                else:
                    logger.error(f"API error: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching dataset: {str(e)}")
            return []
    
    @staticmethod
    async def search_datasets(query: str) -> List[Dict[str, str]]:
        """Search for relevant datasets based on query"""
        query_lower = query.lower()
        relevant = []
        
        keywords_map = {
            "crop": ["production", "yield"],
            "rain": ["rainfall", "precipitation"],
            "agriculture": ["production", "yield", "farming"],
            "climate": ["rainfall", "temperature"],
            "फसल": ["production", "yield"],  # Hindi: crop
            "बारिश": ["rainfall"],  # Hindi: rain
            "कृषि": ["production", "yield"]  # Hindi: agriculture
        }
        
        for dataset in KNOWN_DATASETS:
            score = 0
            for keyword, related in keywords_map.items():
                if keyword in query_lower:
                    if any(r in dataset["title"].lower() or r in dataset["description"].lower() for r in related):
                        score += 1
            
            if score > 0 or any(word in dataset["title"].lower() for word in query_lower.split()):
                relevant.append(dataset)
        
        return relevant[:3]  # Return top 3 relevant datasets

class QueryProcessor:
    """Process natural language queries using Gemini"""
    
    def __init__(self):
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
    
    async def extract_query_intent(self, question: str, language: str) -> Dict[str, Any]:
        """Extract structured intent from natural language question"""
        system_prompt = """You are a query analyzer for agricultural and climate data. 
Extract key information from user questions:
- Main topic (agriculture, climate, rainfall, crops, etc.)
- Location/State mentioned
- Time period
- Specific metrics requested
- Query type (comparison, trend, statistics, top-N)

Respond in JSON format with: {"topic": "...", "location": "...", "time_period": "...", "metrics": [...], "query_type": "..."}"""
        
        chat = LlmChat(
            api_key=self.llm_key,
            session_id="query_processor",
            system_message=system_prompt
        ).with_model("gemini", "gemini-2.5-pro")
        
        user_msg = UserMessage(text=f"Analyze this {language} question: {question}")
        response = await chat.send_message(user_msg)
        
        try:
            import json
            intent = json.loads(response)
            return intent
        except:
            return {"topic": question, "query_type": "general"}

class AnswerGenerator:
    """Generate answers with source citations"""
    
    def __init__(self):
        self.llm_key = os.environ.get('EMERGENT_LLM_KEY')
    
    async def generate_answer(self, question: str, data_context: List[Dict], language: str) -> str:
        """Generate natural language answer from data"""
        lang_instruction = "Answer in Hindi (हिंदी में उत्तर दें)" if language == "hi" else "Answer in English"
        
        system_prompt = f"""You are an agricultural and climate data expert for India. 
Provide accurate, policy-relevant answers based on the provided data.
{lang_instruction}.

Guidelines:
- Be precise and cite specific numbers from the data
- Highlight trends and patterns
- Provide actionable insights for policymakers
- Keep answers concise but comprehensive
- If data is insufficient, acknowledge limitations"""
        
        # Format data context
        context_text = "Data available:\n"
        for idx, item in enumerate(data_context, 1):
            context_text += f"{idx}. {item}\n"
        
        chat = LlmChat(
            api_key=self.llm_key,
            session_id="answer_generator",
            system_message=system_prompt
        ).with_model("gemini", "gemini-2.5-pro")
        
        user_msg = UserMessage(text=f"Question: {question}\n\n{context_text}")
        response = await chat.send_message(user_msg)
        
        return response

# Initialize services
data_service = DataService()
query_processor = QueryProcessor()
answer_generator = AnswerGenerator()

@api_router.get("/")
async def root():
    return {"message": "Agri-Climate Q&A System", "status": "operational"}

@api_router.post("/chat/query", response_model=ChatResponse)
async def process_query(request: ChatRequest):
    """Process a natural language query about agricultural/climate data"""
    try:
        # Generate or use existing session ID
        session_id = request.session_id or str(uuid.uuid4())
        
        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            role="user",
            content=request.question
        )
        doc = user_message.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(doc)
        
        # Step 1: Understand query intent
        intent = await query_processor.extract_query_intent(request.question, request.language)
        logger.info(f"Query intent: {intent}")
        
        # Step 2: Search for relevant datasets
        relevant_datasets = await data_service.search_datasets(request.question)
        
        if not relevant_datasets:
            # Fallback response
            answer = "मुझे खेद है, मैं इस प्रश्न के लिए प्रासंगिक डेटा नहीं ढूंढ पाया।" if request.language == "hi" else "I apologize, but I couldn't find relevant data for this question."
            sources = []
        else:
            # Step 3: Fetch actual data from APIs
            data_context = []
            sources = []
            
            for dataset in relevant_datasets:
                try:
                    records = await data_service.fetch_dataset(dataset["resource_id"], limit=50)
                    if records:
                        # Summarize data for context
                        data_summary = f"{dataset['title']}: {len(records)} records available"
                        if records:
                            sample = records[0]
                            data_summary += f". Sample fields: {', '.join(list(sample.keys())[:5])}"
                        data_context.append(data_summary)
                        
                        sources.append({
                            "title": dataset["title"],
                            "ministry": dataset["ministry"],
                            "url": f"https://data.gov.in/resource/{dataset['resource_id']}",
                            "records": len(records)
                        })
                except Exception as e:
                    logger.error(f"Error fetching {dataset['title']}: {str(e)}")
            
            # Step 4: Generate answer using Gemini
            if data_context:
                answer = await answer_generator.generate_answer(
                    request.question,
                    data_context,
                    request.language
                )
            else:
                answer = "डेटा लाते समय त्रुटि हुई। कृपया बाद में पुनः प्रयास करें।" if request.language == "hi" else "Error fetching data. Please try again later."
        
        # Save assistant message with sources
        assistant_message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=answer,
            sources=sources
        )
        doc = assistant_message.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        await db.chat_messages.insert_one(doc)
        
        return ChatResponse(
            session_id=session_id,
            answer=answer,
            sources=sources,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session"""
    try:
        messages = await db.chat_messages.find(
            {"session_id": session_id},
            {"_id": 0}
        ).sort("timestamp", 1).to_list(1000)
        
        return {"session_id": session_id, "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/datasets")
async def get_datasets():
    """List available datasets"""
    return {
        "datasets": KNOWN_DATASETS,
        "total": len(KNOWN_DATASETS)
    }

@api_router.get("/health")
async def health_check():
    """System health check"""
    try:
        # Check MongoDB
        await db.command("ping")
        mongo_status = "healthy"
    except:
        mongo_status = "unhealthy"
    
    return {
        "status": "operational",
        "services": {
            "mongodb": mongo_status,
            "gemini": "configured",
            "data_api": "available"
        }
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()