import csv
import json
import os
from datetime import datetime
from pathlib import Path


DATA_FILE = "crypto_trades.json"
CSV_FILE = "crypto_trades_export.csv"

STATUSES = {
    "PENDING": "pending_limit",
    "CANCELED": "canceled",
    "ACTIVE": "active",
    "CLOSED": "closed",
}

FIELDNAMES = [
    "trade_id",
    "created_timestamp",
    "filled_timestamp",
    "canceled_timestamp",
    "symbol",
    "direction",
    "order_type",
    "status",
    "planned_entry_price",
    "actual_entry_price",
    "stop_loss_price",
    "risk_per_coin",
    "take_profit_1r",
    "take_profit_2r",
    "take_profit_3r",
    "position_size",
    "fees_paid",
    "exit_price",
    "exit_timestamp",
    "profit_loss_dollars",
    "r_result",
    "result_type",
    "notes",
]


def script_folder():
    return Path(__file__).resolve().parent


def data_path():
    return script_folder() / DATA_FILE


def csv_path():
    return script_folder() / CSV_FILE


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def money(value):
    return f"{value:.2f}"


def number_text(value):
    if value == "":
        return ""
    if value is None:
        return ""
    return f"{float(value):.8f}".rstrip("0").rstrip(".")


def pause():
    input("\nPress Enter to continue...")


def load_trades():
    path = data_path()
    if not path.exists():
        return []

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, list):
                return data
    except json.JSONDecodeError:
        print("The data file could not be read. Starting with an empty list.")
    except OSError:
        print("The data file could not be opened. Starting with an empty list.")

    return []


def save_trades(trades):
    with data_path().open("w", encoding="utf-8") as file:
        json.dump(trades, file, indent=2)


def next_trade_id(trades):
    highest = 0
    for trade in trades:
        trade_id = str(trade.get("trade_id", "T0000"))
        digits = "".join(ch for ch in trade_id if ch.isdigit())
        if digits:
            highest = max(highest, int(digits))
    return f"T{highest + 1:04d}"


def ask_text(prompt, required=True):
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("Please enter a value.")


def ask_float(prompt, allow_blank=False, default=None, minimum=None):
    while True:
        value = input(prompt).strip()

        if value == "" and allow_blank:
            return default

        try:
            number = float(value)
        except ValueError:
            print("Please enter a number.")
            continue

        if minimum is not None and number < minimum:
            print(f"Please enter a number of at least {minimum}.")
            continue

        return number


def ask_price(prompt, allow_blank=False, default=None):
    return ask_float(prompt, allow_blank=allow_blank, default=default, minimum=0.00000001)


def ask_fees(prompt):
    return ask_float(prompt, allow_blank=True, default=0.0, minimum=0.0)


def ask_direction():
    while True:
        direction = input("Direction (long/short): ").strip().lower()
        if direction in ("long", "short"):
            return direction
        print("Please type long or short.")


def validate_stop_loss(direction, entry_price, stop_loss_price):
    if direction == "long" and stop_loss_price >= entry_price:
        print("For a long trade, the stop loss must be below the entry price.")
        return False
    if direction == "short" and stop_loss_price <= entry_price:
        print("For a short trade, the stop loss must be above the entry price.")
        return False
    return True


def ask_trade_setup(is_limit_order):
    symbol = ask_text("Symbol (example BTC, ETH, SOL): ").upper()
    direction = ask_direction()

    while True:
        if is_limit_order:
            entry_price = ask_price("Planned limit entry price: ")
        else:
            entry_price = ask_price("Entry price: ")
        stop_loss_price = ask_price("Stop loss price: ")
        if validate_stop_loss(direction, entry_price, stop_loss_price):
            break

    position_size = ask_float("Position size in coins: ", minimum=0.00000001)
    fees_paid = ask_fees("Fees paid (optional, press Enter for 0): ")
    notes = ask_text("Notes (optional): ", required=False)

    return {
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "stop_loss_price": stop_loss_price,
        "position_size": position_size,
        "fees_paid": fees_paid,
        "notes": notes,
    }


