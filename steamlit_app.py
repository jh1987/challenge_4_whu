import streamlit as st
import requests
import os
import openai

# Load environment variables from .env file
os.environ['ALPHAVANTAGE_API_KEY'] = st.secrets("ALPHAVANTAGE_API_KEY")
os.environ['OPENAI_API_KEY'] = st.secrets('OPENAI_API_KEY')
openai.api_key = st.secrets('OPENAI_API_KEY')

# Function to use GPT to classify the input as a company name or ticker symbol
def classify_input(input_text):
    """
    Uses GPT to determine if the input is a ticker symbol or company name.
    """
    prompt = f"""
    I am working on stock analysis. The user entered the following: "{input_text}".
    Please determine if this is:
    1. A ticker symbol (e.g., AAPL).
    2. A company name (e.g., Apple Inc.).
    If possible, provide the classification as either 'ticker' or 'company' by only stating these words. 
    Also, provide the best guess for the company name or ticker symbol in the format: 'classification: value'.
    """
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": "You are an intelligent assistant."},
                  {"role": "user", "content": prompt}],
        temperature=0
    )
    content = response.choices[0].message.content.strip().lower()
    if "ticker" in content:
        classification = "ticker"
        value = content.split("ticker:")[1].strip()
    elif "company" in content:
        classification = "company"
        value = content.split("company:")[1].strip()
    else:
        classification = "unknown"
        value = input_text
    return classification, value

# Function to fetch the ticker symbol based on a company name
def get_ticker_symbol(company_name):
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    base_url = "https://www.alphavantage.co/query"
    params = {
        "function": "SYMBOL_SEARCH",
        "keywords": company_name,
        "apikey": api_key
    }
    response = requests.get(base_url, params=params)

    if response.status_code == 200:
        data = response.json()
        if "bestMatches" in data and data["bestMatches"]:
            # Filter matches to prioritize US-based stocks with currency USD
            matches = data["bestMatches"]
            preferred_match = None

            for match in matches:
                if match["4. region"] == "United States" and match["8. currency"] == "USD":
                    preferred_match = match
                    break  # Take the first match that meets the criteria
            
            # If a preferred match is found, return it
            if preferred_match:
                symbol = preferred_match["1. symbol"]
                name = preferred_match["2. name"]
                return symbol, name
            
            # If no preferred match is found, fallback to the top result
            top_match = matches[0]
            return top_match["1. symbol"], top_match["2. name"]
        else:
            return None, "No matches found for the company name."
    else:
        return None, "Failed to fetch data from AlphaVantage API."

# Function to fetch stock price using AlphaVantage API
def get_stock_price(ticker):
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    intraday_base_url = "https://www.alphavantage.co/query"
    daily_base_url = "https://www.alphavantage.co/query"

    # Try to fetch intraday stock price first
    intraday_params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": ticker,
        "interval": "1min",
        "outputsize": "compact",
        "apikey": api_key
    }
    intraday_response = requests.get(intraday_base_url, params=intraday_params)

    if intraday_response.status_code == 200:
        intraday_data = intraday_response.json()
        try:
            # Get the most recent intraday stock price
            last_refreshed = intraday_data["Meta Data"]["3. Last Refreshed"]
            stock_price = intraday_data["Time Series (1min)"][last_refreshed]["1. open"]
            return f"The current real-time stock price for {ticker.upper()} is ${stock_price} (last refreshed: {last_refreshed})."
        except KeyError:
            # Fall back to daily price if intraday data is unavailable
            return get_daily_stock_price(ticker)
    else:
        # Fall back to daily price if intraday request fails
        return get_daily_stock_price(ticker)


def get_daily_stock_price(ticker):
    """
    Fetch daily stock price data as a fallback.
    """
    api_key = os.getenv("ALPHAVANTAGE_API_KEY")
    daily_base_url = "https://www.alphavantage.co/query"
    daily_params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": "compact",
        "apikey": api_key
    }
    daily_response = requests.get(daily_base_url, params=daily_params)

    if daily_response.status_code == 200:
        daily_data = daily_response.json()
        print(daily_data)
        try:
            # Get the most recent daily stock price
            last_refreshed = daily_data["Meta Data"]["3. Last Refreshed"]
            stock_price = daily_data["Time Series (Daily)"][last_refreshed]["1. open"]
            return f"Real-time price data is unavailable. The most recent daily stock price for {ticker.upper()} is ${stock_price} (date: {last_refreshed})."
        except KeyError:
            return "Could not retrieve daily stock price. Please check the ticker symbol and try again."
    else:
        return "Failed to fetch data from AlphaVantage API."
    
# Initialize chatbot with Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("Smart Stock Price Checker")
st.write("Enter the name of a publicly listed company or its ticker symbol to get the current stock price.")

# Create a form for user input
with st.form(key="stock_form", clear_on_submit=True):
    user_input = st.text_input("Enter company name or ticker symbol (e.g., Apple or AAPL):")
    submit_button = st.form_submit_button(label="Submit")

if submit_button and user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Classify the input using GPT
    classification, value = classify_input(user_input)
    print(classification, value)
    if classification == "ticker":
        bot_response = get_stock_price(value)
    elif classification == "company":
        # Search for ticker based on company name
        symbol, name = get_ticker_symbol(value)
        if symbol:
            stock_price_response = get_stock_price(symbol)
            bot_response = f"Found ticker symbol: {symbol} for {name}.\n\n{stock_price_response}"
        else:
            bot_response = name  # Error message from get_ticker_symbol
    else:
        bot_response = "I'm not sure if this is a company name or a ticker symbol. Please try again."

    # Add bot response to chat history
    st.session_state.messages.append({"role": "assistant", "content": bot_response})

# Display chat history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    elif msg["role"] == "assistant":
        st.markdown(f"**Bot:** {msg['content']}")