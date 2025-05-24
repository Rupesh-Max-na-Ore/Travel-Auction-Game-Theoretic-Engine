import sqlite3
from tkinter import Tk, Label, Button, Entry, StringVar, IntVar, messagebox, Listbox, Scrollbar, SINGLE, END
from tkinter import Frame
from tabulate import tabulate
from itertools import combinations

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

def fetch_services():
    cursor.execute("SELECT * FROM services")
    rows = cursor.fetchall()
    return {row[0]: {"provider_id": row[1], "name": row[2], "quantity": row[3], "initial_price": row[4], "updated_price": row[4]} for row in rows}

def fetch_service_providers():
    cursor.execute("SELECT * FROM service_providers")
    return {row[0]: row[1] for row in cursor.fetchall()}

def fetch_bids():
    cursor.execute("SELECT * FROM bids")
    rows = cursor.fetchall()
    return [{"id": row[0], "customer": row[1], "bid_price": row[2], "bundle": list(map(int, row[3].split(',')))} for row in rows]

def view_services():
    services = fetch_services()
    service_providers = fetch_service_providers()
    
    table = []
    for service_id, details in services.items():
        if details["quantity"] > 0:
            provider_name = service_providers.get(details['provider_id'], 'Unknown')
            table.append([service_id, details['name'], provider_name, details['quantity'], details['initial_price']])
    
    headers = ["ID", "Name", "Provider", "Quantity", "Initial Price"]
    return table, headers

def add_service_provider(provider_name):
    cursor.execute("INSERT INTO service_providers (name) VALUES (?)", (provider_name,))
    conn.commit()
    
    cursor.execute("SELECT id FROM service_providers WHERE name = ?", (provider_name,))
    provider_id = cursor.fetchone()[0]
    
    return provider_id

def add_service(provider_id, service_name, quantity, initial_price):
    cursor.execute("INSERT INTO services (provider_id, name, quantity, initial_price) VALUES (?, ?, ?, ?)",
                   (provider_id, service_name, quantity, initial_price))
    conn.commit()

def update_service(service_id, new_quantity, new_price):
    cursor.execute("UPDATE services SET quantity = ?, initial_price = ? WHERE id = ?", 
                   (new_quantity, new_price, service_id))
    conn.commit()

def add_customer(customer_name):
    cursor.execute("INSERT INTO customers (name) VALUES (?)", (customer_name,))
    conn.commit()

def add_bid(customer_name, bid_price, selected_services):
    bundle = ",".join(map(str, selected_services))
    cursor.execute("INSERT INTO bids (customer, bid_price, bundle) VALUES (?, ?, ?)",
                   (customer_name, bid_price, bundle))
    conn.commit()

def clear_all_bids():
    cursor.execute("DELETE FROM bids")
    conn.commit()

def clear_all_data():
    cursor.execute("DELETE FROM bids")
    cursor.execute("DELETE FROM services")
    cursor.execute("DELETE FROM service_providers")
    cursor.execute("DELETE FROM customers")
    conn.commit()

def sort_bids(bids):
    return sorted(bids, key=lambda x: -x["bid_price"])

def find_best_allocation(services, sorted_bids):
    max_welfare = 0
    best_allocation = []
    
    for r in range(len(sorted_bids) + 1):
        for allocation in combinations(sorted_bids, r):
            current_allocation = []
            service_usage = {s: 0 for s in services}
            welfare = 0
            
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
            
            if welfare > max_welfare:
                max_welfare = welfare
                best_allocation = current_allocation
    
    return best_allocation, max_welfare

def update_prices(services, allocation, alpha=0.1):
    """
    Update the prices of services based on demand and supply.
    
    :param services: Dictionary of available services.
    :param allocation: List of accepted bids.
    :param alpha: Price adjustment factor.
    """
    demand_count = {s: 0 for s in services}
    
    # Count the demand for each service from the accepted bids
    for bid in allocation:
        for service_id in bid["bundle"]:
            demand_count[service_id] += 1
    
    # Update the price of each service based on its demand vs. supply
    for service_id, details in services.items():
        demand = demand_count[service_id]
        supply = details["quantity"]
        # Increase price if demand exceeds supply
        if demand > supply:
            details["updated_price"] = details["initial_price"] * (1 + alpha) ** (demand - supply)
        else:
            details["updated_price"] = details["initial_price"] * (1 - alpha) ** max(0, (supply - demand))

def calculate_winner_prices(allocation, services):
    """
    Calculate the final price for each winning bid based on updated service prices.

    :param allocation: List of winning bids.
    :param services: Dictionary of available services with updated prices.
    :return: Dictionary mapping each customer to their total price.
    """
    winner_prices = {}
    for bid in allocation:
        total_price = sum(services[service_id]["updated_price"] for service_id in bid["bundle"])
        winner_prices[bid["customer"]] = total_price
    return winner_prices


def update_service_quantities(allocation):
    for bid in allocation:
        for service_id in bid["bundle"]:
            cursor.execute("UPDATE services SET quantity = quantity - 1 WHERE id = ?", (service_id,))
    conn.commit()

