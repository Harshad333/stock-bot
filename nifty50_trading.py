"""
NIFTY 50 Index Trading System
=============================
A focused trading system for NIFTY 50 spot/index trading.
Uses technical analysis (EMA, RSI, ATR) for trade signals.
NO option chain trading - pure NIFTY 50 index analysis.
"""

from datetime import datetime, timedelta
import pandas as pd
import pyotp
from SmartApi import SmartConnect
import time


class Nifty50Trader:
    """NIFTY 50 Index Trading System - No Option Chain"""
    
    def __init__(self):
        # Angel One Credentials
        self.API_KEY = "ai8msNWE"
        self.CLIENT_ID = "A195789"
        self.MPIN = "9001"
        self.TOTP_SECRET = "3RLD7L6DTGGYNJ473BY7LJPIIU"
        
        self.client = None
        self.session_generated = False
        self.connect()
    
    # =========================================================================
    # CONNECTION METHODS
    # =========================================================================
    
    def connect(self):
        """Connect to Angel One"""
        try:
            obj = SmartConnect(api_key=self.API_KEY)
            totp = pyotp.TOTP(self.TOTP_SECRET).now()
            data = obj.generateSession(self.CLIENT_ID, self.MPIN, totp)
            
            if data and data.get('status'):
                self.client = obj
                self.session_generated = True
                print("[✓] Angel One connected for NIFTY 50 Trading!")
            else:
                print(f"[✗] Login failed")
        except Exception as e:
            print(f"[✗] Connection failed: {e}")
    
    # =========================================================================
    # NIFTY 50 DATA METHODS
    # =========================================================================
    
    def get_nifty50_ltp(self):
        """Get current NIFTY 50 LTP (Last Traded Price)"""
        if not self.session_generated:
            return None
        
        try:
            response = self.client.ltpData("NSE", "NIFTY 50", "99926000")
            if response and response.get('data') and response['data'].get('ltp'):
                return float(response['data']['ltp'])
        except Exception as e:
            print(f"[✗] LTP fetch failed: {e}")
        return None
    
    def get_nifty50_market_data(self):
        """Get comprehensive NIFTY 50 market data"""
        if not self.session_generated:
            return None
        
        try:
            response = self.client.ltpData("NSE", "NIFTY 50", "99926000")
            
            if response and response.get('data'):
                data = response['data']
                ltp = float(data.get('ltp', 0))
                open_price = float(data.get('open', ltp))
                high_price = float(data.get('high', ltp))
                low_price = float(data.get('low', ltp))
                
                return {
                    'ltp': ltp,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'range': high_price - low_price,
                    'change': ltp - open_price,
                    'change_percent': ((ltp - open_price) / open_price) * 100 if open_price > 0 else 0,
                    'trend': 'BULLISH' if ltp > open_price else 'BEARISH' if ltp < open_price else 'SIDEWAYS'
                }
        except Exception as e:
            print(f"[✗] Market data fetch failed: {e}")
        return None
    
    def get_candle_data(self, interval="FIFTEEN_MINUTE", days=5):
        """Fetch historical candle data for NIFTY 50"""
        try:
            from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
            to_date = datetime.now().strftime('%Y-%m-%d %H:%M')
            
            data = self.client.getCandleData({
                "exchange": "NSE",
                "symboltoken": "99926000",
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            })
            
            if data and data.get('data'):
                df = pd.DataFrame(data['data'], columns=['date', 'open', 'high', 'low', 'close', 'volume'])
                df['date'] = pd.to_datetime(df['date'])
                df['close'] = df['close'].astype(float)
                df['high'] = df['high'].astype(float)
                df['low'] = df['low'].astype(float)
                df['open'] = df['open'].astype(float)
                return df
            return None
        except Exception as e:
            print(f"[✗] Candle data fetch failed: {e}")
            return None
    
    # =========================================================================
    # TECHNICAL INDICATORS
    # =========================================================================
    
    def calculate_ema(self, series, period):
        """Calculate Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean()
    
    def calculate_sma(self, series, period):
        """Calculate Simple Moving Average"""
        return series.rolling(window=period).mean()
    
    def calculate_rsi(self, series, period=14):
        """Calculate Relative Strength Index"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def calculate_macd(self, series, fast=12, slow=26, signal=9):
        """Calculate MACD (Moving Average Convergence Divergence)"""
        ema_fast = self.calculate_ema(series, fast)
        ema_slow = self.calculate_ema(series, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def calculate_bollinger_bands(self, series, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        sma = self.calculate_sma(series, period)
        std = series.rolling(window=period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band
    
    def calculate_vwap(self, df):
        """Calculate Volume Weighted Average Price"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap
    
    # =========================================================================
    # TRADING SIGNALS
    # =========================================================================
    
    def get_technical_analysis(self):
        """Get comprehensive technical analysis for NIFTY 50"""
        print("\n[📊] Fetching NIFTY 50 Technical Analysis...")
        
        df = self.get_candle_data()
        
        if df is None or len(df) < 50:
            print("[✗] Not enough data for technical analysis")
            return None
        
        # Calculate all indicators
        df['ema_9'] = self.calculate_ema(df['close'], 9)
        df['ema_20'] = self.calculate_ema(df['close'], 20)
        df['ema_50'] = self.calculate_ema(df['close'], 50)
        df['sma_200'] = self.calculate_sma(df['close'], 200) if len(df) >= 200 else df['close']
        df['rsi'] = self.calculate_rsi(df['close'], 14)
        df['atr'] = self.calculate_atr(df, 14)
        
        # MACD
        df['macd'], df['macd_signal'], df['macd_hist'] = self.calculate_macd(df['close'])
        
        # Bollinger Bands
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = self.calculate_bollinger_bands(df['close'])
        
        # VWAP
        df['vwap'] = self.calculate_vwap(df)
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Build analysis result
        analysis = {
            # Current values
            'close': current['close'],
            'ema_9': current['ema_9'],
            'ema_20': current['ema_20'],
            'ema_50': current['ema_50'],
            'rsi': current['rsi'],
            'atr': current['atr'],
            'macd': current['macd'],
            'macd_signal': current['macd_signal'],
            'macd_hist': current['macd_hist'],
            'bb_upper': current['bb_upper'],
            'bb_middle': current['bb_middle'],
            'bb_lower': current['bb_lower'],
            'vwap': current['vwap'],
            
            # Trend Analysis
            'trend_ema': 'BULLISH' if current['close'] > current['ema_20'] > current['ema_50'] else 
                         'BEARISH' if current['close'] < current['ema_20'] < current['ema_50'] else 'SIDEWAYS',
            
            # Momentum
            'rsi_zone': 'OVERBOUGHT' if current['rsi'] > 70 else 
                        'OVERSOLD' if current['rsi'] < 30 else 'NEUTRAL',
            
            # MACD Signal
            'macd_signal_type': 'BULLISH' if current['macd'] > current['macd_signal'] else 'BEARISH',
            'macd_crossover': 'BULLISH_CROSS' if (prev['macd'] < prev['macd_signal'] and current['macd'] > current['macd_signal']) else
                              'BEARISH_CROSS' if (prev['macd'] > prev['macd_signal'] and current['macd'] < current['macd_signal']) else 'NONE',
            
            # Bollinger Band Position
            'bb_position': 'UPPER' if current['close'] > current['bb_upper'] else
                           'LOWER' if current['close'] < current['bb_lower'] else 'MIDDLE',
            
            # VWAP Trend
            'vwap_trend': 'ABOVE_VWAP' if current['close'] > current['vwap'] else 'BELOW_VWAP',
            
            # Volatility
            'volatility': current['atr'],
            
            'success': True
        }
        
        return analysis
    
    def generate_trading_signal(self):
        """Generate trading signal based on technical analysis"""
        analysis = self.get_technical_analysis()
        market_data = self.get_nifty50_market_data()
        
        if not analysis or not analysis.get('success') or not market_data:
            return None
        
        # Scoring system for signals
        bullish_score = 0
        bearish_score = 0
        signals = []
        
        # 1. EMA Trend (Weight: 25%)
        if analysis['trend_ema'] == 'BULLISH':
            bullish_score += 25
            signals.append("EMA Trend: BULLISH ↑")
        elif analysis['trend_ema'] == 'BEARISH':
            bearish_score += 25
            signals.append("EMA Trend: BEARISH ↓")
        else:
            signals.append("EMA Trend: SIDEWAYS →")
        
        # 2. RSI (Weight: 20%)
        if analysis['rsi'] > 50 and analysis['rsi'] < 70:
            bullish_score += 20
            signals.append(f"RSI: {analysis['rsi']:.1f} (Bullish Momentum)")
        elif analysis['rsi'] < 50 and analysis['rsi'] > 30:
            bearish_score += 20
            signals.append(f"RSI: {analysis['rsi']:.1f} (Bearish Momentum)")
        elif analysis['rsi'] > 70:
            bearish_score += 15  # Overbought - potential reversal
            signals.append(f"RSI: {analysis['rsi']:.1f} (OVERBOUGHT - Caution)")
        elif analysis['rsi'] < 30:
            bullish_score += 15  # Oversold - potential reversal
            signals.append(f"RSI: {analysis['rsi']:.1f} (OVERSOLD - Potential Bounce)")
        
        # 3. MACD (Weight: 25%)
        if analysis['macd_crossover'] == 'BULLISH_CROSS':
            bullish_score += 25
            signals.append("MACD: BULLISH CROSSOVER ✓")
        elif analysis['macd_crossover'] == 'BEARISH_CROSS':
            bearish_score += 25
            signals.append("MACD: BEARISH CROSSOVER ✗")
        elif analysis['macd_signal_type'] == 'BULLISH':
            bullish_score += 15
            signals.append("MACD: Above Signal Line")
        else:
            bearish_score += 15
            signals.append("MACD: Below Signal Line")
        
        # 4. VWAP (Weight: 15%)
        if analysis['vwap_trend'] == 'ABOVE_VWAP':
            bullish_score += 15
            signals.append("VWAP: Trading Above VWAP")
        else:
            bearish_score += 15
            signals.append("VWAP: Trading Below VWAP")
        
        # 5. Bollinger Bands (Weight: 15%)
        if analysis['bb_position'] == 'LOWER':
            bullish_score += 15
            signals.append("BB: Near Lower Band (Potential Bounce)")
        elif analysis['bb_position'] == 'UPPER':
            bearish_score += 15
            signals.append("BB: Near Upper Band (Potential Pullback)")
        else:
            signals.append("BB: Trading in Middle Zone")
        
        # Calculate final signal
        total_score = bullish_score + bearish_score
        if total_score > 0:
            bullish_percent = (bullish_score / total_score) * 100
            bearish_percent = (bearish_score / total_score) * 100
        else:
            bullish_percent = 50
            bearish_percent = 50
        
        # Determine action
        if bullish_score >= 60:
            action = "BUY"
            confidence = "HIGH"
        elif bullish_score >= 45:
            action = "BUY"
            confidence = "MEDIUM"
        elif bearish_score >= 60:
            action = "SELL"
            confidence = "HIGH"
        elif bearish_score >= 45:
            action = "SELL"
            confidence = "MEDIUM"
        else:
            action = "WAIT"
            confidence = "LOW"
        
        # Calculate levels using ATR
        atr = analysis['atr']
        current_price = market_data['ltp']
        
        if action == "BUY":
            entry = current_price
            stop_loss = current_price - (atr * 1.5)
            target_1 = current_price + (atr * 1.0)
            target_2 = current_price + (atr * 2.0)
            target_3 = current_price + (atr * 3.0)
        elif action == "SELL":
            entry = current_price
            stop_loss = current_price + (atr * 1.5)
            target_1 = current_price - (atr * 1.0)
            target_2 = current_price - (atr * 2.0)
            target_3 = current_price - (atr * 3.0)
        else:
            entry = current_price
            stop_loss = current_price - (atr * 1.5)
            target_1 = current_price + (atr * 1.0)
            target_2 = current_price + (atr * 2.0)
            target_3 = current_price + (atr * 3.0)
        
        return {
            'action': action,
            'confidence': confidence,
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'bullish_percent': bullish_percent,
            'bearish_percent': bearish_percent,
            'entry': round(entry, 2),
            'stop_loss': round(stop_loss, 2),
            'target_1': round(target_1, 2),
            'target_2': round(target_2, 2),
            'target_3': round(target_3, 2),
            'signals': signals,
            'analysis': analysis,
            'market_data': market_data
        }
    
    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================
    
    def display_market_summary(self):
        """Display current market summary"""
        market_data = self.get_nifty50_market_data()
        
        if not market_data:
            print("[✗] Could not fetch market data")
            return
        
        print("\n" + "=" * 70)
        print(" " * 20 + "📈 NIFTY 50 MARKET SUMMARY")
        print("=" * 70)
        print(f"  {'Current Time':<20}: {datetime.now().strftime('%d %B %Y - %H:%M:%S')}")
        print("-" * 70)
        print(f"  {'Last Traded Price':<20}: ₹{market_data['ltp']:,.2f}")
        print(f"  {'Day Open':<20}: ₹{market_data['open']:,.2f}")
        print(f"  {'Day High':<20}: ₹{market_data['high']:,.2f}")
        print(f"  {'Day Low':<20}: ₹{market_data['low']:,.2f}")
        print(f"  {'Day Range':<20}: {market_data['range']:.2f} points")
        print("-" * 70)
        
        change = market_data['change']
        change_pct = market_data['change_percent']
        trend_icon = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
        
        print(f"  {'Change':<20}: {trend_icon} {change:+.2f} ({change_pct:+.2f}%)")
        print(f"  {'Trend':<20}: {market_data['trend']}")
        print("=" * 70)
    
    def display_technical_analysis(self):
        """Display technical analysis"""
        analysis = self.get_technical_analysis()
        
        if not analysis or not analysis.get('success'):
            print("[✗] Could not perform technical analysis")
            return
        
        print("\n" + "=" * 70)
        print(" " * 18 + "📊 TECHNICAL ANALYSIS REPORT")
        print("=" * 70)
        
        # Moving Averages
        print("\n[MOVING AVERAGES]")
        print("-" * 50)
        print(f"  {'EMA 9':<15}: ₹{analysis['ema_9']:,.2f}")
        print(f"  {'EMA 20':<15}: ₹{analysis['ema_20']:,.2f}")
        print(f"  {'EMA 50':<15}: ₹{analysis['ema_50']:,.2f}")
        print(f"  {'Trend':<15}: {analysis['trend_ema']}")
        
        # RSI
        print("\n[MOMENTUM - RSI]")
        print("-" * 50)
        rsi_bar = "█" * int(analysis['rsi'] / 5) + "░" * (20 - int(analysis['rsi'] / 5))
        print(f"  RSI(14): [{rsi_bar}] {analysis['rsi']:.2f}")
        print(f"  Zone: {analysis['rsi_zone']}")
        
        # MACD
        print("\n[MACD]")
        print("-" * 50)
        print(f"  {'MACD Line':<15}: {analysis['macd']:.2f}")
        print(f"  {'Signal Line':<15}: {analysis['macd_signal']:.2f}")
        print(f"  {'Histogram':<15}: {analysis['macd_hist']:.2f}")
        print(f"  {'Signal':<15}: {analysis['macd_signal_type']}")
        if analysis['macd_crossover'] != 'NONE':
            print(f"  {'Crossover':<15}: ⚡ {analysis['macd_crossover']}")
        
        # Bollinger Bands
        print("\n[BOLLINGER BANDS]")
        print("-" * 50)
        print(f"  {'Upper Band':<15}: ₹{analysis['bb_upper']:,.2f}")
        print(f"  {'Middle Band':<15}: ₹{analysis['bb_middle']:,.2f}")
        print(f"  {'Lower Band':<15}: ₹{analysis['bb_lower']:,.2f}")
        print(f"  {'Position':<15}: {analysis['bb_position']}")
        
        # VWAP
        print("\n[VWAP]")
        print("-" * 50)
        print(f"  {'VWAP':<15}: ₹{analysis['vwap']:,.2f}")
        print(f"  {'Status':<15}: {analysis['vwap_trend']}")
        
        # ATR
        print("\n[VOLATILITY - ATR]")
        print("-" * 50)
        print(f"  {'ATR(14)':<15}: {analysis['atr']:.2f} points")
        
        print("\n" + "=" * 70)
    
    def display_trading_signal(self):
        """Display trading signal with recommendation"""
        signal = self.generate_trading_signal()
        
        if not signal:
            print("[✗] Could not generate trading signal")
            return
        
        print("\n" + "=" * 70)
        print(" " * 18 + "🎯 TRADING SIGNAL & RECOMMENDATION")
        print("=" * 70)
        
        # Action Display
        action = signal['action']
        if action == "BUY":
            action_icon = "🟢 BUY"
            action_color = "BULLISH"
        elif action == "SELL":
            action_icon = "🔴 SELL"
            action_color = "BEARISH"
        else:
            action_icon = "⚪ WAIT"
            action_color = "NEUTRAL"
        
        print(f"\n  {'SIGNAL':<15}: {action_icon}")
        print(f"  {'CONFIDENCE':<15}: {signal['confidence']}")
        print(f"  {'BIAS':<15}: {action_color}")
        
        # Score Display
        print("\n[SIGNAL STRENGTH]")
        print("-" * 50)
        bull_bar = "🟩" * (signal['bullish_score'] // 10)
        bear_bar = "🟥" * (signal['bearish_score'] // 10)
        print(f"  Bullish: {bull_bar} {signal['bullish_score']}% ({signal['bullish_percent']:.1f}%)")
        print(f"  Bearish: {bear_bar} {signal['bearish_score']}% ({signal['bearish_percent']:.1f}%)")
        
        # Signal Details
        print("\n[SIGNAL DETAILS]")
        print("-" * 50)
        for sig in signal['signals']:
            print(f"  • {sig}")
        
        # Trade Levels
        print("\n[TRADE LEVELS]")
        print("-" * 50)
        print(f"  {'Entry Price':<15}: ₹{signal['entry']:,.2f}")
        print(f"  {'Stop Loss':<15}: ₹{signal['stop_loss']:,.2f}")
        print(f"  {'Target 1':<15}: ₹{signal['target_1']:,.2f}")
        print(f"  {'Target 2':<15}: ₹{signal['target_2']:,.2f}")
        print(f"  {'Target 3':<15}: ₹{signal['target_3']:,.2f}")
        
        # Risk/Reward
        if action != "WAIT":
            risk = abs(signal['entry'] - signal['stop_loss'])
            reward_1 = abs(signal['target_1'] - signal['entry'])
            rr_ratio = reward_1 / risk if risk > 0 else 0
            
            print("\n[RISK MANAGEMENT]")
            print("-" * 50)
            print(f"  {'Risk (SL)':<15}: {risk:.2f} points")
            print(f"  {'Reward (T1)':<15}: {reward_1:.2f} points")
            print(f"  {'Risk:Reward':<15}: 1:{rr_ratio:.2f}")
        
        print("\n" + "=" * 70)
    
    def run_live_analysis(self):
        """Run complete live analysis"""
        print("\n" + "=" * 70)
        print(" " * 15 + "🚀 NIFTY 50 TRADING SYSTEM - LIVE ANALYSIS")
        print("=" * 70)
        print(f"  Started at: {datetime.now().strftime('%d %B %Y - %H:%M:%S')}")
        print("=" * 70)
        
        # Display all analysis
        self.display_market_summary()
        self.display_technical_analysis()
        self.display_trading_signal()
        
        print("\n" + "=" * 70)
        print(" " * 20 + "✅ ANALYSIS COMPLETE")
        print("=" * 70)
    
    def run_continuous_monitor(self, interval_seconds=30):
        """Run continuous monitoring"""
        print("\n[📡] Starting Continuous NIFTY 50 Monitoring...")
        print(f"[ℹ] Refresh interval: {interval_seconds} seconds")
        print("[ℹ] Press Ctrl+C to stop\n")
        
        try:
            while True:
                import os
                os.system('cls' if os.name == 'nt' else 'clear')
                
                self.run_live_analysis()
                
                print(f"\n[⏰] Next update in {interval_seconds} seconds... (Ctrl+C to stop)")
                time.sleep(interval_seconds)
                
        except KeyboardInterrupt:
            print("\n\n[⏹] Monitoring stopped by user")


# =========================================================================
# MAIN EXECUTION - AUTO START CONTINUOUS MONITOR (30 SECONDS)
# =========================================================================

if __name__ == "__main__":
    import os
    
    print("\n" + "=" * 70)
    print(" " * 10 + "🚀 NIFTY 50 TRADING SYSTEM - CONTINUOUS MONITOR")
    print(" " * 10 + "Auto-refreshing every 30 seconds with Strategy")
    print("=" * 70)
    
    trader = Nifty50Trader()
    
    print("\n[📡] Starting Continuous NIFTY 50 Monitoring...")
    print("[ℹ] Refresh interval: 30 seconds")
    print("[ℹ] Press Ctrl+C to stop\n")
    
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print("\n" + "=" * 70)
            print(" " * 10 + "🚀 NIFTY 50 TRADING SYSTEM - LIVE ANALYSIS")
            print(" " * 10 + f"Updated: {datetime.now().strftime('%d %B %Y - %H:%M:%S')}")
            print("=" * 70)
            
            # Get market data
            market_data = trader.get_nifty50_market_data()
            if market_data:
                print("\n" + "=" * 70)
                print(" " * 20 + "📈 NIFTY 50 MARKET SUMMARY")
                print("=" * 70)
                print(f"  {'Last Traded Price':<20}: ₹{market_data['ltp']:,.2f}")
                print(f"  {'Day Open':<20}: ₹{market_data['open']:,.2f}")
                print(f"  {'Day High':<20}: ₹{market_data['high']:,.2f}")
                print(f"  {'Day Low':<20}: ₹{market_data['low']:,.2f}")
                print(f"  {'Day Range':<20}: {market_data['range']:.2f} points")
                print("-" * 70)
                
                change = market_data['change']
                change_pct = market_data['change_percent']
                trend_icon = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
                
                print(f"  {'Change':<20}: {trend_icon} {change:+.2f} ({change_pct:+.2f}%)")
                print(f"  {'Trend':<20}: {market_data['trend']}")
                print("=" * 70)
            
            # Generate trading signal with strategy
            signal = trader.generate_trading_signal()
            
            if signal:
                print("\n" + "=" * 70)
                print(" " * 15 + "🎯 TRADING STRATEGY & RECOMMENDATION")
                print("=" * 70)
                
                # Action Display
                action = signal['action']
                if action == "BUY":
                    action_icon = "🟢 BUY NIFTY 50"
                    strategy_name = "BULLISH MOMENTUM STRATEGY"
                elif action == "SELL":
                    action_icon = "🔴 SELL NIFTY 50"
                    strategy_name = "BEARISH MOMENTUM STRATEGY"
                else:
                    action_icon = "⚪ WAIT"
                    strategy_name = "NO TRADE - SIDEWAYS MARKET"
                
                print(f"\n  {'STRATEGY':<15}: {strategy_name}")
                print(f"  {'SIGNAL':<15}: {action_icon}")
                print(f"  {'CONFIDENCE':<15}: {signal['confidence']}")
                
                # Signal Strength
                print("\n[SIGNAL STRENGTH]")
                print("-" * 50)
                bull_bar = "🟩" * (signal['bullish_score'] // 10)
                bear_bar = "🟥" * (signal['bearish_score'] // 10)
                print(f"  Bullish: {bull_bar} {signal['bullish_score']}%")
                print(f"  Bearish: {bear_bar} {signal['bearish_score']}%")
                
                # Signal Details
                print("\n[TECHNICAL SIGNALS]")
                print("-" * 50)
                for sig in signal['signals']:
                    print(f"  • {sig}")
                
                # Trade Levels
                print("\n[TRADE LEVELS]")
                print("-" * 50)
                print(f"  {'Entry Price':<15}: ₹{signal['entry']:,.2f}")
                print(f"  {'Stop Loss':<15}: ₹{signal['stop_loss']:,.2f}")
                print(f"  {'Target 1':<15}: ₹{signal['target_1']:,.2f}")
                print(f"  {'Target 2':<15}: ₹{signal['target_2']:,.2f}")
                print(f"  {'Target 3':<15}: ₹{signal['target_3']:,.2f}")
                
                # Risk/Reward
                if action != "WAIT":
                    risk = abs(signal['entry'] - signal['stop_loss'])
                    reward_1 = abs(signal['target_1'] - signal['entry'])
                    rr_ratio = reward_1 / risk if risk > 0 else 0
                    
                    print("\n[RISK MANAGEMENT]")
                    print("-" * 50)
                    print(f"  {'Risk (SL)':<15}: {risk:.2f} points")
                    print(f"  {'Reward (T1)':<15}: {reward_1:.2f} points")
                    print(f"  {'Risk:Reward':<15}: 1:{rr_ratio:.2f}")
                
                # Strategy Description
                print("\n[STRATEGY DETAILS]")
                print("-" * 50)
                if action == "BUY":
                    print("  📈 BULLISH STRATEGY:")
                    print("  • EMA trend is bullish (Price > EMA20 > EMA50)")
                    print("  • RSI shows bullish momentum")
                    print("  • Entry at current market price")
                    print("  • Exit at Target 1/2/3 or Stop Loss")
                    print("  • Hold time: Intraday or Positional")
                elif action == "SELL":
                    print("  📉 BEARISH STRATEGY:")
                    print("  • EMA trend is bearish (Price < EMA20 < EMA50)")
                    print("  • RSI shows bearish momentum")
                    print("  • Short at current market price")
                    print("  • Cover at Target 1/2/3 or Stop Loss")
                    print("  • Hold time: Intraday or Positional")
                else:
                    print("  ⏸️ NO TRADE STRATEGY:")
                    print("  • Market is in sideways/consolidation phase")
                    print("  • Wait for clear breakout or breakdown")
                    print("  • Avoid trading in choppy conditions")
                    print("  • Next analysis in 30 seconds")
                
                print("\n" + "=" * 70)
            
            print(f"\n[⏰] Next update in 30 seconds... (Ctrl+C to stop)")
            print("=" * 70)
            
            time.sleep(30)
            
    except KeyboardInterrupt:
        print("\n\n[⏹] Monitoring stopped by user")
        print("Thank you for using NIFTY 50 Trading System!")
