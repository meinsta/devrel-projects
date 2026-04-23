"""Data loading module for HousingQA dataset."""

from typing import Dict, List, Any
from datasets import load_dataset
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HousingQADataLoader:
    """Load and process the HousingQA statutes dataset."""
    
    def __init__(self):
        self.dataset = None
        
    def load_statutes(self) -> List[Dict[str, Any]]:
        """
        Load the statutes split from HousingQA dataset.
        
        Returns:
            List of statute dictionaries with fields: idx, citation, state, text, path
        """
        logger.info("Loading HousingQA statutes dataset from HuggingFace...")
        
        try:
            # Load the statutes corpus split
            # Note: trust_remote_code=True is required for this dataset
            self.dataset = load_dataset(
                "reglab/housing_qa", 
                "statutes", 
                split="corpus",
                trust_remote_code=True
            )
            logger.info(f"Successfully loaded {len(self.dataset)} statutes")
            
            # Convert to list of dictionaries
            statutes = []
            for item in self.dataset:
                statute = {
                    'idx': item['idx'],
                    'citation': item['citation'],
                    'state': item['state'],
                    'text': item['text'],
                    'path': item['path']
                }
                statutes.append(statute)
            
            return statutes
            
        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            raise
    
    def get_statutes_by_state(self, state: str) -> List[Dict[str, Any]]:
        """
        Get all statutes for a specific state.
        
        Args:
            state: State name to filter by
            
        Returns:
            List of statute dictionaries for the specified state
        """
        if self.dataset is None:
            self.load_statutes()
        
        filtered = [s for s in self.dataset if s['state'] == state]
        logger.info(f"Found {len(filtered)} statutes for {state}")
        return filtered
    
    def get_unique_states(self) -> List[str]:
        """
        Get list of unique states in the dataset.
        
        Returns:
            Sorted list of unique state names
        """
        if self.dataset is None:
            self.load_statutes()
        
        states = sorted(set(s['state'] for s in self.dataset if s['state']))
        logger.info(f"Found {len(states)} unique states")
        return states


    def load_questions(self, split: str = "test") -> List[Dict[str, Any]]:
        """
        Load questions from the HousingQA dataset.
        
        Args:
            split: Dataset split to load ('test', 'train', 'validation')
            
        Returns:
            List of question dictionaries with fields: idx, state, question, answer, statutes, etc.
        """
        logger.info(f"Loading HousingQA questions dataset (split: {split})...")
        
        try:
            questions_dataset = load_dataset(
                "reglab/housing_qa",
                "questions",
                split=split,
                trust_remote_code=True
            )
            logger.info(f"Successfully loaded {len(questions_dataset)} questions")
            
            # Convert to list of dictionaries
            questions = []
            for item in questions_dataset:
                question = {
                    'idx': item['idx'],
                    'state': item['state'],
                    'question': item['question'],
                    'answer': item['answer'],
                    'question_group': item.get('question_group', None),
                    'statutes': item.get('statutes', []),  # List of relevant statute references
                    'original_question': item.get('original_question', None),
                    'caveats': item.get('caveats', None)
                }
                questions.append(question)
            
            return questions
            
        except Exception as e:
            logger.error(f"Error loading questions: {e}")
            raise


def load_housing_statutes() -> List[Dict[str, Any]]:
    """
    Convenience function to load all housing statutes.
    
    Returns:
        List of statute dictionaries
    """
    loader = HousingQADataLoader()
    return loader.load_statutes()


def load_housing_questions(split: str = "test") -> List[Dict[str, Any]]:
    """
    Convenience function to load housing questions.
    
    Args:
        split: Dataset split ('test', 'train', 'validation')
        
    Returns:
        List of question dictionaries
    """
    loader = HousingQADataLoader()
    return loader.load_questions(split=split)

