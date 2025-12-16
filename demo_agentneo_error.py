import asyncio
from typing import AsyncGenerator, List

# Import necessary ADK components
from google.genai import types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.runners import InMemoryRunner

# --- 1. Simulation Tools (without AgentNeo tracing) ---

def mock_training_check():
    """Simulates checking if training is complete."""
    print("[Tool:mock_training_check] Checking training status...")
    return "Training finished successfully. Artifact: model_v1.pt (12GB)"

def mock_gsutil_backup(filenames: List[str], bucket: str):
    """Simulates gsutil cp with a disk space failure."""
    print(f"\n[Tool:mock_gsutil_backup] Attempting to copy {filenames} to {bucket}...")
    for f in filenames:
        if "model" in f:
            # Simulate a disk full error during the staging phase of upload
            raise OSError(f"[Errno 28] No space left on device: '/tmp/gsutil_staging/{f}'. Upload failed.")
    return "Upload successful."

# --- 2. Mock LLM (without AgentNeo tracing) ---

class MockLlm(BaseLlm):
    model: str = "mock-model-error-sim"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        
        full_context = ""
        # Extract system instruction
        if llm_request.config.system_instruction:
            sys_inst = llm_request.config.system_instruction
            if isinstance(sys_inst, str):
                full_context += sys_inst + "\n"
            elif hasattr(sys_inst, 'parts'):
                 for part in sys_inst.parts:
                     if part.text:
                        full_context += part.text + "\n"
        
        # Extract conversation history and tool outputs
        for content in llm_request.contents:
            for part in content.parts:
                if part.text: full_context += part.text
                if part.function_response: full_context += str(part.function_response.response)

        response_content = None

        # --- Trainer Agent Logic ---
        if "Check training status" in full_context:
            if "Training finished" in full_context: # Tool output present
                response_content = types.Content(role='model', parts=[types.Part(text="Training is complete. We have 'model_v1.pt' ready for backup.")])
            else:
                # Call tool
                fc = types.FunctionCall(name="mock_training_check", args={})
                response_content = types.Content(role='model', parts=[types.Part(function_call=fc)])

        # --- Backup Agent Logic ---
        elif "Backup the model" in full_context:
            # If we see the error in context (from the tool output), react to it
            if "No space left" in full_context:
                response_content = types.Content(role='model', parts=[types.Part(text="CRITICAL FAILURE: Backup failed due to lack of disk space. Corrupted file suspected. Notifying Ops.")])
            elif "Upload successful" in full_context:
                response_content = types.Content(role='model', parts=[types.Part(text="Backup complete.")])
            else:
                # Initiate backup
                fc = types.FunctionCall(name="mock_gsutil_backup", args={"filenames": ["model_v1.pt"], "bucket": "gs://models-archive"})
                response_content = types.Content(role='model', parts=[types.Part(function_call=fc)])
        
        else:
            response_content = types.Content(role='model', parts=[types.Part(text="Acknowledged.")])

        yield LlmResponse(partial=False, content=response_content)

# --- Re-assemble Agents with Mock LLM ---

mock_llm = MockLlm()

trainer = LlmAgent(
    name="trainer",
    model=mock_llm,
    instruction="Check training status and report artifacts.",
    tools=[mock_training_check]
)

backup_ops = LlmAgent(
    name="backup_ops",
    model=mock_llm,
    instruction="Backup the model artifacts to GCS. If it fails, report the error detail.",
    tools=[mock_gsutil_backup]
)

# --- 3. Workflow ---

pipeline = SequentialAgent(
    name="deployment_pipeline",
    sub_agents=[trainer, backup_ops]
)

async def main():
    print("--- ADK Multi-Agent Error Handling Demo (Simplified) ---")
    print("Scenario: Training Success -> Backup OutOfDisk -> Agent Handling\n")
        
    runner = InMemoryRunner(agent=pipeline)
    
    try:
        await runner.run_debug("Start the deployment pipeline.")
            
    except Exception as e:
        print(f"\n[Main] Exception caught in top-level execution: {e}")
        
    print("\n--- Execution Complete ---")
    print("This is the raw ADK output. To see AgentNeo tracing, you would manually instrument your LLM and tool calls with AgentNeo's Tracer API (e.g., @tracer.trace_llm, @tracer.trace_tool) and launch its dashboard.")
    print("  AgentNeo Dashboard (if running): http://localhost:8000/ (or specified port)")

if __name__ == "__main__":
    asyncio.run(main())
