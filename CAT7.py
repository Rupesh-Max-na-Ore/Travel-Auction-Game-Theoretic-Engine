import sqlite3
from itertools import combinations
from tabulate import tabulate

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('auction_engine2.db')
cursor = conn.cursor()

# Create tables if not already created
cursor.execute('''CREATE TABLE IF NOT EXISTS service_providers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    initial_price REAL DEFAULT 10.0,
                    FOREIGN KEY (provider_id) REFERENCES service_providers(id)
                )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS bids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer TEXT NOT NULL,
                    bid_price REAL NOT NULL,
                    bundle TEXT NOT NULL
                )''')

cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL
                )''')

conn.commit()

# Fetch all services and their quantities from the database
def fetch_services():
    cursor.execute("SELECT * FROM services")
    rows = cursor.fetchall()
    print(f"Debug: Fetching services, rows fetched: {rows}")  # Debugging line
    return {row[0]: {"provider_id": row[1], "name": row[2], "quantity": row[3], "initial_price": row[4], "updated_price": row[4]} for row in rows}

# Fetch all service providers from the database
def fetch_service_providers():
    cursor.execute("SELECT * FROM service_providers")
    return {row[0]: row[1] for row in cursor.fetchall()}

# Fetch all bids from the database
def fetch_bids():
    cursor.execute("SELECT * FROM bids")
    rows = cursor.fetchall()
    return [{"id": row[0], "customer": row[1], "bid_price": row[2], "bundle": list(map(int, row[3].split(',')))} for row in rows]

def view_services():
    print("\n--- Available Services ---")
    services = fetch_services()
    service_providers = fetch_service_providers()
    
    table = []
    for service_id, details in services.items():
        provider_name = service_providers.get(details['provider_id'], 'Unknown')
        table.append([service_id, details['name'], provider_name, details['quantity'], details['initial_price']])
    
    headers = ["ID", "Name", "Provider", "Quantity", "Initial Price"]
    print(tabulate(table, headers=headers, tablefmt="grid"))
    print()

def add_service_provider():
    print("\nAdd Service Provider:")
    provider_name = input("Enter Service Provider Name: ")
    cursor.execute("INSERT INTO service_providers (name) VALUES (?)", (provider_name,))
    conn.commit()
    
    # Fetch the ID of the newly added provider
    cursor.execute("SELECT id FROM service_providers WHERE name = ?", (provider_name,))
    provider_id = cursor.fetchone()[0]
    
    print(f"Service Provider '{provider_name}' added successfully with ID {provider_id}.\n")

def add_service():
    try:
        print("\nAdd Service:")
        provider_id = int(input("Enter Service Provider ID: "))
        cursor.execute("SELECT id FROM service_providers WHERE id = ?", (provider_id,))
        if not cursor.fetchone():
            print("Invalid Service Provider ID.")
            return

        service_name = input("Enter Service Name: ")
        quantity = int(input("Enter Quantity: "))
        initial_price = float(input("Enter Initial Price: "))
        cursor.execute("INSERT INTO services (provider_id, name, quantity, initial_price) VALUES (?, ?, ?, ?)",
                       (provider_id, service_name, quantity, initial_price))
        conn.commit()
        print(f"Service '{service_name}' added successfully.\n")
    except Exception as e:
        print(f"Error adding service: {e}\n")

def update_service_list():
    print("\nUpdate Service List:")
    service_id = int(input("Enter Service ID to Update: "))
    try:
        new_quantity = int(input("Enter New Quantity: "))
        new_price = float(input("Enter New Initial Price: "))
        cursor.execute("UPDATE services SET quantity = ?, initial_price = ? WHERE id = ?", 
                       (new_quantity, new_price, service_id))
        conn.commit()
        print(f"Service ID {service_id} updated successfully.\n")
    except Exception as e:
        print(f"Error updating service: {e}\n")

def add_customer():
    print("\nAdd Customer:")
    customer_name = input("Enter Customer Name: ")
    cursor.execute("INSERT INTO customers (name) VALUES (?)", (customer_name,))
    conn.commit()
    print(f"Customer '{customer_name}' added successfully.\n")

def add_bid():
    try:
        print("\n--- Add Bundle Bid ---")
        cursor.execute("SELECT * FROM customers")
        customers = cursor.fetchall()
        print("Customers:")
        for customer in customers:
            print(f"{customer[0]}: {customer[1]}")
        customer_id = int(input("Select Customer ID for Bidding: "))
        customer_name = [c[1] for c in customers if c[0] == customer_id][0]

        view_services()  # Show available services

        selected_services = input("Enter Service IDs for Bundle (comma-separated): ").split(',')
        selected_services = [int(s) for s in selected_services]

        if not all(service_id in fetch_services() for service_id in selected_services):
            print("One or more service IDs are invalid.")
            return

        bid_price = float(input("Enter Bid Price: "))
        bundle = ",".join(map(str, selected_services))

        cursor.execute("INSERT INTO bids (customer, bid_price, bundle) VALUES (?, ?, ?)",
                       (customer_name, bid_price, bundle))
        conn.commit()
        print(f"Bid by '{customer_name}' added successfully.\n")
    except Exception as e:
        print(f"Error adding bid: {e}\n")

# Sort the bids based on bid prices in descending order
def sort_bids(bids):
    return sorted(bids, key=lambda x: -x["bid_price"])

# Backtracking function to find the best allocation maximizing total welfare
def find_best_allocation(services, sorted_bids):
    max_welfare = 0
    best_allocation = []
    
    # Iterate over all possible allocations of bids
    for r in range(len(sorted_bids) + 1):
        for allocation in combinations(sorted_bids, r):
            current_allocation = []
            service_usage = {s: 0 for s in services}
            welfare = 0
            
            # Check if the allocation is valid and calculate welfare
            for bid in allocation:
                is_valid = True
                for service_id in bid["bundle"]:
                    if service_usage[service_id] + 1 > services[service_id]["quantity"]:
                        is_valid = False
                        break
                    service_usage[service_id] += 1
                
                if is_valid:
                    current_allocation.append(bid)
                    welfare += bid["bid_price"]
            
            # Update best allocation if welfare is maximized
            if welfare > max_welfare:
                max_welfare = welfare
                best_allocation = current_allocation
    
    return best_allocation, max_welfare

# Update prices based on demand and supply for the allocated services
def update_prices(services, allocation, alpha=0.1):
    # Calculate demand for each service based on the allocation
    demand_count = {s: 0 for s in services}
    for bid in allocation:
        for service_id in bid["bundle"]:
            demand_count[service_id] += 1
    
    # Update prices based on demand and supply
    for service_id, details in services.items():
        demand = demand_count[service_id]
        supply = details["quantity"]
        if demand > supply:
            details["updated_price"] = details["initial_price"] * (1 + alpha) ** (demand - supply)
        else:
            details["updated_price"] = details["initial_price"]  # No change if demand <= supply

# Determine the price each winner needs to pay for their bundle
def calculate_winner_prices(allocation, services):
    winner_prices = {}
    for bid in allocation:
        total_price = sum(services[service_id]["updated_price"] for service_id in bid["bundle"])
        winner_prices[bid["customer"]] = total_price
    return winner_prices

# Update service quantities after auction
def update_service_quantities(allocation):
    for bid in allocation:
        for service_id in bid["bundle"]:
            cursor.execute("UPDATE services SET quantity = quantity - 1 WHERE id = ?", (service_id,))
    conn.commit()

# Remove winning bids from the bid list
def remove_winning_bids(allocation):
    for bid in allocation:
        cursor.execute("DELETE FROM bids WHERE id = ?", (bid["id"],))
    conn.commit()

# Main function to resolve auction conflicts and determine winners
def resolve_conflicts():
    # Fetch services and bids from the database
    services = fetch_services()
    bids = fetch_bids()

    # Sort the bids by price
    sorted_bids = sort_bids(bids)

    # Find the best allocation maximizing social welfare
    best_allocation, max_welfare = find_best_allocation(services, sorted_bids)

    # Update prices based on demand and supply
    update_prices(services, best_allocation)

    # Calculate the prices each winner needs to pay for their bundle
    winner_prices = calculate_winner_prices(best_allocation, services)

    # Output the results
    print(f"Total Welfare: {max_welfare}")
    print("Accepted Bids and Prices:")
    for bid in best_allocation:
        print(f"Customer: {bid['customer']}, Bid Price: {bid['bid_price']}, "
              f"Bundle: {[services[s]['name'] for s in bid['bundle']]}, "
              f"Price to Pay: {winner_prices[bid['customer']]}")
    print("Rejected Bids:")
    for bid in sorted_bids:
        if bid not in best_allocation:
            print(f"Customer: {bid['customer']}, Bid Price: {bid['bid_price']}, "
                  f"Bundle: {[services[s]['name'] for s in bid['bundle']]}")
    
    # Update service quantities after auction
    update_service_quantities(best_allocation)

    # Remove winning bids from the bid list
    print("\nDo you want to remove winning bids from the bid list? (yes/no)")
    if input().lower() == 'yes':
        remove_winning_bids(best_allocation)
        print("Winning bids removed from the bid list.\n")

def main_menu():
    while True:
        print("\n--- Auction Engine Menu ---")
        print("1. Add Service Provider")
        print("2. Add Service to Service List")
        print("3. View Service List for Customers")
        print("4. Update Service List")
        print("5. Add Customer")
        print("6. Add Bundles for Customer Bids")
        print("7. Start Auction")
        print("8. Exit")
        choice = input("Select an option: ")

        if choice == '1':
            add_service_provider()
        elif choice == '2':
            add_service()
        elif choice == '3':
            view_services()
        elif choice == '4':
            update_service_list()
        elif choice == '5':
            add_customer()
        elif choice == '6':
            add_bid()
        elif choice == '7':
            resolve_conflicts()
        elif choice == '8':
            print("Exiting Auction Engine. Goodbye!")
            break
        else:
            print("Invalid option, please try again.")

# Run the main menu
main_menu()

# Close the database connection when done
conn.close()
