from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import requests
import time

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def groq_analyze(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama3-70b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
            "temperature": 0.3
        }
        res = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        data = res.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI Analysis error: {str(e)}"

def fetch_ticker_data(symbol):
    """Fetch with retry logic"""
    for attempt in range(3):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            if info and len(info) > 5:
                return ticker
        except Exception:
            pass
        time.sleep(2)
    return None

def calc_dupont(financials, balance_sheet):
    try:
        net_income = None
        revenue = None
        total_assets = None
        total_equity = None

        for key in ['Net Income', 'NetIncome', 'Net Income Common Stockholders']:
            if key in financials.index:
                net_income = float(financials.loc[key].iloc[0])
                break

        for key in ['Total Revenue', 'TotalRevenue', 'Revenue']:
            if key in financials.index:
                revenue = float(financials.loc[key].iloc[0])
                break

        for key in ['Total Assets', 'TotalAssets']:
            if key in balance_sheet.index:
                total_assets = float(balance_sheet.loc[key].iloc[0])
                break

        for key in ['Stockholders Equity', 'StockholdersEquity', 'Total Equity Gross Minority Interest', 'Common Stock Equity']:
            if key in balance_sheet.index:
                total_equity = float(balance_sheet.loc[key].iloc[0])
                break

        if not all([net_income, revenue, total_assets, total_equity]):
            return None

        net_margin = (net_income / revenue) * 100
        asset_turnover = revenue / total_assets
        equity_multiplier = total_assets / total_equity
        roe = (net_margin / 100) * asset_turnover * equity_multiplier * 100

        return {
            "net_profit_margin": round(net_margin, 2),
            "asset_turnover": round(asset_turnover, 3),
            "equity_multiplier": round(equity_multiplier, 2),
            "roe": round(roe, 2),
            "net_income_cr": round(net_income / 1e7, 2),
            "revenue_cr": round(revenue / 1e7, 2),
            "total_assets_cr": round(total_assets / 1e7, 2),
            "total_equity_cr": round(total_equity / 1e7, 2)
        }
    except Exception as e:
        return None

def calc_altman(financials, balance_sheet, info):
    try:
        total_assets = None
        total_equity = None
        retained_earnings = None
        ebit = None
        revenue = None
        current_assets = None
        current_liabilities = None

        for key in ['Total Assets']:
            if key in balance_sheet.index:
                total_assets = float(balance_sheet.loc[key].iloc[0])

        for key in ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest']:
            if key in balance_sheet.index:
                total_equity = float(balance_sheet.loc[key].iloc[0])
                break

        for key in ['Retained Earnings']:
            if key in balance_sheet.index:
                retained_earnings = float(balance_sheet.loc[key].iloc[0])
                break

        for key in ['EBIT', 'Operating Income', 'Ebit']:
            if key in financials.index:
                ebit = float(financials.loc[key].iloc[0])
                break

        for key in ['Total Revenue', 'Revenue']:
            if key in financials.index:
                revenue = float(financials.loc[key].iloc[0])
                break

        for key in ['Current Assets']:
            if key in balance_sheet.index:
                current_assets = float(balance_sheet.loc[key].iloc[0])
                break

        for key in ['Current Liabilities']:
            if key in balance_sheet.index:
                current_liabilities = float(balance_sheet.loc[key].iloc[0])
                break

        if not all([total_assets, total_equity, ebit, revenue]):
            return None

        total_liabilities = total_assets - total_equity
        if retained_earnings is None:
            retained_earnings = total_equity * 0.5
        if current_assets is None:
            current_assets = total_assets * 0.4
        if current_liabilities is None:
            current_liabilities = total_liabilities * 0.4

        market_cap = float(info.get('marketCap', total_equity))
        working_capital = current_assets - current_liabilities

        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x4 = market_cap / total_liabilities if total_liabilities > 0 else 1
        x5 = revenue / total_assets

        z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5

        if z_score > 2.99:
            zone = "Safe Zone"
            zone_emoji = "🟢"
            interpretation = "நிறுவனம் financially strong — bankruptcy risk மிகவும் குறைவு"
        elif z_score > 1.81:
            zone = "Grey Zone"
            zone_emoji = "🟡"
            interpretation = "நிறுவனம் moderate risk — கவனமாக monitor பண்ணவும்"
        else:
            zone = "Distress Zone"
            zone_emoji = "🔴"
            interpretation = "நிறுவனம் high risk — கவனம் தேவை"

        return {
            "z_score": round(z_score, 2),
            "zone": zone,
            "zone_emoji": zone_emoji,
            "interpretation": interpretation,
            "components": {
                "x1_working_capital": round(x1, 3),
                "x2_retained_earnings": round(x2, 3),
                "x3_ebit": round(x3, 3),
                "x4_market_equity": round(x4, 3),
                "x5_revenue": round(x5, 3)
            }
        }
    except Exception as e:
        return None

