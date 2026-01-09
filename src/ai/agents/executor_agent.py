from .base_agent import BaseAgent
from src.ai.ai_schemas.structured_responses import ExecutorAgentOutput
from src.ai.agent_prompts.executor_agent import SYSTEM_PROMPT
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from src.ai.llm.model import get_llm, get_llm_alt
from src.ai.llm.config import ExecutorConfig
import json
import re
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
        
        # Detect if using Ollama
        self.is_ollama = self._is_ollama_model(exc.MODEL)
        self.is_ollama_alt = self._is_ollama_model(exc.ALT_MODEL)

    def _is_ollama_model(self, model_name: str) -> bool:
        """Check if the model is from Ollama"""
        ollama_indicators = ['ollama', 'llama', 'mistral', 'qwen', 'kimi', 'deepseek', 'gemma', 'phi']
        return any(indicator in model_name.lower() for indicator in ollama_indicators)

    def _extract_json_from_response(self, content: str) -> dict:
        """Extract JSON from markdown or mixed content"""
        # Try direct JSON parsing first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, content, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass
        
        # Try to find the largest JSON object in the text
        json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\})*)*\}))*\}'
        matches = re.findall(json_pattern, content, re.DOTALL)
        
        # Sort by length to get the most complete JSON object
        matches = sorted(matches, key=len, reverse=True)
        
        for match in matches:
            try:
                parsed = json.loads(match)
                # Validate it has expected structure
                if 'task_list' in parsed and isinstance(parsed['task_list'], list):
                    return parsed
            except json.JSONDecodeError:
                continue
        
        raise ValueError(f"Could not extract valid JSON from response. Content preview: {content[:500]}")

    def _get_json_instruction_prompt(self) -> str:
        """Get JSON format instructions for Ollama models"""
        schema_example = {
            "task_list": [
                {
                    "task_name": "task_1",
                    "agent_name": "Finance Data Agent",
                    "agent_task": "Fetch real-time stock data for Tesla",
                    "instructions": "Retrieve current stock price, market cap, and key financial metrics",
                    "expected_output": "Real-time financial data with metrics",
                    "required_context": []
                },
                {
                    "task_name": "task_2",
                    "agent_name": "Response Generator Agent",
                    "agent_task": "Generate summary of Tesla's financial position",
                    "instructions": "Create comprehensive summary using the financial data",
                    "expected_output": "Well-structured financial summary",
                    "required_context": ["task_1"]
                }
            ]
        }
        
        return f"""

**CRITICAL - OUTPUT FORMAT REQUIREMENTS**:
You MUST respond with ONLY valid JSON matching this EXACT structure:

{json.dumps(schema_example, indent=2)}

STRICT RULES:
1. NO markdown formatting (no ```json blocks)
2. NO explanations or text before/after the JSON
3. Start directly with {{ and end with }}
4. Each task MUST have ALL these fields:
   - task_name: string (e.g., "task_1", "task_2")
   - agent_name: string (exact agent name)
   - agent_task: string (clear task description)
   - instructions: string (detailed instructions)
   - expected_output: string (what output is expected)
   - required_context: array of strings (task_name values from previous tasks, or empty array [])
5. Ensure proper JSON syntax: quotes, commas, brackets
6. task_list must be an array of task objects

RESPOND WITH ONLY THE JSON OBJECT - NO OTHER TEXT.
"""

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

        # Add JSON instructions for Ollama models
        if self.is_ollama:
            input_prompt += self._get_json_instruction_prompt()

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
            if self.is_ollama:
                # Ollama: Don't use response_format, as it doesn't support it properly
                print("Using Ollama model without structured output")
                response = self.model.invoke(input=[system_message, human_message])
            else:
                # OpenAI/Azure: Use structured output
                print("Using OpenAI/Azure model with structured output")
                response = self.model.invoke(
                    input=[system_message, human_message], response_format=self.response_schema)
        except Exception as e:
            print(f"Falling back to alternate model: {str(e)}")
            sleep(self.invoke_delay)
            try:
                # agent = create_react_agent(model=self.model_alt, tools=self.tools, prompt=system_message) 
                # response = agent.invoke(input)
                if self.is_ollama_alt:
                    print("Using Ollama alternate model without structured output")
                    response = self.model_alt.invoke(input=[system_message, human_message])
                else:
                    print("Using OpenAI/Azure alternate model with structured output")
                    response = self.model_alt.invoke(
                        input=[system_message, human_message], response_format=self.response_schema)
            except Exception as e:
                print(f"Error occurred in fallback model: {str(e)}")
                raise e
            
        print("Xecutor Agent - task_list vvv")
        print(f"response = {response}")
        print("-"*10)
        print(f"response.content = {response.content}")
        print(f"response.content type: {type(response.content)}")
        print("-"*10)

        # Parse response based on model type and response format
        try:
            # Check for structured output (OpenAI/Azure)
            if hasattr(response, 'parsed') and response.parsed:
                print("Using parsed structured output")
                task_list = response.parsed.model_dump() if hasattr(response.parsed, 'model_dump') else response.parsed
            # Check if content is already a dict
            elif isinstance(response.content, dict):
                print("Response content is already a dict")
                task_list = response.content
            # Handle string responses (typical for Ollama)
            elif isinstance(response.content, str):
                print(f"Parsing string response (Ollama model: {self.is_ollama or self.is_ollama_alt})")
                if self.is_ollama or self.is_ollama_alt:
                    # Use robust JSON extraction for Ollama
                    task_list = self._extract_json_from_response(response.content)
                else:
                    # Direct JSON parsing for OpenAI/Azure string responses
                    task_list = json.loads(response.content)
            else:
                raise ValueError(f"Unexpected response type: {type(response.content)}")
            
            print("-"*10)
            print(f"task_list = {task_list}")
            print("Xecutor Agent - task_list AAA")
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"ERROR: Failed to parse response as JSON")
            print(f"Error details: {e}")
            print(f"Response content (first 1000 chars): {str(response.content)[:1000]}")
            print(f"Is Ollama model: {self.is_ollama or self.is_ollama_alt}")
            raise ValueError(
                f"LLM returned invalid format. Error: {e}\n"
                f"Model type: {'Ollama' if (self.is_ollama or self.is_ollama_alt) else 'OpenAI/Azure'}\n"
                f"Response preview: {str(response.content)[:500]}"
            )

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

