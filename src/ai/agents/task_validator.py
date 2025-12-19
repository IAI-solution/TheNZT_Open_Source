from .base_agent import BaseAgent
from src.ai.ai_schemas.structured_responses import ValidationFeedback
from src.ai.agent_prompts.task_validator import SYSTEM_PROMPT
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
import json
from src.ai.llm.model import get_llm, get_llm_alt
#from src.ai.llm.config import TaskValidationConfig
from src.ai.llm.config_openai import  TaskValidationConfig

tvc = TaskValidationConfig()


class TaskValidation(BaseAgent):
    def __init__(self):
        super().__init__()
        self.model = get_llm(tvc.MODEL, tvc.TEMPERATURE, tvc.MAX_TOKENS)
        self.model_alt = get_llm_alt(tvc.ALT_MODEL, tvc.ALT_TEMPERATURE, tvc.ALT_MAX_TOKENS)
        self.response_schema = ValidationFeedback
        self.system_prompt = SYSTEM_PROMPT

    def format_input_prompt(self, state: Dict[str, Any]) -> str:
        current_task = state.get('current_task', {})
        task_messages = current_task.get('task_messages', [])

        agent_task = current_task.get('agent_task', '')
        agent_name = current_task.get('agent_name', '')

        messages_str = task_messages[-1].content

        input_prompt = (
            f"Agent Name: {agent_name}\n"
            f"Agent Task: {agent_task}\n"
            f"Agent Response:\n{messages_str}\n\n"
            "Please evaluate the response and return your validation."
            f"\n{state['user_metadata']}\n"
        )

        return input_prompt

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        input_prompt = self.format_input_prompt(state)
        system_message = SystemMessage(content=self.system_prompt)
        human_message = HumanMessage(content=input_prompt)

        try:
            response = self.model.invoke(
                input=[system_message, human_message], response_format=self.response_schema)
        except Exception as e:
            print(f"Falling back to alternate model: {str(e)}")
            try:
                response = self.model_alt.invoke(
                    input=[system_message, human_message], response_format=self.response_schema)
            except Exception as e:
                print(f"Error occurred in fallback model: {str(e)}")
                raise e

        validation_result = json.loads(response.content)

        return validation_result


task_validation = TaskValidation()
