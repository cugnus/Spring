# basic_switchable_gui

import serial
import time
import os
from datetime import datetime
import threading
import matplotlib.pyplot as plt

# GUI-related imports (only used if GUI is enabled)
USE_GUI = True  # Set to True to enable GUI, False for non-GUI mode
if USE_GUI:
    import tkinter as tk
    from tkinter import messagebox

# User-configurable variables
massSpring = 0.609  # Mass of the spring in kg
collect_time = 10  # Data collection time in seconds

# Global variables
saved_file_path = None
data_save_event = threading.Event()
stop_event = threading.Event()

def find_esp32_port():
    ports = [port for port in os.listdir('/dev/') if port.startswith('ttyACM') or port.startswith('ttyUSB')]
    if not ports:
        raise Exception("No serial ports found. Ensure your ESP32 is connected.")
    return f"/dev/{ports[0]}"

def notify_user(title, message, error=False):
    """Handles notifications via GUI messagebox or prints to the terminal."""
    if USE_GUI:
        if error:
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)
    else:
        print(f"[{title}] {message}")

def save_data_to_file(data):
    global saved_file_path
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Spring")
    os.makedirs(desktop_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(desktop_path, f"spring_{timestamp}.txt")
    metadata = f"Mass of Spring: {massSpring} kg\nDuration: {collect_time} seconds\n\n"

    try:
        with open(file_path, 'w') as file:
            file.write(metadata + data)
        notify_user("Success", f"Data saved to: {file_path}")
    except Exception as e:
        notify_user("Error", f"Error saving data: {e}", error=True)
        file_path = None
    return file_path

def read_and_save_data():
    global saved_file_path
    stop_event.clear()
    try:
        port = find_esp32_port()
        ser = serial.Serial(port, 115200, timeout=0.01)
        time.sleep(2)  # Allow time for connection
        start_time = time.time()
        data_buffer = ""

        notify_user("Info", "Collecting data...")

        while time.time() - start_time < collect_time:
            if stop_event.is_set():
                break
            while ser.in_waiting > 0:
                data_str = ser.read(ser.in_waiting).decode('utf-8')
                data_buffer += data_str
            time.sleep(0.01)
        
        saved_file_path = save_data_to_file(data_buffer)
        notify_user("Info", "Data collection complete.")

    except Exception as e:
        notify_user("Error", f"Error: {e}", error=True)
    finally:
        if 'ser' in locals():
            ser.close()
        data_save_event.set()

def plot_data():
    global saved_file_path
    if saved_file_path is None:
        notify_user("Warning", "No data file available to plot.")
        return

    try:
        with open(saved_file_path, 'r') as file:
            data = file.readlines()
        times, distances = [], []
        for line in data:
            parts = line.strip().split(" ")
            if len(parts) == 2:
                try:
                    times.append(float(parts[0]))
                    distances.append(float(parts[1]))
                except ValueError:
                    continue
        if not distances:
            notify_user("Warning", "No valid data points available for plotting.")
            return
        times = [t - times[0] for t in times[1:]]
        distances = distances[1:]
        eqmPosition = sum(distances) / len(distances)
        
        fig, ax = plt.subplots()
        ax.plot(times, distances, label="Spring Motion")
        ax.axhline(y=eqmPosition, color='r', linestyle='--', label="Equilibrium Position")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Distance (mm)")
        ax.set_title("Spring Motion Over Time")
        ax.legend()
        plt.show()
    except Exception as e:
        notify_user("Error", f"Plotting error: {e}", error=True)

def start_data_collection():
    threading.Thread(target=read_and_save_data).start()

def stop_data_collection():
    stop_event.set()

# GUI Setup (only runs if USE_GUI is True)
def create_gui():
    root = tk.Tk()
    root.title("ESP32 Spring Data Logger")
    root.geometry("300x200")

    btn_start = tk.Button(root, text="Start Data Collection", command=start_data_collection)
    btn_start.pack(pady=10)

    btn_stop = tk.Button(root, text="Stop Collection Early", command=stop_data_collection)
    btn_stop.pack(pady=10)

    btn_plot = tk.Button(root, text="Plot Data", command=plot_data)
    btn_plot.pack(pady=10)
    
    root.mainloop()

if __name__ == "__main__":
    if USE_GUI:
        create_gui()
    else:
        print("Running without GUI... Starting data collection automatically.")
        read_and_save_data()

        # Ask the user if they want to plot the data
        while True:
            user_input = input("Do you want to plot the collected data? (y/n): ").strip().lower()
            if user_input == 'y':
                plot_data()
                break
            elif user_input == 'n':
                print("Exiting without plotting.")
                break
            else:
                print("Invalid input. Please enter 'y' or 'n'.")
