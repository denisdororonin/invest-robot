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
from utils import setup_logger, candles_until_end_of_day
from globals import STRAT_ORDERS_FOLDER, MAX_PARAM0, MAX_PARAM1, ORDER_DIR_STR, TREND_STR
from globals import OrderChangeReason, StrategyCommand, OrderStatus, PerformedAction, Trend
from strategies import get_SMA, get_EMA, get_alligator, get_MACD, get_ADX, get_RSI, get_Stochastic, get_ATR, get_dailypoints
from schemas import Order, OrderDir, StrategyResp
from readsettings import StrategySettings

logger = setup_logger(__name__)

#Simple Moving Average cross strategy
#BUY signal when fast MA crosses slow MA rom down to up
#SELL signal wnen fast MA crosses slow MA from up to down
def strategy_MA_cross(data: list[Tick], params: list[int], current_order: Order = None, instrument: Instr = None) -> StrategyResp:
    
    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED

    ma_fast = get_SMA(data, params[0], instrument)
    ma_slow = get_SMA(data, params[1], instrument)
    ma_fast_prev = get_SMA(data[:-1], params[0], instrument)
    ma_slow_prev = get_SMA(data[:-1], params[1], instrument)

    if ma_fast_prev < ma_slow_prev and ma_fast > ma_slow:
        operation = StrategyCommand.OPEN_BUY
        trend = Trend.UP
    elif ma_fast_prev > ma_slow_prev and ma_fast < ma_slow:
        operation = StrategyCommand.OPEN_SELL
        trend = Trend.DOWN
    else:
        if ma_fast < ma_slow: trend = Trend.DOWN
        elif ma_fast > ma_slow: trend = Trend.UP

    return StrategyResp(operation, ind_val=[ma_fast, ma_slow, ma_fast_prev, ma_slow_prev], trend=trend)

#Simple Moving Average cross strategy
#BUY signal when fast MA crosses slow MA rom down to up
#SELL signal wnen fast MA crosses slow MA from up to down
def strategy_MA_cross_sl_tp(data: list[Tick], params: list[int], current_order: Order = None, instrument: Instr = None) -> StrategyResp:
    
    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED
    sl = tp = -1

    ma_fast_param = params[0]
    ma_slow_param = params[1]
    atr_param = params[2]
    sl_param = params[3]
    tp_param = params[4]

    ma_fast = get_SMA(data, ma_fast_param, instrument)
    ma_slow = get_SMA(data, ma_slow_param, instrument)
    ma_fast_prev = get_SMA(data[:-1], ma_fast_param, instrument)
    ma_slow_prev = get_SMA(data[:-1], ma_slow_param, instrument)

    if ma_fast_prev < ma_slow_prev and ma_fast > ma_slow:
        operation = StrategyCommand.OPEN_BUY
        trend = Trend.UP
        atr = get_ATR(data, atr_param, instrument)
        sl = data[-1].Close - atr * (sl_param/10)
        tp = data[-1].Close + atr * (tp_param/10)

    elif ma_fast_prev > ma_slow_prev and ma_fast < ma_slow:
        operation = StrategyCommand.OPEN_SELL
        trend = Trend.DOWN
        atr = get_ATR(data, atr_param, instrument)
        sl = data[-1].Close + atr * (sl_param/10)
        tp = data[-1].Close - atr * (tp_param/10)
    else:
        if ma_fast < ma_slow: trend = Trend.DOWN
        elif ma_fast > ma_slow: trend = Trend.UP

    return StrategyResp(operation, sl=sl, tp=tp, trend=trend)

def strategy_MA_cross_sl(data: list[Tick], params: list[int], current_order: Order = None, instrument: Instr = None) -> StrategyResp:
    
    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED
    sl = -1

    ma_fast_param = params[0]
    ma_slow_param = params[1]
    atr_param = params[2]
    sl_param = params[3]

    ma_fast = get_SMA(data, ma_fast_param, instrument)
    ma_slow = get_SMA(data, ma_slow_param, instrument)
    ma_fast_prev = get_SMA(data[:-1], ma_fast_param, instrument)
    ma_slow_prev = get_SMA(data[:-1], ma_slow_param, instrument)

    if ma_fast_prev < ma_slow_prev and ma_fast > ma_slow:
        operation = StrategyCommand.OPEN_BUY
        trend = Trend.UP
        atr = get_ATR(data, atr_param, instrument)
        #sl = data[-1].Close - atr * (sl_param/10)
        sl = find_prev_swing_low(data) - atr * (sl_param/10)

    elif ma_fast_prev > ma_slow_prev and ma_fast < ma_slow:
        operation = StrategyCommand.OPEN_SELL
        trend = Trend.DOWN
        atr = get_ATR(data, atr_param, instrument)
        #sl = data[-1].Close + atr * (sl_param/10)
        sl = find_prev_swing_high(data) + atr * (sl_param/10)
    else:
        if ma_fast < ma_slow: trend = Trend.DOWN
        elif ma_fast > ma_slow: trend = Trend.UP

    return StrategyResp(operation, sl=sl, trend=trend)

