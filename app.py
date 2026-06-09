import time
import pandas as pd
import streamlit as st
import requests
import statistics
from collections import defaultdict
import plotly.graph_objects as go

st.set_page_config(page_title="CMC 카테고리 분석", layout="wide")
st.title("🔥 CoinMarketCap - 카테고리별 24h 상승률 순위 + 미니 차트 (통합 시세 데이터)")

# ================== 🔑 API 키 설정 ==================
CMC_API_KEY = "8135c5b9fcb545f9b1bb7ded2dd77bc1"
CMC_HEADERS = {'Accepts': 'application/json', 'X-CMC_PRO_API_KEY': CMC_API_KEY}

CRYPTOCOMPARE_API_KEY = "431d2e36e0cb590d88f14b8fc1a8167a3f235b64e6ece20cd5ab7de050aa232c"

# ================== 📊 Plotly 차트 생성 함수 ==================
def create_usd_chart(df30):
    if df30 is None or len(df30) < 10: return None
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df30['date'], open=df30['open'], high=df30['high'],
                                 low=df30['low'], close=df30['close'],
                                 increasing_line_color='lime', decreasing_line_color='red'))
    colors = ['orange', 'limegreen', 'turquoise', 'lightblue', 'hotpink']
    periods = [50, 100, 150, 200, 365]
    for color, period in zip(colors, periods):
        if f'SMA{period}' in df30.columns:
            fig.add_trace(go.Scatter(x=df30['date'], y=df30[f'SMA{period}'],
                                   line=dict(color=color, width=2 if period == 365 else 1.2)))
    fig.update_layout(height=160, width=220, margin=dict(l=0,r=0,t=0,b=0),
                      plot_bgcolor='black', paper_bgcolor='black',
                      xaxis=dict(visible=False), yaxis=dict(type='log', visible=False), 
                      showlegend=False)
    return fig

def create_relative_candle(df_base, df_compare, title=""):
    if df_base is None or df_compare is None or len(df_base) < 30 or len(df_compare) < 30: return None
    
    merged = pd.merge(
        df_base[['date', 'open', 'high', 'low', 'close']], 
        df_compare[['date', 'open', 'high', 'low', 'close']], 
        on='date', suffixes=('_base', '_compare'), how='inner'
    )
    
    if len(merged) < 20: return None
    
    merged['open']  = merged['open_base']  / merged['open_compare']
    merged['high']  = merged['high_base']  / merged['high_compare']
    merged['low']   = merged['low_base']   / merged['low_compare']
    merged['close'] = merged['close_base'] / merged['close_compare']
    
    for p in [50, 100, 150, 200, 365]:
        merged[f'SMA{p}'] = merged['close'].rolling(p).mean()
    
    df30 = merged.tail(30).copy()
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df30['date'], open=df30['open'], high=df30['high'], low=df30['low'], close=df30['close'],
        increasing_line_color='lime', decreasing_line_color='red'
    ))
    
    colors = ['orange', 'limegreen', 'turquoise', 'lightblue', 'hotpink']
    periods = [50, 100, 150, 200, 365]
    for color, period in zip(colors, periods):
        fig.add_trace(go.Scatter(x=df30['date'], y=df30[f'SMA{period}'],
                               line=dict(color=color, width=2 if period == 365 else 1.2)))
    
    fig.update_layout(height=160, width=220, margin=dict(l=0,r=0,t=0,b=0),
                      plot_bgcolor='black', paper_bgcolor='black',
                      xaxis=dict(visible=False), yaxis=dict(type='log', visible=False),
                      showlegend=False, title=dict(text=title, font=dict(size=10)))
    return fig

# ================== 📉 차트 데이터 전담: CryptoCompare API ==================
@st.cache_data(ttl=600)
def fetch_futures_ohlcv(symbol):
    try:
        url = "https://min-api.cryptocompare.com/data/v2/histoday"
        params = {"fsym": symbol.upper(), "tsym": "USD", "limit": 400}
        if CRYPTOCOMPARE_API_KEY and CRYPTOCOMPARE_API_KEY != "YOUR_CRYPTOCOMPARE_API_KEY_HERE":
            params["api_key"] = CRYPTOCOMPARE_API_KEY

        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        
        if data.get("Response") == "Success" and data.get("Data", {}).get("Data"):
            raw_candles = data["Data"]["Data"]
            df = pd.DataFrame(raw_candles)
            if not df.empty and 'close' in df.columns:
                df['date'] = pd.to_datetime(df['time'], unit='s')
                df = df.rename(columns={'volumeto': 'volume'}) 
                for p in [50, 100, 150, 200, 365]:
                    df[f'SMA{p}'] = df['close'].rolling(p).mean()
                return df, 'cc'
    except Exception:
        pass

    try:
        import yfinance as yf
        ticker_symbol = f"{symbol.upper()}-USD"
        ticker = yf.Ticker(ticker_symbol)
        df_raw = ticker.history(period="400d", interval="1d")
        
        if not df_raw.empty:
            df = df_raw.reset_index()
            df = df.rename(columns={
                'Date': 'date', 'Open': 'open', 'High': 'high', 
                'Low': 'low', 'Close': 'close', 'Volume': 'volume'
            })
            df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
            for p in [50, 100, 150, 200, 365]:
                df[f'SMA{p}'] = df['close'].rolling(p).mean()
            return df, 'yf'
    except Exception:
        pass

    return None, None

