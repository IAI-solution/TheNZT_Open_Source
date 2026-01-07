
import json
import sys
import os

# Mock the graph generation tool
from src.ai.tools.graph_gen_tool import graph_generation_tool

def test_graph_generation():
    print("Testing graph generation with stock data...")
    stock_table = """
| Date       | Close |
|------------|-------|
| 2024-01-01| 150.0 |
| 2024-01-02| 152.5 |
| 2024-01-03| 151.0 |
| 2024-01-04| 155.0 |
| 2024-01-05| 158.0 |
    """
    
    try:
        result_str = graph_generation_tool._run(stock_table)
        print(f"Tool output: {result_str}")
        
        if result_str == "NO_CHART_GENERATED":
             print("FAILURE: No chart generated.")
             return False

        if "No chart generated" in result_str and "skip creating" in result_str:
             print("FAILURE: Tool returned skip message.")
             return False
             
        result = json.loads(result_str)
        chart_collection = result.get("chart_collection", [])
        
        if not chart_collection:
            print("FAILURE: Empty chart collection.")
            return False
            
        chart = chart_collection[0]
        print(f"Chart Type: {chart.get('chart_type')}")
        
        if chart.get('chart_type') == 'lines':
            print("SUCCESS: Line chart generated for stock data.")
            return True
        else:
            print(f"WARNING: generated chart type is {chart.get('chart_type')}, expected lines for stock data, but graph WAS generated.")
            return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_graph_generation()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