# from .base_agent import BaseAgent
# from src.ai.ai_schemas.structured_responses import ExecutorAgentOutput
# from src.ai.agent_prompts.executor_agent import SYSTEM_PROMPT
# from typing import Dict, Any
# from langchain_core.messages import HumanMessage, SystemMessage
# from src.ai.llm.model import get_llm, get_llm_alt
# from src.ai.llm.config import ExecutorConfig
# import json
# from time import sleep
# from langgraph.prebuilt import create_react_agent

# exc = ExecutorConfig()

# class ExecutorAgent(BaseAgent):
#     def __init__(self):
#         super().__init__()
#         self.model = get_llm(exc.MODEL, exc.TEMPERATURE)
#         self.model_alt = get_llm_alt(exc.ALT_MODEL, exc.ALT_TEMPERATURE)
#         self.response_schema = ExecutorAgentOutput
#         self.system_prompt = SYSTEM_PROMPT
#         self.invoke_delay = 20.0

#     def format_input_prompt(self, state: Dict[str, Any]) -> str:

#         user_query = state.get('formatted_user_query', state['user_query'])

#         input_prompt = "## Analyze the following User Query and generated task-list:"
#         input_prompt += f"- User Query: {user_query}\n"
#         input_prompt += f"- Plan Based on which task needs to be generated: {json.dumps(state['research_plan'], indent=4)}\n"

#         input_prompt += f"\n{state['user_metadata']}\n\n"

#         if state.get('doc_ids'):
#             input_prompt += f"### Document IDs of user uploaded files: {state['doc_ids']}\n\n"

#         if state.get('prev_doc_ids'):
#             input_prompt += f"### The Latest User Query maybe based on these Previous Document IDs: {state['prev_doc_ids']}\n\n"

#         print("----Executor Input----\n", input_prompt, "\n----Executor Input End----")
#         return input_prompt

#     def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
#         input_prompt = self.format_input_prompt(state)
#         system_message = SystemMessage(content=self.system_prompt)
#         human_message = HumanMessage(content=input_prompt)
        
#         # input = {"messages": [human_message]}
        