def calculate_r_values(direction, entry_price, stop_loss_price):
    # R is the distance from entry to stop loss.
    # For a long, price must rise to make profit. For a short, price must fall.
    if direction == "long":
        risk_per_coin = entry_price - stop_loss_price
        take_profit_1r = entry_price + risk_per_coin
        take_profit_2r = entry_price + (risk_per_coin * 2)
        take_profit_3r = entry_price + (risk_per_coin * 3)
    else:
        risk_per_coin = stop_loss_price - entry_price
        take_profit_1r = entry_price - risk_per_coin
        take_profit_2r = entry_price - (risk_per_coin * 2)
        take_profit_3r = entry_price - (risk_per_coin * 3)

    return {
        "risk_per_coin": risk_per_coin,
        "take_profit_1r": take_profit_1r,
        "take_profit_2r": take_profit_2r,
        "take_profit_3r": take_profit_3r,
    }


def calculate_profit_loss(direction, entry_price, exit_price, position_size, fees_paid):
    # Dollar profit/loss is price movement times coin size, minus all fees.
    if direction == "long":
        return ((exit_price - entry_price) * position_size) - fees_paid
    return ((entry_price - exit_price) * position_size) - fees_paid


def calculate_r_result(direction, entry_price, exit_price, risk_per_coin):
    # R result measures the exit move compared to the original risk per coin.
    if direction == "long":
        return (exit_price - entry_price) / risk_per_coin
    return (entry_price - exit_price) / risk_per_coin


def result_type(profit_loss):
    if profit_loss > 0:
        return "win"
    if profit_loss < 0:
        return "loss"
    return "breakeven"


def show_r_values(entry_price, stop_loss_price, values):
    print("\nR Plan")
    print(f"Entry price:       {number_text(entry_price)}")
    print(f"-1R stop loss:     {number_text(stop_loss_price)}")
    print(f"Risk per coin:     {number_text(values['risk_per_coin'])}")
    print(f"1R target:         {number_text(values['take_profit_1r'])}")
    print(f"2R target:         {number_text(values['take_profit_2r'])}")
    print(f"3R target:         {number_text(values['take_profit_3r'])}")


def create_trade_record(trade_id, setup, order_type, status):
    entry_price = setup["entry_price"]
    r_values = calculate_r_values(setup["direction"], entry_price, setup["stop_loss_price"])

    actual_entry = entry_price if status == STATUSES["ACTIVE"] else ""
    filled_timestamp = now_text() if status == STATUSES["ACTIVE"] else ""

    record = {
        "trade_id": trade_id,
        "created_timestamp": now_text(),
        "filled_timestamp": filled_timestamp,
        "canceled_timestamp": "",
        "symbol": setup["symbol"],
        "direction": setup["direction"],
        "order_type": order_type,
        "status": status,
        "planned_entry_price": entry_price,
        "actual_entry_price": actual_entry,
        "stop_loss_price": setup["stop_loss_price"],
        "risk_per_coin": r_values["risk_per_coin"],
        "take_profit_1r": r_values["take_profit_1r"],
        "take_profit_2r": r_values["take_profit_2r"],
        "take_profit_3r": r_values["take_profit_3r"],
        "position_size": setup["position_size"],
        "fees_paid": setup["fees_paid"],
        "exit_price": "",
        "exit_timestamp": "",
        "profit_loss_dollars": "",
        "r_result": "",
        "result_type": "",
        "notes": setup["notes"],
    }

    return record


def print_trade_row(trade):
    entry = trade.get("actual_entry_price") or trade.get("planned_entry_price")
    print(
        f"{trade.get('trade_id')} | {trade.get('symbol')} | "
        f"{trade.get('direction')} | {trade.get('order_type')} | "
        f"{trade.get('status')} | entry {number_text(entry)} | "
        f"stop {number_text(trade.get('stop_loss_price'))} | "
        f"size {number_text(trade.get('position_size'))}"
    )


def print_trade_details(trade):
    print_trade_row(trade)
    print(
        f"  Risk: {number_text(trade.get('risk_per_coin'))} | "
        f"1R: {number_text(trade.get('take_profit_1r'))} | "
        f"2R: {number_text(trade.get('take_profit_2r'))} | "
        f"3R: {number_text(trade.get('take_profit_3r'))}"
    )
    if trade.get("status") == STATUSES["CLOSED"]:
        print(
            f"  Exit: {number_text(trade.get('exit_price'))} | "
            f"P/L: ${money(float(trade.get('profit_loss_dollars', 0)))} | "
            f"R: {number_text(trade.get('r_result'))}R | "
            f"{trade.get('result_type')}"
        )
    if trade.get("notes"):
        print(f"  Notes: {trade.get('notes')}")


