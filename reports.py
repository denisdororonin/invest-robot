import os
import numpy as np
from datetime import datetime, timedelta
from schemas import Order
from utils import setup_logger, get_param
from globals import OrderChangeReason, StrategyCommand, OrderStatus, PerformedAction
from globals import STATS_FOLDER, STRAT_CMD_STR, ORD_CHNG_REASON_STR, PERF_ACTION_STR, WORK_DAYS_RATE
from candles import Tick

logger = setup_logger(__name__)

class StratLog1Tick:
    def __init__(self, candle: Tick, indicators: list[float], params: list[int], strat_ord: StrategyCommand, reason: OrderChangeReason, sl: float, tp: float, action: PerformedAction):
        self.candle: Tick = candle
        self.indicators: list[float] = indicators[:]
        self.params: list[int] = params[:]
        self.strat_ord: StrategyCommand = strat_ord
        self.sl = sl
        self.tp = tp
        self.reason: OrderChangeReason = reason
        self.action = action

class StrategyLog:
    def __init__(self):
        self.log: list[StratLog1Tick] = []
    
    def add(self, log: StratLog1Tick):
        self.log.append(log)

    def save(self, ticker: str, strategy: str):

        ticker_dir = os.path.join(STATS_FOLDER, ticker)
        if not os.path.exists(ticker_dir): os.mkdir(ticker_dir)
        strat_dir = os.path.join(ticker_dir, strategy)
        if not os.path.exists(strat_dir): os.mkdir(strat_dir)
        filename = os.path.join(strat_dir, "strat-"  + str(self.log[0].params) + ".csv")

        with open(filename, 'w', newline='') as file_report:

            file_report.write("Time,Open,Close,Low,High,Volume,Indicator1,Indicator2,Indicator3,Indicator4,Param1,Param2,Param3,Param4,Command,Reason,SL,TP,Last Action\n")
            for i in self.log:
                file_report.write(i.candle.Time.strftime("%Y-%m-%d %H:%M:%S") + "," + 
                                  '{:.4f}'.format(round(i.candle.Open, 4)) + "," + '{:.4f}'.format(round(i.candle.Close, 4)) + "," + 
                                  '{:.4f}'.format(round(i.candle.Low, 4)) + "," + '{:.4f}'.format(round(i.candle.High, 4)) + "," + 
                                  '{0:07d}'.format(i.candle.Volume) + "," + 
                                  '{:.4f}'.format(round(i.indicators[0], 4)) + "," + '{:.4f}'.format(round(i.indicators[1], 4)) + "," + 
                                  '{:.4f}'.format(round(i.indicators[2], 4)) + "," + '{:.4f}'.format(round(i.indicators[3], 4)) + "," + 
                                  '{0:03d}'.format(get_param(i.params, 0)) + "," + '{0:03d}'.format(get_param(i.params, 1)) + "," + 
                                  '{0:03d}'.format(get_param(i.params, 2)) + "," + '{0:03d}'.format(get_param(i.params, 3)) + "," + 
                                  str(STRAT_CMD_STR[i.strat_ord]) + "," + str(ORD_CHNG_REASON_STR[i.reason]) + "," +
                                  '{:.4f}'.format(round(i.sl, 4)) + "," + '{:.4f}'.format(round(i.tp, 4)) + "," +
                                  str(PERF_ACTION_STR[i.action]) + "\n")
        
        return


