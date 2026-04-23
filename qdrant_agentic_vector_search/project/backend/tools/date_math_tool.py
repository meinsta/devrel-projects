"""
Date Math Tool for CrewAI Agents
Computes legal deadlines with California court calendar rules
"""

from datetime import datetime, timedelta
from typing import ClassVar, List
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class DateMathInput(BaseModel):
    """Input for deadline calculation."""
    trigger_date: str = Field(
        ...,
        description="Starting date in YYYY-MM-DD format (e.g., '2025-11-12')"
    )
    days: int = Field(..., description="Number of days to add")
    day_type: str = Field(
        default="calendar",
        description="'calendar' for calendar days or 'business' for business days"
    )


class DateMathTool(BaseTool):
    """Calculate exact legal deadlines accounting for California court rules."""
    
    name: str = "compute_deadline"
    description: str = """Calculate exact deadline dates for California legal procedures.
    Accounts for calendar vs. business days and California court holidays.
    Use this for notice periods, filing deadlines, response times, etc.
    Example: compute_deadline("2025-11-12", 3, "calendar") for 3-day notice"""
    
    args_schema: type[BaseModel] = DateMathInput
    
    # California court holidays (simplified - would need annual update)
    CA_HOLIDAYS_2025: ClassVar[List[str]] = [
        "2025-01-01",  # New Year's
        "2025-01-20",  # MLK Day
        "2025-02-17",  # Presidents Day
        "2025-05-26",  # Memorial Day
        "2025-07-04",  # Independence Day
        "2025-09-01",  # Labor Day
        "2025-11-11",  # Veterans Day
        "2025-11-27",  # Thanksgiving
        "2025-12-25",  # Christmas
    ]
    
    def _is_weekend(self, date: datetime) -> bool:
        """Check if date is weekend."""
        return date.weekday() >= 5  # 5=Saturday, 6=Sunday
    
    def _is_holiday(self, date: datetime) -> bool:
        """Check if date is California court holiday."""
        date_str = date.strftime("%Y-%m-%d")
        return date_str in self.CA_HOLIDAYS_2025
    
    def _is_court_day(self, date: datetime) -> bool:
        """Check if California courts are open."""
        return not (self._is_weekend(date) or self._is_holiday(date))
    
    def _run(self, trigger_date: str, days: int, day_type: str = "calendar") -> str:
        """Calculate the deadline."""
        
        try:
            start = datetime.strptime(trigger_date, "%Y-%m-%d")
        except ValueError:
            return f"Error: Invalid date format. Use YYYY-MM-DD (e.g., '2025-11-12')"
        
        if day_type == "calendar":
            # Simple calendar day calculation
            deadline = start + timedelta(days=days)
            
            # If deadline falls on weekend/holiday, move to next court day
            while not self._is_court_day(deadline):
                deadline += timedelta(days=1)
            
            return (
                f"Deadline: {deadline.strftime('%B %d, %Y')} ({deadline.strftime('%A')})\n"
                f"Calculation: {trigger_date} + {days} calendar days = {deadline.strftime('%Y-%m-%d')}\n"
                f"Note: If deadline fell on weekend/holiday, moved to next court day."
            )
        
        elif day_type == "business":
            # Business days (skip weekends and holidays)
            current = start
            days_counted = 0
            
            while days_counted < days:
                current += timedelta(days=1)
                if self._is_court_day(current):
                    days_counted += 1
            
            deadline = current
            
            return (
                f"Deadline: {deadline.strftime('%B %d, %Y')} ({deadline.strftime('%A')})\n"
                f"Calculation: {trigger_date} + {days} business days (excluding weekends/holidays)\n"
                f"Court days counted: {days}, Calendar days elapsed: {(deadline - start).days}"
            )
        
        else:
            return f"Error: day_type must be 'calendar' or 'business', got '{day_type}'"

