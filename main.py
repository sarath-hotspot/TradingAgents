import csv
from datetime import date, timedelta

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create a custom config
config = DEFAULT_CONFIG.copy()
config["deep_think_llm"] = "gpt-5.4-mini"  # Use a different model
config["quick_think_llm"] = "gpt-5.4-mini"  # Use a different model
config["max_debate_rounds"] = 1  # Increase debate rounds

# Configure data vendors (default uses yfinance, no extra API keys needed)
config["data_vendors"] = {
    "core_stock_apis": "alpha_vantage",           # Options: alpha_vantage, yfinance
    "technical_indicators": "alpha_vantage",      # Options: alpha_vantage, yfinance
    "fundamental_data": "alpha_vantage",          # Options: alpha_vantage, yfinance
    "news_data": "alpha_vantage",                 # Options: alpha_vantage, yfinance
}

# Initialize with custom config
ta = TradingAgentsGraph(debug=True, config=config)

# forward propagate
# _, decision = ta.propagate("AAPL", "2024-01-01")
# print(decision)

# Run AAPL daily analysis from Jan 1 to Jan 10, 2024
start_date = date(2024, 1, 2)
end_date = date(2024, 3, 31)
aapl_results = []

current = start_date
while current <= end_date:
    if current.weekday() < 5:  # skip weekends
        date_str = current.strftime("%Y-%m-%d")
        print(f"STARTING DAY={date_str} ANALYSIS")
        _, day_decision = ta.propagate("AAPL", date_str)
        aapl_results.append({"date": date_str, "decision": day_decision})
        print(f"{date_str}: {day_decision}")
        print(f"COMPLETED DAY={date_str} ANALYSIS\n")
    current += timedelta(days=1)

with open("aapl.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["date", "decision"])
    writer.writeheader()
    writer.writerows(aapl_results)

print("Decisions written to aapl.csv")

# Memorize mistakes and reflect
# ta.reflect_and_remember(1000) # parameter is the position returns
