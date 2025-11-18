import os
import pickle
import copy
from globals import OrderChangeReason, OrderStatus, PerformedAction, OrderDir, StrategyCommand, Trend
from globals import BROKER_FEE, ORD_CHNG_REASON_STR, ORD_STAT_STR, ORDER_DIR_STR,STRATEGY_SETTINGS_FOLDER
from candles import Tick
from datetime import datetime
from utils import setup_logger

logger = setup_logger(__name__)

class Order:
    def __init__(self, direction: OrderDir, lots, price, time, status = OrderStatus.OPEN, sl=-1, tp=-1):
        self.direction: OrderDir = direction
        self.status: OrderStatus = status
        self.lots: int = lots
        self.o_price: float = price
        self.c_price: float = -1
        self.o_time: datetime = time
        self.c_time: datetime = None
        self.sl: float = sl
        self.tp: float = tp
        self.params: list[int] = [-1, -1, -1, -1]
        self.reason: OrderChangeReason = OrderChangeReason.UNSPECIFIED
        self.last_action: PerformedAction = PerformedAction.DID_NOTHING
        self.extras: dict = {}
        self.profit = 0
        self.profit_percent = 0

    #close order means to create new order in orders history adding operation, open/close times and prices as well as number of lots.
    def close(self, operation: OrderDir, candle: Tick, reason: OrderChangeReason, spread: float, report: list, ticker: str = ""):

        if self.status == OrderStatus.OPEN and self.direction == operation:
            if reason == OrderChangeReason.STOP_LOSS and self.sl > 0:
                self.c_price = self.sl
            elif reason == OrderChangeReason.TAKE_PROFIT and self.tp > 0:
                self.c_price = self.tp
            else:
                self.c_price = candle.Close

            self.c_time = candle.Time
            self.reason = reason
            self.status = OrderStatus.CLOSED
            if self.direction == OrderDir.BUY:
                if self.reason == OrderChangeReason.STOP_LOSS:
                    self.last_action = PerformedAction.CLOSED_BUY_SL
                elif self.reason == OrderChangeReason.TAKE_PROFIT:
                    self.last_action = PerformedAction.CLOSED_BUY_TP
                else:
                    self.last_action = PerformedAction.CLOSED_BUY
            if self.direction == OrderDir.SELL:
                if   self.reason == OrderChangeReason.STOP_LOSS:
                    self.last_action = PerformedAction.CLOSED_SELL_SL
                elif self.reason == OrderChangeReason.TAKE_PROFIT:
                    self.last_action = PerformedAction.CLOSED_SELL_TP
                else:
                    self.last_action = PerformedAction.CLOSED_SELL           

            self.profit = self.lots*(self.c_price - self.o_price) if self.direction == OrderDir.BUY else self.lots*(self.o_price - self.c_price)
            self.profit -= self.lots*self.o_price*BROKER_FEE #subtract broker fee from profit for open order
            self.profit -= self.lots*self.c_price*BROKER_FEE #subtract broker fee from profit for close order
            self.profit -= 2*self.lots*spread
            self.profit_percent = round(100*self.profit/(self.lots*self.o_price), 2)
        
            report.append(copy.deepcopy(self))

            #only when calling from trade_bot (when calling from strategy_tester, ticker must be "")
            if ticker != "":
                with open(os.path.join(STRATEGY_SETTINGS_FOLDER, "order_" + ticker + ".dat"), "wb") as file:
                    pickle.dump(self, file)

        return

    def open(self, direction: OrderDir, candle: Tick, sl, tp, reason: OrderChangeReason, lots: int, params: list[int], ticker: str = ""):
        
        if self.status != OrderStatus.OPEN:
            self.status = OrderStatus.OPEN
            self.direction = direction
            self.lots = lots
            self.o_price = candle.Close
            self.o_time = candle.Time
            self.sl = sl
            self.tp = tp
            self.c_price = -1
            self.c_time = None
            self.params = params[:]
            self.reason = reason

            if reason in (OrderChangeReason.NEW_TREND, OrderChangeReason.RESTORE):
                self.last_action = PerformedAction.OPENED_BUY if self.direction == OrderDir.BUY else PerformedAction.OPENED_SELL
            elif reason == OrderChangeReason.CHANGE_DIRECTION:
                self.last_action = PerformedAction.CHANGED_DIR_TO_BUY if self.direction == OrderDir.BUY else PerformedAction.CHANGED_DIR_TO_SELL
            else:
                self.last_action = PerformedAction.DID_NOTHING
                logger.error(f"open_order(): order was opened with reason {ORD_CHNG_REASON_STR[reason]} - not supported")

            #only when calling from trade_bot (when calling from strategy_tester, ticker must be "")
            if ticker != "":
                with open(os.path.join(STRATEGY_SETTINGS_FOLDER, "order_" + ticker + ".dat"), "wb") as file:
                    pickle.dump(self, file)

        return
    
    def print(self):
        logger.info(f"Current order: Status: {ORD_STAT_STR[self.status]} Dir: {ORDER_DIR_STR[self.direction]} Lots: {self.lots} \n\
                    O price: {self.o_price} C price: {self.c_price} O time: {self.o_time} C time: {self.c_time}\n\
                    SL: {self.sl} TP: {self.tp} Reason: {ORD_CHNG_REASON_STR[self.reason]}")
        

class StrategyResp: 
    def __init__(self, cmd: StrategyCommand, reason: OrderChangeReason = OrderChangeReason.UNSPECIFIED, sl: float=-1, tp: float=-1, lots: int = 1, ind_val: list[float] = [-1,-1,-1,-1], trend: Trend = Trend.UNSPECIFIED):
        self.cmd: StrategyCommand = cmd
        self.trend: Trend = trend
        self.tp: float = tp
        self.sl: float = sl
        self.lots = lots
        self.reason: OrderChangeReason = reason
        self.indicator_values = ind_val[:]
        return
