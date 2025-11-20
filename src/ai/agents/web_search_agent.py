from .base_agent import BaseAgent
from src.ai.tools.web_search_tools import tool_list
from src.ai.agent_prompts.web_search_agent import SYSTEM_PROMPT
from typing import Dict, Any, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from .utils import get_context_messages
from langgraph.prebuilt import create_react_agent
from src.ai.llm.model import get_llm, get_llm_alt
from src.ai.llm.config import WebSearchConfig
from langgraph.types import Command
from time import sleep


wsc = WebSearchConfig()


class WebSearchAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.model = get_llm(wsc.MODEL, wsc.TEMPERATURE)
        self.model_alt = get_llm_alt(wsc.ALT_MODEL, wsc.ALT_TEMPERATURE)
        self.tools = tool_list
        self.system_prompt = SYSTEM_PROMPT
        self.invoke_delay = 30.0

    def format_input_prompt(self, state: Dict[str, Any]) -> str:
        task = state['current_task']

        input_prompt = f"""### Task Name: {task['task_name']}\n### Instruction: {task['instructions']}
### Expected Output: {task['expected_output']}\n{state['user_metadata']}\n"""

        if task.get('task_feedback'):
            input_prompt += f"""\n### Feedback from Previous Iteration:\n{task.get('task_feedback')}
### Note for This Iteration: Please improve the results based on the feedback provided above. 
Address any identified issues and enhance the overall quality of the output.\n"""

        return input_prompt

    def __call__(self, state: Dict[str, Any]) -> Command[Literal["Manager Agent", "Task Router"]]:
        task = state['current_task'].copy()

        input_prompt = self.format_input_prompt(state)
        system_message = SystemMessage(content=self.system_prompt)
        human_message = HumanMessage(content=input_prompt)

        context_messages = []
        if task.get('required_context') and state.get('task_list'):
            context_messages = get_context_messages(
                task['required_context'], state['task_list'])

        input = {"messages": context_messages + [human_message]}
        
        sleep(self.invoke_delay)

        try:
            agent = create_react_agent(model=self.model, tools=self.tools, prompt=system_message)
            communication_log = agent.invoke(input)

        except Exception as e:
            print(f"Falling back to alternate model: {str(e)}")
            sleep(self.invoke_delay)
            try:
                agent = create_react_agent(
                    model=self.model_alt, tools=self.tools, prompt=system_message)
                communication_log = agent.invoke(input)

            except Exception as e:
                print(f"Error occurred in fallback model: {str(e)}")
                raise e

        message_history = communication_log['messages']
        filtered_message_history = [
            msg for msg in message_history if msg not in context_messages]
        task['task_messages'] = filtered_message_history
        
        if state['reasoning']:
            agent_name = "Manager Agent"
        else:
            agent_name = "Task Router"

        return Command(
            goto=agent_name,
            update={
                "messages": filtered_message_history,
                "current_task": task
            }
        )
