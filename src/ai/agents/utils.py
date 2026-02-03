from typing import List, Dict, Any, Literal
from langgraph.types import Command
from langgraph.graph import END
from langchain_core.messages import AIMessage, ToolMessage
from src.ai.llm.model import get_llm, get_llm_alt
from src.ai.ai_schemas.structured_responses import RelatedQueries
import json
import re
from dotenv import load_dotenv
#from src.ai.llm.config import GenerateSessionTitleConfig, GetRelatedQueriesConfig
from src.ai.llm.config import  GenerateSessionTitleConfig, GetRelatedQueriesConfig

load_dotenv()


gstc = GenerateSessionTitleConfig()
grqc = GetRelatedQueriesConfig()

def get_context_messages(required_context: List[str], task_list: List[Dict[str, Any]]) -> List:
    context_messages = []
    required_tool_names = [
        'get_webpage_info', 'get_reddit_post_text_tool', 'db_search_tool', 'code_execution_tool']

    if required_context:
        for task_name in required_context:
            for subtask in task_list:
                if subtask['task_name'] == task_name:
                    for msg in subtask['task_messages']:
                        # if isinstance(msg, ToolMessage):
                        #     if msg.name in required_tool_names:
                        #         msg = AIMessage(content=msg.content)
                        #         context_messages.append(msg)
                        if isinstance(msg, AIMessage):
                            if msg.content and (not msg.tool_calls):
                                context_messages.append(msg)

    return context_messages


def get_context_messages_for_response(required_context: List[str], task_list: List[Dict[str, Any]]) -> List:
    context_messages = []
    required_tool_names = ['get_webpage_info', 'get_reddit_post_text_tool', 'db_search_tool']
    if required_context:
        for task_name in required_context:
            for subtask in task_list:
                if subtask['task_name'] == task_name:
                    if subtask.get('task_messages'):
                        for msg in subtask['task_messages']:
                            if subtask['agent_name'] == 'Coding Agent':
                                if isinstance(msg, ToolMessage):
                                    context_messages.append(
                                        "Response from generated code:\n\n" + msg.content)
                                if isinstance(msg, AIMessage):
                                    if msg.content and (not msg.tool_calls):
                                        context_messages.append(msg.content)
                                    elif msg.tool_calls:
                                        tool_msg = "Generated code:\n"
                                        for tool_call in msg.tool_calls:
                                            tool_msg += f"{tool_call['args']}\n"
                                        context_messages.append(tool_msg)
                            else:
                                # if isinstance(msg, ToolMessage):
                                #     if msg.name in required_tool_names:
                                #         context_messages.append(msg.content)
                                if isinstance(msg, AIMessage):
                                    if msg.content and (not msg.tool_calls):
                                        context_messages.append(msg.content)

    return "\n\n---\n\n".join(context_messages)


# def task_router_node(state: Dict[str, Any]) -> Command[Literal["Web Search Agent", "Social Media Scrape Agent", "Finance Data Agent",
#                                                                "Sentiment Analysis Agent", "Data Comparison Agent", "Coding Agent",
#                                                                "Response Generator Agent", "__end__"]]:
#     task_list = state['task_list'].copy()
#     current_task = state.get('current_task')
#     MAX_RETRIES = 2

#     # if current_task:
#     #     # Validate the current task using the new validation agent
#     #     validation_output = task_validation(state)

#     #     is_valid = validation_output.get("is_valid", "Incorrect Response")
#     #     feedback = validation_output.get("feedback", "")

#     #     # Initialize retry counter if not present.
#     #     if "retry" not in current_task:
#     #         current_task["retry"] = 0

#     #     if is_valid == "Incorrect Response":
#     #         # Store feedback and increment retry count.
#     #         current_task["task_feedback"] = feedback
#     #         current_task["retry"] += 1

#     #         if current_task["retry"] < MAX_RETRIES:
#     #             return Command(
#     #                 goto=current_task["agent_name"],
#     #                 update={
#     #                     "current_task": current_task,
#     #                     "task_list": task_list,
#     #                 }
#     #             )

