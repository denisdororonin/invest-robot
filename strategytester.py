from collections import namedtuple
import os
import time
from datetime import timedelta, datetime
from itertools import product
from tinkoff.invest.utils import now

from readsettings import read_strategy_settings, StrategySettings
from reports import StrategyLog, StratLog1Tick, SingleRunStrategyReport
from schemas import Order, StrategyResp, OrderChangeReason
from candles import Candles, Tick
from strategydata import Instr
from indicatorvals import save_indicators_to_file
from utils import get_settings_filenames, setup_logger, weekdays_2_calendardays, get_account_token, get_day_len_in_candles
from globals import STRATEGY_MIN_ORDERS, STRATEGY_MIN_PROFIT_ORDERS_PERCENT, STATS_FOLDER, DATA_FOLDER, WORK_DAYS_RATE
from globals import OrderStatus, StrategyCommand, OrderDir
from strategies2 import run_strategy

#logger = setup_logger("log_" + datetime.now().strftime('%Y-%m-%d'))
logger = setup_logger(__name__)

TestParam = namedtuple('TestParam', ['name', 'minVal', 'maxVal', 'step'])

def main():

    print("---------------------- main(): called -----------------------")

    start_time = time.time()
    #for strategy tester I expect to test excactly 1 instrument. It supposed to be run without arguments and 
    #default settings file should to be taken
    strategy_tester(get_settings_filenames()[0])
    end_time = time.time()

    print("----------------------- main(): End (duration: ", end_time-start_time,")-------------------------")
    return
    

