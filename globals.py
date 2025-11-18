import os
import logging
from tinkoff.invest import SubscriptionInterval, CandleInterval

#Logs
LOG_LEVEL = logging.INFO
#LOG_LEVEL = logging.ERROR
LOG_OUTPUT = "Console"#"File"#

#Account
ACCOUNT_ENV_VAR_PREFIX = "INVEST_TOKEN_"
ACCOUNT_BALANCE_MAX_USAGE_SELL = 0.88
ACCOUNT_BALANCE_MAX_USAGE_BUY = 0.97

#Strategy
STRATEGY_SETTINGS_FILE_NAME = "strategy_settings.yaml"
STRATEGY_SETTINGS_FOLDER = "settings"
STRATEGY_MIN_ORDERS = 5
STRATEGY_MIN_PROFIT_ORDERS_PERCENT = 75
MARKET_CLOSE_HOUR_UTC = 15
MARKET_OPEN_HOUR_UTC = 7
MAX_PARAM0 = 199
MAX_PARAM1 = 200
WORK_DAYS_RATE = 0.67    #To get number of working days, get total number of days and split to WORK_DAYS_RATE

NANO_DIV = 1000000000

#folders
DATA_FOLDER = "data"
INDICATORS_FOLDER = os.path.join(DATA_FOLDER, "indicators")
LOGS_FOLDER = os.path.join(DATA_FOLDER, "logs")
STATS_FOLDER = os.path.join(DATA_FOLDER, "stats")
STRAT_ORDERS_FOLDER = os.path.join(DATA_FOLDER, "orders")
SAVED_PARAMS = os.path.join(STRATEGY_SETTINGS_FOLDER, "params_")

class StrategyCommand:
    UNSPECIFIED = 0
    OPEN_BUY = 1
    OPEN_SELL = 2
    CLOSE_BUY = 3
    CLOSE_SELL = 4
    CLOSE_ALL = 5

STRAT_CMD_STR = {
    StrategyCommand.UNSPECIFIED: "Unspecified",
    StrategyCommand.OPEN_BUY:    "Open BUY",
    StrategyCommand.OPEN_SELL:   "Open SELL",
    StrategyCommand.CLOSE_BUY:   "Close BUY",
    StrategyCommand.CLOSE_SELL:  "Close SELL",
    StrategyCommand.CLOSE_ALL:   "Close ALL"
}

class OrderDir:
    UNSPECIFIED = 0
    BUY = 1
    SELL = 2

ORDER_DIR_STR = {
    OrderDir.BUY:         "BUY",
    OrderDir.SELL:        "SELL",
    OrderDir.UNSPECIFIED: "UNSPECIFIED"
}

class OrderChangeReason:
    UNSPECIFIED = 0
    CHANGE_DIRECTION = 1
    STOP_LOSS = 2
    TAKE_PROFIT = 3
    END_DAY = 4
    END_TREND = 5
    NEW_TREND = 6
    CONTINUE_TREND = 7
    RESTORE = 8

ORD_CHNG_REASON_STR = {
    OrderChangeReason.UNSPECIFIED:      "Unspecified",
    OrderChangeReason.CHANGE_DIRECTION: "Change Dir",
    OrderChangeReason.STOP_LOSS:        "SL",
    OrderChangeReason.TAKE_PROFIT:      "TP",
    OrderChangeReason.END_DAY:          "End Day",
    OrderChangeReason.END_TREND:        "End Trend",
    OrderChangeReason.NEW_TREND:        "New Trend",
    OrderChangeReason.CONTINUE_TREND:   "Continue Trend",
    OrderChangeReason.RESTORE:          "Restore"}

class OrderStatus:
    UNSPECIFIED = 0
    OPEN = 1
    CLOSED = 2

ORD_STAT_STR = {
    OrderStatus.UNSPECIFIED:  "Unspecified",
    OrderStatus.OPEN:         "Open",
    OrderStatus.CLOSED:       "Closed"}

class PerformedAction:
    DID_NOTHING = 0
    OPENED_BUY = 1
    OPENED_SELL = 2
    CHANGED_DIR_TO_BUY = 3
    CHANGED_DIR_TO_SELL = 4
    CLOSED_BUY = 5
    CLOSED_SELL = 6
    CLOSED_BUY_SL = 7
    CLOSED_BUY_TP = 8
    CLOSED_SELL_SL = 9
    CLOSED_SELL_TP = 10

PERF_ACTION_STR = {
    PerformedAction.DID_NOTHING:         "Did Nothing",
    PerformedAction.OPENED_BUY:          "Opened BUY",
    PerformedAction.OPENED_SELL:         "Opened SELL",
    PerformedAction.CHANGED_DIR_TO_BUY:  "Changed dir to BUY",
    PerformedAction.CHANGED_DIR_TO_SELL: "Changed dir to SELL",
    PerformedAction.CLOSED_BUY:          "Closed BUY",
    PerformedAction.CLOSED_BUY_SL:       "Closed BUY SL",
    PerformedAction.CLOSED_BUY_TP:       "Closed BUY TP",
    PerformedAction.CLOSED_SELL:         "Closed SELL",
    PerformedAction.CLOSED_SELL_SL:      "Closed SELL SL",
    PerformedAction.CLOSED_SELL_TP:      "Closed SELL TP"}

