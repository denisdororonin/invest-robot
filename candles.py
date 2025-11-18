import os
import csv
import time
import pandas as pd
import numpy as np
from collections import namedtuple

from tinkoff.invest import Client, InstrumentShort
from tinkoff.invest.constants import INVEST_GRPC_API

from globals import STATS_FOLDER
from globals import cndResDict
from utils import is_it_holiday, setup_logger, is_it_early_mornining, is_it_late_evening, quote2float, get_account_token
from readsettings import StrategySettings

logger = setup_logger(__name__)

Tick = namedtuple('Tick', ['Time','Open','Close','Low','High','Volume'])

class Candles:
    def __init__(self, skip_holidays: bool = True, skip_morning_hours: bool = True, skip_evening_hours: bool = True) -> None:
        self.data: list[Tick] = []
        self.df: pd.DataFrame = pd.DataFrame()
        self.skip_holidays = skip_holidays
        self.skip_morning_hrs = skip_morning_hours
        self.skip_evening_hrs = skip_evening_hours

    def add(self, tick: Tick) -> bool:
        if self._ignore(tick):
            logger.debug(f"Tick ignored (holiday or early morning): {tick.Time}")
            return False
        self.data.append(tick)
        return True

    def collect(self, settings: StrategySettings, startdate, enddate, b_save=True) -> list[Tick]:

        token = get_account_token(settings.acc_name)
        instr: InstrumentShort = self._find_instrument(token, settings.ticker)
        if not instr:
            raise Exception("Candles.collect(): Can't find such ticker: ", settings.ticker)
    
        self.data.clear()
        for i in range(3):
            try:
                with Client(token) as client:
                    for candle in client.get_all_candles(figi=instr.figi, from_=startdate, to=enddate,
                                                         interval=settings.candles_int):
            
                        tick = Tick(candle.time, 
                                    quote2float(candle.open), quote2float(candle.close), 
                                    quote2float(candle.low), quote2float(candle.high), candle.volume)
                        self.add(tick)
                break
            except Exception as e:
                logger.error(f"Candles.collect(): Exception in get_all_candles: ", e)
                self.data.clear()
                time.sleep(30)
                continue

        if b_save and len(self.data) > 0:
            if not os.path.exists(STATS_FOLDER + '/' + instr.ticker): 
                os.mkdir(STATS_FOLDER + '/' + instr.ticker)
            resolution = list(cndResDict.keys())[list(cndResDict.values()).index(settings.candles_int)]
            fileName = STATS_FOLDER + '/' + instr.ticker + "/" + instr.ticker + '_' + startdate.strftime('%Y-%m-%d') + '_' + enddate.strftime('%Y-%m-%d') + '_' + resolution + '.csv'
            with open(fileName, 'w', newline='') as csvFile:
                historyWriter = csv.writer(csvFile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                historyWriter.writerow(['Time', 'Open', 'High', 'Low', 'Close', 'Volume']) #write csv header
                for candle in self.data:
                    historyWriter.writerow([candle.Time.strftime("%Y-%m-%d %H:%M:%S"), 
                                            candle.Open, candle.High, candle.Low, candle.Close, candle.Volume])
        return self.data

    def daily_price_change_avg(self) -> float:
        
        curr_day_close_values: list[float] = []
        list_of_daily_price_change: list[float] = []
        curr_day = self.data[0].Time.day

        for iter in self.data:
            if curr_day != iter.Time.day:
                list_of_daily_price_change.append(100.0*((max(curr_day_close_values) - min(curr_day_close_values))/curr_day_close_values[0]))
                curr_day_close_values.clear()
                curr_day = iter.Time.day

            curr_day_close_values.append(iter.Close)
        
        return sum(list_of_daily_price_change)/len(list_of_daily_price_change)

    def _find_instrument(self, token, ticker) -> InstrumentShort:
        try:
            with Client(token, target=INVEST_GRPC_API) as client:
                resp = client.instruments.find_instrument(query=ticker)
                for i in resp.instruments:
                    if i.ticker == ticker and (i.class_code == 'TQBR' or i.class_code == 'TQTF'):
                        return i
        except:
            logger.exception("Exception while trying to find instrument", exc_info=True)
        return None
    
    def _ignore(self, tick: Tick) -> bool:
        '''Checks if we need to ignore this tick (come on holiday or early morninng and corresp setting)'''
        b_ignore_tick = False
        
        if self.skip_holidays and is_it_holiday(tick.Time):
            b_ignore_tick = True
        elif self.skip_morning_hrs and is_it_early_mornining(tick.Time):
            b_ignore_tick = True
        elif self.skip_evening_hrs and is_it_late_evening(tick.Time):
            b_ignore_tick = True

        return b_ignore_tick

    def ticks_to_dataframe(self) -> pd.DataFrame:

        if not self.data:
            return pd.DataFrame(columns=Tick._fields)
    
        df = pd.DataFrame(self.data, columns=Tick._fields)
        df['Time'] = pd.to_datetime(df['Time'])
        df.set_index('Time', inplace=True)

        self.df = df
        return df
    
    def add_metrics(self, window: int = 300):

        if len(self.df) < window:
            logger.error(f"Candles.add_metrics: Can't add metrics. Len={len(self.df)}, Requested len = {window}")
            return
        
        data = self.df.tail(window).copy()
        
        # === Метрики объёма ===
        V_mean = data['Volume'].mean()
        V_std = data['Volume'].std(ddof=1)
        CV_V = V_std / V_mean if V_mean != 0 else np.nan
        Z_V = (data['Volume'].iloc[-1] - V_mean) / V_std if V_std != 0 else np.nan

        # === Метрики цены/волатильности ===
        data['Return'] = data['Close'].pct_change()
        sigma = data['Return'].std(ddof=1)

        data['Amplitude'] = (data['Close'] - data['Open']).abs()
        mean_amp = data['Amplitude'].mean()
        std_amp = data['Amplitude'].std(ddof=1)
        CV_A = std_amp / mean_amp if mean_amp != 0 else np.nan

        # ATR (упрощённо)
        tr1 = data['High'] - data['Low']
        tr2 = (data['High'] - data['Close'].shift()).abs()
        tr3 = (data['Low'] - data['Close'].shift()).abs()
        TR = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        ATR = TR.mean()

        # === Связь объём ↔ скорость ===
        corr_vol_absret = data['Volume'].corr(data['Return'].abs())
        corr_vol_amp = data['Volume'].corr(data['Amplitude'])

        # === Итог ===
        metrics = {
            "V_mean": V_mean,
            "V_std": V_std,
            "CV_V": CV_V,
            "Z_V": Z_V,
            "ATR": ATR,
            "sigma": sigma,
            "mean_amp": mean_amp,
            "CV_A": CV_A,
            "Corr_Vol_AbsRet": corr_vol_absret,
            "Corr_Vol_Amp": corr_vol_amp,
        }
        return metrics