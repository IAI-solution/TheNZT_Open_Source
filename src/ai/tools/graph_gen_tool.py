import requests
import json
import random
from langchain_core.tools import tool, BaseTool
from typing import List, Literal, Type, Dict
import time
import os 
from pydantic import BaseModel, Field
from src.ai.ai_schemas.tool_structured_input import GeocodeInput
from typing import Optional, List, Literal, Tuple, Dict, Union
from src.ai.tools.graph_gen_tool_system_prompt import SYSTEM_PROMPT_STRUCT_OUTPUT
# from langchain_litellm import ChatLiteLLM
# from langchain_community.chat_models import ChatLiteLLM
from dotenv import load_dotenv
from src.ai.llm.model import get_llm
from src.ai.llm.config import GraphGenerationConfig

load_dotenv()

ggc = GraphGenerationConfig()

# from smolagents import LiteLLMModel, CodeAgent

# def extract_markdown_tables_from_string(md_content):
#     """Extracts all markdown tables from a markdown string.

#     This function scans the provided markdown string and extracts any tables
#     written in GitHub Flavored Markdown format. A table is identified by a header
#     row containing '|' and a separator line immediately following it (with '-', ':' and '|').
#     The function returns each found table as a string (including header, separator, and rows).

#     Args:
#         md_content (str): The markdown content as a string.

#     Returns:
#         list of str: A list where each element is a string representation of a markdown table
#         found in the string, preserving line breaks within each table.
#     """
#     tables = []
#     current_table = []
#     in_table = False

#     # Split input string into lines
#     lines = md_content.splitlines()

#     for i, line in enumerate(lines):
#         line_strip = line.strip()

#         # Table header row: must contain '|' and not only dashes/spaces
#         if '|' in line_strip and not set(line_strip.replace('|', '').replace(' ', '')).issubset({'-', ':'}):
#             # Check next line for separator
#             if i + 1 < len(lines):
#                 next_line = lines[i + 1].strip()
#                 if (
#                     '|' in next_line
#                     and set(next_line.replace('|', '').replace(' ', '')).issubset({'-', ':'})
#                     and len(next_line.replace('|', '').replace(' ', '')) >= 3
#                 ):
#                     # Start of a new table
#                     in_table = True
#                     current_table.append(line.rstrip('\n'))
#                     continue

#         # If we're in a table, append lines
#         if in_table:
#             if line_strip == '' or not '|' in line_strip:
#                 # End of table
#                 if current_table:
#                     tables.append('\n'.join(current_table))
#                 current_table = []
#                 in_table = False
#             else:
#                 current_table.append(line.rstrip('\n'))

#     # Handle last table if string ends with a table
#     if current_table:
#         tables.append('\n'.join(current_table))

#     return tables

# Load the LLM
# AZURE_API_KEY = os.getenv("AZURE_API_KEY")
# AZURE_API_BASE = os.getenv("AZURE_API_BASE")

# llm = ChatLiteLLM(
#     model="azure/gpt-4.1-mini", 
#     temperature=0.1, 
#     azure_api_key=AZURE_API_KEY, 
#     api_base=AZURE_API_BASE
# )
# llm = ChatLiteLLM(
#     model="gemini/gemini-2.5-pro", 
#     temperature=0.1, 
#     # azure_api_key=AZURE_API_KEY, 
#     # api_base=AZURE_API_BASE
# )
llm = get_llm(model_name=ggc.MODEL, temperature=ggc.TEMPERATURE)

class SingleChartData(BaseModel):
    legend_label: str = Field(description="The legend label for the given data.")
    x_axis_data: List[Union[float, str]] = Field(description="List of values for the x-axis of the chart")
    y_axis_data: List[float] = Field(description="List of values for the y-axis of the chart")
    color: str = Field(description="Color of the chart in Hex Color Code. Use only the color mentioned: `#1537ba`, `#00a9f4`, `#051c2c`, `#82a6c9`, `#99e6ff`, `#14b8ab`, `#9c217d`", max_length=7, min_length=7)


class StructOutput(BaseModel):
    chart_type: Literal['bar', 'group_bar', 'lines'] = Field(description="Type of the chart to be generated")
    chart_title: str = Field(description="Title of the chart")
    x_label: str = Field(description="Label for the x-axis")
    y_label: str = Field(description="Label for the y-axis")    
    data: List[SingleChartData] = Field(description="List of ChartData, containing x and y axis data")
    

class StructOutputList(BaseModel):
    chart_collection: List[StructOutput] = Field(description="List of individual chart configurations to be generated from the input data. Each StructOutput represents one chart with its data and metadata. Don't put more than 1 element in this List.", max_length=1)


