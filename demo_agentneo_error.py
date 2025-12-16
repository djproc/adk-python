import asyncio
import agentneo
from typing import AsyncGenerator, List

from google.genai import types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.runners import InMemoryRunner

# --- 1. Simulation Tools ---

def mock_training_check():
    """Simulates checking if training is complete."""
    return "Training finished successfully. Artifact: model_v1.pt (12GB)"

def mock_gsutil_backup(filenames: List[str], bucket: str):
    """Simulates gsutil cp with a disk space failure."""
    print(f"\n[System] Attempting to copy {filenames} to {bucket}...")
    for f in filenames:
        if "model" in f:
            # Simulate a disk full error during the staging phase of upload
            raise OSError(f"[Errno 28] No space left on device: '/tmp/gsutil_staging/{f}'. Upload failed.")
    return "Upload successful."

# --- 2. Traced LLM ---

class TracedMockLlm(BaseLlm):
    model: str = "mock-model-error-sim"

    @agentneo.trace(name="llm_generation", input_args=["llm_request"])
    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        
        # Simple context extraction
        full_context = ""
        for content in llm_request.contents:
            for part in content.parts:
                if part.text: full_context += part.text
                if part.function_response: full_context += str(part.function_response)

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

llm = TracedMockLlm()

# --- 3. Agents ---

trainer = LlmAgent(
    name="trainer",
    model=llm,
    instruction="Check training status and report artifacts.",
    tools=[mock_training_check]
)

backup_ops = LlmAgent(
    name="backup_ops",
    model=llm,
    instruction="Backup the model artifacts to GCS. If it fails, report the error detail.",
    tools=[mock_gsutil_backup]
)

# --- 4. Workflow ---

pipeline = SequentialAgent(
    name="deployment_pipeline",
    sub_agents=[trainer, backup_ops]
)

async def main():
    print("--- AgentNeo Error Handling Demo ---")
    print("Scenario: Training Success -> Backup OutOfDisk -> Agent Handling\n")
    
    # We trace the entire session
    session = agentneo.Session(session_id="error-demo-session")
    
    runner = InMemoryRunner(agent=pipeline)
    
    try:
        with session.trace(name="deployment_run"):
            # Trigger the workflow
            await runner.run_debug("Start the deployment pipeline.")
            
    except Exception as e:
        print(f"\n[Main] Exception caught in top-level trace: {e}")
        # AgentNeo would capture this exception in the trace visualization
        
    print("\n[AgentNeo] Trace finished. In the dashboard, you would see:")
    print("1. 'trainer' span: Success.")
    print("2. 'backup_ops' span: Tool call 'mock_gsutil_backup' throwing OSError.")
    print("3. LLM observing the OSError in history and generating the 'CRITICAL FAILURE' response.")

if __name__ == "__main__":
    asyncio.run(main())
