from sys import maxsize
from candles import Tick

class Indicators:

    def sma(data: list[float], period: int) -> float:

        if period <= 0 or len(data) < period:
            raise Exception("Data too short or period is wrong. Period: ", period, ". Data len: ", len(data))

        return sum(data[-period:])/period

    #the function below seems to be correct: chat GPT returned same value as this function up to 10th digits after dot.
    def ema(data: list[float], period: int) -> float:

        if period <= 0 or len(data) < 2*period:
            raise ValueError("Data too short or period is wrong. Expected: ", 2*period, ". Data len: ", len(data))

        k = 2.0/(period + 1.0)
        p =  period if len(data) >= 2*period else len(data) - period
        prev_ema = Indicators.sma(data[:-period], p)
        for iter in data[-period:]:
            ema = (iter - prev_ema)*k + prev_ema
            prev_ema = ema

        return ema

    def smma(data, period):

        if period < 1:
            raise Exception("Wrong period parameter: ", period)
        if len(data) < period*2:
            raise Exception("Data too short. Expected: ", period*2, ". Got: ", len(data))

        prev_sma = sum(data[-period*2: -period])/period

        for iter in data[-period:]:
            prev_sma = (prev_sma*(period-1) + iter)/period

        return prev_sma
    
    def alligator(data, jaw_p, teeth_p, lip_p, jaw_s, teeth_s, lip_s):

        if jaw_p < 1 or teeth_p < 1 or lip_p < 1 or jaw_s < 1 or teeth_s < 1 or lip_s < 1:
            raise Exception("Bad input parameters: ", jaw_p, teeth_p, lip_p, jaw_s, teeth_s, lip_s, sep = " ")

        minlen = jaw_p*2+jaw_s
        if len(data) < minlen:
            raise Exception("Data too short. Expected: ", minlen, ". Got: ", len(data))

        gator = [0, 0, 0]
        gator[0] = Indicators.smma(data[:-jaw_s], jaw_p)
        gator[1] = Indicators.smma(data[:-teeth_s], teeth_p)
        gator[2] = Indicators.smma(data[:-lip_s], lip_p)

        return gator

    def macd(data: list[float], fast, slow, signal) -> tuple:

        if fast < 1 or slow < 1 or signal < 1:
            raise ValueError("Wrong input parameters: ", fast, slow, signal, sep=" ")

        if len(data) < 2*slow + 2*signal:
            raise ValueError(f"Data length must be not less than 2*slow + 2*signal. But len={len(data)}, slow={slow}, signal={signal}")

        macd = [0.0]*signal*2
        macd[signal*2-1] = Indicators.ema(data[-2*fast:], fast) - Indicators.ema(data[-2*slow:], slow)
        for i in range(1, signal*2):
            macd[signal*2-1-i] = Indicators.ema(data[-2*fast-i:-i], fast) - Indicators.ema(data[-2*slow-i:-i], slow)

        signal_line = Indicators.ema(macd, signal)

        return macd[-1], signal_line, macd[-1]-signal_line    

    #the function below seems to be correct: chat GPT returned same value as this function did.
    def rsi(data: list, period: int = 14) -> float:
        """
        Calculate the most recent Relative Strength Index (RSI).

        Parameters:
            data (list): A list containing the price data (e.g., closing prices).
            period (int): The look-back period for calculating RSI (default is 14).

        Returns:
            float: The most recent RSI value.
        """
        if len(data) < period + 1:
            raise ValueError("Data length must be greater than the period.")
        
        if period <= 0:
            raise ValueError("Period must be greater than zero")

        # Calculate price changes for the most recent period
        delta = [data[i] - data[i - 1] for i in range(1, len(data))]
        recent_delta = delta[-period:]

        # Separate gains and losses
        gain = sum(x for x in recent_delta if x > 0)
        loss = -sum(x for x in recent_delta if x < 0)

        # Avoid division by zero
        if loss == 0:
            return 100.0

        # Calculate the Relative Strength (RS)
        rs = gain / loss

        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def stochastic(data, params):
        """
        Calculate the most recent %K and %D values of the Stochastic Oscillator.

        Parameters:
            close_prices (list): List of candle close values.
            params (list): List of oscillator parameters [k_period, d_period, smooth].

        Returns:
            tuple: The most recent Stochastic Oscillator values (%K, %D).
        """
        k_period, d_period, smooth = params
    
        # Check if there are enough close prices
        if len(data) < k_period:
            raise ValueError("Not enough close prices to calculate the Stochastic Oscillator.")

        # Check if params are sane
        if k_period < 1 or d_period < 1 or smooth < 1:
            raise ValueError(f"Params are not suitable to calculate the Stochastic Oscillator: {k_period},{d_period},{smooth}")

        # Calculate %K
        recent_close = data[-1]
        lowest_low = min(data[-k_period:])
        highest_high = max(data[-k_period:])
    
        if highest_high == lowest_low:
            percent_k = 0
        else:
            percent_k = ((recent_close - lowest_low) / (highest_high - lowest_low)) * 100

        # Calculate %D (smoothed %K values over the d_period)
        if len(data) < k_period + d_period - 1:
            raise ValueError("Not enough close prices to calculate smoothed %D.")

        recent_k_values = []
        for i in range(d_period):
            lowest_low_d = min(data[-k_period - i:-i or None])
            highest_high_d = max(data[-k_period - i:-i or None])
            if highest_high_d == lowest_low_d:
                recent_k_values.append(0)
            else:
                recent_k_values.append(((data[-1 - i] - lowest_low_d) / (highest_high_d - lowest_low_d)) * 100)

        # Smooth the %K values for %D calculation
        percent_d = sum(recent_k_values[-smooth:]) / smooth

        return percent_k, percent_d

    def calculate_tr(high, low, close_prev):
        return max(high - low, abs(high - close_prev), abs(low - close_prev))


    def adx(low: list[float], high: list[float], close: list[float], period=14) -> float:
        """
        Calculate the Average Directional Index (ADX) indicator.
        :param low, high, close values from the market.
        :param period: Lookback period (default is 14 days).
        :return: ADX value.
        """
        if len(low) != len(high) or len(low) != len(close):
            raise ValueError(f"Lengths of low/high/close lists are not equal: {len(low)}:{len(high)}:{len(close)}")
    
        if len(low) < 2*(period+1):
            raise ValueError(f"Data lengh too small: len={len(low)}, expected {2*(period+1)}")
    
        tr_list, plus_dm_list, minus_dm_list = [], [], []
        for i in range(1, len(low)):
        
            tr = Indicators.calculate_tr(high[i], low[i], close[i-1])
            plus_dm = max(high[i] - high[i-1], 0) if (high[i] - high[i-1]) > (low[i-1] - low[i]) else 0
            minus_dm = max(low[i-1] - low[i], 0) if (low[i-1] - low[i]) > (high[i] - high[i-1]) else 0
        
            tr_list.append(tr)
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
    
        tr_smoothed = [Indicators.sma(tr_list[i:i+period], period) for i in range(len(tr_list)-period+1)]
        plus_dm_smoothed = [Indicators.smma(plus_dm_list[i:i+2*period], period) for i in range(len(plus_dm_list)-2*period+1)]
        minus_dm_smoothed = [Indicators.smma(minus_dm_list[i:i+2*period], period) for i in range(len(minus_dm_list)-2*period+1)]
        tr_smoothed = tr_smoothed[-len(plus_dm_smoothed):]

        plus_di = [100 * (plus_dm_smoothed[i] / tr_smoothed[i]) for i in range(len(tr_smoothed))]
        minus_di = [100 * (minus_dm_smoothed[i] / tr_smoothed[i]) for i in range(len(tr_smoothed))]
    
        dx = [100 * abs(plus_di[i] - minus_di[i]) / (plus_di[i] + minus_di[i]) for i in range(len(plus_di))]
    
        adx = Indicators.smma(dx, period)
        return adx, plus_di[-1], minus_di[-1]

    def boilinger(data: list[float], period: int) -> tuple:

        if len(data) < 2*period:
            raise ValueError(f"Data lengh too small: len={len(data)}, expected {2*period}")

        multiplier = 2.0
        middle = Indicators.sma(data, period)

        #Standard deviation formula: sqrt (1/Period * SUM( (Price[i] - SMA)^2 ) )
        #Where i from 0 to Period; SMA - from Period
        deviation = (sum([(data[i] - Indicators.sma(data[i+1-period:i+1], period))**2 for i in range(len(data)-period, len(data))])/period)**0.5

        upper = middle + deviation*multiplier
        lower = middle - deviation*multiplier

        return middle, upper, lower

    def atr(candles: list[Tick], period: int) -> float:

        if len(candles) < 2*period + 1:
            raise ValueError(f"Data lengh too small: len={len(candles)}, expected {2*period + 1}")

        candles_num = len(candles)
        true_range = [max(candles[i].High - candles[i].Low, candles[i].High - candles[i-1].Close, candles[i].Low - candles[i-1].Close) for i in range(candles_num - 2*period, candles_num)]

        return Indicators.ema(true_range, period)
    

    def dailypivotpoints(candles: list[Tick]) -> tuple:
        
        curr_day = candles[-1].Time.day
        prev_day = -1
        for i in range(-1, -len(candles), -1):
            if candles[i].Time.day != curr_day:
                prev_day = candles[i].Time.day
                prev_day_index = i
                break
        
        prev_day_close = candles[prev_day_index].Close
        prev_day_high = -1
        prev_day_low = maxsize

        for i in range(prev_day_index, -len(candles), -1):
            if prev_day == candles[i].Time.day:
                if candles[i].High > prev_day_high: 
                    prev_day_high = candles[i].High
                if candles[i].Low < prev_day_low: 
                    prev_day_low = candles[i].Low
            else:
                break

        p  = (prev_day_close + prev_day_high + prev_day_low)/3
        r1 = 2*p - prev_day_low
        s1 = 2*p - prev_day_high
        r2 = p + (prev_day_high - prev_day_low)
        s2 = p - (prev_day_high - prev_day_low)

        return r1, s1, r2, s2

#ema10 = Indicators.ema([414.35,415.6,414.6,417.15,416.9,415.55,417.0,416.8,417.5,419.15,420.75,422.65,428.1,427.5,426.8,422.3,423.0,425.5,424.25,429.75], 10)
#print(ema10)

#rsi14 = Indicators.rsi([414.35,415.6,414.6,417.15,416.9,415.55,417.0,416.8,417.5,419.15,420.75,422.65,428.1,427.5,426.8,422.3,423.0,425.5,424.25,429.75], 14)
#print(rsi14)



