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

def calc_dupont(info, financials, balance_sheet):
    try:
        # Net Profit Margin = Net Income / Revenue
        net_income = financials.loc['Net Income'].iloc[0] if 'Net Income' in financials.index else None
        revenue = financials.loc['Total Revenue'].iloc[0] if 'Total Revenue' in financials.index else None
        total_assets = balance_sheet.loc['Total Assets'].iloc[0] if 'Total Assets' in balance_sheet.index else None
        total_equity = balance_sheet.loc['Stockholders Equity'].iloc[0] if 'Stockholders Equity' in balance_sheet.index else None
        total_debt = balance_sheet.loc['Total Debt'].iloc[0] if 'Total Debt' in balance_sheet.index else 0

        if not all([net_income, revenue, total_assets, total_equity]):
            return None

        net_margin = (net_income / revenue) * 100
        asset_turnover = revenue / total_assets
        equity_multiplier = total_assets / total_equity
        roe = net_margin * asset_turnover * equity_multiplier / 100

        return {
            "net_profit_margin": round(float(net_margin), 2),
            "asset_turnover": round(float(asset_turnover), 2),
            "equity_multiplier": round(float(equity_multiplier), 2),
            "roe": round(float(roe * 100), 2),
            "net_income": round(float(net_income / 1e7), 2),
            "revenue": round(float(revenue / 1e7), 2),
            "total_assets": round(float(total_assets / 1e7), 2),
            "total_equity": round(float(total_equity / 1e7), 2)
        }
    except Exception as e:
        return None

def calc_altman(financials, balance_sheet, info):
    try:
        total_assets = float(balance_sheet.loc['Total Assets'].iloc[0])
        total_equity = float(balance_sheet.loc['Stockholders Equity'].iloc[0])
        total_liabilities = total_assets - total_equity
        retained_earnings = float(balance_sheet.loc['Retained Earnings'].iloc[0]) if 'Retained Earnings' in balance_sheet.index else total_equity * 0.5
        ebit = float(financials.loc['EBIT'].iloc[0]) if 'EBIT' in financials.index else float(financials.loc['Operating Income'].iloc[0])
        revenue = float(financials.loc['Total Revenue'].iloc[0])
        current_assets = float(balance_sheet.loc['Current Assets'].iloc[0]) if 'Current Assets' in balance_sheet.index else total_assets * 0.4
        current_liabilities = float(balance_sheet.loc['Current Liabilities'].iloc[0]) if 'Current Liabilities' in balance_sheet.index else total_liabilities * 0.4
        market_cap = float(info.get('marketCap', total_equity))

        working_capital = current_assets - current_liabilities

        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x4 = market_cap / total_liabilities if total_liabilities > 0 else 1
        x5 = revenue / total_assets

        z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5

        if z_score > 2.99:
            zone = "Safe Zone 🟢"
            interpretation = "நிறுவனம் financially strong — bankruptcy risk மிகவும் குறைவு"
        elif z_score > 1.81:
            zone = "Grey Zone 🟡"
            interpretation = "நிறுவனம் moderate risk-ல் இருக்கிறது — கவனமாக monitor பண்ணவும்"
        else:
            zone = "Distress Zone 🔴"
            interpretation = "நிறுவனம் high bankruptcy risk-ல் இருக்கிறது — கவனம் தேவை"

        return {
            "z_score": round(float(z_score), 2),
            "zone": zone,
            "interpretation": interpretation,
            "components": {
                "x1_working_capital": round(float(x1), 3),
                "x2_retained_earnings": round(float(x2), 3),
                "x3_ebit": round(float(x3), 3),
                "x4_market_equity": round(float(x4), 3),
                "x5_revenue": round(float(x5), 3)
            }
        }
    except Exception as e:
        return None

@app.route('/')
def home():
    return jsonify({'status': 'MITS 360 Fundamental Analysis API Live!'})

@app.route('/analyze')
def analyze():
    symbol = request.args.get('symbol', '').strip().upper()
    if not symbol:
        return jsonify({'error': 'No symbol provided'}), 400

    try:
        ticker = yf.Ticker(symbol + '.NS')
        info = ticker.info
        financials = ticker.financials
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow

        if financials.empty or balance_sheet.empty:
            return jsonify({'error': f'{symbol} data not available'}), 404

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

        # DuPont
        dupont = calc_dupont(info, financials, balance_sheet)

        # Altman Z-Score
        altman = calc_altman(financials, balance_sheet, info)

        # Groq AI Analysis
        financial_summary = f"""
Company: {company_name} ({symbol})
Sector: {sector} | Industry: {industry}
Market Cap: ₹{round(market_cap/1e7, 0) if market_cap else 'N/A'} Cr
Current Price: ₹{current_price}
PE Ratio: {pe_ratio}
PB Ratio: {pb_ratio}
Debt/Equity: {debt_to_equity}
ROE: {round(roe*100, 2) if roe else 'N/A'}%
ROA: {round(roa*100, 2) if roa else 'N/A'}%
DuPont ROE: {dupont['roe'] if dupont else 'N/A'}%
Altman Z-Score: {altman['z_score'] if altman else 'N/A'} ({altman['zone'] if altman else 'N/A'})
"""

        prompt = f"""You are an expert Indian stock market fundamental analyst with 20+ years experience.

Analyze this NSE listed company based on the financial data below:

{financial_summary}

Provide a comprehensive analysis in Tamil + English (Tanglish style) covering:

1. **Management Quality** (2-3 points):
   - Capital allocation quality
   - ROE consistency
   - Debt management

2. **Auditor & Governance Issues** (check for common red flags):
   - Auditor qualification concerns
   - Related Party Transactions (RPT) concerns
   - Corporate governance rating

3. **Order Book & Business Outlook** (2-3 points):
   - Recent order wins or business momentum
   - Revenue growth trend
   - Sector tailwinds/headwinds

4. **Red Flags** (list any concerns):
   - High debt, low margins, promoter pledge etc.

5. **Overall Verdict** (1 sentence):
   - Buy/Hold/Avoid with reason

Format with clear sections. Be specific and actionable. Max 400 words."""

        ai_analysis = groq_analyze(prompt)
        time.sleep(0.5)

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
            'dupont': dupont,
            'altman': altman,
            'ai_analysis': ai_analysis
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
