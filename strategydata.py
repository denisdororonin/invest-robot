import os
from datetime import datetime, time, timezone, timedelta
import pytz
from tinkoff.invest import (
    Client, 
    InstrumentIdType,
    InstrumentType,
    TradingSchedulesResponse,
    ShareResponse,
    GetOrderBookResponse
)
from tinkoff.invest.constants import INVEST_GRPC_API

from readsettings import StrategySettings
from telegrambot import TelegramBot
from globals import ACCOUNT_BALANCE_MAX_USAGE_SELL, ACCOUNT_BALANCE_MAX_USAGE_BUY
from globals import STRATEGY_SETTINGS_FILE_NAME, ORD_CHNG_REASON_STR
from globals import STATS_FOLDER
from candles import Candles
from schemas import Order, OrderDir, OrderStatus
from utils import is_it_holiday, setup_logger, quote2float, get_account_token, get_day_len_in_candles

logger = setup_logger(__name__)

class StrategyData:
    settings_filename = STRATEGY_SETTINGS_FILE_NAME
    tbot = TelegramBot()
    def __init__(self, yaml_settings: StrategySettings):
        #account info
        self.account = Account(yaml_settings.acc_name)
        self.account.set_account_id()
        #instrument info
        self.instrument: Instr = Instr(ticker=yaml_settings.ticker, shorts=yaml_settings.short_enabled, use_precalculated_indicators=yaml_settings.use_precalculated_indicators)
        self.instrument.set_figi(self.account.token)
        self.instrument.set_instrument_details(self.account.token)
        self.instrument.set_trade_session_times(self.account.token, datetime.now())
        #self.instrument.set_trade_session_times_manual(yaml_settings.day_start_utc, yaml_settings.day_end_utc)
        self.instrument.set_best_spread(self.account.token, yaml_settings.spread)

        #settingst for strategy from settings.yaml
        self.settings: StrategySettings = yaml_settings
        self.settings.day_len = get_day_len_in_candles(self.instrument.day_start.hour, self.instrument.day_end.hour,
                                                       self.settings.interval)

        #runtime params
        self.last_candle_time = datetime(2000, 12, 31, 23, 59, 59, 999999).replace(tzinfo=pytz.UTC)
        self.last_params_updated_time = datetime(2000, 12, 31, 23, 59, 59, 999999).replace(tzinfo=pytz.UTC)
        self.candles = Candles(skip_holidays=self.settings.skip_holidays, skip_morning_hours=self.settings.skip_morning_hours, skip_evening_hours=self.settings.skip_evening_hours)
        self.params = []
        self.current_order = Order(direction=OrderDir.UNSPECIFIED, lots=0, price=0, time=datetime.now(), status=OrderStatus.CLOSED, sl=-1, tp=-1)
        self.orders_history: Order = []        
    
    def save_orders_history(self):

        total_orders = len(self.orders_history)
        profit = profit_orders = loss_orders = 0
        for i in self.orders_history:
            profit = profit + i.profit
            if i.profit > 0: 
                profit_orders += 1 
            elif i.profit < 0: 
                loss_orders += 1
        percent_of_profit_orders = round(profit_orders/total_orders*100.0, 2) if total_orders > 0 else 0
        profit_in_percents = round(profit/self.orders_history[-1].priceClose*100.0, 2) if len(self.orders_history) > 0 else 0

        filename = os.path.join(STATS_FOLDER, self.instrument.ticker, "strategy_run_" + str(self.settings.numdays) + "d_" + datetime.now().strftime("%Y-%m-%d_%H-%M") + ".txt")
        file_report = open(filename, 'w', newline='')

        file_report.write("Numdays: " + str(self.settings.numdays) + "\n")
        file_report.write("Skip holidays: " + str(self.settings.skip_holidays) + "\n")
        file_report.write("Strategy: " + str(self.settings.strategy_name) + "\n")
        file_report.write("Best approach: " + str(self.settings.best_approach) + "\n")
        file_report.write("SL: " + str(self.settings.stop_loss) + "\n")
        file_report.write("TP: " + str(self.settings.take_prof) + "\n")
        file_report.write("Trail stops: " + str(self.settings.trail_stops) + "\n")
        file_report.write("Close shorts on day end: " + str(self.settings.close_shorts_on_day_end) + "\n")
        file_report.write("Adjust params: " + str(self.settings.adjust_params) + ", Period: " + str(self.settings.adjust_period) + "\n\n")
        
        file_report.write("Orders: " + str(total_orders) + "\n")
        file_report.write("Profit Orders: " + str(profit_orders) + " Loss orders: " + str(loss_orders) + " Percent of profit orders: " + str(percent_of_profit_orders) + "\n")
        file_report.write("Total profit: " + str(profit) + " Profit in %: " + str(profit_in_percents) + "\n\n")
        operation = {0: "UNSPECIFIED", 1: "BUY ", 2: "SELL"}
        sum_of_percents = 0
        for i in self.orders_history:
            percent = round(i.profit/i.priceOpen*100.0, 2)
            report_string = "{0}: Tm op: {1}, Tm cl: {2}, Pr open: {3:7}, Pr close: {4:7}, Profit: {5:5}% Params: {6}, Rsn: {7}\n".format(operation[i.operation], i.timeOpen.strftime("%Y-%m-%d %H:%M:%S"), i.timeClose.strftime("%Y-%m-%d %H:%M:%S"), round(i.priceOpen,4), round(i.priceClose,4), percent, i.params, ORD_CHNG_REASON_STR[i.reason])
            file_report.write(report_string)
            sum_of_percents += percent

        file_report.write("\nSum of percents: " + str(sum_of_percents) + "\n")
        file_report.close()
        return