#     # If no current task or validation passed, select the next task
#     if current_task is None:
#         next_task = task_list[0]
#     else:
#         # Find the index of the current task
#         current_task_index = next((index for index, task in enumerate(task_list) if task['task_name'] == current_task['task_name']), -1)
#         task_list[current_task_index] = current_task
#         # if current_task['task_name'] in state['research_plan']:
#         #     task_id = current_task['task_name']
#         #     current_plan = state['research_plan'].get('task_id')
#         #     if current_plan:
#         #         current_plan['complete'] = True
#         #         print(f"\n{current_plan}\n")


#         if current_task_index == len(task_list) - 1:
#             return Command(
#                 goto=END,
#                 update={
#                     'task_list': task_list
#                 }
#             )

#         next_task = task_list[current_task_index + 1]

#     target_agent = next_task['agent_name']
#     # if next_task['task_name'] in state['research_plan']:
#     #     task_id = next_task['task_name']
#     #     current_plan = state['research_plan'].get('task_id')
#     #     if current_plan:
#     #         current_plan['agent'] = target_agent


#     return Command(
#         goto=target_agent,
#         update={
#             'current_task': next_task,
#             'task_list': task_list
#         }
#     )


def task_router_node(state: Dict[str, Any]) -> Command[Literal["Web Search Agent", "Social Media Scrape Agent", "Finance Data Agent",
                                                               "Sentiment Analysis Agent", "Data Comparison Agent", "Coding Agent",
                                                               "Response Generator Agent", "__end__"]]:
    task_list = state['task_list'].copy()
    current_task = state.get('current_task')
    TOTAL_PROGRESS = 70.0

    if current_task is None:
        # First task
        next_task = task_list[0]
        
        num_tasks = len(task_list) - 1
        progress_per_task = TOTAL_PROGRESS / num_tasks if num_tasks > 0 else 0.0
        
        new_progress = state.get("progress_bar", 0.0)  # no increment here
        # print("====Inside Executor agent (initial task)====")
        # print(f"===Progress in Executor Agent: {new_progress}===")
        # print(f"===Progress in Executor Agent: {new_progress+10}===")
    else:
        # Continuing task list
        current_task_index = next((index for index, task in enumerate(task_list) if task['task_name'] == current_task['task_name']), -1)
        task_list[current_task_index] = current_task

        num_tasks = len(task_list) - 1
        progress_per_task = TOTAL_PROGRESS / num_tasks if num_tasks > 0 else 0.0
        
        print(f"\n====Progress per task: {progress_per_task}====\n")
        current_progress = state.get("progress_bar", 0.0)
        new_progress = min(current_progress + progress_per_task, 100.0)

        print("====Inside Executor agent====")
        print(f"===Progress in Executor Agent: {new_progress}===")

        if current_task_index == len(task_list) - 1:
            return Command(
                goto=END,
                update={
                    'task_list': task_list,
                    'progress_bar': new_progress
                }
            )

        next_task = task_list[current_task_index + 1]

    target_agent = next_task['agent_name']

    return Command(
        goto=target_agent,
        update={
            'current_task': next_task,
            'task_list': task_list,
            'progress_bar': new_progress
        }
    )


def get_context_based_answer_prompt(context: str, query: str) -> str:
    prompt = (
        f"You are a helpful assistant. Your task is to answer the `User Query` based only on the given `Context`.\n",
        f"---\n",
        f"### Context:\n{context}\n",
        f"---\n",
        f"### User Query:\n{query}\n"
    )

    return "\n".join(prompt)


def detect_query_language(text: str) -> str:
    """
    Detect if text is primarily English or Hindi based on character analysis.
    Returns 'english' or 'hindi'.
    """
    if not text:
        return 'english'

    # Count Devanagari characters (Hindi script range: U+0900 to U+097F)
    devanagari_count = sum(1 for char in text if '\u0900' <= char <= '\u097F')
    # Count ASCII letters
    ascii_count = sum(1 for char in text if char.isascii() and char.isalpha())

    # If more than 10% of alphabetic characters are Devanagari, consider it Hindi
    total_alpha = devanagari_count + ascii_count
    if total_alpha > 0 and (devanagari_count / total_alpha) > 0.1:
        return 'hindi'
    return 'english'


