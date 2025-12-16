import asyncio
import json
import subprocess
from typing import AsyncGenerator, List
from unittest.mock import MagicMock, patch

from google.genai import types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.agents import SequentialAgent, LlmAgent
from google.adk.runners import InMemoryRunner

# Import the real tool definition
from gcs_tools import move_files_to_bucket

# --- 1. Simulated Infrastructure (MockStorage) ---
# Used by Scanner to "list" files
class MockStorage:
    def __init__(self):
        self.files = {
            "report_current.txt": {"size": "1MB", "days_old": 2, "type": "txt"},
            "access_logs_2020.log": {"size": "500MB", "days_old": 1500, "type": "log"},
            "temp_data_old.tmp": {"size": "50MB", "days_old": 45, "type": "tmp"},
            "project_specs.pdf": {"size": "2MB", "days_old": 5, "type": "pdf"}
        }

    def list_files(self) -> str:
        return json.dumps(self.files, indent=2)

storage = MockStorage()

def list_directory_func():
    return storage.list_files()

# --- 2. Mock LLM ---

class MockToolLlm(BaseLlm):
    model: str = "mock-tool-model"

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        
        full_context = ""
        # Reconstruct context from request
        if llm_request.config.system_instruction:
             sys_inst = llm_request.config.system_instruction
             if isinstance(sys_inst, str):
                 full_context += f"[System]: {sys_inst}\n"
             elif hasattr(sys_inst, 'parts'):
                 for part in sys_inst.parts:
                     if part.text: full_context += f"[System]: {part.text}\n"

        for content in llm_request.contents:
            for part in content.parts:
                if part.text: full_context += f"[{content.role}]: {part.text}\n"
                if part.function_response:
                     full_context += f"[Function Output]: {part.function_response.response}\n"

        response_content = None

        # --- Agent 1: Scanner ---
        if "List all files" in full_context:
            if "[Function Output]" in full_context:
                response_content = types.Content(role='model', parts=[types.Part(text="Files listed.")])
            else:
                fc = types.FunctionCall(name="list_directory_func", args={})
                response_content = types.Content(role='model', parts=[types.Part(function_call=fc)])

        # --- Agent 2: Archivist ---
        elif "Identify files older than 30 days" in full_context:
            if "access_logs_2020.log" in full_context:
                 response_text = "Found candidates: 'access_logs_2020.log' and 'temp_data_old.tmp'."
            else:
                 response_text = "No files found."
            response_content = types.Content(role='model', parts=[types.Part(text=response_text)])

        # --- Agent 3: Mover (Using gsutil) ---
        elif "Move the identified files" in full_context:
            
            # Check if we just finished a tool call
            last_was_fr = False
            if llm_request.contents and llm_request.contents[-1].parts[0].function_response:
                last_was_fr = True

            if last_was_fr:
                 response_content = types.Content(role='model', parts=[types.Part(text="Transfer complete.")])
            else:
                 # Extract files and generate call to move_files_to_bucket
                 files_to_move = []
                 if "access_logs_2020.log" in full_context:
                     files_to_move.append("access_logs_2020.log")
                 if "temp_data_old.tmp" in full_context:
                     files_to_move.append("temp_data_old.tmp")
                
                 if files_to_move:
                     fc = types.FunctionCall(
                         name="move_files_to_bucket",
                         args={
                             "filenames": files_to_move,
                             "bucket_name": "corporate-archive-bucket-v1"
                         }
                     )
                     response_content = types.Content(role='model', parts=[types.Part(function_call=fc)])
                 else:
                     response_content = types.Content(role='model', parts=[types.Part(text="No files to move.")])

        else:
             response_content = types.Content(role='model', parts=[types.Part(text="Done.")])

        yield LlmResponse(partial=False, content=response_content)

mock_llm = MockToolLlm()

# --- 3. Agents ---

scanner = LlmAgent(
    name="scanner",
    model=mock_llm,
    instruction="List all files.",
    tools=[list_directory_func]
)

archivist = LlmAgent(
    name="archivist",
    model=mock_llm,
    instruction="Identify files older than 30 days."
)

mover = LlmAgent(
    name="mover",
    model=mock_llm,
    instruction="Move the identified files to the bucket using gsutil.",
    tools=[move_files_to_bucket] # Using the real tool definition
)

workflow = SequentialAgent(
    name="gsutil_workflow",
    sub_agents=[scanner, archivist, mover]
)

# --- 4. Main Execution with Mocked Subprocess ---

async def main():
    runner = InMemoryRunner(agent=workflow)

    # We patch subprocess.run so we don't actually need gsutil installed or credentials
    with patch("subprocess.run") as mock_run:
        # Configure mock to simulate success
        mock_run.return_value = MagicMock(returncode=0, stdout="OK")
        
        print("Starting GSUtil Archive Workflow...")
        print("-" * 50)
        
        await runner.run_debug("Start archiving.")
        
        print("-" * 50)
        print("Verifying tool execution:")
        # Check if subprocess.run was called with expected gsutil commands
        found_calls = 0
        for call in mock_run.call_args_list:
            args = call[0][0] # The command list
            if args[0] == "gsutil" and args[1] == "mv":
                print(f"  [EXEC] {' '.join(args)}")
                found_calls += 1
        
        if found_calls == 2:
            print("\nSUCCESS: Verified 'gsutil mv' was called for both files.")
            print("Note: 'gsutil mv' implicitly verifies checksums before removing source.")
        else:
            print(f"\nWARNING: Expected 2 gsutil calls, found {found_calls}.")

if __name__ == "__main__":
    asyncio.run(main())