def strategy_tester(settings_file: str, ticker: str = "", shorts_enabled: bool = True, timenow = now(), instrument: Instr = None):
    
    logger.info("strategy_tester(): start")

    settings: StrategySettings = read_strategy_settings(settings_file)
    token = get_account_token(settings.acc_name)
    settings.print_settings()

    #overwrite ticker name and shorts_enabled from settings if it was passed as additional parameters
    #I need this to run strategy_tester many times for many tickers
    settings.ticker = ticker if ticker != "" else settings.ticker
    settings.shorts_enabled = shorts_enabled if not shorts_enabled else settings.shorts_enabled

    if not os.path.exists(DATA_FOLDER):  os.mkdir(DATA_FOLDER)
    if not os.path.exists(STATS_FOLDER): os.mkdir(STATS_FOLDER)

    if not instrument:
        instrument: Instr = Instr(settings.ticker, use_precalculated_indicators=settings.use_precalculated_indicators)
        instrument.set_figi(token)
        instrument.set_trade_session_times(token, datetime.now())
        instrument.set_best_spread(token, settings.spread)
    
    #add more candles to cover indicators wich are looking back to the past.
    max_possible_param = max(sublist[2] for sublist in settings.params)
    needed_candles_num = settings.candles_num + 4*max_possible_param + 1

    #get number of candles in 1 day to calculate start date for collecting historical candles
    settings.day_len = get_day_len_in_candles(instrument.day_start.hour, instrument.day_end.hour, settings.candles_int)
    if settings.skip_morning_hours: settings.day_len -= 2
    if settings.skip_evening_hours: settings.day_len -= 2

    if settings.day_len <= 0:
        logger.error(f"strategy_tester(): wrong day length: {settings.day_len}. Can't recover. EXIT")
        return
    
    candles = []
    candles.clear()

    #WORK_DAYS_RATE is a magic number - approx ratio of working and not working days in Russia.
    startdate = settings.candles_enddate - timedelta(days=int((needed_candles_num/settings.day_len)/WORK_DAYS_RATE) + 1)
    enddate =settings.candles_enddate
    candles = Candles(settings.skip_holidays, settings.skip_morning_hours, settings.skip_evening_hours).collect(settings, startdate, enddate, b_save=True)
    logger.info(f"strategy_tester(): {settings.ticker} Candles collected: {len(candles)} (from {startdate} to {enddate}). Settings asked: {settings.candles_num}")
    logger.info(f"strategy_tester(): Testing strategy : {settings.strategy_name} for {settings.ticker}")
    logger.info(f"strategy_tester(): Choose best params approach: {settings.strategy_selection}")

    if settings.spread > 0:
        instrument.spread = (settings.spread * candles[-1].Close)/100.0
        logger.info(f"strategy_tester(): Override spread with settings value: {instrument.spread}(or {settings.spread}%)")

    all_reports = test_strategy(settings, candles, instrument=instrument)
    all_reports.sort(reverse=True, key=lambda report: report.profitability)
    save_summary(all_reports, STATS_FOLDER + "/" + settings.ticker + "/" + settings.strategy_name)
    
    #update all indicators if I used them (ugly)
    if instrument and instrument.indicators_were_updated:
        if instrument.indicators.get("SMA", None):
            save_indicators_to_file(instrument.indicators.get("SMA", None))
        if instrument.indicators.get("EMA", None):
            save_indicators_to_file(instrument.indicators.get("EMA", None))
        if instrument.indicators.get("SMMA", None):
            save_indicators_to_file(instrument.indicators.get("SMMA", None))
        if instrument.indicators.get("ADX", None):
            save_indicators_to_file(instrument.indicators.get("ADX", None))
        if instrument.indicators.get("MACD", None):
            save_indicators_to_file(instrument.indicators.get("MACD", None))
        if instrument.indicators.get("RSI", None):
            save_indicators_to_file(instrument.indicators.get("RSI", None))
        if instrument.indicators.get("ATR", None):
            save_indicators_to_file(instrument.indicators.get("ATR", None))


    if settings.strategy_selection == "Profit":
        best_report = choose_best_params_profit(all_reports)
    elif settings.strategy_selection == "Reliable":
        best_report = choose_best_params_reliable(all_reports, settings.numdays, settings.min_profit_ord_percent)
    elif settings.strategy_selection == "Weighted":
        st =  (timenow - timedelta(days=settings.numdays)) if settings.numdays > 0 else settings.start_date
        end = timenow if settings.numdays > 0 else settings.end_date
        best_report = choose_best_params_weighted(all_reports, st, end)
    else:
        best_report = choose_best_params_profit(all_reports)

    #detailed logs to file
    if settings.strategy_log and best_report:
        best_report.save_report(os.path.join(STATS_FOLDER, settings.ticker, settings.strategy_name))
        best_report.strategy_log.save(settings.ticker, settings.strategy_name)


    if not best_report:
        logger.warning("strategy_tester(): best params were not found. NO GO\n")
        return [-1, -1, -1, -1], None
    
    logger.info(f"strategy_tester(): BEST PARAMS to run now on {settings.ticker}: {best_report.params}")
    logger.info(f"strategy_tester(): End\n")

    if best_report:
        best_report.print_kpis()

    #all_reports[0].print_kpis()
    #all_reports[1].print_kpis()
    #all_reports[2].print_kpis()
    #all_reports[3].print_kpis()
    #all_reports[4].print_kpis()

    return best_report.params, best_report

#strategy - function that implements strategy  
#parameters - parameters for strategy
def test_strategy(settings: StrategySettings, candles: list[Tick], instrument: Instr = None):

    #make folders structure for reports
    ticker_dir = STATS_FOLDER + "/" + settings.ticker
    if not os.path.exists(ticker_dir): 
        os.mkdir(ticker_dir)
    strat_dir = ticker_dir + "/" + settings.strategy_name
    if not os.path.exists(strat_dir): 
        os.mkdir(strat_dir)

    all_params_combinations = make_list_of_experiments(settings)

    
    in_sample_candles =  candles[:-int(settings.candles_num * settings.backtest_percent)]  #all candles minus 30% (reserve them for back test)
    in_sample_start_index = len(candles) - settings.candles_num
    out_sample_candles = candles[:]
    out_sample_start_index = len(candles) - int(settings.candles_num * settings.backtest_percent)


    all_reports = train_strategy(in_sample_candles, settings, all_params_combinations, instrument)
    
    return all_reports


