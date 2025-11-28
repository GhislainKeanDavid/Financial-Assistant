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

def record_transaction_db(user_id: str, amount: float, category: str, description: Optional[str] = None) -> bool:
    """Inserts a new transaction record into the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        sql = """
            INSERT INTO transactions (user_id, amount, category, description)
            VALUES (%s, %s, %s, %s);
        """
        cur.execute(sql, (user_id, amount, category, description))
        
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