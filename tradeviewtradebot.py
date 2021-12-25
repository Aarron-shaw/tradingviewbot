#!/usr/bin/python3

from datetime import datetime
import email
import imaplib
import time
import logging
import math
import json
from bs4 import BeautifulSoup
import requests
import threading
import curses
import urllib.parse

from binance.client import Client

#First version of my trading view trading bot. 



#Use this for your tradingview alert 
# Currency {{ticker}} Action {{strategy.order.action}} Price {{strategy.order.price}}

user_key =  "binanceapikey"
secret_key = "binanceapisecret"


client = Client(user_key, secret_key)

user = "yourgmail"
pwd = "gmailapppassword"

trade_list = []



def gen_perc(num,lev):
    return (num / 100) / lev 

def telegram_msg(text):
    #you need to edit this 
    # telegram_con = "https://api.telegram.org/telegrambotapikey/sendMessage?chat_id=-groupid&parse_mode=HTML&text=" + urllib.parse.quote_plus(text)
    # #print(telegram_con)
    # result = requests.get(telegram_con)
    # #print(result)
    return False

def perc_to_set(num,lev):
    return num / (100 / lev)


sl = 30 #Stop loss % you want 
trail_stop = 29 #Trailing stop loss % you want 
roe_check = 1 # This will trigger the trailing stop loss
tp = 100 # take profit %
lev = 20 # Leverage you want to use
percs = gen_perc(sl,lev)
trail_percs = gen_perc(trail_stop,lev)
perct = gen_perc(tp,lev)
total_profit = 0
total_roe = 0
allowed_trades = 10 # account balance / allowed_trades 
log_details = []

f = open("trade.log", "a")
f.write("New logfile\n")
f.close()

def write_to_log(message,fun):
    global log_details
    my_time = datetime.now()
    my_time = my_time.strftime("%c")
    result = "[{} - {} - {}]".format(my_time,fun,message)
    log_details.append(result)
    f = open("trade.log", "a")
    f.write(result + "\n")
    f.close()

def get_profit(price,current,qty, side ):
    price = float(price)
    current = float(current)
    qty = float(qty)
    if side == 'BUY':
        profit = (current - price) * qty
    if side == 'SELL':
        profit = (price - current) * qty
    
    return profit
 
def get_imr(price, qty):
    price = float(price)
    
    qty = float(qty)
    imr = price * qty * (1/lev)
    return (imr) 
    
def get_roe(profit,imr):
    price = float(price)
    
    roe = profit / imr
    
   
    return roe

def roe_quick(price,current,qty, side):
    price = float(price)
    current = float(current)
    qty = float(qty)
    if side == 'BUY':
        profit = (current - price) * qty
    if side == 'SELL':
        profit = (price - current) * qty
    imr = price * qty * (1/lev)
    
    
    roe = (profit / imr ) * 100
    return roe
    
def test_gen_sl_tp(price,action):
    price = float(price)
    if action == "BUY":
        stop_loss = price - (price * percs)
        take_profit = price + (price * perct)
        stop_side = "SELL"
        take_side = "BUY"
    if action == "SELL":
        stop_loss = price + (price * percs)
        take_profit = price - (price * perct)
        stop_side = "SELL"
        take_side = "BUY"
    #print(stop_loss,take_profit)
    return stop_loss, take_profit
    
def test_gen_trail(price,action):
    price = float(price)
    if action == "BUY":
        stop_loss = price - (price * trail_percs)
        take_profit = price + (price * perct)
        stop_side = "SELL"
        take_side = "BUY"
    if action == "SELL":
        stop_loss = price + (price * trail_percs)
        take_profit = price - (price * perct)
        stop_side = "SELL"
        take_side = "BUY"
    #print(stop_loss,take_profit)
    return stop_loss, take_profit

def check_filled(my_list):
    #print("Checking for finished trades...")
    global trade_list
    global total_profit
    global total_roe
    global log_details
    for i in my_list:
        
        clear = False
        i['SL'] = order_info(i['SL'])
        i['TP'] = order_info(i['TP'])
        start_price = float(i['Parent']['avgPrice'])
        side = i['Parent']['side']
        qty = i['Parent']['origQty']
        take = float(i['TP']['stopPrice'])
        stop = float(i['SL']['stopPrice'])
        #print(i['SL'])
        #print(i['TP'])
        if i['SL']['status'] == 'FILLED':
            res = client.futures_cancel_order(symbol=i['TP']['symbol'],orderId=i['TP']['orderId'])
            #print(order_info(i['SL']))
            profit = get_profit(start_price,i['SL']['stopPrice'],qty, side )
            total_profit += profit
            roe = roe_quick(start_price,i['SL']['stopPrice'], qty,side)
            total_roe += roe
            write_to_log("SL hit for {}, profit {}".format(i['TP']['symbol'], profit),'check_filled()')
            telegram_msg("""
            
SL hit for {}
Entry: {}
Exit: {}
ROE: {}%
Total ROE: {}%
Profit: ${}
Total Profit: ${}
            """.format(i['TP']['symbol'],start_price,stop,round(roe,2),round(total_roe,2),round(profit,2),round(total_profit,2)))
            clear = True
            
            
            
        if i['TP']['status'] == 'FILLED':
            res = client.futures_cancel_order(symbol=i['SL']['symbol'],orderId=i['SL']['orderId'])
            #print(order_info(i['TP']))
            profit = get_profit(start_price,i['TP']['stopPrice'],qty, side )
            total_profit += profit
            roe = roe_quick(start_price,i['TP']['stopPrice'], qty,side)
            total_roe += roe
            write_to_log("TP hit for {}, profit ${}".format(i['TP']['symbol'],profit),'check_filled()')
            telegram_msg("""
            
TP hit for {}
Entry: {}
Exit: {}
ROE: {}%
Total ROE: {}%
Profit: ${}
Total Profit: ${}

""".format(i['TP']['symbol'],start_price,take,round(roe,2),round(total_roe,2),round(profit,2),round(total_profit,2)))
            clear = True
        
        if clear:
            trade_list.remove(i)
    return trade_list

