from .base_agent import BaseAgent
from typing import Dict, Any, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from .utils import get_context_messages_for_response
from src.ai.llm.model import get_llm, get_llm_alt
from src.ai.llm.config_old import MapConfig
from src.ai.ai_schemas.structured_responses import SingleLayerResponse
from src.ai.agent_prompts.map_agent import SYSTEM_PROMPT
from src.ai.tools.map_tools import tool_list
from langgraph.types import Command

mapc = MapConfig()

class MapAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.tools = tool_list
        self.model = get_llm(mapc.MODEL, mapc.TEMPERATURE, mapc.MAX_TOKENS)
        self.model_alt = get_llm_alt(mapc.ALT_MODEL, mapc.ALT_TEMPERATURE, mapc.ALT_MAX_TOKENS)
        self.system_prompt = SYSTEM_PROMPT
        self.response_schema = SingleLayerResponse

    def format_input_prompt(self, state: Dict[str, Any]) -> str:
        task = state['current_task']

        input_prompt = f"""### User Query: {state['user_query']}\n### Task Name: {task['task_name']}\n## Instruction: {task['agent_task']}\n\n{state['user_metadata']}\n"""

        if task.get('required_context') and state.get('task_list'):
            context_messages = get_context_messages_for_response(task['required_context'], state['task_list'])
            input_prompt += f"- Use the following information as **Context** to extract locations and related information: {context_messages}\n\n"

        return input_prompt

    def __call__(self, state: Dict[str, Any]) -> Command[Literal["Manager Agent", "Task Router"]]:
        task = state['current_task'].copy()

        input_prompt = self.format_input_prompt(state)
        system_message = SystemMessage(content=self.system_prompt)
        human_message = HumanMessage(content=input_prompt)


        agent_input = {"messages": [human_message]}

        try:
            agent = create_react_agent(model=self.model, tools=self.tools, response_format=self.response_schema, prompt=system_message)
            communication_log = agent.invoke(agent_input)

        except Exception as e:
            print(f"Falling back to alternate model: {str(e)}")
            try:
                agent = create_react_agent(model=self.model_alt, tools=self.tools, response_format=self.response_schema, prompt=system_message)
                communication_log = agent.invoke(agent_input)

            except Exception as e:
                print(f"Error occurred in fallback model: {str(e)}")
                raise e

        message_history = communication_log['messages']
        task['task_messages'] = communication_log['structured_response'].model_dump()

        if state['reasoning']:
            agent_name = "Manager Agent"
        else:
            agent_name = "Task Router"

        return Command(
            goto=agent_name,
            update={
                "messages": message_history,
                "current_task": task
            }
        )
