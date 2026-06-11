from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = "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"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

def get_nse_session():
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(1)
    except:
        pass
    return session

def get_stock_data(symbol):
    session = get_nse_session()
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        res = session.get(url, timeout=15)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        pass
    return None

def get_financials(symbol):
    session = get_nse_session()
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}&section=financials"
        res = session.get(url, timeout=15)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

def groq_analyze(prompt):
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.3
        }
        res = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        data = res.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"AI Analysis error: {str(e)}"

def calc_dupont(net_income, revenue, total_assets, total_equity):
    try:
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
            "roe": round(roe, 2)
        }
    except:
        return None

def calc_altman(working_capital, retained_earnings, ebit, market_cap, revenue, total_assets, total_liabilities):
    try:
        if total_assets == 0:
            return None
        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x4 = market_cap / total_liabilities if total_liabilities > 0 else 1
        x5 = revenue / total_assets
        z = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
        if z > 2.99:
            zone, emoji = "Safe Zone", "🟢"
            interp = "நிறுவனம் financially strong — bankruptcy risk குறைவு"
        elif z > 1.81:
            zone, emoji = "Grey Zone", "🟡"
            interp = "நிறுவனம் moderate risk — monitor பண்ணவும்"
        else:
            zone, emoji = "Distress Zone", "🔴"
            interp = "நிறுவனம் high risk — கவனம் தேவை"
        return {
            "z_score": round(z, 2),
            "zone": zone,
            "zone_emoji": emoji,
            "interpretation": interp,
            "components": {
                "x1": round(x1, 3),
                "x2": round(x2, 3),
                "x3": round(x3, 3),
                "x4": round(x4, 3),
                "x5": round(x5, 3)
            }
        }
    except:
        return None

@app.route('/')
def home():
    return jsonify({
        'status': 'MITS 360 Fundamental Analysis API Live!',
        'usage': '/analyze?symbol=TCS'
    })

@app.route('/analyze')
def analyze():
    symbol = request.args.get('symbol', '').strip().upper()
    if not symbol:
        return jsonify({'error': 'No symbol provided'}), 400

    try:
        stock_data = get_stock_data(symbol)

        if not stock_data:
            # Fallback: use Groq AI with known data
            prompt = f"""You are an expert Indian stock market fundamental analyst with 20+ years experience.

Analyze NSE listed company: {symbol}

Provide a comprehensive analysis in Tanglish (Tamil+English mix) covering:

**1. Company Overview**
- Business model, sector, key products/services

**2. DuPont Analysis** (use your knowledge of latest annual report)
- Net Profit Margin, Asset Turnover, Equity Multiplier, ROE breakdown

**3. Altman Z-Score Analysis**
- Estimate Z-Score based on known financials
- Financial health assessment

**4. Management Quality**
- Capital allocation, promoter background, track record

**5. Auditor & Governance Issues**
- Auditor name, any qualifications, RPT concerns

**6. Order Book & Business Outlook**
- Latest order wins, revenue pipeline, growth drivers

**7. Red Flags**
- Any concerns: debt levels, margins, pledging, etc.

**8. Overall Verdict**
- Clear Buy/Hold/Avoid with target range

Use latest available data (FY2024-25). Be specific with numbers. Max 500 words."""

            ai_analysis = groq_analyze(prompt)

            return jsonify({
                'symbol': symbol,
                'company_name': symbol,
                'data_source': 'AI Analysis (NSE data temporarily unavailable)',
                'ai_analysis': ai_analysis,
                'dupont': None,
                'altman': None,
                'note': 'Live financial data unavailable. AI analysis based on latest known data.'
            })

        # Extract data from NSE response
        info = stock_data.get('info', {})
        metadata = stock_data.get('metadata', {})
        price_info = stock_data.get('priceInfo', {})
        industry_info = stock_data.get('industryInfo', {})

        company_name = metadata.get('companyName', symbol)
        sector = industry_info.get('sector', 'N/A')
        industry = industry_info.get('industry', 'N/A')
        current_price = price_info.get('lastPrice', 0)
        market_cap = info.get('marketCap', 0)
        pe_ratio = info.get('pdSectorPe', 0)
        pb_ratio = info.get('pdSectorPb', 0)

        # Build AI prompt with available data
        prompt = f"""You are an expert Indian stock market fundamental analyst with 20+ years experience.

Analyze NSE listed company: {company_name} ({symbol})
Sector: {sector} | Industry: {industry}
Current Price: ₹{current_price}
Market Cap: ₹{round(market_cap/1e7, 0) if market_cap else 'N/A'} Crores
PE Ratio: {pe_ratio}
PB Ratio: {pb_ratio}

Provide comprehensive analysis in Tanglish (Tamil+English mix):

**1. DuPont Analysis** (FY2024-25 latest data)
- Net Profit Margin %, Asset Turnover, Equity Multiplier, ROE %
- Compare with industry average

**2. Altman Z-Score**
- Calculate/estimate Z-Score
- {symbol} financial health zone (Safe/Grey/Distress)

**3. Management Quality**
- Promoter background, capital allocation quality
- ROE consistency over 3-5 years

**4. Auditor & Governance**
- Auditor firm name, any recent qualifications
- Related Party Transactions (RPT) — any concerns?
- Corporate governance rating

**5. Order Book & Business Outlook**
- Latest order wins (if applicable)
- Revenue growth trajectory
- Near-term catalysts

**6. Red Flags** (be honest)
- High debt, low margins, promoter pledge %, any issues

**7. Overall Verdict**
- Buy / Hold / Avoid
- 1-year target price range
- Key risks

Be specific with numbers from FY2024-25 annual report. Max 500 words."""

        ai_analysis = groq_analyze(prompt)

        return jsonify({
            'symbol': symbol,
            'company_name': company_name,
            'sector': sector,
            'industry': industry,
            'current_price': current_price,
            'market_cap_cr': round(market_cap/1e7, 0) if market_cap else 0,
            'pe_ratio': pe_ratio,
            'pb_ratio': pb_ratio,
            'data_source': 'NSE India + Groq AI',
            'ai_analysis': ai_analysis,
            'dupont': None,
            'altman': None
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