def clear_trades(my_list):
    #print("Checking SL/TP")
    global total_profit
    global total_roe
    global trade_list
    global log_details
    trail_stop_perc = gen_perc(trail_stop,lev)
    for i in my_list:
        try:
            i['SL'] = order_info(i['SL'])
            i['TP'] = order_info(i['TP'])
        except:
            continue
        
        btc_current = client.futures_symbol_ticker(symbol=i['Parent']['symbol'])
        btc_current_price = float(btc_current['price'])
        start_price = float(i['Parent']['avgPrice'])
        #print(i['Parent'])
        side = i['Parent']['side']
        qty = i['Parent']['origQty']
        take = float(i['TP']['stopPrice'])
        stop = float(i['SL']['stopPrice'])
        take_roe = roe_quick(start_price,btc_current_price, qty,side)
        stop_roe = roe_quick(start_price,stop,qty,side)
        #print("""Current ROE {}\nCurrent Price: {}""".format(take_roe,btc_current_price))
        
        if side == 'BUY':
            
            if take_roe >= roe_check:
                #print("Trying to generate new SL/TP")
                
                new_stop, new_take = test_gen_sl_tp(btc_current_price,side)
                #print(new_take,take)
                if new_stop > stop:
        
            
                    try:
                        i['SL'], i['TP'] = update_sltp(i['Parent'],i['SL'], i['TP'],trail_stop_perc)
                        #print("Sucessfully updated SL/TP for {}".format(i['Parent']['symbol']))
                        #write_to_log("Sucessfully updated SL/TP for {}".format(i['Parent']['symbol']),'clear_trades()')
                        # print("""
# ROE from SL {}%
# Current ROE {}%""".format(round(roe_quick(start_price,float(i['SL']['stopPrice']),qty,side),2),take_roe))
                    except Exception as e:
                        print("Error in update_sltp() ", (e))
                        write_to_log("Error in update_sltp() {}".format(e),'clear_trades()')
                        for q in i:
                            print(q)
                        # print("""BUY:
                                # start_price: {}
                                # Current price: {}
                                # Old SL: {}
                                # New SL: {}
                                # Old TP: {}
                                # New TP: {}
                                # """.format(start_price,btc_current_price,stop,new_stop,take,new_take))
                        pass
        if side == 'SELL':
            if take_roe >= roe_check:
                #print("Trying to generate new SL/TP")
                
                new_stop, new_take = test_gen_sl_tp(btc_current_price,side)
                #print(new_take,take)
                if new_stop < stop:
        
            
                    try:
                        i['SL'], i['TP'] = update_sltp(i['Parent'],i['SL'], i['TP'],trail_stop_perc)
                        
                        #print("Sucessfully updated SL/TP for {}".format(i['Parent']['symbol']))
                        #print("ROE from SL {}".format(roe_quick(start_price,float(i['SL']['stopPrice']),qty,side)))
                        #write_to_log("Sucessfully updated SL/TP for {}".format(i['Parent']['symbol']),'clear_trades')
                        i['SL'] = order_info(i['SL'])
                        i['TP'] = order_info(i['TP'])
                    except Exception as e:
                        print("Error in update_sltp() ", (e))
                        write_to_log("Error in update_sltp() {}".format(e),'clear_trades()')
                        for q in i:
                            print(q)
                        # print("""SELL
                                # start_price: {}
                                # Current price: {}
                                # Old SL: {}
                                # New SL: {}
                                # Old TP: {}
                                # New TP: {}
                                # """.format(start_price,btc_current_price,stop,new_stop,take,new_take))
                        pass
            
                            
            #get_diff_price(price,current,side,diff_check=5,lev=20):
            
        
            
            
    return trade_list


