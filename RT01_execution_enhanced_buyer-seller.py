"""
ENHANCED BUYER/SELLER DETECTION - SENSITIVE VERSION
Fixed thresholds to catch 100+ point moves
Reduced thresholds for better signal generation
"""

import datetime
import pandas as pd
import numpy as np
from SmartApi import SmartConnect
import pyotp
import time
import os
import requests
import threading
import json
from openpyxl import Workbook, load_workbook

class EnhancedBuyerSellerDetectionSensitive:
    def __init__(self):
        self.API_KEY = "9uRi7U23"
        self.CLIENT_ID = "H75840"
        self.MPIN = "6026"
        self.TOTP_SECRET = "WSTVTP65A55FD6KOGJF63LNMLQ"
        self.client = None
        self.session_generated = False
        
        self.buyer_seller_threshold = 0.10  # Ultra low - was 0.35, now 0.10
        self.strong_signal_threshold = 0.25  # Ultra low - was 0.55, now 0.25
        self.volume_threshold = 1.1  # Ultra low - was 1.5, now 1.1
        self.momentum_threshold = 0.05  # Ultra low - was 0.15, now 0.05
        self.buying_pressure_threshold = 0.25  # Ultra low - was 0.55, now 0.25
        
        # TRADING SETTINGS
        self.ENABLE_TRADING = True  # Set to False for paper trading
        self.ORDER_QUANTITY = 50   # 1 Lot Nifty (was 75, now 50 - correct lot size)
        self.stop_loss_percent = 10
        self.target_percent = 30  # Initial Target 30%
        
        # TRAILING SL SETTINGS
        self.trail_activation_percent = 10   # Activate trailing at 10% profit
        self.trail_lock_percent = 3         # Lock 3% profit when activated
        self.trail_step_percent = 5         # Move SL up 5% for every 5% profit rise
        
        # TRACKING
        self.active_positions = {}
        self.active_sl_orders = {}
        self.instrument_df = None
        self.trade_log_file = "RT01_Trade_Log.xlsx"
        self.state_file = "RT01_Trade_State.json"
        self.current_trade_row = None
        self.fast_contract_map = {} # Cache for instant lookup
        
        self.connect()
        if self.session_generated:
            self.display_funds()  # Show balance
            threading.Thread(target=self.download_instrument_master).start()
            self.sync_state_from_broker()
    
    def sync_state_from_broker(self):
        """
        Reconstruct state directly from Broker Data (Stateless/Robust)
        - Fetches Open Positions (NetQty != 0)
        - Fetches Pending SL Orders
        - Rebuilds active_positions dict
        """
        try:
            print("\n[SYNC] Checking Open Positions from Broker...")
            
            # 1. Fetch Positions
            pos_response = self.client.position()
            if not pos_response or not pos_response.get('status'):
                print("[SYNC] No position data available")
                return

            open_positions = [p for p in pos_response['data'] if int(p.get('netqty', 0)) != 0]
            
            if not open_positions:
                print("[SYNC] No open positions found.")
                return

            # 2. Fetch Order Book (to find SL orders)
            order_book_resp = self.client.orderBook()
            pending_sl_orders = {} # key: symboltoken, val: {id, price}
            
            if order_book_resp and order_book_resp.get('status'):
                for order in order_book_resp.get('data', []):
                    # Look for Trigger Pending SL orders
                    if order.get('status') == 'trigger pending' and 'STOPLOSS' in order.get('ordertype', '').upper():
                        pending_sl_orders[order.get('symboltoken')] = {
                            'id': order.get('orderid'),
                            'trigger_price': float(order.get('triggerprice', 0))
                        }

            print(f"[SYNC] Found {len(open_positions)} Open Positions. Restoring state...")

            # 3. Reconstruct State
            for pos in open_positions:
                token = pos.get('symboltoken')
                symbol = pos.get('tradingsymbol')
                net_qty = int(pos.get('netqty'))
                entry_price = float(pos.get('buyavgprice'))
                
                # Check for existing SL Order
                current_sl_price = 0
                sl_order_id = None
                
                if token in pending_sl_orders:
                    sl_data = pending_sl_orders[token]
                    current_sl_price = sl_data['trigger_price']
                    sl_order_id = sl_data['id']
                    
                    # Code uses 'order_id' as main key. Use SYNC_ID fallback
                    main_order_id = f"SYNC_{token}" 
                    
                    self.active_sl_orders[main_order_id] = sl_order_id
                    print(f"   + Linked Broker SL Order: {sl_order_id} @ {current_sl_price}")
                else:
                    # If SL missing, assume 10% risk
                    current_sl_price = entry_price * (1 - self.stop_loss_percent/100)
                    print(f"   ! No Broker SL found. Using Virtual SL: {current_sl_price}")

                main_order_id = f"SYNC_{token}"
                
                self.active_positions[main_order_id] = {
                    'symbol': symbol,
                    'token': token,
                    'entry_time': datetime.datetime.now(),
                    'quantity': net_qty,
                    'entry_price': entry_price,
                    'sl_price': current_sl_price,
                    'target_price': entry_price * (1 + self.target_percent/100), 
                    'target_stage': 0, 
                    'highest_price': entry_price,
                    'trail_active': False
                }
                
                print(f"   => Resumed Trade: {symbol} | Entry: {entry_price} | Qty: {net_qty}")
                
        except Exception as e:
            print(f"[SYNC ERROR] {e}")

    def connect(self):
        try:
            obj = SmartConnect(api_key=self.API_KEY)
            totp = pyotp.TOTP(self.TOTP_SECRET).now()
            data = obj.generateSession(self.CLIENT_ID, self.MPIN, totp)
            
            if data and data.get('status'):
                self.client = obj
                self.session_generated = True
                print("[SUCCESS] Enhanced Detection System (SENSITIVE) Connected!")
                return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
        return False

    def display_funds(self):
        """Fetch and display account balance"""
        try:
            # Fetch RMS (Risk Management System) limits
            response = self.client.rmsLimit()
            
            if response and isinstance(response, dict) and response.get('status'):
                data = response.get('data', {})
                # Angel One returns net available margin
                net_margin = float(data.get('net', 0))
                available_cash = float(data.get('availablecash', 0))
                
                print(f"\n[ACCOUNT BALANCE]")
                print("=" * 30)
                print(f"Net Available Margin: Rs.{net_margin:,.2f}")
                print(f"Available Cash:       Rs.{available_cash:,.2f}")
                print("=" * 30)
            else:
                print("[WARN] Could not fetch account balance")
                
        except Exception as e:
            print(f"[ERROR] Fund fetch failed: {e}")
    
    def get_tick_data(self):
        """Get real-time tick data with fallback for API errors"""
        try:
            end_time = datetime.datetime.now()
            start_time = end_time - datetime.timedelta(minutes=30)
            
            # Try with retry logic for API errors
            for attempt in range(3):
                try:
                    response = self.client.getCandleData({
                        "exchange": "NSE",
                        "symboltoken": "99926000",
                        "interval": "FIVE_MINUTE",
                        "fromdate": start_time.strftime("%Y-%m-%d %H:%M"),
                        "todate": end_time.strftime("%Y-%m-%d %H:%M")
                    })
                    
                    if response and response.get('data'):
                        df = pd.DataFrame(response['data'], 
                                        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        for col in ['open', 'high', 'low', 'close', 'volume']:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                        return df.dropna()
                    else:
                        print(f"[WARN] No data in response, attempt {attempt + 1}/3")
                        
                except Exception as api_error:
                    print(f"[API ERROR] Attempt {attempt + 1}/3: {api_error}")
                    if attempt < 2:  # Don't sleep on last attempt
                        time.sleep(2)  # Wait before retry
                        
            # Fallback: Create synthetic data based on LTP
            print(f"[FALLBACK] Creating synthetic data from LTP...")
            return self.create_synthetic_data()
            
        except Exception as e:
            print(f"[ERROR] Tick data failed: {e}")
            return self.create_synthetic_data()
    
    def get_5min_data(self):
        """Get 5-minute candle data for trend confirmation"""
        try:
            end_time = datetime.datetime.now()
            start_time = end_time - datetime.timedelta(hours=2)
            
            response = self.client.getCandleData({
                "exchange": "NSE",
                "symboltoken": "99926000",
                "interval": "FIVE_MINUTE",
                "fromdate": start_time.strftime("%Y-%m-%d %H:%M"),
                "todate": end_time.strftime("%Y-%m-%d %H:%M")
            })
            
            if response and response.get('data'):
                df = pd.DataFrame(response['data'], 
                                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                return df.dropna()
            return None
        except Exception as e:
            print(f"[ERROR] 5min data failed: {e}")
            return None
    
    def create_synthetic_data(self):
        """Create synthetic data when API fails"""
        try:
            # Get current LTP
            ltp_response = self.client.ltpData("NSE", "NIFTY 50", "99926000")
            if ltp_response and ltp_response.get('data'):
                current_ltp = float(ltp_response['data'].get('ltp', 26000))
                
                # Create 10 synthetic candles with small variations
                synthetic_data = []
                base_time = datetime.datetime.now() - datetime.timedelta(minutes=10)
                
                for i in range(10):
                    # Small random variations around current LTP
                    variation = (i - 5) * 2  # -10 to +10 points variation
                    price = current_ltp + variation
                    
                    synthetic_data.append({
                        'timestamp': base_time + datetime.timedelta(minutes=i),
                        'open': price - 1,
                        'high': price + 2,
                        'low': price - 2,
                        'close': price,
                        'volume': 100000 + (i * 10000)  # Synthetic volume
                    })
                
                df = pd.DataFrame(synthetic_data)
                print(f"[SYNTHETIC] Created {len(df)} candles around LTP {current_ltp}")
                return df
            else:
                print(f"[ERROR] Could not get LTP for synthetic data")
                return None
                
        except Exception as e:
            print(f"[ERROR] Synthetic data creation failed: {e}")
            return None
    
    def enhanced_buyer_seller_analysis_sensitive(self, df):
        """SENSITIVE analysis with much lower thresholds"""
        if df is None or len(df) < 5:  # Reduced from 10 to 5
            return None
        
        # Calculate enhanced indicators
        df = self.calculate_enhanced_indicators(df)
        latest = df.iloc[-1]
        
        # Get 5-minute trend confirmation
        df_5min = self.get_5min_data()
        trend_5min = self.analyze_5min_trend(df_5min) if df_5min is not None else {'direction': 'NEUTRAL', 'confidence': 0.5}
        
        # IMMEDIATE MOMENTUM CHECK (NEW)
        immediate_momentum = self.check_immediate_momentum(df)
        
        # Multiple detection methods with LOWER thresholds
        methods = {
            'immediate_momentum': immediate_momentum,  # NEW: Catches live moves
            'volume_price_trend': self.detect_volume_price_trend_sensitive(df),
            'candle_body_analysis': self.detect_candle_body_pressure_sensitive(df),
            'momentum_divergence': self.detect_momentum_divergence_sensitive(df),
            'support_resistance': self.detect_sr_pressure_sensitive(df),
            'price_velocity': self.detect_price_velocity(df),  # NEW: Speed detection
            'movement_diversion': self.detect_movement_diversion(df),  # NEW: Movement diversion detection
            'operator_activity': self.detect_operator_activity(df),  # NEW: Operator activity detection
            '5min_trend': trend_5min  # NEW: 5-minute trend confirmation
        }
        
        # Enhanced weighted scoring with peak detection
        buyer_score = 0
        seller_score = 0
        
        # Peak/Trough filter
        current_peak = latest.get('is_peak', False)
        current_trough = latest.get('is_trough', False)
        
        # Peak filter - reduce buy signals at peaks (removed BB check)
        peak_penalty = 0.3 if current_peak else 0
        trough_penalty = 0.3 if current_trough else 0
        
        # 5-minute trend boost/penalty
        trend_boost = 0.2 if trend_5min['direction'] != 'NEUTRAL' else 0
        
        # FIXED WEIGHTS - Total = 100% (LOWERED DOMINANCE THRESHOLD)
        
        # Immediate momentum (25% weight) - Reduced to accommodate 5min
        im = methods['immediate_momentum']
        if im['direction'] == 'BUYERS':
            boost = trend_boost if trend_5min['direction'] == 'BUYERS' else 0
            buyer_score += im['confidence'] * 0.25 * (1 - peak_penalty) * (1 + boost)
        elif im['direction'] == 'SELLERS':
            boost = trend_boost if trend_5min['direction'] == 'SELLERS' else 0
            seller_score += im['confidence'] * 0.25 * (1 - trough_penalty) * (1 + boost)
        
        # 5-minute trend confirmation (20% weight) - NEW
        trend_5 = methods['5min_trend']
        if trend_5['direction'] == 'BUYERS':
            buyer_score += trend_5['confidence'] * 0.20
        elif trend_5['direction'] == 'SELLERS':
            seller_score += trend_5['confidence'] * 0.20
        buyer_score = 0
        seller_score = 0
        
        # Peak/Trough filter
        current_peak = latest.get('is_peak', False)
        current_trough = latest.get('is_trough', False)
        
        # Peak filter - reduce buy signals at peaks (removed BB check)
        peak_penalty = 0.3 if current_peak else 0
        trough_penalty = 0.3 if current_trough else 0
        
        # FIXED WEIGHTS - Total = 100% (LOWERED DOMINANCE THRESHOLD)
        
        # Immediate momentum (30% weight) - Most important
        im = methods['immediate_momentum']
        if im['direction'] == 'BUYERS':
            buyer_score += im['confidence'] * 0.30 * (1 - peak_penalty)
        elif im['direction'] == 'SELLERS':
            seller_score += im['confidence'] * 0.30 * (1 - trough_penalty)
        
        # Volume-Price Trend (15% weight) - REDUCED
        vpt = methods['volume_price_trend']
        if vpt['direction'] == 'BUYERS':
            buyer_score += vpt['confidence'] * 0.15
        elif vpt['direction'] == 'SELLERS':
            seller_score += vpt['confidence'] * 0.15
        
        # Operator Activity (15% weight) - High importance
        op_act = methods['operator_activity']
        if op_act['direction'] == 'BUYERS':
            buyer_score += op_act['confidence'] * 0.15
        elif op_act['direction'] == 'SELLERS':
            seller_score += op_act['confidence'] * 0.15
        
        # Price Velocity (15% weight) - ADDED BACK
        pv = methods['price_velocity']
        if pv['direction'] == 'BUYERS':
            buyer_score += pv['confidence'] * 0.15
        elif pv['direction'] == 'SELLERS':
            seller_score += pv['confidence'] * 0.15
        
        # Candle Body Analysis (10% weight) - REDUCED
        cba = methods['candle_body_analysis']
        if cba['direction'] == 'BUYERS':
            buyer_score += cba['confidence'] * 0.10
        elif cba['direction'] == 'SELLERS':
            seller_score += cba['confidence'] * 0.10
        
        # Movement Diversion (8% weight)
        md_div = methods['movement_diversion']
        if md_div['direction'] == 'BUYERS':
            buyer_score += md_div['confidence'] * 0.08
        elif md_div['direction'] == 'SELLERS':
            seller_score += md_div['confidence'] * 0.08
        
        # Momentum Divergence (5% weight) - REDUCED
        md = methods['momentum_divergence']
        if md['direction'] == 'BUYERS':
            buyer_score += md['confidence'] * 0.05
        elif md['direction'] == 'SELLERS':
            seller_score += md['confidence'] * 0.05
        
        # Support/Resistance (2% weight) - REDUCED
        sr = methods['support_resistance']
        if sr['direction'] == 'BUYERS':
            buyer_score += sr['confidence'] * 0.02
        elif sr['direction'] == 'SELLERS':
            seller_score += sr['confidence'] * 0.02
        
        # Final decision with ultra-low thresholds
        if buyer_score > seller_score and buyer_score > 0.05:  # Ultra low - was 0.13, now 0.05
            if current_peak:
                direction = 'BUYERS_AT_PEAK'
                confidence = min(buyer_score * 100, 85)  # Increased confidence multiplier
            else:
                direction = 'BUYERS_DOMINATING'
                confidence = min(buyer_score * 120, 95)  # Boosted confidence
        elif seller_score > buyer_score and seller_score > 0.05:  # Ultra low - was 0.13, now 0.05
            if current_trough:
                direction = 'SELLERS_AT_TROUGH'
                confidence = min(seller_score * 100, 85)  # Increased confidence multiplier
            else:
                direction = 'SELLERS_DOMINATING'
                confidence = min(seller_score * 120, 95)  # Boosted confidence
        else:
            direction = 'BALANCED'
            confidence = max(buyer_score, seller_score) * 120  # Boosted neutral confidence
        
        return {
            'direction': direction,
            'confidence': confidence,
            'buyer_score': buyer_score,
            'seller_score': seller_score,
            'methods': methods,
            'current_price': latest['close'],
            'timestamp': latest['timestamp'],
            'price_change_5min': latest['close'] - df['close'].iloc[-6] if len(df) >= 6 else 0,
            'at_peak': current_peak,
            'at_trough': current_trough
        }
    
    def check_immediate_momentum(self, df):
        """NEW: Check immediate momentum for live moves"""
        try:
            if len(df) < 3:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            # Last 3 candles momentum
            recent_3 = df.tail(3)
            price_start = recent_3['close'].iloc[0]
            price_end = recent_3['close'].iloc[-1]
            price_change = price_end - price_start
            price_change_pct = (price_change / price_start) * 100
            
            # Volume in last 3 candles
            recent_volume = recent_3['volume'].mean()
            overall_volume = df['volume'].mean()
            volume_ratio = recent_volume / overall_volume if overall_volume > 0 else 1
            
            # ULTRA LOW thresholds for immediate detection
            if abs(price_change) > 10:  # 10+ points move (was 20+)
                if price_change > 0 and volume_ratio > 1.05:  # Was 1.2, now 1.05
                    return {'direction': 'BUYERS', 'confidence': min(0.95, 0.7 + abs(price_change_pct) * 15)}
                elif price_change < 0 and volume_ratio > 1.05:
                    return {'direction': 'SELLERS', 'confidence': min(0.95, 0.7 + abs(price_change_pct) * 15)}
            
            # Medium moves (5+ points)
            elif abs(price_change) > 5:  # Was 10+, now 5+
                if price_change > 0 and volume_ratio > 1.02:  # Was 1.1, now 1.02
                    return {'direction': 'BUYERS', 'confidence': 0.8}
                elif price_change < 0 and volume_ratio > 1.02:
                    return {'direction': 'SELLERS', 'confidence': 0.8}
            
            # Small moves (2+ points) - ULTRA LOW threshold
            elif abs(price_change) > 2:  # Was 5+, now 2+
                if price_change > 0 and volume_ratio > 1.01:  # Was 1.05, now 1.01
                    return {'direction': 'BUYERS', 'confidence': 0.7}
                elif price_change < 0 and volume_ratio > 1.01:
                    return {'direction': 'SELLERS', 'confidence': 0.7}
            
            # Tiny moves (1+ points) - MINIMAL threshold
            elif abs(price_change) > 1:  # Was 3+, now 1+
                if price_change > 0 and volume_ratio > 1.005:  # Was 1.02, now 1.005
                    return {'direction': 'BUYERS', 'confidence': 0.65}
                elif price_change < 0 and volume_ratio > 1.005:
                    return {'direction': 'SELLERS', 'confidence': 0.65}
            
            # Any directional move (0.5+ points)
            elif abs(price_change) > 0.5:  # Was 1+, now 0.5+
                if price_change > 0:
                    return {'direction': 'BUYERS', 'confidence': 0.6}
                elif price_change < 0:
                    return {'direction': 'SELLERS', 'confidence': 0.6}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_price_velocity(self, df):
        """NEW: Detect price velocity/acceleration"""
        try:
            if len(df) < 5:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            # Calculate price velocity (points per minute)
            recent_5 = df.tail(5)
            time_diff = 5  # 5 minutes
            price_diff = recent_5['close'].iloc[-1] - recent_5['close'].iloc[0]
            velocity = price_diff / time_diff  # Points per minute
            
            # Velocity thresholds (MINIMAL)
            if velocity > 1:  # 1+ points per minute = BUYERS (was 2+)
                return {'direction': 'BUYERS', 'confidence': min(0.9, 0.6 + abs(velocity) * 0.1)}
            elif velocity < -1:  # -1 points per minute = SELLERS (was -2)
                return {'direction': 'SELLERS', 'confidence': min(0.9, 0.6 + abs(velocity) * 0.1)}
            elif velocity > 0.5:  # Mild bullish velocity (was 1)
                return {'direction': 'BUYERS', 'confidence': 0.7}
            elif velocity < -0.5:  # Mild bearish velocity (was -1)
                return {'direction': 'SELLERS', 'confidence': 0.7}
            elif velocity > 0.2:  # Very mild bullish (was 0.5)
                return {'direction': 'BUYERS', 'confidence': 0.6}
            elif velocity < -0.2:  # Very mild bearish (was -0.5)
                return {'direction': 'SELLERS', 'confidence': 0.6}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def calculate_enhanced_indicators(self, df):
        """Calculate enhanced indicators with Bollinger Bands and Peak Detection"""
        # Volume indicators
        df['volume_ma'] = df['volume'].rolling(5).mean()
        df['volume_ratio'] = df['volume'] / df['volume_ma']
        
        # Price indicators
        df['price_change'] = df['close'].diff()
        df['price_velocity'] = df['price_change'].rolling(2).mean()
        
        # Peak/Trough Detection
        
        # Peak/Trough Detection
        df['is_peak'] = False
        df['is_trough'] = False
        if len(df) >= 3:
            for i in range(1, len(df)-1):
                if df['high'].iloc[i] > df['high'].iloc[i-1] and df['high'].iloc[i] > df['high'].iloc[i+1]:
                    df.loc[df.index[i], 'is_peak'] = True
                if df['low'].iloc[i] < df['low'].iloc[i-1] and df['low'].iloc[i] < df['low'].iloc[i+1]:
                    df.loc[df.index[i], 'is_trough'] = True
        
        # Body analysis
        df['body'] = abs(df['close'] - df['open'])
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        df['total_range'] = df['high'] - df['low']
        
        # Momentum
        df['momentum_2'] = (df['close'] - df['close'].shift(2)) / df['close'].shift(2) * 100
        df['momentum_3'] = (df['close'] - df['close'].shift(3)) / df['close'].shift(3) * 100
        
        # Support/Resistance
        df['resistance'] = df['high'].rolling(10).max()
        df['support'] = df['low'].rolling(10).min()
        
        return df
    
    def detect_volume_price_trend_sensitive(self, df):
        """SENSITIVE Volume-Price Trend Analysis"""
        try:
            recent = df.tail(3)  # Reduced from 5 to 3
            
            up_candles = recent[recent['close'] > recent['open']]
            down_candles = recent[recent['close'] < recent['open']]
            
            up_volume = up_candles['volume'].sum() if len(up_candles) > 0 else 0
            down_volume = down_candles['volume'].sum() if len(down_candles) > 0 else 0
            
            if up_volume + down_volume > 0:
                buying_pressure = up_volume / (up_volume + down_volume)
                selling_pressure = down_volume / (up_volume + down_volume)
                
                # ULTRA REDUCED thresholds
                if buying_pressure > 0.40:  # Was 0.45, now 0.40
                    return {'direction': 'BUYERS', 'confidence': buying_pressure}
                elif selling_pressure > 0.40:
                    return {'direction': 'SELLERS', 'confidence': selling_pressure}
                elif buying_pressure > 0.30:  # Weak buying
                    return {'direction': 'BUYERS', 'confidence': buying_pressure * 0.8}
                elif selling_pressure > 0.30:  # Weak selling
                    return {'direction': 'SELLERS', 'confidence': selling_pressure * 0.8}
                elif buying_pressure > 0.25:  # Very weak buying
                    return {'direction': 'BUYERS', 'confidence': buying_pressure * 0.7}
                elif selling_pressure > 0.25:  # Very weak selling
                    return {'direction': 'SELLERS', 'confidence': selling_pressure * 0.7}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_candle_body_pressure_sensitive(self, df):
        """SENSITIVE Candle Body Analysis"""
        try:
            latest = df.iloc[-1]
            
            body_ratio = latest['body'] / latest['total_range'] if latest['total_range'] > 0 else 0
            upper_shadow_ratio = latest['upper_shadow'] / latest['total_range'] if latest['total_range'] > 0 else 0
            lower_shadow_ratio = latest['lower_shadow'] / latest['total_range'] if latest['total_range'] > 0 else 0
            
            # MUCH MORE REDUCED thresholds
            if (latest['close'] > latest['open'] and 
                body_ratio > 0.3 and  # Was 0.4, now 0.3
                lower_shadow_ratio < 0.4):  # Was 0.3, now 0.4
                return {'direction': 'BUYERS', 'confidence': 0.7}
            
            elif (latest['close'] < latest['open'] and 
                  body_ratio > 0.3 and 
                  upper_shadow_ratio < 0.4):
                return {'direction': 'SELLERS', 'confidence': 0.7}
            
            # Any bullish candle
            elif latest['close'] > latest['open'] and body_ratio > 0.2:
                return {'direction': 'BUYERS', 'confidence': 0.55}
            
            # Any bearish candle
            elif latest['close'] < latest['open'] and body_ratio > 0.2:
                return {'direction': 'SELLERS', 'confidence': 0.55}
            
            # REDUCED hammer/shooting star thresholds
            elif (lower_shadow_ratio > 0.3 and body_ratio < 0.5):  # Was 0.4, now 0.3
                return {'direction': 'BUYERS', 'confidence': 0.6}
            
            elif (upper_shadow_ratio > 0.3 and body_ratio < 0.5):
                return {'direction': 'SELLERS', 'confidence': 0.6}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_momentum_divergence_sensitive(self, df):
        """SENSITIVE Momentum Divergence Analysis"""
        try:
            if len(df) < 5:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            recent_momentum = df['momentum_2'].iloc[-1]  # Using 2-period momentum
            volume_momentum = df['volume_ratio'].iloc[-1]
            
            # ULTRA LOW thresholds
            if recent_momentum > 0.05 and volume_momentum > 1.2:  # Much lower
                return {'direction': 'BUYERS', 'confidence': 0.65}
            elif recent_momentum < -0.05 and volume_momentum > 1.2:
                return {'direction': 'SELLERS', 'confidence': 0.65}
            elif recent_momentum > 0.02:  # Any positive momentum
                return {'direction': 'BUYERS', 'confidence': 0.55}
            elif recent_momentum < -0.02:  # Any negative momentum
                return {'direction': 'SELLERS', 'confidence': 0.55}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_sr_pressure_sensitive(self, df):
        """SENSITIVE Support/Resistance Pressure"""
        try:
            latest = df.iloc[-1]
            
            resistance_distance = (latest['resistance'] - latest['close']) / latest['close'] * 100
            support_distance = (latest['close'] - latest['support']) / latest['close'] * 100
            
            # INCREASED distance threshold for easier detection
            if resistance_distance < 0.3 and latest['volume_ratio'] > 1.2:  # Was 0.2 & 1.3
                if latest['close'] > latest['open']:
                    return {'direction': 'BUYERS', 'confidence': 0.7}
                else:
                    return {'direction': 'SELLERS', 'confidence': 0.6}
            
            elif support_distance < 0.3 and latest['volume_ratio'] > 1.2:
                if latest['close'] > latest['open']:
                    return {'direction': 'BUYERS', 'confidence': 0.7}
                else:
                    return {'direction': 'SELLERS', 'confidence': 0.6}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
        except:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    def detect_movement_diversion(self, df):
        """Detect movement diversion patterns - Price vs Volume vs Momentum"""
        try:
            if len(df) < 5:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            recent_5 = df.tail(5)
            
            # Price trend (last 5 candles)
            price_start = recent_5['close'].iloc[0]
            price_end = recent_5['close'].iloc[-1]
            price_change = price_end - price_start
            price_trend = 'UP' if price_change > 5 else 'DOWN' if price_change < -5 else 'FLAT'
            
            # Volume trend
            recent_volume = recent_5['volume'].mean()
            earlier_volume = df['volume'].iloc[-10:-5].mean() if len(df) >= 10 else recent_volume
            volume_ratio = recent_volume / earlier_volume if earlier_volume > 0 else 1
            volume_trend = 'INCREASING' if volume_ratio > 1.2 else 'DECREASING' if volume_ratio < 0.8 else 'STABLE'
            
            # Momentum trend
            momentum_recent = recent_5['momentum_2'].iloc[-1] if 'momentum_2' in recent_5.columns else 0
            momentum_trend = 'STRONG_UP' if momentum_recent > 0.3 else 'STRONG_DOWN' if momentum_recent < -0.3 else 'WEAK'
            
            # Bullish Divergence: Price down but volume/momentum up
            if price_trend == 'DOWN' and volume_trend == 'INCREASING' and momentum_trend != 'STRONG_DOWN':
                return {'direction': 'BUYERS', 'confidence': 0.75, 'type': 'BULLISH_DIVERGENCE'}
            
            # Bearish Divergence: Price up but volume/momentum weak
            elif price_trend == 'UP' and (volume_trend == 'DECREASING' or momentum_trend == 'WEAK'):
                return {'direction': 'SELLERS', 'confidence': 0.70, 'type': 'BEARISH_DIVERGENCE'}
            
            # Volume-Price Divergence
            elif abs(price_change) > 15 and volume_ratio < 0.7:
                direction = 'SELLERS' if price_change > 0 else 'BUYERS'
                return {'direction': direction, 'confidence': 0.65, 'type': 'VOLUME_PRICE_DIVERGENCE'}
            
            return {'direction': 'NEUTRAL', 'confidence': 0.5, 'type': 'NO_DIVERGENCE'}
            
        except Exception as e:
            return {'direction': 'NEUTRAL', 'confidence': 0.5, 'type': 'ERROR'}
    
    def detect_operator_activity(self, df):
        """Detect operator/institutional activity patterns"""
        try:
            if len(df) < 10:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            latest = df.iloc[-1]
            recent_5 = df.tail(5)
            
            # Volume spike detection
            avg_volume = df['volume'].mean()
            recent_volume = recent_5['volume'].mean()
            volume_spike = recent_volume / avg_volume if avg_volume > 0 else 1
            
            # Price impact analysis
            price_change_5min = recent_5['close'].iloc[-1] - recent_5['close'].iloc[0]
            
            # Large candle detection
            body_size = abs(latest['close'] - latest['open'])
            avg_body = df['body'].mean() if 'body' in df.columns else 10
            large_candle = body_size / avg_body if avg_body > 0 else 1
            
            operator_score = 0
            operator_signals = []
            
            # Volume spike (MUCH LOWER)
            if volume_spike > 2.0:  # Was 3.0, now 2.0
                operator_score += 0.8
                operator_signals.append(f"VOL_SPIKE_{volume_spike:.1f}x")
            elif volume_spike > 1.5:  # Was 2.0, now 1.5
                operator_score += 0.6
                operator_signals.append(f"HIGH_VOL_{volume_spike:.1f}x")
            elif volume_spike > 1.2:  # NEW: Mild volume increase
                operator_score += 0.4
                operator_signals.append(f"MILD_VOL_{volume_spike:.1f}x")
            
            # Price move with volume (LOWER)
            if abs(price_change_5min) > 15 and volume_spike > 1.3:  # Was 25 & 1.5
                operator_score += 0.7
                operator_signals.append(f"BIG_MOVE_{abs(price_change_5min):.0f}pts")
            elif abs(price_change_5min) > 8 and volume_spike > 1.2:  # NEW: Small moves
                operator_score += 0.5
                operator_signals.append(f"SMALL_MOVE_{abs(price_change_5min):.0f}pts")
            
            # Unusual candle size
            if large_candle > 2.5:
                operator_score += 0.6
                operator_signals.append(f"LARGE_CANDLE")
            
            # Block trades (high volume, small price impact)
            if volume_spike > 2.5 and abs(price_change_5min) < 15:
                operator_score += 0.6
                operator_signals.append("BLOCK_TRADE")
            
            # Determine direction (LOWER threshold)
            if operator_score > 0.3:  # Was 0.6, now 0.3
                if price_change_5min > 2:  # Was 5, now 2
                    direction = 'BUYERS'
                elif price_change_5min < -2:  # Was -5, now -2
                    direction = 'SELLERS'
                else:
                    direction = 'ACCUMULATION'
                confidence = min(operator_score, 0.9)
            else:
                direction = 'NEUTRAL'
                confidence = 0.5
            
            return {
                'direction': direction,
                'confidence': confidence,
                'volume_spike': volume_spike,
                'signals': operator_signals,
                'operator_score': operator_score
            }
            
        except Exception as e:
            return {'direction': 'NEUTRAL', 'confidence': 0.5, 'signals': []}
    
    def analyze_5min_trend(self, df_5min):
        """Analyze 5-minute trend for confirmation"""
        try:
            if df_5min is None or len(df_5min) < 6:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
            
            recent_6 = df_5min.tail(6)
            
            # Price trend over 30 minutes (6 candles)
            price_start = recent_6['close'].iloc[0]
            price_end = recent_6['close'].iloc[-1]
            price_change = price_end - price_start
            price_change_pct = (price_change / price_start) * 100
            
            # Volume trend
            recent_vol = recent_6['volume'].mean()
            earlier_vol = df_5min['volume'].mean() if len(df_5min) > 6 else recent_vol
            vol_ratio = recent_vol / earlier_vol if earlier_vol > 0 else 1
            
            # Trend strength calculation
            if abs(price_change) > 50:  # Strong trend (50+ points)
                confidence = min(0.9, 0.7 + abs(price_change_pct) * 0.05)
            elif abs(price_change) > 25:  # Medium trend
                confidence = 0.75
            elif abs(price_change) > 10:  # Weak trend
                confidence = 0.65
            else:  # No clear trend
                confidence = 0.5
            
            # Volume confirmation
            if vol_ratio > 1.3:
                confidence *= 1.1
            elif vol_ratio < 0.8:
                confidence *= 0.9
            
            # Direction determination
            if price_change > 10:
                return {'direction': 'BUYERS', 'confidence': min(confidence, 0.95)}
            elif price_change < -10:
                return {'direction': 'SELLERS', 'confidence': min(confidence, 0.95)}
            else:
                return {'direction': 'NEUTRAL', 'confidence': 0.5}
                
        except Exception as e:
            return {'direction': 'NEUTRAL', 'confidence': 0.5}
    
    # REMOVED: get_bb_data_5min and calculate_bollinger_bands functions
    # BB calculation is now done directly in calculate_enhanced_indicators
    
    def find_pivot_points(self, df):
        """Find previous support and next resistance pivot points"""
        try:
            if df is None or len(df) < 10:
                return {'prev_support': None, 'next_resistance': None}
            
            current_price = df['close'].iloc[-1]
            
            # Find pivot highs (resistance levels)
            pivot_highs = []
            for i in range(2, len(df)-2):
                high = df['high'].iloc[i]
                if (high > df['high'].iloc[i-1] and high > df['high'].iloc[i-2] and
                    high > df['high'].iloc[i+1] and high > df['high'].iloc[i+2]):
                    pivot_highs.append({'price': high, 'index': i})
            
            # Find pivot lows (support levels)
            pivot_lows = []
            for i in range(2, len(df)-2):
                low = df['low'].iloc[i]
                if (low < df['low'].iloc[i-1] and low < df['low'].iloc[i-2] and
                    low < df['low'].iloc[i+1] and low < df['low'].iloc[i+2]):
                    pivot_lows.append({'price': low, 'index': i})
            
            # Find previous support (highest low below current price)
            prev_support = None
            for pivot in reversed(pivot_lows):
                if pivot['price'] < current_price:
                    prev_support = pivot['price']
                    break
            
            # Find next resistance (lowest high above current price)
            next_resistance = None
            for pivot in reversed(pivot_highs):
                if pivot['price'] > current_price:
                    if next_resistance is None or pivot['price'] < next_resistance:
                        next_resistance = pivot['price']
            
            return {
                'prev_support': prev_support,
                'next_resistance': next_resistance,
                'support_distance': (current_price - prev_support) if prev_support else None,
                'resistance_distance': (next_resistance - current_price) if next_resistance else None
            }
            
        except Exception as e:
            print(f"[ERROR] Pivot points calculation failed: {e}")
            return {'prev_support': None, 'next_resistance': None}
    


    # =========================================================================
    # STATE PERSISTENCE METHODS (RESUME CAPABILITY)
    # =========================================================================
    
    def save_state(self):
        """Save active positions to JSON file"""
        try:
            state_data = {}
            for order_id, pos in self.active_positions.items():
                # Convert datetime to string for JSON
                pos_copy = pos.copy()
                if 'entry_time' in pos_copy:
                    pos_copy['entry_time'] = pos_copy['entry_time'].strftime("%Y-%m-%d %H:%M:%S")
                state_data[order_id] = pos_copy
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=4)
                
            # print(f"[STATE] Saved {len(state_data)} positions")
        except Exception as e:
            print(f"[ERROR] State save failed: {e}")

    def load_state(self):
        """Load active positions from JSON file"""
        try:
            if not os.path.exists(self.state_file):
                return
            
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
            
            count = 0
            for order_id, pos in state_data.items():
                # Convert string back to datetime
                if 'entry_time' in pos:
                    try:
                        pos['entry_time'] = datetime.datetime.strptime(pos['entry_time'], "%Y-%m-%d %H:%M:%S")
                    except:
                        pos['entry_time'] = datetime.datetime.now()
                
                self.active_positions[order_id] = pos
                count += 1
            
            if count > 0:
                print(f"[RESUMED] Restored {count} active trades from previous session")
                print(f"           Monitoring will continue automatically...")
        except Exception as e:
            print(f"[ERROR] State load failed: {e}")

    # =========================================================================
    # REAL TRADE EXECUTION METHODS
    # =========================================================================
    
    def download_instrument_master(self):
        """Download instrument master"""
        try:
            print("[INFO] Downloading instrument master...")
            url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                self.instrument_df = pd.DataFrame(data)
                
                # Filter NFO options
                exch_col = 'exch_seg' if 'exch_seg' in self.instrument_df.columns else 'exchange'
                if exch_col in self.instrument_df.columns:
                    self.instrument_df = self.instrument_df[self.instrument_df[exch_col].isin(['NFO', 'NSE'])].copy()
                
                self.instrument_df['strike'] = pd.to_numeric(self.instrument_df['strike'], errors='coerce').fillna(0).astype(int)
                print(f"[SUCCESS] {len(self.instrument_df)} instruments loaded")
                
                # ----------------------------------------------------
                # BUILD FAST CACHE MAP (ZERO LATENCY)
                # ----------------------------------------------------
                print("[INFO] Building Fast Contract Map...")
                filtered = self.instrument_df[
                    (self.instrument_df['instrumenttype'] == 'OPTIDX') &
                    (self.instrument_df['name'] == 'NIFTY')
                ].copy()
                
                # Helper for expiry parsing
                def parse_expiry(expiry_str):
                    try:
                        return datetime.datetime.strptime(expiry_str, '%d%b%Y')
                    except:
                        try:
                            # Handle different formats if needed
                            return datetime.datetime.strptime(expiry_str, '%d%B%Y')
                        except:
                            return datetime.datetime.max
                
                filtered['expiry_dt'] = filtered['expiry'].apply(parse_expiry)
                today = datetime.datetime.now().date()
                future_opts = filtered[filtered['expiry_dt'].dt.date >= today]
                
                if not future_opts.empty:
                    # Find nearest expiry
                    min_expiry = future_opts['expiry_dt'].min()
                    # Filter for only nearest expiry contracts
                    nearest_opts = future_opts[future_opts['expiry_dt'] == min_expiry]
                    
                    tradingsymbol_col = 'tradingsymbol' if 'tradingsymbol' in self.instrument_df.columns else 'symbol'
                    token_col = 'token' if 'token' in self.instrument_df.columns else 'symboltoken'
                    
                    for _, row in nearest_opts.iterrows():
                        strike = int(row['strike'])
                        # Determine type from symbol (CE/PE)
                        tsym = row[tradingsymbol_col]
                        otype = "CE" if "CE" in tsym else "PE" if "PE" in tsym else "XX"
                        
                        # Populate Map: Key = (Strike, Type), Value = {Data}
                        # We store divided by 100 strike logic just in case api has it, but usually standard strike
                        # Checking standard strike first
                        self.fast_contract_map[(strike, otype)] = {
                            'symbol': tsym,
                            'token': str(row[token_col]),
                            'expiry': row['expiry']
                        }
                        # Also handle the /100 case sometimes seen in API
                        self.fast_contract_map[(strike/100, otype)] = {
                            'symbol': tsym,
                            'token': str(row[token_col]),
                            'expiry': row['expiry']
                        }
                        
                    print(f"[CACHE] Indexed {len(nearest_opts)} contracts for instant lookup")
                
                return True
            else:
                print(f"[ERROR] Instrument download HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"[ERROR] Download failed: {e}")
            return False
    
    def find_option_contract(self, strike, option_type):
        """Find option contract (Zero Latency Version)"""
        try:
            # 1. FAST LOOKUP (Priority)
            if (strike, option_type) in self.fast_contract_map:
                contract = self.fast_contract_map[(strike, option_type)]
                # print(f"[FAST LOOKUP] Found {contract['symbol']}")
                return contract
                
            # print(f"[WARN] Cache miss for {strike} {option_type}, falling back to slow search")
            
            if self.instrument_df is None:
                print("[WARN] Instrument master not loaded yet")
                return None
            
            tradingsymbol_col = 'tradingsymbol' if 'tradingsymbol' in self.instrument_df.columns else 'symbol'
            token_col = 'token' if 'token' in self.instrument_df.columns else 'symboltoken'
            exch_col = 'exch_seg' if 'exch_seg' in self.instrument_df.columns else 'exchange'
            
            # Filter NIFTY options
            filtered = self.instrument_df[
                (self.instrument_df['instrumenttype'] == 'OPTIDX') &
                (self.instrument_df[exch_col] == 'NFO') &
                ((self.instrument_df['strike'] == strike) | (self.instrument_df['strike'] == strike * 100)) &
                (self.instrument_df[tradingsymbol_col].str.contains(option_type, na=False)) &
                (self.instrument_df[tradingsymbol_col].str.startswith('NIFTY', na=False)) &
                (~self.instrument_df[tradingsymbol_col].str.contains('BANK|MID|FIN|SENSEX', case=False, na=False))
            ]
            
            if filtered.empty:
                return None
            
            # Get nearest expiry
            def parse_expiry(expiry_str):
                try:
                    return datetime.datetime.strptime(expiry_str, '%d%b%Y')
                except:
                    try:
                        return datetime.datetime.strptime(expiry_str, '%d%B%Y')
                    except:
                        return datetime.datetime.max
            
            filtered = filtered.copy()
            filtered['expiry_date'] = filtered['expiry'].apply(parse_expiry)
            
            # Future dates only
            today = datetime.datetime.now().date()
            filtered = filtered[filtered['expiry_date'].dt.date >= today]
            
            if filtered.empty:
                return None
            
            # Nearest expiry
            filtered = filtered.sort_values('expiry_date')
            option_row = filtered.iloc[0]
            
            return {
                'symbol': option_row[tradingsymbol_col],
                'token': str(option_row[token_col]),
                'strike': strike,
                'expiry': option_row['expiry']
            }
            
        except Exception as e:
            print(f"[ERROR] Contract search failed: {e}")
            return None

    def get_option_ltp(self, symbol, token=""):
        """Get option LTP with proper token handling"""
        try:
            # If no token provided, try to find it
            if not token:
                # Extract strike and type from symbol
                import re
                match = re.search(r'(\d+)(CE|PE)', symbol)
                if match:
                    strike = int(match.group(1))
                    option_type = match.group(2)
                    contract = self.find_option_contract(strike, option_type)
                    if contract:
                        token = contract['token']
                    else:
                        print(f"[WARN] Could not find contract for {symbol}")
                        return None
                else:
                    print(f"[WARN] Could not parse symbol {symbol}")
                    return None
            
            ltp_data = self.client.ltpData("NFO", symbol, token)
            if ltp_data and ltp_data.get('data'):
                return float(ltp_data['data'].get('ltp', 0))
            return None
        except Exception as e:
            print(f"[LTP ERROR] {e}")
            return None

    def place_order(self, symbol, token, quantity, order_type="BUY", entry_price=None):
        """Place Normal Order with lot size validation"""
        try:
            if not self.ENABLE_TRADING:
                print("[PAPER] Order simulated")
                return "SIM_" + str(int(time.time()))
            
            # Validate lot size for NIFTY options (lot size = 50)
            if quantity % 50 != 0:
                print(f"[LOT SIZE ERROR] Quantity {quantity} is not multiple of 50. Adjusting to {(quantity // 50) * 50}")
                quantity = (quantity // 50) * 50
                if quantity == 0:
                    quantity = 50  # Minimum 1 lot
            
            # Place Normal Market Order
            normal_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": order_type,
                "exchange": "NFO",
                "ordertype": "MARKET",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": str(quantity)
            }
            
            print(f"[ORDER] {symbol} x {quantity} (Lot Size Validated)")
            print(f"  Type: {order_type} MARKET")
            
            response = self.client.placeOrder(normal_params)
            
            # Handle response
            if isinstance(response, str) and response and len(response) > 5:
                print(f"[SUCCESS] Order ID: {response}")
                return response
            
            if response and isinstance(response, dict):
                if response.get('status'):
                    data = response.get('data', {})
                    if isinstance(data, dict):
                        order_id = data.get('orderid', str(data))
                    elif isinstance(data, str):
                        order_id = data
                    else:
                        order_id = str(data) if data else None
                    
                    if order_id:
                        print(f"[SUCCESS] Order ID: {order_id}")
                        return order_id
                else:
                    error_msg = response.get('message', str(response))
                    error_code = response.get('errorcode', '')
                    print(f"[ERROR] Order failed: {error_msg} (Code: {error_code})")
                    
                    # Handle specific lot size error
                    if 'lot size' in error_msg.lower() or error_code == 'AB4014':
                        print(f"[LOT SIZE FIX] Retrying with quantity 50...")
                        normal_params['quantity'] = '50'
                        retry_response = self.client.placeOrder(normal_params)
                        if retry_response and retry_response.get('status'):
                            retry_order_id = retry_response.get('data', {}).get('orderid')
                            if retry_order_id:
                                print(f"[RETRY SUCCESS] Order ID: {retry_order_id}")
                                return retry_order_id
                    
                    return None
            
            print(f"[ORDER FAILED] {response}")
            return None
                
        except Exception as e:
            print(f"[ORDER ERROR] {e}")
            return None
    
    def check_if_bracket_order(self, order_id):
        """Check if order is a Bracket Order"""
        try:
            if not self.ENABLE_TRADING:
                return False
                
            order_book_resp = self.client.orderBook()
            if order_book_resp and order_book_resp.get('status'):
                orders = order_book_resp.get('data', [])
                for order in orders:
                    if str(order.get('orderid')) == str(order_id):
                        variety = order.get('variety', '')
                        return variety == 'BO'
            return False
        except:
            return False

    def round_to_tick(self, price, tick_size=0.05):
        """Round price to the nearest tick size (0.05)"""
        return round(price / tick_size) * tick_size

    def place_sl_order(self, main_order_id, sl_price):
        """Place stop loss order with STOPLOSS variety"""
        if not self.ENABLE_TRADING:
            return "SIM_SL_" + main_order_id
            
        try:
            position = self.active_positions[main_order_id]
            symbol = position['symbol']
            token = position.get('token', '')
            quantity = position['quantity']
            
            # Fix: Round to Valid Tick Size (0.05) to prevent rejection
            sl_price = self.round_to_tick(sl_price)
            trigger_price = self.round_to_tick(sl_price + 0.05) # Trigger slightly above SL
            
            sl_params = {
                "variety": "STOPLOSS",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "SELL",
                "exchange": "NFO",
                "ordertype": "STOPLOSS_LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": str(sl_price),
                "triggerprice": str(trigger_price),
                "quantity": str(quantity)
            }
            
            print(f"[SL ORDER] Placing SL at Rs.{sl_price:.2f} (Trigger: Rs.{trigger_price:.2f})")
            response = self.client.placeOrder(sl_params)
            
            # Handle response
            if isinstance(response, str) and response and len(response) > 5:
                self.active_sl_orders[main_order_id] = response
                print(f"[SL SUCCESS] Order ID: {response}")
                return response
            
            if response and isinstance(response, dict):
                if response.get('status'):
                    data = response.get('data', {})
                    if isinstance(data, dict):
                        sl_order_id = data.get('orderid')
                    elif isinstance(data, str):
                        sl_order_id = data
                    else:
                        sl_order_id = str(data) if data else None
                    
                    if sl_order_id:
                        self.active_sl_orders[main_order_id] = sl_order_id
                        print(f"[SL SUCCESS] Order ID: {sl_order_id}")
                        return sl_order_id
                else:
                    error_msg = response.get('message', str(response))
                    print(f"[SL ERROR] {error_msg}")
                    return None
            
            print(f"[SL ERROR] Failed: {response}")
            return None
            
        except Exception as e:
            print(f"[SL ERROR] {e}")
            return None
    
    def place_target_order(self, main_order_id, target_price):
        """Place limit target order"""
        if not self.ENABLE_TRADING:
            return "SIM_TGT_" + main_order_id
            
        try:
            position = self.active_positions[main_order_id]
            symbol = position['symbol']
            token = position.get('token', '')
            quantity = position['quantity']
            
            # Fix: Round to Valid Tick Size (0.05)
            target_price = self.round_to_tick(target_price)
            
            target_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "SELL",
                "exchange": "NFO",
                "ordertype": "LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": str(target_price),
                "quantity": str(quantity)
            }
            
            print(f"[TARGET ORDER] Placing Target at Rs.{target_price:.1f}")
            response = self.client.placeOrder(target_params)
            
            if response and response.get('status'):
                target_order_id = response.get('data', {}).get('orderid')
                if target_order_id:
                    # Store target order ID
                    if not hasattr(self, 'active_target_orders'):
                        self.active_target_orders = {}
                    self.active_target_orders[main_order_id] = target_order_id
                    return target_order_id
            
            print(f"[TARGET ERROR] Failed to place target order: {response}")
            return None
            
        except Exception as e:
            print(f"[TARGET ERROR] {e}")
            return None

    def modify_sl_order(self, sl_order_id, new_sl_price, symbol):
        """Modify SL order using STOPLOSS_LIMIT (Matched with fetch script logic)"""
        if not self.ENABLE_TRADING:
            print(f"[PAPER] SL Modifed to {new_sl_price}")
            return True
            
        try:
            # Round to tick size
            new_sl_price = self.round_to_tick(new_sl_price)
            # Trigger price slightly above limit price for Sell SL
            trigger_price = self.round_to_tick(new_sl_price + 0.05)
            
            # Fetch quantity from active positions
            quantity = None
            for oid, pos in self.active_positions.items():
                if str(self.active_sl_orders.get(oid)) == str(sl_order_id):
                    quantity = str(pos['quantity'])
                    break
            
            # Fallback/Safety Check
            if not quantity or quantity == "0":
                print(f"[SL MODIFY WARN] Could not find quantity for SL Order {sl_order_id}. Defaulting to '0' (Might Fail)")
                quantity = "0"
            
            modify_params = {
                "variety": "STOPLOSS",
                "orderid": sl_order_id,
                "tradingsymbol": symbol,
                "exchange": "NFO",
                "ordertype": "STOPLOSS_LIMIT",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": quantity,
                "price": str(new_sl_price),
                "triggerprice": str(trigger_price)
            }
            
            print(f"[SL MODIFY] Price: {new_sl_price} | Trigger: {trigger_price} | Qty: {quantity}")
            
            response = self.client.modifyOrder(modify_params)
            
            if isinstance(response, str) and len(response) > 5:
                return True
            if isinstance(response, dict) and response.get('status'):
                return True
            
            # Detailed Error Handling
            error_msg = ""
            if isinstance(response, dict):
                error_msg = response.get('message', str(response))
                error_code = response.get('errorcode', '')
                if error_code:
                    error_msg = f"{error_msg} (Code: {error_code})"
            else:
                error_msg = str(response)
                
            print(f"\n❌ [SL MODIFY REJECTED] Reason: {error_msg}")
            return False
            
        except Exception as e:
            print(f"[SL MODIFY ERROR] {e}")
            return False

    def exit_position(self, order_id, reason):
        """Exit position"""
        try:
            position = self.active_positions[order_id]
            symbol = position['symbol']
            quantity = position['quantity']
            
            print(f"[EXITING] {symbol} Reason: {reason}")
            
            # Only place exit order if NOT already closed manually in broker
            if self.ENABLE_TRADING and reason != "MANUAL_EXIT_BROKER":
                exit_params = {
                    "variety": "NORMAL",
                    "tradingsymbol": symbol,
                    "symboltoken": position.get('token', ''),  # ADDED for proper exit
                    "transactiontype": "SELL",
                    "exchange": "NFO",
                    "ordertype": "MARKET",
                    "producttype": "INTRADAY",
                    "duration": "DAY",
                    "quantity": str(quantity),
                    "price": "0"
                }
                self.client.placeOrder(exit_params)
                
            # Simulate or get actual exit price with proper token
            exit_ltp = self.get_option_ltp(symbol, position.get('token', '')) or position['entry_price']
            pnl = (exit_ltp - position['entry_price']) * quantity
            
            print(f"[POSITION CLOSED] {reason}")
            print(f"   Exit Price: ₹{exit_ltp:.1f}")
            print(f"   Final P&L: ₹{pnl:+.0f}")
            
            # Finalize Excel log
            self.finalize_trade_log(order_id, exit_ltp, reason, pnl)
            
            # Cleanup
            del self.active_positions[order_id]
            
            # Cancel pending SL and Target orders
            if order_id in self.active_sl_orders and self.ENABLE_TRADING:
                try:
                    sl_order_id = self.active_sl_orders[order_id]
                    self.client.cancelOrder(sl_order_id, "NORMAL")
                    print(f"[SL CANCELLED] Order ID: {sl_order_id}")
                except Exception as cancel_err:
                    print(f"[SL CANCEL WARN] {cancel_err}")
                del self.active_sl_orders[order_id]
            
            # Cancel Target order
            if hasattr(self, 'active_target_orders') and order_id in self.active_target_orders and self.ENABLE_TRADING:
                try:
                    target_order_id = self.active_target_orders[order_id]
                    self.client.cancelOrder(target_order_id, "NORMAL")
                    print(f"[TARGET CANCELLED] Order ID: {target_order_id}")
                except Exception as cancel_err:
                    print(f"[TARGET CANCEL WARN] {cancel_err}")
                del self.active_target_orders[order_id]
            
            # Save state after exit
            self.save_state()
                    
        except Exception as e:
            print(f"[EXIT ERROR] {e}")

    def calculate_trailing_sl(self, entry_price, current_price, current_sl):
        """
        Calculate new trailing SL based on profit level
        
        THREE-PHASE TRAILING SL LOGIC (ENHANCED):
        ==========================================
        Phase 1 (7% to 19% profit):
        - Activate at 7% profit, lock 5%
        - Every 5% step, add 5% to locked profit
        - 7% -> 5% locked, 12% -> 10% locked, 17% -> 15% locked
        
        Phase 2 (20% to 29% profit):
        - Tighter trailing - 3% steps
        - 20% -> 18% locked, 23% -> 21% locked, 26% -> 24% locked
        
        Phase 3 (30%+ profit) - SUPER TIGHT:
        - Very tight trailing - 2% steps
        - 30% -> 28% locked, 32% -> 30% locked, 34% -> 32% locked
        
        Example (Entry = ₹100):
        | LTP   | Profit % | SL Price | Locked Profit | Phase |
        |-------|----------|----------|---------------|-------|
        | ₹105  | +5%      | ₹90      | No trail      | -     |
        | ₹107  | +7%  ✅  | ₹105     | 5% locked     | P1    |
        | ₹112  | +12%     | ₹110     | 10% locked    | P1    |
        | ₹117  | +17%     | ₹115     | 15% locked    | P1    |
        | ₹120  | +20%     | ₹118     | 18% locked    | P2    |
        | ₹123  | +23%     | ₹121     | 21% locked    | P2    |
        | ₹126  | +26%     | ₹124     | 24% locked    | P2    |
        | ₹129  | +29%     | ₹127     | 27% locked    | P2    |
        | ₹130  | +30%     | ₹128     | 28% locked    | P3    |
        | ₹132  | +32%     | ₹130     | 30% locked    | P3    |
        | ₹134  | +34%     | ₹132     | 32% locked    | P3    |
        | ₹140  | +40%     | ₹138     | 38% locked    | P3    |
        """
        try:
            profit_percent = ((current_price - entry_price) / entry_price) * 100
            
            # If not yet at 7% profit, keep initial SL (10% below entry)
            if profit_percent < 7:
                return current_sl, False  # (sl_price, should_modify)
            
            locked_profit_percent = 0
            
            # PHASE 3: Profit >= 30% (Super tight trailing - 2% steps)
            if profit_percent >= 30:
                # Formula: 28 + floor((profit - 30) / 2) * 2
                steps_after_30 = int((profit_percent - 30) / 2)
                locked_profit_percent = 28 + (steps_after_30 * 2)
            
            # PHASE 2: Profit 20% to <30% (Tighter trailing - 3% steps)
            elif profit_percent >= 20:
                # Formula: 18 + floor((profit - 20) / 3) * 3
                steps_after_20 = int((profit_percent - 20) / 3)
                locked_profit_percent = 18 + (steps_after_20 * 3)
            
            # PHASE 1: Profit 7% to <20% (Standard trailing - 5% steps)  
            elif profit_percent >= 7:
                # Formula: 5 + floor((profit - 7) / 5) * 5
                steps_above_7 = int((profit_percent - 7) / 5)
                locked_profit_percent = 5 + (steps_above_7 * 5)
            
            # Calculate new SL price
            new_sl = round(entry_price * (1 + locked_profit_percent / 100), 2)
            
            # Ensure safe rounding to tick
            new_sl = self.round_to_tick(new_sl)
            
            # Only modify if new SL is higher than current SL
            if new_sl > current_sl:
                return new_sl, True
            
            return current_sl, False
        except Exception as e:
            print(f"[CALC SL ERROR] {e}")
            return current_sl, False

    def update_trailing_sl(self, order_id, current_ltp, pnl_percent):
        """
        Update Trailing SL using ported logic from fetch_account_balance.py
        """
        try:
            position = self.active_positions[order_id]
            entry_price = position['entry_price']
            current_sl = position['sl_price']
            
            # Use the CALCULATE function from fetch script
            new_sl, should_modify = self.calculate_trailing_sl(entry_price, current_ltp, current_sl)

            # --- APPLY UPDATE ---
            if should_modify and new_sl > current_sl:
                # Minimum 0.5 point check to avoid micro-updates
                if (new_sl - current_sl) > 0.5:
                    position['sl_price'] = new_sl
                    # Mark trail active if we moved it
                    position['trail_active'] = True 
                    
                    self.save_state()
                    
                    sl_reason = "Trailing Logic update"
                    print(f"[SL TRAIL] {sl_reason} -> Rs.{new_sl:.1f} (Profit Locked: {((new_sl-entry_price)/entry_price)*100:.1f}%)")
                    
                    # Modify SL order in Broker
                    if order_id in self.active_sl_orders:
                        sl_order_id = self.active_sl_orders[order_id]
                        # Now uses the UPDATED modify_sl_order (Limit)
                        self.modify_sl_order(sl_order_id, new_sl, position['symbol'])
                    
        except Exception as e:
            print(f"[TRAIL ERROR] {e}")

    def verify_position_status(self):
        """Verify if active positions are still open in broker"""
        if not self.active_positions or not self.ENABLE_TRADING:
            return

        try:
            # Fetch fresh position data
            response = self.client.position()
            
            if not response or not isinstance(response, dict) or not response.get('status'):
                return
                
            positions_data = response.get('data', [])
            
            # Create a map of Token -> NetQty
            real_positions = {} 
            for pos in positions_data:
                token = pos.get('symboltoken')
                net_qty = int(pos.get('netqty', 0))
                real_positions[token] = net_qty
            
            # Check our local active positions
            params_to_remove = []
            
            for order_id, position in self.active_positions.items():
                token = position.get('token')
                symbol = position['symbol']
                
                # If token not in real_positions OR net qty is 0, it is closed
                if token in real_positions:
                    net_qty = real_positions[token]
                    if net_qty == 0:
                        print(f"\n[MANUAL EXIT DETECTED] Position for {symbol} is closed in broker")
                        params_to_remove.append(order_id)
                else:
                    # Token not found - assume closed if checking real positions
                    print(f"\n[MANUAL EXIT DETECTED] Position for {symbol} not found in broker list")
                    params_to_remove.append(order_id)
            
            # Remove closed positions
            for order_id in params_to_remove:
                self.exit_position(order_id, "MANUAL_EXIT_BROKER")
                
        except Exception as e:
            print(f"[POSITION CHECK ERROR] {e}")

    def manage_active_positions(self):
        """Monitor active positions and check order status"""
        if not self.active_positions:
            return

        # First, check if any positions were closed manually in broker
        self.verify_position_status()
        
        if not self.active_positions:
            return
        
        print(f"\n[MONITORING] {len(self.active_positions)} active trades...")
        
        # Check order book for SL/Target hits
        self.check_order_status()
        
        for order_id, position in list(self.active_positions.items()):
            symbol = position['symbol']
            entry_price = position['entry_price']
            target_price = position['target_price']
            
            current_ltp = self.get_option_ltp(symbol, position.get('token', ''))
            
            if current_ltp:
                pnl = (current_ltp - entry_price) * position['quantity']
                pnl_percent = ((current_ltp - entry_price) / entry_price) * 100
                
                print(f"  {symbol}: ₹{current_ltp:.1f} | P&L: ₹{pnl:+.0f} ({pnl_percent:+.1f}%) | SL: {position['sl_price']:.1f} | Target: {target_price:.1f}")
                
                # ========== INTERNAL TARGET CHECK (No broker order) ==========
                if current_ltp >= target_price:
                    print(f"\n[TARGET HIT] {symbol} LTP {current_ltp:.1f} >= Target {target_price:.1f}")
                    print(f"[AUTO EXIT] Placing Market Sell to close position...")
                    self.exit_position(order_id, "TARGET_HIT_INTERNAL")
                    return  # Exit after closing position
                
                # ========== INTERNAL SL CHECK (Backup if broker SL missed) ==========
                if current_ltp <= position['sl_price']:
                    print(f"\n[SL HIT] {symbol} LTP {current_ltp:.1f} <= SL {position['sl_price']:.1f}")
                    print(f"[AUTO EXIT] Internal SL triggered, closing position...")
                    self.exit_position(order_id, "SL_HIT_INTERNAL")
                    return  # Exit after closing position
                
                # Update highest price
                if current_ltp > position['highest_price']:
                    position['highest_price'] = current_ltp
                
                # Trailing SL
                self.update_trailing_sl(order_id, current_ltp, pnl_percent)
    
    def check_order_status(self):
        """Check if SL or Target orders are executed"""
        try:
            if not self.ENABLE_TRADING:
                return
                
            order_book_resp = self.client.orderBook()
            if not order_book_resp or not order_book_resp.get('status'):
                return
                
            orders = order_book_resp.get('data', [])
            
            for order_id, position in list(self.active_positions.items()):
                # Check SL order status
                if order_id in self.active_sl_orders:
                    sl_order_id = self.active_sl_orders[order_id]
                    for order in orders:
                        if str(order.get('orderid')) == str(sl_order_id):
                            if order.get('status') == 'complete':
                                print(f"[SL EXECUTED] {position['symbol']} - SL order filled")
                                self.exit_position(order_id, "SL_HIT")
                                return
                
                # Check Target order status
                if hasattr(self, 'active_target_orders') and order_id in self.active_target_orders:
                    target_order_id = self.active_target_orders[order_id]
                    for order in orders:
                        if str(order.get('orderid')) == str(target_order_id):
                            if order.get('status') == 'complete':
                                print(f"[TARGET EXECUTED] {position['symbol']} - Target order filled")
                                self.exit_position(order_id, "TARGET_HIT")
                                return
                                
        except Exception as e:
            print(f"[ORDER STATUS ERROR] {e}")

    def log_trade_to_excel(self, order_id, position):
        """Log trade to Excel"""
        try:
            if not os.path.exists(self.trade_log_file):
                wb = Workbook()
                ws = wb.active
                headers = ['Date', 'Time', 'Symbol', 'Strike', 'Type', 'Entry Price', 
                          'Qty', 'Initial SL', 'Exit Time', 'Exit Price', 'Exit Reason', 'P&L']
                ws.append(headers)
                wb.save(self.trade_log_file)
            
            wb = load_workbook(self.trade_log_file)
            ws = wb.active
            
            row_data = [
                datetime.datetime.now().strftime("%Y-%m-%d"),
                position['entry_time'].strftime("%H:%M:%S"),
                position['symbol'],
                position['strike'],
                position['option_type'],
                position['entry_price'],
                position['quantity'],
                position['sl_price'],
                '', '', '', ''
            ]
            ws.append(row_data)
            self.current_trade_row = ws.max_row
            
            wb.save(self.trade_log_file)
            print(f"[LOGGED] Trade entry saved to Excel")
            
        except Exception as e:
            print(f"[LOG ERROR] {e}")

    def finalize_trade_log(self, order_id, exit_price, exit_reason, pnl):
        """Finalize trade log"""
        try:
            if not os.path.exists(self.trade_log_file):
                return
            
            wb = load_workbook(self.trade_log_file)
            ws = wb.active
            
            # Simple assumption: Last row is the current trade if only one trade at a time
            # For robust multi-trade, we'd search for Order ID, but sticking to simple last row for now
            row = ws.max_row 
            
            ws.cell(row=row, column=9, value=datetime.datetime.now().strftime("%H:%M:%S"))  # Exit Time
            ws.cell(row=row, column=10, value=exit_price)  # Exit Price
            ws.cell(row=row, column=11, value=exit_reason)  # Exit Reason
            ws.cell(row=row, column=12, value=pnl)  # P&L
            
            wb.save(self.trade_log_file)
            print(f"[FINALIZED] Trade log updated")
            
        except Exception as e:
            print(f"[FINALIZE ERROR] {e}")

    def execute_trade(self, signal, confidence, current_price):
        """Execute trade based on signal"""
        try:
            # 1. Determine Option details
            atm_strike = round(current_price / 50) * 50
            option_type = "CE" if signal == 'BUY' else "PE"
            
            if signal == 'BUY':
                contract_strike = atm_strike
                print(f"\n[EXECUTING BUY] {atm_strike} CE for Bullish Signal")
            else:
                contract_strike = atm_strike
                print(f"\n[EXECUTING BUY] {atm_strike} PE for Bearish Signal") # Buying Put for Sell signal
            
            # 2. Find Contract
            contract = self.find_option_contract(contract_strike, option_type)
            if not contract:
                print("[ERROR] Option contract not found")
                return
            
            print(f"[CONTRACT FOUND] {contract['symbol']} ({contract['expiry']})")
            
            # 3. Place Bracket Order with SL & Target
            order_id = self.place_order(contract['symbol'], contract['token'], self.ORDER_QUANTITY, "BUY")
            
            if order_id:
                # Fetch Entry Price with Retry (No default 100)
                # Fetch Entry Price from Order Book (Most Accurate)
                print(f"[ORDER STATUS] Checking fill for SL calculation...")
                entry_price = 0
                
                # Poll for up to 10 seconds for order completion (Fast poll 0.2s)
                for attempt in range(50): 
                    try:
                        order_book_resp = self.client.orderBook()
                        if order_book_resp and order_book_resp.get('status') and order_book_resp.get('data'):
                            orders = order_book_resp['data']
                            found_order = False
                            
                            for order in orders:
                                if str(order.get('orderid')) == str(order_id):
                                    found_order = True
                                    status = order.get('status') # 'complete', 'rejected', etc.
                                    
                                    if status == 'complete':
                                        avg_price = float(order.get('averageprice', 0.0))
                                        if avg_price > 0:
                                            entry_price = avg_price
                                            print(f"[ORDER FILLED] Avg Price: {entry_price}")
                                            break # Exit inner loop if order found and filled
                            
                            if entry_price > 0:
                                break # Exit outer loop if entry price is found
                                
                    except Exception as e:
                        print(f"[POLL ERROR] {e}")
                    
                    time.sleep(0.2) # Faster polling
                
                # Fallback: Try fetching LTP if Order Book failed (e.g. order still open/batched)
                if entry_price == 0:
                    for _ in range(50): # Changed range to 50
                        time.sleep(0.2) # Changed sleep to 0.2
                        price = self.get_option_ltp(contract['symbol'])
                        if price and price > 0:
                            entry_price = price
                            print(f"[LTP FALLBACK] Fetched live price: {entry_price}")
                            break
                        print("[WARN] Retrying price fetch...")
                
                if entry_price == 0:
                    print("[ERROR] Critical: Could not fetch entry price from Order Book or LTP.")
                    print("[ACTION] Setting assumed price 100.0 to avoid Index Price SL disaster.")
                    # ABSOLUTELY DO NOT USE current_price (Index Price)
                    entry_price = 100.0 # Safer dummy value than 25000
                
                # 4. Store Position
                self.active_positions[order_id] = {
                    'symbol': contract['symbol'],
                    'token': contract['token'],  # ADDED for SL/Exit orders
                    'strike': contract_strike,
                    'option_type': option_type,
                    'quantity': self.ORDER_QUANTITY,
                    'entry_time': datetime.datetime.now(),
                    'entry_price': entry_price,
                    'sl_price': entry_price * (1 - self.stop_loss_percent/100),
                    'target_price': entry_price * (1 + self.target_percent/100),
                    'target_stage': 0, # 0=30%, 1=50%, 2=175%
                    'highest_price': entry_price,
                    'trail_active': False
                }
                
                print(f"[POSITION OPENED] ID: {order_id}")
                print(f"   Entry: ₹{entry_price:.1f}")
                print(f"   SL: ₹{self.active_positions[order_id]['sl_price']:.1f}")
                
                # 5. Log & Save State
                self.save_state()
                threading.Thread(target=self.log_trade_to_excel, args=(order_id, self.active_positions[order_id])).start()
                
                # 6. Check if Bracket Order or place separate SL/Target
                sl_price = self.active_positions[order_id]['sl_price']
                target_price = self.active_positions[order_id]['target_price']
                
                # Check if it's a Bracket Order (BO variety)
                is_bracket_order = self.check_if_bracket_order(order_id)
                
                if is_bracket_order:
                    print(f"[BRACKET ORDER] SL & Target already attached to main order")
                    print(f"  SL: Rs.{sl_price:.1f} | Target: Rs.{target_price:.1f}")
                else:
                    print(f"[PLACING SL ORDER] Target will be monitored internally...")
                    
                    # ========== SL ORDER WITH RETRY LOGIC ==========
                    sl_order_id = None
                    max_retries = 3
                    
                    for attempt in range(max_retries):
                        sl_order_id = self.place_sl_order(order_id, sl_price)
                        if sl_order_id:
                            print(f"[SL ORDER SUCCESS] Placed: {sl_order_id}")
                            break
                        else:
                            print(f"[SL ORDER FAILED] Attempt {attempt+1}/{max_retries}")
                            if attempt < max_retries - 1:
                                time.sleep(1)  # Wait before retry
                    
                    # ========== EMERGENCY EXIT IF SL FAILED ==========
                    if not sl_order_id:
                        print(f"\n[CRITICAL] SL ORDER FAILED AFTER {max_retries} ATTEMPTS!")
                        print(f"[EMERGENCY EXIT] Closing position to prevent unprotected trade...")
                        self.exit_position(order_id, "SL_PLACEMENT_FAILED")
                        return
                    
                    # ========== NO TARGET ORDER - MONITORED INTERNALLY ==========
                    # Target will be checked in manage_active_positions()
                    print(f"[TARGET MONITORING] Target Rs.{target_price:.1f} will be monitored internally")
                    print(f"[INFO] When LTP >= Target, bot will auto-exit via Market Order")
                
        except Exception as e:
            print(f"[EXECUTION ERROR] {e}")
    
    def run_sensitive_detection(self):
        """Run sensitive buyer/seller detection with multi-timeframe probability"""
        print("=" * 80)
        print("ENHANCED OPTIONS TRADING SYSTEM - CALL/PUT SIGNALS")
        print("FILTERS: 65% Score Threshold + 100-Point System")
        print("=" * 80)
        
        while True:
            try:
                current_time = datetime.datetime.now()
                
                # Skip if market closed
                if current_time.hour < 9 or current_time.hour >= 15:
                    print(f"[{current_time.strftime('%H:%M:%S')}] Market Closed")
                    time.sleep(60)
                    continue
                
                # Get data and analyze
                df = self.get_tick_data()
                result = self.enhanced_buyer_seller_analysis_sensitive(df)
                
                # Bollinger Bands trend peak filter (REMOVED)
                trend_filter = None
                
                # Pivot points analysis
                pivot_points = self.find_pivot_points(df)
                
                # MONITOR ACTIVE POSITIONS
                self.manage_active_positions()
                
                if result:
                    print(f"\n[{current_time.strftime('%H:%M:%S')}] SENSITIVE DETECTION")
                    print("-" * 60)
                    print(f"Direction: {result['direction']}")
                    print(f"Buyer Score: {result['buyer_score']:.3f} (Max: 1.000)")
                    print(f"Seller Score: {result['seller_score']:.3f} (Max: 1.000)")
                    print(f"Score Difference: {abs(result['buyer_score'] - result['seller_score']):.3f}")
                    print(f"Current Price: {result['current_price']:.1f}")
                    print(f"5-Min Price Change: {result['price_change_5min']:+.1f} points")
                    print(f"At Peak: {result.get('at_peak', False)} | At Trough: {result.get('at_trough', False)}")
                    
                    # Movement Diversion Info
                    div_data = result['methods'].get('movement_diversion', {})
                    if div_data.get('type') != 'NO_DIVERGENCE':
                        print(f"Movement Diversion: {div_data.get('type', 'NONE')} ({div_data.get('confidence', 0):.2f})")
                    
                    # Operator Activity Info
                    op_data = result['methods'].get('operator_activity', {})
                    if op_data.get('operator_score', 0) > 0.6:
                        volume_spike = op_data.get('volume_spike', 1)
                        signals = ', '.join(op_data.get('signals', []))
                        print(f"[OPERATOR] ACTIVITY: {op_data.get('direction')} (Vol: {volume_spike:.1f}x) - {signals}")
                    
                    # NEW: Pivot Points display
                    if pivot_points:
                        print(f"\n[PIVOT POINTS ANALYSIS]")
                        print("-" * 60)
                        current_price = result['current_price']
                        
                        if pivot_points['prev_support']:
                            support_dist = pivot_points['support_distance']
                            print(f"Previous Support: {pivot_points['prev_support']:.1f} (Distance: +{support_dist:.1f} points)")
                        else:
                            print(f"Previous Support: Not found")
                        
                        if pivot_points['next_resistance']:
                            resistance_dist = pivot_points['resistance_distance']
                            print(f"Next Resistance: {pivot_points['next_resistance']:.1f} (Distance: {resistance_dist:.1f} points)")
                        else:
                            print(f"Next Resistance: Not found")
                        
                        print(f"Current Price: {current_price:.1f}")
                    

                    
                    # Show method breakdown with dominance display
                    print(f"\nMethod Breakdown (DEBUG):")
                    total_buyer_contribution = 0
                    total_seller_contribution = 0
                    weights = {
                        'immediate_momentum': 0.30,
                        'volume_price_trend': 0.15, 
                        'operator_activity': 0.15,
                        'price_velocity': 0.15,
                        'candle_body_analysis': 0.10,
                        'movement_diversion': 0.08,
                        'momentum_divergence': 0.05,
                        'support_resistance': 0.02
                    }
                    
                    for method, data in result['methods'].items():
                        weight = weights.get(method, 0)
                        contribution = data['confidence'] * weight if data['direction'] != 'NEUTRAL' else 0
                        
                        # Determine dominance indicator
                        if data['direction'] == 'BUYERS':
                            total_buyer_contribution += contribution
                            dominance_indicator = "🟢 BUYERS"
                        elif data['direction'] == 'SELLERS':
                            total_seller_contribution += contribution
                            dominance_indicator = "🔴 SELLERS"
                        else:
                            dominance_indicator = "⚪ NEUTRAL"
                            
                        if method == 'movement_diversion' and 'type' in data:
                            print(f"  {method}: {dominance_indicator} ({data['confidence']:.2f}) Weight:{weight:.0%} Contrib:{contribution:.3f} - {data['type']}")
                        elif method == 'operator_activity' and 'signals' in data:
                            signals_str = ', '.join(data['signals']) if data['signals'] else 'NONE'
                            print(f"  {method}: {dominance_indicator} ({data['confidence']:.2f}) Weight:{weight:.0%} Contrib:{contribution:.3f} - {signals_str}")
                        else:
                            print(f"  {method}: {dominance_indicator} ({data['confidence']:.2f}) Weight:{weight:.0%} Contrib:{contribution:.3f}")
                    
                    # Overall dominance summary
                    if total_buyer_contribution > total_seller_contribution:
                        overall_dominance = f"🟢 BUYERS DOMINATING ({total_buyer_contribution:.3f} vs {total_seller_contribution:.3f})"
                    elif total_seller_contribution > total_buyer_contribution:
                        overall_dominance = f"🔴 SELLERS DOMINATING ({total_seller_contribution:.3f} vs {total_buyer_contribution:.3f})"
                    else:
                        overall_dominance = f"⚪ BALANCED MARKET ({total_buyer_contribution:.3f} vs {total_seller_contribution:.3f})"
                    
                    print(f"\n[DOMINANCE SUMMARY] {overall_dominance}")
                    print(f"\n[SCORE DEBUG]")
                    print(f"Total Buyer Contribution: {total_buyer_contribution:.3f}")
                    print(f"Total Seller Contribution: {total_seller_contribution:.3f}")
                    print(f"Expected Buyer Score: ~{total_buyer_contribution:.3f}")
                    print(f"Expected Seller Score: ~{total_seller_contribution:.3f}")
                    print(f"Actual Buyer Score: {result['buyer_score']:.3f}")
                    print(f"Actual Seller Score: {result['seller_score']:.3f}")
                    
                    # COMPREHENSIVE SCORING SYSTEM FOR TRADE SIGNALS
                    trade_score = self.calculate_trade_score(result, trend_filter)
                    
                    print(f"\n[TRADE SCORING SYSTEM]")
                    print("=" * 50)
                    for category, score_data in trade_score['breakdown'].items():
                        status = "[PASS]" if score_data['achieved'] else "[FAIL]"
                        print(f"{status} {category}: {score_data['current']:.1f}/{score_data['required']:.1f} ({score_data['percentage']:.1f}%)")
                    
                    print(f"\nTOTAL TRADE SCORE: {trade_score['total_score']:.1f}/100 ({trade_score['total_score']:.1f}%)")
                    print(f"TRADE THRESHOLD: 35/100 (35%) for signal generation")
                    print(f"TRADE SIGNAL: {trade_score['signal']}")
                    
                    # 35 points minimum for trade (35% of 100) - ULTRA SENSITIVE
                    min_trade_score = 35  # Was 65, now 35 for ultra-sensitive detection
                    if trade_score['total_score'] >= min_trade_score:
                        print(f"\n[TRADE APPROVED] Score: {trade_score['total_score']:.1f}/100 ({trade_score['total_score']:.1f}%)")
                        
                        # 1. INSTANT ALERT (Zero Latency Display) - UPDATED TO USE VELOCITY IF AVAILABLE
                        # Get PRICE VELOCITY data early for accurate alert
                        price_velocity_data = result['methods'].get('price_velocity', {'direction': 'NEUTRAL', 'confidence': 0})
                        velocity_direction = price_velocity_data['direction']
                        velocity_confidence = price_velocity_data['confidence']
                        
                        # Use Velocity direction for alert if strong, otherwise Score direction
                        alert_direction = velocity_direction if (velocity_confidence > 0.5 and velocity_direction in ['BUYERS', 'SELLERS']) else trade_score['direction']
                        # Map BUYERS/SELLERS to BUY/SELL for alert function
                        if alert_direction == 'BUYERS': alert_direction = 'BUY'
                        elif alert_direction == 'SELLERS': alert_direction = 'SELL'
                        
                        self.print_quick_alert(alert_direction, result['current_price'])
                        
                        # 2. CHECK VELOCITY CONDITIONS FOR TRADE TYPE (SEPARATE IF - NO FALLBACK)
                        if len(self.active_positions) == 0:
                            # Get PRICE VELOCITY for trade type decision
                            price_velocity_data = result['methods'].get('price_velocity', {'direction': 'NEUTRAL', 'confidence': 0})
                            velocity_direction = price_velocity_data['direction']
                            velocity_confidence = price_velocity_data['confidence']
                            
                            # Get BB position
                            bb_position = result.get('bb_position', 0.5)
                            
                            trade_executed = False
                            
                            # CALL CHECK: BUYERS velocity - ULTRA LOW THRESHOLD
                            if velocity_direction == 'BUYERS' and velocity_confidence > 0.25:  # Was 0.5, now 0.25
                                print(f"[AUTO TRADE] BUYERS Velocity ({velocity_confidence:.2f}) → BUY CALL (CE)")
                                self.execute_trade('BUY', trade_score['total_score'], result['current_price'])
                                trade_executed = True
                            
                            # PUT CHECK: SELLERS velocity - ULTRA LOW THRESHOLD
                            elif velocity_direction == 'SELLERS' and velocity_confidence > 0.25:  # Was 0.5, now 0.25
                                print(f"[AUTO TRADE] SELLERS Velocity ({velocity_confidence:.2f}) → BUY PUT (PE)")
                                self.execute_trade('SELL', trade_score['total_score'], result['current_price'])
                                trade_executed = True
                            
                            # VELOCITY NOT MET
                            if velocity_confidence <= 0.25 or velocity_direction not in ['BUYERS', 'SELLERS']:  # Updated threshold
                                print(f"[NO TRADE] Velocity conditions not met: {velocity_direction} ({velocity_confidence:.2f})")
                                print(f"  Need: BUYERS or SELLERS with confidence > 0.25")  # Updated message
                        else:
                            print(f"\n[AUTO TRADE SKIPPED] Position already active")
                        
                        # Generate Recommendation explicitly AFTER execution to avoid display lag
                        self.generate_trade_recommendation(result, trade_score, pivot_points)
                            
                    else:
                        print(f"\n[TRADE REJECTED] Score: {trade_score['total_score']:.1f}/100 ({trade_score['total_score']:.1f}%) - Need 35%+")
                        missing_points = min_trade_score - trade_score['total_score']
                        print(f"   Missing {missing_points:.1f} points for 35% trade signal")
                    
                    # Enhanced trading recommendation with peak detection
                    if False:  # Disabled old logic
                        
                        # Get price velocity from methods
                        price_velocity_data = result['methods'].get('price_velocity', {'confidence': 0})
                        price_velocity = price_velocity_data['confidence']
                        
                        # Get BB position
                        bb_position = trend_filter.get('position', 0.5) if trend_filter else 0.5
                        bb_middle = trend_filter.get('bb_middle', 0) if trend_filter else 0
                        current_price = result['current_price']
                        
                        if result['direction'] in ['BUYERS_DOMINATING', 'BUYERS_AT_PEAK']:
                            velocity_ok = price_velocity > 0.65
                            bb_position_ok = (current_price <= bb_middle * 1.002)
                            at_peak = result.get('at_peak', False)
                            
                            if result['direction'] == 'BUYERS_AT_PEAK':
                                print(f"\n[PEAK WARNING] BUYERS AT PEAK - High Risk Signal")
                                print(f"[WARN]  BB Position: {result.get('bb_position', 0):.2f} | At Peak: {at_peak}")
                                print(f"   Consider waiting for pullback or use smaller position")
                            
                            if not velocity_ok:
                                print(f"\n[FILTERED] BUY SIGNAL BLOCKED - Price velocity too low ({price_velocity:.2f} < 0.65)")
                            elif bb_position > 0.5 and result['direction'] != 'BUYERS_AT_PEAK':
                                print(f"\n[FILTERED] BUY SIGNAL BLOCKED - Price above BB center line")
                                print(f"           BB Position: {bb_position:.2f} (Above 0.50 center)")
                            elif trend_filter and trend_filter['at_peak'] and result['direction'] != 'BUYERS_AT_PEAK':
                                print(f"\n[FILTERED] BUY SIGNAL BLOCKED - At trend peak")
                            else:
                                signal_type = "PEAK CALL" if result['direction'] == 'BUYERS_AT_PEAK' else "CALL BUY"
                                print(f"\n[{signal_type} SIGNAL] {result['direction']}")
                                print(f"✅ Velocity: {price_velocity:.2f} | BB Position: {result.get('bb_position', 0):.2f}")
                                
                                # OPTIONS TRADE SETUP - CALL BUY
                                current_price = result['current_price']
                                
                                # Select strike prices
                                atm_strike = round(current_price / 50) * 50  # Nearest 50 strike
                                otm_call_strike = atm_strike + 50  # 50 points OTM
                                
                                print(f"\n[OPTIONS TRADE SETUP - CALL BUY]")
                                print("=" * 50)
                                print(f"Underlying Price: {current_price:.1f}")
                                print(f"Recommended Strike: {atm_strike} CE (ATM)")
                                print(f"Alternative Strike: {otm_call_strike} CE (OTM)")
                                
                                # Calculate targets and SL based on underlying movement
                                if pivot_points and pivot_points['next_resistance']:
                                    target_price = pivot_points['next_resistance']
                                    expected_move = target_price - current_price
                                else:
                                    expected_move = 50  # Default 50 points move
                                    target_price = current_price + expected_move
                                
                                if pivot_points and pivot_points['prev_support']:
                                    sl_price = pivot_points['prev_support']
                                else:
                                    sl_price = current_price - 20  # Default 20 points SL
                                
                                print(f"\n[UNDERLYING TARGETS]")
                                print(f"Target Price: {target_price:.1f} (Move: +{expected_move:.1f} points)")
                                print(f"Stop Loss Price: {sl_price:.1f}")
                                
                                print(f"\n[OPTION STRATEGY]")
                                print(f"Action: BUY {atm_strike} CE")
                                print(f"Entry: At Market Price")
                                print(f"Stop Loss: 30-40% of premium paid")
                                print(f"Target 1: 50-80% profit")
                                print(f"Target 2: 100-150% profit")
                                print(f"Time Decay Risk: Monitor closely if no movement")
                                
                        elif result['direction'] in ['SELLERS_DOMINATING', 'SELLERS_AT_TROUGH']:
                            velocity_ok = price_velocity > 0.65
                            bb_position_ok = (current_price >= bb_middle * 0.998)
                            at_trough = result.get('at_trough', False)
                            
                            if result['direction'] == 'SELLERS_AT_TROUGH':
                                print(f"\n[TROUGH WARNING] SELLERS AT TROUGH - High Risk Signal")
                                print(f"[WARN]  BB Position: {result.get('bb_position', 0):.2f} | At Trough: {at_trough}")
                                print(f"   Consider waiting for bounce or use smaller position")
                            
                            if not velocity_ok:
                                print(f"\n[FILTERED] SELL SIGNAL BLOCKED - Price velocity too low ({price_velocity:.2f} < 0.65)")
                            elif bb_position < 0.5 and result['direction'] != 'SELLERS_AT_TROUGH':
                                print(f"\n[FILTERED] SELL SIGNAL BLOCKED - Price below BB center line")
                                print(f"           BB Position: {bb_position:.2f} (Below 0.50 center)")
                            elif trend_filter and trend_filter['at_bottom'] and result['direction'] != 'SELLERS_AT_TROUGH':
                                print(f"\n[FILTERED] SELL SIGNAL BLOCKED - At trend bottom")
                            else:
                                signal_type = "TROUGH PUT" if result['direction'] == 'SELLERS_AT_TROUGH' else "PUT BUY"
                                print(f"\n[{signal_type} SIGNAL] {result['direction']}")
                                print(f"✅ Velocity: {price_velocity:.2f} | BB Position: {result.get('bb_position', 0):.2f}")
                                
                                # OPTIONS TRADE SETUP - PUT BUY
                                current_price = result['current_price']
                                
                                # Select strike prices
                                atm_strike = round(current_price / 50) * 50  # Nearest 50 strike
                                otm_put_strike = atm_strike - 50  # 50 points OTM
                                
                                print(f"\n[OPTIONS TRADE SETUP - PUT BUY]")
                                print("=" * 50)
                                print(f"Underlying Price: {current_price:.1f}")
                                print(f"Recommended Strike: {atm_strike} PE (ATM)")
                                print(f"Alternative Strike: {otm_put_strike} PE (OTM)")
                                
                                # Calculate targets and SL based on underlying movement
                                if pivot_points and pivot_points['prev_support']:
                                    target_price = pivot_points['prev_support']
                                    expected_move = current_price - target_price
                                else:
                                    expected_move = 50  # Default 50 points move
                                    target_price = current_price - expected_move
                                
                                if pivot_points and pivot_points['next_resistance']:
                                    sl_price = pivot_points['next_resistance']
                                else:
                                    sl_price = current_price + 20  # Default 20 points SL
                                
                                print(f"\n[UNDERLYING TARGETS]")
                                print(f"Target Price: {target_price:.1f} (Move: -{expected_move:.1f} points)")
                                print(f"Stop Loss Price: {sl_price:.1f}")
                                
                                print(f"\n[OPTION STRATEGY]")
                                print(f"Action: BUY {atm_strike} PE")
                                print(f"Entry: At Market Price")
                                print(f"Stop Loss: 30-40% of premium paid")
                                print(f"Target 1: 50-80% profit")
                                print(f"Target 2: 100-150% profit")
                                print(f"Time Decay Risk: Monitor closely if no movement")
                                
                    else:
                        if result['direction'] == 'BALANCED':
                            print(f"\n[NEUTRAL] MARKET BALANCED - Wait for clearer direction")
                        # Old logic disabled
                        pass
                
                time.sleep(8)  # FASTER updates - Fixed weight calculation
                
            except KeyboardInterrupt:
                print("\n[INFO] Detection stopped by user")
                break
            except Exception as e:
                print(f"[ERROR] Detection error: {e}")
                time.sleep(5)
    
    def calculate_trade_score(self, result, trend_filter):
        """Calculate simplified 100-point trade score"""
        try:
            score_breakdown = {}
            total_score = 0
            
            # Determine signal direction first
            if result['buyer_score'] > result['seller_score']:
                dominant_score = result['buyer_score']
                signal_direction = 'BUY'
            else:
                dominant_score = result['seller_score']
                signal_direction = 'SELL'
            
            # 1. Price Velocity (40 points - ULTRA LOW THRESHOLD)
            price_velocity_data = result['methods'].get('price_velocity', {'confidence': 0})
            price_velocity = price_velocity_data['confidence']
            velocity_score = 40 if price_velocity > 0.25 else 0  # Was 0.65, now 0.25
            score_breakdown['Price Velocity (>0.25)'] = {
                'current': price_velocity,
                'required': 0.25,
                'percentage': velocity_score,
                'achieved': price_velocity > 0.25
            }
            total_score += velocity_score
            
            # 2. Bollinger Band Confirmation (REMOVED)
            # 20 points reallocated to Price Velocity
            score_breakdown['Bollinger Band'] = {
                'current': 0, 'required': 0, 'percentage': 0, 'achieved': True
            }
            
            # 3. Buyer/Seller Score (15 points) - ULTRA LOW THRESHOLD
            dominance_score = 15 if dominant_score > 0.05 else 0  # Was 0.13, now 0.05
            score_breakdown['Buyer/Seller Dominance (>0.05)'] = {
                'current': dominant_score,
                'required': 0.05,
                'percentage': dominance_score,
                'achieved': dominant_score > 0.05
            }
            total_score += dominance_score
            
            # 4. Candle Body Analysis (10 points)
            candle_data = result['methods'].get('candle_body_analysis', {'confidence': 0.5, 'direction': 'NEUTRAL'})
            candle_confidence = candle_data['confidence']
            candle_direction = candle_data['direction']
            
            candle_score = 10 if (candle_confidence > 0.6 and candle_direction != 'NEUTRAL') else 0
            score_breakdown['Candle Body Analysis (>0.6)'] = {
                'current': candle_confidence,
                'required': 0.6,
                'percentage': candle_score,
                'achieved': candle_confidence > 0.6 and candle_direction != 'NEUTRAL'
            }
            total_score += candle_score
            
            # 5. Movement Diversion (10 points)
            diversion_data = result['methods'].get('movement_diversion', {'confidence': 0.5, 'type': 'NO_DIVERGENCE'})
            diversion_type = diversion_data.get('type', 'NO_DIVERGENCE')
            diversion_confidence = diversion_data['confidence']
            
            diversion_score = 10 if ('DIVERGENCE' in diversion_type and diversion_confidence > 0.65) else 0
            score_breakdown['Movement Diversion'] = {
                'current': diversion_confidence if 'DIVERGENCE' in diversion_type else 0,
                'required': 0.65,
                'percentage': diversion_score,
                'achieved': 'DIVERGENCE' in diversion_type and diversion_confidence > 0.65
            }
            total_score += diversion_score
            
            # 6. Operator Activity (10 points)
            operator_data = result['methods'].get('operator_activity', {'operator_score': 0, 'direction': 'NEUTRAL'})
            operator_score_raw = operator_data.get('operator_score', 0)
            operator_direction = operator_data['direction']
            
            operator_score = 10 if (operator_score_raw > 0.6 and operator_direction != 'NEUTRAL') else 0
            score_breakdown['Operator Activity'] = {
                'current': operator_score_raw,
                'required': 0.6,
                'percentage': operator_score,
                'achieved': operator_score_raw > 0.6 and operator_direction != 'NEUTRAL'
            }
            total_score += operator_score
            
            # 7. Volume Momentum (8 points)
            volume_data = result['methods'].get('volume_price_trend', {'confidence': 0.5, 'direction': 'NEUTRAL'})
            volume_confidence = volume_data['confidence']
            volume_direction = volume_data['direction']
            
            volume_score = 8 if (volume_confidence > 0.55 and volume_direction != 'NEUTRAL') else 0
            score_breakdown['Volume Momentum'] = {
                'current': volume_confidence,
                'required': 0.55,
                'percentage': volume_score,
                'achieved': volume_confidence > 0.55 and volume_direction != 'NEUTRAL'
            }
            total_score += volume_score
            
            # 8. Market Timing (7 points)
            current_time = datetime.datetime.now()
            market_hour = current_time.hour
            market_minute = current_time.minute
            
            # Best trading hours: 9:30-11:30 and 1:30-2:30
            prime_time = (9 <= market_hour < 11) or (13 <= market_hour < 14 and market_minute >= 30)
            timing_score = 7 if prime_time else 0
            
            score_breakdown['Market Timing'] = {
                'current': market_hour + (market_minute/60),
                'required': 10.0,
                'percentage': timing_score,
                'achieved': prime_time
            }
            total_score += timing_score
            
            # Determine final signal (Total = 100 points) - ULTRA LOW THRESHOLDS
            if total_score >= 70:  # 70%+ (was 80%)
                signal = 'STRONG_TRADE'
            elif total_score >= 35:  # 35%+ (was 65% - MAJOR REDUCTION)
                signal = 'MODERATE_TRADE'
            elif total_score >= 20:  # 20%+ (was 50%)
                signal = 'WEAK_SIGNAL'
            else:
                signal = 'NO_TRADE'
            
            return {
                'total_score': total_score,
                'signal': signal,
                'direction': signal_direction,
                'breakdown': score_breakdown
            }
            
        except Exception as e:
            print(f"[ERROR] Trade score calculation failed: {e}")
            return {'total_score': 0, 'signal': 'ERROR', 'breakdown': {}}
    
    def get_pivot_points_score(self, pivot_points, current_price, direction):
        """Calculate pivot points based scoring"""
        if not pivot_points:
            return 2
        
        try:
            if direction == 'BUY':
                # For buy, check distance to resistance (target) vs support (risk)
                resistance_dist = pivot_points.get('resistance_distance')
                support_dist = pivot_points.get('support_distance')
                
                if resistance_dist and support_dist:
                    if resistance_dist > 30 and support_dist > 15:  # Good RR
                        return 5
                    elif resistance_dist > 20:  # Decent target
                        return 3
                    else:
                        return 1
            else:  # SELL
                support_dist = pivot_points.get('support_distance')
                resistance_dist = pivot_points.get('resistance_distance')
                
                if support_dist and resistance_dist:
                    if support_dist > 30 and resistance_dist > 15:  # Good RR
                        return 5
                    elif support_dist > 20:  # Decent target
                        return 3
                    else:
                        return 1
            
            return 2  # Default
        except:
            return 2
    
    def print_quick_alert(self, direction, current_price):
        """Print instant alert without network calls (Zero Latency)"""
        try:
            atm_strike = round(current_price / 50) * 50
            if direction == 'BUY':
                print(f"\n🚀 [INSTANT ALERT] BUY NIFTY {atm_strike} CE !!!")
            else:
                print(f"\n🔻 [INSTANT ALERT] BUY NIFTY {atm_strike} PE !!!")
        except:
            pass

    def generate_trade_recommendation(self, result, trade_score, pivot_points):
        """Generate detailed trade recommendation"""
        try:
            current_price = result['current_price']
            direction = trade_score['direction']
            
            if direction == 'BUY':
                print(f"\n🚀 [CALL BUY RECOMMENDATION]")
                print("=" * 50)
                
                # Strike selection
                atm_strike = round(current_price / 50) * 50
                otm_strike = atm_strike + 50
                
                # Fetch Option Price with proper token
                current_time_str = datetime.datetime.now().strftime("%H:%M:%S")
                opt_ltp = 0
                contract = self.find_option_contract(atm_strike, 'CE')
                if contract:
                    opt_ltp = self.get_option_ltp(contract['symbol'], contract['token']) or 0
                
                print(f"Time: {current_time_str}")
                print(f"Underlying: NIFTY @ {current_price:.1f}")
                print(f"Recommended: {atm_strike} CE (ATM) @ ₹{opt_ltp:.1f}")
                print(f"Alternative: {otm_strike} CE (OTM)")
                
                # Targets
                if pivot_points and pivot_points['next_resistance']:
                    target1 = pivot_points['next_resistance']
                    target2 = target1 + 30
                else:
                    target1 = current_price + 40
                    target2 = current_price + 70
                
                sl_price = current_price - 25
                
                print(f"\n⚡ [SUGGESTED TARGETS & SL]")
                print(f"  Target 1: {target1:.1f} (Spot Level)")
                print(f"  Target 2: {target2:.1f} (Jackpot Level)")
                print(f"  🛑 HIT STOP LOSS (SPOT): {sl_price:.1f}")
                print(f"  🛑 OPTION SL: 10% of Premium Price (Auto-set)")
                
            else:  # SELL
                print(f"\n🔻 [PUT BUY RECOMMENDATION]")
                print("=" * 50)
                
                # Strike selection
                atm_strike = round(current_price / 50) * 50
                otm_strike = atm_strike - 50
                
                # Fetch Option Price with proper token
                current_time_str = datetime.datetime.now().strftime("%H:%M:%S")
                opt_ltp = 0
                contract = self.find_option_contract(atm_strike, 'PE')
                if contract:
                    opt_ltp = self.get_option_ltp(contract['symbol'], contract['token']) or 0
                
                print(f"Time: {current_time_str}")
                print(f"Underlying: NIFTY @ {current_price:.1f}")
                print(f"Recommended: {atm_strike} PE (ATM) @ ₹{opt_ltp:.1f}")
                print(f"Alternative: {otm_strike} PE (OTM)")
                
                # Targets
                if pivot_points and pivot_points['prev_support']:
                    target1 = pivot_points['prev_support']
                    target2 = target1 - 30
                else:
                    target1 = current_price - 40
                    target2 = current_price - 70
                
                sl_price = current_price + 25
                
                print(f"\n⚡ [SUGGESTED TARGETS & SL]")
                print(f"  Target 1: {target1:.1f} (Spot Level)")
                print(f"  Target 2: {target2:.1f} (Jackpot Level)")
                print(f"  🛑 HIT STOP LOSS (SPOT): {sl_price:.1f}")
                print(f"  🛑 OPTION SL: 10% of Premium Price (Auto-set)")
            
            print(f"\nRisk Management:")
            print(f"  Position Size: 1-2 lots maximum")
            print(f"  Time Decay: Monitor closely")
            print(f"  Trade Score: {trade_score['total_score']:.1f}/100 ({trade_score['total_score']:.1f}%)")
            print(f"  Threshold Met: {'YES' if trade_score['total_score'] >= 65 else 'NO'} (Need 65%+)")
            
        except Exception as e:
            print(f"[ERROR] Trade recommendation failed: {e}")

def main():
    detector = EnhancedBuyerSellerDetectionSensitive()
    if detector.session_generated:
        detector.run_sensitive_detection()
    else:
        print("[ERROR] Failed to connect")

if __name__ == "__main__":
    main()