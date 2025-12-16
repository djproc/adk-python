import asyncio
import os
import logging
from unittest.mock import MagicMock, patch

# Configure logging to suppress specific warning from google_genai
class ApiKeyWarningFilter(logging.Filter):
    def filter(self, record):
        return "Both GOOGLE_API_KEY and GEMINI_API_KEY are set" not in record.getMessage()

# Apply to specific logger where the message originates
logging.getLogger("google_genai._api_client").addFilter(ApiKeyWarningFilter())
logging.getLogger("google_genai.types").addFilter(ApiKeyWarningFilter()) # For the other warning about non-text parts if desired

from google.adk.runners import InMemoryRunner
from google.adk.agents import SequentialAgent

# Import the agents that we "wired" up with reporting capabilities
from blab_agents.wired_agents import scanner_agent, archivist_agent, mover_agent

# Re-assemble the workflow using the modified agents
wired_workflow = SequentialAgent(
    name="wired_archive_manager",
    sub_agents=[scanner_agent, archivist_agent, mover_agent]
)

# Mock data for the tools to use (so we don't need real GCS bucket)
MOCK_FILES = {
    "report_current.txt": {"size": "1MB", "days_old": 2, "type": "txt"},
    "access_logs_2020.log": {"size": "500MB", "days_old": 1500, "type": "log"},
    "temp_data_old.tmp": {"size": "50MB", "days_old": 45, "type": "tmp"},
    "project_specs.pdf": {"size": "2MB", "days_old": 5, "type": "pdf"}
}

async def main():
    print("Initializing Wired Archive Workflow...")
    
    runner = InMemoryRunner(agent=wired_workflow)
    
    # We patch the tools to simulate success and valid data
    # 1. Patch 'check_system_permissions' to always pass
    # 2. Patch 'list_local_files' to return our mock JSON
    # 3. Patch 'subprocess.run' for the Mover's gsutil call
    
    with patch("blab_agents.archive_manager.tools.check_system_permissions", return_value="System Check Passed"):
        with patch("blab_agents.archive_manager.tools.list_local_files") as mock_list:
            import json
            mock_list.return_value = json.dumps(MOCK_FILES, indent=2)
            
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="OK")
                
                print("Starting run... (Check your TUI Monitor!)")
                print("-" * 50)
                
                # We trigger the workflow
                # The prompt explicitly mentions the tool requirement to ensure the model picks it up
                await runner.run_debug(
                    "Please scan the system, identify old files, and move them to the archive. "
                    "Remember to report your status to HQ."
                )
                
    print("-" * 50)
    print("Run complete.")

if __name__ == "__main__":
    asyncio.run(main())