#         sleep(self.invoke_delay)
#         try:
#             # agent = create_react_agent(model=self.model, tools=self.tools, prompt=system_message)     
#             # response = agent.invoke(input)
#             response = self.model.invoke(
#                 input=[system_message, human_message], response_format=self.response_schema)
#         except Exception as e:
#             print(f"Falling back to alternate model: {str(e)}")
#             sleep(self.invoke_delay)
#             try:
#                 # agent = create_react_agent(model=self.model_alt, tools=self.tools, prompt=system_message) 
#                 # response = agent.invoke(input)
#                 response = self.model_alt.invoke(
#                     input=[system_message, human_message], response_format=self.response_schema)
#             except Exception as e:
#                 print(f"Error occurred in fallback model: {str(e)}")
#                 raise e
            
#         print("Xecutor AGent - task_list vvv")
#         print(f"response = {response}")
#         print("-"*10)
#         print(f"response.content = {response.content}")
#         print("-"*10)

#         task_list = json.loads(response.content)
        
#         print("-"*10)
#         print(f"task_list = {task_list}")
#         print("Xecutor AGent - task_list AAA")

#         # map_task = {
#         #     'task_name': 'Extract location data', 
#         #     'agent_name': 'Map Agent', 
#         #     'agent_task': 'Based on User Query extract all the relevant locations from the given context.', 
#         #     'instructions': 'Perform task.',
#         #     'expected_output': 'Provide coordinates of the locations.',
#         #     'required_context': [item['task_name'] for item in task_list['task_list'][:-1]]
#         # }

#         # task_list['task_list'].insert(len(task_list['task_list'])-1, map_task)

#         tasks = task_list['task_list']
#         last_task = tasks[-1]
#         if last_task.get('agent_name') != 'Response Generator Agent':
#             previous_task_names = [task['task_name'] for task in tasks]
#             next_task_number = len(tasks) + 1
#             new_task_name = f'task_{next_task_number}'

#             response_generator_task = {
#                 'task_name': new_task_name,
#                 'agent_name': 'Response Generator Agent',
#                 'agent_task': 'Synthesize the analyzed information into a concise, coherent summary that captures the essence of the documents while maintaining clarity and relevance. Conclude and prepare the final summary output, ensuring it is well-structured, highlights key points, and addresses any nuances or complexities found in the documents.',
#                 'instructions': 'Using the detailed analysis reports from all previous agent tasks, synthesize the information into a clear, concise, and coherent summary that captures the essence of the documents. Ensure the summary is well-structured, highlights key points, and addresses any nuances or complexities found in the documents. Provide the final summary in English.',
#                 'expected_output': 'A well-structured, concise, and coherent summary capturing the key points, main ideas, and any nuances or complexities from all analyzed documents. The summary should be in English.',
#                 'required_context': previous_task_names
#             }
#             task_list['task_list'].append(response_generator_task)

#         return {
#             "task_list": task_list['task_list'],
#             "messages": [human_message, response],
#         }


# from .base_agent import BaseAgent
# from src.ai.ai_schemas.structured_responses import ExecutorAgentOutput
# from src.ai.agent_prompts.executor_agent import SYSTEM_PROMPT
# from typing import Dict, Any, List
# from langchain_core.messages import HumanMessage, SystemMessage
# from src.ai.llm.model import get_llm, get_llm_alt
# from src.ai.llm.config import ExecutorConfig
# import json
# from time import sleep
# import re
# from langgraph.prebuilt import create_react_agent

# exc = ExecutorConfig()

# class ExecutorAgent(BaseAgent):
#     def __init__(self):
#         super().__init__()
#         self.model = get_llm(exc.MODEL, exc.TEMPERATURE)
#         self.model_alt = get_llm_alt(exc.ALT_MODEL, exc.ALT_TEMPERATURE)
#         self.response_schema = ExecutorAgentOutput
#         self.system_prompt = SYSTEM_PROMPT
#         self.invoke_delay = 20.0

#     def _parse_task_list_text(self, content: str) -> Dict[str, Any]:
#         """
#         Fallback parser for when the model returns a text-based list instead of JSON.
#         Expected format is numbered tasks with fields like Task name, Agent, Instructions, Expected output.
#         """
#         print("Attempting to parse text response with fallback parser...")
        
#         # Normalize newlines
#         content = content.replace('\\n', '\n')
        
#         current_task = {}
#         lines = content.split('\n')
        
#         current_key = None
#         tasks = []
        
#         def flush_task():
#             if current_task:
#                 # Check conditions to save the task
#                 # We need at least task_name and instructions.
                