class Account:
    balance_use_sell = ACCOUNT_BALANCE_MAX_USAGE_SELL    #percent of available balance that can be used for next sell order
    balance_use_buy = ACCOUNT_BALANCE_MAX_USAGE_BUY    #percent of available balance that can be used for next buy order
    def __init__(self, acc_name):
        self.name = acc_name
        self._token = get_account_token(acc_name)
        self._id = ""
    
    def set_account_id(self):
        try:
            with Client(self.token, target=INVEST_GRPC_API) as client:
                resp = client.users.get_accounts().accounts
                for iter in resp:
                    if iter.name == self.name:
                        self._id = iter.id
        except:
            self._id = ""
            logger.exception("Exception in set_account_id.", exc_info=True)
        return
    
    @property
    def id(self):
        if self._id == "":
            self.set_account_id()
        return self._id
    
    @property
    def token(self):
        return self._token

class Instr:
    def __init__(self, ticker: str = "", figi: str = "", shorts: bool = True, use_precalculated_indicators: bool = False):
        self.ticker = ticker
        self.figi = figi
        self.kind: InstrumentType = InstrumentType.INSTRUMENT_TYPE_UNSPECIFIED
        self.short_enabled = shorts
        self.min_price = -1.0
        self.lot_size = 1
        self.day_start: datetime = datetime.combine(datetime.today(), time(7, 0, 0, tzinfo=timezone.utc))
        self.day_end: datetime = datetime.combine(datetime.today(), time(15, 39, 0, tzinfo=timezone.utc))
        self.lever_short = 1.0
        self.lever_long = 1.0
        self.spread = 0.0

        self.indicators = {"SMA" : None, "EMA" : None, "SMMA" : None, "ADX" : None, "MACD" : None, "RSI" : None, "ATR": None}
        self.use_precalculated_indicators = use_precalculated_indicators
        self.indicators_were_updated = False
        
    def set_figi(self, token: str):
        try:
            with Client(token, target=INVEST_GRPC_API) as client:
                resp = client.instruments.find_instrument(query=self.ticker)
                for i in resp.instruments:
                    if i.ticker == self.ticker and (i.class_code == 'TQBR' or i.class_code == 'TQTF'):
                        self.figi = i.figi
                        self.kind = i.instrument_kind
                        return
        except:
            self.figi = ""
            logger.exception("Exception in set_figi.", exc_info=True)
        return

    def set_instrument_details(self, token: str):
        try:
            with Client(token, target=INVEST_GRPC_API) as client:
                instr = client.instruments.get_instrument_by(id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, 
                                                                        id=self.figi).instrument
                
                self.min_price = quote2float(instr.min_price_increment)
                self.lot_size = instr.lot
                self.short_enabled = instr.short_enabled_flag
                self.lever_long = 1.0/quote2float(instr.dlong_min)
                self.lever_short = 1.0/quote2float(instr.dshort_min)
        except:
            self.min_price = -1
            self.lot_size = 1
            self.short_enabled = False
            logger.exception("Exception in set_instrument_details.", exc_info=True)
        return

    def set_trade_session_times_manual(self, start_utc: int, end_utc: int):

        self.day_start = datetime(datetime.now().year, datetime.now().month, datetime.now().day, start_utc, 0, 0, tzinfo=timezone.utc)
        self.day_end = datetime(datetime.now().year, datetime.now().month, datetime.now().day, end_utc, 0, 0, tzinfo=timezone.utc)

        return

    def set_trade_session_times(self, token: str, date: datetime):

        dt = date
        while is_it_holiday(dt):
            dt = dt + timedelta(days=1)

        with Client(token) as client:
            if self.kind == InstrumentType.INSTRUMENT_TYPE_SHARE: s_resp = client.instruments.share_by(id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=self.figi)
            elif self.kind == InstrumentType.INSTRUMENT_TYPE_ETF: s_resp = client.instruments.etf_by(id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=self.figi)
            else:
                logger.error(f"set_trade_session_times(): Instrument type {self.kind} is not supported")
                return
            
            t_resp: TradingSchedulesResponse = client.instruments.trading_schedules(exchange=s_resp.instrument.exchange,from_=dt,to=dt)

        if t_resp.exchanges[0].days[0].is_trading_day:
            self.day_start = t_resp.exchanges[0].days[0].start_time
            self.day_end = t_resp.exchanges[0].days[0].end_time

            #TEMPORARY REMOVED FOR SIMPLIER APPROACH (ABOVE)
            #main_session = [x for x in t_resp.exchanges[0].days[0].intervals if x.type == 'regular_trading_session_main']
            #evening_session = [x for x in t_resp.exchanges[0].days[0].intervals if x.type == 'regular_trading_session_evening']
            #if len(main_session) != 0:
            #    self.day_start = main_session[0].interval.start_ts
            #    self.day_end = main_session[0].interval.end_ts
            #    if len(evening_session) != 0:
            #        self.day_end = evening_session[0].interval.end_ts
            #else:
            #    logger.error(f"set_trade_session_times: couldn't find main session time interval")

        logger.info(f"Trade session for {self.ticker} hours: {self.day_start} - {self.day_end}.")
        return

    def is_market_open(self, time: datetime):

        if is_it_holiday(time):
            return False
            
        return True if self.day_start.time() <= time.time() < self.day_end.time() else False
    
    def is_trade_day(self, token: str, date: datetime) -> bool:

        with Client(token) as client:
            s_resp: ShareResponse = client.instruments.share_by(id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI, id=self.figi)
            t_resp: TradingSchedulesResponse = client.instruments.trading_schedules(exchange=s_resp.instrument.exchange,from_=date,to=date)
        
        #this thing alays returns True, even for Sunday
        return t_resp.exchanges[0].days[0].is_trading_day
    
    #best spread values from top of the trading glass
    def set_best_spread(self, token: str, settings_spread: float) -> float:
    
        order_book: GetOrderBookResponse = None
        ask = bid = 0
        with Client(token, target=INVEST_GRPC_API) as client:
            order_book = client.market_data.get_order_book(figi=self.figi, depth=10)
        
        if len(order_book.asks) > 0 and len(order_book.bids) > 0:
            ask = quote2float(order_book.asks[0].price)
            bid = quote2float(order_book.bids[0].price)
            if settings_spread <= 0:
                #spread = ask - bid
                self.spread = ask - bid if (ask-bid) > 0 else 0
                logger.info(f"Spread for {self.ticker}: {round(100.0*(ask-bid)/bid,2)}%")
            else:
                #spread defined in settings in %
                self.spread = (settings_spread * max(ask, bid)) / 100.0
                logger.info(f"Spread for {self.ticker}: {settings_spread}%")
        else:
            self.spread = 0
            logger.warning(f"set_best_spread(): WARNING: asks/bids list is empty. Setting spread to 0")
       
        return

class StrategyDynamicParams:
    def __init__(self, params: list[int], last_strategy_run_date: datetime):
        self.params = params
        self.last_strategy_run_date: datetime = last_strategy_run_date
