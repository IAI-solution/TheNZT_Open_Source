import asyncio,time
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_community.document_loaders import PyPDFLoader, WebBaseLoader, PyMuPDFLoader
import regex as re
from src.backend.utils.utils import pretty_format
from typing import List, Dict, Any, Type, Tuple, Optional
from src.ai.agents.utils import get_context_based_answer_prompt
from src.ai.llm.model import get_llm, get_llm_alt
import os
from src.ai.ai_schemas.tool_structured_input import WebPageInfoSchema, WebSearchSchema, TavilyToolSchema
from collections import defaultdict
import datetime
from datetime import timezone
import json
import concurrent.futures
from langchain_tavily import TavilySearch
from src.backend.utils.utils import get_second_level_domain, get_favicon_link
import src.backend.db.mongodb as mongodb
from langgraph.config import get_stream_writer
#from src.ai.llm.config import WebSearchConfig
from src.ai.llm.config import  WebSearchConfig


# serper_api_key = os.environ.get("GOOGLE_SERPER_API_KEY")

wsc=WebSearchConfig()

# class InternetSearchTool(BaseTool):
#     name: str = "search_internet"
#     description: str = """This is a backup tool that searches input query on the internet using Google Search.
# Returns search results containing website links, titles, and snippets.
# """
#     args_schema: Type[BaseModel] = WebSearchSchema

#     def _run(self, query: List[str], explanation: str) -> List[Dict]:
#         try:
#             search_tool = GoogleSerperAPIWrapper(
#                 serper_api_key=serper_api_key, k=6)
#             # response = defaultdict(list)
#             response = []
#             for q in query:
#                 result = search_tool.results(q)
#                 response.extend(result.get('organic', []))
#                 response.extend(result.get('topStories', []))

#             return response

#         except Exception as e:
#             print(
#                 f"Google Serper search failed: {str(e)}. Falling back to DuckDuckGo.")

#             try:
#                 duckduckgo_tool = DuckDuckGoSearchResults(
#                     num_results=5, output_format="list")
#                 response = []
#                 for q in query:
#                     result = duckduckgo_tool.invoke(q)
#                     response.extend(result)
#                 return response

#             except Exception as fallback_e:
#                 error_msg = f"Both Google Serper and DuckDuckGo searches failed: {str(fallback_e)}"
#                 return error_msg


# class WebpageInfoTool(BaseTool):
#     name: str = "get_webpage_info"
#     description: str = """This is a backup tool that extracts required information from given webpage urls, when websearch method is google or duckduckgo. Returns a list of dictionaries containing webpage titles, urls and available info.
# """
#     args_schema: Type[BaseModel] = WebPageInfoSchema

#     def _run(self, webpages: List[dict], explanation: str) -> Dict:
#         tool_response = []
#         file_to_write = []
#         try:
#             with concurrent.futures.ThreadPoolExecutor(max_workers=len(webpages)) as executor:
#                 future_to_webpage = {
#                     executor.submit(self._process_webpage, webpage): webpage
#                     for webpage in webpages
#                 }

#                 for future in concurrent.futures.as_completed(future_to_webpage):
#                     webpage_result = future.result()
#                     if webpage_result:
#                         tool_response.append(webpage_result['tool_output'])
#                         file_to_write.append(webpage_result['file_to_store'])

#             # if file_to_write:
#                 # asyncrunner.run_coroutine(mongodb.insert_in_db(file_to_write))

#             return tool_response
#         except Exception as e:
#             error_msg = f"Error in extracting information from webpages: {str(e)}"
#             print(error_msg)
#             return [{'error': error_msg}]

#     def _process_webpage(self, webpage):
#         link = webpage.link
#         information_to_extract = webpage.information_to_extract
#         timestamp = datetime.datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
#         filename = f"webpage_extraction_{timestamp}.json"

#         tool_output = {'link': link, 'available_info': '', 'filename': filename}
#         file_to_write = {'link': link, 'title': link, 'snippet': link,  'raw_content': ''}

#         if not link.startswith(("https://", "http://")):
#             raise RuntimeError("Invalid link")

