"""RAG pipeline module with OpenAI integration."""

from typing import List, Dict, Any, Optional
import os
from openai import OpenAI
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HousingQARAG:
    """RAG pipeline for answering housing law questions."""
    
    def __init__(
        self,
        vector_store,
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo-preview"
    ):
        """
        Initialize RAG pipeline.
        
        Args:
            vector_store: QdrantVectorStore instance
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: OpenAI model to use
        """
        self.vector_store = vector_store
        self.model = model
        
        # Initialize OpenAI client
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=api_key)
        logger.info(f"Initialized RAG pipeline with model: {model}")
    
    def build_prompt(
        self,
        question: str,
        state: str,
        statute_texts: List[str]
    ) -> str:
        """
        Build prompt following HousingQA format.
        
        Args:
            question: The question to answer
            state: The state for context
            statute_texts: List of statute text excerpts
            
        Returns:
            Formatted prompt string
        """
        # Format statutes
        statutes_section = "\n\n".join([
            f"Statute {i+1}:\n{text}"
            for i, text in enumerate(statute_texts)
        ])
        
        prompt = f"""Consider statutory law for {state} in the year 2021. Read the following statute excerpts which govern housing law in this state, and answer the question below.

Statutes ################## 

{statutes_section}

Question ##################

{question}

Answer "Yes" or "No".

Answer:"""
        
        return prompt
    
    def answer_question(
        self,
        question: str,
        state: str,
        top_k: int = 5,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Answer a housing law question using RAG.
        
        Args:
            question: The question to answer
            state: The state to query about
            top_k: Number of statute chunks to retrieve
            temperature: OpenAI temperature parameter
            
        Returns:
            Dictionary with answer, retrieved chunks, and metadata
        """
        logger.info(f"Answering question for {state}: '{question[:50]}...'")
        
        # Import retriever here to avoid circular imports
        from .retriever import StatuteRetriever
        
        # Retrieve relevant statutes
        retriever = StatuteRetriever(self.vector_store)
        retrieved_chunks = retriever.retrieve(
            query=question,
            state=state,
            top_k=top_k
        )
        
        if not retrieved_chunks:
            logger.warning(f"No relevant statutes found for {state}")
            return {
                'question': question,
                'state': state,
                'answer': "Unable to answer: No relevant statutes found.",
                'retrieved_chunks': [],
                'model': self.model
            }
        
        # Extract statute texts and citations
        statute_texts = [chunk['text'] for chunk in retrieved_chunks]
        citations = [chunk['citation'] for chunk in retrieved_chunks]
        
        # Build prompt
        prompt = self.build_prompt(question, state, statute_texts)
        
        # Call OpenAI API
        try:
            logger.info(f"Calling OpenAI API with model: {self.model}")
            
            # GPT-5 and newer models have different API requirements
            # Check if model is GPT-5 or newer
            is_gpt5_or_newer = 'gpt-5' in self.model.lower() or 'o3' in self.model.lower() or 'o1' in self.model.lower()
            
            api_params = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a legal expert specializing in housing law. Provide accurate answers based on the provided statutes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
            }
            
            # GPT-5 doesn't support custom temperature (only default 1)
            if not is_gpt5_or_newer:
                api_params["temperature"] = temperature
            
            # Use the correct parameter based on model
            if is_gpt5_or_newer:
                api_params["max_completion_tokens"] = 500
            else:
                api_params["max_tokens"] = 500
            
            response = self.client.chat.completions.create(**api_params)
            
            answer = response.choices[0].message.content.strip()
            logger.info("Successfully generated answer")
            
            return {
                'question': question,
                'state': state,
                'answer': answer,
                'retrieved_chunks': retrieved_chunks,
                'citations': citations,
                'model': self.model,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return {
                'question': question,
                'state': state,
                'answer': f"Error generating answer: {str(e)}",
                'retrieved_chunks': retrieved_chunks,
                'citations': citations,
                'model': self.model,
                'error': str(e)
            }
    
    def format_response(self, result: Dict[str, Any]) -> str:
        """
        Format the RAG result into a readable string.
        
        Args:
            result: Result dictionary from answer_question
            
        Returns:
            Formatted response string
        """
        output = []
        output.append(f"Question: {result['question']}")
        output.append(f"State: {result['state']}")
        output.append(f"\nAnswer:\n{result['answer']}")
        
        if result.get('citations'):
            output.append(f"\nRelevant Citations:")
            for i, citation in enumerate(result['citations'], 1):
                output.append(f"  [{i}] {citation}")
        
        if result.get('usage'):
            output.append(f"\nTokens used: {result['usage']['total_tokens']}")
        
        return "\n".join(output)


def answer_housing_question(
    vector_store,
    question: str,
    state: str,
    model: str = "gpt-4-turbo-preview",
    top_k: int = 5
) -> Dict[str, Any]:
    """
    Convenience function to answer a housing law question.
    
    Args:
        vector_store: QdrantVectorStore instance
        question: The question to answer
        state: The state to query about
        model: OpenAI model to use
        top_k: Number of chunks to retrieve
        
    Returns:
        Result dictionary with answer and metadata
    """
    rag = HousingQARAG(vector_store=vector_store, model=model)
    return rag.answer_question(question=question, state=state, top_k=top_k)