def order_info(i,debug=0):
    global log_details
    
    
    try:
        cur = i['symbol']
        tmp_order = client.futures_get_order(orderId=i['orderId'],symbol=cur)
        # if debug == 1:
            # print(tmp_order)
        ts_c = datetime.fromtimestamp((tmp_order['time']/1000))
        ts_l = datetime.fromtimestamp((tmp_order['updateTime']/1000))
        # if debug == 1:
            # print("""
        # ID:         {}
        # Coin:       {}
        # Status:     {}
        # Price:      {}
        # AvgPrice:   {}
        # Side:       {}
        # Created:    {}
        # Last:       {}
        # QTY:        {}
        # """.format(tmp_order['orderId'],tmp_order['symbol'],tmp_order['status'],tmp_order['price'],tmp_order['avgPrice'],tmp_order['side'],ts_c.strftime('%Y-%m-%d %H:%M:%S'),ts_l.strftime('%Y-%m-%d %H:%M:%S'),tmp_order['executedQty']))
        return tmp_order
    except Exception as e:
            print("Error in order_info() ", (e))
            write_to_log("Error in order_info() {}".format(e),'order_info')
            #print(i)
            return i
    

def make_stoptake(order):
    global log_details
    
    if order['status'] == 'NEW':
        order=order_info(order)
    
    price = float(order['avgPrice'])
    #print(price)
    
    cur = order['symbol']
    action = order['side']
    min = order['executedQty']
    write_to_log("Trying to make SL/TP for {} @ {} SIDE={}".format(cur,price,action),'make_stoptake')
    if action == "BUY":
        stop_loss = price - (price * percs)
        take_profit = price + (price * perct)
        stop_side = "SELL"
        take_side = "BUY"
    if action == "SELL":
        stop_loss = price + (price * percs)
        take_profit = price - (price * perct)
        stop_side = "BUY"
        take_side = "BUY"
    stop_loss = get_price_precision(order['symbol'],stop_loss)
    take_profit = get_price_precision(order['symbol'],take_profit)
    try:
        #res = client.futures_cancel_order(symbol=sl['symbol'],orderId=sl['orderId'])
        stop_one = client.futures_create_order(
        symbol=cur,
        
        type='STOP_MARKET',
        stopPrice=stop_loss,
        
        side=stop_side,
        quantity=min,
        reduceOnly=True
        )
        
    except Exception as e:
        print("Error in make_stoptake() ", (e))
        write_to_log("Error in make_stoptake() {} ".format(e),'make_stoptake()')
        # print("""
    
# current_price: {},
# symbol={},
# timeInForce='GTC',
# price={},
# type='STOP',
# stopPrice={},

# side={},
# quantity={}
# """.format(price,cur,stop_loss,stop_loss,stop_side,min
        # ))
        return False
    try:
        #res = client.futures_cancel_order(symbol=tp['symbol'],orderId=tp['orderId'])
        stop_two = client.futures_create_order(
        symbol=cur,
        
        type='TAKE_PROFIT_MARKET',
        stopPrice=take_profit,
        
        side=stop_side,
        quantity=min,
        reduceOnly=True
        )
        
    except Exception as e:
        print("Error in make_stoptake() ", (e))
        write_to_log("Error in make_stoptake() {} ".format(e),'make_stoptake()')
        
        return False

    return order, stop_one, stop_two

def check_decimals(symbol):
    info = client.get_symbol_info(symbol)
    val = info['filters'][2]['stepSize']
    decimal = 0
    is_dec = False
    for c in val:
        if is_dec is True:
            decimal += 1
        if c == '1':
            break
        if c == '.':
            is_dec = True
    return decimal

def get_price_precision(symbol,price):
    
    info = client.futures_exchange_info()
    for item in info['symbols']:
        if(item['symbol'] == symbol):
            #print(item)
            #print("Price Pre ",item['pricePrecision'])

            pricePrecision = item['pricePrecision']
            quantityS = price
            quantityB = "{:0.0{}f}".format(quantityS, pricePrecision)
            #print(item['symbol'],quantityS, quantityB)
            return quantityB