#         try:
#             loader = WebBaseLoader([link])
#             documents = loader.load()
#             if documents[0].metadata.get('title'):
#                 file_to_write['title'] = documents[0].metadata.get('title')
#             file_to_write['snippet'] = documents[0].metadata.get('description', file_to_write['title'])
#             file_to_write['raw_content'] = file_to_write['snippet']
#             tool_output['available_info'] = file_to_write['snippet']

#             context = ""
#             for doc in documents:
#                 context += self._clean_text(doc.page_content) + "\n\n"

#             if not context.strip():
#                 raise RuntimeError("Unable to extract text from webpage.")

#             file_to_write['raw_content'] = context

#             if len(context.split()) > 600:
#                 tool_output['available_info'] = self._extract_info(context, information_to_extract)
#             else:
#                 tool_output['available_info'] = context

#             return {
#                 'tool_output': tool_output, 
#                 'file_to_store': {'filename': filename, 'data': file_to_write}
#             }

#         except Exception as e:
#             tool_output['error'] = f"Unable to extract information from webpage. Error: {str(e)}"
#             return {
#                 'tool_output': tool_output, 
#                 'file_to_store': {'filename': filename, 'data': file_to_write}
#             }

#     def _clean_text(self, text: str) -> str:
#         try:
#             text = re.sub(r'\n\s*\n', '\n', text)
#             text = re.sub(r'\t+', ' ', text)
#             text = text.strip()
#             text = re.sub(r' +', ' ', text)
#             return text
#         except Exception as e:
#             print(f"Error in cleaning webpage text: {str(e)}")
#             return text

#     def _extract_info(self, context: str, info_to_extract: str) -> str:
#         try:
#             # model = get_llm("azure/gpt-4.1-nano", 0.0)
#             # model = get_llm("gemini/gemini-2.5-pro", 0.0)
#             # model_alt = get_llm_alt("gemini/gemini-2.0-flash-lite", 0.0)
#             model = get_llm(model_name=wsc.MODEL, temperature=wsc.TEMPERATURE)
#             model_alt = get_llm_alt(model_name=wsc.ALT_MODEL, temperature=wsc.ALT_TEMPERATURE)
#             text = f"Extract the following information from the given context:\n{info_to_extract}"
#             input = get_context_based_answer_prompt(context, text)

#             try:
#                 response = model.invoke(input)
#             except Exception as e:
#                 print(f"Falling back to alternate model: {str(e)}")
#                 try:
#                     response = model_alt.invoke(input)
#                 except Exception as e:
#                     print(f"Error occurred in fallback model: {str(e)}")
#                     return " ".join(context.split()[:600])

#             return response.content.strip()
#         except Exception as e:
#             error_msg = f"Error in extracting key information from webpage: {str(e)}"
#             print(error_msg)
#             return " ".join(context.split()[:600])


