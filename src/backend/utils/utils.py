import asyncio
from datetime import datetime, timezone
from io import BytesIO
from langchain_community.document_loaders import PyPDFLoader, PyMuPDFLoader
import pandas as pd
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, AIMessageChunk, BaseMessage
import json
import numpy as np
import re
from typing import List, Dict, Awaitable, Any
import tldextract
import uuid
import os
import src.backend.db.mongodb as mongodb
import threading
import ipinfo
import ipaddress
import logging
from zoneinfo import ZoneInfo
# from azure.storage.blob import ContentSettings, BlobServiceClient
# import plotly.graph_objects as go
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from src.ai.llm.model import get_llm
from src.ai.llm.config import CountUsageMetricsPricingConfig

cmp = CountUsageMetricsPricingConfig()

# load_dotenv(dotenv_path=".env", override=True)
# ipinfo_api_key = os.environ.get("IPINFO_API_KEY")
# CONNECTION_STRING = os.getenv("AZURE_CONNECTION_STRING")
# CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME")

# blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
# container_client = blob_service_client.get_container_client(CONTAINER_NAME)


# PRICING = {
#     "azure/gpt-4.1-mini": {
#         "input": 0.40 / 1_000_000,
#         "output": 1.60 / 1_000_000
#     },
#     "azure/gpt-4.1-nano": {
#         "input": 0.100 / 1_000_000,
#         "output": 0.400 / 1_000_000
#     },
#     "azure/gpt-4o-mini": {
#         "input": 0.15 / 1_000_000,
#         "output": 0.60 / 1_000_000
#     }
# }

PRICING = {
    cmp.MODEL: {
        "input": 0.40 / 1_000_000,
        "output": 1.60 / 1_000_000
    },
    cmp.MODEL: {
        "input": 0.100 / 1_000_000,
        "output": 0.400 / 1_000_000
    },
    cmp.MODEL: {
        "input": 0.15 / 1_000_000,
        "output": 0.60 / 1_000_000
    }
}