#                 if 'task_name' in current_task:
#                      if 'agent_task' not in current_task and 'instructions' in current_task:
#                          # Use brief of instructions for agent_task if missing
#                          current_task['agent_task'] = current_task['instructions'][:100]
                         
#                      if 'agent_name' in current_task:
#                          # Infer required_context from instructions
#                          # Look for references like "task 1", "task_1", etc.
#                          instructions = current_task.get('instructions', '')
#                          refs = re.findall(r'task[ _-]?(\d+)', instructions, re.IGNORECASE)
                         
#                          context = []
#                          for r in refs:
#                              idx = int(r) - 1
#                              if 0 <= idx < len(tasks):
#                                  context.append(tasks[idx]['task_name'])
                         
#                          if context:
#                              current_task['required_context'] = context
                             
#                          tasks.append(current_task.copy())
#                 current_task.clear()

#         for line in lines:
#             line = line.strip()
#             if not line:
#                 continue
            
#             # Check for header like "task_1 – Finance Data Agent" or "1. task_name: ..."
#             # Case A: "task_1 – Finance Data Agent"
            
#             header_match = re.match(r'^task_?\d+\s*[-–]\s*(?P<agent>.+)', line, re.IGNORECASE)
#             if header_match:
#                 flush_task()
#                 current_task['agent_name'] = header_match.group('agent').strip()
#                 continue

#             # Case B: Standard "Task name:" line
#             if re.match(r'^(\d+\.|-)?\s*(Task name|task_name):', line, re.IGNORECASE):
#                 if 'task_name' in current_task:
#                     flush_task()
                
#                 val = re.sub(r'^(\d+\.|-)?\s*(Task name|task_name):\s*', '', line, flags=re.IGNORECASE).strip()
#                 val = val.strip('“”"\'') 
#                 current_task['task_name'] = val
#                 continue
                
#             if re.match(r'^Agent:', line, re.IGNORECASE):
#                 val = re.sub(r'^Agent:\s*', '', line, flags=re.IGNORECASE).strip()
#                 current_task['agent_name'] = val
#                 continue
            
#             if re.match(r'^Instruction(s?):', line, re.IGNORECASE):
#                 val = re.sub(r'^Instruction(s?):\s*', '', line, flags=re.IGNORECASE).strip()
#                 current_task['instructions'] = val
#                 current_key = 'instructions'
#                 continue
                
#             if re.match(r'^(Expected output|expected_output):', line, re.IGNORECASE):
#                 val = re.sub(r'^(Expected output|expected_output):\s*', '', line, flags=re.IGNORECASE).strip()
#                 current_task['expected_output'] = val
#                 current_key = 'expected_output'
#                 continue
            
#             # Continuation of previous key
#             if current_key and line:
#                  if current_key in current_task:
#                      current_task[current_key] += " " + line
        
#         flush_task()
        
#         if not tasks:
#             print("Fallback parser failed to extract any tasks.")
#             raise ValueError("Could not parse task list from text content")
            
#         print(f"Fallback parser successfully extracted {len(tasks)} tasks.")
#         return {"task_list": tasks}

#     def format_input_prompt(self, state: Dict[str, Any]) -> str:

#         user_query = state.get('formatted_user_query', state['user_query'])

#         input_prompt = "## Analyze the following User Query and generated task-list:"
#         input_prompt += f"- User Query: {user_query}\n"
#         input_prompt += f"- Plan Based on which task needs to be generated: {json.dumps(state['research_plan'], indent=4)}\n"

#         input_prompt += f"\n{state['user_metadata']}\n\n"

#         if state.get('doc_ids'):
#             input_prompt += f"### Document IDs of user uploaded files: {state['doc_ids']}\n\n"

#         if state.get('prev_doc_ids'):
#             input_prompt += f"### The Latest User Query maybe based on these Previous Document IDs: {state['prev_doc_ids']}\n\n"

#         print("----Executor Input----\n", input_prompt, "\n----Executor Input End----")
#         return input_prompt

#     def _infer_context_for_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
#         """
#         Post-process tasks to infer required_context from instructions if missing.
#         """
#         for i, task in enumerate(tasks):
#             if not task.get('required_context'):
#                 instructions = task.get('instructions', '')
#                 # Look for references like "task 1", "task_1", etc.
#                 refs = re.findall(r'task[ _-]?(\d+)', instructions, re.IGNORECASE)
                
