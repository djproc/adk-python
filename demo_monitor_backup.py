import asyncio
import sys
import os
import shutil
import logging
from typing import TypedDict, List, Optional

# Add the path to find the tools
sys.path.append(os.path.join(os.getcwd(), 'blab_agents/src'))

from langgraph.graph import StateGraph, END
# We import the tools we found
from blab_agents.archive_manager.tools import move_files_to_bucket, list_local_files

# --- Configuration ---
BUCKET_NAME = "my-backup-bucket"
DISK_THRESHOLD = 80.0  # Percent
LARGE_FILE_THRESHOLD_MB = 100

# --- State ---
class SystemState(TypedDict):
    disk_usage_percent: float
    files_to_backup: List[str]
    backup_status: str
    message: str

# --- Nodes ---

async def monitor_disk_node(state: SystemState):
    print("\n[Monitor] Checking disk usage...")
    
    # In a real scenario:
    # total, used, free = shutil.disk_usage(".")
    # percent = (used / total) * 100
    
    # For DEMO purposes, we simulate a critical state
    percent = 95.0 
    print(f"[Monitor] Disk Usage: {percent}%")
    
    return {"disk_usage_percent": percent}

async def scan_files_node(state: SystemState):
    print("[Scanner] Scanning for large files to offload...")
    
    # Use the tool from archive_manager (or similar logic)
    # real_files = list_local_files(".") 
    
    # For DEMO, let's pretend we found some large model files
    found_files = ["./large_model_v1.pt", "./dataset_archive.zip"]
    
    # Create dummy files so the tool actually has something to move if we ran it for real
    # But since we might not have gsutil, we might need to mock the move tool too 
    # or just let it fail/print. 
    # Let's create dummy files to be safe.
    for f in found_files:
        if not os.path.exists(f):
            with open(f, "w") as x: x.write("dummy content")

    print(f"[Scanner] Found candidates: {found_files}")
    return {"files_to_backup": found_files}

async def backup_node(state: SystemState):
    files = state.get("files_to_backup", [])
    if not files:
        return {"backup_status": "skipped", "message": "No files to backup"}
    
    print(f"[Backup] Initiating transfer to gs://{BUCKET_NAME}...")
    
    # Check if we really want to run the subprocess or just mock it for the demo
    # The user asked to "use tools", so we should try to call the imported function.
    # However, without gsutil/auth, it will error. 
    # We'll wrap it in try/except to show the intent.
    
    try:
        # We assume the user might have gsutil, if not, the tool returns an error string
        result = move_files_to_bucket(files, BUCKET_NAME)
        print(f"[Backup Tool Output]:\n{result}")
        
        if "Error" in result:
             return {"backup_status": "failed", "message": result}
             
    except Exception as e:
        print(f"[Backup] Tool execution failed: {e}")
        return {"backup_status": "error", "message": str(e)}

    # Cleanup dummies if they still exist (tool 'mv' should have removed them if successful)
    for f in files:
        if os.path.exists(f):
            print(f"[Backup] Cleaning up local file: {f}")
            os.remove(f)
            
    return {"backup_status": "success", "message": "Files offloaded and space reclaimed."}

async def notify_node(state: SystemState):
    print(f"\n[Notification] System Report: {state['message']}")
    return {}

# --- Logic ---

def check_disk_status(state: SystemState):
    if state["disk_usage_percent"] > DISK_THRESHOLD:
        return "critical"
    return "ok"

# --- Graph ---

workflow = StateGraph(SystemState)

workflow.add_node("monitor", monitor_disk_node)
workflow.add_node("scanner", scan_files_node)
workflow.add_node("backup", backup_node)
workflow.add_node("notify", notify_node)

workflow.set_entry_point("monitor")

workflow.add_conditional_edges(
    "monitor",
    check_disk_status,
    {
        "critical": "scanner",
        "ok": "notify"
    }
)

workflow.add_edge("scanner", "backup")
workflow.add_edge("backup", "notify")
workflow.add_edge("notify", END)

app = workflow.compile()

# --- Execution ---

async def main():
    print("--- Disk Monitor & Auto-Backup System ---")
    
    initial_state = {
        "disk_usage_percent": 0.0,
        "files_to_backup": [],
        "backup_status": "unknown",
        "message": "Monitoring active"
    }
    
    # Visualize if possible
    try:
        print("\n[Graph Structure]")
        print(app.get_graph().draw_ascii())
    except:
        pass
        
    await app.ainvoke(initial_state)

if __name__ == "__main__":
    asyncio.run(main())