'''
Make the list of all possible experiments
out - list of all possible combinations of given parameters and step of their change 
'''
def make_list_of_experiments(settings: StrategySettings):

    range_of_params = []
    for i in settings.params:
        range_of_params.append(range(i[1], i[2], i[3]))

    all_combinations = list(product(*range_of_params))

    if settings.strategy_name in ("strategy_MACD", "strategy_MACD_sl_tp", "strategy_MACD_simple", "strategy_MA_cross", "strategy_MA_cross_sl_tp", "strategy_MA_cross_sl", "strategy_MA_cross_simple", "strategy_MA_Volume", "strategy_MA_Volume_sl", "strategy_MA_ADX_sl", "strategy_MA_cross_price_deviation", "strategy_EMA_cross", "strategy_EMA_cross_simple", "strategy_ADX_MA", "strategy_MACD_RSI", "strategy_trend_pullback"):
        filtered_params = [t for t in all_combinations if t[0] < t[1]]
    else:
        filtered_params = all_combinations[:]

    logger.debug(f"make_list_of_experiments(): all experiments: {filtered_params}")

    return filtered_params

def train_strategy(in_sample_candles: list[Tick], settings: StrategySettings, all_params_combinations: list[tuple], instrument: Instr = None):

    all_reports = []
    counter = 0
    for iter in all_params_combinations:
        report: SingleRunStrategyReport = strategy_single_run(in_sample_candles, settings, iter, instrument)        
        all_reports.append(report)
        
        counter += 1
        if counter%200 == 0:
            logger.info(f"train_strategy(): {counter} of {len(all_params_combinations)} experiments done")

    return all_reports

'''
Run strategy on historical data set with concrete parameters
in - list of Tick = namedtuple('Tick', ['Time','Open','Close','Low','High','Volume'])
   - strategy params in form of [1,2,3,4] where 1,2,3,4 are up to 4 parameters of the strategy
out - report
'''
def strategy_single_run(candles: list[Tick], settings: StrategySettings, params: list[int], instrument: Instr = None):

    current_order = Order(OrderDir.UNSPECIFIED, lots=1, price=0, time=datetime.now(), status=OrderStatus.CLOSED, sl=-1, tp=-1)
    one_run_report = []
    strategy_log = StrategyLog()

    start_index = len(candles) - int(settings.candles_num * (1-settings.backtest_percent))

    logger.debug(f"strategy_single_run(): Start date: {candles[start_index].Time}, End date: {candles[-1].Time}, Candles between: {len(candles) - start_index} ({(candles[-1].Time - candles[start_index].Time).days} days)")
    for i in range(start_index, len(candles)):

        resp: StrategyResp = run_strategy(candles[:i+1], params, settings, instrument, current_order)        

        if resp.cmd == StrategyCommand.OPEN_BUY:
            current_order.close(OrderDir.SELL, candles[i], resp.reason, instrument.spread, one_run_report)
            current_order.open(OrderDir.BUY, candles[i], resp.sl, resp.tp, resp.reason, lots=1, params=params)

        elif resp.cmd == StrategyCommand.OPEN_SELL:
            current_order.close(OrderDir.BUY, candles[i], resp.reason, instrument.spread, one_run_report)
            if settings.shorts_enabled:
                current_order.open(OrderDir.SELL, candles[i], resp.sl, resp.tp, resp.reason, lots=1, params=params)
        
        elif resp.cmd == StrategyCommand.CLOSE_BUY:
            current_order.close(OrderDir.BUY, candles[i], resp.reason, instrument.spread, one_run_report)

        elif resp.cmd == StrategyCommand.CLOSE_SELL:
            current_order.close(OrderDir.SELL, candles[i], resp.reason, instrument.spread, one_run_report)

        elif resp.cmd == StrategyCommand.CLOSE_ALL:
            current_order.close(OrderDir.BUY, candles[i], resp.reason, instrument.spread, one_run_report)
            current_order.close(OrderDir.SELL, candles[i], resp.reason, instrument.spread, one_run_report)

        elif resp.cmd == StrategyCommand.UNSPECIFIED:
            pass
        else:
            logger.error(f"strategy_single_run(): order returned by strategy is not supported - {resp.cmd}")

        strategy_log.add(StratLog1Tick(candles[i], resp.indicator_values[:], params, strat_ord=resp.cmd, reason=resp.reason, sl=resp.sl, tp=resp.tp, action=current_order.last_action))

    #end of strrategy run. Closing last order if any.
    current_order.close(OrderDir.BUY, candles[-1], OrderChangeReason.END_TREND, instrument.spread, one_run_report)
    current_order.close(OrderDir.SELL, candles[-1], OrderChangeReason.END_TREND, instrument.spread, one_run_report)

    report = SingleRunStrategyReport(one_run_report, params, settings.start_capital, strategy_log, candles[start_index].Time, candles[-1].Time)
    report.generate_report()
    report.calcuate_CAGR(candles[start_index].Time, candles[-1].Time)
    report.calculate_Sharpe()
    report.calculate_Profit_Factor()
    report.calcuate_max_drawdown()

    return report