def get_related_queries_util(previous_messages: dict) -> List[str]:
    # input = "The following are the user queries from previous interactions from oldest to latest:\n"
    input = """
    You are given a list of user search queries and corresponding AI responses from a past interaction, ordered from oldest to latest. Your task is to generate four related search queries that a user might ask next or that are semantically similar to the original queries, taking into account both the user query and the AI response. All generated queries must focus on financial or economic aspects related to the topic of the original query and response. The queries should be concise, relevant, and designed to explore financial implications, economic impacts, or business-related angles.
    """

    print(f"previous_messages = {previous_messages['messages']}")

    # Extract user query for language detection
    user_query_text = ""
    for msg in previous_messages['messages'][-1:]:
        user_query_text = msg[0]
        input += f" User Query: {msg[0]}\n"
        input += f" AI Answer: {msg[1]}\n"

    # Detect language of user query
    detected_language = detect_query_language(user_query_text)

    print("From get_related_queries_util")
    print(f"Detected language: {detected_language} (from query: {user_query_text[:50]}...)" if len(user_query_text) > 50 else f"Detected language: {detected_language} (from query: {user_query_text})")
    print(f"input = {input}")
        
    input += '''### Guidelines to generate the related queries:
                1. **All generating or reformulating queries from user input, ensure all follow-up queries remain in the business or financial domain and are semantically aligned with the original user intent.**
                2. Use a mix of query types:
                    - Question-based (e.g., “How to…”, “Why does…”, “What are…”)
                    - Keyword/phrase-based 
                    - Exploratory or comparative (e.g., “alternatives to X”, “X vs Y”)
                3. Use **natural, conversational, or web-search-like phrasing**.
                4. Keep the output concise, readable, and non-redundant.
                5. The queries should be diverse but **not stray outside the core theme** of the input queries.
                6. **For example:**
                   - Query: "which android mobile is best for me"
                      - Related financial queries:
                          - What are the top-selling Android smartphones in 2025 based on revenue?
                          - Which Android brands show strong stock performance this year?
                          - What is the financial outlook of Samsung vs Xiaomi?
                          - Which smartphone brand offers the best investment potential?


                ### Output format:
                Return the related queries in a JSON object as specified by the schema below.
                Do not include any text outside the JSON object.
            '''

    # input += '''### Guidelines to generate the related queries:
    #             1. All generated queries must be semantically related to the user’s intent or topic.
    #             2. Use a mix of query types:
    #                 - Question-based (e.g., “How to…”, “Why does…”, “What are…”)
    #                 - Keyword/phrase-based 
    #                 - Exploratory or comparative (e.g., “alternatives to X”, “X vs Y”)
    #             3. Use **natural, conversational, or web-search-like phrasing**.
    #             4. Keep the output concise, readable, and non-redundant.
    #             5. The queries should be diverse but **not stray outside the core theme** of the input queries.

    #             ### Output format:
    #             Return **exactly 4** related queries, formatted as a list with each query on a new line. 
    #             Do not explain or add extra commentary.
    #         '''

    # Add explicit language instruction at the END (more effective position)
    if detected_language == 'english':
        language_instruction = """

    **CRITICAL LANGUAGE REQUIREMENT**: The User Query is in ENGLISH. You MUST generate ALL 4 related queries in ENGLISH ONLY.
    Do NOT use Hindi, Devanagari script, or any other language. Every single query must be written entirely in English.
    """
    else:
        language_instruction = """

    **CRITICAL LANGUAGE REQUIREMENT**: The User Query is in HINDI. You MUST generate ALL 4 related queries in HINDI ONLY.
    Use Devanagari script. Every single query must be written entirely in Hindi.
    """
    input += language_instruction

    # Append schema instruction to input
    schema_instruction = f"\n\nYou must return the output as a valid JSON object matching this schema:\n{json.dumps(RelatedQueries.model_json_schema(), indent=2)}\n\nDo not include any text outside the JSON object."
    input += schema_instruction

    try:
        # model = get_llm(model_name="gemini/gemini-2.5-pro", temperature=0.2)
        model = get_llm(model_name=grqc.MODEL, temperature=grqc.TEMPERATURE, agent_name="RelatedQueriesAgent")
        # Remove response_format
        response = model.invoke(input=input)

    except Exception as e:
        print(f"Falling back to alternate model: {str(e)}")
        try:
            # model = get_llm_alt("gemini/gemini-2.0-flash-lite", 0.6)
            model = get_llm_alt(model_name=grqc.ALT_MODEL, temperature=grqc.ALT_TEMPERATURE, agent_name="RelatedQueriesAgent")
            # Remove response_format
            response = model.invoke(input=input)
        except Exception as e:
            print(f"Error occurred in fallback model: {str(e)}")
            raise e

    if response.content:
        # Manual JSON extraction
        response_content = response.content
        # Remove thinking section if present
        response_without_thinking = re.sub(r'<think>.*?</think>', '', response_content, flags=re.DOTALL)
        
        # Extract JSON content from markdown blocks if present
        json_match = re.search(r'```json\s*(.*?)\s*```', response_without_thinking, re.DOTALL)
        if json_match:
            json_content = json_match.group(1).strip()
        else:
            # Try to find the first { and last }
            start = response_without_thinking.find('{')
            end = response_without_thinking.rfind('}')
            if start != -1 and end != -1:
                json_content = response_without_thinking[start:end+1]
            else:
                json_content = response_without_thinking

        try:
            related_queries = json.loads(json_content)['related_queries']
            return related_queries
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print("Raw content:", response_content)
            # Return empty list on failure to avoid crashing
            return []
            
    return []


