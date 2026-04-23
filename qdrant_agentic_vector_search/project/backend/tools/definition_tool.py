"""
Definition Tool for CrewAI Agents
Finds statutory definitions of legal terms
"""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from .hybrid_search_tool import HybridSearchTool


class DefinitionInput(BaseModel):
    """Input for definition lookup."""
    term: str = Field(
        ...,
        description="The legal term to define (e.g., 'dwelling unit', 'rent', 'landlord')"
    )
    context: str = Field(
        default="",
        description="Optional context about where the term appears"
    )


class DefinitionTool(BaseTool):
    """Find statutory definitions of legal terms in California housing law."""
    
    name: str = "get_definition"
    description: str = """Find the statutory definition of a legal term in California housing law.
    Use this when a statute uses a term like 'dwelling unit', 'rent', 'landlord', 'tenant', etc.
    and you need to know exactly how California law defines it.
    Example: get_definition("dwelling unit") or get_definition("rent")"""
    
    args_schema: type[BaseModel] = DefinitionInput
    
    search_tool: HybridSearchTool = None
    
    def __init__(self):
        super().__init__()
        self.search_tool = HybridSearchTool()
    
    def _run(self, term: str, context: str = "") -> str:
        """Find the statutory definition."""
        
        # Craft query to find definitions
        query = f'definition of "{term}" California housing law'
        if context:
            query += f" {context}"
        
        # Search for definition statutes
        results = self.search_tool._run(query=query, top_k=3)
        
        if "No relevant statutes found" in results:
            return f"No statutory definition found for '{term}' in California housing law corpus."
        
        return f"Definition of '{term}':\n\n{results}"

