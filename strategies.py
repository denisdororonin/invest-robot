import random
import operator
import os
import csv
from datetime import datetime
from pathlib import Path

from indicators import Indicators
from indicatorvals import IndicatorValues, IndicatorAttr, IndicatorAttrSimple, IndicatorValuesSimple, IndicatorAttrMACD, IndicatorValuesMACD, load_indicators_from_file
from candles import Tick
from strategydata import Instr
from utils import setup_logger
from globals import STRAT_ORDERS_FOLDER, MAX_PARAM0, MAX_PARAM1, STRAT_CMD_STR
from globals import OrderChangeReason, StrategyCommand
from schemas import StrategyResp

class StrategyLog:
    ticker: str = ""
    candles: Tick = []
    close_values: float = []
    params: int = [-1,-1, -1, -1]
    indicators: float = [0.0, 0.0, 0.0, 0.0]
    order: StrategyCommand = StrategyCommand.UNSPECIFIED
    time: datetime
    def __init__(self, ticker: str, candles: list, params: list, indicators: list, order: StrategyCommand):
        self.ticker = ticker
        self.candles = candles.copy()
        self.params = params.copy()
        self.indicators = indicators
        self.order = order
        self.time = candles[-1].Time
        ma_slow_param = params[1]
        self.close_values = list(map(operator.attrgetter('Close'), candles[-ma_slow_param:])).copy()

    def save_strategy_orders(self):
        logger.debug(f"Strategy: Order : {STRAT_CMD_STR[self.order]}")
        logger.debug(f"Strategy: Time  : {self.time}")
        logger.debug(f"Strategy: Params: {self.params}")
        logger.debug(f"Strategy: Indica: {self.indicators}")
        logger.debug(f"Strategy: Close : {self.close_values}")

        if not os.path.exists(STRAT_ORDERS_FOLDER): os.mkdir(STRAT_ORDERS_FOLDER)
        if not os.path.exists(STRAT_ORDERS_FOLDER + "/" + self.ticker): os.mkdir(STRAT_ORDERS_FOLDER + "/" + self.ticker)

        fileName = STRAT_ORDERS_FOLDER + '/' + self.ticker + "/" + self.ticker + '_strategy_ord.csv'
        if not Path(fileName).is_file():
            with open(fileName, 'w', newline='') as csvFile:
                historyWriter = csv.writer(csvFile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                historyWriter.writerow(['Order','Time','P1','P2','P3','P4','I1','I2','I3','I4','Close[]',])

        with open(fileName, 'a', newline='') as csvFile:
            historyWriter = csv.writer(csvFile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            historyWriter.writerow([STRAT_CMD_STR[self.order], self.time.strftime("%Y-%m-%d %H:%M:%S"),
                                    self.params[0], self.params[1], self.params[2], self.params[3], 
                                    self.indicators[0], self.indicators[1], self.indicators[2], self.indicators[3], 
                                    self.close_values])

''''
input:
    data - list of namedtple Tick with the most recent tick data: candles[biggest_index] 
    params - list of parameters in form of [23, 54, 17]. For example if I use Bill Williams oscillator it would be parameters for teeths/gums/jaws

output: 
    one simple answer - buy/sell/do nothing
'''

#logger = setup_logger("log_" + datetime.now().strftime('%Y-%m-%d'))
logger = setup_logger(__name__)

def strategy_rand(data, params) -> StrategyResp:
    #print("Function: Strategy1 called")
    #print("  --> newest candle:", data[-1])
    return StrategyResp(random.randint(0,2))

def strategy_MA_cross_price_deviation(data: Tick, params, instrument: Instr = None) -> StrategyResp:
    
    operation = StrategyCommand.UNSPECIFIED

    ma_fast_param = params[0]
    ma_slow_param = params[1]
    price_deviation_limit = float(params[2])/10.0
    calm_days_to_stop = params[3]

    trade_allowed = can_I_trade(data, price_deviation_limit, calm_days_to_stop)

    ma_fast = Indicators.sma(list(map(operator.attrgetter('Close'), data[-ma_fast_param:])), ma_fast_param)
    ma_slow = Indicators.sma(list(map(operator.attrgetter('Close'), data[-ma_slow_param:])), ma_slow_param)

    ma_fast_prev = Indicators.sma(list(map(operator.attrgetter('Close'), data[-ma_fast_param-1:-1])), ma_fast_param)
    ma_slow_prev = Indicators.sma(list(map(operator.attrgetter('Close'), data[-ma_slow_param-1:-1])), ma_slow_param)

    supposed = StrategyCommand.UNSPECIFIED

    if ma_fast_prev < ma_slow_prev and ma_fast > ma_slow:
        operation = StrategyCommand.OPEN_BUY if trade_allowed else StrategyCommand.CLOSE_SELL
    elif ma_fast_prev > ma_slow_prev and ma_fast < ma_slow:
        operation = StrategyCommand.OPEN_SELL if trade_allowed else StrategyCommand.CLOSE_BUY
    else:
        operation = StrategyCommand.UNSPECIFIED
        if trade_allowed:
            if ma_fast < ma_slow: supposed = StrategyCommand.OPEN_SELL
            elif ma_fast > ma_slow: supposed = StrategyCommand.OPEN_BUY
        else:
            supposed = StrategyCommand.UNSPECIFIED

    #print("MA_cross: Trade? ", trade_allowed, " Operation: ", operation, " Tick: ", data[-1]) #!!!!!!!!!!

    return StrategyResp(operation, supposed_open=supposed)

def strategy_ADX(data: list[Tick], params: list[int], instrument: Instr = None) -> StrategyResp:
    
    operation = StrategyCommand.UNSPECIFIED

    adx, di_plus, di_minus = get_ADX(data, params[0], instrument)
    adx_prev, _, _ = get_ADX(data[:-1], params[0], instrument)

    if di_plus > di_minus and adx > di_minus and adx > adx_prev:
        operation = StrategyCommand.OPEN_BUY
    elif di_minus > di_plus and adx > di_plus and adx > adx_prev:
        operation = StrategyCommand.OPEN_SELL
    elif di_plus < di_minus:
        operation = StrategyCommand.CLOSE_BUY
    elif di_minus < di_plus:
        operation = StrategyCommand.CLOSE_SELL
    elif adx < di_plus and adx < di_minus:
        operation = StrategyCommand.CLOSE_ALL

    logger.debug(f"strategy_ADX(): Oper={operation}, adx={adx}, di+={di_plus}, di-={di_minus}, adx_prev={adx_prev}")

    return StrategyResp(operation)

def strategy_ADX_MA(data: list, params: list, instrument: Instr = None) -> StrategyResp:

    if params[0] < 1 or params[1] < 1 or params[2] < 1:
        raise ValueError(f"strategy_ADX_MA(): bad params - {params[0]}/{params[1]}/{params[2]}")
    
    if len(data) < 4*(params[2]+1):
        raise ValueError(f"strategy_ADX_MA(): not enough data length. Len:{len(data)}. Expected: {4*(params[2]+1)}")

    adx = get_ADX(data, params[2], instrument)
    if adx < 20:
        return StrategyResp(StrategyCommand.CLOSE_ALL)

    return strategy_MA_cross_simple(data, params, instrument)

b_overbought = False
b_oversell = False
def strategy_MACD_RSI_old(data: list[Tick], params: list, instrument: Instr = None) -> StrategyResp:

    global b_overbought
    global b_oversell
    operation = StrategyCommand.UNSPECIFIED
    macd_fast   = params[0]
    macd_slow   = params[1]
    macd_signal = params[2]
    rsi_period  = params[3]

    macd_now, signal_now, _   = get_MACD(data, [macd_fast, macd_slow, macd_signal], instrument)
    macd_prev, signal_prev, _ = get_MACD(data[:-1], [macd_fast, macd_slow, macd_signal], instrument)
    rsi_now  = get_RSI(data, rsi_period, instrument)
    
    if rsi_now >= 70.0:
        b_oversell = False
        b_overbought = True
    elif rsi_now <= 30.0:
        b_oversell = True
        b_overbought = False

    logger.debug(f"strategy_MACD_RSI(): NOW  macd:{macd_now}, sign:{signal_now}, rsi:{rsi_now}")
    logger.debug(f"strategy_MACD_RSI(): PREV macd:{macd_prev}, sign:{signal_prev}")

    if macd_now > signal_now and macd_prev < signal_prev:
        if rsi_now > 30.0 and b_oversell == True:
            operation = StrategyCommand.OPEN_BUY
            #logger.info("!!!BUY!!!")
    
    elif macd_now < signal_now and macd_prev > signal_prev:
        if rsi_now < 70.0 and b_overbought == True:
            operation = StrategyCommand.OPEN_SELL
            #logger.info("!!!SELL!!!")

    return StrategyResp(operation)


def strategy_trend_pullback(candles: list[Tick], params: list[int], instrument: Instr = None) -> StrategyResp:

    # Calculate EMA values
    ema_fast = get_EMA(candles, params[0], instrument)
    ema_slow = get_EMA(candles, params[1], instrument)

    # Last closed candle (the one we're evaluating)
    last_candle = candles[-1]
    prev_candle = candles[-2]  # previous candle for engulfing check

    # TREND DETECTION
    trend_up = ema_fast > ema_slow
    trend_down = ema_fast < ema_slow

    # PULLBACK CONDITION (price near EMA20 or EMA50)
    def is_near_ema(price, ema, threshold=0.005):
        return abs(price - ema) / ema <= threshold  # within 0.5%

    close_near_ema = is_near_ema(last_candle.Close, ema_fast) or is_near_ema(last_candle.Close, ema_slow)

    # Volume filter: current volume > 1.2 * avg of last 20
    volume_avg_20 = sum(t.Volume for t in candles[-21:-1]) / 20
    strong_volume = last_candle.Volume > 1.2 * volume_avg_20

    # Candlestick body size
    def body_size(candle):
        return abs(candle.Close - candle.Open)


    # CANDLE PATTERN DETECTION: Bullish Engulfing
    bullish_engulfing = (
        prev_candle.Close < prev_candle.Open and     # red candle
        last_candle.Close > last_candle.Open and     # green candle
        last_candle.Close > prev_candle.Open and
        last_candle.Open < prev_candle.Close and
        body_size(last_candle) > 1.3 * body_size(prev_candle)) # strong engulf

    # Bearish Engulfing
    bearish_engulfing = (
        prev_candle.Close > prev_candle.Open and     # green candle
        last_candle.Close < last_candle.Open and     # red candle
        last_candle.Open > prev_candle.Close and
        last_candle.Close < prev_candle.Open and
        body_size(last_candle) > 1.3 * body_size(prev_candle)  # strong engulf
    )

    #TODO: DO WE NEED TO ADD "HAMMER"(4uptrend) and "SHOOTING STAR"(4downtrend) here?

    operation = StrategyCommand.UNSPECIFIED
    # ENTRY CONDITIONS
    if trend_up and close_near_ema and bullish_engulfing and strong_volume:
        operation = StrategyCommand.OPEN_BUY
    elif trend_down and close_near_ema and bearish_engulfing and strong_volume:
        operation = StrategyCommand.OPEN_SELL
    # EXIT CONDITIONS
    elif trend_down:
       operation = StrategyCommand.CLOSE_BUY
    elif trend_up:
        operation = StrategyCommand.CLOSE_SELL

    return StrategyResp(operation)


def get_alligator(data:Tick, params):
    
    #base params usually 13,8,5
    jawlength = 13 #params[0]
    teethlength = 8 #params[1]
    liplength = 5 #params[2]
    
    #shifts, usually 8, 5, 3 
    jawshift = 8 #params[1]
    teethshift = 5 #params[2]
    lipshift = 3 #params[3]

    #prepare data. For 1 set of jaw/teeth/lip its enough jawlength+jawshift
    ta_data = []
    ta_data.clear()
    for iter in data[-(2*jawlength+jawshift):]:
        ta_data.append((iter.High + iter.Low)/2)

    #print("Data for alligator: ", ta_data)
    gator = Indicators.alligator(ta_data, jawlength, teethlength, liplength, jawshift, teethshift, lipshift)
    #print("Gator: ", gator)
    
    return gator

def get_SMA(data: Tick, param: int, instrument: Instr = None) -> float:
    
    if instrument and instrument.use_precalculated_indicators:
        #try to get pre-calculated values of SMA.
        indicators: IndicatorValuesSimple = instrument.indicators.get("SMA", None)
        if not indicators: 
            indicators = load_indicators_from_file(instrument.ticker, "SMA")
            instrument.indicators["SMA"] = indicators
        
        #If it is not yet calculated - then calculate and store
        sma = indicators.values.get(IndicatorAttrSimple(data[-1].Time, param), -1)
        if sma == -1:
            sma = Indicators.sma(list(map(operator.attrgetter('Close'), data[-param:])), param)
            indicators.values |= {IndicatorAttrSimple(data[-1].Time, param) : sma}
            instrument.indicators_were_updated = True
    else:
        sma = Indicators.sma(list(map(operator.attrgetter('Close'), data[-param:])), param)

    return sma

def get_EMA(data: list[Tick], param: int, instrument: Instr = None) -> float:
    
    if instrument.use_precalculated_indicators:
        #try to get pre-calculated values of EMA.
        indicators: IndicatorValues = instrument.indicators.get("EMA", None)
        if not indicators: 
            indicators = load_indicators_from_file(instrument.ticker, "EMA")
            instrument.indicators["EMA"] = indicators
        #If it is not yet calculated - then calculate and store
        ema = indicators.values.get(IndicatorAttr(data[-1].Time, param), [-1,-1,-1,-1])[0]
        if ema == -1:
            ema = Indicators.ema(list(map(operator.attrgetter('Close'), data[-2*param:])), param)
            indicators.values |= {IndicatorAttr(data[-1].Time, param) : [ema, -1, -1, -1]}
            instrument.indicators_were_updated = True
    else:
        ema = Indicators.ema(list(map(operator.attrgetter('Close'), data[-2*param:])), param)

    return ema

def get_MACD(data: list[Tick], params: list[int], instrument: Instr = None):

    fast = params[0]
    slow = params[1]
    signal = params[2]
    needed_len = 2*(slow + signal)
    
    if instrument.use_precalculated_indicators:
        #try to get pre-calculated values of MACD.
        indicators: IndicatorValuesMACD = instrument.indicators.get("MACD", None)
        if not indicators: 
            indicators = load_indicators_from_file(instrument.ticker, "MACD")
            instrument.indicators["MACD"] = indicators

        #If it is not yet calculated - then calculate and store
        macd_vals = indicators.values.get(IndicatorAttrMACD(data[-1].Time, p1=fast, p2=slow, p3=signal), [-1,-1])
        if macd_vals[0] == -1:
            m_val, s_val, _ = Indicators.macd(list(map(operator.attrgetter('Close'), data[-needed_len:])), fast, slow, signal)
            indicators.values |= {IndicatorAttrMACD(data[-1].Time, p1=fast, p2=slow, p3=signal) : [m_val, s_val]}
            instrument.indicators_were_updated = True
        else:
            m_val = macd_vals[0]
            s_val = macd_vals[1]
    else:
        m_val, s_val, _ = Indicators.macd(list(map(operator.attrgetter('Close'), data[-needed_len:])), fast, slow, signal)

    return m_val, s_val, m_val-s_val

def get_RSI(data: list[Tick], period: int, instrument: Instr = None) -> float:

    if instrument.use_precalculated_indicators:
        #try to get pre-calculated values of RSI.
        indicators: IndicatorValuesSimple = instrument.indicators.get("RSI", None)
        if not indicators: 
            indicators = load_indicators_from_file(instrument.ticker, "RSI")
            instrument.indicators["RSI"] = indicators
        #If it is not yet calculated - then calculate and store
        rsi = indicators.values.get(IndicatorAttrSimple(data[-1].Time, period), -1)
        if rsi == -1:
            rsi = Indicators.rsi(list(map(operator.attrgetter('Close'), data[-period-1:])), period)
            indicators.values |= {IndicatorAttrSimple(data[-1].Time, period) : rsi}
            instrument.indicators_were_updated = True
    else:
        rsi = Indicators.rsi(list(map(operator.attrgetter('Close'), data[-period-1:])), period)

    return rsi

def get_ATR(data: list[Tick], period: int, instrument: Instr = None) -> float:

    if instrument and instrument.use_precalculated_indicators:
        #try to get pre-calculated values of ATR.
        indicators: IndicatorValuesSimple = instrument.indicators.get("ATR", None)
        if not indicators: 
            indicators = load_indicators_from_file(instrument.ticker, "ATR")
            instrument.indicators["ATR"] = indicators
        #If it is not yet calculated - then calculate and store
        atr = indicators.values.get(IndicatorAttrSimple(data[-1].Time, period), -1)
        if atr == -1:
            atr = Indicators.atr(data, period)
            indicators.values |= {IndicatorAttrSimple(data[-1].Time, period) : atr}
            instrument.indicators_were_updated = True
    else:
        atr = Indicators.atr(data, period)

    return atr

def get_Stochastic(data: list[Tick], params: list[int], instrument: Instr = None) -> float:
    
    k_period, d_period, smooth = params
    needed_len = k_period + d_period - 1

    rsi = Indicators.stochastic(list(map(operator.attrgetter('Close'), data[-needed_len:])), [k_period, d_period, smooth])

    return rsi

def get_dailypoints(data: list[Tick]) -> tuple:
    
    r1, s1, r2, s2 = Indicators.dailypivotpoints(data)

    return r1, s1, r2, s2

def get_ADX(data: list[Tick], period: int, instrument: Instr = None) -> float:

    if instrument.use_precalculated_indicators:
        #try to get pre-calculated values of ADX.
        indicators: IndicatorValues = instrument.indicators.get("ADX", None)
        if not indicators: 
            indicators = load_indicators_from_file(instrument.ticker, "ADX")
            instrument.indicators["ADX"] = indicators
        #If it is not yet calculated - then calculate and store
        adx_vals = indicators.values.get(IndicatorAttr(data[-1].Time, period), [-1,-1,-1,-1])
        if adx_vals[0] == -1:
            adx, di_plus, di_minus = Indicators.adx(low=list(map(operator.attrgetter('Low'), data[-4*(period+1):])),
                                                    high=list(map(operator.attrgetter('High'), data[-4*(period+1):])),
                                                    close=list(map(operator.attrgetter('Close'), data[-4*(period+1):])),
                                                    period=period)

            indicators.values |= {IndicatorAttr(data[-1].Time, period) : [adx, di_plus, di_minus, -1]}
            instrument.indicators_were_updated = True
        else:
            adx = adx_vals[0]
            di_plus = adx_vals[1]
            di_minus = adx_vals[2]
    else:
        adx, di_plus, di_minus = Indicators.adx(low=list(map(operator.attrgetter('Low'), data[-4*(period+1):])),
                                                high=list(map(operator.attrgetter('High'), data[-4*(period+1):])),
                                                close=list(map(operator.attrgetter('Close'), data[-4*(period+1):])),
                                                period=period)


    return adx, di_plus, di_minus

# 'min day price' to 'max day price' delta in percent, during last day of provided data set
def last_day_price_deviation(data: Tick) -> float:
    
    day_value = int(data[-1].Time.day)
    min_price = 9999999
    max_price = -1
    for i in range(len(data)-1, -1, -1):
        min_price = data[i].Close if data[i].Close < min_price else min_price
        max_price = data[i].Close if data[i].Close > max_price else max_price
        if day_value != int(data[i].Time.day):
            break
    
    return 100*(max_price-min_price)/min_price

# average price deviation for last "days" days in percent
def avg_price_deviation(data: Tick, days: int) -> float:

    deviations = []
    deviations.clear()

    day_value = int(data[-1].Time.day)
    deviations.append(last_day_price_deviation(data))
    day_count = 1
    for i in range(len(data)-1, -1, -1):
        
        if day_count >= days:
            break
        
        if day_value != int(data[i].Time.day):
            deviations.append(last_day_price_deviation(data[0:i+1]))
            day_value = int(data[i].Time.day)
            day_count += 1

    return sum(deviations)/len(deviations)

def can_I_trade(data, price_deviation_limit, calm_days_to_stop):

    return True if avg_price_deviation(data, calm_days_to_stop) >= price_deviation_limit else False

#dictionary of all strategiess
strategy_functions = {'strategy_rand': strategy_rand, 
                      "strategy_MA_cross_price_deviation" : strategy_MA_cross_price_deviation, 
                      "strategy_trend_pullback": strategy_trend_pullback,
                      "strategy_ADX" : strategy_ADX,
                      "strategy_ADX_MA" : strategy_ADX_MA,
                      "strategy_MACD_RSI" : strategy_MACD_RSI_old}