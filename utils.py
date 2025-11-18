import sys
import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from tinkoff.invest import Quotation, MoneyValue, CandleInterval
from globals import STRATEGY_SETTINGS_FILE_NAME, STRATEGY_SETTINGS_FOLDER, DATA_FOLDER, LOGS_FOLDER
from globals import MARKET_CLOSE_HOUR_UTC, MARKET_OPEN_HOUR_UTC
from globals import LOG_LEVEL, LOG_OUTPUT
from globals import NANO_DIV, ACCOUNT_ENV_VAR_PREFIX
from globals import SHORT_POSITION_DAY_FEE
from globals import candles_in_1_hour, minutes_in_candle_interval

STATE_HOLIDAYS = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08", 
                  "2024-02-23", "2024-03-08", "2024-04-29", "2024-04-30", "2024-05-01", "2024-05-09", 
                  "2024-05-10", "2024-06-12", "2024-11-04", "2024-12-31",

                  "2025-01-01", "2025-01-02", "2025-01-07",
                  "2025-02-24", "2025-05-01", "2025-05-02", "2025-05-09",
                  "2025-06-12", "2025-06-13", "2025-11-04",
                  ]

WORKING_SATURDAYS = ["2024-11-02", "2024-12-28", "2025-11-01"]

def setup_logger(name: str):

    if not os.path.exists(DATA_FOLDER):
        os.mkdir(DATA_FOLDER)
    if not os.path.exists(LOGS_FOLDER):
        os.mkdir(LOGS_FOLDER)

    logger = logging.getLogger(name)
    logger.setLevel(level=LOG_LEVEL)
    handler = RotatingFileHandler(f"{LOGS_FOLDER}/{name}.log", maxBytes=512000, backupCount=3)
    formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    if LOG_OUTPUT == "Console":
        logger.addHandler(logging.StreamHandler())
    else:
        logger.addHandler(handler)
    logger.info(f"MODULE {sys.modules[__name__]}")
    return logger

logger = setup_logger(__name__)

def get_account_token(account_name: str) -> str:
    return os.getenv(ACCOUNT_ENV_VAR_PREFIX + account_name)

def get_settings_filenames():

    settings_files = []
    args_number = len(sys.argv)
    if len(sys.argv) > 1:
        for i in range(1, args_number):
            if os.path.splitext(sys.argv[i])[1] == ".yaml":
                settings_files.append(os.path.join(STRATEGY_SETTINGS_FOLDER, sys.argv[i]))
    
    if len(settings_files) == 0:
        settings_files.append(STRATEGY_SETTINGS_FILE_NAME)
        
    logger.info(f"get_settings_files(): Settings files are: {settings_files}")

    return settings_files

def is_it_holiday(date: datetime):
    b_holiday = True if date.weekday() in (5, 6) else False
    if not b_holiday:
        try:
            STATE_HOLIDAYS.index(date.strftime("%Y-%m-%d"))
            b_holiday = True
        except:
            pass

    if b_holiday:
        try:
            WORKING_SATURDAYS.index(date.strftime("%Y-%m-%d"))
            b_holiday = False
        except:
            pass

    return b_holiday

def weekdays_2_calendardays(date: datetime, working_days: int) -> int:
    """Calculates the number of calendar days that we need to subrtact from 'date' to actually subtract working days"""
    cal_days = 1
    counter = 1
    while counter <= working_days:        
        if not is_it_holiday(date - timedelta(days=cal_days)):
            counter += 1
        cal_days += 1
    return cal_days-1

def is_it_early_mornining(date: datetime) -> bool:
    '''Checks if it's early morning: candles starting to arrive ar 4am, but real trade "volume" starts at 7am'''
    return True if date.hour < MARKET_OPEN_HOUR_UTC-1 else False

def is_it_late_evening(date: datetime) -> bool:
    '''Checks if it's early morning: candles starting to arrive ar 4am, but real trade "volume" starts at 7am'''
    return True if date.hour > MARKET_CLOSE_HOUR_UTC else False

def is_it_friday_evening(date: datetime):
    return True if (date.weekday == 4 and date.hour == MARKET_CLOSE_HOUR_UTC-1) else False

def candles_until_end_of_day(timenow: datetime, market_close_time: datetime, candle_interval: CandleInterval) -> int:
    """Calculates the number of candles until the end of the trade day"""
    candles_to_close_market = 0
    if market_close_time > timenow:
        markt_close = datetime.combine(datetime.today(), market_close_time.time())
        markt_curnt = datetime.combine(datetime.today(), timenow.time())
        if markt_close > markt_curnt:
            candles_to_close_market = int((markt_close - markt_curnt).seconds/60//minutes_in_candle_interval[candle_interval])
    
    return candles_to_close_market

def quote2float(quote: Quotation) -> float:
    return quote.units + quote.nano/NANO_DIV

def money2float(money: MoneyValue) -> float:
    return money.units + money.nano/NANO_DIV

def get_overnight_fee(amount: float) -> int:
    fee = SHORT_POSITION_DAY_FEE[list(SHORT_POSITION_DAY_FEE.keys())[-1]]*amount

    for eddge_amount in SHORT_POSITION_DAY_FEE.keys():
        if amount < eddge_amount:
            if SHORT_POSITION_DAY_FEE[eddge_amount] > 1 or SHORT_POSITION_DAY_FEE[eddge_amount] == 0:
                fee = SHORT_POSITION_DAY_FEE[eddge_amount]
            else:
                fee = amount*SHORT_POSITION_DAY_FEE[eddge_amount]
            break
    return fee

def get_day_len_in_candles(day_start: int, day_end: int, candle_interval: CandleInterval) -> int:
    return (day_end - day_start + 1)*candles_in_1_hour[candle_interval] if day_end > day_start else 0

def time_to_yearmon(tm: datetime) -> str:
    return str(tm.year) + "-" + str(tm.month).zfill(2)

def get_param(params: list[int], index: int, default=0) -> int:
    return params[index] if 0 <= index < len(params) else default