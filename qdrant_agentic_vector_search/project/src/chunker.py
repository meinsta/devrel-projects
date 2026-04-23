"""Text chunking module using Chonkie for statute processing."""

from typing import Dict, List, Any, Optional, Iterator
from chonkie import TokenChunker, RecursiveChunker
import logging
import json
import os
from pathlib import Path
import ijson

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StatuteChunker:
    """Process statutes - kept as single units without chunking.
    
    According to the HousingQA paper (https://arxiv.org/pdf/2505.03970):
    - Golden passages ARE the statutes themselves (not excerpts)
    - Average statute length: ~349 tokens
    - ~1.84M statutes/passages in the corpus
    - No extra chunking beyond statute level is specified
    
    This class does NOT chunk statutes - each statute is kept as a single unit.
    This ensures that:
    1. Statutes match golden passages exactly (1:1 mapping)
    2. Evaluation works correctly (retrieved chunks = statutes = golden passages)
    3. Matches the paper's approach where each statute is a passage
    
    The chunk_size, chunk_overlap, and chunker_type parameters are kept for
    API compatibility but are not used (statutes are never split).
    """
    
    def __init__(
        self, 
        chunk_size: int = 512, 
        chunk_overlap: int = 0,
        chunker_type: str = "token"
    ):
        """
        Initialize the statute processor.
        
        Note: Per HousingQA paper, statutes are NOT chunked - each statute is kept
        as a single unit. The chunk_size parameter is kept for API compatibility
        but is not used (statutes are never split).
        
        Args:
            chunk_size: Not used - kept for API compatibility
            chunk_overlap: Not used - kept for API compatibility  
            chunker_type: Not used - kept for API compatibility
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunker_type = chunker_type.lower()
        
        # Log the approach
        logger.info("Matching HousingQA paper approach:")
        logger.info("  - Golden passages ARE the statutes themselves (~1.84M statutes)")
        logger.info("  - No chunking: each statute = one passage = one chunk")
        logger.info("  - This ensures evaluation works correctly (statutes match golden passages)")
    
    def chunk_statute(self, statute: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Process a single statute - kept as a single unit (no chunking).
        
        Per HousingQA paper (https://arxiv.org/pdf/2505.03970):
        - Golden passages ARE the statutes themselves
        - No extra chunking beyond statute level
        - Each statute = one passage = one chunk
        
        Args:
            statute: Dictionary containing statute data (idx, citation, state, text, path)
            
        Returns:
            List with single chunk dictionary (the statute itself)
        """
        text = statute.get('text', '')
        
        # Handle empty or very short texts
        if not text or len(text.strip()) < 10:
            logger.warning(f"Skipping empty/short statute: {statute.get('citation', 'unknown')}")
            return []
        
        try:
            # Estimate token count (rough: ~4 chars per token)
            estimated_tokens = len(text) / 4
            
            # Keep statute as single unit - no chunking
            # This matches the paper: statutes are passages, no chunking needed
            chunk_dict = {
                'chunk_id': f"{statute['idx']}_0",
                'chunk_idx': 0,
                'text': text,
                'token_count': int(estimated_tokens),
                'statute_idx': statute['idx'],
                'citation': statute['citation'],
                'state': statute['state'],
                'path': statute.get('path', ''),
            }
            
            return [chunk_dict]
            
        except Exception as e:
            logger.error(f"Error processing statute {statute.get('citation', 'unknown')}: {e}")
            return []
    
    def chunk_statutes(self, statutes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple statutes - each kept as a single unit (no chunking).
        
        Args:
            statutes: List of statute dictionaries
            
        Returns:
            List of all chunks (one chunk per statute)
        """
        logger.info(f"Processing {len(statutes)} statutes (no chunking - each statute = one chunk)...")
        
        all_chunks = []
        processed = 0
        skipped = 0
        
        for statute in statutes:
            chunks = self.chunk_statute(statute)
            if chunks:
                all_chunks.extend(chunks)
                processed += 1
            else:
                skipped += 1
            
            # Log progress periodically
            if (processed + skipped) % 10000 == 0:
                logger.info(f"Processed {processed + skipped} statutes, created {len(all_chunks)} chunks")
        
        logger.info(f"Processing complete: {processed} statutes processed, {skipped} skipped, {len(all_chunks)} total chunks")
        logger.info(f"Note: {len(all_chunks)} chunks = {processed} statutes (1:1 mapping, no chunking)")
        return all_chunks
    
    def save_chunks(self, chunks: List[Dict[str, Any]], filepath: str):
        """
        Save chunks to a JSON file.
        
        Args:
            chunks: List of chunk dictionaries
            filepath: Path to save the chunks file
        """
        logger.info(f"Saving {len(chunks):,} chunks to {filepath}")
        logger.info("This may take several minutes for large datasets...")
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        
        # Use compact JSON (no indentation) for faster writing and smaller file size
        logger.info("Writing chunks to disk (compact format)...")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, separators=(',', ':'))
        
        # Get file size
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"✓ Chunks saved successfully!")
        logger.info(f"  File: {filepath}")
        logger.info(f"  Size: {file_size_mb:.2f} MB")
        logger.info(f"  Chunks: {len(chunks):,}")
    
    @staticmethod
    def load_chunks(filepath: str) -> Optional[List[Dict[str, Any]]]:
        """
        Load chunks from a JSON file (loads entire file into memory).
        For large files, use load_chunks_in_batches instead.
        
        Args:
            filepath: Path to the chunks file
            
        Returns:
            List of chunk dictionaries or None if file doesn't exist
        """
        if not os.path.exists(filepath):
            return None
        
        # Get file size for progress indication
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"Loading chunks from {filepath}")
        logger.info(f"File size: {file_size_mb:.2f} MB - This may take a few minutes...")
        
        # Warn if file is very large
        if file_size_mb > 500:
            logger.warning(f"File is very large ({file_size_mb:.2f} MB). Consider using load_chunks_in_batches() instead.")
        
        try:
            import time
            start_time = time.time()
            with open(filepath, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            elapsed = time.time() - start_time
            logger.info(f"✓ Loaded {len(chunks):,} chunks from cache in {elapsed:.1f} seconds")
            return chunks
        except Exception as e:
            logger.error(f"Error loading chunks from {filepath}: {e}")
            return None
    
    @staticmethod
    def load_chunks_in_batches(filepath: str, batch_size: int = 1000) -> Iterator[List[Dict[str, Any]]]:
        """
        Load chunks from a JSON file in batches using streaming JSON parser.
        This method uses ijson to parse the JSON incrementally, avoiding loading
        the entire file into memory at once.
        
        Args:
            filepath: Path to the chunks file
            batch_size: Number of chunks to yield per batch
            
        Yields:
            Batches of chunk dictionaries
        """
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return
        
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        logger.info(f"Loading chunks from {filepath} in batches")
        logger.info(f"File size: {file_size_mb:.2f} MB")
        logger.info(f"Batch size: {batch_size:,} chunks per batch")
        
        try:
            import time
            start_time = time.time()
            batch = []
            total_loaded = 0
            
            with open(filepath, 'rb') as f:
                # Parse JSON array items incrementally
                # 'item' path tells ijson to yield each item in the root array
                parser = ijson.items(f, 'item')
                
                for chunk in parser:
                    batch.append(chunk)
                    
                    # Yield batch when it reaches batch_size
                    if len(batch) >= batch_size:
                        total_loaded += len(batch)
                        if total_loaded % (batch_size * 10) == 0:
                            elapsed = time.time() - start_time
                            rate = total_loaded / elapsed if elapsed > 0 else 0
                            logger.info(f"Loaded {total_loaded:,} chunks so far... ({elapsed:.1f}s, {rate:.0f} chunks/s)")
                        yield batch
                        batch = []
                
                # Yield remaining chunks in final batch
                if batch:
                    total_loaded += len(batch)
                    elapsed = time.time() - start_time
                    logger.info(f"✓ Loaded {total_loaded:,} chunks from cache in {elapsed:.1f} seconds")
                    yield batch
                    
        except Exception as e:
            logger.error(f"Error loading chunks from {filepath}: {e}")
            raise


def create_chunks_from_statutes(statutes: List[Dict[str, Any]], 
                                chunk_size: int = 512, 
                                chunk_overlap: int = 0,
                                chunker_type: str = "token") -> List[Dict[str, Any]]:
    """
    Convenience function to chunk statutes.
    
    Per HousingQA paper: statutes are passages (golden passages). Each statute
    is kept as a single chunk unless it exceeds chunk_size.
    
    Args:
        statutes: List of statute dictionaries
        chunk_size: Maximum tokens per chunk (default 512 to accommodate avg ~349 tokens)
        chunk_overlap: Number of overlapping tokens (default 0 - statutes kept as units)
        chunker_type: Type of chunker ("token" or "recursive").
                     Only used if a statute exceeds chunk_size.
        
    Returns:
        List of chunk dictionaries (usually 1 chunk per statute)
    """
    chunker = StatuteChunker(
        chunk_size=chunk_size, 
        chunk_overlap=chunk_overlap,
        chunker_type=chunker_type
    )
    return chunker.chunk_statutes(statutes)