def remove_winning_bids(allocation):
    for bid in allocation:
        cursor.execute("DELETE FROM bids WHERE id = ?", (bid["id"],))
    conn.commit()

def resolve_conflicts():
    services = fetch_services()
    bids = fetch_bids()

    sorted_bids = sort_bids(bids)
    best_allocation, max_welfare = find_best_allocation(services, sorted_bids)
    update_prices(services, best_allocation)
    winner_prices = calculate_winner_prices(best_allocation, services)

    result = f"Total Welfare: {max_welfare}\n\nAccepted Bids and Prices:\n"
    for bid in best_allocation:
        bundle_names = [services[service_id]['name'] for service_id in bid['bundle']]
        total_price = sum(services[service_id]['updated_price'] for service_id in bid['bundle'])
        result += (f"Customer: {bid['customer']}, Bid Price: {bid['bid_price']}, "
                   f"Bundle: {bundle_names}, Total Price to Pay: {total_price}\n")
    
    result += "\nRejected Bids:\n"
    for bid in sorted_bids:
        if bid not in best_allocation:
            bundle_names = [services[service_id]['name'] for service_id in bid['bundle']]
            result += (f"Customer: {bid['customer']}, Bid Price: {bid['bid_price']}, "
                       f"Bundle: {bundle_names}\n")

    update_service_quantities(best_allocation)
    if messagebox.askyesno("Remove Winning Bids", "Do you want to remove winning bids from the bid list?"):
        remove_winning_bids(best_allocation)
        result += "\nWinning bids removed from the bid list."

    return result