async def generate_session_title(content: str) -> str:
    print(f"\n\n----\nGenerating session title for content: {content}\n\n")
    input = f"""<Role>
You are a Conversation Title Generator Assistant. 
You are provided with context of a chat conversation, which may include greetings, questions and their responses.
Your task is to give a concise and short title to the conversation by following the `Instructions`.
</Role>

<Instructions>
1. If all the User Queries in the Conversation are greetings and the count is less than five then strictly repond with "New Chat" as the title.
2. If count of User Query only containing greetings is more than five then response with title appropriately reflecting the continuous greetings.
3. If the conversation is about a specific context or question other than greetings, generate a title that reflects the main topic discussed in the chat.
4. If the conversation starts with a greeting and then transition to a specific topic, generate a title that reflects the main topic discussed in the chat.
5. If a user query has spelling or formatting mistakes but the assistant still understood and responded meaningfully, generate a title based on the understood topic.
6. Keep the title length short and concise, i.e., 4-5 words, and avoid using special characters.
Example Response Titles: "Latest Tech Trends", "Healthy Eating Tips", "Traveling to Japan", "Python Programming Basics", "Water Conservation Essay", "Google Password Leak Alert".
7. If the conversation does not have any User Query or is empty, respond with "New Chat".
</Instructions>

<Conversation Context>
{content}
</Conversation Context>
"""
    try:
        # model = get_llm(model_name = "gemini/gemini-2.5-pro", temperature = 0.4)
        model = get_llm(model_name=gstc.MODEL, temperature=gstc.TEMPERATURE, agent_name="SessionTitleAgent")
        response = await model.ainvoke(input=input)
        
    except Exception as e:
        print(f"Falling back to alternate model: {str(e)}")
        try:
            # model = get_llm_alt("gemini/gemini-2.0-flash-lite", 0.4)
            model = get_llm_alt(model_name=gstc.ALT_MODEL, temperature=gstc.ALT_TEMPERATURE, agent_name="SessionTitleAgent")
            response = await model.ainvoke(input=input)
        except Exception as e:
            print(f"Error occurred in fallback model: {str(e)}")
            raise e
    print(f"\n\n----\nGenerated session title: {response.content.strip()}")
    return response.content.strip() if response.content else "New Chat"




# from typing import List, Dict, Any, Literal
# from langgraph.types import Command
# from langgraph.graph import END
# from langchain_core.messages import AIMessage, ToolMessage
# from src.ai.llm.model import get_llm, get_llm_alt
# from src.ai.ai_schemas.structured_responses import RelatedQueries
# import json
# from dotenv import load_dotenv
# # #from src.ai.llm.config import GenerateSessionTitleConfig, GetRelatedQueriesConfig
from src.ai.llm.config import  GenerateSessionTitleConfig, GetRelatedQueriesConfig

# load_dotenv()


# gstc = GenerateSessionTitleConfig()
# grqc = GetRelatedQueriesConfig()

# def get_context_messages(required_context: List[str], task_list: List[Dict[str, Any]]) -> List:
#     context_messages = []
#     required_tool_names = [
#         'get_webpage_info', 'get_reddit_post_text_tool', 'db_search_tool', 'code_execution_tool']

