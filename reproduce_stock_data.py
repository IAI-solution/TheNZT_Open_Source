import asyncio
import os
from dotenv import load_dotenv
from src.ai.tools.financial_tools import GetStockData, TickerSchema

# Load environment variables
load_dotenv()

async def main():
    print("Checking API Keys...")
    print(f"BIG_AIR_LAB_FINANCE_API_KEY present: {bool(os.getenv('BIG_AIR_LAB_FINANCE_API_KEY'))}")
    print(f"FM_API_KEY present: {bool(os.getenv('FM_API_KEY'))}")

    tool = GetStockData()
    ticker_data = [TickerSchema(ticker="AAPL", exchange_symbol="NASDAQ")]
    
    print("\nRunning GetStockData for AAPL...")
    try:
        # The tool's _run method calls asyncio.run, so we should call _arun directly if we are already in async
        # But _run is synchronous wrapper. Let's call _arun.
        result = await tool._arun(ticker_data=ticker_data, period="1M")
        print("\nResult:")
        import json
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(main())
