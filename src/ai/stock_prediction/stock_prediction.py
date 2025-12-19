import os
import json
import requests
from typing import Dict, List, Any, Optional, TypedDict, Annotated
from datetime import datetime
import operator
# from langchain_community.chat_models import ChatLiteLLM
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain.agents import create_react_agent
from langchain.agents.react.agent import ReActSingleInputOutputParser
from langchain_core.prompts import PromptTemplate
from yahooquery import search
from src.backend.db.mongodb import FMP_API_KEY
from src.ai.stock_prediction.stock_prediction_functions import get_rating_stock_price
from src.ai.stock_prediction.stock_prediction_functions import sarimax_predict
from src.ai.llm.model import get_llm
#from src.ai.llm.config import StockPredictionConfig
from src.ai.llm.config import  StockPredictionConfig

load_dotenv()
FMP_API_KEY = os.getenv("FM_API_KEY")

spc = StockPredictionConfig()

# Define the agent state
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    company_name: str
    ticker: str
    file_path: str
    prediction_results: Optional[Dict]
    error: Optional[str]
    step: str

# Define tools for the agent
# @tool
# def search_company_ticker(company_name: str) -> Dict[str, Any]:
#     """Search for a company's ticker symbol using the company name."""
#     try:
#         results = search(company_name)
#         quotes = results.get("quotes", [])
#         if not quotes:
#             return {"error": f"No ticker found for '{company_name}'", "ticker": None, "longname": None}
        
#         top_result = quotes[0]
#         ticker = top_result.get("symbol")
#         longname = top_result.get("longname", company_name)
        
#         return {
#             "ticker": ticker,
#             "longname": longname,
#             "success": True,
#             "message": f"Found ticker {ticker} for company {longname}"
#         }
#     except Exception as e:
#         return {"error": str(e), "ticker": None, "longname": None}

@tool
def search_company_ticker(company_name: str) -> Dict[str, Any]:
   """Search for a company's ticker symbol using the company name."""
   try:
       
       print(f"\n===Company name: {company_name}===\n")
       url = f"https://financialmodelingprep.com/stable/search-symbol?query={company_name}&apikey={FMP_API_KEY}"
       response = requests.get(url)
       data = response.json()
      
       if not data:
           return {
               "error": f"No ticker found for '{company_name}'",
               "ticker": None,
               "longname": None,
               "success": False
           }
      
       ticker = data[0].get("symbol", None)
       longname = data[0].get("name", company_name)
       
       print("\n===Inside search company ticker function===\n")
       print(f"Searching for ticker for company: {company_name}\n")
       print(f"\n===Ticker found: {ticker}, Longname: {longname}===\n")

       return {
           "ticker": ticker,
           "longname": longname,
           "success": True,
           "message": f"Found ticker {ticker} for company {longname}"
       }


   except Exception as e:
       return {
           "error": str(e),
           "ticker": None,
           "longname": None,
           "success": False
       }


@tool
def get_stock_data_and_rating(company_name: str, ticker: str) -> Dict[str, Any]:
    """Get stock data and sentiment rating for a company."""
    try:
        ticker_data = [{"company": company_name, "ticker": ticker}]
        file_path = get_rating_stock_price(ticker_data)
        
        if file_path:
            return {
                "success": True,
                "file_path": file_path,
                "message": f"Stock data saved to: {file_path}"
            }
        else:
            return {
                "error": "Failed to save stock data",
                "file_path": None
            }
    except Exception as e:
        return {"error": str(e), "file_path": None}

@tool
def run_sarimax_prediction(file_path: str, forecast_steps: int = 5) -> Dict[str, Any]:
    """Run SARIMAX prediction on the stock data."""
    try:
        results = sarimax_predict(file_path, forecast_steps=forecast_steps)
        return {
            "success": True,
            "results": results,
            "message": f"SARIMAX prediction completed with {forecast_steps} forecast steps"
        }
    except Exception as e:
        return {"error": str(e), "results": None}