#     if required_context:
#         for task_name in required_context:
#             for subtask in task_list:
#                 if subtask['task_name'] == task_name:
#                     for msg in subtask['task_messages']:
#                         # if isinstance(msg, ToolMessage):
#                         #     if msg.name in required_tool_names:
#                         #         msg = AIMessage(content=msg.content)
#                         #         context_messages.append(msg)
#                         if isinstance(msg, AIMessage):
#                             if msg.content and (not msg.tool_calls):
#                                 context_messages.append(msg)

#     return context_messages


# def get_context_messages_for_response(required_context: List[str], task_list: List[Dict[str, Any]]) -> List:
#     context_messages = []
#     required_tool_names = ['get_webpage_info', 'get_reddit_post_text_tool', 'db_search_tool']
#     if required_context:
#         for task_name in required_context:
#             for subtask in task_list:
#                 if subtask['task_name'] == task_name:
#                     if subtask.get('task_messages'):
#                         for msg in subtask['task_messages']:
#                             if subtask['agent_name'] == 'Coding Agent':
#                                 if isinstance(msg, ToolMessage):
#                                     context_messages.append(
#                                         "Response from generated code:\n\n" + msg.content)
#                                 if isinstance(msg, AIMessage):
#                                     if msg.content and (not msg.tool_calls):
#                                         context_messages.append(msg.content)
#                                     elif msg.tool_calls:
#                                         tool_msg = "Generated code:\n"
#                                         for tool_call in msg.tool_calls:
#                                             tool_msg += f"{tool_call['args']}\n"
#                                         context_messages.append(tool_msg)
#                             else:
#                                 # if isinstance(msg, ToolMessage):
#                                 #     if msg.name in required_tool_names:
#                                 #         context_messages.append(msg.content)
#                                 if isinstance(msg, AIMessage):
#                                     if msg.content and (not msg.tool_calls):
#                                         context_messages.append(msg.content)

#     return "\n\n---\n\n".join(context_messages)


# # def task_router_node(state: Dict[str, Any]) -> Command[Literal["Web Search Agent", "Social Media Scrape Agent", "Finance Data Agent",
# #                                                                "Sentiment Analysis Agent", "Data Comparison Agent", "Coding Agent",
# #                                                                "Response Generator Agent", "__end__"]]:
# #     task_list = state['task_list'].copy()
# #     current_task = state.get('current_task')
# #     MAX_RETRIES = 2

# #     # if current_task:
# #     #     # Validate the current task using the new validation agent
# #     #     validation_output = task_validation(state)

# #     #     is_valid = validation_output.get("is_valid", "Incorrect Response")
# #     #     feedback = validation_output.get("feedback", "")

# #     #     # Initialize retry counter if not present.
# #     #     if "retry" not in current_task:
# #     #         current_task["retry"] = 0

# #     #     if is_valid == "Incorrect Response":
# #     #         # Store feedback and increment retry count.
# #     #         current_task["task_feedback"] = feedback
# #     #         current_task["retry"] += 1

# #     #         if current_task["retry"] < MAX_RETRIES:
# #     #             return Command(
# #     #                 goto=current_task["agent_name"],
# #     #                 update={
# #     #                     "current_task": current_task,
# #     #                     "task_list": task_list,
# #     #                 }
# #     #             )

# #     # If no current task or validation passed, select the next task
# #     if current_task is None:
# #         next_task = task_list[0]
# #     else:
# #         # Find the index of the current task
# #         current_task_index = next((index for index, task in enumerate(task_list) if task['task_name'] == current_task['task_name']), -1)
# #         task_list[current_task_index] = current_task
# #         # if current_task['task_name'] in state['research_plan']:
# #         #     task_id = current_task['task_name']
# #         #     current_plan = state['research_plan'].get('task_id')
# #         #     if current_plan:
# #         #         current_plan['complete'] = True
# #         #         print(f"\n{current_plan}\n")


# #         if current_task_index == len(task_list) - 1:
# #             return Command(
# #                 goto=END,
# #                 update={
# #                     'task_list': task_list
# #                 }
# #             )

# #         next_task = task_list[current_task_index + 1]

# #     target_agent = next_task['agent_name']
# #     # if next_task['task_name'] in state['research_plan']:
# #     #     task_id = next_task['task_name']
# #     #     current_plan = state['research_plan'].get('task_id')
# #     #     if current_plan:
# #     #         current_plan['agent'] = target_agent


