import asyncio
import re
from typing import AsyncGenerator, Any

from google.genai import types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.agents import SequentialAgent, ParallelAgent, LlmAgent
from google.adk.runners import InMemoryRunner

class MockLlm(BaseLlm):
    model: str = "mock-model"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        
        # Combine system instruction and content to determine context
        prompt_text = ""
        if llm_request.config.system_instruction:
            sys_inst = llm_request.config.system_instruction
            if isinstance(sys_inst, str):
                prompt_text += sys_inst + "\n"
            elif hasattr(sys_inst, 'parts'):
                 for part in sys_inst.parts:
                     if part.text:
                        prompt_text += part.text + "\n"
        
        last_user_text = ""
        history_text = ""
        
        for content in llm_request.contents:
            for part in content.parts:
                if part.text:
                    history_text += part.text + "\n"
        
        # Extract specifically the last user message for Gatekeeper check
        for content in reversed(llm_request.contents):
            if content.role == 'user':
                for part in content.parts:
                    if part.text:
                        last_user_text += part.text + "\n"
                break
        
        full_context = prompt_text + "\n" + history_text
        
        response_text = "I am a mock response."
        
        # Logic for Gatekeeper
        if "safety gatekeeper" in full_context:
            # Check ONLY the last user input for the forbidden topic
            if "Cooking" in last_user_text or "cooking" in last_user_text:
                response_text = "REJECTED"
            else:
                response_text = "APPROVED"
        
        # Logic for Benefits
        elif "benefits of the topic" in full_context:
            # Check for the specific status pattern injected into instruction
            if "status: REJECTED" in full_context: 
                 response_text = "Analysis Skipped"
            else:
                 response_text = "1. Increased efficiency\n2. Automation of tasks\n3. New capabilities"

        # Logic for Risks
        elif "risks or downsides" in full_context:
             if "status: REJECTED" in full_context:
                 response_text = "Analysis Skipped"
             else:
                 response_text = "1. Job displacement\n2. Bias in algorithms\n3. Security vulnerabilities"

        # Logic for Aggregator
        elif "lead analyst" in full_context:
             # Check if "Analysis Skipped" is in the prompt (injected from reports)
             # The instruction will look like "Benefits Report: Analysis Skipped..."
             if "Analysis Skipped" in full_context:
                 response_text = "I apologize, but we cannot analyze this topic as it is outside our safety guidelines."
             else:
                 response_text = "FINAL REPORT:\nThe research team identified key benefits including efficiency and automation, while noting risks such as job displacement and bias."

        # Return response
        response = LlmResponse(
            partial=False,
            content=types.Content(
                role='model',
                parts=[types.Part(text=response_text)]
            )
        )
        yield response

# Create mock LLM
mock_llm = MockLlm()

# 1. Gatekeeper Agent
# Sets 'topic_status' in session state based on output
gatekeeper = LlmAgent(
    name="gatekeeper",
    model=mock_llm,
    instruction=(
        "You are a safety gatekeeper. You analyze the user's topic. "
        "If the topic involves 'cooking', set the status to 'REJECTED'. "
        "Otherwise, set it to 'APPROVED'. "
        "Return ONLY the status word."
    ),
    output_key="topic_status",
)

# 2. Parallel Processing Agents
# They use {topic_status} from session state in their instructions
benefits_agent = LlmAgent(
    name="benefits_expert",
    model=mock_llm,
    instruction=(
        "Current topic status: {topic_status}. "
        "If status is REJECTED, reply with 'Analysis Skipped'. "
        "Otherwise, list 3 benefits of the topic."
    ),
    output_key="benefits_report",
)

risks_agent = LlmAgent(
    name="risks_expert",
    model=mock_llm,
    instruction=(
        "Current topic status: {topic_status}. "
        "If status is REJECTED, reply with 'Analysis Skipped'. "
        "Otherwise, list 3 potential risks or downsides of the topic."
    ),
    output_key="risks_report",
)

research_team = ParallelAgent(
    name="research_team",
    sub_agents=[benefits_agent, risks_agent]
)

# 3. Aggregator
aggregator = LlmAgent(
    name="aggregator",
    model=mock_llm,
    instruction=(
        "You are the lead analyst. "
        "Review the reports from the research team. "
        "Benefits Report: {benefits_report}. "
        "Risks Report: {risks_report}. "
        "Synthesize them into a final short summary. "
        "If the reports say 'Skipped', just apologize to the user."
    )
)

# 4. Orchestrator
workflow = SequentialAgent(
    name="workflow",
    sub_agents=[gatekeeper, research_team, aggregator]
)

async def main():
    runner = InMemoryRunner(agent=workflow)
    
    print("--- Test 1: Valid Topic (AI) ---")
    await runner.run_debug("Please analyze 'Artificial Intelligence'.")
    
    print("\n" + "="*50 + "\n")
    
    print("--- Test 2: Invalid Topic (Cooking) ---")
    # New session for clean state
    await runner.run_debug("Please analyze 'Cooking Pasta'.", session_id="session_2")

if __name__ == "__main__":
    asyncio.run(main())