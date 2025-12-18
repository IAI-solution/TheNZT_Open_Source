from .base_agent import BaseAgent
from src.ai.ai_schemas.structured_responses import ExecutorAgentOutput
from src.ai.agent_prompts.executor_agent import SYSTEM_PROMPT
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from src.ai.llm.model import get_llm, get_llm_alt
from src.ai.llm.config import ExecutorConfig
import json
from time import sleep
import re
import logging
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

        # Try to parse response.content as JSON first; if that fails,
        # attempt a forgiving plain-text parser that extracts numbered
        # task blocks like:
        # 1. task_name: ...\n   agent: ...\n   instruction: ...
        content_obj = None
        content_str = ''
        try:
            if isinstance(response.content, (dict, list)):
                content_obj = response.content
            else:
                content_str = str(response.content or '').strip()
                if content_str:
                    content_obj = json.loads(content_str)
                else:
                    content_obj = None
        except Exception as e:
            logging.warning("ExecutorAgent: response.content is not valid JSON; falling back to text parser. Error: %s", str(e))
            # First: try re-prompting the model to return strict JSON (N retries).
            parsed_from_reprompt = None
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    logging.info("ExecutorAgent: attempting JSON-only re-prompt (attempt %s/%s)", attempt+1, max_retries)
                    json_instruct = (
                        "You must ONLY return valid JSON matching this schema:\n"
                        "{\"task_list\": [{\"task_name\": string, \"agent_name\": string, \"agent_task\": string, \"instructions\": string, \"expected_output\": string}]}\n\n"
                        "Do NOT include any explanatory text. If a field is unknown, use an empty string.\n\n"
                        "Here is the model output that needs to be converted to JSON:\n\n" + content_str + "\n\n"
                        "Return only JSON."
                    )
                    reprompt_msg = HumanMessage(content=json_instruct)
                    # small delay before invoking again
                    sleep(self.invoke_delay)
                    try:
                        retry_resp = self.model.invoke(input=[system_message, reprompt_msg])
                    except Exception:
                        # try alternate model once
                        logging.warning("ExecutorAgent: primary model failed on re-prompt, trying alternate model")
                        sleep(self.invoke_delay)
                        retry_resp = self.model_alt.invoke(input=[system_message, reprompt_msg])

                    retry_content = getattr(retry_resp, 'content', '')
                    if isinstance(retry_content, (dict, list)):
                        parsed_from_reprompt = retry_content
                        break
                    retry_text = str(retry_content or '').strip()
                    if retry_text and retry_text[0] in ('{', '['):
                        try:
                            parsed_from_reprompt = json.loads(retry_text)
                            break
                        except Exception as _:
                            logging.warning("ExecutorAgent: re-prompt returned non-JSON or malformed JSON on attempt %s", attempt+1)
                            continue
                except Exception as exrp:
                    logging.exception("ExecutorAgent: exception during re-prompt attempt: %s", str(exrp))
                    continue

            if parsed_from_reprompt is not None:
                # we got structured JSON from the re-prompt; prefer it over text fallback
                content_obj = parsed_from_reprompt
            else:
                # fallback: parse plain text into structured task list
                try:
                    # Split into lines and group blocks that start with a numbered item
                    lines = content_str.splitlines()
                    blocks = []
                    curr = []
                    for line in lines:
                        if re.match(r'^\s*\d+\.', line):
                            if curr:
                                blocks.append(curr)
                                curr = []
                            curr.append(line)
                        else:
                            if line.strip() == '' and curr:
                                # blank line separates blocks
                                blocks.append(curr)
                                curr = []
                            elif curr or line.strip():
                                curr.append(line)
                    if curr:
                        blocks.append(curr)

                    tasks = []
                    for block in blocks:
                        text = ' '.join([l.strip() for l in block])
                        # find key: value pairs for common fields
                        fields = {}
                        for m in re.finditer(r"(task_name|agent|agent_name|agent_task|instruction|instructions|expected_output|required_context)\s*:\s*(.*?)(?=\s+\b(task_name|agent|agent_name|agent_task|instruction|instructions|expected_output|required_context)\b\s*:|$)", text, flags=re.I):
                            k = m.group(1).strip().lower()
                            v = m.group(2).strip()
                            fields[k] = v

                        if not fields:
                            # if we couldn't extract structured fields, store raw block
                            tasks.append({'task_name': None, 'agent_name': None, 'agent_task': ' '.join([l.strip() for l in block]), 'instructions': '', 'expected_output': ''})
                            continue

                        task = {
                            'task_name': fields.get('task_name'),
                            'agent_name': fields.get('agent_name') or fields.get('agent'),
                            'agent_task': fields.get('agent_task') or fields.get('instructions') or fields.get('instruction') or '',
                            'instructions': fields.get('instructions') or fields.get('instruction') or '',
                            'expected_output': fields.get('expected_output') or '',
                        }
                        tasks.append(task)

                    content_obj = {'task_list': tasks}
                except Exception as e2:
                    logging.error("ExecutorAgent: fallback parsing also failed: %s", str(e2))
                    content_obj = None

        # Normalize content_obj to the expected structure
        if isinstance(content_obj, list):
            task_list = {'task_list': content_obj}
        elif isinstance(content_obj, dict) and 'task_list' in content_obj:
            task_list = content_obj
        elif isinstance(content_obj, dict) and all(isinstance(v, dict) for v in content_obj.values()):
            # maybe a mapping of tasks
            task_list = {'task_list': list(content_obj.values())}
        else:
            # As a last resort, wrap raw content into a single task
            if content_obj is None:
                logging.error('ExecutorAgent: No parsable task list found in response.content; returning empty task list.')
                task_list = {'task_list': []}
            else:
                task_list = {'task_list': [content_obj]}
        
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
