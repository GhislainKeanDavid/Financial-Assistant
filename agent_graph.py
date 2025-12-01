import os
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
# FIX: ToolInvocation and ToolExecutor are removed, relying on manual message handling
from dotenv import load_dotenv

# Import our custom components
from models.state import GraphState
from models.budget import Budget
from database_tools import FINANCIAL_TOOLS
# Ensure specific tool functions are imported here if needed, but not necessary for this approach.

# Load environment variables
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY") 

# --- 1. Initialize Core Components ---
LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# --- 2. Define Custom Nodes ---

def call_model(state: GraphState):
    """NODE 1: The Planner. Calls the LLM to decide the next action."""
    
    messages = state['messages']
    thread_id = state['thread_id']
    
    # System prompt remains the same
    system_prompt = (
        "You are a helpful financial assistant named Kean's MakwentaBot. Your thread_id is {thread_id}. "
        "You MUST use the provided tools for recording, reporting, or checking budgets. "
        "If a transaction is recorded, you must follow up with the 'check_budget' tool immediately. "
        "Do NOT invent data or perform calculations yourself."
    ).format(thread_id=thread_id)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        *messages
    ])
    
    model_with_tools = LLM.bind_tools(FINANCIAL_TOOLS)
    response = model_with_tools.invoke(prompt.format_messages(messages=messages))

    # Return the LLM's response (which may contain tool calls)
    return {"messages": [response]}

def call_tool_executor(state: GraphState):
    """NODE 2: The Executor. Manually executes the tool calls requested by the LLM."""
    last_message = state['messages'][-1]
    tool_calls = last_message.tool_calls
    
    tool_messages = []
    
    for call in tool_calls:
        tool_name = call.get("name")
        tool_args = call.get("args", {}).copy()
        
        # Inject state data into tool calls
        tool_args['user_id'] = state['thread_id']
        
        if tool_name in ["check_budget", "get_daily_summary"]:
            tool_args['current_budget'] = state['budget']
        
        # Find and execute the tool (We must use the tool.func attribute from the list)
        tool_func = None
        for tool in FINANCIAL_TOOLS:
            if tool.name == tool_name:
                tool_func = tool.func
                break
        
        if tool_func:
            try:
                # Execute the function with the prepared arguments
                result = tool_func(**tool_args)
                
                # Append the ToolMessage (Observation) to the list
                tool_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=call["id"], # Crucial link back to the AIMessage
                        name=tool_name
                    )
                )
            except Exception as e:
                # Handle execution errors
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing {tool_name}: {str(e)}",
                        tool_call_id=call["id"],
                        name=tool_name
                    )
                )
        
    # Return ONLY the ToolMessages (Observations) to be added to the state. 
    # The original AIMessage (Request) is already in the state history.
    return {"messages": tool_messages}

# --- 3. Define Conditional Edge Logic (Remains Correct) ---

def should_continue(state: GraphState):
    """Decides whether to loop back to the planner, or end the process."""
    last_message = state['messages'][-1]
    # Check if the last message has a tool_calls attribute and if the list is populated
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "continue_tool"
    return "end"

# --- 4. Build and Compile the Graph (Remains Correct) ---

def create_agent_graph():
    """Builds and returns the compiled LangGraph object."""
    workflow = StateGraph(GraphState)
    workflow.add_node("planner", call_model)
    workflow.add_node("tool_executor", call_tool_executor)
    workflow.set_entry_point("planner")
    workflow.add_conditional_edges(
        "planner", 
        should_continue, 
        {"continue_tool": "tool_executor", "end": END}
    )
    workflow.add_edge("tool_executor", "planner")
    return workflow.compile()

# Example usage (Visualization code is assumed to be appended here)
app = create_agent_graph()