# #     return Command(
# #         goto=target_agent,
# #         update={
# #             'current_task': next_task,
# #             'task_list': task_list
# #         }
# #     )


# def task_router_node(state: Dict[str, Any]) -> Command[Literal["Web Search Agent", "Social Media Scrape Agent", "Finance Data Agent",
#                                                                "Sentiment Analysis Agent", "Data Comparison Agent", "Coding Agent",
#                                                                "Response Generator Agent", "__end__"]]:
#     task_list = state['task_list'].copy()
#     current_task = state.get('current_task')
#     TOTAL_PROGRESS = 70.0

#     if current_task is None:
#         # First task
#         next_task = task_list[0]
        
#         num_tasks = len(task_list) - 1
#         progress_per_task = TOTAL_PROGRESS / num_tasks if num_tasks > 0 else 0.0
        
#         new_progress = state.get("progress_bar", 0.0)  # no increment here
#         # print("====Inside Executor agent (initial task)====")
#         # print(f"===Progress in Executor Agent: {new_progress}===")
#         # print(f"===Progress in Executor Agent: {new_progress+10}===")
#     else:
#         # Continuing task list
#         current_task_index = next((index for index, task in enumerate(task_list) if task['task_name'] == current_task['task_name']), -1)
#         task_list[current_task_index] = current_task

#         num_tasks = len(task_list) - 1
#         progress_per_task = TOTAL_PROGRESS / num_tasks if num_tasks > 0 else 0.0
        
#         print(f"\n====Progress per task: {progress_per_task}====\n")
#         current_progress = state.get("progress_bar", 0.0)
#         new_progress = min(current_progress + progress_per_task, 100.0)

#         print("====Inside Executor agent====")
#         print(f"===Progress in Executor Agent: {new_progress}===")

#         if current_task_index == len(task_list) - 1:
#             return Command(
#                 goto=END,
#                 update={
#                     'task_list': task_list,
#                     'progress_bar': new_progress
#                 }
#             )

#         next_task = task_list[current_task_index + 1]

#     target_agent = next_task['agent_name']

#     return Command(
#         goto=target_agent,
#         update={
#             'current_task': next_task,
#             'task_list': task_list,
#             'progress_bar': new_progress
#         }
#     )


# def get_context_based_answer_prompt(context: str, query: str) -> str:
#     prompt = (
#         f"You are a helpful assistant. Your task is to answer the `User Query` based only on the given `Context`.\n",
#         f"---\n",
#         f"### Context:\n{context}\n",
#         f"---\n",
#         f"### User Query:\n{query}\n"
#     )

#     return "\n".join(prompt)


# def get_related_queries_util(previous_messages: dict) -> List[str]:
#     # input = "The following are the user queries from previous interactions from oldest to latest:\n"
#     input = """
#     You are given a list of user search queries and corresponding AI responses from a past interaction, ordered from oldest to latest. Your task is to generate four related search queries that a user might ask next or that are semantically similar to the original queries, taking into account both the user query and the AI response. All generated queries must focus on financial or economic aspects related to the topic of the original query and response. The queries should be concise, relevant, and designed to explore financial implications, economic impacts, or business-related angles. Generate the queries same language as the response generasted by the AI.
#     """

#     print(f"previous_messages = {previous_messages['messages']}")
#     for msg in previous_messages['messages'][-1:]:
#         input += f" User Query: {msg[0]}\n"
#         input += f" AI Answer: {msg[1]}\n"
    
#     print("From get_related_queries_util")
#     print(f"input = {input}")
        
#     input += '''### Guidelines to generate the related queries:
#                 1. **All generating or reformulating queries from user input, ensure all follow-up queries remain in the business or financial domain and are semantically aligned with the original user intent.**
#                 2. Use a mix of query types:
#                     - Question-based (e.g., “How to…”, “Why does…”, “What are…”)
#                     - Keyword/phrase-based 
#                     - Exploratory or comparative (e.g., “alternatives to X”, “X vs Y”)
#                 3. Use **natural, conversational, or web-search-like phrasing**.
#                 4. Keep the output concise, readable, and non-redundant.
#                 5. The queries should be diverse but **not stray outside the core theme** of the input queries.
#                 6. **For example:**
#                    - Query: "which android mobile is best for me"
#                       - Related financial queries:
#                           - What are the top-selling Android smartphones in 2025 based on revenue?
#                           - Which Android brands show strong stock performance this year?
#                           - What is the financial outlook of Samsung vs Xiaomi?
#                           - Which smartphone brand offers the best investment potential?


