# Importing necessary libraries
import serial  # For communicating with the serial port (ESP32)
import time  # For handling time-related tasks (e.g., delays)
import os  # For file and directory operations (e.g., saving files)
from datetime import datetime  # For working with dates and times (e.g., creating unique filenames)
import threading  # For handling multiple tasks at once (e.g., collecting data while performing other tasks)
import matplotlib.pyplot as plt  # For plotting data visually
import tkinter as tk  # For creating the graphical user interface (GUI)
from tkinter import messagebox  # For showing pop-up messages (success or error alerts)

# User-configurable variables
massSpring = 0.609  # The mass of the spring in kilograms (used for data metadata)
collect_time = 10  # The duration (in seconds) for which data will be collected

# Global variables to hold data and control events
saved_file_path = None  # Will store the path of the saved data file
data_save_event = threading.Event()  # Event used to signal when data is saved
stop_event = threading.Event()  # Event used to signal when data collection should stop

# Function to find the ESP32 serial port
def find_esp32_port():
    # Looks for devices in /dev/ that start with 'ttyACM' or 'ttyUSB' (common names for serial ports)
    ports = [port for port in os.listdir('/dev/') if port.startswith('ttyACM') or port.startswith('ttyUSB')]
    
    # If no serial ports are found, raise an error
    if not ports:
        raise Exception("No serial ports found. Ensure your ESP32 is connected.")
    # Return the path to the first found serial port
    return f"/dev/{ports[0]}"

# Function to save collected data to a text file
def save_data_to_file(data):
    # Creates a path to save the file on the user's Desktop, inside a folder named 'Spring'
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Spring")
    os.makedirs(desktop_path, exist_ok=True)  # Creates the folder if it doesn't exist

    # Creates a unique filename based on the current date and time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(desktop_path, f"spring_{timestamp}.txt")

    # Metadata that will be written to the file (information about the spring and data collection)
    metadata = f"Mass of Spring: {massSpring} kg\nDuration: {collect_time} seconds\n\n"

    try:
        # Opens the file in write mode and saves the data and metadata
        with open(file_path, 'w') as file:
            file.write(metadata + data)
        # Show a success message when the file is saved
        messagebox.showinfo("Success", f"Data saved to: {file_path}")
    except Exception as e:
        # If there's an error while saving, show an error message
        messagebox.showerror("Error", f"Error saving data: {e}")
        file_path = None  # Set the file path to None in case of error
    # Return the path of the saved file (or None if there was an error)
    return file_path

# Function to read data from the ESP32 and save it to a file
def read_and_save_data():
    global saved_file_path
    stop_event.clear()  # Clears any previous stop signal

    try:
        # Find the ESP32 serial port and open it for communication
        port = find_esp32_port()
        ser = serial.Serial(port, 115200, timeout=0.01)  # Set up the serial connection
        time.sleep(2)  # Wait for the connection to establish
        start_time = time.time()  # Record the start time of data collection
        data_buffer = ""  # Initialize an empty string to store incoming data

        # Collect data until the specified collection time is reached
        while time.time() - start_time < collect_time:
            if stop_event.is_set():  # If a stop event is triggered, exit the loop
                break
            # Read any available data from the serial port
            while ser.in_waiting > 0:
                data_str = ser.read(ser.in_waiting).decode('utf-8')  # Read and decode the data
                data_buffer += data_str  # Add the new data to the buffer
            time.sleep(0.01)  # Sleep briefly to prevent excessive CPU usage

        # Save the collected data to a file
        saved_file_path = save_data_to_file(data_buffer)
    except Exception as e:
        # Show an error message if there's an issue while reading data
        messagebox.showerror("Error", f"Error: {e}")
    finally:
        # Close the serial connection and set the data save event
        ser.close()
        data_save_event.set()

# Function to plot the collected data
def plot_data():
    global saved_file_path, massSpring
    if saved_file_path is None:
        messagebox.showwarning("Warning", "No data file available to plot.")
        return

    try:
        # Open the saved data file and read its contents
        with open(saved_file_path, 'r') as file:
            data = file.readlines()

        # Prepare lists to hold time and distance data
        times, distances = [], []
        for line in data:
            parts = line.strip().split(" ")  # Split each line into components
            if len(parts) == 2:
                try:
                    # Try to convert the time and distance to floats
                    times.append(float(parts[0]))
                    distances.append(float(parts[1]))
                except ValueError:
                    continue  # Skip lines with invalid data

        # If no valid distance data was found, show a warning
        if not distances:
            messagebox.showwarning("Warning", "No valid data points available for plotting.")
            return
        
        # Normalize times (set the first time to 0)
        times = [t - times[0] for t in times[1:]]
        distances = distances[1:]

        # Calculate the equilibrium position (average position of the spring)
        eqmPosition = sum(distances) / len(distances)

        # Create a plot using Matplotlib
        fig, ax = plt.subplots()
        ax.plot(times, distances, label="Spring Motion")  # Plot the motion of the spring
        ax.axhline(y=eqmPosition, color='r', linestyle='--', label="Equilibrium Position")  # Draw a line for equilibrium position
        ax.set_xlabel("Time (s)")  # Label for the x-axis
        ax.set_ylabel("Distance (mm)")  # Label for the y-axis
        ax.set_title("Spring Motion Over Time")  # Title for the plot
        ax.legend()  # Show the legend
        plt.show()  # Display the plot
    except Exception as e:
        # If an error occurs during plotting, show an error message
        messagebox.showerror("Error", f"Plotting error: {e}")

# Function to start data collection in a separate thread
def start_data_collection():
    data_thread = threading.Thread(target=read_and_save_data)  # Create a thread to run the data collection function
    data_thread.start()  # Start the thread

# Function to stop data collection early
def stop_data_collection():
    stop_event.set()  # Signal the collection to stop

# Function to create the graphical user interface (GUI)
def create_gui():
    root = tk.Tk()  # Create the main window
    root.title("ESP32 Spring Data Logger")  # Set the title of the window
    root.geometry("300x200")  # Set the size of the window

    # Create a button to start data collection
    btn_start = tk.Button(root, text="Start Data Collection", command=start_data_collection)
    btn_start.pack(pady=10)  # Add the button to the window with some padding

    # Create a button to stop data collection early
    btn_stop = tk.Button(root, text="Stop Collection Early", command=stop_data_collection)
    btn_stop.pack(pady=10)

    # Create a button to plot the collected data
    btn_plot = tk.Button(root, text="Plot Data", command=plot_data)
    btn_plot.pack(pady=10)
    
    # Start the GUI event loop
    root.mainloop()

# This runs when the script is executed directly (not imported as a module)
if __name__ == "__main__":
    create_gui()  # Call the function to create and start the GUI
