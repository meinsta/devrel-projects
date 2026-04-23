"""
Local Rule Tool for CrewAI Agents
Flags local rent control and just cause ordinances
"""

from typing import ClassVar, Dict, Any
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class LocalRuleInput(BaseModel):
    """Input for local rule check."""
    city: str = Field(..., description="City name (e.g., 'Los Angeles', 'San Francisco', 'Oakland')")
    issue: str = Field(default="", description="Specific issue (e.g., 'eviction', 'rent increase')")


class LocalRuleTool(BaseTool):
    """Check for local rent control and just cause ordinances in California cities."""
    
    name: str = "check_local_rules"
    description: str = """Check if a California city has stricter local rent control or just cause eviction ordinances.
    Use this when the client's property is in a specific city to flag potential local law overlays.
    Returns whether local rules exist and if they're stricter than state law.
    Example: check_local_rules("Los Angeles", "eviction")"""
    
    args_schema: type[BaseModel] = LocalRuleInput
    
    # Simplified local rule database (MVP for major cities)
    LOCAL_RULES: ClassVar[Dict[str, Any]] = {
        "los angeles": {
            "rent_control": True,
            "just_cause": True,
            "stricter_than_state": True,
            "key_ordinances": ["LAMC § 151.09 (Just Cause)", "RSO (Rent Stabilization)"],
            "notes": "LA requires just cause for eviction in rent-controlled units. Additional notice requirements and relocation assistance may apply."
        },
        "san francisco": {
            "rent_control": True,
            "just_cause": True,
            "stricter_than_state": True,
            "key_ordinances": ["SF Rent Ordinance § 37.9", "Just Cause Eviction"],
            "notes": "SF has strict rent control and just cause requirements. Ellis Act and owner move-in have specific rules."
        },
        "oakland": {
            "rent_control": True,
            "just_cause": True,
            "stricter_than_state": True,
            "key_ordinances": ["OMC § 8.22 (Just Cause)", "Rent Adjustment Ordinance"],
            "notes": "Oakland requires just cause and has rent control. Relocation assistance required for no-fault evictions."
        },
        "berkeley": {
            "rent_control": True,
            "just_cause": True,
            "stricter_than_state": True,
            "key_ordinances": ["BMC § 13.76 (Rent Stabilization)"],
            "notes": "Berkeley has strong tenant protections including rent control and just cause requirements."
        },
        "santa monica": {
            "rent_control": True,
            "just_cause": True,
            "stricter_than_state": True,
            "key_ordinances": ["SMMC § 1801-1821 (Rent Control)"],
            "notes": "Santa Monica has comprehensive rent control and just cause eviction ordinances."
        },
    }
    
    def _run(self, city: str, issue: str = "") -> str:
        """Check for local rules in the specified city."""
        
        city_key = city.lower().strip()
        
        if city_key not in self.LOCAL_RULES:
            return (
                f"No known local rent control or just cause ordinances for {city} in our database.\n"
                f"Note: California has 15+ cities with local rules. If this is a smaller city, "
                f"verify with local housing authority. State law (CA Civil Code) applies by default."
            )
        
        rules = self.LOCAL_RULES[city_key]
        
        result = f"⚠️ LOCAL RULES DETECTED: {city.title()}\n\n"
        
        if rules["stricter_than_state"]:
            result += "✓ This city has STRICTER rules than California state law\n\n"
        
        result += "Key Local Ordinances:\n"
        for ordinance in rules["key_ordinances"]:
            result += f"  • {ordinance}\n"
        
        result += f"\nSummary: {rules['notes']}\n"
        
        if rules["rent_control"]:
            result += "\n⚠️ RENT CONTROL: This city has rent control ordinances. "
            result += "Verify allowable rent increases and exemptions.\n"
        
        if rules["just_cause"]:
            result += "\n⚠️ JUST CAUSE REQUIRED: Cannot evict without approved reason. "
            result += "State no-fault eviction rules may not apply.\n"
        
        result += f"\n💡 Action: Review local ordinances before proceeding. State law is not sufficient."
        
        return result