class AdvancedInternetSearchTool(BaseTool):
    name: str = "advanced_internet_search"
    description: str = """Searches input query on the internet, extracts content from the webpages and provides results.
Returns search results containing website url, title, content and score.
When searching a query which is specific to a country or region, provide the country name in small letters in the `country` input field.
"""
    args_schema: Type[BaseModel] = TavilyToolSchema

    def _count_words(self, text: str) -> int:
        if not isinstance(text, str) or not text:
            return 0
        return len(text.split())

    def _collapse_repeated_words(self, text: str) -> str:
        # Use more efficient regex with limits
        text = re.sub(r'\b(\w+)(?:\s+\1\b){2,}', r'\1', text)  # Only collapse 3+ repeats
        return text

    def _remove_duplicate_lines(self, text: str) -> str:
        """Optimized version with early termination"""
        if not text or len(text) < 100:  # Skip for very short text
            return text
            
        seen = set()
        lines = text.splitlines()
        if len(lines) < 10:  # Skip for short content
            return text
            
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if len(new_lines) == 0 or new_lines[-1].strip():
                    new_lines.append('')
                continue

            key = stripped.lower()
            if key not in seen:
                seen.add(key)
                new_lines.append(line)
                
        return "\n".join(new_lines)

    def _remove_long_redundant_blocks_optimized(self, text: str, min_block_words: int = 30) -> str:
        """Much more efficient version with early termination and limits"""
        tokens = text.split()
        n = len(tokens)
        
        # Early termination for small texts
        if n < min_block_words * 2:
            return text
            
        # Limit processing for very large texts to avoid performance issues
        if n > 5000:  # Process only first 5000 tokens for very long content
            tokens = tokens[:5000]
            n = 5000

        keep = [True] * n
        first_occurrence = {}
        
        # Reduce max phrase length to improve performance
        max_phrase = min(min_block_words + 5, n // 3)  # Reduced from n//2

        # Process only larger blocks first (reverse order for efficiency)
        for L in range(max_phrase, min_block_words - 1, -1):
            for i in range(0, n - L + 1):
                if not all(keep[i:i+L]):
                    continue
                    
                phrase = tuple(tokens[i:i+L])
                if phrase in first_occurrence:
                    # Mark tokens for removal
                    for k in range(i, i+L):
                        keep[k] = False
                else:
                    first_occurrence[phrase] = i
                    
                # Early termination if we've processed enough
                if len(first_occurrence) > 100:  # Limit memory usage
                    break

        filtered = [tok for (tok, kf) in zip(tokens, keep) if kf]
        return " ".join(filtered)

    def _clean_text_optimized(self, text: str) -> str:
        """Optimized text cleaning with early termination and limits"""
        try:
            if not text or len(text) < 50:
                return text.strip()
                
            # Limit text size to prevent excessive processing
            if len(text) > 50000:  # 50k chars limit
                text = text[:50000] + "..."
                
            # Basic cleaning
            text = re.sub(r'\n\s*\n', '\n', text)
            text = re.sub(r'\t+', ' ', text)
            text = text.strip()
            text = re.sub(r' +', ' ', text)

            # Only apply expensive operations for medium-sized texts
            if 100 < len(text) < 20000:
                text = self._collapse_repeated_words(text)
                text = self._remove_duplicate_lines(text)
                
                # Only apply block removal for longer texts
                if len(text) > 1000:
                    text = self._remove_long_redundant_blocks_optimized(text, min_block_words=30)

            return text
        except Exception as e:
            print(f"Error in cleaning webpage text: {str(e)}")
            return text[:1000] if len(text) > 1000 else text  # Return truncated version on error
    
    def _prepare_output_and_file_data(self, result_dict: Dict, source: str) -> Tuple[Dict, Optional[Dict]]:
        link = result_dict.get('url') or result_dict.get('link')
        title = result_dict.get('title', 'No Title')
        raw_content = result_dict.get('raw_content')
        snippet_content = result_dict.get('content') or result_dict.get('snippet', '')

        content_for_llm = ""

        if source == "Tavily" and raw_content:
            # Quick word count before expensive cleaning
            estimated_word_count = len(raw_content.split())
            if estimated_word_count <= 3000:  # Increased threshold slightly
                content_for_llm = self._clean_text_optimized(raw_content)
            else:
                # For very long content, just clean the snippet
                content_for_llm = self._clean_text_optimized(snippet_content)
        else:
            content_for_llm = self._clean_text_optimized(snippet_content)

        if content_for_llm is None:
            content_for_llm = ""

        tool_output = {
            'link': link,
            'content': content_for_llm,
        }

        source_to_send = {
            'title': title,
            'link': link,
            "favicon": get_favicon_link(link),
            "domain": get_second_level_domain(link),
            'snippet': snippet_content or title,
        }

        return tool_output, source_to_send
    
    def _run(self, query: List[str] = None, time_range: str = None, country: str = None, explanation: str = None) -> Dict:
        writer = get_stream_writer()
        output = {'results': [], 'errors': []}

        # Initialize search engines once
        search_tavily = TavilySearch(max_results=5, include_raw_content=True, time_range=time_range, include_domains=None, country=country)
        # search_google = GoogleSerperAPIWrapper(serper_api_key=serper_api_key, k=6)
        search_duckduckgo = DuckDuckGoSearchResults(num_results=5, output_format="list")

        def process_query(q):
            current_results = []
            sources_data = []
            error_messages = []
            method_used = "None"

            # Try Tavily first
            try:
                start = time.time()
                first_search = search_tavily.invoke(input={'query': q})
                tavily_raw_results = first_search.get('results', [])
                tavily_time = time.time() - start
                print(f"Tavily search time: {tavily_time:.2f}s for query: {q}")

                if tavily_raw_results:
                    method_used = "Tavily"
                    
                    # Process results in batch to reduce writer calls
                    start_process = time.time()
                    for r in tavily_raw_results:
                        tool_res, source_to_send = self._prepare_output_and_file_data(r, "Tavily")
                        current_results.append(tool_res)
                        sources_data.append(source_to_send)
                    
                    process_time = time.time() - start_process
                    print(f"Text processing time: {process_time:.2f}s for {len(tavily_raw_results)} results")

                    # Single writer call instead of multiple
                    if sources_data:
                        writer({'source_update': sources_data})

                    if current_results:
                        return {"method": method_used, "results": current_results, "query": q, "error": None}
                        
            except Exception as e:
                error_messages.append(f"Tavily error for query '{q}': {str(e)}")

            # # Fallback to Google (same optimization pattern)
            # try:
            #     google_structured_result = search_google.results(q)
            #     google_api_results = google_structured_result.get('organic', []) + google_structured_result.get('topStories', [])

            #     if google_api_results:
            #         method_used = "Google"
            #         for r in google_api_results:
            #             tool_res, source_to_send = self._prepare_output_and_file_data(r, "Google")
            #             current_results.append(tool_res)
            #             sources_data.append(source_to_send)

            #         if sources_data:
            #             writer({'source_update': sources_data})

            #         if current_results:
            #             return {"method": method_used, "results": current_results, "query": q, "error": None}
                        
            # except Exception as e:
            #     error_messages.append(f"Google error for query '{q}': {str(e)}")

            # Fallback to DuckDuckGo
            try:
                ddg_structured_results = search_duckduckgo.invoke(q)
                if ddg_structured_results:
                    method_used = "DuckDuckGo"
                    for r in ddg_structured_results:
                        tool_res, source_to_send = self._prepare_output_and_file_data(r, "DuckDuckGo")
                        current_results.append(tool_res)
                        sources_data.append(source_to_send)

                    if sources_data:
                        writer({'source_update': sources_data})

                    if current_results:
                        return {"method": method_used, "results": current_results, "query": q, "error": None}
                        
            except Exception as e:
                error_messages.append(f"DuckDuckGo error for query '{q}': {str(e)}")

            return {
                "method": "Failed",
                "results": [],
                "query": q,
                "error": f"All search methods failed for query '{q}': " + "; ".join(error_messages)
            }

        try:
            start_all = time.time()
            
            # Use ProcessPoolExecutor for CPU-intensive text processing
            # Or limit ThreadPoolExecutor workers to avoid resource contention
            max_workers = min(3, len(query))  # Limit concurrent searches
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_query = {executor.submit(process_query, q): q for q in query}
                
                for future in concurrent.futures.as_completed(future_to_query):
                    try:
                        result = future.result(timeout=60)  # Add timeout to prevent hanging
                        if result["method"] != "Failed":
                            output['results'].extend(result["results"])
                        else:
                            if result.get("error"):
                                output['errors'].append(result["error"])
                    except concurrent.futures.TimeoutError:
                        q = future_to_query[future]
                        err_msg = f"Timeout processing query '{q}'"
                        print(err_msg)
                        output['errors'].append(err_msg)
                    except Exception as e:
                        q = future_to_query[future]
                        err_msg = f"Critical error processing result for query '{q}': {str(e)}"
                        print(err_msg)
                        output['errors'].append(err_msg)
                        
            total_time = time.time() - start_all
            print(f"Total execution time: {total_time:.2f}s for {len(query)} queries")

        except Exception as e:
            error_msg = f"Critical error during concurrent search execution: {str(e)}"
            print(error_msg)
            output['errors'].append(error_msg)

        return output


# search_internet = InternetSearchTool()
# get_webpage_info = WebpageInfoTool()
advanced_internet_search = AdvancedInternetSearchTool()

tool_list = [
    advanced_internet_search,
    # get_webpage_info
]
