import asyncio
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END

# --- 1. Simulation Logic ---
def simulate_upload(artifact: str):
    if "model" in artifact:
        raise OSError(f"[Errno 28] No space left on device while staging '{artifact}'")
    return "OK"

# --- 2. State Definition ---
class PipelineState(TypedDict):
    step: str
    artifact: Optional[str]
    backup_status: str
    error: Optional[str]
    alert_sent: bool

# --- 3. Nodes ---

async def training_node(state: PipelineState):
    print("[Graph:Training] Checking training job...")
    # Simulate success
    return {
        "step": "training_complete",
        "artifact": "model_v1.pt", 
        "backup_status": "pending"
    }

async def backup_node(state: PipelineState):
    artifact = state.get("artifact")
    print(f"[Graph:Backup] Attempting backup of {artifact}...")
    
    try:
        # Simulate the tool call
        simulate_upload(artifact)
        return {"backup_status": "success"}
    except OSError as e:
        print(f"[Graph:Backup] ! Error detected: {e}")
        # Return error state to graph
        return {
            "backup_status": "failed",
            "error": str(e)
        }

async def alert_node(state: PipelineState):
    error_msg = state.get("error")
    print(f"\n[Graph:Alert] !!! ALERTING OPS TEAM !!!")
    print(f"[Graph:Alert] Reason: {error_msg}")
    print(f"[Graph:Alert] Triggering disk cleanup protocols...")
    return {"alert_sent": True}

# --- 4. Edge Logic ---

def check_backup_status(state: PipelineState):
    if state.get("backup_status") == "failed":
        return "alert_ops"
    return "end"

# --- 5. Graph Construction ---

workflow = StateGraph(PipelineState)

workflow.add_node("trainer", training_node)
workflow.add_node("backup_ops", backup_node)
workflow.add_node("alert_ops", alert_node)

workflow.set_entry_point("trainer")

workflow.add_edge("trainer", "backup_ops")

# Conditional Edge: Based on backup result, go to Alert or End
workflow.add_conditional_edges(
    "backup_ops",
    check_backup_status,
    {
        "alert_ops": "alert_ops",
        "end": END
    }
)

workflow.add_edge("alert_ops", END)

app = workflow.compile()

# --- 6. Execution ---

async def main():
    print("--- LangGraph Error Handling Demo ---")
    print("Scenario: Disk Corruption -> Conditional Edge -> Alert Node\n")
    
    initial_state = {
        "step": "start", 
        "artifact": None, 
        "backup_status": "unknown", 
        "error": None, 
        "alert_sent": False
    }
    
    # Run the graph
    final_state = await app.ainvoke(initial_state)
    
    print("\n--- Final Graph State ---")
    print(f"Status: {final_state['backup_status']}")
    print(f"Error:  {final_state['error']}")
    print(f"Alerted: {final_state['alert_sent']}")

if __name__ == "__main__":
    asyncio.run(main())
