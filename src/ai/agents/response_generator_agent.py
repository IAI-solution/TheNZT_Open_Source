from .base_agent import BaseAgent
from src.ai.agent_prompts.response_generator_agent import SYSTEM_PROMPT
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from .utils import get_context_messages_for_response
from src.ai.llm.model import get_llm, get_llm_alt
#from src.ai.llm.config import ReportGenerationConfig
from src.ai.llm.config import  ReportGenerationConfig
from src.ai.tools.graph_gen_tool import graph_tool_list
from langgraph.prebuilt import create_react_agent
from datetime import date
from time import sleep


rgc = ReportGenerationConfig()


class ReportGenerationAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.model = get_llm(rgc.MODEL, rgc.TEMPERATURE, rgc.MAX_TOKENS)
        self.model_alt = get_llm_alt(rgc.ALT_MODEL, rgc.ALT_TEMPERATURE, rgc.ALT_MAX_TOKENS)
        self.tools = graph_tool_list
        self.system_prompt = SYSTEM_PROMPT
        self.invoke_delay = 10.0

    def format_input_prompt(self, state: Dict[str, Any]) -> str:
        # print("--- From inside format_input_prompt of ReportGenerationAgent ---") #
        # print(f"\n state inside report generation agent = {state}\n") #

        task = state['current_task']
        user_query = state.get('formatted_user_query', state['user_query'])
        user_query = user_query + " **Include relevant financial graphs by passing tables to the tool `graph_generation_tool` and include them properly as mentioned in Chart Generation and Visualization Guidelines. Ensure stock price charts are never included in the final response. Provide a detailed, well-structured descriptive report with clear headings, subheadings, and a professional format, covering all relevant financial insights.**"

        # input_prompt = f"### Latest User Query: {state['user_query']}\n"
        input_prompt = f"### Latest User Query: {user_query}\n\n"

        input_prompt += f"### Task: {task['agent_task']}\n"
        input_prompt += f"### Instructions: {task['instructions']}\n"
        input_prompt += f"### Expected_output: {task['expected_output']}\n"
        input_prompt += f"\n{state['user_metadata']}\n"
        input_prompt += f"### {state['currency_rates']}\n"
        input_prompt += f"\nToday's date: {date.today()}\n"

        if task.get('required_context') and state.get('task_list'):
            context_messages = get_context_messages_for_response(task['required_context'], state['task_list'])
            input_prompt += f"- Use the following information as **Context** to answer the User Query: {context_messages}\n---\n\n"
        
        if state.get('previous_messages'):
            input_prompt += f"The Latest User Query may be based on the previous queries and their responses.\n"
            msg_hist = "\n".join([f"Query: {msg[0]}\nResponse: ```{msg[1]}```\n" for msg in state['previous_messages']])
            input_prompt += f"**Q&A Context**:\n\nHere is the list of messages from oldest to latest:\n{msg_hist}\n--- END of Q&A Context---\n\n"

        if state.get('initial_info'):
            input_prompt += f"- You can also use this data retrieved from Internal Database as context:\n{state['initial_info']}"

        print(f"\n input_prompt of report generation agent= {input_prompt} \n") #

        return input_prompt

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        task = state['current_task'].copy()
        # print("--- Start of ReportGenerationAgent ---") #
        # print(f"\n state inside ReportGenerationAgent = {state}\n") #

        input_prompt = self.format_input_prompt(state)
        system_message = SystemMessage(content=self.system_prompt)
        human_message = HumanMessage(content=input_prompt)

        input = {"messages": [human_message]}
        
        sleep(self.invoke_delay)

        try:
            # response = self.model.invoke(input=[system_message, human_message])
            agent = create_react_agent(model=self.model, tools=self.tools, prompt=system_message)            
            response = agent.invoke(input)
            print(f"response of report generation agent = {response}.") 

        except Exception as e:
            print(f"Falling back to alternate model: {str(e)}")
            sleep(self.invoke_delay)
            try:
                agent = create_react_agent(
                    model=self.model_alt, tools=self.tools, prompt=system_message)
                response = agent.invoke(input)
            except Exception as e:
                print(f"Error occurred in fallback model: {str(e)}")
                raise e

        # final_response = response.content.strip()
        # Safely extract final response from the last message
        messages = response.get("messages", [])
        if messages and hasattr(messages[-1], "content"):
            final_response = messages[-1].content.strip()
        else:
            final_response = ""  # Or handle error

        # print(f"final_response of report generation agent = {final_response}.") #

        # 1. Convert HumanMessage/SystemMessage to dicts if needed
        def msg_to_dict(msg):
            # If it's a dict, don't touch it—preserve all keys (esp. tool_call_id)
            if isinstance(msg, dict):
                return msg
            # If it's a LangChain Message object, use .dict() if available, else .__dict__
            if hasattr(msg, "dict"):
                return msg.dict()
            if hasattr(msg, "__dict__"):
                return msg.__dict__
            # fallback
            return {"role": "unknown", "content": str(msg)}

        
        # 2. Gather all messages
        all_messages = []
        all_messages.append(msg_to_dict(human_message))
        # Add agent messages (flatten if needed)
        if isinstance(response, dict) and "messages" in response:
            for m in response["messages"]:
                all_messages.append(msg_to_dict(m))
        else:
            all_messages.append(msg_to_dict(response))

        # print(f"all_messages = {all_messages}.")

        # print("--- End of ReportGenerationAgent ---") #
        
        current_progress = state.get("progress_bar", 0.0)
        progress = 100.0  # Assuming the report generation is the final step, set progress to 100%
     
        print(f"===Progress in Response Generator Agent: {progress}===")
        
        return {
            "messages": all_messages,
            "final_response": final_response,
            "progress_bar": progress
        }
