import ccxt
import asyncio
import sqlite3

# Set up Bybit API credentials
bybit_main = ccxt.bybit({
    'apiKey': 'IlnYUKJM4gFeMIbOgm',
    'secret': 'KL9nGplpcjvlZoeyoqwO04MQ7n0R3B9Bphia',
})

bybit_replica = ccxt.bybit({
    'apiKey': 'lzO2VsPlupfL3heYx0',
    'secret': 'pnxkQIn2Z4PeKGgNqr2L1b4XBgwMHjeOQKPJ',
})

# Establish a persistent database connection
conn = sqlite3.connect('trades.db')
cursor = conn.cursor()

def get_replica_trade_id(main_trade_id):
    cursor.execute('SELECT replica_trade_id FROM trade_mappings WHERE main_trade_id = ?', (main_trade_id,))
    row = cursor.fetchone()
    return row[0] if row else None

def store_trade_mapping(main_trade_id, replica_trade_id, symbol):
    cursor.execute('INSERT INTO trade_mappings (main_trade_id, replica_trade_id, symbol) VALUES (?, ?, ?)', (main_trade_id, replica_trade_id, symbol))
    conn.commit()
    print(f"Stored trade mapping: Main Trade ID {main_trade_id} with Symbol {symbol} -> Replica Trade ID {replica_trade_id}")

def remove_trade_mapping(main_trade_id):
    cursor.execute('DELETE FROM trade_mappings WHERE main_trade_id = ?', (main_trade_id,))
    conn.commit()
    print(f"Removed trade mapping: Main Trade ID {main_trade_id}")

async def replicate_positions():
    print("Checking for new positions to replicate...")
    try:
        open_positions_main = bybit_main.fetch_positions()
        print(f"Fetched {len(open_positions_main)} open positions from the main account.")
    except Exception as e:
        print(f"Error fetching open positions from the main account: {e}")
        return

    for position in open_positions_main:
        try:
            # Construct a unique identifier for the position
            position_id = f"{position['symbol']}_{position['side']}"

            if position_id and not get_replica_trade_id(position_id):
                direction = 'sell' if position['side'] == 'long' else 'buy'
                position_amount = position['contracts']  # Assuming 'contracts' is the correct field for amount

                order = bybit_replica.create_market_order(symbol=position['symbol'],
                                                          side=direction,
                                                          amount=position_amount)

                store_trade_mapping(position_id, order['id'], position['symbol'])
                print(f"Replicated position: {position['symbol']} {direction.upper()} {position_amount}")
            else:
                print(f"Skipping position {position_id}: Missing data or already replicated.")
        except Exception as e:
            print(f"Error replicating position {position_id}: {e}")



async def check_and_close_trades():
    print("Checking for trades to close...")
    try:
        current_positions_main = bybit_main.fetch_positions()
        current_positions_main_ids = {f"{p['symbol']}_{p['side']}" for p in current_positions_main}
        print(f"Current open positions in main account: {current_positions_main_ids}")
    except Exception as e:
        print(f"Error fetching current positions from the main account: {e}")
        return

    cursor.execute('SELECT main_trade_id, symbol FROM trade_mappings')
    stored_trade_mappings = cursor.fetchall()

    for main_trade_id, symbol in stored_trade_mappings:
        if main_trade_id not in current_positions_main_ids:
            try:
                replica_trade_id = get_replica_trade_id(main_trade_id)
                if replica_trade_id:
                    _, main_side = main_trade_id.split('_')
                    # Determine the correct closing direction based on the main account's position side
                    close_direction = 'buy' if main_side == 'long' else 'sell'

                    try:
                        replica_position = bybit_replica.fetch_position(symbol)
                        position_amount = replica_position['contracts']
                        print(f"Placing {close_direction.upper()} order for {position_amount} of {symbol} in replica account...")

                        close_order_response = bybit_replica.create_market_order(symbol=symbol, side=close_direction, amount=position_amount)
                        print(f"Close order response: {close_order_response}")

                        remove_trade_mapping(main_trade_id)
                        print(f"Removed trade mapping for {main_trade_id}")
                    except Exception as e:
                        print(f"Error in closing position for {main_trade_id}: {e}")
            except Exception as e:
                print(f"Error processing position {main_trade_id}: {e}")



async def main():
    while True:
        await replicate_positions()
        await check_and_close_trades()
        await asyncio.sleep(2)  # Check every 60 seconds
        print("Waiting for the next check...")

print("Starting trade replication script...")
# Run the asynchronous main function
asyncio.run(main())

# Close the database connection when the script is terminated
conn.close()
