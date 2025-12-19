from .base_agent import BaseAgent
from src.ai.agent_prompts.validation_agent import SYSTEM_PROMPT
from typing import Dict, Any, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from src.ai.ai_schemas.structured_responses import ValidationFeedback
from langgraph.types import Command, interrupt
from langgraph.graph import END
import json
from src.ai.llm.model import get_llm, get_llm_alt
#from src.ai.llm.config import ValidationConfig
from src.ai.llm.config import  ValidationConfig

vc= ValidationConfig()


class ValidationAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.model = get_llm(vc.MODEL, vc.TEMPERATURE, vc.MAX_TOKENS)
        self.model_alt = get_llm_alt(vc.ALT_MODEL, vc.ALT_TEMPERATURE, vc.ALT_MAX_TOKENS)
        self.system_prompt = SYSTEM_PROMPT
        self.response_schema = ValidationFeedback

    def format_input_prompt(self, state: Dict[str, Any]) -> str:
        input_prompt = (
            "Validate following Proposed Response generated for the input User Query.",
            f"### User Query: {state['user_query']}\n{state['user_metadata']}\n",
            f"### Proposed Response:\n{state['final_response']}",
        )
        return "\n".join(input_prompt)

  
    def __call__(self, state: Dict[str, Any]) -> Command[Literal["Planner Agent", "Manager Agent", "__end__"]]:
        FEEDBACK_CYCLE_LIMIT = 3

        if state.get('feedback_cycle', 0) >= FEEDBACK_CYCLE_LIMIT:
            return Command(
                goto=END,
                update={
                    "validation_result": {"is_valid": "Fully Correct Response", "feedback": "Maximum retries reached"},
                    "feedback_cycle": state.get('feedback_cycle', 0),
                    "current_task": None
                }
            )

        input_prompt = self.format_input_prompt(state)
        system_message = SystemMessage(content=self.system_prompt)
        human_message = HumanMessage(content=input_prompt)

        try:
            response = self.model.invoke(
                input=[system_message, human_message],
                response_format=self.response_schema
            )
        except Exception as e:
            print(f"Falling back to alternate model: {str(e)}")
            try:
                response = self.model_alt.invoke(
                    input=[system_message, human_message],
                    response_format=self.response_schema
                )
            except Exception as e:
                print(f"Error occurred in fallback model: {str(e)}")
                raise e

        validation_result = json.loads(response.content)

        new_cycle = state.get('feedback_cycle', 0) + (1 if validation_result['is_valid'] == "Incorrect Response" else 0)

        if validation_result['is_valid'] in ["Fully Correct Response", "Partially Correct Response"]:
            if validation_result['is_valid'] == "Fully Correct Response":
                validation_result['feedback'] = "No Feedback"
            return Command(
                goto=END,
                update={
                    "validation_result": validation_result,
                    "feedback_cycle": new_cycle,
                    # "messages": [human_message, response]
                }
            )

        human_feedback = interrupt({
            "validation_feedback": validation_result.get('feedback', 'No specific feedback provided'),
            "current_response": state['final_response']
        })

        human_response = human_feedback.get('human_response')
        feedback = human_feedback.get('validation_feedback', 'No specific feedback provided')
        # print(human_feedback)

        if human_response.lower() in ['n', 'no']:
            return Command(
                goto=END,
                update={
                    "validation_result": {"is_valid": "Partially Correct Response", "feedback": "Manually approved"},
                    "feedback_cycle": state.get('feedback_cycle', 0),
                    "human_intervention": human_feedback,
                    "current_task": None
                }
            )
        elif human_response.lower() in ['y', 'yes']:
            if state['reasoning']:
                agent_name = "Manager Agent"
            else:
                agent_name = "Planner Agent"

            return Command(
                goto=agent_name,
                update={
                    "validation_result": {"is_valid": "Incorrect Response", "feedback": feedback},
                    "feedback_cycle": state.get('feedback_cycle', 0) + 1,
                    "human_intervention": human_feedback,
                    "current_task": None
                }
            )
