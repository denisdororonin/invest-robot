import yaml
import pytz
from datetime import datetime, time, timezone
from globals import cndResDict
from utils import setup_logger

#logger = setup_logger("log_" + datetime.now().strftime('%Y-%m-%d'))
logger = setup_logger(__name__)

class StrategySettings:
    def __init__(self, settings):
        self.ticker = settings['candles']['ticker']
        self.candles_enddate = datetime.strptime(settings['candles']['candles_enddate'], '%d-%m-%Y').replace(tzinfo=pytz.UTC) if settings['candles']['candles_enddate'] != 'now' else datetime.now()
        self.candles_num = int(settings['candles']['candles_num'])
        self.candles_int = cndResDict[settings['candles']['candles_int']]
        
        self.strategy_name = settings['strategy']['strategy_name']
        self.strategy_selection = settings['strategy']['strategy_selection']
        self.backtest_percent = float(settings['strategy']['backtest_percent'])
        self.trade_allowed = settings['strategy']['trade_allowed']
        self.lots = int(settings['strategy']['lots'])
        self.shorts_enabled = settings['strategy']['shorts_enabled']
        self.params  = settings['strategy']['params']
        
        self.acc_name = settings['account']['acc_name']
        
        self.day_len = int(settings['finder']['day_len'])
        self.good_deviation = float(settings['finder']['good_deviation'])

        self.simulation_start_date = datetime.strptime(settings['tester']['simulation_start_date'], '%d-%m-%Y').replace(tzinfo=pytz.UTC)
        self.testmode = settings['tester']['testmode']
        self.start_capital = float(settings['tester']['start_capital'])
        self.day_start_utc: datetime = time(int(settings['tester']['day_start_utc']), 0, 0, tzinfo=timezone.utc)
        self.day_end_utc: datetime = time(int(settings['tester']['day_end_utc']), 0, 0, tzinfo=timezone.utc)
        self.spread = float(settings['tester']['spread'])
        self.strategy_log = settings['tester']['strategy_log']

        self.skip_holidays = settings['tuning']['skip_holidays']
        self.skip_morning_hours = settings['tuning']['skip_morning_hours']
        self.skip_evening_hours = settings['tuning']['skip_evening_hours']
        self.stop_loss = int(settings['tuning']['stop_loss'])
        self.take_prof = int(settings['tuning']['take_prof'])
        self.trail_stops = settings['tuning']['trail_stops']
        self.sl_tp_method = settings['tuning']['sl_tp_method']
        self.min_profit_ord_percent = int(settings['tuning']['min_profit_ord_percent'])
        self.candle_wait_close = settings['tuning']['candlewaitclose']
        self.adjust_params = settings['tuning']['adjust_params']
        self.adjust_period = int(settings['tuning']['adjust_period'])
        self.use_precalculated_indicators = settings['tuning']['use_precalculated_indicators']
        self.close_shorts_on_day_end = settings['tuning']['close_shorts_on_day_end']
        
    def print_settings(self):
        
        logger.info(f"Strategy Settings:") 
        logger.info(f"    Candles ticker: {self.ticker}")
        logger.info(f"    Candles end date: {self.candles_enddate}")
        logger.info(f"    Candles number of candles: {self.candles_num}")
        logger.info(f"    Candles interval: {self.candles_int}")
        logger.info(f"    Account name: {self.acc_name}")

        logger.info(f"    Strategy name: {self.strategy_name}")
        logger.info(f"    Strategy best approach: {self.strategy_selection}")
        logger.info(f"    Strategy testmode: {self.testmode}")
        logger.info(f"    Strategy stop_loss: {self.stop_loss}")
        logger.info(f"    Strategy take_profit: {self.take_prof}")
        logger.info(f"    Strategy short_enabled: {self.shorts_enabled}")
        logger.info(f"    Strategy skip_holidays: {self.skip_holidays}")
        logger.info(f"    Strategy day_len: {self.day_len}")
        logger.info(f"    Strategy good_deviation: {self.good_deviation}")
        logger.info(f"    Strategy quantity: {self.lots}")
        logger.info(f"    Strategy params: {self.params}")

        logger.info(f"    Strategy start capital: {self.start_capital}")
        logger.info(f"    Market spread % (manual, or take from market when 0): {self.spread}")

        logger.info(f"    Skip Holidays: {self.skip_holidays}")
        logger.info(f"    Skip Morning Hours: {self.skip_morning_hours}")
        logger.info(f"    Skip Evening Hours: {self.skip_evening_hours}")
        logger.info(f"    Candle Wait Close: {self.candle_wait_close}")
        logger.info(f"    Adjust strategy params: {self.adjust_params}")
        logger.info(f"    Adjust params period(days): {self.adjust_period}")
        logger.info(f"    Use pre-calculated indicator values: {self.use_precalculated_indicators}")
        logger.info(f"    Close short orders at the end of day: {self.close_shorts_on_day_end}")
        logger.info(f"    Trail stops: {self.trail_stops}")
        logger.info(f"    Trail stops method: {self.sl_tp_method}")

        return
    

#read file with settings (kobo file system details, books location on local PC)
def read_strategy_settings(settingsFile: str):
    yaml_settings = {}
    try:
        with open(settingsFile, "r") as stream:
            try:
                yaml_settings = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                logger.exception(f"ERROR: Can't parse settings file: ", exc_info=True)
                return None
            finally:
                stream.close()
    except:
        logger.exception(f"File {settingsFile} was not found", exc_info=True)
        return None

    return StrategySettings(yaml_settings)

settings = read_strategy_settings("strategy_settings.yaml")
settings.print_settings()