def get_step_size(symbol):
    info = client.futures_exchange_info()
    for item in info['symbols']:
        if(item['symbol'] == symbol):
            for f in item['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    return step_size
                    
def get_precise_quantity(symbol,quantity):
    info = client.futures_exchange_info()
    for item in info['symbols']:
        if(item['symbol'] == symbol):
            for f in item['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    break
    precision = int(round(-math.log(step_size, 10), 0))
    quantity = float(round(quantity, precision))
    return quantity


def round_down( client, quantity, symbol):
        info = client.get_symbol_info(symbol)
        step_size = [float(_['stepSize']) for _ in info['filters'] if _['filterType'] == 'LOT_SIZE'][0]
        step_size = '%.8f' % step_size
        step_size = step_size.rstrip('0')
        decimals = len(step_size.split('.')[1])
        return math.floor(quantity * 10 ** decimals) / 10 ** decimals

def get_futures_usdt():
        futures_usd = 0.0
        for asset in client.futures_account_balance():
            name = asset["asset"]
            balance = float(asset["balance"])
            if name == "USDT":
                futures_usd += balance
        return float(futures_usd)

def get_futures_withdrawals():
        futures_usd = 0.0
        for asset in client.futures_account_balance():
            name = asset["asset"]
            balance = float(asset["withdrawAvailable"])
            if name == "USDT":
                futures_usd += balance
        return float(futures_usd)
        
def check_sub(subject):
    for i in subject.split():
        if get_coin(i):
            currency = get_coin(i)
        try:
            if float(i) > 0:
                price = i
        except:
            pass
        if i == "buy":
            action = "BUY"
        if i == "sell":
            action = "SELL"
    #print("C:{} A:{} P:{}".format(currency,action,price))
    return currency, action,price

def get_min_trade(cur,price,total_trades):
    balance = get_futures_withdrawals()
    balance = balance / total_trades
    #print(balance)
           
    price = float(price)
    
    min = round_down(client,( balance / (price / lev)), cur)
    
    quantity = get_precise_quantity(symbol = cur,quantity = min)
    min = quantity
    #print(min)
    return min
 
def trade(cur,action,price):
    global trade_list
    global total_profit
    global total_roe
    
    price = float(price)
    orders = client.futures_get_all_orders(symbol=cur, limit=1)
    
    #check for open orders and cancel them. 
    # open = client.futures_get_open_orders(symbol=cur)
    # for i in open:
        # #print("Cancel Order: {} ID: {}".format(cur,i['orderId']))
        # client.futures_cancel_order(symbol=cur,orderId=i['orderId'])
        #THIS MAYBE CAUSING ERRORS ^^ logic needs fixing 
    for x in trade_list:
        if x['Parent']['symbol'] == cur:
            client_info = client.futures_position_information()
            for p in client_info:
                if p['symbol'] == cur:
                   amnt = p['positionAmt']
                   if amnt < 0:
                    amnt = amnt * -1
            if x['Parent']['side'] == 'BUY':
                can = 'SELL'
            if x['Parent']['side'] == 'SELL':
                can = 'BUY'
            client.futures_create_order(
                symbol=cur,
    
                type='MARKET',
    
    
                side=can,
                quantity=amnt,
                reduceOnly=True
            )
            open = client.futures_get_open_orders(symbol=cur)
            for i in open:
                #print("Cancel Order: {} ID: {}".format(cur,i['orderId']))
                client.futures_cancel_order(symbol=cur,orderId=i['orderId'])
            write_to_log("Sucessfully changed {} trade from {} to {}".format(cur,x['Parent']['side'],can),'trade()')
            start_price = x['Parent']['avgPrice']
            current_price = price
            quantity = x['Parent']['executedQty']
            old_side = x['Parent']['side'] 
            profit = get_profit(start_price,current_price,quantity, side )
            total_profit += profit
            roe = roe_quick(start_price,i['TP']['stopPrice'], quantity,side)
            total_roe += roe
                 
            trade_list.remove(x)
    
    min = get_min_trade(cur,price,allowed_trades)
    #print("{} / {} = {}".format(price,balance, ( balance*20 / price)))
    #print("Min size: {}".format(min))
    client.futures_change_leverage(symbol=cur, leverage=lev)
    
    if action == "BUY":
        stop_loss = price - (price * percs)
        take_profit = price + (price * perct)
        stop_side = "SELL"
        take_side = "BUY"
    if action == "SELL":
        stop_loss = price + (price * percs)
        take_profit = price - (price * perct)
        stop_side = "BUY"
        take_side = "BUY"
    write_to_log("Order, Sym={}, price={}, side={}, qty={}".format(cur,price,action,min),'trade()')
    res = client.futures_create_order(
    symbol=cur,
    
    type='MARKET',
    
    
    side=action,
    quantity=min
    )
    par, stop,take = make_stoptake(res)
    try:
        res = order_info(res)
    except Exception as oops:
        print("Failed to make order: ", oops)
        write_to_log("Failed to make order: {}".format(oops),'trade()')
        res = par
        
    telegram_msg("""
    
New Trade: {}
Coin:   {}
Side:   {}
Price:  {}
QTY:    {}
SL:     {}
TP:     {}
    """.format(res['orderId'],cur,res['side'],price,res['executedQty'],stop['stopPrice'],take['stopPrice']))
    
    
    try:
        order_info(res)
        trade_dict = { 'Parent' : par, 'SL' : stop, 'TP' : take } 
        trade_list.append(trade_dict)
        #log_details.append("Trying to create order for {} @ {} SIDE={} qty={}".format(cur,price,action))
    except Exception as oops:
        print("Failed to make order: ", oops)
        write_to_log("Failed to make order: {}".format(oops),'trade()')
    
    

def get_coin(coin):
    if "USDT" in coin:
        
        result = coin.replace("USDT","")
        result = coin.replace("PERP","")
        return result
    return False


def readmail():
    #print("Checking mail...")
    #    time.sleep(1.5)
    m = imaplib.IMAP4_SSL("imap.gmail.com")
    m.login(user, pwd)
    m.select('"[Gmail]/All Mail"')
    resp, items = m.search(None,
                           "NOT SEEN FROM tradingview")
    items = items[0].split()
    #print(items)
    for emailid in items:
        
        resp, data = m.fetch(emailid,
                             "(RFC822)")
        
        
            
        email_body = data[0][1]
        #print(type(data))
        #print(email_body)
        try:
            mail = email.message_from_bytes(email_body)
            
        except Exception as oops:
            print("Error in read_mail() ", (oops))
            write_to_log("Error in read_mail() 1 {} ".format(oops),'read_mail()')
            # print(type(data))
            # print(data[0])
            # print(data[0][0])
            mail = email.message_from_bytes(data[1][1])
            #print(mail['Subject'])
            
        #print(mail['Subject'])
        
        ts = time.time()
        st = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        cur, act, pri = check_sub(mail['Subject'])
        try:
            
            if act == "BUY":
                #log_details.append("New {} order for {} @".format(act,cur,pri))
                m.store(emailid, '+FLAGS', '\\Deleted')
                
                #logging.info(st + ' Buy' + ' Triggered on ' + cur)
                trade(cur,act,pri)
            if act == "SELL":
                #log_details.append("New {} order for {} @".format(act,cur,pri))
                m.store(emailid, '+FLAGS', '\\Deleted')
                
                #logging.info(st + ' Sell' + ' Triggered on ' + cur)
                trade(cur,act,pri)
            m.expunge()
        except Exception as oh:
            print("Error in read_mail() 2 ", (oh))
            write_to_log("Error in read_mail() 2 {} ".format(oh),'read_mail()')
            
    #print("Finished reading mail...")
            
def get_perc_price(price,current,side):
    price = float(price)
    current = float(current)
    if side =='BUY':
        diff = round(((current - price)/price) * 100 * lev,2)
        diff = diff / 2
    if side == 'SELL':
        diff = round(((price - current)/price) * 100 * lev,2) 
        
    return diff
            
def get_diff_price(price,current,side,diff_check = 5.0):
    
    if side =='BUY':
        diff = round(((current - price)/price) * 100 * lev,2)
        diff = diff / 2
    if side == 'SELL':
        diff = round(((price - current)/price) * 100 * lev,2) 
        
    #print("BTC start {} BTC current {} diff% {}".format(price,current,diff))
    
    diff = float(diff)
    if diff >= diff_check:
        #print("Needs updating!")
        return True
    return False            

def gen_new_sltp(order,stop_perc):
    percs_tmp = stop_perc 
    action = order['side']
    price = client.futures_symbol_ticker(symbol=order['symbol'])
    price = float(price['price'])
    tp_price = float(order['avgPrice'])
    
    if action == "BUY":
        stop_loss = price - (price * percs_tmp)
        take_profit = tp_price + (tp_price * perct)
        stop_side = "SELL"
        take_side = "BUY"
    if action == "SELL":
        stop_loss = price + (price * percs_tmp)
        take_profit = tp_price - (tp_price * perct)
        stop_side = "BUY"
        take_side = "BUY"
    stop_loss = get_price_precision(order['symbol'],stop_loss)
    take_profit = get_price_precision(order['symbol'],take_profit)
    #print("New SL/TP {} {}".format(stop_loss,take_profit))
    return stop_loss, take_profit, stop_side, take_side
    
def update_sltp(order,sl,tp,stop_perc):
    #cancel old sl/tp
    #create new one
    
    stop_loss, take_profit, stop_side, take_side = gen_new_sltp(order,stop_perc)
    #print(tp['stopPrice'],take_profit)
    
    #print("Coin {} updating SL/TP".format(order['symbol']))
    #print("Old TP {} , New TP {}, side {}".format(tp['stopPrice'],take_profit,order['side']))
    
    cur = order['symbol']
    min = order['executedQty']
    #print(tp['stopPrice'],take_profit)
    #print(order['avgPrice'])
    price = client.futures_symbol_ticker(symbol=order['symbol'])
    price = float(price['price'])
    #print(price)
    open = client.futures_get_open_orders(symbol=cur)
    for p in open:
                #print("Cancel Order: {} ID: {}".format(cur,p['orderId']))
                client.futures_cancel_order(symbol=cur,orderId=p['orderId'])
    try:
        
        stop_one = client.futures_create_order(
        symbol=cur,
        
        type='STOP_MARKET',
        stopPrice=stop_loss,
        
        side=stop_side,
        quantity=min,
        reduceOnly=True
        )
        
    except Exception as e:
        print("Error in main update_sltp()  ", (e))
        print(order)
        print(sl)
        print(tp)
        # print("""
        
# current_price: {},
# symbol={},
# timeInForce='GTC',
# price={},
# type='STOP',
# stopPrice={},

# side={},
# quantity={}
# """.format(price,cur,stop_loss,stop_loss,stop_side,min
        # ))
        return False
    try:
        
        stop_two = client.futures_create_order(
        symbol=cur,
        
        type='TAKE_PROFIT_MARKET',
        stopPrice=take_profit,
        
        side=stop_side,
        quantity=min,
        reduceOnly=True
        )
        
    except Exception as e:
        print("Error in update_sltp() ", (e))
        # print("""
        
# current_price: {},
# symbol={},
# timeInForce='GTC',
# price={},
# type='TAKE_PROFIT',
# stopPrice={},

# side={},
# quantity={}
# """.format(price,cur,take_profit,take_profit,stop_side,min
        # ))
        return False
    
    return stop_one,stop_two
            
            
      
# cur,act,pri = check_sub("Alert: Currency BTCUSDTPERP Action buy Price 39129.78")   
# trade(cur,act,pri)      
# cur,act,pri = check_sub("Alert: Currency BTCUSDTPERP Action sell Price 39129.78")   
# trade(cur,act,pri)    

def gen_test_settings(price,qty): 
    test_price = price
    test_qty = qty
    side = 'BUY'
    test_sl, test_tp = test_gen_sl_tp(test_price,side)
    test_trail_sl, test_trail_tp = test_gen_trail(test_price,side)
    roe_sl = roe_quick(test_price,test_sl,test_qty, side)
    roe_tp =  roe_quick(test_price,test_tp,test_qty, side)
    roe_trail = roe_quick(test_price,test_trail_sl,qty,side)
    
    
    
    telegram_msg("Starting new instance")
    telegram_msg("Account balance: {}".format(get_futures_usdt()))
    
    my_str = """
SL/TP% settings 
stop_loss: {} 
trailing_stop_loss: {} 
trail_enabled: {} 
take_profit: {} 
Lev: {} 
Total Open Trades: {} 
""".format(round(roe_sl,2),
                        round(roe_trail,2),
                        roe_check,
                        round(roe_tp,2),
                        lev,
                        allowed_trades)
    telegram_msg(my_str)
    for x in my_str.split("\n"):
        write_to_log(x,'gen_test_settings')
            
def create_fake_trade(cur,side):
    client_info = client.futures_position_information()
    for i in client_info:
        qty = float(i['positionAmt'])
        if side == 'SELL':
            
            qty = qty * -1
        if i['symbol'] == cur:
            
            result = {'symbol': str(cur), 'orderId': 603979786, 'orderListId': -1, 'clientOrderId': 'and_b2ac94a73a434398ab2846394d2027aa', 'price': float(i['entryPrice']), 'avgPrice' : float(i['entryPrice']), 'origQty': qty, 'executedQty': qty, 'cummulativeQuoteQty': '261.72747000', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'LIMIT', 'side': side, 'stopPrice': '0.00000000', 'icebergQty': '0.00000000', 'time': 1622885916811, 'updateTime': 1622885925533, 'isWorking': True, 'origQuoteOrderQty': '0.00000000'}
            #print(result)
            return result

def close_trade(cur,qty,side):
    if side == 'BUY':
        pos = 'SELL'
    if side == 'SELL':
        pos = 'BUY'
    res = client.futures_create_order(
    symbol=cur,
    
    type='MARKET',
    
    
    side=pos,
    quantity=qty,
    reduceOnly=True
    
    )

def check_trade_conditions(order,side):
    cur = order['symbol']
    coin_price = client.futures_symbol_ticker(symbol=order['symbol'])
    coin_price = float(coin_price['price'])
    order_price = float(order['avgPrice'])
    qty = float(order['executedQty'])
    stop_test, take_test = test_gen_sl_tp(order_price,side)
    write_to_log("Coin: {}, order_price {}, Mark price {}, SIDE {}".format(
            order['symbol'],
            order_price,
            coin_price,
            side),'chk_trade_con()')
    if side == 'SELL':
        if coin_price >= order_price:
            print("Trying to Generate new SL/TP for found order {}".format(order['symbol']))
            if coin_price > stop_test:
                print("Trade beyond SL test, trying to exit trade")
                close_trade(cur,qty,side)
                return
            par,stop,take = make_stoptake(order)
            return stop, take
            
    if side == 'BUY':
        if coin_price <= order_price:
            print("Generating new SL/TP for found order {}".format(order['symbol']))
            if coin_price < stop_test:
                write_to_log("Trade  {} beyond SL test, trying to exit trade ".format(order['symbol'],'chk_trade_con()'))
                close_trade(cur,qty,side)
                return
            par,stop,take = make_stoptake(order)
            return stop,take
            
    print("{} Trade in profit, generating new SL/TP based on Current price".format(order['symbol']))
    tmp_order = order
    tmp_order['avgPrice'] = coin_price
    par,stop,take = make_stoptake(tmp_order)
    tmp_order['avgPrice'] = order_price
    
    return stop,take

def check_open_single(coin):
    global trade_list
    #print("Running check_open()...")
    #print("trade_list size = {}".format(len(trade_list)))
    trade_list = []
    #print("trade_list size = {}".format(len(trade_list)))
    client_info = client.futures_position_information()
    result = 0
    for i in client_info:
        if i['symbol'] == coin:
            if float(i['positionAmt']) != 0:
                print("Found open trade: {}".format(i['symbol']))
                open = client.futures_get_open_orders(symbol=i['symbol'])
                for p in open:
                    #print("Cancel Order: {} ID: {}".format(i['symbol'],p['orderId']))
                    client.futures_cancel_order(symbol=i['symbol'],orderId=p['orderId'])
                if float(i['positionAmt']) > 0:
                    pos_side = 'BUY'
                if float(i['positionAmt']) < 0:
                    pos_side = 'SELL'
                #print(i)
                result += find_trades(i['symbol'],pos_side,i['positionAmt'])
        return result

def check_open():
    global trade_list
    #print("Running check_open()...")
    #print("trade_list size = {}".format(len(trade_list)))
    trade_list = []
    #print("trade_list size = {}".format(len(trade_list)))
    client_info = client.futures_position_information()
    result = 0
    for i in client_info:
        
        if float(i['positionAmt']) != 0:
            print("Found open trade: {}".format(i['symbol']))
            open = client.futures_get_open_orders(symbol=i['symbol'])
            for p in open:
                #print("Cancel Order: {} ID: {}".format(i['symbol'],p['orderId']))
                client.futures_cancel_order(symbol=i['symbol'],orderId=p['orderId'])
            if float(i['positionAmt']) > 0:
                pos_side = 'BUY'
            if float(i['positionAmt']) < 0:
                pos_side = 'SELL'
            #print(i)
            result += find_trades(i['symbol'],pos_side,i['positionAmt'])
    return result
            

            
          
def find_trades(cur,side,qty):
    global trade_list
    qty = float(qty)
    par = False
    stop = False
    take = False
    if side == 'SELL':
        qty = qty * -1
        #print(qty)
    
    orders = client.futures_get_all_orders(symbol=cur)
    for x in orders:
        if x['status'] == 'NEW':
            #print(x)
            if x['type'] == 'STOP_MARKET':
                stop = x
            if x['type'] == 'TAKE_PROFIT_MARKET':
                take = x
        tmp_qty = float(x['executedQty'])
        if x['status'] == 'FILLED':
            if tmp_qty == qty:
                par = x
    if not par or not stop or not take:
        print("Missing order, SL or TP")
        print("Creating dummy order for {}".format(cur))
        par = create_fake_trade(cur,side)
        print(par)
        if par:
            open = client.futures_get_open_orders(symbol=cur)
            for i in open:
                #print("Cancel Order: {} ID: {}".format(cur,i['orderId']))
                client.futures_cancel_order(symbol=cur,orderId=i['orderId'])
            stop,take = check_trade_conditions(par,side)
        #print(order_info(stop))
    try:
        print(par)
        trade_dict = { 'Parent' : par, 'SL' : stop, 'TP' : take } 
        trade_list.append(trade_dict)
        return 1
    except Exception as e:
            print("Error in find_trades() ", (e))
            
    return 0
    
def check_trade_list():
    global trade_list
    client_info = client.futures_position_information()
    trade_list_len = len(trade_list)
    current_trades = 0
    for x in client_info:
        if float(x['positionAmt']) != 0:
            current_trades += 1
    if current_trades != trade_list_len:
        write_to_log("Trade_list broken: {} trades found {} trades in list".format(current_trades,trade_list_len),'check_trade_list')
        if current_trades == 0 and trade_list_len > 0:
            #open_trades = check_open() 
            write_to_log("Fixing trade list",'check_trade_list()')
        return True
    return False

print("Starting client....")
write_to_log("Starting client","init()")
oldtime = time.time()
checktime = time.time()
gen_test_settings(1,1)
open_trades = check_open() 
telegram_msg("Checking for open trades...")
telegram_msg("Open trades found: {}".format(open_trades))
write_to_log("Checking open trades",'init()')

screen = curses.initscr()

mail = threading.Thread(target=readmail)

mail.start()
write_to_log("Starting mail thread!...","readmail()")

clear = threading.Thread(target=clear_trades, args=(trade_list,))
clear.start()
write_to_log("Starting clear_trades thread!...","clear_trades()")



filled = threading.Thread(target=check_filled, args=(trade_list,))
filled.start()
write_to_log("Starting check_filled thread!...","check_filled()")

print("Going to main loop!")
 
error_list = False
#print(trade_list)
ch = ''
while ch != ord('q'):
    try:
        local_time = datetime.now()
        if time.time() - oldtime > 7200:
            write_to_log("Trying to gen new client...",'2 hours passed')
            client = Client(user_key, secret_key)
            #check_open()
            oldtime = time.time()
            
     
        
          
        
        client_info = client.futures_position_information()
        curses.cbreak()
        screen.clear()
        screen.addstr(0, 0, "|  Tradingview Alerts Traders  |")
        screen.addstr(1,0,  "================================================================")
        screen.addstr(2,0,  "|   Open trades {}             |{}".format(len(trade_list),local_time.strftime("%c")))
        screen.addstr(3,0,  "================================================================")
        screen.addstr(4,0,  "###    |Coin   |ROE    |PnL    |Price  |QTY    |Side   |SL     |TP     |SLROE")
        screen.addstr(5,0,  "================================================================")
        scr_balance = get_futures_usdt()
        final_roe = 0
        final_pnl = 0
        x = 5
        for i in trade_list:
            x += 1
            cur = i['Parent']['symbol']
            cur_str = cur.replace('USDT','')
            
            cur_price = client.futures_symbol_ticker(symbol=cur)
            cur_price=float(cur_price['price'])
            start_price = float(i['Parent']['avgPrice'])
            side = i['Parent']['side']
            qty = float(i['Parent']['executedQty'])
            my_roe = roe_quick(start_price,cur_price, float(qty), side)
            pnl = get_profit(start_price,cur_price,qty, side )
            sl_p = float(i['SL']['stopPrice'])
            sl_t = float(i['TP']['stopPrice'])
            sl_roe = roe_quick(start_price,sl_p, float(qty), side)
            final_roe += my_roe
            final_pnl += pnl
            
            # x-5,cur_str,
                                                    # round(my_roe,2),
                                                    # round(pnl,2),
                                                    # qty,
                                                    # round(cur_price,2),
                                                    # side,
                                                    # round(sl_p,2),
                                                    # round(sl_t,2)
            
            #Formating strings
            cur_str = cur_str.ljust(8)
            
            roe_str = str(round(my_roe,2))
            roe_str = roe_str.ljust(8)
            
            pnl_str = str(round(pnl,2))
            pnl_str = pnl_str.ljust(8)
            qty_str = str(qty)
            qty_str = qty_str.ljust(8)
            side = side.ljust(8)
            sl_str = str(round(sl_p,4))
            sl_str = sl_str.ljust(9)
            tp_str = str(round(sl_t,4))
            tp_str = tp_str.ljust(9)
            price_str = str(cur_price)
            price_str = price_str.ljust(9)
            sl_roe_str = str(round(sl_roe,1))
            number = str(x-5)
            number = number.ljust(8)
            screen.addstr(x,0,  "{}{}{}{}{}{}{}{}{}{}".format(
                number,cur_str,roe_str,pnl_str,price_str,qty_str,side,sl_str,tp_str,sl_roe_str))
            
                                                    
        screen.addstr(x+1,0, "=========================")
        try:
            avg_croe = final_roe/len(trade_list)
        except:
            avg_croe = 0
        screen.addstr(x+2,0, "# |TOTAL |CROE {}% |TROE {}% |CPROFIT ${}|TPROFIT ${}|   ".format(round(avg_croe,2),round(total_roe,2),round(final_pnl,2),round(total_profit,2)))
        screen.addstr(x+3,0, "Balance ${} | Equity: ${}".format(scr_balance,get_futures_withdrawals()))
        
        screen.addstr(x+4,0, "========")
        screen.addstr(x+5,0, "Logs:")
        screen.addstr(x+6,0, "========")
        log_num = x + 6
        for i in reversed(log_details):
            try:
                log_num += 1
                screen.addstr(log_num,0, "{}".format(i))
            except:
                pass
        
        
        curses.napms(10)
        screen.nodelay(1)
        ch = screen.getch()
        screen.refresh()
        
    except Exception as exc:
            print('generated an exception: %s' % ( exc))
            write_to_log("generated an exception: {}".format(exc),'mainloop')
        
    try:
        #if time.time() - checktime > 5:
        try:
            if mail.is_alive():
                pass #print("skipping thread!")
            else:
                mail = threading.Thread(target=readmail)
                
                mail.start()
                #mail.join()
        except Exception as e:
            print("Error ", (e)) 
            # mail = threading.Thread(target=readmail)
            
            # mail.start()
            #mail.join()
            #readmail()
        try:
            if clear.is_alive():
                pass #print("skipping thread!")
            else:
                
                clear = threading.Thread(target=clear_trades, args=(trade_list,))
                clear.start()
                clear.join()
        except Exception as e:
            print("Error ", (e))   
            
            #clear_trades(trade_list)
            
            
        try:
            if filled.is_alive():
                pass #print("skipping thread!")
            else:
            
                filled = threading.Thread(target=check_filled, args=(trade_list,))
                filled.start()
                filled.join()
        except Exception as e:
            print("Error ", (e))   
            
            
            last_error = error_list 
            error_list = check_trade_list()
            if last_error == True and error_list == True:
                write_to_log("Something wrong with the list?", 'error_list()')
                check_filled()
                
            
            
            
            
        
                    
                    
            
    except Exception as exc:
            print('main loop generated an exception: %s' % ( exc))
            write_to_log("generated an exception: {}".format(exc),'mainloop')
            #telegram_msg('generated an exception: %s' % ( exc))
telegram_msg("Session terminated by user...")
curses.endwin()            
    