class AuctionApp:
    def __init__(self, root):
        self.root = root
        root.title("Auction Engine")
        
        # Create and place widgets
        self.create_widgets()

    def create_widgets(self):


        # Frames
        self.frame = Frame(self.root)
        self.frame.pack(padx=10, pady=10)

        # Provider Name Entry
        self.provider_name_var = StringVar()
        Label(self.frame, text="Service Provider Name:").grid(row=0, column=0, padx=5, pady=5)
        self.provider_name_entry = Entry(self.frame, textvariable=self.provider_name_var)
        self.provider_name_entry.grid(row=0, column=1, padx=5, pady=5)
        Button(self.frame, text="Add Service Provider", command=self.add_service_provider).grid(row=0, column=2, padx=5, pady=5)

        # Service Entries
        self.provider_id_var = IntVar()
        self.service_name_var = StringVar()
        self.quantity_var = IntVar()
        self.initial_price_var = StringVar()
        
        Label(self.frame, text="Service Provider ID:").grid(row=1, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.provider_id_var).grid(row=1, column=1, padx=5, pady=5)
        Label(self.frame, text="Service Name:").grid(row=2, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.service_name_var).grid(row=2, column=1, padx=5, pady=5)
        Label(self.frame, text="Quantity:").grid(row=3, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.quantity_var).grid(row=3, column=1, padx=5, pady=5)
        Label(self.frame, text="Initial Price:").grid(row=4, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.initial_price_var).grid(row=4, column=1, padx=5, pady=5)
        Button(self.frame, text="Add Service", command=self.add_service).grid(row=5, column=1, padx=5, pady=5)

        # Add these lines to add update quantity section
        self.update_service_id_var = IntVar()
        self.update_quantity_var = IntVar()

        Label(self.frame, text="Service ID to Update:").grid(row=16, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.update_service_id_var).grid(row=16, column=1, padx=5, pady=5)

        Label(self.frame, text="New Quantity:").grid(row=17, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.update_quantity_var).grid(row=17, column=1, padx=5, pady=5)

        Button(self.frame, text="Update Service Quantity", command=self.update_service_quantity).grid(row=18, column=1, padx=5, pady=5)


        # Customer Entry
        self.customer_name_var = StringVar()
        Label(self.frame, text="Customer Name:").grid(row=6, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.customer_name_var).grid(row=6, column=1, padx=5, pady=5)
        Button(self.frame, text="Add Customer", command=self.add_customer).grid(row=6, column=2, padx=5, pady=5)

        # Bid Entries
        self.bid_customer_name_var = StringVar()
        self.bid_price_var = StringVar()
        self.selected_services_var = StringVar()

        Label(self.frame, text="Bid Customer Name:").grid(row=7, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.bid_customer_name_var).grid(row=7, column=1, padx=5, pady=5)
        Label(self.frame, text="Bid Price:").grid(row=8, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.bid_price_var).grid(row=8, column=1, padx=5, pady=5)
        Label(self.frame, text="Selected Services (comma-separated):").grid(row=9, column=0, padx=5, pady=5)
        Entry(self.frame, textvariable=self.selected_services_var).grid(row=9, column=1, padx=5, pady=5)
        Button(self.frame, text="Add Bid", command=self.add_bid).grid(row=10, column=1, padx=5, pady=5)

        # Actions
        Button(self.frame, text="View Services", command=self.view_services).grid(row=11, column=1, padx=5, pady=5)
        Button(self.frame, text="Start Auction", command=self.start_auction).grid(row=12, column=1, padx=5, pady=5)
        Button(self.frame, text="Clear All Bids", command=self.clear_all_bids).grid(row=13, column=1, padx=5, pady=5)
        Button(self.frame, text="Clear All Data and Restart", command=self.restart_app).grid(row=14, column=1, padx=5, pady=5)

        # Service Selection for Bundles
        self.service_listbox = Listbox(self.frame, selectmode=SINGLE, width=80)  # Increased width here
        self.service_listbox.grid(row=15, column=0, columnspan=3, padx=5, pady=5)
        self.service_listbox.bind('<<ListboxSelect>>', self.on_service_select)
        self.update_service_list()

    def add_service_provider(self):
        provider_name = self.provider_name_var.get()
        if provider_name:
            provider_id = add_service_provider(provider_name)
            messagebox.showinfo("Provider Added", f"Service Provider '{provider_name}' added with ID {provider_id}.")
        else:
            messagebox.showwarning("Input Error", "Service Provider Name cannot be empty.")

    def add_service(self):
        provider_id = self.provider_id_var.get()
        service_name = self.service_name_var.get()
        quantity = self.quantity_var.get()
        initial_price = self.initial_price_var.get()

        if not provider_id or not service_name or not quantity or not initial_price:
            messagebox.showwarning("Input Error", "All fields must be filled.")
            return

        try:
            quantity = int(quantity)
            initial_price = float(initial_price)
            add_service(provider_id, service_name, quantity, initial_price)
            messagebox.showinfo("Service Added", f"Service '{service_name}' added successfully.")
            self.update_service_list()
        except ValueError:
            messagebox.showwarning("Input Error", "Invalid quantity or initial price.")

    def add_customer(self):
        customer_name = self.customer_name_var.get()
        if customer_name:
            add_customer(customer_name)
            messagebox.showinfo("Customer Added", f"Customer '{customer_name}' added successfully.")
        else:
            messagebox.showwarning("Input Error", "Customer Name cannot be empty.")

    def add_bid(self):
        customer_name = self.bid_customer_name_var.get()
        bid_price = self.bid_price_var.get()
        selected_services = self.selected_services_var.get()

        if not customer_name or not bid_price or not selected_services:
            messagebox.showwarning("Input Error", "All fields must be filled.")
            return

        try:
            bid_price = float(bid_price)
            selected_services = list(map(int, selected_services.split(',')))
            add_bid(customer_name, bid_price, selected_services)
            messagebox.showinfo("Bid Added", "Bid added successfully.")
        except ValueError:
            messagebox.showwarning("Input Error", "Invalid bid price or service IDs.")

    def view_services(self):
        services_table, headers = view_services()
        table_str = tabulate(services_table, headers=headers, tablefmt="grid")
        messagebox.showinfo("Service List", f"\n{table_str}")

    def start_auction(self):
        result = resolve_conflicts()  # This runs the auction process
        messagebox.showinfo("Auction Result", result)
        self.update_service_list()  # Refresh the service list to reflect changes


    def clear_all_bids(self):
        clear_all_bids()
        messagebox.showinfo("Bids Cleared", "All bids have been cleared.")

    def restart_app(self):
        clear_all_data()
        self.update_service_list()
        messagebox.showinfo("Data Cleared", "All data has been cleared. The application will restart.")
        self.root.quit()  # Close the current window
        self.root.destroy()  # Ensure the Tkinter main loop is stopped
        self.__init__(Tk())  # Restart the application

    def update_service_list(self):
        self.service_listbox.delete(0, END)
        services = fetch_services()
        for service_id, details in services.items():
            if details["quantity"] > 0:
                # Updated line: include the quantity of the service in the listbox entry
                self.service_listbox.insert(
                    END, 
                    f"{service_id}: {details['name']} (Price: {details['updated_price']}, Quantity: {details['quantity']})"
                )   

    def update_service_quantity(self):
        service_id = self.update_service_id_var.get()
        new_quantity = self.update_quantity_var.get()

        if not service_id or not new_quantity:
            messagebox.showwarning("Input Error", "Service ID and new quantity must be filled.")
            return

        try:
            new_quantity = int(new_quantity)
            if new_quantity < 0:
                messagebox.showwarning("Input Error", "Quantity must be a non-negative integer.")
                return

            # Update the service quantity in the database
            cursor.execute("UPDATE services SET quantity = ? WHERE id = ?", (new_quantity, service_id))
            conn.commit()

            messagebox.showinfo("Quantity Updated", f"Service ID {service_id} quantity updated to {new_quantity}.")
            self.update_service_list()  # Refresh the service list
        except ValueError:
            messagebox.showwarning("Input Error", "Invalid quantity. Please enter a valid integer.")
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to update quantity: {str(e)}")


    def on_service_select(self, event):
        selected_index = self.service_listbox.curselection()
        if selected_index:
            selected_service = self.service_listbox.get(selected_index)
            service_id = int(selected_service.split(':')[0])
            self.selected_services_var.set(f"{service_id}")

# Run the application
root = Tk()
app = AuctionApp(root)
root.mainloop()

# Close the database connection when done
conn.close()