# Create the agent class
class StockAnalysisAgent:
    # def __init__(self, model_name: str = "azure/gpt-4o-mini", temperature: float = 0):
    # def __init__(self, model_name: str = "gemini/gemini-2.5-pro", temperature: float = 0):
    #     self.llm = ChatLiteLLM(model=model_name, temperature=temperature)
    #     self.tools = [search_company_ticker, get_stock_data_and_rating, run_sarimax_prediction]
    #     self.graph = self._create_graph()
    def __init__(self):
        self.llm = get_llm(model_name=spc.MODEL, temperature=spc.TEMPERATURE)
        self.tools = [search_company_ticker, get_stock_data_and_rating, run_sarimax_prediction]
        self.graph = self._create_graph()
    
    def _create_graph(self):
        # Create the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("start", self.start_node)
        workflow.add_node("search_ticker", self.search_ticker_node)
        workflow.add_node("get_data", self.get_data_node)
        workflow.add_node("predict", self.predict_node)
        workflow.add_node("finish", self.finish_node)
        workflow.add_node("error_handler", self.error_handler_node)
        
        # Add edges
        workflow.add_edge(START, "start")
        workflow.add_conditional_edges(
            "start",
            self.should_continue_after_start,
            {
                "search": "search_ticker",
                "error": "error_handler"
            }
        )
        workflow.add_conditional_edges(
            "search_ticker",
            self.should_continue_after_search,
            {
                "get_data": "get_data",
                "error": "error_handler"
            }
        )
        workflow.add_conditional_edges(
            "get_data",
            self.should_continue_after_data,
            {
                "predict": "predict",
                "error": "error_handler"
            }
        )
        workflow.add_conditional_edges(
            "predict",
            self.should_continue_after_predict,
            {
                "finish": "finish",
                "error": "error_handler"
            }
        )
        workflow.add_edge("finish", END)
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()
    
    def start_node(self, state: AgentState) -> AgentState:
        """Initialize the analysis process."""
        messages = state.get("messages", [])
        
        # Extract company name from the last human message
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                company_name = last_message.content.strip()
            else:
                company_name = str(last_message).strip()
        else:
            company_name = state.get("company_name", "")
        
        if not company_name:
            return {
                **state,
                "error": "No company name provided",
                "step": "error",
                "messages": messages + [AIMessage(content="Error: No company name provided")]
            }
        
        return {
            **state,
            "company_name": company_name,
            "step": "search",
            "messages": messages + [AIMessage(content=f"Starting analysis for company: {company_name}")]
        }
    
    def search_ticker_node(self, state: AgentState) -> AgentState:
        """Search for company ticker."""
        company_name = state["company_name"]
        
        # Use the search tool
        result = search_company_ticker.invoke({"company_name": company_name})
        
        if result.get("success"):
            return {
                **state,
                "ticker": result["ticker"],
                "company_name": result["longname"],
                "step": "get_data",
                "messages": state["messages"] + [AIMessage(content=result["message"])]
            }
        else:
            return {
                **state,
                "error": result.get("error", "Failed to find ticker"),
                "step": "error",
                "messages": state["messages"] + [AIMessage(content=f"Error: {result.get('error')}")]
            }
    
    def get_data_node(self, state: AgentState) -> AgentState:
        """Get stock data and sentiment rating."""
        company_name = state["company_name"]
        ticker = state["ticker"]
        
        # Use the get stock data tool
        result = get_stock_data_and_rating.invoke({
            "company_name": company_name,
            "ticker": ticker
        })
        
        if result.get("success"):
            return {
                **state,
                "file_path": result["file_path"],
                "step": "predict",
                "messages": state["messages"] + [AIMessage(content=result["message"])]
            }
        else:
            return {
                **state,
                "error": result.get("error", "Failed to get stock data"),
                "step": "error",
                "messages": state["messages"] + [AIMessage(content=f"Error: {result.get('error')}")]
            }
    
    def predict_node(self, state: AgentState) -> AgentState:
        """Run SARIMAX prediction."""
        file_path = state["file_path"]
        
        # Use the prediction tool
        result = run_sarimax_prediction.invoke({
            "file_path": file_path,
            "forecast_steps": 5
        })
        
        if result.get("success"):
            return {
                **state,
                "prediction_results": result["results"],
                "step": "finish",
                "messages": state["messages"] + [AIMessage(content=result["message"])]
            }
        else:
            return {
                **state,
                "error": result.get("error", "Failed to run prediction"),
                "step": "error",
                "messages": state["messages"] + [AIMessage(content=f"Error: {result.get('error')}")]
            }
    
    def finish_node(self, state: AgentState) -> AgentState:
        """Finish the analysis and provide summary."""
        company_name = state["company_name"]
        ticker = state["ticker"]
        file_path = state["file_path"]
        
        summary = f"""
Stock Analysis Complete for {company_name} ({ticker})

✅ Company ticker found: {ticker}
✅ Stock data and sentiment rating retrieved
✅ Data saved to: {file_path}
✅ SARIMAX prediction completed with 5 forecast steps

The analysis workflow has been completed successfully. You can find the detailed results in the saved file and prediction output.
        """
        
        return {
            **state,
            "step": "completed",
            "messages": state["messages"] + [AIMessage(content=summary.strip())]
        }
    
    def error_handler_node(self, state: AgentState) -> AgentState:
        """Handle errors in the workflow."""
        error = state.get("error", "Unknown error occurred")
        
        error_message = f"""
❌ Stock Analysis Failed

Error: {error}

The analysis could not be completed. Please check the company name and try again.
        """
        
        return {
            **state,
            "step": "failed",
            "messages": state["messages"] + [AIMessage(content=error_message.strip())]
        }
    
    # Conditional edge functions
    def should_continue_after_start(self, state: AgentState) -> str:
        return "error" if state.get("error") else "search"
    
    def should_continue_after_search(self, state: AgentState) -> str:
        return "error" if state.get("error") else "get_data"
    
    def should_continue_after_data(self, state: AgentState) -> str:
        return "error" if state.get("error") else "predict"
    
    def should_continue_after_predict(self, state: AgentState) -> str:
        return "error" if state.get("error") else "finish"
    
    def analyze_stock(self, company_name: str) -> Dict[str, Any]:
        """Main method to analyze a stock."""
        initial_state = {
            "messages": [HumanMessage(content=company_name)],
            "company_name": "",
            "ticker": "",
            "file_path": "",
            "prediction_results": None,
            "error": None,
            "step": "start"
        }
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        return {
            "success": final_state["step"] == "completed",
            "company_name": final_state.get("company_name", ""),
            "ticker": final_state.get("ticker", ""),
            "file_path": final_state.get("file_path", ""),
            "prediction_results": final_state.get("prediction_results"),
            "error": final_state.get("error"),
            "messages": [msg.content if hasattr(msg, 'content') else str(msg) for msg in final_state["messages"]]
        }



    def analyze_stock_with_formatted_results(self, company_name: str) -> Dict[str, Any]:
            """
            Main method to analyze a stock and return formatted results for API.
            This method calls the existing analyze_stock method and formats the prediction results.
            """
            # Get the raw results from existing method
            result = self.analyze_stock(company_name)
            
            # Format prediction_results for API consumption
            if result.get("prediction_results") is not None:
                pred_results = result["prediction_results"]
                
                if isinstance(pred_results, tuple) and len(pred_results) >= 2:
                    forecast_data = pred_results[0]  # pandas Series
                    confidence_intervals = pred_results[1]  # pandas DataFrame
                    
                    # Convert to clean structured format
                    forecast_list = []
                    
                    # Handle pandas Series for forecast
                    if hasattr(forecast_data, 'index') and hasattr(forecast_data, 'values'):
                        for date, value in zip(forecast_data.index, forecast_data.values):
                            date_str = date.strftime('%Y-%m-%d') if hasattr(date, 'strftime') else str(date)
                            forecast_entry = {
                                "date": date_str,
                                "predicted_price": round(float(value), 2)
                            }
                            
                            # Add confidence intervals if available
                            if hasattr(confidence_intervals, 'loc'):
                                try:
                                    ci_row = confidence_intervals.loc[date]
                                    forecast_entry["confidence_interval"] = {
                                        "lower": round(float(ci_row.iloc[0]), 2),
                                        "upper": round(float(ci_row.iloc[1]), 2)
                                    }
                                except:
                                    pass
                            
                            forecast_list.append(forecast_entry)
                    
                    # Create structured prediction results
                    result["prediction_results"] = {
                        "forecast": forecast_list,
                        "summary": {
                            "total_predictions": len(forecast_list),
                            "forecast_period": f"{forecast_list[0]['date']} to {forecast_list[-1]['date']}" if forecast_list else None,
                            "average_predicted_price": round(sum(item["predicted_price"] for item in forecast_list) / len(forecast_list), 2) if forecast_list else None
                        }
                    }
                else:
                    # Fallback for other formats
                    result["prediction_results"] = {
                        "raw_data": str(pred_results),
                        "note": "Unable to parse prediction format"
                    }
            
            return result