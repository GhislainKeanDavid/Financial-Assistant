import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from typing import Dict, Any

# --- Telegram Bot Dependencies ---
import telegram
from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from starlette.requests import Request
from starlette.responses import JSONResponse
import httpx 

# Import the compiled LangGraph agent and state models
from agent_graph import app
from models.state import GraphState
from models.budget import Budget

import os

load_dotenv()

# --- FastAPI Setup ---
app_fastapi = FastAPI(title="LangGraph Financial Assistant API")

# --- Telegram Constants (Read from .env) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 

# --- Initialize Global State and Budget ---
# This is a temporary, in-memory dictionary for user-specific state persistence
USER_AGENTS: Dict[str, Any] = {}
DEFAULT_BUDGET = Budget(
    user_name="Kean",
    currency_symbol="₱",
    daily_limits={"Groceries": 500.0, "Transport": 200.0, "All": 1000.0},
    weekly_limits={"Groceries": 3000.0, "All": 5000.0}
)


# --- Agent Request Model ---
class AgentRequest(BaseModel):
    user_input: str
    thread_id: str 

async def handle_message(update: Update, context):
    """Processes the message from Telegram and calls the internal /api/chat endpoint."""
    if update.message and update.message.text and application:
        user_input = update.message.text
        chat_id = str(update.message.chat_id)
        
        # 1. Call the internal FastAPI endpoint
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    INTERNAL_API_URL, 
                    json={"user_input": user_input, "thread_id": chat_id}
                )
                
                if response.status_code == 200:
                    api_response = response.json()
                    final_text = api_response.get("response", "Sorry, I couldn't process that.")
                else:
                    final_text = f"Error: Agent API failed with status {response.status_code}."

            except Exception as e:
                print(f"Internal API Call Error: {e}")
                final_text = "I'm sorry, I seem to be having trouble connecting to my brain right now."
        
        # 2. Send the final response back to the user via Telegram
        await context.bot.send_message(chat_id=chat_id, text=final_text)

# --- Agent Invocation Logic ---
@app_fastapi.post("/api/chat")
async def chat_endpoint(request: AgentRequest):
    try:
        thread_id = request.thread_id
        user_input = request.user_input
        
        # 1. Initialize or Retrieve Agent State
        if thread_id not in USER_AGENTS:
            initial_state = GraphState(
                thread_id=thread_id,
                messages=[],
                tool_calls=[],
                tool_observation="",
                intent="",
                budget=DEFAULT_BUDGET
            )
            USER_AGENTS[thread_id] = initial_state
        
        current_state = USER_AGENTS[thread_id]
        
        # 2. Append the new HumanMessage
        current_state['messages'].append(HumanMessage(content=user_input))

        # 3. Invoke the compiled LangGraph app
        final_state = app.invoke(current_state)

        # 4. Save the final state back to the user's slot
        USER_AGENTS[thread_id] = final_state
        
        # 5. Extract the final response text
        final_message = final_state['messages'][-1].content
        
        print(f"User {thread_id} processed. Final response: {final_message[:50]}...")

        return {"thread_id": thread_id, "response": final_message}

    except Exception as e:
        print(f"An error occurred in /api/chat: {e}")
        raise HTTPException(status_code=500, detail="Internal agent processing error.")


# --- Telegram Bot Setup (FIXED SCOPE) ---

if TELEGRAM_BOT_TOKEN:
    # Initialize the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()
else:
    application = None


if application:
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))




# Register the handler only if the application object was successfully initialized
if application:
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))


# --- Webhook Endpoint (FIXED SCOPE) ---
# This is now a standard, global FastAPI route registration
@app_fastapi.post("/webhook")
async def telegram_webhook(request: Request):
    """This endpoint receives all message updates from Telegram's servers."""
    if application:
        try:
            update = Update.de_json(await request.json(), application.bot)
            await application.process_update(update)
            # Must return 200 OK immediately
            return JSONResponse({"message": "ok"})
        except Exception as e:
            print(f"Error processing Telegram update: {e}")
            return JSONResponse({"message": "error"}, status_code=500)
    else:
        return JSONResponse({"message": "Telegram token not configured"}, status_code=500)

# In main.py, add this code block after the @app_fastapi.post("/webhook") function

@app_fastapi.on_event("startup")
async def startup_event():
    """Initializes the Telegram application asynchronously when FastAPI starts."""
    if application:
        try:
            # We must await the initialize call since it's an async function
            await application.initialize()
            print("INFO: Telegram Application Initialized successfully via startup event.")
        except Exception as e:
            print(f"ERROR: Failed to initialize Telegram application: {e}")


# --- Server Run Command ---
PORT = int(os.getenv("PORT", 8080))
INTERNAL_API_URL = f"http://127.0.0.1:{PORT}/api/chat"

if __name__ == "__main__":
    uvicorn.run(app_fastapi, host="0.0.0.0", port=PORT)