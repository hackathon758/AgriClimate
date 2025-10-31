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
import google.generativeai as genai
import httpx
import pandas as pd
import io
import asyncio
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured successfully")
else:
    logger.warning("No Gemini API key found in environment")

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

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
        "title": "Current Daily Price of Various Commodities from Various Markets (Mandi)",
        "ministry": "Ministry of Agriculture & Farmers Welfare",
        "description": "Current daily prices of agricultural commodities including vegetables, fruits, and crops from mandis across India. Includes state-wise, district-wise, and market-wise price data for various commodities."
    }
]

# Trusted reference sources for fallback responses
TRUSTED_SOURCES = {
    "agriculture": [
        {
            "title": "Ministry of Agriculture & Farmers Welfare",
            "url": "https://agricoop.nic.in/",
            "description": "Official portal for agricultural statistics and schemes"
        },
        {
            "title": "India Meteorological Department",
            "url": "https://mausam.imd.gov.in/",
            "description": "Weather forecasts and agricultural advisories"
        },
        {
            "title": "National Portal of India - Agriculture",
            "url": "https://www.india.gov.in/topics/agriculture",
            "description": "Comprehensive agricultural information and resources"
        }
    ],
    "prices": [
        {
            "title": "Agmarknet - MANDI Portal",
            "url": "https://agmarknet.gov.in/",
            "description": "Real-time agricultural commodity prices from mandis"
        },
        {
            "title": "Department of Consumer Affairs",
            "url": "https://consumeraffairs.nic.in/",
            "description": "Price monitoring and consumer information"
        }
    ],
    "crops": [
        {
            "title": "Directorate of Economics & Statistics",
            "url": "https://eands.dacnet.nic.in/",
            "description": "Crop production statistics and agricultural census"
        },
        {
            "title": "Indian Council of Agricultural Research",
            "url": "https://icar.org.in/",
            "description": "Research findings and best practices"
        }
    ],
    "climate": [
        {
            "title": "India Meteorological Department",
            "url": "https://mausam.imd.gov.in/",
            "description": "Climate data and weather predictions"
        },
        {
            "title": "Ministry of Earth Sciences",
            "url": "https://www.moes.gov.in/",
            "description": "Climate research and monsoon forecasts"
        }
    ],
    "general": [
        {
            "title": "Data.gov.in",
            "url": "https://data.gov.in/",
            "description": "India's open government data platform"
        },
        {
            "title": "PM-KISAN Portal",
            "url": "https://pmkisan.gov.in/",
            "description": "Direct income support for farmers"
        }
    ]
}

