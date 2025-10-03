from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

MODEL_EMBEDDING = os.getenv("MODEL_EMBEDDING")
MODEL_ORCHESTRATOR = os.getenv("MODEL_ORCHESTRATOR")
MODEL_SPECIALIST = os.getenv("MODEL_SPECIALIST")
MODEL_SUMMARIZATION = os.getenv("MODEL_SUMMARIZATION")
SUPABASE_URL=os.getenv("SUPABASE_URL")
SUPABASE_KEY=os.getenv("SUPABASE_KEY")

def get_supabase_client() -> Client:
    """
    Initializes and returns the Supabase client.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase URL and Key must be set in the .env file.")
        
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_openai_embeddings() -> OpenAIEmbeddings:
    """
    Initializes and returns the OpenAI Embeddings model.
    """ 
    return OpenAIEmbeddings(model=MODEL_EMBEDDING)

def get_orchestrator_llm() -> ChatOpenAI:
    """
    Initializes and returns the Gemini LLM for orchestration (fast and cheap).
    """
    return ChatOpenAI(model=MODEL_ORCHESTRATOR)


def get_specialist_llm() -> ChatOpenAI:
    """
    Initializes and returns the Gemini LLM for specialist tasks (powerful).
    """
    return ChatOpenAI(
        model=MODEL_SPECIALIST,
        temperature=0,
        max_retries=2
    )

def get_summarization_llm() -> ChatOpenAI:
    """
    Initializes and returns the Google Gemini LLM for summarization tasks.
    """
    return ChatOpenAI(model=MODEL_SUMMARIZATION)

# Initialize clients
supabase_client = get_supabase_client()
embeddings_model = get_openai_embeddings()
orchestrator_llm = get_orchestrator_llm()
specialist_llm = get_specialist_llm()
summarization_llm = get_summarization_llm()

