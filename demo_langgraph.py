import asyncio
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

# --- 1. Define State ---
class AgentState(TypedDict):
    # The user's initial request
    topic: str
    
    # Internal state passed between nodes
    status: str
    benefits: str
    risks: str
    
    # Final output
    final_report: str

# --- 2. Define Nodes (Agents) ---
# In a real app, these would call the LLM. 
# Here we simulate the logic to match demo_workflow.py

async def gatekeeper_node(state: AgentState):
    print(f"[Gatekeeper] Analyzing: {state['topic']}")
    if "Cooking" in state['topic'] or "cooking" in state['topic']:
        return {"status": "REJECTED"}
    return {"status": "APPROVED"}

async def benefits_node(state: AgentState):
    print("[Benefits] Generating report...")
    if state['status'] == "REJECTED":
        return {"benefits": "Analysis Skipped"}
    return {"benefits": "1. Increased efficiency\n2. Automation of tasks\n3. New capabilities"}

async def risks_node(state: AgentState):
    print("[Risks] Generating report...")
    if state['status'] == "REJECTED":
        return {"risks": "Analysis Skipped"}
    return {"risks": "1. Job displacement\n2. Bias in algorithms\n3. Security vulnerabilities"}

async def aggregator_node(state: AgentState):
    print("[Aggregator] Synthesizing final response...")
    if state['benefits'] == "Analysis Skipped":
        return {"final_report": "I apologize, but we cannot analyze this topic as it is outside our safety guidelines."}
    
    report = (
        "FINAL REPORT:\n"
        "The research team identified key benefits including efficiency and automation, "
        "while noting risks such as job displacement and bias."
    )
    return {"final_report": report}

# --- 3. Build Graph ---

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("gatekeeper", gatekeeper_node)
workflow.add_node("benefits_expert", benefits_node)
workflow.add_node("risks_expert", risks_node)
workflow.add_node("aggregator", aggregator_node)

# Add edges
# Start -> Gatekeeper
workflow.set_entry_point("gatekeeper")

# Gatekeeper -> (Benefits, Risks) in parallel
# LangGraph handles parallel execution when multiple edges branch from one node 
# or when we don't await them sequentially? 
# Actually, StateGraph executes nodes. To do parallel, we usually connect to multiple next nodes.
workflow.add_edge("gatekeeper", "benefits_expert")
workflow.add_edge("gatekeeper", "risks_expert")

# (Benefits, Risks) -> Aggregator
workflow.add_edge("benefits_expert", "aggregator")
workflow.add_edge("risks_expert", "aggregator")

# Aggregator -> End
workflow.add_edge("aggregator", END)

# Compile
app = workflow.compile()

# --- 4. Execution ---

async def main():
    print("--- LangGraph Demo: Valid Topic ---")
    inputs = {"topic": "Artificial Intelligence", "status": "", "benefits": "", "risks": "", "final_report": ""}
    
    # app.invoke executes the graph
    result = await app.ainvoke(inputs)
    
    print("\nGraph Output:")
    print(f"Status: {result['status']}")
    print(f"Final Report: {result['final_report']}")

    print("\n" + "="*50 + "\n")

    print("--- LangGraph Demo: Invalid Topic ---")
    inputs = {"topic": "Cooking Pasta", "status": "", "benefits": "", "risks": "", "final_report": ""}
    result = await app.ainvoke(inputs)
    
    print("\nGraph Output:")
    print(f"Status: {result['status']}")
    print(f"Final Report: {result['final_report']}")

if __name__ == "__main__":
    asyncio.run(main())