def is_private_ip(ip: str) -> bool:
    """Check if an IP address is private"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except:
        return False
    

# def get_ip_info(ip_address: str):
#     try:
#         handler = ipinfo.getHandler(access_token= ipinfo_api_key) 
#         details = handler.getDetails(ip_address)

#         is_private = is_private_ip(ip_address)

#         if is_private:
#             return {}

#         location_data = {
#             "city": details.get('city'),
#             "region": details.get('region'),
#             "country": details.get('country') 
#         }
#         return location_data
#     except Exception as e:
#         print(f"Error in getting location from ip: {str(e)}")
#         return {}


def get_user_metadata(timezone: str, ip_address: str = None):
    date_time = get_date_time(timezone)

    location_data = {"location": timezone}

    location_data_str = json.dumps(location_data)
    return f"<UserMetaData>\n- User's current Datetime:{date_time.isoformat()}\n - User's current location details: {location_data_str}\n</UserMetaData>"


def get_date_time(timezone: str = "UTC"):
  
    return datetime.now(ZoneInfo(timezone))


def pretty_format(obj, indent=0):
    """
    Recursively convert an object into a human-readable string with proper indentation.
    - For lists, it will join the recursively converted elements with newlines and proper indentation.
    - For dictionaries, it will produce indented lines of the form "key: value".
    - For any other type, it converts to a string.

    Args:
        obj: The object to format
        indent: The current indentation level (default: 0)

    Returns:
        A formatted string representation of the object
    """
    # Calculate the indentation string
    if obj is None:
        return ""

    # Calculate the indentation string
    indent_str = "  " * indent

    if isinstance(obj, str):
        return obj.strip() if obj.strip() else ""

    elif isinstance(obj, (list, tuple, set)):
        # Filter out None, empty strings, and empty collections
        non_empty_items = [
            item for item in obj 
            if item is not None 
            and (isinstance(item, str) and item.strip() != "" 
                 or not isinstance(item, str) and item)
        ]

        if not non_empty_items:
            return ""

        if len(non_empty_items) == 1:
            formatted = pretty_format(non_empty_items[0], indent)
            return formatted if formatted else ""

        formatted_items = [
            item for item in (pretty_format(item, indent + 1) for item in non_empty_items)
            if item
        ]
        
        if not formatted_items:
            return ""

        md = ""
        for item in formatted_items:
            md += f'{indent_str}- {item}\n'
        return md.strip()

    elif isinstance(obj, dict):
        if not obj:  # Handle empty dict
            return ""

        lines = []
        for key, value in obj.items():
            if key is None or (isinstance(key, str) and not key.strip()):
                continue

            formatted_value = pretty_format(value, indent + 1)
            if not formatted_value:  # Skip if value is empty/None
                continue

            formatted_key = pretty_format(key, indent)
            
            # Handle multi-line values
            if isinstance(value, str):
                lines.append(f"{indent_str}- {formatted_key}: {formatted_value}")
            else:
                lines.append(f"{indent_str}- {formatted_key}:\n{formatted_value}")

        return "\n".join(lines).strip()

    else:
        return str(obj) if obj is not None else ""


def get_unique_response_id():
    return "run-"+str(uuid.uuid4())


def get_unique_stock_data_id():
    return "stockData-"+str(uuid.uuid4())


def extract_file_content(file_path: str):
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
        return df.head().to_markdown()
    if file_path.endswith(".xlsx"):
        df = pd.read_excel(file_path)
        return df.head().to_markdown()
    if file_path.endswith(".pdf"):
        loader = PyPDFLoader(file_path)
        document = loader.load()
        return document[0].page_content
    if file_path.endswith(".txt"):
        with open(file_path, "r") as f:
            return f.read()
    # if file_path.endswith(".docx"):
    #     loader = DoclingLoader(file_path)
    #     document = loader.load()
    #     return document[0].page_content


def get_second_level_domain(url: str) -> str:
    extracted = tldextract.extract(url)
    if not extracted.subdomain or extracted.subdomain == "www":
        return f"{extracted.domain}.{extracted.suffix}".upper()
    else:
        return f"{extracted.subdomain}.{extracted.domain}.{extracted.suffix}".upper()


def get_favicon_link(url: str) -> str:
    return f"https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url={url}&size=32&type=svg"


def extract_subreddit_name(reddit_post_link: str) -> str:
    match = re.search(r'reddit\.com/r/([^/]+)/', reddit_post_link)
    if match:
        return "r/" + match.group(1)
    else:
        return "r/Subreddit"


def get_tool_call_title(tool_call: Dict):
    tools_list = {
        'search_company_info': 'Searching Information for `{query}`',
        'get_usa_based_company_profile': 'Getting Profile for `{ticker}`',
        'db_search_tool': 'Searching internal database for `{query}`',
    }

    if tool_call['name'] == 'search_company_info':
        return tools_list['search_company_info'].format(query=tool_call['args']['query'])
    elif tool_call['name'] == 'get_usa_based_company_profile':
        return tools_list['get_usa_based_company_profile'].format(ticker=tool_call['args']['symbol'])
    elif tool_call['name'] == 'db_search_tool':
        return tools_list['db_search_tool'].format(query=tool_call['args']['query'])


def get_token_usage_data(msg: AIMessage):
    if msg.get('usage_metadata'):
        return {'model': msg.response_metadata.get('model_name', 'azure/gpt-4.1-mini'), **msg.usage_metadata}


async def format_tool_calling_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                for key, value in update.items():
                    for field, valu in value.items():
                        if field == 'messages':
                            for msg in valu:
                                if isinstance(msg, AIMessage):
                                    # token_metrics = get_token_usage_data(msg)
                                    # response_list.append({'token_usage': token_metrics})
                                    if msg.tool_calls:
                                        tool_msg_list = []
                                        for tool_call in msg.tool_calls:
                                            tool_msg = f"Using function `{tool_call['name']}` with following arguments:\n"
                                            tool_msg += pretty_format(tool_call['args'])
                                            if tool_call['args'].get('explanation'):
                                                title = tool_call['args'].get('explanation')
                                            else:
                                                title = get_tool_call_title(tool_call)
                                            tool_msg_list.append((tool_msg, title))

                                        for tool_msg in tool_msg_list:
                                            response_list.append({'type': 'research', 'agent_name': agent_name, 'content': tool_msg[0], 'title': tool_msg[1], 'id': msg.id})

                                    if msg.content and not msg.tool_calls:
                                        # if not (agent_name == "Map Agent"):
                                        response_list.extend([
                                            {'type': 'research', 'agent_name': agent_name, 'title': f"**{agent_name}** has completed its task.", 'content': msg.content},
                                        ])

                                elif isinstance(msg, ToolMessage):
                                    response_list.append({'agent_name': agent_name, 'title': 'Analyzing result', 'id': msg.id})
            # elif stream_mode == "messages":
            #     msg = update[0]
            #     if isinstance(msg, AIMessageChunk) and msg.content:

        return response_list
    except Exception as e:
        print(f"Error in format_tool_calling_agent_update : {str(e)}")
        response_list.append({'format_error': f"Error in format_tool_calling_agent_update : {str(e)}"})
        return response_list
        # raise RuntimeError(f"Error in format_tool_calling_agent_update : {str(e)}")


async def format_map_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                for key, value in update.items():
                    for field, valu in value.items():
                        if field == 'messages':
                            for msg in valu:
                                if isinstance(msg, AIMessage):
                                    # token_metrics = get_token_usage_data(msg)
                                    # response_list.append({'token_usage': token_metrics})
                                    if msg.tool_calls:
                                        for tool_call in msg.tool_calls:
                                            tool_msg = f"Using function `{tool_call['name']}` with following arguments:\n"
                                            tool_msg += pretty_format(tool_call['args'])
                                            if tool_call['args'].get('explanation'):
                                                title = tool_call['args'].get('explanation')
                                            else:
                                                title = tool_msg
                                            response_list.append({'type': 'research', 'agent_name': agent_name, 'title': title, 'id': msg.id})

                                    # if msg.content and not msg.tool_calls:
                                    #     response_list.extend([
                                    #         {'type': 'research', 'agent_name': agent_name, 'title': f"**{agent_name}** has completed its task.", 'id': msg.id},
                                    #     ])

                                elif isinstance(msg, ToolMessage):
                                    response_list.append({'agent_name': agent_name, 'title': 'Analyzing result', 'id': msg.id})
                        
                        elif field == 'structured_response':
                            pass
                            # response_list.append({'type': 'research', 'agent_name': agent_name, 'title': pretty_format(valu.model_dump()['data']), 'id': get_unique_response_id()})
                            # print(valu.model_dump()['data'])

        return response_list
    except Exception as e:
        print(f"Error in format_map_agent_update : {str(e)}")
        response_list.append({'format_error': f"Error in format_map_agent_update : {str(e)}"})
        return response_list
        # raise RuntimeError(f"Error in format_map_agent_update : {str(e)}")


async def format_map_agent_update_struct_response(agent_name, stream_mode, update):
    """
    Given an 'update' dict, extract all current_task.task_messages contents
    when stream_mode == "updates", and return a list of lists of strings.
    """
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                message_container_key = None
                if agent_name in update:
                    message_container_key = agent_name
                else:
                    return response_list
                
                value = update.get(message_container_key, {})
                
                if value and 'messages' in value and isinstance(value['messages'], list):
                    msg_list = value['messages']
                    # if isinstance(msg_list[-1], AIMessage):
                        # token_metrics = get_token_usage_data(msg_list[-1])
                        # response_list.append({'token_usage': token_metrics})

                if 'current_task' in value:
                    map_data = value.get('current_task').get('task_messages', {})
                    response_list.append({'type': 'map_layers', 'agent_name': agent_name, 'data': map_data, 'id': get_unique_response_id()})

        return response_list

    except Exception as e:
        print(f"Error in format_map_agent_update_struct_response : {str(e)}")
        response_list.append({'format_error': f"Error in format_map_agent_update_struct_response : {str(e)}"})
        return response_list
        # raise RuntimeError(f"Error in format_map_agent_update_struct_response : {str(e)}")

    
async def format_finance_data_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                message_container_key = None
                if 'agent' in update:
                    message_container_key = 'agent'
                elif 'tools' in update:
                    message_container_key = 'tools'
                else:
                    return response_list

                messages_list = update.get(message_container_key, {}).get('messages')

                if not messages_list or not isinstance(messages_list, list) or not messages_list:
                    return response_list

                # msg = messages_list[0]
                for msg in messages_list:
                    if isinstance(msg, AIMessage):
                        # token_metrics = get_token_usage_data(msg)
                        # response_list.append({'token_usage': token_metrics})

                        if msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                if not isinstance(tool_call, dict):
                                    continue # Skip if tool_call is not a dictionary

                                args = tool_call.get('args', {})
                                if not isinstance(args, dict): # Ensure args is a dictionary
                                    # args = {}
                                    continue

                                title = args.get('explanation')
                                if not title:
                                    title = 'Performing tool call'

                                response_list.append({
                                    'type': 'research',
                                    'agent_name': agent_name,
                                    'title': title,
                                    'id': tool_call.get('id') or get_unique_response_id()
                                })
                        elif msg.content:  # AIMessage with content but no tool_calls
                            response_list.append({
                                'type': 'research', # Or a more specific type like 'final_answer'
                                'agent_name': agent_name,
                                'title': f"**{agent_name}** has completed its task.",
                                'content': msg.content,
                                'id': msg.id
                            })

                    elif isinstance(msg, ToolMessage):
                        # Initial entry for tool processing
                        response_list.append({
                            'agent_name': agent_name, # Or consider msg.name for context
                            'title': f'Analyzing result for tool: {msg.name}',
                            'id': msg.id, # ID of the ToolMessage
                        })

                        # Specific handling based on tool name
                        if msg.name == "get_stock_data":
                            data_list_from_tool = []
                            if isinstance(msg.content, str):
                                try:
                                    loaded_content = json.loads(msg.content)
                                    if isinstance(loaded_content, list):
                                        data_list_from_tool = loaded_content
                                    elif isinstance(loaded_content, dict): # If a single item, wrap in list
                                        data_list_from_tool = [loaded_content]
                                except json.JSONDecodeError:
                                    # print(f"Warning: JSON decoding failed for get_stock_data content: {msg.content}")
                                    pass # Or append an error object to response_list
                            elif isinstance(msg.content, list):
                                data_list_from_tool = msg.content

                            for data_item in data_list_from_tool:
                                if isinstance(data_item, dict) and (data_item.get('realtime') is not None and data_item.get('historical') is not None) and (not 'error' in data_item.get('realtime') and not 'error' in data_item.get('historical')):
                                    data_item["chart_session_id"] = get_unique_stock_data_id()
                                    response_list.append({
                                        'type': 'stock_data', 'agent_name': agent_name, 'data': data_item, 'chat_session_id': data_item.get('chart_session_id')
                                    })

            return response_list
    except Exception as e:
        print(f"Error in format_finance_data_agent_update : {str(e)}")
        response_list.append({'format_error': f"Error in format_finance_data_agent_update : {str(e)}"})
        return response_list
        # raise RuntimeError(f"Error in format_finance_data_agent_update: {str(e)}")


async def format_web_search_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                message_container_key = None
                if 'agent' in update:
                    message_container_key = 'agent'
                elif 'tools' in update:
                    message_container_key = 'tools'
                else:
                    return response_list

                messages_list = update.get(message_container_key, {}).get('messages')

                if not messages_list or not isinstance(messages_list, list) or not messages_list:
                    return response_list
                
                for msg in messages_list:
                    if isinstance(msg, AIMessage):
                        # token_metrics = get_token_usage_data(msg)
                        # response_list.append({'token_usage': token_metrics})

                        if msg.tool_calls:
                            tool_title = {
                                'advanced_internet_search': '{explanation}\n\n---\nSearching\n{queries}',
                                'get_webpage_info': '{explanation}\n\n---\nReading\n{webpage}',
                            }
                            for tool_call in msg.tool_calls:
                                if tool_call['name'] == 'advanced_internet_search':
                                    queries = ' '.join(f'`{query}`' for query in tool_call['args']['query'])
                                    title = tool_title['advanced_internet_search'].format(
                                        explanation=tool_call['args']['explanation'], queries=queries)
                                    response_list.append({'type': 'research', 'agent_name': agent_name, 'title': title,
                                                            'searching': tool_call['args']['query'], 'id': tool_call.get('id') or get_unique_response_id()})

                        elif msg.content and not msg.tool_calls:
                            response_list.extend([
                                {'type': 'research', 'agent_name': agent_name,
                                    'title': f"**{agent_name}** has completed its task.", 'content': msg.content, 'id': msg.id},
                            ])

                    elif isinstance(msg, ToolMessage):
                        sources = []
                        if msg.name == 'advanced_internet_search':
                            op = json.loads(msg.content)
                            results = op.get("results", [])
                            if results:
                                update_links = [
                                    f"[{get_second_level_domain(result.get('link', ''))}]({result.get('link', '')})"
                                    for result in results if result.get('link')
                                ]
                                link_data = [result.get('link') for result in results if result.get('link')]
                                if update_links:
                                    response_list.append({
                                        'type': 'research',
                                        'agent_name': agent_name,
                                        'title': (
                                            "I am extracting information from the following relevant webpages.\n\n"
                                            "---\nReading\n" + ' '.join(update_links)
                                        ),
                                        'reading': link_data,
                                        'id': msg.id
                                    })
                        response_list.append({'agent_name': agent_name, 'content': msg.content, 'sources': sources})
            return response_list
    except Exception as e:
        print(f"Error in format_web_search_agent_update : {str(e)}")
        response_list.append({'format_error': f"Error in format_web_search_agent_update : {str(e)}"})
        return response_list
        # raise RuntimeError(f"Error in format_web_search_agent_update : {str(e)}")


async def format_db_search_agent_aimessage(agent_name, stream_mode, update):
    try:
        response_list = []
        
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                message_container_key = None
                if 'agent' in update:
                    message_container_key = 'agent'
                elif 'tools' in update:
                    message_container_key = 'tools'
                else:
                    return response_list

                messages_list = update.get(message_container_key, {}).get('messages')

                if not messages_list or not isinstance(messages_list, list) or not messages_list:
                    return response_list
                
                for msg in messages_list:
                    if isinstance(msg, AIMessage):
                        # token_metrics = get_token_usage_data(msg)
                        # response_list.append({'token_usage': token_metrics})

                        # Handle tool calls if present
                        if msg.tool_calls:
                            tool_title_templates = {
                                # 'execute_query': '{explanation}\n\n---\nExecuting Query\n{query}',
                                'search_audit_documents': '{explanation}\n\n---\nSearching Database {query} from {len} documents',
                                # 'validate_results': '{explanation}\n\n---\nValidating Results\n{validation_criteria}',
                            }
                            
                            for tool_call in msg.tool_calls:
                                tool_name = tool_call.get('name')
                                tool_args = tool_call.get('args', {})
                                tool_id = tool_call.get('id') or get_unique_response_id()
                                if tool_name == 'search_audit_documents':
                                    query = tool_args.get('query', 'Unknown query')
                                    doc_ids = tool_args.get('doc_ids', [])
                                    explanation = tool_args.get('explanation', 'Searching audit documents')
                                    title = tool_title_templates['search_audit_documents'].format(
                                        explanation=explanation, 
                                        query=f'`{query}`',
                                        len = len(doc_ids)
                                    )
                                    response_list.append({
                                        'type': 'research', 
                                        'agent_name': agent_name, 
                                        'title': title,
                                        'searching': query, 
                                        'id': tool_id
                                    })

                                # elif hasattr(msg, 'invalid_tool_calls') and msg.invalid_tool_calls:
                                #     for invalid_call in msg.invalid_tool_calls:
                                #         response_list.append({
                                #             'type': 'database_error', 
                                #             'agent_name': agent_name, 
                                #             'title': f"Invalid tool call detected",
                                #             'error': f"Tool: {invalid_call.get('name', 'Unknown')}, Args: {invalid_call.get('args', 'Unknown')}", 
                                #             'id': invalid_call.get('id') or get_unique_response_id()
                                #         })

                        # elif msg.content and not msg.tool_calls:
                        #     response_list.extend([
                        #         {
                        #             'type': 'database', 
                        #             'agent_name': agent_name,
                        #             'title': f"**{agent_name}** has completed its database operation.", 
                        #             'content': msg.content, 
                        #             'id': getattr(msg, 'id', get_unique_response_id())
                        #         },
                        #     ])

                        # elif not msg.content and not msg.tool_calls:
                        #     response_list.append({
                        #         'type': 'database_status', 
                        #         'agent_name': agent_name,
                        #         'title': f"**{agent_name}** is processing...", 
                        #         'id': getattr(msg, 'id', get_unique_response_id())
                        #     })

                    elif isinstance(msg, ToolMessage):
                        response_list.append({'agent_name': agent_name, 'title': 'Analyzing result', 'id': msg.id})

        return response_list
        
    except Exception as e:
        print(f"Error in format_db_search_agent_aimessage : {str(e)}")
        response_list.append({'format_error': f"Error in format_db_search_agent_aimessage : {str(e)}"})
        return response_list
        # raise RuntimeError(f"Error in format_db_search_agent_aimessage: {str(e)}")


async def format_social_media_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                message_container_key = None
                if 'agent' in update:
                    message_container_key = 'agent'
                elif 'tools' in update:
                    message_container_key = 'tools'
                else:
                    return response_list

                messages_list = update.get(message_container_key, {}).get('messages')

                if not messages_list or not isinstance(messages_list, list) or not messages_list:
                    return response_list
                
                for msg in messages_list:
                    if isinstance(msg, AIMessage):
                        # token_metrics = get_token_usage_data(msg)
                        # response_list.append({'token_usage': token_metrics})

                        if msg.tool_calls:
                            tool_title = {
                                'reddit_post_search_tool': '{explanation}\n\n---\nSearching Reddit\n{queries}',
                                'get_reddit_post_text_tool': '{explanation}\n\n---\nReading Subreddit Posts\n{posts}',
                                'search_twitter': '{explanation}\n\n---\nSearching Twitter/X\n{queries}'
                            }
                            for tool_call in msg.tool_calls:
                                if tool_call['name'] == 'reddit_post_search_tool':
                                    title = tool_title['reddit_post_search_tool'].format(explanation=tool_call.get('args').get('explanation', 'Searching reddit posts'), queries=f"`{tool_call['args']['query']}`")
                                    response_list.extend([{'type': 'research', 'agent_name': agent_name, 'title': title, 'searching': [tool_call['args']['query']], 'id': tool_call.get('id') or get_unique_response_id()}])

                                elif tool_call['name'] == 'get_reddit_post_text_tool':
                                    posts = ' '.join(
                                        f"[REDDIT]({post_link})" for post_link in tool_call['args']['post_url'])
                                    title = tool_title['get_reddit_post_text_tool'].format(
                                        explanation=tool_call.get('args').get('explanation', 'Reading reddit post/comment'), posts=posts)
                                    response_list.append({'type': 'research', 'agent_name': agent_name, 'title': title, 'reading': tool_call['args']['post_url'], 'id': tool_call.get('id') or get_unique_response_id()})

                                elif tool_call['name'] == 'search_twitter':
                                    queries = ' '.join(
                                        f'`{query}`' for query in tool_call['args']['query'])
                                    title = tool_title['search_twitter'].format(
                                        explanation=tool_call.get('args').get('explanation', 'Searching relevant posts on Twitter/X'), queries=queries)
                                    response_list.extend([{'type': 'research', 'agent_name': agent_name, 'title': title, 'searching': tool_call['args']['query'], 'id': tool_call.get('id') or get_unique_response_id()}])

                        if msg.content and not msg.tool_calls:
                            response_list.extend([
                                {'type': 'research', 'agent_name': agent_name,
                                    'title': f"**{agent_name}** has completed its task.", 'content': msg.content, 'id': msg.id},
                            ])

                    elif isinstance(msg, ToolMessage):
                        sources = []
                        if msg.name == 'get_reddit_post_text_tool':
                            for post in json.loads(msg.content):
                                if 'link' in post and 'title' in post:
                                    sources.append({'link': post['link'], 'title': post['title'], 'snippet': post.get('snippet') or post.get('title', ''), 'favicon': get_favicon_link(post['link']), 'domain': 'REDDIT.COM'})

                        if msg.name == 'search_twitter':
                            op = json.loads(msg.content)
                            update_links = []
                            link_data = []
                            for post in op:
                                if 'link' in post and 'title' in post:
                                    sources.append({'link': post['link'], 'title': post['title'], 'snippet': post.get('snippet') or post.get('title', ''), 'favicon': get_favicon_link(
                                        post['link']), 'domain': 'X.COM'})

                                    update_links.extend([f"[X.com]({post['link']})"])
                                    link_data.extend([post['link']])

                            response_list.append({'type': 'research', 'agent_name': agent_name, 'title': f"I am extracting information from the following twitter/X posts.\n\n---\nReading\n{' '.join(update_links)}", 'reading': link_data, 'id': msg.id})

                        response_list.append({'agent_name': agent_name, 'content': msg.content, 'sources': sources})

            return response_list
    except Exception as e:
        print(f"Error in format_social_media_agent_update : {str(e)}")
        response_list.append({'format_error': f"Error in format_social_media_agent_update : {str(e)}"})
        return response_list
        # raise RuntimeError(f"Error in format_social_media_agent_update : {str(e)}")


async def format_coding_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                for key, value in update.items():
                    for field, valu in value.items():
                        if field == 'messages':
                            for msg in valu:
                                if isinstance(msg, AIMessage):
                                    # token_metrics = get_token_usage_data(msg)
                                    # response_list.append({'token_usage': token_metrics})

                                    if msg.tool_calls:
                                        tool_msg_list = []
                                        for tool_call in msg.tool_calls:
                                            title = f"{tool_call['args']['explanation']}\n\n---\n"
                                            title += f"```Python\n{tool_call['args']['code']}\n```"

                                            response_list.append({'type': 'research', 'agent_name': agent_name, 'title': title,
                                                                'code': tool_call['args']['code'], 'id': tool_call.get('id') or get_unique_response_id()})

                                    if msg.content and not msg.tool_calls:
                                        response_list.extend([
                                            {'type': 'research', 'agent_name': agent_name,
                                                'title': f"**{agent_name}** has completed its task.", 'content': msg.content, 'id': msg.id},
                                        ])

                                elif isinstance(msg, ToolMessage):
                                    response_list.extend([
                                        {'agent_name': agent_name,
                                            'content': msg.content},
                                    ])
        return response_list
    except Exception as e:
        print(f"Error in format_coding_agent_update : {str(e)}")
        response_list.append({'format_error': f"Error in format_coding_agent_update : {str(e)}"})
        return response_list
        # raise RuntimeError(f"Error in format_coding_agent_update : {str(e)}")


async def format_intent_detector_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                markdown_output = "**Query Review Result:**\n\n"
                message_container_key = None
                if 'Query Intent Detector' in update:
                    message_container_key = 'Query Intent Detector'
                else:
                    return response_list
                
                value = update.get(message_container_key, {})
                
                if value:
                    # messages can be a list or a single message object. Normalize to a single message `msg`.
                    msg = None
                    messages = value.get('messages')
                    if isinstance(messages, list) and messages:
                        # pick the last message that has `.content` attribute
                        for m in reversed(messages):
                            if hasattr(m, 'content'):
                                msg = m
                                break
                        if not msg:
                            msg = messages[-1]
                    elif hasattr(messages, 'content'):
                        msg = messages

                    # Safely parse content: it may be empty, plain text, or JSON.
                    parsed_obj = None
                    content_str = ''
                    if msg is not None:
                        content_str = getattr(msg, 'content', '') or ''
                        if isinstance(content_str, (dict, list)):
                            parsed_obj = content_str
                        else:
                            content_str = str(content_str)
                            content_str_stripped = content_str.strip()
                            if content_str_stripped:
                                try:
                                    # only attempt json.loads when it looks like JSON
                                    if content_str_stripped[0] in ('{', '['):
                                        parsed_obj = json.loads(content_str)
                                    else:
                                        # Not JSON — keep raw text
                                        parsed_obj = content_str
                                except Exception:
                                    # fallback: keep raw content and log a brief warning
                                    print(f"Warning: Query Intent Detector content is not valid JSON. Using raw content. Content snippet: {repr(content_str)[:500]}")
                                    parsed_obj = content_str
                            else:
                                parsed_obj = None
                    else:
                        parsed_obj = None

                    # Use pretty_format on either parsed object or on the raw content string
                    if parsed_obj is not None:
                        markdown_output += pretty_format(parsed_obj)
                    else:
                        # nothing useful to show
                        markdown_output += ""

                    # Ensure msg_id exists later when adding to response_list
                    msg_id = getattr(msg, 'id', get_unique_response_id())
                    
                    if value.get('progress') or value.get('progress_bar'):
                        progress_data = {}
                        if value.get('progress'):
                            progress_data['progress'] = value['progress']
                        if value.get('progress_bar'):
                            progress_data['progress_bar'] = value['progress_bar']
                        
                        response_list.append({
                            'type': 'progress',
                            'agent_name': agent_name,
                            **progress_data
                        })

                    if value.get('final_response'):
                        response = f"\n\n{value['final_response']}"
                        response_list.extend([                             
                                {'type': 'research', 'agent_name': agent_name, 'title': markdown_output, 'id': msg.id},                             
                                {'type': 'response', 'agent_name': agent_name, 'content': response, 'id': msg.id}                         
                            ]) 
                    else:
                        response_list.extend([                             
                                {'type': 'research', 'agent_name': agent_name, 'title': markdown_output, 'id': msg.id},                         
                            ]) 
        return response_list
    except Exception as e:
        # print(f"Error in format_intent_detector_update : {str(e)}")
        # response_list.append({'format_error': f"Error in format_intent_detector_update : {str(e)}"})
        # return response_list
        raise RuntimeError(f"Error in format_intent_detector_update : {str(e)}")


async def format_planner_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                markdown_output = "### Initial Plan:\n\n"
                message_container_key = None
                if 'Planner Agent' in update:
                    message_container_key = 'Planner Agent'
                else:
                    return response_list
                
                value = update.get(message_container_key, {})
                
                if value and 'messages' in value and isinstance(value['messages'], list):
                    msg_list = value['messages']
                    # if isinstance(msg_list[-1], AIMessage):
                        # token_metrics = get_token_usage_data(msg_list[-1])
                        # response_list.append({'token_usage': token_metrics})
                if value.get('progress_bar'):
                    response_list.append({
                        'type': 'progress',
                        'agent_name': agent_name,
                        'progress_bar': value['progress_bar']
                    })

                if value.get('research_plan'):
                    subtasks_list = value.get('research_plan')
                    for task_id, task in subtasks_list.items():
                        markdown_output += f"- {task.get('plan')}\n"

                                    
                    # markdown_output = pretty_format(subtasks_list)

                response_list.extend([
                    {'type': 'research', 'agent_name': agent_name, 'title': markdown_output, 'id': get_unique_response_id()}
                ])
        
        return response_list
    except Exception as e:
        # print(f"Error in format_planner_agent_update : {str(e)}")
        # response_list.append({'format_error': f"Error in format_planner_agent_update : {str(e)}"})
        # return response_list
        raise RuntimeError(f"Error in format_planner_agent_update : {str(e)}")


async def format_executor_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                markdown_output = "Initiating the devised Plan:\n\n---\n"
                message_container_key = None
                if 'Executor Agent' in update:
                    message_container_key = 'Executor Agent'
                else:
                    return response_list

                value = update.get(message_container_key, {})

                if value and 'messages' in value and isinstance(value['messages'], list):
                    msg_list = value['messages']
                    # if isinstance(msg_list[-1], AIMessage):
                    #     token_metrics = get_token_usage_data(msg_list[-1])
                        # response_list.append({'token_usage': token_metrics})
                        
                if value.get('progress_bar'):
                    response_list.append({
                        'type': 'progress',
                        'agent_name': agent_name,
                        'progress_bar': value['progress_bar']
                    })
                
                # task_list may come as part of the update dict or embedded in the last message content.
                extracted_task_list = None
                if value.get('task_list'):
                    extracted_task_list = value['task_list']
                else:
                    # try to extract from messages: look for AIMessage content that contains a task list
                    if isinstance(value.get('messages'), list) and value.get('messages'):
                        for m in reversed(value.get('messages')):
                            content = None
                            if isinstance(m, AIMessage):
                                content = getattr(m, 'content', '')
                            elif isinstance(m, dict) and 'content' in m:
                                content = m.get('content')
                            elif isinstance(m, (str, bytes)):
                                content = str(m)

                            if content:
                                content_str = str(content).strip()
                                # try JSON first
                                try:
                                    if content_str and content_str[0] in ('{', '['):
                                        parsed = json.loads(content_str)
                                        if isinstance(parsed, dict) and parsed.get('task_list'):
                                            extracted_task_list = parsed.get('task_list')
                                            break
                                        elif isinstance(parsed, list):
                                            extracted_task_list = parsed
                                            break
                                except Exception:
                                    # fallback: parse numbered/plain task blocks
                                    try:
                                        lines = content_str.splitlines()
                                        blocks = []
                                        curr = []
                                        for line in lines:
                                            if re.match(r'^\s*\d+\.|^\s*\d+\.', line):
                                                if curr:
                                                    blocks.append(curr)
                                                    curr = []
                                                curr.append(line)
                                            else:
                                                if line.strip() == '' and curr:
                                                    blocks.append(curr)
                                                    curr = []
                                                elif curr or line.strip():
                                                    curr.append(line)
                                        if curr:
                                            blocks.append(curr)

                                        tasks = []
                                        for block in blocks:
                                            text = ' '.join([l.strip() for l in block])
                                            fields = {}
                                            for m2 in re.finditer(r"(task_name|task name|task_\d+|agent|agent_name|agent task|agent_task|instruction|instructions|expected_output|required_context)\s*[:\-]\s*(.*?)(?=\s+\b(task_name|task name|task_\d+|agent|agent_name|agent task|agent_task|instruction|instructions|expected_output|required_context)\b\s*[:\-]|$)", text, flags=re.I):
                                                k = m2.group(1).strip().lower()
                                                v = m2.group(2).strip()
                                                fields[k] = v

                                            if not fields:
                                                tasks.append({'task_name': None, 'agent_name': None, 'agent_task': ' '.join([l.strip() for l in block]), 'instructions': '', 'expected_output': ''})
                                                continue

                                            task = {
                                                'task_name': fields.get('task_name') or fields.get('task name') or None,
                                                'agent_name': fields.get('agent_name') or fields.get('agent') or None,
                                                'agent_task': fields.get('agent task') or fields.get('agent_task') or fields.get('instructions') or fields.get('instruction') or '',
                                                'instructions': fields.get('instructions') or fields.get('instruction') or '',
                                                'expected_output': fields.get('expected_output') or '',
                                            }
                                            tasks.append(task)

                                        if tasks:
                                            extracted_task_list = tasks
                                            break
                                    except Exception:
                                        continue

                if extracted_task_list:
                    task_list = extracted_task_list

                    # Validate parsed tasks: require at minimum an agent and a task name.
                    invalid_count = 0
                    for subtask in task_list:
                        if not (subtask.get('task_name') or subtask.get('task')) or not (subtask.get('agent_name') or subtask.get('agent')):
                            invalid_count += 1

                    if invalid_count == len(task_list):
                        # Parser produced only invalid/incomplete tasks. Surface an explicit format error
                        logging.warning("ExecutorAgent: parsed task_list seems invalid — %s/%s tasks missing required fields. Returning format_error.", invalid_count, len(task_list))
                        response_list.append({'type': 'format_error', 'agent_name': agent_name, 'title': 'Executor Agent: could not parse structured task list from model output.', 'content': 'The executor agent returned an unstructured or incomplete task list. Please re-run or ensure the planner outputs structured JSON with `task_list`.', 'id': get_unique_response_id()})
                        return response_list

                    # Otherwise, render the tasks we could parse, but mark incomplete fields clearly.
                    for subtask in task_list:
                        task_name = subtask.get('task_name') or subtask.get('task') or 'Unnamed Task'
                        agent_name_val = subtask.get('agent_name') or subtask.get('agent') or 'Unknown Agent'
                        agent_task_val = subtask.get('agent_task') or subtask.get('task_description') or ''
                        instructions_val = subtask.get('instructions') or subtask.get('instruction') or ''
                        expected_output_val = subtask.get('expected_output') or ''

                        markdown_output += f"*{task_name}*\n"
                        markdown_output += f"- Agent: {agent_name_val}\n"
                        markdown_output += f"- Task: {agent_task_val}\n"
                        markdown_output += f"- Instructions: {instructions_val}\n"
                        markdown_output += f"- Expected Output: {expected_output_val}\n"

                        required_ctx = subtask.get('required_context') or subtask.get('required_context_list') or None
                        if required_ctx:
                            try:
                                ctx_list = list(required_ctx) if not isinstance(required_ctx, str) else [required_ctx]
                                markdown_output += f"- Required Context: {', '.join(f'`{item}`' for item in ctx_list)}\n"
                            except Exception:
                                markdown_output += f"- Required Context: `{required_ctx}`\n"

                        # mark if some key fields were missing for this subtask
                        missing = []
                        if not (subtask.get('task_name') or subtask.get('task')):
                            missing.append('task_name')
                        if not (subtask.get('agent_name') or subtask.get('agent')):
                            missing.append('agent_name')
                        if missing:
                            markdown_output += f"- _Parsing note_: missing fields: {', '.join(missing)}\n"

                        markdown_output += "\n"

                    response_list.extend([
                        {'type': 'research', 'agent_name': agent_name, 'title': markdown_output, 'id': get_unique_response_id()}
                    ])

        return response_list
            
    except Exception as e:
        # print(f"Error in format_executor_agent_update : {str(e)}")
        # response_list.append({'format_error': f"Error in format_executor_agent_update : {str(e)}"})
        # return response_list
        raise RuntimeError(f"Error in format_executor_agent_update : {str(e)}")


def clean_message_aggressive(content):
    """
    Aggressively removes XML tags, thinking tags, and their remnants
    Handles multi-line broken tags and fragments
    """
    content = re.sub(r'<[^>]*>', '', content, flags=re.DOTALL)

    content = re.sub(r'<[^>]*$', '', content, flags=re.MULTILINE)

    content = re.sub(r'^\s*>\s*', '', content, flags=re.MULTILINE)

    content = re.sub(r'>\s*', ' ', content)
    thinking_words = [
        r'\bthink\b', r'\bthinking\b', r'\bthought\b', r'\bthoughts\b',
        r'\bconsidering\b', r'\bpondering\b', r'\breflecting\b'
    ]
    
    for pattern in thinking_words:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)

    fragments = [
        r'\bink\b', r'\bth\b', r'\bnk\b', r'\bki\b', r'\bik\b',
        r'\binking\b', r'\bought\b', r'\bght\b', r'\bng\b'
    ]
    
    for fragment in fragments:
        content = re.sub(fragment, '', content, flags=re.IGNORECASE)

    # content = re.sub(r'\b[a-z]{1,2}\b', '', content, flags=re.IGNORECASE)

    # content = re.sub(r'\s+', ' ', content)
    # content = content.strip()
    
    return content


async def format_manager_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                message_container_key = None
                if 'Manager Agent' in update:
                    message_container_key = 'Manager Agent'
                else:
                    return response_list
                
                value = update.get(message_container_key, {})
                
                if value:
                    if 'messages' in value and isinstance(value['messages'], list):
                        msg_list = value['messages']
                        # if isinstance(msg_list[-1], AIMessage):
                        #     token_metrics = get_token_usage_data(msg_list[-1])
                            # response_list.append({'token_usage': token_metrics})

                    if value.get('progress_bar'):
                        response_list.append({
                            'type': 'progress',
                            'agent_name': agent_name,
                            'progress_bar': value['progress_bar']
                        })

                    if 'manager_instructions' in value and isinstance(value['manager_instructions'], list):
                        message_list = value['manager_instructions']

                        msg = message_list[-1]
                        response_list.extend([{'agent_name': agent_name, 'research-manager': msg.content, 'id': msg.id}])
            
        elif stream_mode == "messages":
            msg = update[0]
            if isinstance(msg, AIMessageChunk):
                if not "<think>" in msg.content and not "</think>" in msg.content:
                    content = clean_message_aggressive(msg.content)
                    # if agent_name == "Response Generator Agent":
                    #     print("RGA here--->  ",content,"\n")
                    response_list.append({'type': 'research-chunk', 'agent_name': agent_name, 'title': content, 'id': msg.id})

        return response_list
    except Exception as e:
        # print(f"Error in format_manager_agent_update : {str(e)}")
        # response_list.append({'format_error': f"Error in format_manager_agent_update : {str(e)}"})
        # return response_list
        raise RuntimeError(f"Error in format_manager_agent_update : {str(e)}")


async def format_task_router_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            if update and isinstance(update, dict):
                message_container_key = None
                if 'Task Router' in update:
                    message_container_key = 'Task Router'
                else:
                    return response_list

                value = update.get(message_container_key, {})
                current_task_dict = value.get('current_task')

                if not current_task_dict or not isinstance(current_task_dict, dict):
                    return response_list

                if value.get('progress_bar'):
                    response_list.append({
                        'type': 'progress',
                        'agent_name': agent_name,
                        'progress_bar': value['progress_bar']
                    })

                markdown_output = f"**Task Router** is initiating ***{current_task_dict['agent_name']}*** to perform the task '*{current_task_dict['task_name']}*'."
                if current_task_dict.get('task_feedback'):
                    markdown_output = f"**Task Validator** is retrying the task '*{current_task_dict['task_name']}*' {current_task_dict['retry']}th time through ***{current_task_dict['agent_name']}*** with following feedback:\n{current_task_dict['task_feedback']}"
                # markdown_output += f"with following instructions:\n{value['instructions']}"
                response_list.append({'type': 'task_change', 'agent_name': current_task_dict['agent_name'],
                        'task_name': current_task_dict['task_name'], 'id': get_unique_response_id()})
                return response_list
                    # else:
                    #     return {'type': 'message', 'agent_name': agent_name, 'content': "Solution generated by specialized agents."}
    except Exception as e:
        # print(f"Error in format_task_router_update : {str(e)}")
        # response_list.append({'format_error': f"Error in format_task_router_update : {str(e)}"})
        # return response_list
        raise RuntimeError(f"Error in format_task_router_update : {str(e)}")


async def format_response_generator_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            message_container_key = None
            if 'Response Generator Agent' in update:
                message_container_key = 'Response Generator Agent'
            else:
                return response_list
            
            value = update.get(message_container_key, {})

            if value and 'messages' in value and isinstance(value['messages'], list):
                msg_list = value['messages']
                # if isinstance(msg_list[-1], AIMessage):
                #     token_metrics = get_token_usage_data(msg_list[-1])
                    # response_list.append({'token_usage': token_metrics})
            if value.get('progress_bar'):
                    response_list.append({
                        'type': 'progress',
                        'agent_name': agent_name,
                        'progress_bar': value['progress_bar']
                    })

            if 'final_response' in value:
                valu = value.get('final_response')
                response_list.extend([{'agent_name': agent_name, 'response': valu, 'id': get_unique_response_id()},])

        elif stream_mode == "messages":
            msg = update[0]
            if isinstance(msg, AIMessageChunk):
                response_list.append({'type': 'response-chunk', 'agent_name': agent_name, 'content': msg.content, 'id': msg.id})

        return response_list
    except Exception as e:
        # print(f"Error in format_response_generator_agent_update : {str(e)}")
        # response_list.append({'format_error': f"Error in format_response_generator_agent_update : {str(e)}"})
        # return response_list
        raise RuntimeError(f"Error in format_response_generator_agent_update : {str(e)}")


async def format_validation_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            for key, value in update.items():
                for field, valu in value.items():
                    if field == 'validation_result':
                        markdown_output = f"   - Is response sufficient: {valu['is_valid']}\n"
                        markdown_output += f"   - Agent Feedback: {valu.get('feedback', 'No feedback.')}"

                        response_list.append({'type': 'validation', 'agent_name': agent_name, 'content': markdown_output, 'id': get_unique_response_id()})

        return response_list
    except Exception as e:
        raise RuntimeError(f"Error in format_validation_agent_update : {str(e)}")


async def format_non_tool_calling_agent_update(agent_name, stream_mode, update):
    try:
        response_list = []
        if stream_mode == "updates":
            for key, value in update.items():
                for field, valu in value.items():
                    if field == 'messages':
                        markdown_output = valu[-1].content.strip()
                        response_list.append(
                            {'type': 'research', 'agent_name': agent_name, 'title': f"**{agent_name}** has completed its task.", 'content': markdown_output, 'id': get_unique_response_id()}
                        )

        return response_list
    except Exception as e:
        # print(f"Error in format_non_tool_calling_agent_update : {str(e)}")
        # response_list.append({'format_error': f"Error in format_non_tool_calling_agent_update : {str(e)}"})
        # return response_list
        raise RuntimeError(f"Error in format_non_tool_calling_agent_update : {str(e)}")



async def format_langgraph_message(event):
    agent_id, stream_mode, update = event
    # TOOL_CALLING_AGENTS = ["DB Search Agent", "Map Agent"]
    TOOL_CALLING_AGENTS = ["Map Agent"]
    if agent_id:
        agent_name = agent_id[0].split(':')[0]
        # Call the appropriate formatter and ensure we always return a list-like iterable.
        try:
            if agent_name in TOOL_CALLING_AGENTS:
                res = await format_tool_calling_agent_update(agent_name, stream_mode, update)
            elif agent_name == "Coding Agent":
                res = await format_coding_agent_update(agent_name, stream_mode, update)
            elif agent_name == "Web Search Agent":
                res = await format_web_search_agent_update(agent_name, stream_mode, update)
            elif agent_name == "Social Media Scrape Agent":
                res = await format_social_media_agent_update(agent_name, stream_mode, update)
            elif agent_name == "Finance Data Agent":
                res = await format_finance_data_agent_update(agent_name, stream_mode, update)
            elif agent_name == 'Query Intent Detector':
                res = await format_intent_detector_update(agent_name, stream_mode, update)
            elif agent_name == 'Planner Agent':
                res = await format_planner_agent_update(agent_name, stream_mode, update)
            elif agent_name == 'Executor Agent':
                res = await format_executor_agent_update(agent_name, stream_mode, update)
            elif agent_name == 'Task Router':
                res = await format_task_router_update(agent_name, stream_mode, update)
            elif agent_name == 'Manager Agent':
                res = await format_manager_agent_update(agent_name, stream_mode, update)
            elif agent_name == 'Response Generator Agent':
                res = await format_response_generator_agent_update(agent_name, stream_mode, update)
            elif agent_name == 'Validation Agent':
                res = await format_validation_agent_update(agent_name, stream_mode, update)
            elif agent_name == 'DB Search Agent':
                res = await format_db_search_agent_aimessage(agent_name, stream_mode, update)
            else:
                res = await format_non_tool_calling_agent_update(agent_name, stream_mode, update)

            # coerce res into a list to satisfy callers that expect an iterable
            def _coerce_to_list(x):
                from collections.abc import Iterable
                if x is None:
                    return []
                if isinstance(x, list):
                    return x
                if isinstance(x, (tuple, set)):
                    return list(x)
                if isinstance(x, dict):
                    return [x]
                # strings are iterable but shouldn't be expanded
                if isinstance(x, str):
                    return [x]
                if isinstance(x, Iterable):
                    try:
                        return list(x)
                    except Exception:
                        return [x]
                return [x]

            coerced = _coerce_to_list(res)
            # remove any None entries that could break downstream extend()
            try:
                coerced = [c for c in coerced if c is not None]
            except Exception:
                # if coercion produced a non-iterable unexpectedly, wrap in list
                coerced = [coerced]

            # debug log truncated snapshot to help diagnose persistent None issues
            try:
                logging.debug("Formatter %s produced res=%s coerced=%s", agent_name, repr(res)[:500], repr(coerced)[:500])
            except Exception:
                logging.debug("Formatter %s produced non-serializable output", agent_name)

            if not coerced:
                logging.warning("Formatter for %s returned empty result after coercion. Returning explicit format_error to prevent LangGraph crash.", agent_name)
                return [{'type': 'format_error', 'agent_name': agent_name, 'title': 'Formatter returned empty result', 'content': 'Formatter produced no usable output after parsing.'}]

            return coerced
        except Exception as e:
            logging.exception("Error formatting message for agent %s: %s", agent_name, str(e))
            return []
    else:
            for key in update.keys():
                try:
                    if key == 'Query Intent Detector':
                        res = await format_intent_detector_update(key, stream_mode, update)
                    elif key == 'Planner Agent':
                        res = await format_planner_agent_update(key, stream_mode, update)
                    elif key == 'Executor Agent':
                        res = await format_executor_agent_update(key, stream_mode, update)
                    elif key == 'Task Router':
                        res = await format_task_router_update(key, stream_mode, update)
                    elif key == 'Manager Agent':
                        res = await format_manager_agent_update(key, stream_mode, update)
                    elif key == 'Response Generator Agent':
                        res = await format_response_generator_agent_update(key, stream_mode, update)
                    elif key == 'Validation Agent':
                        res = await format_validation_agent_update(key, stream_mode, update)
                    elif key == "Map Agent":
                        res = await format_map_agent_update_struct_response(key, stream_mode, update)
                    else:
                        res = await format_non_tool_calling_agent_update(key, stream_mode, update)

                    # coerce result into a list for consistency
                    def _coerce_to_list_key(x):
                        from collections.abc import Iterable
                        if x is None:
                            return []
                        if isinstance(x, list):
                            return x
                        if isinstance(x, (tuple, set)):
                            return list(x)
                        if isinstance(x, dict):
                            return [x]
                        if isinstance(x, str):
                            return [x]
                        if isinstance(x, Iterable):
                            try:
                                return list(x)
                            except Exception:
                                return [x]
                        return [x]

                    coerced = _coerce_to_list_key(res)
                    try:
                        coerced = [c for c in coerced if c is not None]
                    except Exception:
                        coerced = [coerced]

                    try:
                        logging.debug("Formatter for key %s produced res=%s coerced=%s", key, repr(res)[:500], repr(coerced)[:500])
                    except Exception:
                        logging.debug("Formatter for key %s produced non-serializable output", key)

                    if not coerced:
                        logging.warning("Formatter for key %s returned empty result after coercion. Returning explicit format_error.", key)
                        return [{'type': 'format_error', 'agent_name': key, 'title': 'Formatter returned empty result', 'content': 'Formatter produced no usable output after parsing.'}]

                    return coerced
                except Exception:
                    logging.exception("Error formatting langgraph message for key %s", key)
                    return []


async def format_fast_agent_update(stream_mode, update):
    agent_name = "Fast Insight Agent"
    try:
        response_list = []
        if stream_mode == "updates":
            message_container_key = None
            if 'agent' in update:
                message_container_key = 'agent'
            elif 'tools' in update:
                message_container_key = 'tools'
            else:
                return response_list
            
            messages_list = update.get(message_container_key, {}).get('messages')

            if not messages_list or not isinstance(messages_list, list) or not messages_list:
                return response_list
            
            for msg in messages_list:
                if isinstance(msg, AIMessage):
                    # token_metrics = get_token_usage_data(msg)
                    # response_list.append({'token_usage': token_metrics})

                    if msg.tool_calls:
                        tool_title = {
                            'advanced_internet_search': '{explanation}\n\n---\nSearching\n{queries}',
                            'search_audit_documents': '{explanation}\n\n---\nSearching\n{queries}',
                        }
                        for tool_call in msg.tool_calls:
                            if tool_call['name'] == 'advanced_internet_search':
                                queries = ' '.join(f'`{query}`' for query in tool_call['args']['query'])
                                title = tool_title['advanced_internet_search'].format(explanation=tool_call['args']['explanation'], queries=queries)
                                response_list.append(
                                    {'type': 'research', 'agent_name': agent_name, 'title': title, 'searching': tool_call['args']['query'], 'id': tool_call.get('id') or get_unique_response_id()}
                                )
                            elif tool_call['name'] == 'search_audit_documents':
                                alt_explanation = "Searching from uploaded document"
                                title = tool_title['advanced_internet_search'].format(explanation=tool_call['args'].get('explanation', alt_explanation), queries=tool_call['args']['query'])
                                response_list.append(
                                    {'type': 'research', 'agent_name': agent_name, 'title': title, 'searching': tool_call['args']['query'], 'id': tool_call.get('id') or get_unique_response_id()}
                                )
                            elif tool_call['name'] == 'search_company_info':
                                title = tool_call['args'].get('explanation', "Searching for correct ticker symbol")
                                response_list.append(
                                    {'type': 'research', 'agent_name': agent_name, 'title': title, 'id': tool_call.get('id') or get_unique_response_id()}
                                )
                            elif tool_call['name'] == 'get_stock_data':
                                title = tool_call['args'].get('explanation', "Fetching the realtime and historical stock data")
                                response_list.append(
                                    {'type': 'research', 'agent_name': agent_name, 'title': title, 'id': tool_call.get('id') or get_unique_response_id()}
                                )
                    
                    elif msg.content and not msg.tool_calls:
                        response_list.extend([{'agent_name': agent_name, 'response': msg.content, 'id': get_unique_response_id()}])
                
                elif isinstance(msg, ToolMessage):
                    sources = []
                    try:
                        if msg.name == 'advanced_internet_search':
                            op = json.loads(msg.content)
                            results = op.get("results", [])
                            if results:
                                update_links = [
                                    f"[{get_second_level_domain(result.get('link', ''))}]({result.get('link', '')})"
                                    for result in results if result.get('link')
                                ]
                                link_data = [result.get('link') for result in results if result.get('link')]
                                if update_links:
                                    response_list.append({
                                        'type': 'research',
                                        'agent_name': agent_name,
                                        'title': (
                                            "I am extracting information from the following relevant webpages.\n\n"
                                            "---\nReading\n" + ' '.join(update_links)
                                        ),
                                        'reading': link_data,
                                        'id': msg.id
                                    })
                    except Exception as e:
                        print(f"Error parsing advanced_internet_search content in fast agent: {str(e)}")
                        response_list.append({'format_error': f"Error parsing advanced_internet_search content in fast agent: {str(e)}"})

                    try:
                        if msg.name == "get_stock_data":
                            data_list_from_tool = []
                            if isinstance(msg.content, str):
                                try:
                                    loaded_content = json.loads(msg.content)
                                    if isinstance(loaded_content, list):
                                        data_list_from_tool = loaded_content
                                    elif isinstance(loaded_content, dict): # If a single item, wrap in list
                                        data_list_from_tool = [loaded_content]
                                except json.JSONDecodeError:
                                    # print(f"Warning: JSON decoding failed for get_stock_data content: {msg.content}")
                                    pass # Or append an error object to response_list
                            elif isinstance(msg.content, list):
                                data_list_from_tool = msg.content

                            for data_item in data_list_from_tool:
                                if isinstance(data_item, dict) and (data_item.get('realtime') is not None and data_item.get('historical') is not None) and (not 'error' in data_item.get('realtime') and not 'error' in data_item.get('historical')):
                                    data_item['chart_session_id'] = get_unique_stock_data_id()
                                    response_list.append({
                                        'type': 'stock_data', 'agent_name': agent_name, 'data': data_item, 'chat_session_id': data_item.get('chart_session_id')
                                    })
                    except Exception as e:
                        print(f"Error parsing get_stock_data content in fast agent: {str(e)}")
                        response_list.append({'format_error': f"Error parsing get_stock_data content in fast agent: {str(e)}"})

                    response_list.append({'agent_name': agent_name, 'content': msg.content, 'sources': sources})

        elif stream_mode == "messages":
            msg = update[0]
            if isinstance(msg, AIMessageChunk) and msg.content:
                response_list.append({'type': 'response-chunk', 'agent_name': agent_name, 'content': msg.content, 'id': msg.id})

        return response_list
    except Exception as e:
        raise RuntimeError(f"Error in format_fast_agent_update : {str(e)}")


def render_charts_as_images(chart_json_str: str) -> list[str]:
    from matplotlib.ticker import FuncFormatter

    if os.path.exists("/.dockerenv"):  # we're inside a Docker container
        charts_dir = "/data/charts"
    else:  # running locally
        charts_dir = os.path.join("data", "charts")

    os.makedirs(charts_dir, exist_ok=True)


    COLOR_PALETTE = [
        '#3B82F6',  # Blue
        '#F97316',  # Orange
        '#8B5CF6',  # Purple
        '#EF4444',  # Red
        '#10B981',  # Green
        '#F59E0B',  # Yellow
        '#06B6D4',  # Cyan
        '#EC4899',  # Pink
        '#84CC16',  # Lime
        '#6366F1',  # Indigo
    ]

    CHART_COLOR_MAP = {
        'Total Income': '#3B82F6',
        'Net Income': '#EC4899',
        'Cash & Investments': '#06B6D4',
        'Revenue': '#f7b23cff',
        'Net Profit': '#d67506ff',
        'Market Cap': '#581579',
        'P/E Ratio': '#185a06',
        'GDP Growth Rate': '#4aa0b6ff',
        'CPI Inflation': '#b45698ff',
        'Debt-to-GDP': '#bdc572ff',
        'Trade Balance': '#ec9fb6ff',
        'FDI Inflows': '#916666ff',
    }

    chart_data = json.loads(chart_json_str)
    image_urls = []

    for chart in chart_data.get("chart_collection", []):
        chart_type = chart.get("chart_type", "").lower()
        chart_title = chart.get("chart_title", "Chart")
        x_title = chart.get("x_label", "X-axis")
        y_title = chart.get("y_label", "Y-axis")

        x_labels = chart["data"][0]["x_axis_data"]

        x_labels = []
        for series in chart["data"]:
            for label in series["x_axis_data"]:
                if label not in x_labels:
                    x_labels.append(label)
        
        # Sort the labels (assuming they're years or can be sorted)
        try:
            x_labels.sort(key=lambda x: int(x) if x.isdigit() else x)
        except:
            pass 

        plt.figure(figsize=(10, 6.5), dpi=100)
        ax = plt.gca()
        def format_large_numbers(x, pos):
            if abs(x) >= 1e9:
                return f'{x/1e9:.0f}B'
            elif abs(x) >= 1e6:
                return f'{x/1e6:.0f}M'
            else:
                return f'{x:g}'

        ax.yaxis.set_major_formatter(FuncFormatter(format_large_numbers))

        # Background like Plotly
        ax.set_facecolor('#f1f1e2')
        plt.gcf().patch.set_facecolor('#f1f1e2')

        # Title
        # plt.title(chart_title, fontsize=14, fontweight='bold', color='#1F2937', pad=30)

        # Axis labels
        plt.xlabel(x_title, fontsize=12, color='#374151', labelpad=10)
        plt.ylabel(y_title, fontsize=12, color='#374151', labelpad=10)

        # Axis + grid styling
        ax.spines['bottom'].set_color('#D1D5DB')
        ax.spines['left'].set_color('#D1D5DB')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        ax.tick_params(axis='x', colors='#374151', labelrotation=45)
        ax.tick_params(axis='y', colors='#374151')
        ax.set_axisbelow(True)
        ax.grid(True, color='#E5E7EB', linewidth=0.7, alpha=0.7)

        if chart_type in ["bar", "group_bar"]:
            total_series = len(chart["data"])
            bar_width = 0.8 / total_series  if chart_type == "group_bar" else 0.9/ total_series 
            x = np.arange(len(x_labels))

            for idx, series in enumerate(chart["data"]):
                legend = series["legend_label"]
                series_x_labels = series["x_axis_data"]
                series_y_data = series["y_axis_data"]
                
                # Create positions and values only for the labels this series has
                series_positions = []
                series_values = []
                
                for i, label in enumerate(x_labels):
                    if label in series_x_labels:
                        label_idx = series_x_labels.index(label)
                        series_positions.append(i)
                        series_values.append(series_y_data[label_idx])
                
                # Skip if no data for this series
                if not series_positions:
                    continue
                
                color = CHART_COLOR_MAP.get(legend, COLOR_PALETTE[idx % len(COLOR_PALETTE)])
                
                if chart_type == "bar":
                    gap = 0.01  # Adjust gap size as needed (0.1 = 10% of a bar width)
                    offset = idx * (bar_width + gap) - ((total_series - 1) * (bar_width + gap)) / 2
                else:  # group_bar
                    offset = (idx - total_series/2 + 0.5) * bar_width
                
                # Plot only the positions where this series has data
                ax.bar(
                    np.array(series_positions) + offset,
                    series_values,
                    width=bar_width,
                    label=legend,
                    color=color,
                    alpha=0.9
                )

            ax.set_xticks(x)
            ax.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=10)

        elif chart_type == "lines":
            for idx, series in enumerate(chart["data"]):
                legend = series["legend_label"]

                color = CHART_COLOR_MAP.get(
                    legend, COLOR_PALETTE[idx % len(COLOR_PALETTE)]
                )

                ax.plot(
                    series["x_axis_data"],
                    series["y_axis_data"],
                    marker='o',
                    label=legend,
                    color=color,
                    linewidth=2.5,
                    markersize=6,
                    markeredgecolor='white',
                    markeredgewidth=1.5
                )

        else:
            print(f"Unsupported chart_type: {chart_type}")
            plt.close()
            continue
        num_series = len(chart["data"])
        ncol = min(4, num_series) 

        ax.legend(frameon=False, fontsize=10, bbox_to_anchor=(0.5, 0.96), loc='lower center', ncol=ncol)

        plt.tight_layout(pad=3.0)
        num_rows = (len(chart["data"]) + ncol - 1) // ncol
        top_margin = 0.82 - (0.05 * (num_rows - 1))  # shift down if multiple rows
        plt.subplots_adjust(top=top_margin)

        # Save image to blob
        image_stream = BytesIO()
        plt.savefig(
            image_stream,
            format="png",
            dpi=100,
            bbox_inches='tight',
            facecolor='#f1f1e2'
        )
        plt.close()
        image_stream.seek(0)

         # Save to /data folder with unique name
        file_name = f"{uuid.uuid4().hex[:8]}.png"
        # file_path = os.path.join("/data", "charts", file_name)
        file_path = os.path.join(charts_dir, file_name)

        with open(file_path, "wb") as f:
            f.write(image_stream.getbuffer())

        # Use a file URL or relative path
        image_url = os.path.relpath(file_path, os.getcwd())
        image_urls.append(image_url)
        print(f"Saved {chart_type} chart to {file_path}")

    return image_urls