class DataService:
    """Service to fetch and process data from data.gov.in"""
    
    @staticmethod
    async def fetch_dataset(resource_id: str, filters: Dict = None, limit: int = 100, max_retries: int = 3) -> List[Dict]:
        """Fetch data from data.gov.in API with retry mechanism"""
        retry_delays = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s
        
        for attempt in range(max_retries):
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
                        records = data.get("records", [])
                        if attempt > 0:
                            logger.info(f"✅ Successfully fetched data on retry attempt {attempt + 1}")
                        return records
                    else:
                        logger.warning(f"API error on attempt {attempt + 1}: {response.status_code}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delays[attempt])
                        
            except Exception as e:
                logger.error(f"Error fetching dataset (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delays[attempt]} seconds...")
                    await asyncio.sleep(retry_delays[attempt])
        
        logger.error(f"Failed to fetch data after {max_retries} attempts")
        return []
    
    @staticmethod
    async def search_datasets(query: str) -> List[Dict[str, str]]:
        """Search for relevant datasets based on query with broad matching"""
        query_lower = query.lower()
        relevant = []
        
        # Comprehensive keywords map covering agricultural topics
        keywords_map = {
            # Price-related keywords
            "price": ["price", "commodity", "mandi", "market"],
            "cost": ["price", "commodity", "mandi", "market"],
            "rate": ["price", "commodity", "mandi", "market"],
            "mandi": ["price", "commodity", "mandi", "market"],
            "market": ["price", "commodity", "mandi", "market"],
            "commodity": ["price", "commodity", "mandi", "market"],
            # Crop-related keywords
            "crop": ["production", "yield", "commodity", "price"],
            "agriculture": ["production", "yield", "farming", "commodity", "price"],
            "farming": ["production", "yield", "commodity", "price"],
            "production": ["production", "yield", "commodity"],
            # Specific crops (common vegetables and grains)
            "rice": ["commodity", "price", "production"],
            "wheat": ["commodity", "price", "production"],
            "potato": ["commodity", "price", "production"],
            "onion": ["commodity", "price", "production"],
            "tomato": ["commodity", "price", "production"],
            "vegetable": ["commodity", "price", "production"],
            "grain": ["commodity", "price", "production"],
            "fruit": ["commodity", "price", "production"],
            # Hindi equivalents
            "मूल्य": ["price", "commodity", "mandi", "market"],  # price
            "कीमत": ["price", "commodity", "mandi", "market"],  # price/cost
            "मंडी": ["price", "commodity", "mandi", "market"],  # mandi
            "फसल": ["production", "yield", "commodity", "price"],  # crop
            "कृषि": ["production", "yield", "commodity", "price"],  # agriculture
            "चावल": ["commodity", "price", "production"],  # rice
            "गेहूं": ["commodity", "price", "production"],  # wheat
            "आलू": ["commodity", "price", "production"],  # potato
            "प्याज": ["commodity", "price", "production"],  # onion
            "टमाटर": ["commodity", "price", "production"],  # tomato
            "सब्जी": ["commodity", "price", "production"],  # vegetable
        }
        
        # Search logic with scoring
        for dataset in KNOWN_DATASETS:
            score = 0
            dataset_text = f"{dataset['title'].lower()} {dataset['description'].lower()}"
            
            # Check keyword matches
            for keyword, related in keywords_map.items():
                if keyword in query_lower:
                    if any(r in dataset_text for r in related):
                        score += 2
            
            # Check if any word from query is in dataset title or description
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3:  # Only consider words longer than 3 characters
                    if word in dataset_text:
                        score += 1
            
            if score > 0:
                relevant.append(dataset)
        
        # If no datasets matched, check if query is completely outside agricultural domain
        # For non-agricultural queries, return empty to trigger AI fallback
        if not relevant:
            # Define clearly non-agricultural terms that should trigger fallback
            non_agricultural_terms = [
                'weather', 'forecast', 'quantum', 'physics', 'computing', 'technology',
                'artificial intelligence', 'machine learning', 'software', 'programming',
                'mathematics', 'chemistry', 'biology', 'history', 'geography', 'politics',
                'entertainment', 'sports', 'music', 'movies', 'books', 'literature',
                # Hindi terms
                'मौसम', 'भविष्यवाणी', 'क्वांटम', 'भौतिकी', 'कंप्यूटिंग', 'तकनीक',
                'कृत्रिम बुद्धिमत्ता', 'मशीन लर्निंग', 'सॉफ्टवेयर', 'प्रोग्रामिंग',
                'गणित', 'रसायन', 'जीवविज्ञान', 'इतिहास', 'भूगोल', 'राजनीति'
            ]
            
            # Check if query contains clearly non-agricultural terms
            is_non_agricultural = any(term in query_lower for term in non_agricultural_terms)
            
            if is_non_agricultural:
                logger.info(f"Query '{query}' identified as non-agricultural. Triggering AI fallback.")
                return []  # Return empty to trigger AI fallback
            else:
                logger.info(f"No specific match for query '{query}', using all datasets as fallback")
                relevant = KNOWN_DATASETS.copy()
        
        return relevant[:3]  # Return top 3 relevant datasets

class QueryProcessor:
    """Process natural language queries using Gemini"""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
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
        
        prompt = f"{system_prompt}\n\nAnalyze this {language} question: {question}"
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            intent = json.loads(response.text)
            return intent
        except Exception as e:
            logger.error(f"Error extracting query intent: {str(e)}")
            return {"topic": question, "query_type": "general"}

class AnswerGenerator:
    """Generate answers with source citations"""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    @staticmethod
    def get_relevant_sources(question: str) -> List[Dict[str, str]]:
        """Get relevant trusted sources based on query topic"""
        question_lower = question.lower()
        relevant_sources = []
        
        # Determine query topic and add relevant sources
        if any(word in question_lower for word in ['price', 'cost', 'rate', 'mandi', 'market', 'मूल्य', 'कीमत', 'मंडी']):
            relevant_sources.extend(TRUSTED_SOURCES['prices'])
        
        if any(word in question_lower for word in ['crop', 'production', 'yield', 'farming', 'फसल', 'उत्पादन']):
            relevant_sources.extend(TRUSTED_SOURCES['crops'])
        
        if any(word in question_lower for word in ['weather', 'climate', 'rainfall', 'monsoon', 'मौसम', 'जलवायु', 'बारिश']):
            relevant_sources.extend(TRUSTED_SOURCES['climate'])
        
        if any(word in question_lower for word in ['agriculture', 'agricultural', 'farming', 'कृषि']):
            relevant_sources.extend(TRUSTED_SOURCES['agriculture'])
        
        # Always add general sources
        relevant_sources.extend(TRUSTED_SOURCES['general'])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_sources = []
        for source in relevant_sources:
            if source['url'] not in seen:
                seen.add(source['url'])
                unique_sources.append(source)
        
        return unique_sources[:5]  # Return top 5 most relevant sources
    
    async def generate_answer(self, question: str, data_context: List[Dict], records_data: List[Dict], language: str) -> str:
        """Generate natural language answer from live data only"""
        lang_instruction = "Answer in Hindi (हिंदी में उत्तर दें)" if language == "hi" else "Answer in English"
        
        system_prompt = f"""You are an agricultural and climate data expert for India. 
Analyze and answer questions based ONLY on the live data provided from data.gov.in.
{lang_instruction}.

Guidelines:
- Use ONLY the data provided - do not add information from general knowledge
- Be precise and cite specific numbers, states, and values from the actual data
- If data shows commodity prices, mention states, markets, and price ranges
- Provide actionable insights for policymakers based on the data
- Keep answers concise but comprehensive
- If the data doesn't fully answer the question, clearly state what information is missing"""
        
        # Format data context with actual records
        context_text = "Live data from data.gov.in:\n\n"
        for idx, item in enumerate(data_context, 1):
            context_text += f"{idx}. {item}\n"
        
        # Add sample records for detailed analysis
        if records_data:
            context_text += "\nSample data records for analysis:\n"
            for idx, record in enumerate(records_data[:10], 1):  # Include up to 10 records
                context_text += f"\nRecord {idx}: {record}\n"
        
        prompt = f"{system_prompt}\n\nQuestion: {question}\n\n{context_text}"
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating answer: {str(e)}")
            return f"Unable to generate answer due to error: {str(e)}"
    
    async def generate_hybrid_answer(self, question: str, partial_data: List[Dict], partial_records: List[Dict], language: str) -> tuple:
        """Generate hybrid answer combining partial live data with AI knowledge"""
        lang_instruction = "Answer in Hindi (हिंदी में उत्तर दें)" if language == "hi" else "Answer in English"
        
        disclaimer_en = "ℹ️ Hybrid Response: Combining available live data with general knowledge for a comprehensive answer.\n\n"
        disclaimer_hi = "ℹ️ हाइब्रिड प्रतिक्रिया: व्यापक उत्तर के लिए उपलब्ध लाइव डेटा को सामान्य ज्ञान के साथ जोड़ना।\n\n"
        disclaimer = disclaimer_hi if language == "hi" else disclaimer_en
        
        system_prompt = f"""You are an agricultural and climate expert for India. 
You have PARTIAL live data from data.gov.in, but not complete information to fully answer the question.

Your task:
1. First, analyze and present the LIVE DATA that IS available (mark this section clearly)
2. Then, supplement with general knowledge to provide a complete answer (mark this section clearly)
3. Be transparent about which parts are from live data vs general knowledge
{lang_instruction}.

Guidelines:
- Clearly separate live data insights from general knowledge
- Use phrases like "Based on available live data..." and "From general knowledge..."
- Provide practical examples and seasonal trends
- Include typical price ranges, production patterns, or climate information
- Offer actionable tips for farmers or policymakers
- Keep the answer comprehensive but well-structured"""
        
        # Format partial data context
        context_text = "Partial live data available from data.gov.in:\n\n"
        for idx, item in enumerate(partial_data, 1):
            context_text += f"{idx}. {item}\n"
        
        if partial_records:
            context_text += "\nSample records from available data:\n"
            for idx, record in enumerate(partial_records[:5], 1):
                context_text += f"\nRecord {idx}: {record}\n"
        
        prompt = f"{system_prompt}\n\nQuestion: {question}\n\n{context_text}"
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            # Get relevant trusted sources
            trusted_sources = self.get_relevant_sources(question)
            
            return disclaimer + response.text, trusted_sources
        except Exception as e:
            logger.error(f"Error generating hybrid answer: {str(e)}")
            error_msg = "क्षमा करें, उत्तर उत्पन्न करने में त्रुटि।" if language == "hi" else "Error generating answer."
            return disclaimer + error_msg, []
    
    async def generate_fallback_answer(self, question: str, language: str, reason: str = "data_unavailable") -> tuple:
        """Generate enhanced answer using general knowledge with trusted sources"""
        lang_instruction = "Answer in Hindi (हिंदी में उत्तर दें)" if language == "hi" else "Answer in English"
        
        disclaimer_en = "⚠️ Note: Live data from data.gov.in is currently unavailable. This answer is based on general knowledge and trusted sources.\n\n"
        disclaimer_hi = "⚠️ नोट: data.gov.in से लाइव डेटा वर्तमान में उपलब्ध नहीं है। यह उत्तर सामान्य ज्ञान और विश्वसनीय स्रोतों पर आधारित है।\n\n"
        disclaimer = disclaimer_hi if language == "hi" else disclaimer_en
        
        system_prompt = f"""You are an agricultural and climate expert for India with extensive knowledge about:
- Agricultural commodity prices and market trends
- Crop production and seasonal patterns
- State-wise agricultural statistics
- Government agricultural policies and initiatives
- Climate and weather patterns affecting agriculture
- Best practices and practical farming tips

Since live data from data.gov.in is not available right now, provide a COMPREHENSIVE and ENHANCED answer based on your general knowledge.
{lang_instruction}.

Guidelines for ENHANCED responses:
- Provide detailed, actionable information with practical examples
- Include seasonal trends and typical patterns (e.g., "Prices typically rise during...")
- Add practical tips for farmers or policymakers
- Mention typical price ranges or production statistics from recent years
- Include regional variations if relevant (e.g., "In Maharashtra..." vs "In Punjab...")
- Suggest best practices and government schemes when applicable
- Provide context about factors affecting the topic (weather, market demand, etc.)
- Make answers comprehensive but well-structured with clear sections
- End with a note about checking official sources for latest real-time data"""
        
        prompt = f"{system_prompt}\n\nQuestion: {question}"
        
        # Get relevant trusted sources for this query (do this first, before AI call)
        trusted_sources = self.get_relevant_sources(question)
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            # Return both answer and sources
            return disclaimer + response.text, trusted_sources
        except Exception as e:
            logger.error(f"Error generating fallback answer: {str(e)}")
            error_msg = "क्षमा करें, इस समय उत्तर उत्पन्न करने में असमर्थ।" if language == "hi" else "Sorry, unable to generate answer at this time."
            # Still return trusted sources even if AI generation fails
            return disclaimer + error_msg, trusted_sources

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
        logger.info(f"Found {len(relevant_datasets)} relevant datasets for query: '{request.question}'")
        
        if not relevant_datasets:
            # No relevant datasets found - use AI fallback with general knowledge
            logger.info("No relevant datasets found. Generating enhanced fallback answer with trusted sources.")
            fallback_answer, trusted_sources = await answer_generator.generate_fallback_answer(
                request.question,
                request.language,
                reason="no_datasets"
            )
            
            assistant_message = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=fallback_answer,
                sources=trusted_sources
            )
            doc = assistant_message.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.chat_messages.insert_one(doc)
            
            return ChatResponse(
                session_id=session_id,
                answer=fallback_answer,
                sources=trusted_sources,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Step 3: Fetch actual data from data.gov.in APIs (with retry mechanism)
        data_context = []
        sources = []
        all_records = []
        
        for dataset in relevant_datasets:
            try:
                logger.info(f"Fetching data for dataset: {dataset['title']}")
                records = await data_service.fetch_dataset(dataset["resource_id"], limit=100)
                if records:
                    logger.info(f"Successfully fetched {len(records)} records from {dataset['title']}")
                    # Store actual records for detailed analysis
                    all_records.extend(records[:20])  # Include up to 20 records per dataset
                    
                    # Summarize dataset info
                    data_summary = f"{dataset['title']}: {len(records)} records fetched from data.gov.in"
                    if records:
                        sample = records[0]
                        data_summary += f". Fields: {', '.join(list(sample.keys())[:8])}"
                    data_context.append(data_summary)
                    
                    sources.append({
                        "title": dataset["title"],
                        "ministry": dataset["ministry"],
                        "url": f"https://data.gov.in/resource/{dataset['resource_id']}",
                        "records": str(len(records))
                    })
            except Exception as e:
                logger.error(f"Error fetching {dataset['title']}: {str(e)}")
        
        # Check if we got any actual data
        if not data_context or not all_records:
            logger.warning(f"No data fetched from any dataset after retries. Generating enhanced fallback answer.")
            fallback_answer, trusted_sources = await answer_generator.generate_fallback_answer(
                request.question,
                request.language,
                reason="fetch_failed"
            )
            
            assistant_message = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=fallback_answer,
                sources=trusted_sources
            )
            doc = assistant_message.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.chat_messages.insert_one(doc)
            
            return ChatResponse(
                session_id=session_id,
                answer=fallback_answer,
                sources=trusted_sources,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Check if we have partial data (less than expected)
        # If we have some data but it seems limited, use hybrid mode
        if len(all_records) < 5:  # Threshold for "partial data"
            logger.info(f"Limited data available ({len(all_records)} records). Using hybrid mode.")
            hybrid_answer, trusted_sources = await answer_generator.generate_hybrid_answer(
                request.question,
                data_context,
                all_records,
                request.language
            )
            
            # Combine live data sources with trusted reference sources
            combined_sources = sources + trusted_sources[:3]  # Add top 3 trusted sources
            
            assistant_message = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=hybrid_answer,
                sources=combined_sources
            )
            doc = assistant_message.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.chat_messages.insert_one(doc)
            
            return ChatResponse(
                session_id=session_id,
                answer=hybrid_answer,
                sources=combined_sources,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
        
        # Step 4: Generate answer using Gemini with live data ONLY
        answer = await answer_generator.generate_answer(
            request.question,
            data_context,
            all_records,
            request.language
        )
        
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