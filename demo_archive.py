import asyncio
import json
from typing import AsyncGenerator, List
from datetime import datetime, timedelta

from google.genai import types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool

# --- 1. Simulated Infrastructure ---

class MockStorage:
    def __init__(self):
        self.files = {
            "report_current.txt": {"size": "1MB", "days_old": 2, "type": "txt"},
            "access_logs_2020.log": {"size": "500MB", "days_old": 1500, "type": "log"},
            "temp_data_old.tmp": {"size": "50MB", "days_old": 45, "type": "tmp"},
            "project_specs.pdf": {"size": "2MB", "days_old": 5, "type": "pdf"}
        }
        self.bucket = []

    def list_files(self) -> str:
        """Lists files in the mock directory."""
        return json.dumps(self.files, indent=2)

    def move_to_archive(self, filenames: List[str]) -> str:
        """Moves specified files to the archive bucket."""
        moved = []
        not_found = []
        for name in filenames:
            if name in self.files:
                file_data = self.files.pop(name)
                self.bucket.append({"name": name, **file_data})
                moved.append(name)
            else:
                not_found.append(name)
        
        result = f"Moved to bucket: {moved}"
        if not_found:
            result += f". Failed to find: {not_found}"
        return result

storage = MockStorage()

# Wrappers for ADK Tools
def list_directory_func():
    return storage.list_files()

def archive_files_func(filenames: List[str]):
    return storage.move_to_archive(filenames)

# --- 2. Mock LLM with Tool Logic ---

class MockToolLlm(BaseLlm):
    model: str = "mock-tool-model"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        
        # 1. Build Full Context (System Instruction + Contents)
        full_context = ""
        
        # Extract System Instruction (where Agent Instruction lives)
        if llm_request.config.system_instruction:
            sys_inst = llm_request.config.system_instruction
            if isinstance(sys_inst, str):
                full_context += f"[System]: {sys_inst}\n"
            elif hasattr(sys_inst, 'parts'):
                 for part in sys_inst.parts:
                     if part.text:
                        full_context += f"[System]: {part.text}\n"

        # Extract Conversation History
        for content in llm_request.contents:
            role_prefix = f"[{content.role}]: "
            for part in content.parts:
                if part.text:
                    full_context += f"{role_prefix}{part.text}\n"
                if part.function_response:
                     full_context += f"[Function Output]: {part.function_response.response}\n"

        # print(f"DEBUG CONTEXT:\n{full_context}\n{'='*20}") # Uncomment for debugging

        response_content = None

        # --- Logic for Agent 1: Scanner ---
        if "List all files" in full_context:
            # Check if we already have the function output
            if "[Function Output]" in full_context:
                # Tool has run, generate summary to finish turn
                response_content = types.Content(
                    role='model',
                    parts=[types.Part(text="I have listed the files from storage.")]
                )
            else:
                # Tool hasn't run, call it
                fc = types.FunctionCall(
                    name="list_directory_func",
                    args={}
                )
                response_content = types.Content(
                    role='model',
                    parts=[types.Part(function_call=fc)]
                )

        # --- Logic for Agent 2: Archivist ---
        elif "Identify files older than 30 days" in full_context:
            # Simulate logic
            if "access_logs_2020.log" in full_context:
                 response_text = "Found candidates: 'access_logs_2020.log' and 'temp_data_old.tmp'."
            else:
                 response_text = "No files found."
            
            response_content = types.Content(
                role='model',
                parts=[types.Part(text=response_text)]
            )

        # --- Logic for Agent 3: Mover ---
        elif "Move the identified files" in full_context:
            # Check the LAST content object specifically to see if we just finished a tool call
            last_content_was_fr = False
            if llm_request.contents:
                last_content = llm_request.contents[-1]
                # print(f"DEBUG: Mover last content role: {last_content.role}")
                if last_content.parts and last_content.parts[0].function_response:
                    last_content_was_fr = True

            if last_content_was_fr:
                 response_content = types.Content(
                    role='model',
                    parts=[types.Part(text="Archiving complete.")]
                )
            else:
                # Logic to decide to call tool
                 files_to_move = []
                 if "access_logs_2020.log" in full_context:
                     files_to_move.append("access_logs_2020.log")
                 if "temp_data_old.tmp" in full_context:
                     files_to_move.append("temp_data_old.tmp")
                
                 if files_to_move:
                     # Prevent infinite loop: Check if we ALREADY called this function recently in the context
                     # This is a hack for the mock. Real model would see it in history.
                     # But here, we must ensure we don't just keep generating the same FC if the previous turn didn't result in an FR for some reason.
                     # Actually, if last_content_was_fr is False, and we see files, we generate FC.
                     
                     fc = types.FunctionCall(
                         name="archive_files_func",
                         args={"filenames": files_to_move}
                     )
                     response_content = types.Content(
                         role='model',
                         parts=[types.Part(function_call=fc)]
                     )
                 else:
                     response_content = types.Content(
                         role='model',
                         parts=[types.Part(text="No files to move.")]
                     )

        # Default / Fallback
        else:
             response_content = types.Content(
                role='model',
                parts=[types.Part(text="Task completed.")]
            )

        yield LlmResponse(partial=False, content=response_content)

mock_llm = MockToolLlm()

# --- 3. Agent Definitions ---

# Agent 1: Scanner
# Has the tool to list files.
scanner = LlmAgent(
    name="scanner",
    model=mock_llm,
    instruction="List all files in the current storage.",
    tools=[list_directory_func]
)

# Agent 2: Archivist
# Pure logic agent (no tools), analyzes the conversation history.
archivist = LlmAgent(
    name="archivist",
    model=mock_llm,
    instruction="Identify files older than 30 days from the previous list."
)

# Agent 3: Mover
# Has the tool to move files.
mover = LlmAgent(
    name="mover",
    model=mock_llm,
    instruction="Move the identified files to the archive bucket.",
    tools=[archive_files_func]
)

# Orchestrator
archive_workflow = SequentialAgent(
    name="archive_workflow",
    sub_agents=[scanner, archivist, mover]
)

# --- 4. Main Execution ---

async def main():
    runner = InMemoryRunner(agent=archive_workflow)
    
    print(f"Initial Storage: {list(storage.files.keys())}")
    print(f"Initial Bucket: {storage.bucket}")
    print("-" * 50)

    # We send a trigger message to start the sequence
    await runner.run_debug("Please start the archiving process.")
    
    print("-" * 50)
    print(f"Final Storage: {list(storage.files.keys())}")
    print(f"Final Bucket: {[f['name'] for f in storage.bucket]}")

if __name__ == "__main__":
    asyncio.run(main())
