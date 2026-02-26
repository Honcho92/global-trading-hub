import sys

def calculate_position_size(account_balance, risk_percentage, entry_price, stop_loss):
    risk_amount = account_balance * (risk_percentage / 100)
    stop_loss_dist = abs(entry_price - stop_loss)
    
    # JPY Detection (e.g., AUDJPY 109.95)
    is_jpy = entry_price > 50 
    
    if is_jpy:
        pips = stop_loss_dist / 0.01
        # Approx USD value of 1 pip for 0.01 lot of AUDJPY
        pip_value_micro = 0.09 
    else:
        pips = stop_loss_dist / 0.0001
        # Standard USD value of 1 pip for 0.01 lot of EURUSD
        pip_value_micro = 0.10 
        
    if pips == 0: 
        return 0
    
    # Calculate how many 0.01 lots fit into our risk amount
    total_lots = (risk_amount / (pips * pip_value_micro)) * 0.01
    return round(total_lots, 2)

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 risk_calc.py [balance] [risk_percent] [entry] [stop_loss]")
        print("Example: python3 risk_calc.py 1000 2 109.95 109.00")
    else:
        balance = float(sys.argv[1])
        risk = float(sys.argv[2])
        entry = float(sys.argv[3])
        sl = float(sys.argv[4])
        
        lot = calculate_position_size(balance, risk, entry, sl)
        # Ensure we always use at least the minimum lot size if we trade
        suggested_lot = max(lot, 0.01)
        
        print(f"Target Risk: ${balance * (risk/100):.2f}")
        print(f"Stop Loss Distance: {abs(entry-sl):.2f}")
        print(f"--- SUGGESTED LOT SIZE: {suggested_lot} ---")