def save_summary(all_reports, report_dir):

    file_name = report_dir + "/summary.log"
    file_report = open(file_name, 'w', newline='')

    for iter in all_reports:
        file_report.write("Margin: " + str(round(iter.profitability, 2)) \
                          + "%, Orders: " + str(iter.num_orders) + "(" + str(iter.num_profit_orders) + "/"+ str(iter.num_loss_orders) + ")" \
                          + " Params: " + str(iter.params) + ", % of profit orders: " + str(round(iter.profit_orders_percent,2)) + "\n")

    file_report.close()
    return

def choose_best_params_profit(all_reports: list[SingleRunStrategyReport]) -> SingleRunStrategyReport:

    number_of_best_values = 20
    min_orders = STRATEGY_MIN_ORDERS
    
    all_reports.sort(reverse=True, key=lambda report: report.profitability)
    #take top 10 reports by profiability among those which have more total orders than "min_orders"
    top_reports = [x for x in all_reports if x.num_orders >= min_orders][:number_of_best_values]
    
    i = 0
    while i<len(top_reports) and top_reports[i].num_orders < min_orders:
        i += 1
    
    if i >= len(top_reports):
        logger.warning(f"choose_best_params_profit(): FAIL: Not enough orders. I ordered top 10 parameters-set by profitability -> Not a sigle one had at least {min_orders} orders made during period")
        return None

    logger.info(f"  choose_best_params_profit(): BEST Profitability: {top_reports[i].profitability}")
    logger.info(f"  choose_best_params_profit(): Start capital: {top_reports[i].start_capital}, End capital: {top_reports[i].end_capital}")
    logger.info(f"  choose_best_params_profit(): Start date: {top_reports[i].start_date}, End capital: {top_reports[i].end_date}")
    logger.info(f"  choose_best_params_profit(): Total orders: {top_reports[i].num_orders} ({top_reports[i].num_profit_orders}/{top_reports[i].num_loss_orders})")
    logger.info(f"  choose_best_params_profit(): Percent of profit orders: {top_reports[i].profit_orders_percent} on params: {top_reports[i].params}")
    logger.info(f"  choose_best_params_profit(): CAGR: {top_reports[i].CAGR}")
    
    if top_reports[i].profitability <= 0.0:
        return None

    #take parameters of top 1
    return top_reports[i]

