import os
import psycopg2
from dotenv import load_dotenv
from typing import Optional, Dict

load_dotenv()

# Get connection string from .env
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Establishes and returns a database connection using the environment variable."""
    if not DATABASE_URL:
        raise ConnectionError("DATABASE_URL not set in environment variables.")
    
    # We use the connection string obtained from Supabase (PostgreSQL)
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def record_transaction_db(user_id: str, amount: float, category: str, description: Optional[str] = None, expense_date: Optional[str] = None) -> bool:
    """Inserts a new transaction record into the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
            INSERT INTO transactions (user_id, amount, category, description, expense_date)
            VALUES (%s, %s, %s, %s);
        """
        cur.execute(sql, (user_id, amount, category, description, expense_date))
        
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database Error on insert: {e}")
        return False

def get_spending_sum_db(user_id: str, period: str, category: Optional[str] = None) -> float:
    """Queries the database to get the sum of spending for a given period."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Define time filters based on the required period
        time_filter = ""
        if period == "day":
            time_filter = "AND transaction_date >= CURRENT_DATE"
        elif period == "week":
            # Start of the current week (Monday)
            time_filter = "AND transaction_date >= date_trunc('week', NOW())"
        
        category_filter = ""
        # Only apply category filter if a specific category is requested
        if category and category.lower() != 'all':
             category_filter = f"AND category ILIKE '{category}'"

        # SQL query to sum the amounts
        sql = f"""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = %s {category_filter} {time_filter};
        """
        cur.execute(sql, (user_id,))
        
        total_sum = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        return float(total_sum)
    except Exception as e:
        print(f"Database Error on query: {e}")
        return 0.0


def get_expenses_by_date_db(user_id: str, query_date: str) -> str:
    """Retrieves expenses for a specific date from the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Query to get transaction details for a specific expense_date
        # We order by record_date to show them in the order they were entered
        sql = """
            SELECT category, amount, description 
            FROM transactions 
            WHERE user_id = %s AND expense_date = %s
            ORDER BY record_date ASC;
        """
        cur.execute(sql, (user_id, query_date))
        rows = cur.fetchall()
        
        cur.close()
        conn.close()

        if not rows:
            return f"No expenses found for {query_date}."

        # Format the output into a readable string for the LLM
        report = f"Expenses for {query_date}:\n"
        total = 0.0
        for row in rows:
            category, amount, description = row
            desc_str = f" ({description})" if description else ""
            report += f"- {category}: ₱{float(amount):,.2f}{desc_str}\n"
            total += float(amount)
        
        report += f"\nTotal: ₱{total:,.2f}"
        return report

    except Exception as e:
        print(f"Database Error on query: {e}")
        return f"Error retrieving data: {str(e)}"


def upsert_budget_db(user_id: str, daily: float, weekly: float, monthly: float) -> bool:
    """Updates the budget limits for a user."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Upsert: Insert if new, Update if exists
        sql = """
            INSERT INTO budgets (user_id, daily_limit, weekly_limit, monthly_limit, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                daily_limit = EXCLUDED.daily_limit,
                weekly_limit = EXCLUDED.weekly_limit,
                monthly_limit = EXCLUDED.monthly_limit,
                updated_at = NOW();
        """
        cur.execute(sql, (user_id, daily, weekly, monthly))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Database Error on upsert_budget: {e}")
        return False

def get_budget_db(user_id: str):
    """Retrieves the current budget limits for a user."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT daily_limit, weekly_limit, monthly_limit FROM budgets WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if row:
            return {"daily": float(row[0]), "weekly": float(row[1]), "monthly": float(row[2])}
        return None # Return None if no budget set
    except Exception as e:
        print(f"Database Error on get_budget: {e}")
        return None