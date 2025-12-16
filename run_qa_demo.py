import asyncio
import os
import logging
from unittest.mock import MagicMock, patch

# Filter warning
class ApiKeyWarningFilter(logging.Filter):
    def filter(self, record):
        return "Both GOOGLE_API_KEY and GEMINI_API_KEY are set" not in record.getMessage()

logging.getLogger("google_genai._api_client").addFilter(ApiKeyWarningFilter())

from google.adk.runners import InMemoryRunner
from google.adk.agents import SequentialAgent

from blab_agents.wired_agents import inspector_agent, compliance_agent

qa_workflow = SequentialAgent(
    name="wired_qa_manager",
    sub_agents=[inspector_agent, compliance_agent]
)

MOCK_LINT_OUTPUT = """
src/main.py:10:5: E722 Do not use bare 'except'
src/utils.py:45:1: F401 'os' imported but unused
"""

MOCK_BANDIT_OUTPUT = """
>> Issue: [B102:exec_used] Use of exec detected.
   Severity: Medium   Confidence: High
   Location: src/dangerous.py:15
"""

async def main():
    print("Initializing Wired QA Workflow...")
    
    runner = InMemoryRunner(agent=qa_workflow)
    
    # Patch the tools to return interesting findings
    with patch("blab_agents.qa_manager.tools.check_qa_permissions", return_value="System Check Passed: All QA tools are available."):
        with patch("blab_agents.qa_manager.tools.read_repository_tree", return_value="src/main.py\nsrc/utils.py\nsrc/dangerous.py"):
            with patch("blab_agents.qa_manager.tools.run_linter", return_value=f"Linting issues found:\n{MOCK_LINT_OUTPUT}"):
                 with patch("blab_agents.qa_manager.tools.run_security_check", return_value=f"⚠️ Security Issues Found:\n{MOCK_BANDIT_OUTPUT}"):
                     with patch("blab_agents.qa_manager.tools.run_pylint", return_value="✅ No critical pylint errors."):
                
                        print("Starting run... (Check your TUI Monitor!)")
                        print("-" * 50)
                        
                        await runner.run_debug(
                            "Perform a full quality assurance audit on the repository. "
                            "Report the findings to HQ."
                        )
                
    print("-" * 50)
    print("Run complete.")

if __name__ == "__main__":
    asyncio.run(main())