def choose_trade(trades, status, empty_message):
    matching = [trade for trade in trades if trade.get("status") == status]
    if not matching:
        print(empty_message)
        return None

    for trade in matching:
        print_trade_row(trade)

    while True:
        trade_id = ask_text("\nEnter trade ID, or B to go back: ").upper()
        if trade_id == "B":
            return None

        for trade in matching:
            if trade.get("trade_id", "").upper() == trade_id:
                return trade

        print("That trade ID was not found in this list.")


def new_market_trade(trades):
    print("\nNew Market Trade")
    setup = ask_trade_setup(is_limit_order=False)
    r_values = calculate_r_values(setup["direction"], setup["entry_price"], setup["stop_loss_price"])
    show_r_values(setup["entry_price"], setup["stop_loss_price"], r_values)

    trade = create_trade_record(next_trade_id(trades), setup, "market", STATUSES["ACTIVE"])
    trades.append(trade)
    save_trades(trades)
    print(f"\nSaved as active trade {trade['trade_id']}.")


def new_limit_order(trades):
    print("\nNew Limit Order")
    setup = ask_trade_setup(is_limit_order=True)
    r_values = calculate_r_values(setup["direction"], setup["entry_price"], setup["stop_loss_price"])
    show_r_values(setup["entry_price"], setup["stop_loss_price"], r_values)

    trade = create_trade_record(next_trade_id(trades), setup, "limit", STATUSES["PENDING"])
    trades.append(trade)
    save_trades(trades)
    print(f"\nSaved as pending limit order {trade['trade_id']}.")


def update_limit_order(trades):
    print("\nPending Limit Orders")
    trade = choose_trade(
        trades,
        STATUSES["PENDING"],
        "There are no pending limit orders.",
    )
    if trade is None:
        return

    while True:
        print("\n1. Filled")
        print("2. Canceled")
        print("3. Back")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            planned_entry = float(trade["planned_entry_price"])
            actual_entry = ask_price(
                "Actual fill price (press Enter to use planned entry): ",
                allow_blank=True,
                default=planned_entry,
            )
            if not validate_stop_loss(trade["direction"], actual_entry, float(trade["stop_loss_price"])):
                continue

            r_values = calculate_r_values(
                trade["direction"],
                actual_entry,
                float(trade["stop_loss_price"]),
            )
            trade["actual_entry_price"] = actual_entry
            trade["risk_per_coin"] = r_values["risk_per_coin"]
            trade["take_profit_1r"] = r_values["take_profit_1r"]
            trade["take_profit_2r"] = r_values["take_profit_2r"]
            trade["take_profit_3r"] = r_values["take_profit_3r"]
            trade["status"] = STATUSES["ACTIVE"]
            trade["filled_timestamp"] = now_text()
            save_trades(trades)

            show_r_values(actual_entry, float(trade["stop_loss_price"]), r_values)
            print(f"\nLimit order {trade['trade_id']} is now active.")
            return

        if choice == "2":
            trade["status"] = STATUSES["CANCELED"]
            trade["canceled_timestamp"] = now_text()
            save_trades(trades)
            print(f"\nLimit order {trade['trade_id']} was canceled.")
            return

        if choice == "3":
            return

        print("Please choose 1, 2, or 3.")


def close_active_trade(trades):
    print("\nActive Trades")
    trade = choose_trade(
        trades,
        STATUSES["ACTIVE"],
        "There are no active trades.",
    )
    if trade is None:
        return

    exit_price = ask_price("Exit price: ")
    exit_fees = ask_fees("Exit fees (optional, press Enter for 0): ")
    closing_notes = ask_text("Closing notes (optional): ", required=False)

    entry_price = float(trade["actual_entry_price"])
    position_size = float(trade["position_size"])
    total_fees = float(trade.get("fees_paid", 0)) + exit_fees
    risk_per_coin = float(trade["risk_per_coin"])

    profit_loss = calculate_profit_loss(
        trade["direction"],
        entry_price,
        exit_price,
        position_size,
        total_fees,
    )
    r_result = calculate_r_result(trade["direction"], entry_price, exit_price, risk_per_coin)

    trade["fees_paid"] = total_fees
    trade["exit_price"] = exit_price
    trade["exit_timestamp"] = now_text()
    trade["profit_loss_dollars"] = profit_loss
    trade["r_result"] = r_result
    trade["result_type"] = result_type(profit_loss)
    trade["status"] = STATUSES["CLOSED"]
    if closing_notes:
        if trade.get("notes"):
            trade["notes"] = trade["notes"] + " | Close: " + closing_notes
        else:
            trade["notes"] = "Close: " + closing_notes

    save_trades(trades)

    print("\nTrade closed.")
    print(f"Profit/Loss: ${money(profit_loss)}")
    print(f"R result: {number_text(r_result)}R")
    print(f"Result: {trade['result_type']}")


