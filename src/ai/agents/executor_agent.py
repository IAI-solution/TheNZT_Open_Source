from .base_agent import BaseAgent
from src.ai.ai_schemas.structured_responses import ExecutorAgentOutput
from src.ai.agent_prompts.executor_agent import SYSTEM_PROMPT
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from src.ai.llm.model import get_llm, get_llm_alt
from src.ai.llm.config import ExecutorConfig
import json
from time import sleep
from langgraph.prebuilt import create_react_agent

exc = ExecutorConfig()

class ExecutorAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.model = get_llm(exc.MODEL, exc.TEMPERATURE)
        self.model_alt = get_llm_alt(exc.ALT_MODEL, exc.ALT_TEMPERATURE)
        self.response_schema = ExecutorAgentOutput
        self.system_prompt = SYSTEM_PROMPT
        self.invoke_delay = 20.0

    def format_input_prompt(self, state: Dict[str, Any]) -> str:

        user_query = state.get('formatted_user_query', state['user_query'])

        input_prompt = "## Analyze the following User Query and generated task-list:"
        input_prompt += f"- User Query: {user_query}\n"
        input_prompt += f"- Plan Based on which task needs to be generated: {json.dumps(state['research_plan'], indent=4)}\n"

        input_prompt += f"\n{state['user_metadata']}\n\n"

        if state.get('doc_ids'):
            input_prompt += f"### Document IDs of user uploaded files: {state['doc_ids']}\n\n"

        if state.get('prev_doc_ids'):
            input_prompt += f"### The Latest User Query maybe based on these Previous Document IDs: {state['prev_doc_ids']}\n\n"

        print("----Executor Input----\n", input_prompt, "\n----Executor Input End----")
        return input_prompt

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        input_prompt = self.format_input_prompt(state)
        system_message = SystemMessage(content=self.system_prompt)
        human_message = HumanMessage(content=input_prompt)
        
        # input = {"messages": [human_message]}
        
        sleep(self.invoke_delay)
        try:
            # agent = create_react_agent(model=self.model, tools=self.tools, prompt=system_message)     
            # response = agent.invoke(input)
            response = self.model.invoke(
                input=[system_message, human_message], response_format=self.response_schema)
        except Exception as e:
            print(f"Falling back to alternate model: {str(e)}")
            sleep(self.invoke_delay)
            try:
                # agent = create_react_agent(model=self.model_alt, tools=self.tools, prompt=system_message) 
                # response = agent.invoke(input)
                response = self.model_alt.invoke(
                    input=[system_message, human_message], response_format=self.response_schema)
            except Exception as e:
                print(f"Error occurred in fallback model: {str(e)}")
                raise e
            
        print("Xecutor AGent - task_list vvv")
        print(f"response = {response}")
        print("-"*10)
        print(f"response.content = {response.content}")
        print("-"*10)

        task_list = json.loads(response.content)
        
        print("-"*10)
        print(f"task_list = {task_list}")
        print("Xecutor AGent - task_list AAA")

        # map_task = {
        #     'task_name': 'Extract location data', 
        #     'agent_name': 'Map Agent', 
        #     'agent_task': 'Based on User Query extract all the relevant locations from the given context.', 
        #     'instructions': 'Perform task.',
        #     'expected_output': 'Provide coordinates of the locations.',
        #     'required_context': [item['task_name'] for item in task_list['task_list'][:-1]]
        # }

        # task_list['task_list'].insert(len(task_list['task_list'])-1, map_task)

        tasks = task_list['task_list']
        last_task = tasks[-1]
        if last_task.get('agent_name') != 'Response Generator Agent':
            previous_task_names = [task['task_name'] for task in tasks]
            next_task_number = len(tasks) + 1
            new_task_name = f'task_{next_task_number}'

            response_generator_task = {
                'task_name': new_task_name,
                'agent_name': 'Response Generator Agent',
                'agent_task': 'Synthesize the analyzed information into a concise, coherent summary that captures the essence of the documents while maintaining clarity and relevance. Conclude and prepare the final summary output, ensuring it is well-structured, highlights key points, and addresses any nuances or complexities found in the documents.',
                'instructions': 'Using the detailed analysis reports from all previous agent tasks, synthesize the information into a clear, concise, and coherent summary that captures the essence of the documents. Ensure the summary is well-structured, highlights key points, and addresses any nuances or complexities found in the documents. Provide the final summary in English.',
                'expected_output': 'A well-structured, concise, and coherent summary capturing the key points, main ideas, and any nuances or complexities from all analyzed documents. The summary should be in English.',
                'required_context': previous_task_names
            }
            task_list['task_list'].append(response_generator_task)

        return {
            "task_list": task_list['task_list'],
            "messages": [human_message, response],
        }
