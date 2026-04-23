"""
Follow Reference Tool for CrewAI Agents
Follows "except as provided in §" cross-references
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from .hybrid_search_tool import HybridSearchTool


class FollowRefInput(BaseModel):
    """Input for following a statute reference."""
    statute_reference: str = Field(
        ..., 
        description="The statute citation to retrieve (e.g., '§ 1942.5', 'Civil Code § 1946.2')"
    )


class FollowRefTool(BaseTool):
    """Follow cross-references in statutes (e.g., 'except as provided in § 1942.5')."""
    
    name: str = "follow_ref"
    description: str = """Follow a statute cross-reference to retrieve the full text.
    Use this when a statute says 'except as provided in §' or 'see §' or references another section.
    Provide the statute citation and get the full text of that referenced statute.
    Example: follow_ref("§ 1942.5") or follow_ref("Civil Code § 1946.2")"""
    
    args_schema: type[BaseModel] = FollowRefInput
    
    search_tool: HybridSearchTool = None
    
    def __init__(self):
        super().__init__()
        # Use hybrid search to find the referenced statute
        self.search_tool = HybridSearchTool()
    
    def _run(self, statute_reference: str) -> str:
        """Retrieve the referenced statute using hybrid search."""
        
        # Clean up the reference for search
        query = f"California {statute_reference}"
        
        # Use hybrid search to find it
        result = self.search_tool._run(query=query, top_k=1)
        
        if "No relevant statutes found" in result:
            return f"Could not locate {statute_reference}. It may not be in the California housing statutes corpus."
        
        return f"Referenced Statute: {statute_reference}\n\n{result}"