def strategy_MA_ADX_sl(data: list[Tick], params: list[int], current_order: Order = None, instrument: Instr = None) -> StrategyResp:

    adx_period = params[4]
    adx, _, _  =  get_ADX(data, adx_period, instrument)

    if adx < 20:
        return StrategyResp(StrategyCommand.CLOSE_ALL, OrderChangeReason.END_TREND)
    else:
        return strategy_MA_cross_sl(data, params, current_order, instrument)

#Even more somple Moving Average cross strategy
#BUY signal when fast MA above slow MA rom down to up
#SELL signal wnen fast MA below slow MA from up to down
#do not send BUY/SELL signall when we already have order opened in right direction
def strategy_MA_cross_simple(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:
    
    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED
    ma_fast = get_SMA(data, params[0], instrument)
    ma_slow = get_SMA(data, params[1], instrument)

    if ma_fast > ma_slow:        
        operation = StrategyCommand.OPEN_BUY
        trend = Trend.UP
    elif ma_fast < ma_slow:
        operation = StrategyCommand.OPEN_SELL
        trend = Trend.DOWN
    
    #Do not send BUY/SELL orders if we already have order opened in same direction
    if current_order.status == OrderStatus.OPEN:
        if current_order.direction == OrderDir.BUY and operation == StrategyCommand.OPEN_BUY:
            operation = StrategyCommand.UNSPECIFIED
        elif current_order.direction == OrderDir.SELL and operation == StrategyCommand.OPEN_SELL:
            operation = StrategyCommand.UNSPECIFIED

    return StrategyResp(operation, ind_val=[ma_fast, ma_slow, -1, -1], trend=trend)

#Volume increase based Moving Average strategy
#When Volume raises above last 3 values and it raises "volume_edge" times more
#we check trend direction: if MA Fast > MA slow then BUY, else SELL
#This strategy MUST be supported by eithr SL/TP/Trail stops....
def strategy_MA_Volume(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:

    ma_fast_param  = params[0]
    ma_slow_param  = params[1]
    vol_edge_param = params[2]

    order: StrategyCommand = StrategyCommand.UNSPECIFIED

    #do not use pre-calculated indicators here. Volumes are not there!
    #I use ma_fast_param here to get avarage Volume value
    #average_volume = Indicators.sma(list(map(operator.attrgetter('Volume'), data[-ma_fast_param-1:-1])), ma_fast_param)
    #if data[-1].Volume > vol_edge_param*average_volume: #max(data[-2].Volume, data[-3].Volume, data[-4].Volume):
    
    if data[-1].Volume > vol_edge_param*max(data[-2].Volume, data[-3].Volume, data[-4].Volume):
        ma_fast = get_SMA(data, ma_fast_param, instrument)
        ma_slow = get_SMA(data, ma_slow_param, instrument)
        if ma_fast > ma_slow: 
            order = StrategyCommand.OPEN_BUY
        elif ma_fast < ma_slow:
            order = StrategyCommand.OPEN_SELL
        
    return StrategyResp(order, tp=-1, sl=-1)

def strategy_MA_Volume_sl(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:

    ma_fast_param  = params[0]
    ma_slow_param  = params[1]
    vol_edge_param = params[2]
    sl_param = params[3]
    atr_param = 14

    order: StrategyCommand = StrategyCommand.UNSPECIFIED
    sl = -1

    if data[-1].Volume > vol_edge_param*max(data[-2].Volume, data[-3].Volume, data[-4].Volume):
        ma_fast = get_SMA(data, ma_fast_param, instrument)
        ma_slow = get_SMA(data, ma_slow_param, instrument)
        if ma_fast > ma_slow: 
            order = StrategyCommand.OPEN_BUY
            atr = get_ATR(data, atr_param, instrument)
            sl = find_prev_swing_low(data) - atr * (sl_param/10)
        elif ma_fast < ma_slow:
            order = StrategyCommand.OPEN_SELL
            atr = get_ATR(data, atr_param, instrument)
            sl = find_prev_swing_high(data) + atr * (sl_param/10)

    return StrategyResp(order, tp=-1, sl=sl)

def strategy_EMA_cross(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:
    
    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED

    ema_fast = get_EMA(data, params[0], instrument)
    ema_slow = get_EMA(data, params[1], instrument)
    ema_fast_prev = get_EMA(data[:-1], params[0], instrument)
    ema_slow_prev = get_EMA(data[:-1], params[1], instrument)

    if ema_fast_prev < ema_slow_prev and ema_fast > ema_slow:
        operation = StrategyCommand.OPEN_BUY
    elif ema_fast_prev > ema_slow_prev and ema_fast < ema_slow:
        operation = StrategyCommand.OPEN_SELL
    else:
        operation = StrategyCommand.UNSPECIFIED
        if ema_fast < ema_slow: trend = Trend.DOWN
        elif ema_fast > ema_slow: trend = Trend.UP

    return StrategyResp(operation, ind_val=[ema_fast, ema_slow, ema_fast_prev, ema_slow_prev], trend=trend)

#Even more somple EMA cross strategy
#BUY signal when fast EMA above slow EMA rom down to up
#SELL signal wnen fast EMA below slow EMA from up to down
#do not send BUY/SELL signall when we already have order opened in right direction
def strategy_EMA_cross_simple(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:
    
    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED
    ema_fast = get_EMA(data, params[0], instrument)
    ema_slow = get_EMA(data, params[1], instrument)

    if ema_fast > ema_slow:        
        operation = StrategyCommand.OPEN_BUY
        trend = Trend.UP
    elif ema_fast < ema_slow:
        operation = StrategyCommand.OPEN_SELL
        trend = Trend.DOWN
    
    #Do not send BUY/SELL orders if we already have order opened in same direction
    if current_order.status == OrderStatus.OPEN:
        if current_order.direction == OrderDir.BUY and operation == StrategyCommand.OPEN_BUY:
            operation = StrategyCommand.UNSPECIFIED
        elif current_order.direction == OrderDir.SELL and operation == StrategyCommand.OPEN_SELL:
            operation = StrategyCommand.UNSPECIFIED

    return StrategyResp(operation, ind_val=[ema_fast, ema_slow, -1, -1], trend=trend)

def strategy_Bull_Bear_reverse(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:

    operation = StrategyResp(StrategyCommand.UNSPECIFIED)

    angulation = params[0]
    min_price_step = 1.0/float(params[1])
    median_price = (data[-1].High + data[-1].Low)/2

    #Bull reverse (expect price to go UP)
    if data[-1].Low < data[-2].Low and data[-2].Low < data[-3].Low and data[-1].Close > (data[-1].Low + (data[-1].High - data[-1].Low)/2):
        gator = get_alligator(data, params)
        #print("Bull reverse (", data[-1].Time, "): ", data[-3].Close,  " ", data[-2].Close, " ", data[-1].Close, "Alligator: ", gator, " Angulation: ", ((gator[1] - median_price)/min_price_step))
        
        if (gator[1] - median_price)/min_price_step > angulation: #buy signal
            operation = StrategyResp(StrategyCommand.OPEN_BUY, open=(data[-1].High + min_price_step), sl=(data[-1].Low - min_price_step))

    #Bear reverse (expect price to go DOWN)
    elif data[-1].High > data[-2].High and data[-2].High > data[-3].High and data[-1].Close < (data[-1].Low + (data[-1].High - data[-1].Low)/2):
        gator = get_alligator(data, params)
        #print("Bear reverse (", data[-1].Time, "): ", data[-3].Close,  " ", data[-2].Close, " ", data[-1].Close, "Alligator: ", gator, " Angulation: ", ((median_price - gator[1])/min_price_step))

        if (median_price - gator[1])/min_price_step > angulation: #sell signal
            operation = StrategyResp(StrategyCommand.OPEN_SELL, open=(data[-1].Low-min_price_step), sl=(data[-1].High + min_price_step))

    #TODO: this is only entry strategy now (and not full)
    # need to:
    # 1 - confirm entrance condition as recommended by Willliams
    # 2 - develop exit condition as recommended by Williams

    return operation

def strategy_MACD(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:

    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED

    #main line (mline) - fast, signal line (sline) - slow
    mline, sline, _ = get_MACD(data, params, instrument)
    mline_prev, sline_prev, _ = get_MACD(data[:-1], params, instrument)

    if mline_prev < sline_prev and mline > sline:
        operation = StrategyCommand.OPEN_BUY
    elif mline_prev > sline_prev and mline < sline:
        operation = StrategyCommand.OPEN_SELL
    else:
        operation = StrategyCommand.UNSPECIFIED
        if mline < sline: trend = Trend.DOWN
        elif mline > sline: trend = Trend.UP

    return StrategyResp(operation, ind_val=[mline, sline, mline_prev, sline_prev], trend=trend)

def strategy_MACD_sl_tp(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:

    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED
    sl = tp = -1

    atr_param = params[3]
    sl_param = params[4]
    tp_param = params[5]

    #main line (mline) - fast, signal line (sline) - slow
    mline, sline, _ = get_MACD(data, params[0:3], instrument)
    mline_prev, sline_prev, _ = get_MACD(data[:-1], params[0:3], instrument)

    if mline_prev < sline_prev and mline > sline:
        operation = StrategyCommand.OPEN_BUY
        trend = Trend.UP
        atr = get_ATR(data, atr_param, instrument)
        sl = data[-1].Close - atr * (sl_param/10)
        tp = data[-1].Close + atr * (tp_param/10)

    elif mline_prev > sline_prev and mline < sline:
        operation = StrategyCommand.OPEN_SELL
        trend = Trend.DOWN
        atr = get_ATR(data, atr_param, instrument)
        sl = data[-1].Close + atr * (sl_param/10)
        tp = data[-1].Close - atr * (tp_param/10)
    else:
        operation = StrategyCommand.UNSPECIFIED
        if mline < sline: trend = Trend.DOWN
        elif mline > sline: trend = Trend.UP

    return StrategyResp(operation, ind_val=[mline, sline, mline_prev, sline_prev], trend=trend, sl=sl, tp=tp)


def strategy_MACD_simple(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:

    operation = StrategyCommand.UNSPECIFIED
    trend = Trend.UNSPECIFIED
    #main line (mline) - fast, signal line (sline) - slow
    mline, sline, _ = get_MACD(data, params, instrument)
    if mline > sline:
        operation = StrategyCommand.OPEN_BUY
        trend = Trend.UP
    elif mline < sline:
        operation = StrategyCommand.OPEN_SELL
        trend = Trend.DOWN

    #Do not send BUY/SELL orders if we already have order opened in same direction
    if current_order.status == OrderStatus.OPEN:
        if current_order.direction == OrderDir.BUY and operation == StrategyCommand.OPEN_BUY:
            operation = StrategyCommand.UNSPECIFIED
        elif current_order.direction == OrderDir.SELL and operation == StrategyCommand.OPEN_SELL:
            operation = StrategyCommand.UNSPECIFIED

    return StrategyResp(operation, ind_val=[mline, sline, -1, -1], trend=trend)

def strategy_MACD_RSI(data: list[Tick], params: list, current_order: Order, instrument: Instr = None) -> StrategyResp:

    operation = StrategyCommand.UNSPECIFIED
    macd_fast   = params[0]
    macd_slow   = params[1]
    macd_signal = params[2]
    rsi_period  = params[3]

    macd_now, signal_now, hist_now   = get_MACD(data, [macd_fast, macd_slow, macd_signal], instrument)
    macd_prev, signal_prev, hist_prev = get_MACD(data[:-1], [macd_fast, macd_slow, macd_signal], instrument)
    rsi_now  = get_RSI(data, rsi_period, instrument)
    
    logger.debug(f"strategy_MACD_RSI(): NOW  macd:{macd_now}, sign:{signal_now}")
    logger.debug(f"strategy_MACD_RSI(): PREV macd:{macd_prev}, sign:{signal_prev}")

    #check take profit condition for this strategy
    if current_order.status == OrderStatus.OPEN:
        if current_order.direction == OrderDir.BUY and (rsi_now > 70 or abs(hist_now) < abs(hist_prev)):
            return StrategyResp(cmd = StrategyCommand.CLOSE_BUY, reason=OrderChangeReason.END_TREND)
        elif  current_order.direction == OrderDir.SELL and (rsi_now < 30 or abs(hist_now) < abs(hist_prev)):
            return StrategyResp(cmd=StrategyCommand.CLOSE_SELL, reason=OrderChangeReason.END_TREND)

    #check open order conditon for this strategy
    if macd_now > signal_now and macd_prev < signal_prev:
        if 70.0 >= rsi_now >= 30.0:
            if data[-1].Close > get_EMA(data, 200, instrument):
                operation = StrategyCommand.OPEN_BUY
    
    elif macd_now < signal_now and macd_prev > signal_prev:
        if 70.0 >= rsi_now >= 30.0:
            if data[-1].Close < get_EMA(data, 200, instrument):
                operation = StrategyCommand.OPEN_SELL

    return StrategyResp(operation)


#SPECIAL STRATEGIES
def strategy_ROSN(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:

    if current_order.status == OrderStatus.OPEN:
        return StrategyResp(StrategyCommand.UNSPECIFIED)

    b_Trend = b_ema_cross_up = b_ema_cross_down = False
    operation = StrategyCommand.UNSPECIFIED
    sl = tp = -1

    #Dynamic params (from settings)
    ema_fast_period: int = params[0]
    ema_slow_period: int = params[1]
    rsi_period: int =      params[2]
    stoch_k_period: int =  params[3]
    stoch_d_period: int =  params[4]
    adx_period: int =      params[5]
    atr_period: int =      params[6]
    
    #Static params
    rsi_buy: float = 30
    rsi_sell: float = 70
    stoch_buy: float = 20
    stoch_sell: float = 80
    adx_trend_threshold: float = 25.0
    sl_mult_meanrev: float = 1.0
    tp_mult_meanrev: float = 1.5
    sl_mult_momo: float = 0.75
    tp_mult_momo: float = 2.0

    adx, _, _  =        get_ADX(data, adx_period, instrument)
    ema_fast =          get_EMA(data, ema_fast_period, instrument)
    ema_slow =          get_EMA(data, ema_slow_period, instrument)
    ema_fast_prev =     get_EMA(data[:-1], ema_fast_period, instrument)
    ema_slow_prev =     get_EMA(data[:-1], ema_slow_period, instrument)
    _, _, macd_hist =   get_MACD(data, [12, 26, 9], instrument)
    rsi =               get_RSI(data, rsi_period, instrument)
    stochastic_k, _ =   get_Stochastic(data, [stoch_k_period, stoch_d_period, 1], instrument)
    atr =               get_ATR(data, atr_period, instrument)
    #dp_r1, dp_s1, _, _ = get_dailypoints(data)

    logger.debug(f"==>> adx={round(adx,2)}, emaf={round(ema_fast,2)}, emas={round(ema_slow,2)}, emaf_p={round(ema_fast_prev,2)}, emas_p={round(ema_slow_prev,2)}, macd_h={round(macd_hist,2)}, rsi={round(rsi,2)}, sto_k={round(stochastic_k,2)}, atr={round(atr,2)}({round(100*atr/data[-1].Close, 2)}%)")    
        
    if ema_fast_prev < ema_slow_prev and ema_fast > ema_slow:
        b_ema_cross_up = True
    elif ema_fast_prev > ema_slow_prev and ema_fast < ema_slow:
        b_ema_cross_down = True

    #regime
    b_Trend = (adx > adx_trend_threshold)

    # Momentum signals (require cross + MACD confirmation)
    b_MO_Long =  (b_Trend and b_ema_cross_up and macd_hist > 0)
    b_MO_Short = (b_Trend and b_ema_cross_down and macd_hist < 0)

    # Mean-reversion signals
    b_MR_Long = (not b_Trend and (rsi < rsi_buy or stochastic_k < stoch_buy) and data[-1].Close <= ema_fast)
    b_MR_Short = (not b_Trend and (rsi > rsi_sell or stochastic_k > stoch_sell) and data[-1].Close >= ema_fast)

    #logger.info(f"==>> trend={b_Trend}, MO_Long={b_MO_Long}, MO_Short={b_MO_Short}, MR_Long={b_MR_Long}, MR_Short={b_MR_Short}")
    
    if b_MO_Long and current_order.last_action != PerformedAction.CLOSED_BUY_SL:
        operation = StrategyCommand.OPEN_BUY
        sl = data[-1].Close - sl_mult_momo*atr
        tp = data[-1].Close + tp_mult_momo*atr
        logger.error(f"==>> BUY MO, sl={round(sl,2)}, tp={round(tp,2)}")
    elif b_MO_Short and current_order.last_action != PerformedAction.CLOSED_SELL_SL:
        operation = StrategyCommand.OPEN_SELL
        sl = data[-1].Close + sl_mult_momo*atr
        tp = data[-1].Close - tp_mult_momo*atr
        logger.error(f"==>> SELL MO, sl={round(sl,2)}, tp={round(tp,2)}")
    elif b_MR_Long and current_order.last_action != PerformedAction.CLOSED_BUY_SL:
        operation = StrategyCommand.OPEN_BUY
        sl = data[-1].Close - sl_mult_meanrev*atr
        tp = data[-1].Close + tp_mult_meanrev*atr
        logger.error(f"==>> BUY MR, sl={round(sl,2)}, tp={round(tp,2)}")
    elif b_MR_Short and current_order.last_action != PerformedAction.CLOSED_SELL_SL:
        operation = StrategyCommand.OPEN_SELL
        sl = data[-1].Close + sl_mult_meanrev*atr
        tp = data[-1].Close - tp_mult_meanrev*atr
        logger.error(f"==>> SELL MR, sl={round(sl,2)}, tp={round(tp,2)}")

    return StrategyResp(cmd=operation, sl=sl, tp=tp)

def strategy_SBER(data: list[Tick], params: list[int], current_order: Order, instrument: Instr = None) -> StrategyResp:

    sl = tp = -1
    operation = StrategyCommand.UNSPECIFIED

    ema_fast_period = 50
    ema_slow_period = 200
    adx_period = 14
    rsi_period = 14
    atr_period = 14
    adx_threshold = 25
    max_holding_bars = 8  # time exit if trade doesn't develop
    sl_atr_mult = 1.2
    tp_atr_mult = 2.5

    ema_fast =          get_EMA(data, ema_fast_period, instrument)
    ema_slow =          get_EMA(data, ema_slow_period, instrument)
    adx, _, _  =        get_ADX(data, adx_period, instrument)
    rsi =               get_RSI(data, rsi_period, instrument)
    atr =               get_ATR(data, atr_period, instrument)

    #Long
    if ema_fast > ema_slow and adx >= adx_threshold:
        if abs(data[-1].Close - ema_fast) <= 0.5*atr and 30 <= rsi <= 60:
            operation = StrategyCommand.OPEN_BUY
            sl = data[-1].Close - sl_atr_mult*atr
            tp = data[-1].Close + tp_atr_mult*atr
            logger.info(f"==>> BUY, sl={round(sl,2)}, tp={round(tp,2)}")
    #Short
    elif ema_fast < ema_slow and adx >= adx_threshold:
        if abs(data[-1].Close - ema_fast) <= 0.5*atr and 40 <= rsi <= 70:
            operation = StrategyCommand.OPEN_SELL
            sl = data[-1].Close + sl_atr_mult*atr
            tp = data[-1].Close - tp_atr_mult*atr
            logger.info(f"==>> SELL, sl={round(sl,2)}, tp={round(tp,2)}")
    #manage open orders
    #TODO: close order after 8 hours anyway
    elif adx < 20 and current_order.status == OrderStatus.OPEN:
        operation = StrategyCommand.CLOSE_ALL

    return StrategyResp(cmd=operation, sl=sl, tp=tp)

#dictionary of all strategies
strategy_functions = {
                      "strategy_MA_cross" : strategy_MA_cross,
                      "strategy_MA_cross_sl_tp" : strategy_MA_cross_sl_tp,
                      "strategy_MA_cross_sl" : strategy_MA_cross_sl,
                      "strategy_MA_cross_simple" : strategy_MA_cross_simple,
                      "strategy_MA_Volume": strategy_MA_Volume,
                      "strategy_MA_Volume_sl": strategy_MA_Volume_sl,
                      "strategy_MA_ADX_sl": strategy_MA_ADX_sl,
                      "strategy_EMA_cross" : strategy_EMA_cross,
                      "strategy_EMA_cross_simple" : strategy_EMA_cross_simple,
                      "strategy_MACD" : strategy_MACD,
                      "strategy_MACD_sl_tp" : strategy_MACD_sl_tp,
                      "strategy_MACD_simple" : strategy_MACD_simple,
                      "strategy_MACD_RSI" : strategy_MACD_RSI,
                      "strategy_ROSN": strategy_ROSN,
                      "strategy_SBER": strategy_SBER,
                      }

#slp - percent of price, for ex 5%
def calc_sl(data: list[Tick], cmd: StrategyCommand, slp: int, method: str, instrument: Instr) -> float:
    sl = -1
    atr_period = 14
    if slp > 0 and method != "atr":
        if   cmd == StrategyCommand.OPEN_BUY:  sl = data[-1].Close*(1 - slp/100.0)
        elif cmd == StrategyCommand.OPEN_SELL: sl = data[-1].Close*(1 + slp/100.0)
        else: sl = -1
    elif slp > 0 and method == "atr": #for atr, sl parameter expected to be 10 times more. Fox ex, 15 means 1.5 atr
        atr = get_ATR(data, atr_period, instrument)
        if   cmd == StrategyCommand.OPEN_BUY:  sl = data[-1].Close - atr * (slp/10)
        elif cmd == StrategyCommand.OPEN_SELL: sl = data[-1].Close + atr * (slp/10)
        else: sl = -1

    return sl

#slp - atr value miltiplier
def calc_sl_atr(candles: list[Tick], cmd: StrategyCommand, atr_period: int, slp: int) -> float:
    sl = -1
    if slp > 0:
        if   cmd == StrategyCommand.OPEN_BUY:
            sl = candles[-1].Close - Indicators.atr(candles, atr_period) * slp #stop_loss/slp becomes multiplier of ATR value here
        elif cmd == StrategyCommand.OPEN_SELL:
            sl = candles[-1].Close + Indicators.atr(candles, atr_period) * slp #stop_loss/slp becomes multiplier of ATR value here

    return sl

#tpp - percent of price, for ex 5%
def calc_tp(data: list[Tick], cmd: StrategyCommand, tpp: int, method: str, instrument: Instr) -> float:
    tp = -1
    atr_period = 14
    if tpp > 0 and method != "atr":
        if   cmd == StrategyCommand.OPEN_BUY:  tp = data[-1].Close*(1 + tpp/100.0)
        elif cmd == StrategyCommand.OPEN_SELL: tp = data[-1].Close*(1 - tpp/100.0)
        else: tp = -1
    elif tpp > 0 and method == "atr":
        atr = get_ATR(data, atr_period, instrument)
        if   cmd == StrategyCommand.OPEN_BUY:  tp = data[-1].Close + atr * (tpp/10)
        elif cmd == StrategyCommand.OPEN_SELL: tp = data[-1].Close - atr * (tpp/10)
        else: tp = -1

    return tp

def if_sl_condition(candle: Tick, current_order: Order) -> bool:

    b_sl = False
    if current_order.sl > 0 and current_order.status == OrderStatus.OPEN:        
        if current_order.direction == OrderDir.BUY and candle.Low <= current_order.sl:
            b_sl = True
            logger.debug(f"if_sl_condition(): STOPLOSS hit on BUY order. Closing price={candle.Close}, SL={current_order.sl}")
        elif current_order.direction == OrderDir.SELL and candle.High >= current_order.sl:
            b_sl = True
            logger.debug(f"if_sl_condition(): STOPLOSS hit on SELL order. Closing price={candle.Close}, SL={current_order.sl}")
    return b_sl

def if_tp_condition(candle: Tick, current_order: Order) -> bool:

    b_tp = False
    if current_order.tp > 0 and current_order.status == OrderStatus.OPEN:
        if current_order.direction == OrderDir.BUY and candle.Close >= current_order.tp: #candle.High >= current_order.tp:
            b_tp = True
            logger.debug(f"if_tp_condition(): TAKEPROFIT hit on BUY order. Closing. price={candle.Close}, TP={current_order.tp}")
        elif current_order.direction == OrderDir.SELL and candle.Close <= current_order.tp: #candle.Low <= current_order.tp:
            b_tp = True
            logger.debug(f"if_tp_condition(): TAKEPROFIT hit on SELL order. Closing. price={candle.Close}, TP={current_order.tp}")
    return b_tp

def trail_stops(candle: Tick, new_sl: float, current_order: Order) -> bool:

    b_updated = False
    if current_order.sl > 0 and current_order.status == OrderStatus.OPEN:
        if current_order.direction == OrderDir.BUY and new_sl > current_order.sl:
            logger.debug(f"trail_stops(): changed STOP LOSS for BUY order. Price:{candle.Close}, Old SL:{current_order.sl}, New SL:{new_sl}")
            current_order.sl = new_sl
            b_updated = True       
        elif current_order.direction == OrderDir.SELL and new_sl < current_order.sl:
            logger.debug(f"trail_stops(): changed STOP LOSS for SELL order. Price:{candle.Close}, Old SL:{current_order.sl}, New SL:{new_sl}")
            current_order.sl = new_sl
            b_updated = True
    return b_updated

def find_prev_swing_low(candles: list[Tick]) -> float:

    swing_low = candles[-1].Low
    for i in range(-3, -len(candles)+2, -1):
        if candles[i].Low == min(candles[i-2].Low, candles[i-1].Low, candles[i].Low, candles[i+1].Low, candles[i+2].Low):
            swing_low = candles[i].Low
            break
    return swing_low

def find_prev_swing_high(candles: list[Tick]) -> float:

    swing_high = candles[-1].High
    for i in range(-3, -len(candles)+2, -1):
        if candles[i].High == max(candles[i-2].High, candles[i-1].High, candles[i].High, candles[i+1].High, candles[i+2].High):
            swing_low = candles[i].High
            break
    return swing_high


def b_end_of_day_closing(candle: Tick, settings: StrategySettings, instrument: Instr):

    b_eod = False
    if settings.close_shorts_on_day_end:
        candles_before_mrkt_close = candles_until_end_of_day(candle.Time, instrument.day_end, settings.candles_int)
        if candles_before_mrkt_close <= 1:
            b_eod = True
            logger.debug(f"b_end_of_day_closing(): Day end close SELL order: {candle.Time}")
    return b_eod


def run_strategy(candles: list[Tick], params: list, settings: StrategySettings, instrument: Instr, current_order: Order, only_sl_tp_check: bool = False) -> StrategyResp:

    #check SL and TP conditions
    if if_sl_condition(candles[-1], current_order):
        return StrategyResp(StrategyCommand.CLOSE_ALL, OrderChangeReason.STOP_LOSS)
    if if_tp_condition(candles[-1], current_order):
        return StrategyResp(StrategyCommand.CLOSE_ALL, OrderChangeReason.TAKE_PROFIT)
    
    if only_sl_tp_check:
        return StrategyResp(StrategyCommand.UNSPECIFIED)

    #check is it is end of day and if we need to close active SELL order
    b_eod = b_end_of_day_closing(candles[-1], settings, instrument)
    if b_eod and current_order.direction == OrderDir.SELL and current_order.status == OrderStatus.OPEN:
        return StrategyResp(StrategyCommand.CLOSE_SELL, OrderChangeReason.END_DAY)

    #run strategy
    resp: StrategyResp = strategy_functions[settings.strategy_name](candles, params, current_order, instrument)

    #set SL if SL enabled in settings, and strategy generated BUY/SELL order request (and didn't put SL by itself)
    if resp.cmd in (StrategyCommand.OPEN_BUY, StrategyCommand.OPEN_SELL) and settings.stop_loss > 0:
        if resp.sl < 0: #strategy didn't set SL. Don't touch it otherwise
            resp.sl = calc_sl(candles, resp.cmd, settings.stop_loss, settings.sl_tp_method, instrument)

    #set TP if TP enabled in settings, and strategy generated BUY/SELL order request (and didn't put TP by itself)
    if resp.cmd in (StrategyCommand.OPEN_BUY, StrategyCommand.OPEN_SELL) and settings.take_prof > 0:
        if resp.tp < 0: #strategy didn't set TP. Don't touch it otherwise
            resp.tp = calc_tp(candles, resp.cmd, settings.take_prof, settings.sl_tp_method, instrument)

    #trail stops if we have active order, strategy didn't request change, trail stops enabled in settings
    if settings.trail_stops and resp.cmd == StrategyCommand.UNSPECIFIED and current_order.status == OrderStatus.OPEN:
        if settings.sl_tp_method == "atr":
            new_sl = calc_sl_atr(candles, current_order.direction, params[0], settings.stop_loss)
        else:
            new_sl = calc_sl(candles, current_order.direction, settings.stop_loss, settings.sl_tp_method, instrument)

        if trail_stops(candles[-1], new_sl, current_order):
            resp.sl = current_order.sl

    #Process strategy command (set reason, update command in special cases)
    if resp.cmd == StrategyCommand.OPEN_BUY:
        if current_order.status == OrderStatus.OPEN:
            if current_order.direction == OrderDir.SELL:
                resp.reason = OrderChangeReason.CHANGE_DIRECTION
            elif current_order.direction == OrderDir.BUY:
                resp.cmd = StrategyCommand.UNSPECIFIED
                resp.reason = OrderChangeReason.CONTINUE_TREND
            else:
                logger.error(f"run_strategy(): new order - BUY, cur order status - OPEN, order dir wrong - {ORDER_DIR_STR[current_order.direction]}")
                resp.reason = OrderChangeReason.UNSPECIFIED
        elif current_order.status == OrderStatus.CLOSED:
            resp.reason = OrderChangeReason.NEW_TREND

    elif resp.cmd == StrategyCommand.OPEN_SELL:
        if current_order.status == OrderStatus.OPEN:
            if b_eod:
                resp.cmd = StrategyCommand.CLOSE_ALL #ALL is intentianal. Even if current order is BUY!
                resp.reason = OrderChangeReason.END_DAY
            else:
                if current_order.direction == OrderDir.BUY:
                    resp.reason = OrderChangeReason.CHANGE_DIRECTION
                elif current_order.direction == OrderDir.SELL:
                    resp.cmd = StrategyCommand.UNSPECIFIED
                    resp.reason = OrderChangeReason.CONTINUE_TREND
                else:
                    logger.error(f"run_strategy(): new order - SELL, cur order status - OPEN, order dir wrong - {ORDER_DIR_STR[current_order.direction]}")
                    resp.reason = OrderChangeReason.UNSPECIFIED
        elif current_order.status == OrderStatus.CLOSED:
            if not b_eod: 
                resp.reason = OrderChangeReason.NEW_TREND
            else:
                resp.cmd = StrategyCommand.UNSPECIFIED

    elif resp.cmd in (StrategyCommand.CLOSE_BUY, StrategyCommand.CLOSE_SELL, StrategyCommand.CLOSE_ALL):
        if current_order.status == OrderStatus.OPEN:
            if resp.reason == OrderChangeReason.UNSPECIFIED: 
                resp.reason = OrderChangeReason.END_TREND
        else:
            resp.cmd = StrategyCommand.UNSPECIFIED
            resp.reason = OrderChangeReason.UNSPECIFIED

    elif resp.cmd == StrategyCommand.UNSPECIFIED and settings.strategy_name not in ["strategy_ROSN", "strategy_SBER"]:
        if b_eod:
            if current_order.status == OrderStatus.OPEN and current_order.direction == OrderDir.SELL:
                resp.cmd = StrategyCommand.CLOSE_SELL
                resp.reason = OrderChangeReason.END_DAY
        elif current_order.last_action == PerformedAction.CLOSED_SELL and current_order.status == OrderStatus.CLOSED:
            if current_order.reason == OrderChangeReason.END_DAY:
                resp.cmd = StrategyCommand.OPEN_SELL
                resp.reason = OrderChangeReason.RESTORE
                resp.sl = current_order.sl #calc_sl(candles, resp.cmd, settings.stop_loss, settings.sl_tp_method, instrument)
                resp.tp = current_order.tp #calc_tp(candles, resp.cmd, settings.take_prof, settings.sl_tp_method, instrument)

    return resp