def choose_best_params_2(all_reports: SingleRunStrategyReport):
    #sort by % of profit orders
    #all_reports.sort(reverse=True, key=lambda report: report.profit_orders_percent)
    all_reports.sort(reverse=True, key=lambda report: report.profitability)

    report_id = -1
    for i in range(0, len(all_reports)):
        #take first with total enough orders that were made and positive profit
        if all_reports[i].num_orders >= STRATEGY_MIN_ORDERS and all_reports[i].profitability > 0:
            report_id = i
            break
    
    if report_id != -1:
        logger.info(f"  choose_best_params_2(): BEST Profitability: {all_reports[report_id].profitability}")
        logger.info(f"  choose_best_params_2(): Total orders: {all_reports[report_id].num_orders} ({all_reports[report_id].num_profit_orders}/{all_reports[report_id].num_loss_orders})")
        logger.info(f"  choose_best_params_2(): Percent of profit orders: {all_reports[report_id].profit_orders_percent} on params: {all_reports[report_id].params}")
    else:
        logger.warning(f"choose_best_params_2(): FAIL: Not enough orders")

    return report_id

def choose_best_params_reliable(all_reports: SingleRunStrategyReport, numdays: int = 0, min_prof_ord_prcnt = STRATEGY_MIN_PROFIT_ORDERS_PERCENT):

    #special case for "numdays" for running strategy tester was set to small value, so we can't expect many orders in general
    if numdays <= 0 or numdays > 15: 
        n_min_orders = STRATEGY_MIN_ORDERS
    else:
        n_min_orders = 2

    all_reports.sort(reverse=True, key=lambda report: report.profitability)
    top_reports = [x for x in all_reports if x.num_orders >= n_min_orders and x.profitability > 0][:]

    best_report: SingleRunStrategyReport = None
    for i in range(0, len(top_reports)):
        #take first with total enough orders that were made and positive profit
        if top_reports[i].profit_orders_percent >= min_prof_ord_prcnt:
            best_report = top_reports[i]
            break
    
    if best_report != None:
        logger.info(f"  choose_best_params_reliable(): BEST Profitability: {best_report.profitability}")
        logger.info(f"  choose_best_params_reliable(): Total orders: {best_report.num_orders} ({best_report.num_profit_orders}/{best_report.num_loss_orders})")
        logger.info(f"  choose_best_params_reliable(): Percent of profit orders: {best_report.profit_orders_percent} on params: {best_report.params}")
    else:
        logger.warning(f"choose_best_params_reliable(): FAIL: Not enough orders")

    return best_report

def choose_best_params_weighted(all_reports: SingleRunStrategyReport, starttime: datetime, endtime: datetime):

    logger.debug(f"--> starttime = {starttime}, endtime = {endtime}")
    for report in all_reports:
        logger.debug(f"--> profitability was: {report.profitability}")
        for order in report.orders_history:
            logger.debug(f"    start={starttime}, end={endtime}, ord={order.timeClose}, profit was = {order.profit}")
            order.profit = order.profit * get_order_profit_multiplier_exp(starttime, endtime, order.timeClose)
            logger.debug(f"    profit now = {order.profit}")
        report.generate_report()
        logger.debug(f"--> profitability now: {report.profitability}")

    return choose_best_params_profit(all_reports)

def get_order_profit_multiplier_linear(starttime: datetime, endtime: datetime, ordertime: datetime):
    return 1.0 + (ordertime - starttime).total_seconds()/(endtime - starttime).total_seconds()


multipliers: list[float] = [-1] * 101
def get_order_profit_multiplier_exp(starttime: datetime, endtime: datetime, ordertime: datetime):
    '''Get profit multiplier for for choose best params wheighed function. Multipliers are in exponential order based on m_koef'''
    global multipliers
    m_koef = 1.0272
    if multipliers[0] == -1:
        multipliers[0] = 1
        for i in range(1, 101, 1):
            multipliers[i] = multipliers[i-1] * m_koef

    index = int(100*(ordertime - starttime).total_seconds()/(endtime - starttime).total_seconds())

    return multipliers[index]


if __name__ == "__main__":
    main()