def view_by_status(trades, status, title, empty_message):
    print(f"\n{title}")
    matching = [trade for trade in trades if trade.get("status") == status]
    if not matching:
        print(empty_message)
        return
    for trade in matching:
        print_trade_details(trade)


def career_stats(trades):
    print("\nCareer Stats")

    closed = [trade for trade in trades if trade.get("status") == STATUSES["CLOSED"]]
    pending_count = len([trade for trade in trades if trade.get("status") == STATUSES["PENDING"]])
    active_count = len([trade for trade in trades if trade.get("status") == STATUSES["ACTIVE"]])

    total_closed = len(closed)
    wins = len([trade for trade in closed if trade.get("result_type") == "win"])
    losses = len([trade for trade in closed if trade.get("result_type") == "loss"])
    breakevens = len([trade for trade in closed if trade.get("result_type") == "breakeven"])

    print(f"Pending limit orders: {pending_count}")
    print(f"Active trades:        {active_count}")
    print(f"Total closed trades:  {total_closed}")

    if total_closed == 0:
        print("No closed trades yet.")
        return

    profit_losses = [float(trade.get("profit_loss_dollars", 0)) for trade in closed]
    r_results = [float(trade.get("r_result", 0)) for trade in closed]

    total_profit_loss = sum(profit_losses)
    total_r = sum(r_results)

    print(f"Wins:                 {wins}")
    print(f"Losses:               {losses}")
    print(f"Breakevens:           {breakevens}")
    print(f"Win rate:             {(wins / total_closed) * 100:.2f}%")
    print(f"Total profit/loss:    ${money(total_profit_loss)}")
    print(f"Average P/L/trade:    ${money(total_profit_loss / total_closed)}")
    print(f"Total R:              {number_text(total_r)}R")
    print(f"Average R/trade:      {number_text(total_r / total_closed)}R")
    print(f"Best trade dollars:   ${money(max(profit_losses))}")
    print(f"Worst trade dollars:  ${money(min(profit_losses))}")
    print(f"Best trade R:         {number_text(max(r_results))}R")
    print(f"Worst trade R:        {number_text(min(r_results))}R")


def export_csv(trades):
    with csv_path().open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for trade in trades:
            row = {}
            for field in FIELDNAMES:
                row[field] = trade.get(field, "")
            writer.writerow(row)

    print(f"\nExported {len(trades)} records to {CSV_FILE}.")


def show_menu():
    print("\nCrypto Trade Logger")
    print("1. New Market Trade")
    print("2. New Limit Order")
    print("3. Update Limit Order")
    print("4. Close Active Trade")
    print("5. View Open Limit Orders")
    print("6. View Active Trades")
    print("7. View Closed Trades")
    print("8. Career Stats")
    print("9. Export CSV")
    print("10. Exit")


def main():
    trades = load_trades()

    while True:
        show_menu()
        choice = input("Choose an option: ").strip()

        if choice == "1":
            new_market_trade(trades)
            pause()
        elif choice == "2":
            new_limit_order(trades)
            pause()
        elif choice == "3":
            update_limit_order(trades)
            pause()
        elif choice == "4":
            close_active_trade(trades)
            pause()
        elif choice == "5":
            view_by_status(
                trades,
                STATUSES["PENDING"],
                "Open Limit Orders",
                "There are no open limit orders.",
            )
            pause()
        elif choice == "6":
            view_by_status(
                trades,
                STATUSES["ACTIVE"],
                "Active Trades",
                "There are no active trades.",
            )
            pause()
        elif choice == "7":
            view_by_status(
                trades,
                STATUSES["CLOSED"],
                "Closed Trades",
                "There are no closed trades.",
            )
            pause()
        elif choice == "8":
            career_stats(trades)
            pause()
        elif choice == "9":
            export_csv(trades)
            pause()
        elif choice == "10":
            print("Goodbye.")
            break
        else:
            print("Please choose a number from 1 to 10.")


if __name__ == "__main__":
    main()