#                 context = []
#                 for r in refs:
#                     idx = int(r) - 1
#                     # Ensure we don't depend on ourselves or future tasks (cyclic/forward dependency)
#                     if 0 <= idx < i:
#                         context.append(tasks[idx]['task_name'])
                
#                 if context:
#                     task['required_context'] = context
#         return tasks

#     def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
#         input_prompt = self.format_input_prompt(state)
#         system_message = SystemMessage(content=self.system_prompt)
#         human_message = HumanMessage(content=input_prompt)
        
#         # input = {"messages": [human_message]}
        
#         sleep(self.invoke_delay)
#         try:
#             # agent = create_react_agent(model=self.model, tools=self.tools, prompt=system_message)     
#             # response = agent.invoke(input)
#             response = self.model.invoke(
#                 input=[system_message, human_message], response_format=self.response_schema)
#         except Exception as e:
#             print(f"Falling back to alternate model: {str(e)}")
#             sleep(self.invoke_delay)
#             try:
#                 # agent = create_react_agent(model=self.model_alt, tools=self.tools, prompt=system_message) 
#                 # response = agent.invoke(input)
#                 response = self.model_alt.invoke(
#                     input=[system_message, human_message], response_format=self.response_schema)
#             except Exception as e:
#                 print(f"Error occurred in fallback model: {str(e)}")
#                 raise e
            
#         print("Xecutor AGent - task_list vvv")
#         print(f"response = {response}")
#         print("-"*10)
#         print(f"response.content = {response.content}")
#         print("-"*10)

#         try:
#             task_list = json.loads(response.content)
#         except json.JSONDecodeError:
#             print("JSON Decode Error encountered. Trying fallback text parser...")
#             try:
#                 task_list = self._parse_task_list_text(response.content)
#             except Exception as e:
#                 print(f"Fallback parsing also failed: {str(e)}")
#                 raise e
        
#         # Ensure task_list is treated as a dict with 'task_list' key
#         if not isinstance(task_list, dict) or 'task_list' not in task_list:
#              if isinstance(task_list, list):
#                  task_list = {'task_list': task_list}
#              else:
#                  print(f"Unexpected structure of task_list: {type(task_list)}")
        
#         # Post-process to infer context
#         if 'task_list' in task_list:
#             task_list['task_list'] = self._infer_context_for_tasks(task_list['task_list'])

#         print("-" * 10)
#         print(f"task_list = {task_list}")
#         print("Xecutor AGent - task_list AAA")

#         # map_task = {
#         #     'task_name': 'Extract location data', 
#         #     'agent_name': 'Map Agent', 
#         #     'agent_task': 'Based on User Query extract all the relevant locations from the given context.', 
#         #     'instructions': 'Perform task.',
#         #     'expected_output': 'Provide coordinates of the locations.',
#         #     'required_context': [item['task_name'] for item in task_list['task_list'][:-1]]
#         # }

#         # task_list['task_list'].insert(len(task_list['task_list'])-1, map_task)

#         tasks = task_list['task_list']
#         last_task = tasks[-1]
#         if last_task.get('agent_name') != 'Response Generator Agent':
#             previous_task_names = [task['task_name'] for task in tasks]
#             next_task_number = len(tasks) + 1
#             new_task_name = f'task_{next_task_number}'

#             response_generator_task = {
#                 'task_name': new_task_name,
#                 'agent_name': 'Response Generator Agent',
#                 'agent_task': 'Synthesize the analyzed information into a concise, coherent summary that captures the essence of the documents while maintaining clarity and relevance. Conclude and prepare the final summary output, ensuring it is well-structured, highlights key points, and addresses any nuances or complexities found in the documents.',
#                 'instructions': 'Using the detailed analysis reports from all previous agent tasks, synthesize the information into a clear, concise, and coherent summary that captures the essence of the documents. Ensure the summary is well-structured, highlights key points, and addresses any nuances or complexities found in the documents. Provide the final summary in English.',
#                 'expected_output': 'A well-structured, concise, and coherent summary capturing the key points, main ideas, and any nuances or complexities from all analyzed documents. The summary should be in English.',
#                 'required_context': previous_task_names
#             }
#             task_list['task_list'].append(response_generator_task)

#         return {
#             "task_list": task_list['task_list'],
#             "messages": [human_message, response],
#         }