class SingleRunStrategyReport:

    def __init__(self, orders_hist, params, start_capital, strategy_log: StrategyLog, start_date: datetime, end_date: datetime):
        self.num_orders = 0 #number of completed orders
        self.total_profit = 0 #sum of all completed orders result (profits and losses)
        self.num_profit_orders = 0
        self.num_loss_orders = 0
        self.profit_orders_percent = 0.0
        self.profitability = 0.0 #sum of profit/loss percents for each order

        self.start_date = start_date
        self.end_date = end_date
        self.start_capital = start_capital
        self.end_capital = 0

        self.orders_history: list[Order] = orders_hist #all closed order after strategy run on fixed set of parameters was done
        self.returns: dict = {}
        self.equities: list[float]
        self.__make_empty_returns()
        self.params = params #fixed list of parameters used to run the strategy
        self.strategy_log: StrategyLog = strategy_log

        self.CAGR = 0.0
        self.mean_return = 0.0
        self.std_return = 0.0
        self.Sharpe = 0.0
        self.profit_factor = 0.0
        self.maxDD = 0.0

    def __make_empty_returns(self):
        self.returns.clear()
        current = self.start_date
        while current <= self.end_date:
            self.returns[current.date()] = 0.0
            current += timedelta(days=1)
        self.returns[self.end_date.date()] = 0.0
        return
    
    def print_kpis(self):
        #for key, value in self.returns.items():
        #    logger.info(f"{key} : {value}")

        logger.info(f"CAGR: {self.CAGR}")
        logger.info(f"Sharpe: {self.Sharpe}")
        logger.info(f"Profit factor: {self.profit_factor}")
        logger.info(f"Max Drawdown (MaxDD)): {self.maxDD}")

        return

    def generate_report(self):
        if len(self.orders_history) > 0:
            self.num_orders = len(self.orders_history)
            self.num_profit_orders = len([p for p in self.orders_history if p.profit > 0])
            self.num_loss_orders = len([p for p in self.orders_history if p.profit < 0])
            for iter in self.orders_history:
                self.total_profit += iter.profit
                self.profitability += round(100*iter.profit/iter.o_price, 2)
            self.profit_orders_percent = 100.0*(float(self.num_profit_orders)/float(self.num_orders))
            self.end_capital = self.start_capital + self.total_profit
    
    def calcuate_CAGR(self, startdate, enddate):
        y = (enddate - startdate).days/365
        self.CAGR = ((self.end_capital/self.start_capital) ** (1/y)) - 1        
        return

    #Sharpe values
    #  < 0.5	    Weak / Unstable
    #  0.5 – 1.0	Borderline
    #  1.0 – 1.5	Acceptable
    #  1.5 – 2.0	Good
    #  2.0 – 3.0	Excellent
    #  > 3.0	    Exceptional (watch for overfitting!)
    def calculate_Sharpe(self):

        risk_free_rate = 0
        periods_per_year = 365/WORK_DAYS_RATE
        #fill in strategy returns for every single day
        self.__make_empty_returns()
        for i in self.orders_history:
            #TODO: I need to divide i.profit to current captial here, not open price value
            self.returns[i.c_time.date()] =self.returns[i.c_time.date()] + i.profit/(i.o_price*i.lots)

        #calculate average daily return and standard deveiation of daily returns
        self.mean_return = sum(self.returns.values())/len(self.returns)
        profits = np.array(list(self.returns.values()))
        self.std_return = np.std(profits, ddof=1)

        excess_return = self.mean_return - (risk_free_rate / periods_per_year)
        self.Sharpe = (excess_return / self.std_return) * np.sqrt(periods_per_year)

        return

    def calculate_Profit_Factor(self):

        sum_profit = sum([p.profit for p in self.orders_history if p.profit > 0])
        sum_loss = sum([p.profit for p in self.orders_history if p.profit < 0])
        self.profit_factor = sum_profit/abs(sum_loss)

        return

    def calcuate_max_drawdown(self):

        #create date:capital based dict
        equities_dict = {}
        current = self.start_date
        while current <= self.end_date:
            equities_dict[current.date()] = 0.0
            current += timedelta(days=1)
        equities_dict[self.end_date.date()] = 0.0

        #fill dict with profits per days
        for i in self.orders_history:
            equities_dict[i.c_time.date()] = equities_dict[i.c_time.date()] + i.profit

        #get all daily profits(or loses) to list
        equities = list(equities_dict.values())
        
        #now convert it to equities at the end of each day
        equities[0] = self.start_capital + equities[0]
        for i in range(1, len(equities)):
            equities[i] = equities[i-1] + equities[i]

        peaks = [0]*len(equities)
        for i in range(0, len(equities)):
            peaks[i] = max(equities[0:i+1])

        drawdowns = [0]*len(equities)
        for i in range(0, len(equities)):
            drawdowns[i] = (equities[i] - peaks[i])/peaks[i]

        self.maxDD = min(drawdowns)
        return

    def print_report(self):
        logger.info("Run summary: ")
        logger.info(f"    Strategy params: {self.params}")
        logger.info(f"    Total orders: {self.num_orders}")
        logger.info(f"    Profit orders: {self.num_profit_orders}")
        logger.info(f"    Loss orders: {self.num_loss_orders}")
        logger.info(f"    Profit: {self.total_profit}")
        logger.info(f"    Profitability: {self.profitability}%")

    def print_strategy_log(self):
        for i in self.strategy_log:
            logger.info(f"{i}")
        return
    
    def save_report(self, rep_dir):
        file_name = rep_dir + "\\param-" + str(self.params) + ".log"
        file_report = open(file_name, 'w', newline='')

        file_report.write("Orders: " + str(self.num_orders) + " (Profit: " + str(self.num_profit_orders) + "/Loss: " + str(self.num_loss_orders) + ")\n")
        file_report.write("Profit: " + str(round(self.total_profit,2)) + ", Profitability: " + str(round(self.profitability, 2)) + "%\n\n")

        operation = {0: "UNSPECIFIED", 1: "BUY ", 2: "SELL"}
        for i in self.orders_history:
            file_report.write(str(operation[i.direction]) + ": Tm open: " + i.o_time.strftime("%Y-%m-%d %H:%M:%S") + ", Tm close: " + i.c_time.strftime("%Y-%m-%d %H:%M:%S") + ", Pr open: " + '{:.4f}'.format(round(i.o_price, 4)) + ", Pr close: " + '{:.4f}'.format(round(i.c_price, 4)) + ", Profit: " + '{:+.2f}'.format(round(i.profit_percent, 2)) + "% Close Reason: " + ORD_CHNG_REASON_STR[i.reason] + "\n")

        file_report.close()
        return
