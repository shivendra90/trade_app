# Database Retrieval & Save functions used in all files
import mysql.connector as sqlConnector
import pandas as pd
from sqlalchemy import create_engine
import datetime
class DBHelper:
    def __init__(self):
        self.con = sqlConnector.connect(host="localhost", user="root", passwd="*******", database="algo", port="3306")
        self.conTick = sqlConnector.connect(host="localhost", user="root", passwd="*******", database="algo", port="3306")
        self.conTick2 = sqlConnector.connect(host="localhost", user="root", passwd="*******", database="algo", port="3306")
        print('target database host: ' + self.con._host)
    #Market Orders    
    
    def GetData(self, query):
        df = pd.read_sql(query, con=self.con)
        return df
    
    def execute_query(self, query):
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def GetOrdersList(self, sdate, edate, userid, status, intent):
        query = "Select zerodha_id, instrument,exchange, qty, transaction_type from marketorders where (timestamp between '{}' AND '{}') AND userid = '{}' AND status = '{}' AND intent = '{}'".format(sdate, edate, userid, status, intent)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def GetOrdersListCompleted(self, sdate, edate, userid, status, intent, slstatus):
        query = "Select zerodha_id, instrument,exchange, qty, transaction_type, remarks, price_executed, limitprice from marketorders where (timestamp between '{}' AND '{}') AND userid = '{}' AND status = '{}' AND intent = '{}' AND StopLossStatus = '{}'".format(sdate, edate, userid, status, intent, slstatus)
        #print(query)
        df = pd.read_sql(query, con=self.con)
        #print(df)
        return df  
    def GetOrdersListCompletedStrategy(self, sdate, status, intent, slstatus, startegy):
        query = "Select zerodha_id, instrument,exchange, qty, transaction_type, remarks, price_executed, limitprice from marketorders where Date(timestamp) = '{}' AND status = '{}' AND intent = '{}' AND StopLossStatus = '{}' AND remarks = '{}' and transaction_type = 'SELL'".format(sdate, status, intent, slstatus, startegy)
        #print(query)
        df = pd.read_sql(query, con=self.con)
        #print(df)
        return df  
    def GetOrdersDetails(self, orderid):
        query = "Select qty, transaction_type, price_executed, status, intent, limitprice, order_type, instrument, exchange, remarks from marketorders where zerodha_id = '{}'".format(orderid)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def updateOrder(self, status, price, zerodha_id):
        query = "update marketorders set status = '{}', price_executed = '{}' where zerodha_id = '{}'".format(status, price, zerodha_id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def updateOrderStatus(self, status, zerodha_id):
        query = "update marketorders set status = '{}' where zerodha_id = '{}'".format(status, zerodha_id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def updateOrderQty(self, qty, zerodha_id):
        query = "update marketorders set qty = '{}' where zerodha_id = '{}'".format(qty, zerodha_id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    
    def changeStopLossOrderStatus(self, sl_status, zerodha_main_order_id):
        query = "update marketorders set StopLossStatus = '{}' where zerodha_id = '{}'".format(sl_status, zerodha_main_order_id)
        #print(query)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def changeOrderPrice(self, zerodha_id, price):
        query = "update marketorders set price_executed = '{}' where zerodha_id = '{}'".format(price, zerodha_id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()    
    
    #Manual Orders
    def GetManualOrdersList(self, userid):
        query = "Select * from manualtrades where active = 1 and userid = '{}'".format(userid)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def updateManualOrderActive(self, status, sno):
        query = "update manualtrades set active = '{}' where sno = '{}'".format(status, sno)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    #trailing order
    def GetTrailingBUYOrdersList(self, userid):
        query = "Select * from trailingbuyorders where active = 1 and userid = '{}'".format(userid)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def updateTrailingBUYOrderActive(self, status, sno):
        query = "update trailingbuyorders set active = '{}' where sno = '{}'".format(status, sno)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def updateTrailingSELLOrderActive(self, status, sno):
        query = "update trailingsellorders set active = '{}' where sno = '{}'".format(status, sno)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def updateTrailingBUYOrderTrail(self, trail, sno):
        query = "Update trailingbuyorders set trail = '{}' where sno = '{}'".format(trail, sno)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def updateTrailingSELLOrderTrail(self, trail, sno):
        query = "Update trailingsellorders set trail = '{}' where sno = '{}'".format(trail, sno)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def updateTrailingBUYOrderExecutionPrice(self, new_execution_price, sno):
        query = "Update trailingbuyorders set current_execution_price = '{}' where sno = '{}'".format(new_execution_price, sno)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    def updateTrailingSELLOrderExecutionPrice(self, new_execution_price, sno):
        query = "Update trailingsellorders set current_execution_price = '{}' where sno = '{}'".format(new_execution_price, sno)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def GetTrailingSELLOrdersList(self, userid):
        query = "Select * from trailingsellorders where active = 1 and userid = '{}'".format(userid)
        df = pd.read_sql(query, con=self.con)
        return df
    
    #Regression to mean
    def setTrailingBUYOrderActive(self, trail_trigger_price, index_name):
        query = "update trailingbuyorders set active = 1, trail = 1, trail_trigger_price = '{}' where trade = 1 and index_name = '{}'".format(trail_trigger_price, index_name)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def setTrailingSELLOrderActive(self, trail_trigger_price, index_name):
        query = "update trailingsellorders set active = 1, trail = 1, trail_trigger_price = '{}' where trade = 1 and index_name = '{}'".format(trail_trigger_price, index_name)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def GetTrailingBUYOrdersCount(self, userid):
        query = "Select count(*) as len from trailingbuyorders where active = 1 and trade = 1 and index_name = 'NIFTY' and userid = '{}'".format(userid)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def GetTrailingSELLOrdersCount(self, userid):
        query = "Select count(*) as len from trailingsellorders where active = 1 and trade = 1 and index_name = 'NIFTY' and userid = '{}'".format(userid)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def GetActiveInstrumentMaster(self):
        query = "SELECT SQL_NO_CACHE * FROM instrument_master where trade = 1"
        df = pd.read_sql(query, con=self.con)
        return df
    
    def GetActiveInstrumentMasterBySymbol(self, trading_symbol):
        query = "SELECT SQL_NO_CACHE * FROM instrument_master where trading_symbol = '{}'".format(trading_symbol)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def UpdateFirstTradeStatus(self, first_trade_status, trade_status, currentphase, idnum):
        query = "update instrument_master set first_trade = '{}', trade_status = '{}', currentphase = '{}' where id = '{}'".format(first_trade_status, trade_status, currentphase, idnum)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def UpdateCurrentPhase(self, currentphase, idnum):
        query = "update instrument_master set currentphase = '{}' where id = '{}'".format(currentphase, idnum)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def UpdateCurrentPhasebySymbol(self, currentphase, trading_symbol):
        query = "update instrument_master set currentphase = '{}' where trading_symbol = '{}'".format(currentphase, trading_symbol)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def UpdateCurrentPhaseAll(self, currentphase):
        query = "update instrument_master set currentphase = '{}'".format(currentphase)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def GetMaketOrdersCount(self):
        query = "SELECT count(*) as len FROM marketorders where intent = 'Fresh' and status <> 'closed'".format()
        df = pd.read_sql(query, con=self.con)
        return df
    
    def GetOptionStrategyCurrentPhase(self):
        query = "SELECT * FROM five_minute_option_strategy;".format()
        df = pd.read_sql(query, con=self.con)
        return df
    
    def insertTradeLog(self, date_log, module, activity, important_data, priority, timestamp):
        query = "Insert into trade_logs(date_log, module, activity, important_data, priority, timestamp) Values('{}','{}','{}','{}','{}','{}')".format(date_log, module, activity, important_data, priority, timestamp)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def getOptionListByStrikePrice(self, option_type, strike_price):
        query = "SELECT name, instrument_token FROM st2_option_list where option_type = '{}' and strike_price = '{}'".format(option_type, strike_price)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def UpdateCurrentPhaseOptionStrategy(self, currentphase):
        query = "update five_minute_option_strategy set current_phase = '{}'".format(currentphase)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def UpdateLastSqroffOptionStrategy(self, last_sqroff):
        query = "update five_minute_option_strategy set last_sqroff = '{}'".format(last_sqroff)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def GetLastSquareOff(self):
        cursor = self.con.cursor()
        cursor.execute('Select last_sqroff from five_minute_option_strategy;')
        for row in cursor:
            return row
    
    def GetNiftyOneMinuteHistoricalData(self, start_date, end_date):
        query = "SELECT date, open, high,low,close, '0' as volume FROM nifty_historical_data_01min where Date(date) between '{}' and '{}' order by date".format(start_date, end_date)
        df = pd.read_sql(query, con=self.con)
        return df
    def InsertNiftyOneMinuteHistoricalData(self, date, open, high,low,close):
        query = "INSERT INTO nifty_historical_data_01min(date, open, high, low, close) VALUES('{}', '{}', '{}','{}','{}');".format(date, open, high,low,close)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    def insertmarketorders(self, zerodha_id, transaction_type, price_executed, status, intent, limitprice, order_type, userid, instrument, exchange, qty, remarks, nw):
        query = "INSERT INTO marketorders(zerodha_id, transaction_type, price_executed, status, intent, limitprice, order_type, userid, instrument, exchange, qty, timestamp, remarks) VALUES('{}', '{}', '{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}');".format(zerodha_id, transaction_type, price_executed, status, intent, limitprice, order_type, userid, instrument, exchange, qty, nw, remarks)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    #Devkant
    def getOptionList(self, option_type):
        query = "SELECT CONCAT('NFO:', name) as name, instrument_token FROM st2_option_list where option_type = '{}' order by strike_price".format(option_type)
        df = pd.read_sql(query, con=self.conDev)
        return df
    
    def GetOptions(self, option_name, user_id):
        query = "Select option_value  from options where option_name = '{}' and user_id = '{}'".format(option_name, user_id)
        cursor = self.conDev.cursor()
        cursor.execute(query)
        for row in cursor:
            return row[0]    
    
    def update_options(self, option_name, option_value, user_id):
        query = "Update options set option_value = '{}' where option_name = '{}' and user_id = '{}'".format(option_value, option_name, user_id)
        cur = self.conDev.cursor()
        cur.execute(query)
        self.conDev.commit()
    
    def GetCEPE(self, strike_price, user_id, option_type):
        query = "Select * from st2_option_list where strike_price = '{}' and option_type = '{}'".format(strike_price, option_type)
        df = pd.read_sql(query, con=self.conDev)
        return df
        
    def insertfinalposition(self, user_id, exchange_update_timestamp, status, tradingsymbol, product, quantity, transaction_type, average_price):
        query = "INSERT INTO optionstrades(user_id, exchange_update_timestamp, status, tradingsymbol, product, quantity, transaction_type, average_price) VALUES('{}', '{}','{}','{}','{}','{}','{}','{}');".format(user_id, exchange_update_timestamp, status, tradingsymbol, product, quantity, transaction_type, average_price)
        cur = self.conDev.cursor()
        cur.execute(query)
        self.conDev.commit()

    def insertm2m(self, timestamp, instrument, m2m):
        query = "INSERT INTO m2m(timestamp, instrument, m2m) VALUES('{}','{}','{}');".format(timestamp, instrument, m2m)
        cur = self.conDev.cursor()
        cur.execute(query)
        self.conDev.commit()
    
    def insert_fake_breeze_orders(self, trading_symbol, qty, exchange, trans_type, timestamp, product, order_type, price, stop_loss_trigger):
        query = "INSERT INTO fake_zeroda_orders(tradingsymbol, quantity, exchange, transaction_type, timestamp, product, order_type, price, stop_loss_trigger_price) VALUES('{}','{}','{}','{}','{}','{}','{}','{}','{}')".format(trading_symbol, qty, exchange, trans_type, timestamp, product, order_type, price, stop_loss_trigger)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def get_fake_breeze_orderid(self):
        query = "SELECT max(order_id) FROM fake_zeroda_orders"
        cursor = self.con.cursor()
        cursor.execute(query)
        for row in cursor:
            return row[0]    
    
    def update_SLtrigger_price_fake_breeze(self, stop_loss_trigger, order_id):
        query = "Update fake_zeroda_orders set stop_loss_trigger_price = '{}' where order_id = '{}'".format(stop_loss_trigger, order_id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def update_ohlc_stats(self, average, standardDeviation, speedChange, maxUpSwing, maxUpSwingDuration, maxDrawDown, maxDrawDownDuration, date):
        query = "UPDATE NIFTY_OHLC_Daily SET average = {}, standardDeviation = {},  speedChange = {}, maxUpSwing = {}, maxUpSwingDuration = {}, maxDrawDown = {}, maxDrawDownDuration = {} WHERE date = '{}'".format(average, standardDeviation, speedChange, maxUpSwing, maxUpSwingDuration, maxDrawDown, maxDrawDownDuration, date)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def insert_trade_fake_zeroda(self, order_id, exchange, tradingsymbol, average_price, quantity, transaction_type, timestamp):
        query = "INSERT INTO fake_zeroda_trades(order_id, exchange, tradingsymbol, average_price, quantity, transaction_type, timestamp)VALUES('{}','{}','{}','{}','{}','{}','{}')".format(order_id, exchange, tradingsymbol, average_price, quantity, transaction_type, timestamp)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def GetTradeByDate_fake_breeze(self, startdate, enddate):
        query = "Select * from fake_zeroda_trades where timestamp between '{}' and '{}'".format(startdate, enddate)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def GetOHLCData(self, sdate, edate):
        query = "Select date, open, high, low, close FROM Algo.NIFTY_OHLC_Daily where date between '{}' AND '{}' order by date;".format(sdate, edate)
        df = pd.read_sql(query, con=self.con)
        #df.set_index('date', inplace=True)
        return df
    def GetTradeByOrderID_fake_breeze(self, order_id):
        query = "SELECT average_price, timestamp as exchange_timestamp, tradingsymbol FROM fake_zeroda_trades where order_id = '{}'".format(order_id)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def update_order_status_fake_breeze(self, status, order_id):
        query = "Update fake_zeroda_orders set status = '{}' where id = '{}'".format(status, order_id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def GetOrdersByDate_fake_zeroda(self, startdate, enddate):
        query = "SELECT * FROM fake_zeroda_trades where timestamp between '{}' and '{}'".format(startdate, enddate)
        df = pd.read_sql(query, con=self.con)
        return df

    def InsertPosition_fake_zeroda(self, tradingsymbol, exchange, product, quantity, average_price, last_price, m2m):
        query = "INSERT INTO fake_zeroda_positions(tradingsymbol, exchange, product, quantity, average_price, last_price, m2m) VALUES('{}', '{}', '{}', '{}', '{}', '{}', '{}')".format(tradingsymbol, exchange, product, quantity, average_price, last_price, m2m)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()    

    def GetPositions_fake_breeze(self):
        query = "SELECT * FROM fake_zeroda_positions".format()
        df = pd.read_sql(query, con=self.con)
        return df
    
    def update_trailBuyOrder(self, trail_trigger_price, current_execution_price, trading_symbol):
        query = "Update trailingbuyorders set trail_trigger_price = '{}', current_execution_price = '{}', active = 1, trail = 0 where trading_symbol = '{}'".format(trail_trigger_price, current_execution_price, trading_symbol)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def update_trailSellOrder(self, trail_trigger_price, current_execution_price, trading_symbol):
        query = "Update trailingsellorders set trail_trigger_price = '{}', current_execution_price = '{}', active = 1, trail = 0 where trading_symbol = '{}'".format(trail_trigger_price, current_execution_price, trading_symbol)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def updateOHLCStraightness(self, Straightness, sdate):
        query = "update Algo.NIFTY_OHLC_Daily set straightness = '{}' where date = '{}';".format(Straightness, sdate)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def Get_NiftyFut_LTP_fake_breeze(self, cur_date, cur_time):
        query = "SELECT LTP FROM Tick where `Date` = '{}' and Time <= '{}' order by `Time` desc LIMIT 1;".format(cur_date, cur_time)
        df = pd.read_sql(query, con=self.conTick)
        return df
    
    def Get_NiftyFut_LTP_fake_breeze_V2(self, cur_date, cur_time):
        query = "SELECT last_price as LTP FROM Algo.mastertickdata where `TDate` = '{}' and ttime <= '{}' order by `Time` desc LIMIT 1;".format(cur_date, cur_time)
        df = pd.read_sql(query, con=self.conTick)
        return df
    
    def GetTickData_fake_breeze(self, ticker, cur_date, start_time, cur_time):
        query = "SELECT Date, Time, LTP FROM Tick where Date = '{}' and Time between '{}' and '{}';".format(cur_date, start_time, cur_time)
        #print(query)
        df = pd.read_sql(query, con=self.conTick)
        return df
    def GetRealTickData(self, ticker, cur_date, cur_time):
        query = "Select TDate As Date, TTime As Time, last_price as LTP from mastertickdata where TDate = '{}' and instrument_token = '{}' and TTime < '{}' order by ID desc;".format(cur_date, ticker, cur_time)
        #print(query)
        df = pd.read_sql(query, con=self.conTick2)
        self.conTick2.commit()
        return df
    def GetRealTickDataRange(self, ticker, cur_date, stime, etime):
        query = "Select TDate As Date, TTime As Time, last_price as LTP from mastertickdata where TDate = '{}' and instrument_token = '{}' and TTime between '{}' AND '{}' order by ID desc;".format(cur_date, ticker, stime, etime)
        #print(query)
        df = pd.read_sql(query, con=self.conTick2)
        self.conTick2.commit()
        return df
    def GetLastTickData_fake_zeroda(self, ticker, cur_date, start_time, cur_time):
        query = "SELECT Date, Time, LTP FROM Tick where Ticker = '{}' and Date = '{}' and Time between '{}' and '{}' LIMIT 1;".format(ticker, cur_date, start_time, cur_time)
        print(query)
        df = pd.read_sql(query, con=self.conTick)
        return df
    
    def GetClientDetailsbyName(self, name):
        query = "Select * from clients where name = '{}'".format(name)
        df = pd.read_sql(query, con=self.conDev)
        return df
    
    def InsertTrade_Fake_breeze(self, order_id, exchange, tradingsymbol, average_price, quantity, transaction_type, timestamp):
        query = "INSERT INTO fake_zeroda_trades(order_id, exchange, tradingsymbol, average_price, quantity, transaction_type, timestamp, trade_date) VALUES ('{}','{}','{}','{}', '{}', '{}', '{}', '{}');".format(order_id, exchange, tradingsymbol, average_price, quantity, transaction_type, timestamp, timestamp)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def getPositions_Fake_breeze(self, tradingsymbol):
        query = "SELECT * FROM fake_zeroda_positions where tradingsymbol = '{}'".format(tradingsymbol)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def updatePosition_fake_breeze(self, quantity, average_price, last_price, m2m, tradingsymbol):
        query = "Update fake_zeroda_positions set quantity = '{}', average_price = '{}', last_price = '{}', m2m = '{}' where tradingsymbol = '{}'".format(quantity, average_price, last_price, m2m, tradingsymbol)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def insertPosition_fake_breeze(self, tradingsymbol, exchange, product, quantity, average_price, last_price, m2m):
        query = "INSERT INTO fake_zeroda_positions(tradingsymbol, exchange, product, quantity, average_price, last_price, m2m) VALUES('{}', '{}', '{}', '{}', '{}', '{}', '{}');".format(tradingsymbol, exchange, product, quantity, average_price, last_price, m2m)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def updateCompleteOrder_fake_breeze(self, orderid, price):
        query = "update fake_zeroda_orders set status = 'COMPLETE', price = '{}' where order_id = '{}'".format(price, orderid)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def getOrderHistory_fake_breeze(self, orderid):
        query = "Select status, '' as status_message FROM fake_zeroda_orders where order_id = '{}'".format(orderid)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def getTickDataDates(self):
        query = "SELECT distinct Date FROM Tick order by date"
        df = pd.read_sql(query, con=self.conTick)
        return df
        
    #new functions 28 Oct 2021
    def insert_instruments_zerodha(self, instrument_token, tradingsymbol, name, last_price, expiry, strike, lot_size, instrument_type, segment, exchange):
        query = "INSERT INTO instruments_zerodha(instrument_token, tradingsymbol, name, last_price,expiry, strike, lot_size, instrument_type, segment, exchange) VALUES ('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}')".format(instrument_token, tradingsymbol, name, last_price, expiry, strike, lot_size, instrument_type, segment, exchange)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()    
        
    def getCallOptionByStrike(self, name, strike, expiry):
        query = "SELECT instrument_token, tradingsymbol, lot_size, margin FROM instruments_zerodha where Name = '{}' and  instrument_type = 'CE' and strike = '{}' and expiry = '{}'".format(name, strike, expiry)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def getPutOptionByStrike(self, name, strike, expiry):
        query = "SELECT instrument_token, tradingsymbol, lot_size, margin FROM instruments_zerodha where Name = '{}' and  instrument_type = 'PE' and strike = '{}' and expiry = '{}'".format(name, strike, expiry)
        df = pd.read_sql(query, con=self.con)
        return df
        
    def GetOrdersListPaper(self, sdate, edate, userid, status, intent):
         query = "Select order_id as zerodha_id, tradingsymbol as instrument,exchange, quantity as qty, transaction_type from fake_zeroda_orders where (timestamp between '{}' AND '{}') AND status = '{}' AND intent = '{}'".format(sdate, edate, status, intent)
         df = pd.read_sql(query, con=self.con)
         return df
     
    # def GetOrdersListCompletedPaper(self, sdate, edate, userid, status, intent, slstatus):
    #     query = "Select order_id as zerodha_id, tradingsymbol as instrument,exchange, quantity as qty, transaction_type, remarks, price as price_executed, price as limitprice from fake_zeroda_orders where (timestamp between '{}' AND '{}') AND status = '{}' AND intent = '{}' AND StopLossStatus = '{}'".format(sdate, edate, status, intent, slstatus)
    #     #print(query)
    #     df = pd.read_sql(query, con=self.con)
    #     return df
    
    def insert_DailyTrade_history(self, index_name, index_token, instrument, current_qty, expiry, stop_loss_points, repurchase_points, direction, userid, index_ltp):
        query = "INSERT INTO DailyTradeHistory(index_name, index_token, instrument, current_qty, expiry, stop_loss_points, repurchase_points, direction, userid, initial_qty, index_ltp) VALUES('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}');".format(index_name, index_token, instrument, current_qty, expiry, stop_loss_points, repurchase_points, direction, userid, current_qty, index_ltp)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def getActiveTradeDetails(self, instrument, userid):
        query = "SELECT * FROM DailyTradeHistory where status = 'open' and instrument = '{}' and userid = '{}'".format(instrument, userid)
        df = pd.read_sql(query, con=self.con)
        return df
        
    def updateDailyTradeStopLoss(self, tradeid, stop_loss, repurchase_target):
        query = "update DailyTradeHistory set index_stoploss = '{}', index_repurchase_target = '{}' where id = '{}'".format(stop_loss, repurchase_target, tradeid)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def updateTradeStatus(self, qty, status, id):
        query = "update DailyTradeHistory set current_qty = '{}', status = '{}' where id = '{}'".format(qty, status, id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def updateTradeCurrentValues(self, qty, index_stoploss, repurchase_price, id):
        query = "update DailyTradeHistory set current_qty = '{}', index_stoploss = '{}', index_repurchase_target = '{}' where id = '{}'".format(qty, index_stoploss, repurchase_price, id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def getFutureByExpiry(self, name, expiry):
        query = "SELECT instrument_token, tradingsymbol, lot_size, margin FROM instruments_zerodha where Name = '{}' and  instrument_type = 'FUT' and expiry = '{}'".format(name, expiry)
        #print(query)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def getCurrentFuture(self, index):
        query = "SELECT instrument_token, tradingsymbol, lot_size, margin FROM instruments_zerodha where Name = '{}' and  instrument_type = 'FUT' and Expiry > CURDATE() order by expiry Limit 1;".format(index)
        #print(query)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def updateTradeM2M(self, m2m, instrument):
        query = "update DailyTradeHistory set m2m = '{}' where instrument = '{}' and status <> 'close'".format(m2m, instrument)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def InsertLTP(self, instrument_token, last_price):
        CurDate = datetime.datetime.now()
        CurTime = CurDate.time()
        query = "INSERT into mastertickdata(TDate, TTime, last_price, instrument_token) Values('{}', '{}','{}','{}')".format(CurDate, CurTime, last_price, instrument_token)
        cur = self.conTick.cursor()
        cur.execute(query)
        self.conTick.commit()
        
    def InsertFirstTrade(self, long_trigger, short_trigger, index_name, instrument_type):
        trade_date = datetime.datetime.now()
        query = "INSERT INTO FirstTrade(trade_date, long_trigger, short_trigger, index_name, instrument_type) VALUES('{}', '{}', '{}', '{}', '{}')".format(trade_date, long_trigger, short_trigger, index_name, instrument_type)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()

    def UpdateLTP(self, instrument_token, last_price):
        CurDate = datetime.datetime.now()
        CurTime = CurDate.time()
        query = "Update LTP set last_price = '{}' where instrument_token = '{}'".format(last_price, instrument_token)
        cur = self.conTick.cursor()
        cur.execute(query)
        self.conTick.commit()
        
    def getFirstTrade(self):
        query = "Select * from FirstTrade where active = 1 and initiated = 0"
        df = pd.read_sql(query, con=self.con)
        return df
    
    def insertTrailingBuyOrder(self, trading_symbol, instrument_token, quantity, userid, exchange, trail_trigger_price, current_execution_price, trail, trade, index_name):
        query = "INSERT INTO trailingbuyorders(trading_symbol, instrument_token, quantity, userid, exchange, trail_trigger_price, current_execution_price, trail, trade, index_name) VALUES('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}')".format(trading_symbol, instrument_token, quantity, userid, exchange, trail_trigger_price, current_execution_price, trail, trade, index_name)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def insertTrailingSellOrder(self, trading_symbol, instrument_token, quantity, userid, exchange, trail_trigger_price, current_execution_price, trail, trade, index_name):
        query = "INSERT INTO trailingsellorders(trading_symbol, instrument_token, quantity, userid, exchange, trail_trigger_price, current_execution_price, trail, trade, index_name) VALUES('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}')".format(trading_symbol, instrument_token, quantity, userid, exchange, trail_trigger_price, current_execution_price, trail, trade, index_name)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def UpdateFirstTradeInitiated(self, id):
        query = "update FirstTrade set initiated = 1 where id = '{}'".format(id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def deActivateFirstTrade(self, id):
        query = "update FirstTrade set active = 0 where id = '{}'".format(id)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def GetMarketViewByIndex(self, cur_date, index):
        query = "SELECT day_open, day_low, day_high, last_ltp, current_view FROM MarketView where current_date = '{}' and Index_name = '{}'".format(cur_date, index)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def insertMarketView(self, current_date, index_name, day_open, day_low, day_high, last_ltp, current_view):
        query = "INSERT INTO MarketView(current_date, index_name, day_open, day_low, day_high, last_ltp, current_view) VALUES('{}', '{}', '{}', '{}', '{}', '{}', '')"
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def UpdateMonitorStocks(self):
        query = "Update MonitorStocks SET enabled = 1"
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def getMonitorStocks(self):
        query = "SELECT CONCAT('NSE:' ,instrument_token) as instrument_token, price, targetprice FROM kimalgo_test.MonitorStocks where enabled = 1"
        df = pd.read_sql(query, con=self.con)
        return df
    
    def getDistinctDateTick(self):
        query = "Select distinct date from Tick where Date > '2021-07-17' order by Date"
        df = pd.read_sql(query, con=self.con)
        return df
    
    def GetPreviousDate(self, date):
        query = "SELECT date FROM NIFTY_OHLC_Daily where date < '{}' order by date desc Limit 1;".format(date)
        cursor = self.con.cursor()
        cursor.execute(query)
        for row in cursor:
            return row[0]   
        
    def InsertMarketSummaryPerMinute(self, Date, low, high, open, close, MaxHigh, MaxDrawdown, HighMsg, LowMsg, thisDrawdown, MinLow, MaxUpSwing, stdev, allStdev, OneMinuteDrawDown, SpeedOfChange, PosColor, NegColor, OneMinuteUpswing, DrawdownPerc, UpswingPerc):
        query = "INSERT INTO MarketSummaryPerMinute(Date, low, high, open, close, MaxHigh, MaxDrawdown, HighMsg, LowMsg, thisDrawdown, MinLow, MaxUpSwing, stdev, allStdev, OneMinuteDrawDown, SpeedOfChange, PosColor, NegColor, OneMinuteUpswing, DrawdownPerc, UpswingPerc, Datetime) VALUES('{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}','{}')".format(Date, low, high, open, close, MaxHigh, MaxDrawdown, HighMsg, LowMsg, thisDrawdown, MinLow, MaxUpSwing, stdev, allStdev, OneMinuteDrawDown, SpeedOfChange, PosColor, NegColor, OneMinuteUpswing, DrawdownPerc, UpswingPerc, Date)
        cur = self.conTick.cursor()
        #print(query)
        cur.execute(query)
        self.conTick.commit()
        
    def DelMarketSummaryPerMinute(self, date):
        query = "Delete from MarketSummaryPerMinute where Date = '{}'".format(date)
        cur = self.conTick.cursor()
        #print(query)
        cur.execute(query)
        self.conTick.commit()
    
    def getHigherRangeTime(self, date, time, price):
        query = "Select TTime, last_price from mastertickdata where TDate = '{}' and TTime < '{}' and last_price > '{}' order by TTime desc Limit 1;".format(date, time, price)
        df = pd.read_sql(query, con=self.conTick)
        return df
    
    def getLowerRangeTime(self, date, time, price):
        query = "Select TTime, last_price from mastertickdata where TDate = '{}' and TTime < '{}' and last_price < '{}' order by TTime desc Limit 1;".format(date, time, price)
        df = pd.read_sql(query, con=self.conTick)
        return df
    
    def getDatabaseLTP(self, date, time):
        query = "Select round(last_price) as close from mastertickdata where TDate = '{}' and TTime <= '{}' order by TTime desc Limit 1;".format(date, time)
        #print(query)
        mycursor = self.conTick.cursor()
        mycursor.execute(query)
        myresult = mycursor.fetchone()
        return myresult[0]
    
    def getDatabaseLTPDF(self, date, time):
        query = "Select round(last_price) as close from mastertickdata where TDate = '{}' and TTime <= '{}' order by TTime desc Limit 1;".format(date, time)
        df = pd.read_sql(query, con=self.conTick)
        return df
    
    def getNIFTY2018OHLC(self, date, stime, etime):
        query = "Select Time, open, low, high, close from NIFTY2018 where Date = '{}' AND Time between '{}' AND '{}' order by time;".format(date, stime, etime)
        df = pd.read_sql(query, con=self.conTick)
        return df

    def getMasterTickData(self, date, stime, etime):
        query = "Select TTime as time, last_price as ltp from mastertickdata where TDate = '{}' AND TTime between '{}' AND '{}' order by ttime;".format(date, stime, etime)
        df = pd.read_sql(query, con=self.conTick)
        return df
    
    def getMasterTickDataDay(self, date):
        query = "Select TTime as time, last_price as ltp from mastertickdata where TDate = '{}' order by ttime;".format(date)
        df = pd.read_sql(query, con=self.conTick)
        return df

    def getRawTickData(self, sdate, edate):
        query = "SELECT Date, Time, LTP, LTQ FROM Algo.Tick where Date between '{}' AND '{}'".format(sdate, edate)
        df = pd.read_sql(query, con=self.conTick)
        return df   
    
    def getRawMasterTickData(self, sdate, edate):
        query = "Select TDate as Date, TTime as Time, last_price as LTP from mastertickdata where TDate between '{}' AND '{}'".format(sdate, edate)
        df = pd.read_sql(query, con=self.conTick)
        return df
    
    def getEventProbabilities(self, event, trend):
        query = "Select Category, Probability, LowValue, HighValue from Algo.MarketEvents E inner join Algo.MarketEventCategories C on E.ID = C.EventID where E.Event = '{}' AND Trend = '{}' order by Probability desc;".format(event, trend)
        df = pd.read_sql(query, con=self.conTick)
        return df  
    
    def GetPreviousDayClose(self, date):
        query = "SELECT close FROM Algo.NIFTY_OHLC_Daily where date < '{}' order by date desc Limit 1;".format(date)
        cursor = self.con.cursor()
        cursor.execute(query)
        for row in cursor:
            return row[0]   
        
    def GetLastOHLCDate(self):
        query = "SELECT max(date) FROM Algo.NIFTY_OHLC_Daily;"
        cursor = self.con.cursor()
        cursor.execute(query)
        for row in cursor:
            return row[0] 
        
    def InsertOHLCData(self, date, open, high, low, close):
        q1 = "INSERT into Algo.NIFTY_OHLC_Daily(date, open, high, low, close) Values('{}','{}','{}','{}','{}') "
        q2 = " ON DUPLICATE KEY UPDATE open = {}, high = {}, low = {}, close = {}"
        q1 = q1.format(date, open, high, low, close)
        q2 = q2.format(open, high, low, close)
        query = q1 + q2
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def updateOHLCAnalysis(self, openGap, highlowgap, closeOpenGap, dayMovement, drawdownLastDay, date):
        query = "update Algo.NIFTY_OHLC_Daily set openGap = '{}', highLowGap = '{}', closeOpenGap = '{}', dayMovement = '{}', drawdownLastDay = '{}' where date = '{}'".format(openGap, highlowgap, closeOpenGap, dayMovement, drawdownLastDay, date)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def GetPerMinData(self, sdate=None):
        if sdate is None:
            CurrentDateTime = datetime.datetime.now()
            sdate = CurrentDateTime.date()
        query = "SELECT date, open, high, low, close FROM Algo.nifty_historical_data_01min where DATE(date) = '{}' order by date;".format(sdate)
        #print(query)
        df = pd.read_sql(query, con=self.conTick)
        return df  
    
    def updatePerMinuteStats(self, date, Open, high, low, close,SpeedAvg, movement, straightness):
        #print('In updatePerMinuteStats')
        q1 = "INSERT INTO `Algo`.`nifty_historical_data_01min`(date, open, high, low, close,SpeedAvg, movement, straightness) VALUES ('{}', {}, {}, {}, {}, {}, {}, {} )"  
        q2 = " ON DUPLICATE KEY UPDATE open = {}, high = {}, low = {}, close = {},SpeedAvg = {}, movement = {}, straightness = {};"
        q1 = q1.format(date, Open, high, low, close,SpeedAvg, movement, straightness)
        q2 = q2.format(Open, high, low, close,SpeedAvg, movement, straightness)
        q1 = q1 + q2
        cur = self.con.cursor()
        cur.execute(q1)
        self.con.commit()
        
    def get_masterTickDataTillTime(self, date, time):
        query = "SELECT TTime as time, last_price as close FROM Algo.mastertickdata where TDate = '{}' AND TTime < '{}' order by ID;".format(date, time)
        df = pd.read_sql(query, con=self.con)
        return df
    
    def getStrategyDetails(self, strategy):
        query = 'SELECT * FROM Algo.NIFTY_DayShort_strategy;'
        if strategy == 'NIFTY_Night_strategy':
            query = 'SELECT * FROM Algo.NIFTY_Night_strategy;'
        df = pd.read_sql(query, con=self.con)
        return df
    def ResetStrategy(self, strategy, CurrentDate):
        query = "Update Algo.NIFTY_Night_strategy set BuyStatus = 0, SellStatus = 0, CurrentDate = '{}'".format(CurrentDate)
        if strategy == 'NIFTY_DayShort_strategy':
            query = "Update Algo.NIFTY_DayShort_strategy set BuyStatus = 0, SellStatus = 0, CurrentDate = '{}', CurrentStatus = 'None'".format(CurrentDate)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def UpdateLongCover(self, CurrentDate):
        print('Update Long Cover Overnight')
        query = "Update Algo.NIFTY_Night_strategy set BuyStatus = 0, SellStatus = 1, CurrentStatus = 'None', CurrentDate = '{}';".format(CurrentDate)
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()   
        
    def UpdateLongInitiate(self):
        print('Update Long Initiate')
        query = "Update Algo.NIFTY_Night_strategy set BuyStatus = 1, CurrentStatus = 'Long';"
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()           
        
    def UpdateDayShortSELL(self):
        print('UpdateDayShortSELL SellStatus = 1')
        query = "Update Algo.NIFTY_DayShort_strategy set SellStatus = 1, CurrentStatus = 'Short';"
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def UpdateDayShortCover(self):
        print('UpdateDayShortCover BuyStatus = 1')
        query = "Update Algo.NIFTY_DayShort_strategy set BuyStatus = 1, CurrentStatus = 'None';"
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
        
    def UpdateNightStrategySELL(self):
        query = "Update Algo.NIFTY_Night_strategy set SellStatus = 1, CurrentStatus = 'None';"
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
    def UpdateNightStrategyBuy(self):
        query = "Update Algo.NIFTY_Night_strategy set BuyStatus = 1, CurrentStatus = 'Long';"
        cur = self.con.cursor()
        cur.execute(query)
        self.con.commit()
    
            