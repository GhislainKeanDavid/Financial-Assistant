import datetime
from langchain.tools import tool
from models.state import Transaction
from typing import List
from langchain_core.tools import tool 
from models.budget import Budget
from .db_manager import record_transaction_db, get_spending_sum_db


# --- FINANCIAL AGENT TOOLS ---

@tool
def record_transaction(
    amount: float,
    category: str,
    user_id: str,
    description: Optional[str] = None # Change description to Optional
) -> str:
    """Records a new financial transaction (expense or income) to the database."""
    if amount <= 0:
        return "Error: Amount must be positive. Please specify a valid expense."
    
    # NEW LOGIC: Call the database manager
    success = record_transaction_db(user_id, amount, category, description)

    if success:
        # Tell the agent what to do next
        return f"Transaction of ${amount} recorded successfully. You MUST now use the check_budget tool."
    else:
        return "ERROR: Failed to record transaction due to a database error."

@tool
def check_budget(
    amount: float, 
    category: str, 
    user_id: str,
    current_budget: Budget 
) -> str:
    """Checks the daily and weekly budget limits against a pending expense for a category."""
    
    daily_limit = current_budget.daily_limits.get(category, float('inf')) 
    weekly_limit = current_budget.weekly_limits.get(category, float('inf')) 

    # NEW LOGIC: Get real spending data from the database
    current_day_spending = get_spending_sum_db(user_id, "day", category)
    current_week_spending = get_spending_sum_db(user_id, "week", category)

    is_daily_over = (current_day_spending + amount) > daily_limit
    is_weekly_over = (current_week_spending + amount) > weekly_limit
    
    if is_daily_over or is_weekly_over:
        details = ""
        if is_daily_over:
            details += f"Daily limit of ${daily_limit:,.2f} will be exceeded (Current: ${current_day_spending:,.2f}). "
        if is_weekly_over:
            details += f"Weekly limit of ${weekly_limit:,.2f} will be exceeded (Current: ${current_week_spending:,.2f}). "
            
        return f"BUDGET WARNING! The expense would cause an overspend. {details} Advise the user."
    
    return "BUDGET SUCCESS: Transaction is within both daily and weekly budget limits. Inform the user."

@tool
def get_daily_summary(user_id: str, current_budget: Budget) -> str:
    """Generates a formatted daily budget and spending summary for a proactive notification."""
    # ... (code to get name and currency remains the same)
    
    # NEW LOGIC: Get real total weekly expense from the database
    total_week_expense = get_spending_sum_db(user_id, "week", "All")
    weekly_budget = current_budget.weekly_limits.get("All", 2000.00) 
    
    # ... (rest of summary formatting remains the same)
    # The return summary will now use real data.
    
    summary = f"Hello {name}!\n📅 {today}\n\n"
    summary += "--- WEEKLY FINANCIAL STATUS ---\n"
    summary += f"Weekly Budget: **{currency}{weekly_budget:,.2f}**\n"
    summary += f"Spent This Week: **{currency}{total_week_expense:,.2f}**\n"
    summary += f"Remaining: **{currency}{(weekly_budget - total_week_expense):,.2f}**\n"

    return summary

# List of tools to be used by the LangGraph agent
FINANCIAL_TOOLS = [record_transaction, check_budget, get_daily_summary]