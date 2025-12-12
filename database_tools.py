import datetime
from models.state import Transaction
from typing import List
from typing import Optional
from langchain_core.tools import tool 
from models.budget import Budget
from db_manager import record_transaction_db, get_spending_sum_db, get_expenses_by_date_db, upsert_budget_db, get_budget_db


# --- FINANCIAL AGENT TOOLS ---

@tool
def record_transaction(
    amount: float,
    category: str,
    user_id: str,
    description: Optional[str] = None,
    expense_date: Optional[str] = None
) -> str:
    """Records a new financial transaction (expense or income) to the database."""
    if amount <= 0:
        return "Error: Amount must be positive. Please specify a valid expense."
    
    # NEW LOGIC: Call the database manager
    success = record_transaction_db(user_id, amount, category, description, expense_date)

    if success:
        # Tell the agent what to do next
        return f"Transaction of ${amount} recorded successfully. You MUST now use the check_budget tool."
    else:
        return "ERROR: Failed to record transaction due to a database error."

@tool
def check_budget(user_id: str) -> str:
    """Checks current spending against the user's defined database budget."""
    
    # 1. Get Limits from DB
    limits = get_budget_db(user_id)
    if not limits:
        return "You haven't set a budget yet. Please tell me your daily, weekly, or monthly budget."
    
    # 2. Get Spending from DB (Existing logic re-used)
    daily_spend = get_spending_sum_db(user_id, "daily")
    weekly_spend = get_spending_sum_db(user_id, "weekly")
    
    # 3. Compare
    status = "📊 **Budget Status:**\n"
    
    # Daily Check
    status += f"Daily: ₱{daily_spend:,.2f} / ₱{limits['daily']:,.2f} "
    if daily_spend > limits['daily']:
        status += "⚠️ (OVER)\n"
    else:
        status += "✅\n"
        
    # Weekly Check
    status += f"Weekly: ₱{weekly_spend:,.2f} / ₱{limits['weekly']:,.2f} "
    if weekly_spend > limits['weekly']:
        status += "⚠️ (OVER)\n"
    else:
        status += "✅"
        
    return status

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

@tool
def get_expenses_by_date(
    user_id: str, 
    date: str
) -> str:
    """
    Retrieves a list of expenses for a specific date. 
    The date parameter MUST be in 'YYYY-MM-DD' format.
    """
    return get_expenses_by_date_db(user_id, date)

@tool
def set_my_budget(
    user_id: str,
    amount: float,
    period: str
) -> str:
    """
    Sets the user's financial budget.
    'amount': The numeric value of the budget.
    'period': MUST be one of 'daily', 'weekly', or 'monthly'.
    """
    period = period.lower()
    daily = 0.0
    weekly = 0.0
    monthly = 0.0
    
    # Automatic Calculation Logic
    if period == 'daily':
        daily = amount
        weekly = amount * 7
        monthly = amount * 30
    elif period == 'weekly':
        weekly = amount
        daily = amount / 7
        monthly = amount * 4.3  # Approx weeks in a month
    elif period == 'monthly':
        monthly = amount
        daily = amount / 30
        weekly = amount / 4.3
    else:
        return "Error: Period must be 'daily', 'weekly', or 'monthly'."

    # Save to Database
    success = upsert_budget_db(user_id, daily, weekly, monthly)
    
    if success:
        return (f"Budget set successfully!\n"
                f"Daily: ₱{daily:,.2f}\n"
                f"Weekly: ₱{weekly:,.2f}\n"
                f"Monthly: ₱{monthly:,.2f}")
    else:
        return "Failed to save budget to database."

# List of tools to be used by the LangGraph agent
FINANCIAL_TOOLS = [record_transaction, check_budget, get_daily_summary, get_expenses_by_date, set_my_budget]