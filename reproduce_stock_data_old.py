import asyncio
import os
from dotenv import load_dotenv
from src.ai.tools.finance_data_tools import GetStockData, TickerSchema

# Load environment variables
load_dotenv()

async def main():
    print("Checking API Keys...")
    print(f"BIG_AIR_LAB_FINANCE_API_KEY present: {bool(os.getenv('BIG_AIR_LAB_FINANCE_API_KEY'))}")
    print(f"FM_API_KEY present: {bool(os.getenv('FM_API_KEY'))}")

    tool = GetStockData()
    ticker_data = [TickerSchema(ticker="AAPL", exchange_symbol="NASDAQ")]
    
    print("\nRunning GetStockData (finance_data_tools) for AAPL...")
    try:
        # The tool's _run method calls asyncio.run inside, but we are already in async loop.
        # finance_data_tools.py _run uses asyncio.run(self._arun(...))? 
        # No, let's check the code.
        # It defines _run and inside it defines async functions but calls them with asyncio.run?
        # Line 370: realtime_response, currency_data = asyncio.run(get_stock_and_currency(ticker, fm_api_key))
        # This will fail if called from an existing loop!
        
        # We should run it in a separate thread or process to avoid "asyncio.run() cannot be called from a running event loop"
        # Or just call it synchronously if it's designed that way.
        
        # But wait, if I run this script with asyncio.run(main()), I am in a loop.
        # If the tool calls asyncio.run() internally, it will crash.
        
        # Let's try running it without asyncio.run(main()) at top level, just plain python script.
        pass
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    # asyncio.run(main()) # This might cause issues if the tool also calls asyncio.run
    
    # Let's just call the tool synchronously as it seems to be designed.
    load_dotenv()
    print("Checking API Keys...")
    print(f"FM_API_KEY present: {bool(os.getenv('FM_API_KEY'))}")

    tool = GetStockData()
    ticker_data = [TickerSchema(ticker="AAPL", exchange_symbol="NASDAQ")]
    
    print("\nRunning GetStockData (finance_data_tools) for AAPL...")
    try:
        result = tool._run(ticker_data=ticker_data, period="1M")
        print("\nResult:")
        import json
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
