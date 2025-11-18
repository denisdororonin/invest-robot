import os
import re
import glob
from datetime import datetime, timezone
import pickle

from utils import setup_logger
from globals import INDICATORS_FOLDER

logger = setup_logger(__name__)

class IndicatorAttr:
    def __init__(self, time: datetime, p1=-1, p2=-1, p3=-1, p4=-1):
        self.time: datetime = time
        self.param1: int = p1
        self.param2: int = p2
        self.param3: int = p3
        self.param4: int = p4

    def __eq__(self, other):
        return isinstance(other, IndicatorAttr) and self.time == other.time \
                                                and self.param1 == other.param1 and self.param2 == other.param2 \
                                                and self.param3 == other.param3 and self.param4 == other.param4

    def __hash__(self):
        return hash((self.time, self.param1, self.param2, self.param3, self.param4))

class IndicatorAttrSimple:
    def __init__(self, time: datetime, p1: int):
        self.time: datetime = time
        self.param1: int = p1

    def __eq__(self, other):
        return isinstance(other, IndicatorAttrSimple) and self.time == other.time and self.param1 == other.param1

    def __hash__(self):
        return hash((self.time, self.param1))

class IndicatorAttrMACD:
    def __init__(self, time: datetime, p1: int, p2: int, p3: int):
        self.time: datetime = time
        self.param1: int = p1
        self.param2: int = p2
        self.param3: int = p3

    def __eq__(self, other):
        return isinstance(other, IndicatorAttrMACD) and self.time == other.time \
                                                and self.param1 == other.param1 and self.param2 == other.param2 and self.param3 == other.param3

    def __hash__(self):
        return hash((self.time, self.param1, self.param2, self.param3))


class IndicatorValues:
    def __init__(self, ticker: str, indicator_name: str):
        self.ticker = ticker
        self.ind_name = indicator_name
        self.values: dict[IndicatorAttr : list[float]] = {}

class IndicatorValuesSimple:
    def __init__(self, ticker: str, indicator_name: str):
        self.ticker = ticker
        self.ind_name = indicator_name
        self.values: dict[IndicatorAttrSimple : float] = {}

class IndicatorValuesMACD:
    def __init__(self, ticker: str, indicator_name: str):
        self.ticker = ticker
        self.ind_name = indicator_name
        self.values: dict[IndicatorAttrMACD : list[float]] = {}

indicators_class_map = {"SMA": IndicatorValuesSimple, "EMA": IndicatorValues, "SMMA": IndicatorValues, "ADX": IndicatorValues, "MACD": IndicatorValuesMACD, "RSI": IndicatorValuesSimple, "ATR": IndicatorValuesSimple}

def load_indicators_from_file(ticker: str, indicator_name: str, filename: str = None):
    
    if not filename: 
        filename = os.path.join(INDICATORS_FOLDER, ticker + "_" + indicator_name + "_values.dat")

    logger.info(f"load_indicators_from_file(): loading {ticker}:{indicator_name} from {filename}")
    try:
        with open(filename, "rb") as file:
            indicators = pickle.load(file)
    except FileNotFoundError:
        indicators = indicators_class_map[indicator_name](ticker, indicator_name)
        save_indicators_to_file(indicators)

    return indicators

def load_indicators_from_partition_files(ticker: str, indicator_name: str):
    
    all_indicators: dict = {}

    filenames = glob.glob(os.path.join(INDICATORS_FOLDER, ticker + "_" + indicator_name + "_*-*_" + "values.dat"))

    year_mon_reg_exp = re.compile(r"(?P<year_mon>\d{4}-\d{2})")
    for filename in filenames:
        result = year_mon_reg_exp.search(filename)
        if result:
            all_indicators |= {result.group("year_mon"): load_indicators_from_file(ticker, indicator_name, filename)}

    return all_indicators


def save_indicators_to_file(indicator_values):

    if not os.path.exists(INDICATORS_FOLDER): 
        os.mkdir(INDICATORS_FOLDER)

    filename = os.path.join(INDICATORS_FOLDER, indicator_values.ticker + "_" + indicator_values.ind_name + "_values.dat")

    with open(filename, "wb") as file:
        pickle.dump(indicator_values, file=file)
    return

def save_indicators_to_parition_files(all_indicators_values: dict):

    if not os.path.exists(INDICATORS_FOLDER): 
        os.mkdir(INDICATORS_FOLDER)

    for indicator_values in all_indicators_values.items():
        filename = os.path.join(INDICATORS_FOLDER, indicator_values[1].ticker + "_" + indicator_values[1].ind_name + "_" + indicator_values[0] + "_values.dat")

        with open(filename, "wb") as file:
            pickle.dump(indicator_values[1], file=file)
    
    return