#                 ### Output format:
#                 Return **exactly 4** related queries, formatted as a list with each query on a new line. 
#                 Do not explain or add extra commentary.
#             '''

#     # input += '''### Guidelines to generate the related queries:
#     #             1. All generated queries must be semantically related to the user’s intent or topic.
#     #             2. Use a mix of query types:
#     #                 - Question-based (e.g., “How to…”, “Why does…”, “What are…”)
#     #                 - Keyword/phrase-based 
#     #                 - Exploratory or comparative (e.g., “alternatives to X”, “X vs Y”)
#     #             3. Use **natural, conversational, or web-search-like phrasing**.
#     #             4. Keep the output concise, readable, and non-redundant.
#     #             5. The queries should be diverse but **not stray outside the core theme** of the input queries.

#     #             ### Output format:
#     #             Return **exactly 4** related queries, formatted as a list with each query on a new line. 
#     #             Do not explain or add extra commentary.
#     #         '''

#     try:
#         # model = get_llm(model_name="gemini/gemini-2.5-pro", temperature=0.2)
#         model = get_llm(model_name=grqc.MODEL, temperature=grqc.TEMPERATURE)
#         response = model.invoke(input=input, response_format=RelatedQueries)

#     except Exception as e:
#         print(f"Falling back to alternate model: {str(e)}")
#         try:
#             # model = get_llm_alt("gemini/gemini-2.0-flash-lite", 0.6)
#             model = get_llm_alt(model_name=grqc.ALT_MODEL, temperature=grqc.ALT_TEMPERATURE)
#             response = model.invoke(input=input, response_format=RelatedQueries)
#         except Exception as e:
#             print(f"Error occurred in fallback model: {str(e)}")
#             raise e

#     if response.content:
#         related_queries = json.loads(response.content)['related_queries']

#         return related_queries
#     return []


# async def generate_session_title(content: str) -> str:
#     print(f"\n\n----\nGenerating session title for content: {content}\n\n")
#     input = f"""<Role>
# You are a Conversation Title Generator Assistant. 
# You are provided with context of a chat conversation, which may include greetings, questions and their responses.
# Your task is to give a concise and short title to the conversation by following the `Instructions`.
# </Role>

# <Instructions>
# 1. If all the User Queries in the Conversation are greetings and the count is less than five then strictly repond with "New Chat" as the title.
# 2. If count of User Query only containing greetings is more than five then response with title appropriately reflecting the continuous greetings.
# 3. If the conversation is about a specific context or question other than greetings, generate a title that reflects the main topic discussed in the chat.
# 4. If the conversation starts with a greeting and then transition to a specific topic, generate a title that reflects the main topic discussed in the chat.
# 5. If a user query has spelling or formatting mistakes but the assistant still understood and responded meaningfully, generate a title based on the understood topic.
# 6. Keep the title length short and concise, i.e., 4-5 words, and avoid using special characters.
# Example Response Titles: "Latest Tech Trends", "Healthy Eating Tips", "Traveling to Japan", "Python Programming Basics", "Water Conservation Essay", "Google Password Leak Alert".
# 7. If the conversation does not have any User Query or is empty, respond with "New Chat".
# </Instructions>

# <Conversation Context>
# {content}
# </Conversation Context>
# """
#     try:
#         # model = get_llm(model_name = "gemini/gemini-2.5-pro", temperature = 0.4)
#         model = get_llm(model_name=gstc.MODEL, temperature=gstc.TEMPERATURE)
#         response = await model.ainvoke(input=input)
        
#     except Exception as e:
#         print(f"Falling back to alternate model: {str(e)}")
#         try:
#             # model = get_llm_alt("gemini/gemini-2.0-flash-lite", 0.4)
#             model = get_llm_alt(model_name=gstc.ALT_MODEL, temperature=gstc.ALT_TEMPERATURE)
#             response = await model.ainvoke(input=input)
#         except Exception as e:
#             print(f"Error occurred in fallback model: {str(e)}")
#             raise e
#     print(f"\n\n----\nGenerated session title: {response.content.strip()}")
#     return response.content.strip() if response.content else "New Chat"