@app.route('/')
def home():
    return jsonify({
        'status': 'MITS 360 Fundamental Analysis API Live!',
        'endpoints': {
            '/analyze?symbol=TCS': 'Full fundamental analysis'
        }
    })

@app.route('/analyze')
def analyze():
    symbol = request.args.get('symbol', '').strip().upper()
    if not symbol:
        return jsonify({'error': 'No symbol provided'}), 400

    nse_symbol = symbol + '.NS'

    try:
        ticker = yf.Ticker(nse_symbol)
        time.sleep(1.5)

        info = ticker.info
        if not info or len(info) < 5:
            return jsonify({'error': f'{symbol} data not found. Check NSE symbol.'}), 404

        financials = ticker.financials
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow

        company_name = info.get('longName', symbol)
        sector = info.get('sector', 'N/A')
        industry = info.get('industry', 'N/A')
        market_cap = info.get('marketCap', 0)
        current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        pe_ratio = info.get('trailingPE', 0)
        pb_ratio = info.get('priceToBook', 0)
        debt_to_equity = info.get('debtToEquity', 0)
        roe = info.get('returnOnEquity', 0)
        roa = info.get('returnOnAssets', 0)
        profit_margins = info.get('profitMargins', 0)
        revenue_growth = info.get('revenueGrowth', 0)
        earnings_growth = info.get('earningsGrowth', 0)

        dupont = None
        altman = None

        if not financials.empty and not balance_sheet.empty:
            dupont = calc_dupont(financials, balance_sheet)
            altman = calc_altman(financials, balance_sheet, info)

        # Groq AI Analysis
        financial_summary = f"""
Company: {company_name} ({symbol})
Sector: {sector} | Industry: {industry}
Market Cap: ₹{round(market_cap/1e7, 0) if market_cap else 'N/A'} Crores
Current Price: ₹{current_price}
PE Ratio: {round(pe_ratio, 2) if pe_ratio else 'N/A'}
PB Ratio: {round(pb_ratio, 2) if pb_ratio else 'N/A'}
Debt/Equity: {round(debt_to_equity, 2) if debt_to_equity else 'N/A'}
ROE: {round(roe*100, 2) if roe else 'N/A'}%
ROA: {round(roa*100, 2) if roa else 'N/A'}%
Profit Margin: {round(profit_margins*100, 2) if profit_margins else 'N/A'}%
Revenue Growth: {round(revenue_growth*100, 2) if revenue_growth else 'N/A'}%
Earnings Growth: {round(earnings_growth*100, 2) if earnings_growth else 'N/A'}%
DuPont ROE: {dupont['roe'] if dupont else 'N/A'}%
Altman Z-Score: {altman['z_score'] if altman else 'N/A'} ({altman['zone'] if altman else 'N/A'})
"""

        prompt = f"""You are an expert Indian stock market fundamental analyst.

Analyze this NSE listed company:
{financial_summary}

Provide analysis in Tanglish (Tamil+English mix) with these sections:

**1. Management Quality**
- Capital allocation, ROE trend, debt management (2-3 points)

**2. Auditor & Governance**
- Common red flags for this sector, RPT concerns, governance rating

**3. Order Book & Business Outlook**
- Recent business momentum, revenue growth trend, sector outlook

**4. Red Flags** 
- Any concerns: high debt, low margins, promoter pledge, etc.

**5. Overall Verdict**
- One clear Buy/Hold/Avoid recommendation with reason

Be specific, actionable, max 350 words."""

        ai_analysis = groq_analyze(prompt)

        return jsonify({
            'symbol': symbol,
            'company_name': company_name,
            'sector': sector,
            'industry': industry,
            'market_cap_cr': round(market_cap/1e7, 0) if market_cap else 0,
            'current_price': current_price,
            'pe_ratio': round(pe_ratio, 2) if pe_ratio else 0,
            'pb_ratio': round(pb_ratio, 2) if pb_ratio else 0,
            'debt_to_equity': round(debt_to_equity, 2) if debt_to_equity else 0,
            'roe_pct': round(roe*100, 2) if roe else 0,
            'roa_pct': round(roa*100, 2) if roa else 0,
            'profit_margin_pct': round(profit_margins*100, 2) if profit_margins else 0,
            'revenue_growth_pct': round(revenue_growth*100, 2) if revenue_growth else 0,
            'dupont': dupont,
            'altman': altman,
            'ai_analysis': ai_analysis
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