class Trend:
    UNSPECIFIED = 0
    UP          = 1
    DOWN        = 2
    FLAT        = 3

TREND_STR = {
    Trend.UNSPECIFIED: "UNSPECIFIED",
    Trend.UP:          "UP",
    Trend.DOWN:        "DOWN",
    Trend.FLAT:        "FLAT",
}

#fees
BROKER_FEE = 0.0005
SHORT_POSITION_DAY_FEE = {5000:0, 
                          50000:45, 
                          100000:90, 
                          250000:220, 
                          500000:440, 
                          1000000:870, 
                          2500000:2150, 
                          5000000:4200, 
                          10000000:8200, 
                          25000000:0.0008, 
                          50000000:0.00077, 
                          50000001:0.00069}

cndResDict = {
'1min' :CandleInterval.CANDLE_INTERVAL_1_MIN,
'2min' :CandleInterval.CANDLE_INTERVAL_2_MIN,
'3min' :CandleInterval.CANDLE_INTERVAL_3_MIN,
'5min' :CandleInterval.CANDLE_INTERVAL_5_MIN,
'10min' :CandleInterval.CANDLE_INTERVAL_10_MIN,
'15min':CandleInterval.CANDLE_INTERVAL_15_MIN,
'30min':CandleInterval.CANDLE_INTERVAL_30_MIN,
'1hour' :CandleInterval.CANDLE_INTERVAL_HOUR,
'2hour' :CandleInterval.CANDLE_INTERVAL_2_HOUR,
'4hour' :CandleInterval.CANDLE_INTERVAL_4_HOUR,
'1day'  :CandleInterval.CANDLE_INTERVAL_DAY,
'1week' :CandleInterval.CANDLE_INTERVAL_WEEK,
'1mon'  :CandleInterval.CANDLE_INTERVAL_MONTH
}

candles_in_1_hour = {
CandleInterval.CANDLE_INTERVAL_1_MIN : 60,
CandleInterval.CANDLE_INTERVAL_2_MIN : 30,
CandleInterval.CANDLE_INTERVAL_3_MIN : 20,
CandleInterval.CANDLE_INTERVAL_5_MIN : 12,
CandleInterval.CANDLE_INTERVAL_10_MIN : 6,
CandleInterval.CANDLE_INTERVAL_15_MIN : 4,
CandleInterval.CANDLE_INTERVAL_30_MIN : 2,
CandleInterval.CANDLE_INTERVAL_HOUR : 1,
CandleInterval.CANDLE_INTERVAL_2_HOUR : 0.5,
CandleInterval.CANDLE_INTERVAL_4_HOUR : 0.25,
CandleInterval.CANDLE_INTERVAL_DAY : 0.12,
CandleInterval.CANDLE_INTERVAL_MONTH : 0.004
}

minutes_in_candle_interval = {
CandleInterval.CANDLE_INTERVAL_1_MIN  : 1,
CandleInterval.CANDLE_INTERVAL_2_MIN  : 2,
CandleInterval.CANDLE_INTERVAL_3_MIN  : 3,
CandleInterval.CANDLE_INTERVAL_5_MIN  : 5,
CandleInterval.CANDLE_INTERVAL_10_MIN : 10,
CandleInterval.CANDLE_INTERVAL_15_MIN : 15,
CandleInterval.CANDLE_INTERVAL_30_MIN : 30,
CandleInterval.CANDLE_INTERVAL_HOUR   : 60,
CandleInterval.CANDLE_INTERVAL_2_HOUR : 120,
CandleInterval.CANDLE_INTERVAL_4_HOUR : 240,
CandleInterval.CANDLE_INTERVAL_DAY    : 840, #14*60
CandleInterval.CANDLE_INTERVAL_MONTH  : 18480 #22*14*60
}

subscriptionIntervalDict = {
'1min' :SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_MINUTE,
'2min' :SubscriptionInterval.SUBSCRIPTION_INTERVAL_2_MIN,
'3min' :SubscriptionInterval.SUBSCRIPTION_INTERVAL_3_MIN,
'5min' :SubscriptionInterval.SUBSCRIPTION_INTERVAL_FIVE_MINUTES,
'10min' :SubscriptionInterval.SUBSCRIPTION_INTERVAL_10_MIN,
'15min':SubscriptionInterval.SUBSCRIPTION_INTERVAL_FIFTEEN_MINUTES,
'30min':SubscriptionInterval.SUBSCRIPTION_INTERVAL_30_MIN,
'1hour' :SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_HOUR,
'2hour' :SubscriptionInterval.SUBSCRIPTION_INTERVAL_2_HOUR,
'4hour' :SubscriptionInterval.SUBSCRIPTION_INTERVAL_4_HOUR,
'1day'  :SubscriptionInterval.SUBSCRIPTION_INTERVAL_ONE_DAY,
'1mon'  :SubscriptionInterval.SUBSCRIPTION_INTERVAL_MONTH
}

SMA_INDICATORS_MATRIX = None