llm_struct_op = llm.with_structured_output(StructOutputList)


def generate_graphs(md_content):
    table = md_content

    INPUT_PROMPT = f"""
The table is listed below:

\n{table}\n

"""
    print(f"INPUT_PROMPT = {INPUT_PROMPT}")
    prompt = SYSTEM_PROMPT_STRUCT_OUTPUT + INPUT_PROMPT

    try:
        result = llm_struct_op.invoke(prompt)
        struct_output = result
        print(f"Output from graph generator struct_output= {struct_output}")
        dump = struct_output.model_dump()
        print(f"Output from graph generator dump= {dump}")

        # if the LLM returns an empty chart_collection, treat that as a failure
        if not dump.get("chart_collection"):
            print(f"No charts in output.")
            return "NO_CHART_GENERATED"
        
        return json.dumps(dump, ensure_ascii=False)
        # print(f"struct_output.model_dump() = {struct_output.model_dump()}")
    except Exception as e:
        print(f"Error in generating graphs {e}")
        return "NO_CHART_GENERATED"

    # # tables = extract_markdown_tables_from_string(md_content)
    # # results = []

    # if not tables:
    #     print("No tables")
    #     return "NO_CHART_GENERATED"
    
    # for idx, table in enumerate(tables, start=1):        
    #     INPUT_PROMPT = f"""
    #     The table is listed below:

    #     \n{table}\n

    #     """
    #     print(f"INPUT_PROMPT = {INPUT_PROMPT}")
    #     prompt = SYSTEM_PROMPT_STRUCT_OUTPUT + INPUT_PROMPT

    #     try:
    #         result = llm_struct_op.invoke(prompt)
    #         struct_output = result
    #         print(f"Output from graph generator struct_output= {struct_output}")
    #         dump = struct_output.model_dump()
    #         print(f"Output from graph generator dump= {dump}")

    #         # if the LLM returns an empty chart_collection, treat that as a failure
    #         if not dump.get("chart_collection"):
    #             print(f"[Table {idx}] no charts in output.")
    #             return "NO_CHART_GENERATED"
            
    #         results.append(dump)
    #         # print(f"struct_output.model_dump() = {struct_output.model_dump()}")
    #     except Exception as e:
    #         print(f"[Table {idx}] Could not generate graphs: {e}")
    #         return "NO_CHART_GENERATED"
    #     # results.append(struct_output.model_dump())
    #     # print(f"[Table {y}] JS Code:\n{struct_output}\n{'-'*30}")

    

    # return json.dumps(results, ensure_ascii=False)


class GraphGenToolInput(BaseModel):
    table: str = Field(description="Provide a table containing numerical data of similar property in markdown format to create the visualization chart.")


class GraphGenTool(BaseTool):
    name: str = "graph_generation_tool"
    description: str = """
    Use this tool to generate a visualization chart by providing the table in markdown format. The tool returns formatted data in json format.
    """
    args_schema: Type[BaseModel] = GraphGenToolInput

    def _run(self, table: str) -> str:
        print(f"---TOOL CALL: graph_generation_tool \n --- \n Table: \n{table}\n --- \n")
        output_string = generate_graphs(table)

        if output_string == "NO_CHART_GENERATED":
            return "No chart generated; please skip creating any ```graph``` block for this table in the response."
        
        print(f"return from generate_graphs = {output_string}")

        return output_string

graph_generation_tool = GraphGenTool()
graph_tool_list = [graph_generation_tool]



# def generate_graphs(md_content):
#     tables = extract_markdown_tables_from_string(md_content)
    
#     # output_dir = "output_graphs/"
#     # os.makedirs(output_dir, exist_ok=True)

#     results = []

    
#     for y, table in enumerate(tables, start=1):
        
#         INPUT_PROMPT = f"""
#         The table is listed below:

#         \n{table}\n

#         """

#         # result = agent.run(SYSTEM_PROMPT + INPUT_PROMPT)

#         # if "```python" not in result:
#         #     results.append(result)
#         # else:
#         #     results.append("NO GRAPH GENERATED!.")

#         prompt = SYSTEM_PROMPT_STRUCT_OUTPUT + INPUT_PROMPT
#         try:
#             result = llm_struct_op.invoke(prompt)
#             struct_output = result
#             print(f"struct_output.model_dump() = {struct_output.model_dump()}")
#         except Exception as e:
#             print(f"Could not generate graphs: {e}")

#         results.append(struct_output.model_dump())
#         print(f"[Table {y}] JS Code:\n{struct_output}\n{'-'*30}")

#     return json.dumps(results, ensure_ascii=False)

