import asyncio
import agentneo
from typing import AsyncGenerator

# Import necessary ADK components
from google.genai import types
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.agents import SequentialAgent, ParallelAgent, LlmAgent
from google.adk.runners import InMemoryRunner

# --- AgentNeo Integration ---
# AgentNeo allows tracing specific functions or the entire execution flow.
# Here we define a TracedMockLlm that explicitly decorates the generation method.

class TracedMockLlm(BaseLlm):
    model: str = "mock-model-traced"

    # We decorate the generation method to capture inputs and outputs in AgentNeo
    @agentneo.trace(name="llm_generate", input_args=["llm_request"])
    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        
        # --- Logic copied from demo_workflow.py MockLlm ---
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
        
        for content in reversed(llm_request.contents):
            if content.role == 'user':
                for part in content.parts:
                    if part.text:
                        last_user_text += part.text + "\n"
                break
        
        full_context = prompt_text + "\n" + history_text
        response_text = "I am a mock response."
        
        if "safety gatekeeper" in full_context:
            if "Cooking" in last_user_text or "cooking" in last_user_text:
                response_text = "REJECTED"
            else:
                response_text = "APPROVED"
        elif "benefits of the topic" in full_context:
            if "status: REJECTED" in full_context: 
                 response_text = "Analysis Skipped"
            else:
                 response_text = "1. Increased efficiency\n2. Automation of tasks\n3. New capabilities"
        elif "risks or downsides" in full_context:
             if "status: REJECTED" in full_context:
                 response_text = "Analysis Skipped"
             else:
                 response_text = "1. Job displacement\n2. Bias in algorithms\n3. Security vulnerabilities"
        elif "lead analyst" in full_context:
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

# --- Re-assemble Agents with Traced LLM ---

traced_llm = TracedMockLlm()

gatekeeper = LlmAgent(
    name="gatekeeper",
    model=traced_llm,
    instruction=(
        "You are a safety gatekeeper. You analyze the user's topic. "
        "If the topic involves 'cooking', set the status to 'REJECTED'. "
        "Otherwise, set it to 'APPROVED'. "
        "Return ONLY the status word."
    ),
    output_key="topic_status",
)

benefits_agent = LlmAgent(
    name="benefits_expert",
    model=traced_llm,
    instruction=(
        "Current topic status: {topic_status}. "
        "If status is REJECTED, reply with 'Analysis Skipped'. "
        "Otherwise, list 3 benefits of the topic."
    ),
    output_key="benefits_report",
)

risks_agent = LlmAgent(
    name="risks_expert",
    model=traced_llm,
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

aggregator = LlmAgent(
    name="aggregator",
    model=traced_llm,
    instruction=(
        "You are the lead analyst. "
        "Review the reports from the research team. "
        "Benefits Report: {benefits_report}. "
        "Risks Report: {risks_report}. "
        "Synthesize them into a final short summary. "
        "If the reports say 'Skipped', just apologize to the user."
    )
)

workflow = SequentialAgent(
    name="traced_workflow",
    sub_agents=[gatekeeper, research_team, aggregator]
)

async def main():
    print("Initializing AgentNeo Project...")
    # Typically you would call agentneo.init() here with credentials
    # agentneo.create_project(project_name="ADK Demo")
    
    runner = InMemoryRunner(agent=workflow)
    
    print("\n--- Starting Traced Execution ---")
    
    # Wrap the high-level execution in a trace
    # The inner LLM calls will be nested within this span
    try:
        # Create a session context
        # agentneo.start_session("adk-run-001")
        
        # We manually trace the run call
        @agentneo.trace(name="full_workflow_run")
        async def run_wrapper():
            await runner.run_debug("Please analyze 'Artificial Intelligence'.")
            
        await run_wrapper()
        
        print("\n--- Execution Complete ---")
        print("Traces captured. To view results, you would typically run:")
        print("  agentneo launch_dashboard")
        
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    asyncio.run(main())