def fetch_specific_source(symbol, source):
    try:
        if source == 'cc':
            url = "https://min-api.cryptocompare.com/data/v2/histoday"
            params = {"fsym": symbol.upper(), "tsym": "USD", "limit": 400}
            if CRYPTOCOMPARE_API_KEY and CRYPTOCOMPARE_API_KEY != "YOUR_CRYPTOCOMPARE_API_KEY_HERE":
                params["api_key"] = CRYPTOCOMPARE_API_KEY
            resp = requests.get(url, params=params, timeout=10).json()
            if resp.get("Response") == "Success" and resp.get("Data", {}).get("Data"):
                df = pd.DataFrame(resp["Data"]["Data"])
                df['date'] = pd.to_datetime(df['time'], unit='s')
                df = df.rename(columns={'volumeto': 'volume'})
                for p in [50, 100, 150, 200, 365]: df[f'SMA{p}'] = df['close'].rolling(p).mean()
                return df
        elif source == 'yf':
            import yfinance as yf
            df_raw = yf.Ticker(f"{symbol.upper()}-USD").history(period="400d", interval="1d")
            if not df_raw.empty:
                df = df_raw.reset_index().rename(columns={'Date': 'date', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
                df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
                for p in [50, 100, 150, 200, 365]: df[f'SMA{p}'] = df['close'].rolling(p).mean()
                return df
    except Exception:
        pass
    return None


def render_mini_charts(symbol, key_suffix):
    try:
        with st.spinner(f"{symbol} 차트 불러오는 중..."):
            df, source = fetch_futures_ohlcv(symbol)
            
            if df is not None:
                df_eth = fetch_specific_source("ETH", source)
                df_btc = fetch_specific_source("BTC", source)
                
                df30 = df.tail(30).copy()
                c1, c2, c3 = st.columns(3)
                with c1: 
                    st.plotly_chart(create_usd_chart(df30), use_container_width=True, key=f"usd_{key_suffix}_{symbol}")
                with c2: 
                    if df_eth is not None:
                        st.plotly_chart(create_relative_candle(df, df_eth, "ETH Relative"), use_container_width=True, key=f"eth_{key_suffix}_{symbol}")
                    else:
                        st.caption("ETH 백업 데이터 부족")
                with c3:
                    if df_btc is not None:
                        st.plotly_chart(create_relative_candle(df, df_btc, "BTC Relative"), use_container_width=True, key=f"btc_{key_suffix}_{symbol}")
                    else:
                        st.caption("BTC 백업 데이터 부족")
            else:
                st.warning(f"데이터 소스에서 {symbol}의 일봉 데이터를 찾을 수 없습니다.")
    except Exception as e:
        st.error(f"차트 불러오기 실패: {e}")

# ================== Session State 초기화 ==================
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
    st.session_state.df_result = None
    st.session_state.coin_details = None
    st.session_state.df_top_risers = None
    st.session_state.df_top_fallers = None
    st.session_state.df_all = None
    st.session_state.selected_symbol = None  
    st.session_state.chart_source = None     
    st.session_state.error_msg = None

# ================== 필터 영역 ==================
filter_col1, filter_col2 = st.columns([3, 5])

with filter_col1:
    st.subheader("🔍분석 필터")
    col_a, col_b = st.columns(2)
    with col_a:
        min_market_cap_input = st.text_input("최소 시가총액 (USD)", value="10,000,000")
        min_market_cap = int(min_market_cap_input.replace(",", "").strip() or 0)
    
    with col_b:
        top_n = st.slider("분석할 Top 코인 수", min_value=100, max_value=1000, value=500, step=100)

    col_c, col_d = st.columns(2)
    with col_c:
        use_median = st.checkbox("중앙값(Median) 사용", value=True)
    with col_d:
        min_coins_per_category = st.number_input("카테고리당 최소 코인 수", min_value=3, value=5)

    if st.button("🚀분석 실행", type="primary", use_container_width=True):
        st.session_state.analysis_done = True
        st.session_state.selected_symbol = None 
        st.session_state.df_result = None

# ================== 종목 검색 영역 ==================
with filter_col2:
    st.subheader("🔎 종목 검색")
    search_term = st.text_input("종목명 또는 심볼 검색", placeholder="BTC 또는 Bitcoin", key="search_input")

    if 'df_all' in st.session_state and st.session_state.df_all is not None and search_term:
        df_search = st.session_state.df_all.copy()
        search_term = search_term.strip().upper()
        if search_term:
            mask = (
                df_search['종목명'].str.upper().str.contains(search_term, na=False) |
                df_search['심볼'].str.upper().str.contains(search_term, na=False)
            )
            df_search = df_search[mask]
            if not df_search.empty:
                st.subheader(f"🔍 검색 결과: {len(df_search)}개")
                
                display_cols = ['종목명', '심볼', '주요_카테고리', '24h_상승률', '시가총액']
                st.dataframe(
                    df_search[display_cols].style.format({
                        '24h_상승률': "{:.2f}%", '시가총액': "{:,.0f}"
                    }).background_gradient(cmap='RdYlGn', subset=['24h_상승률']),
                    use_container_width=True,
                    height=min(300, len(df_search)*40 + 50),
                    hide_index=True
                )

                st.markdown("**📊 차트 보기**")
                btn_cols = st.columns(8)
                for idx, row in df_search.reset_index().iterrows():
                    symbol = row['심볼']
                    with btn_cols[idx % 8]:
                        # [수정] key에 idx 추가 → 중복 심볼이어도 고유 키 보장
                        if st.button(f"{symbol}", key=f"search_btn_{symbol}_{idx}", use_container_width=True):
                            st.session_state.selected_symbol = symbol
                            st.session_state.chart_source = 'search'
                            st.rerun()

                if st.session_state.selected_symbol and st.session_state.chart_source == 'search':
                    st.success(f"**📊 {st.session_state.selected_symbol} 미니 차트 (검색 결과)**")
                    render_mini_charts(st.session_state.selected_symbol, "search")
            else:
                st.warning("검색 결과가 없습니다.")

# ================== 🪙 시장 분석 전담: CoinMarketCap API ==================
if st.session_state.get('analysis_done') and st.session_state.df_result is None:
    with st.spinner("데이터 분석 중..."):
        try:
            start_time = time.time()
            
            @st.cache_data(ttl=180)
            def get_top_coins(top_n_val=500):
                url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
                params = {'limit': top_n_val, 'convert': 'USD', 'sort': 'market_cap'}
                resp = requests.get(url, headers=CMC_HEADERS, params=params, timeout=15)
                resp.raise_for_status()
                return pd.DataFrame(resp.json()['data'])

            df_coins = get_top_coins(top_n)

            btc_change_1h = btc_change_24h = eth_change_1h = eth_change_24h = 0
            for coin in df_coins.to_dict('records'):
                symbol = coin.get('symbol')
                q = coin.get('quote', {}).get('USD', {})
                if symbol == 'BTC':
                    btc_change_1h = q.get('percent_change_1h') or 0
                    btc_change_24h = q.get('percent_change_24h') or 0
                elif symbol == 'ETH':
                    eth_change_1h = q.get('percent_change_1h') or 0
                    eth_change_24h = q.get('percent_change_24h') or 0

            category_data = defaultdict(list)
            category_1h = defaultdict(list)
            coin_details = defaultdict(list)
            top_coins_list = []

            for coin in df_coins.to_dict('records'):
                try:
                    quote = coin.get('quote', {}).get('USD', {})
                    market_cap = quote.get('market_cap') or 0
                    change_24h = quote.get('percent_change_24h')
                    change_1h = quote.get('percent_change_1h')
                    volume_24h = quote.get('volume_24h') or 0

                    if market_cap < min_market_cap or change_24h is None:
                        continue

                    categories = coin.get('categories') or coin.get('tags') or []
                    cat_list = [cat if isinstance(cat, str) else (cat.get('name') or cat.get('slug')) 
                               for cat in categories if isinstance(cat, (str, dict))]
                    cat_list = [c for c in cat_list if c]

                    categories_str = ", ".join(cat_list[:3]) or "-"

                    rel_btc_1h = round(float(change_1h) - btc_change_1h, 2) if change_1h is not None else None
                    rel_btc_24h = round(float(change_24h) - btc_change_24h, 2)
                    rel_eth_1h = round(float(change_1h) - eth_change_1h, 2) if change_1h is not None else None
                    rel_eth_24h = round(float(change_24h) - eth_change_24h, 2)

                    coin_info = {
                        '종목명': coin.get('name', 'Unknown'),
                        '심볼': coin.get('symbol', 'N/A'),
                        '주요_카테고리': categories_str,
                        '1h_상승률': round(float(change_1h), 2) if change_1h is not None else None,
                        '24h_상승률': round(float(change_24h), 2),
                        '/btc_1h': rel_btc_1h, '/btc_24h': rel_btc_24h,
                        '/eth_1h': rel_eth_1h, '/eth_24h': rel_eth_24h,
                        '시가총액': int(market_cap), '24h_거래량': int(volume_24h),
                        '현재가격': quote.get('price', 0)
                    }

                    top_coins_list.append(coin_info)

                    for cat_name in cat_list:
                        category_data[cat_name].append(float(change_24h))
                        if change_1h is not None:
                            category_1h[cat_name].append(float(change_1h))
                        coin_details[cat_name].append(coin_info)
                except Exception:
                    continue

            results = []
            for cat in category_data.keys():
                changes_24h = category_data[cat]
                changes_1h = category_1h.get(cat, [])
                if len(changes_24h) >= min_coins_per_category:
                    avg_24h = statistics.median(changes_24h) if use_median else statistics.mean(changes_24h)
                    avg_1h = statistics.median(changes_1h) if changes_1h else None
                    results.append({
                        'Category': cat,
                        'Avg_1h_Change_%': round(avg_1h, 2) if avg_1h is not None else None,
                        'Avg_24h_Change_%': round(avg_24h, 2),
                        'Coin_Count': len(changes_24h)
                    })

            st.session_state.df_result = pd.DataFrame(results).reset_index(drop=True)
            st.session_state.coin_details = coin_details
            
            # [수정] df_all 생성 시 중복 심볼 제거
            st.session_state.df_all = pd.DataFrame(top_coins_list).drop_duplicates(subset=['심볼']).reset_index(drop=True)
            
            if not st.session_state.df_all.empty:
                # [수정] risers에도 drop_duplicates 추가
                st.session_state.df_top_risers = (
                    st.session_state.df_all
                    .sort_values(by='24h_상승률', ascending=False)
                    .drop_duplicates(subset=['심볼'])
                    .head(30)
                    .reset_index(drop=True)
                )
                
                # [수정] fallers에도 drop_duplicates 추가
                st.session_state.df_top_fallers = (
                    st.session_state.df_all
                    .sort_values(by='24h_상승률', ascending=True)
                    .drop_duplicates(subset=['심볼'])
                    .head(30)
                    .reset_index(drop=True)
                )
            
            st.session_state.elapsed = time.time() - start_time
            st.success(f"✅ 분석 완료! ({st.session_state.elapsed:.1f}초)")

        except Exception as e:
            st.session_state.error_msg = str(e)
            st.error(f"❌ 오류: {str(e)}")

# ================== 메인 화면 레이아웃 ==================
if st.session_state.analysis_done and st.session_state.df_result is not None:
    left_col, right_col = st.columns([1, 1])

    with left_col:
        df_result = st.session_state.df_result
        coin_details = st.session_state.coin_details

        st.subheader("📋 전체 카테고리 순위")
        st.dataframe(
            df_result.style.background_gradient(cmap='RdYlGn', subset=['Avg_24h_Change_%'])
                          .format({'Avg_1h_Change_%': "{:.2f}%", 'Avg_24h_Change_%': "{:.2f}%"}, na_rep="-"),
            use_container_width=True, height=400
        )

        st.subheader("📊 카테고리별 1h 상승률 순위")
        selected_category_1h = st.selectbox(
            "1h 상승률 기준 - 상세 카테고리 선택",
            options=df_result.sort_values(by='Avg_1h_Change_%', ascending=False)['Category'].tolist() if not df_result.empty else [],
            key="category_selector_1h"
        )
        details_1h = coin_details.get(selected_category_1h, [])
        if details_1h:
            st.dataframe(
                pd.DataFrame(details_1h)[['종목명', '심볼', '주요_카테고리', '1h_상승률', '24h_상승률', '시가총액']]
                .style.format({'1h_상승률': "{:.2f}%", '24h_상승률': "{:.2f}%", '시가총액': "{:,.0f}"}, na_rep="-")
                .background_gradient(cmap='RdYlGn', subset=['1h_상승률']),
                use_container_width=True, height=400
            )

        st.subheader("📊 카테고리별 24h 상승률 순위")
        selected_category_24h = st.selectbox(
            "24h 상승률 기준 - 상세 카테고리 선택",
            options=df_result.sort_values(by='Avg_24h_Change_%', ascending=False)['Category'].tolist() if not df_result.empty else [],
            key="category_selector_24h"
        )
        details_24h = coin_details.get(selected_category_24h, [])
        if details_24h:
            st.dataframe(
                pd.DataFrame(details_24h)[['종목명', '심볼', '주요_카테고리', '1h_상승률', '24h_상승률', '시가총액']]
                .style.format({'1h_상승률': "{:.2f}%", '24h_상승률': "{:.2f}%", '시가총액': "{:,.0f}"}, na_rep="-")
                .background_gradient(cmap='RdYlGn', subset=['24h_상승률']),
                use_container_width=True, height=400
            )

    with right_col:
        # ---- 상승률 Top 30 ----
        st.subheader("🚀 24h 상승률 Top 30")
        df_risers = st.session_state.df_top_risers
        
        # 숫자 포맷팅 함수 (1k, 1M, 1B)
        def format_large_number(val):
            if pd.isna(val) or val == 0:
                return "-"
            try:
                val = float(val)
                if val >= 1_000_000_000:
                    return f"{val / 1_000_000_000:.1f}B"
                elif val >= 1_000_000:
                    return f"{val / 1_000_000:.1f}M"
                elif val >= 1_000:
                    return f"{val / 1_000:.1f}k"
                else:
                    return f"{val:,.0f}"
            except:
                return str(val)
        
        if not df_risers.empty:
            # [수정] 표시할 컬럼 변경
            display_cols = ['종목명', '심볼', '주요_카테고리', '1h_상승률', '24h_상승률', '시가총액', '24h_거래량']
            
            st.dataframe(
                df_risers[display_cols].style.format({
                    '1h_상승률': "{:.2f}%", 
                    '24h_상승률': "{:.2f}%",
                    '시가총액': format_large_number,
                    '24h_거래량': format_large_number
                }, na_rep="-")
                .background_gradient(cmap='RdYlGn', subset=['24h_상승률']),
                use_container_width=True, 
                height=400, 
                hide_index=True
            )
            
            st.markdown("**종목 클릭 → 아래에서 차트 확인**")
            cols = st.columns(10)
            for idx, row in df_risers.iterrows():
                symbol = row['심볼']
                with cols[idx % 10]:
                    if st.button(symbol, key=f"rise_{symbol}_{idx}", use_container_width=True):
                        st.session_state.selected_symbol = symbol
                        st.session_state.chart_source = 'riser'
                        st.rerun()

        st.write("---")

        # ---- 하락률 Top 30 ----
        st.subheader("📉 24h 하락률 Top 30")
        df_fallers = st.session_state.get('df_top_fallers', pd.DataFrame())
        if not df_fallers.empty:
            display_cols = ['종목명', '심볼', '주요_카테고리', '1h_상승률', '24h_상승률', '/btc_1h', '/btc_24h', '/eth_1h', '/eth_24h']
            st.dataframe(
                df_fallers[display_cols].style.format({
                    '1h_상승률': "{:.2f}%", '24h_상승률': "{:.2f}%",
                    '/btc_1h': "{:.2f}%", '/btc_24h': "{:.2f}%", '/eth_1h': "{:.2f}%", '/eth_24h': "{:.2f}%"
                }, na_rep="-").background_gradient(cmap='coolwarm_r', subset=['24h_상승률']),
                use_container_width=True, height=400, hide_index=True
            )
            
            st.markdown("**종목 클릭 → 아래에서 차트 확인**")
            cols = st.columns(10)
            for idx, row in df_fallers.iterrows():
                symbol = row['심볼']
                with cols[idx % 10]:
                    # [수정] key에 idx 추가
                    if st.button(symbol, key=f"fall_{symbol}_{idx}", use_container_width=True):
                        st.session_state.selected_symbol = symbol
                        st.session_state.chart_source = 'faller'
                        st.rerun()

        if st.session_state.selected_symbol and st.session_state.chart_source == 'faller':
            st.success(f"**📊 {st.session_state.selected_symbol} 미니 차트 (하락 Top 30)**")
            render_mini_charts(st.session_state.selected_symbol, "faller")

else:
    st.info("👆 **분석 실행** 버튼을 눌러주세요.")

st.caption("Data Source: Market Cap Analysis by CoinMarketCap | Charting by CryptoCompare")
