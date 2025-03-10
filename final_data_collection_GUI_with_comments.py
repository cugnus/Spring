# Import necessary libraries for serial communication, timing, GUI, and data processing
import serial
import time
import os
from datetime import datetime
import tkinter as tk
from tkinter import scrolledtext, filedialog
import threading
import matplotlib.pyplot as plt
import math
import numpy as np
from scipy.optimize import curve_fit

# Mass of the spring (default value in kg)
massSpring = 0.609

# Global variables used throughout the program
saved_file_path = None  # Holds the path of the saved data file
collecting_data = False  # Flag to control data collection process
data_save_event = threading.Event()  # Used to signal when data collection is complete
collect_time = 10  # Default time for data collection in seconds
distance_buffer = []  # Buffer to hold the collected distance values
last_averaged_distance = None  # Holds the last averaged distance

# Flag to control the idle averaging process
idle_running = True

# Function to find the serial port of the ESP32 device
def find_esp32_port():
    ports = [port for port in os.listdir('/dev/') if port.startswith('ttyACM') or port.startswith('ttyUSB')]
    if not ports:
        raise Exception("No serial ports found. Ensure your ESP32 is connected.")
    return f"/dev/{ports[0]}"  # Returns the path of the first available serial port

# Function to save collected data to a file on the Desktop
def save_data_to_file(data):
    # Set the path where the data will be saved
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Spring")
    if not os.path.exists(desktop_path):
        os.makedirs(desktop_path)  # Create the folder if it doesn't exist
    
    # Create a timestamp for the file name to ensure unique files are saved
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"spring_{timestamp}.txt"  # Name of the file
    file_path = os.path.join(desktop_path, filename)  # Full path of the file

    # Metadata to be saved along with the data
    metadata = f"Mass of Spring: {massSpring} kg\nDuration: {collect_time} seconds\nLast Averaged Distance: {last_averaged_distance:.2f} mm\n\n"
    
    try:
        # Open the file in write mode and save both metadata and data
        with open(file_path, 'w') as file:
            file.write(metadata)
            file.write(data)  # Save the actual data
        print(f"Data saved to: {file_path}")  # Confirmation message
    except Exception as e:
        print(f"Error saving data: {e}")  # If there is an error during saving
        file_path = None
    return file_path  # Return the file path

# Function to continuously average the distance readings when the system is idle
def idle_average():
    global idle_running, averaged_distance_label, last_averaged_distance
    local_buffer = []  # Temporary buffer to hold distance readings
    ser = None  # Initialize serial connection

    try:
        # Find the correct serial port and establish connection
        port = find_esp32_port()
        ser = serial.Serial(port, 115200, timeout=0.01)  # Open serial connection with specified port and baud rate
        time.sleep(2)  # Wait for ESP32 to initialize

        while idle_running:
            while ser.in_waiting > 0:  # If there is data to read
                data = ser.read(ser.in_waiting)  # Read all available data
                data_str = data.decode('utf-8')  # Convert the data to a string

                try:
                    # Split the data into lines for easier processing
                    lines = data_str.splitlines()
                    for line in lines:
                        parts = line.split()
                        if len(parts) == 2:  # Expecting two parts in each line: time and distance
                            try:
                                distance = float(parts[1])  # Convert the second part (distance) to a float
                            except ValueError:
                                continue  # Skip if there is an error converting to float

                            local_buffer.append(distance)  # Add the distance to the buffer
                            if len(local_buffer) > 100:  # Keep the buffer size manageable
                                local_buffer.pop(0)  # Remove the oldest value if the buffer exceeds 100

                            if len(local_buffer) == 100:  # When buffer reaches 100 readings, calculate the average
                                avg_distance = sum(local_buffer) / 100  # Calculate average distance
                                last_averaged_distance = avg_distance  # Update the last averaged distance
                                # Update the label on the GUI to show the averaged distance
                                averaged_distance_label.after(0, lambda avg=avg_distance: averaged_distance_label.config(text=f"Averaged Distance: {avg:.2f} mm"))

                except Exception as e:
                    print(f"Idle averaging processing error: {e}")

            time.sleep(0.01)  # Small delay to avoid overwhelming the system

    except Exception as e:
        print(f"Idle averaging error: {e}")

    finally:
        if ser:
            ser.close()  # Close the serial connection

# Function to read data from the ESP32 and save it to a file
def read_and_save_data_from_esp32(port, baud, text_widget, time_remaining_label):
    global collecting_data, saved_file_path, distance_buffer
    ser = None  # Initialize serial connection
    data_buffer = ""  # Buffer to hold collected data
    start_time = time.time()  # Get the start time for data collection

    try:
        # Open the serial port with the specified parameters
        ser = serial.Serial(port, baud, timeout=0.01)
        print(f"Connected to ESP32 on {port}")
        time.sleep(2)

        while collecting_data:
            # Calculate the elapsed time and update the remaining time
            elapsed_time = time.time() - start_time
            remaining_time = max(0, collect_time - elapsed_time)
            time_remaining_label.after(0, lambda rt=remaining_time: time_remaining_label.config(text=f"Time Remaining: {rt:.1f} s"))
            if elapsed_time >= collect_time:  # Stop collection once the set time is reached
                print(f"Collection complete: {collect_time}s reached.")
                break
            while ser.in_waiting > 0:  # If there is data available from the serial port
                data = ser.read(ser.in_waiting)  # Read all available data
                data_str = data.decode('utf-8')  # Convert data to a string
                data_buffer += data_str  # Append the data to the buffer
                text_widget.insert(tk.END, data_str)  # Display the data in the text widget
                text_widget.see(tk.END)  # Scroll the text widget to show the latest data

                try:
                    lines = data_str.splitlines()  # Split the data into lines
                    for line in lines:
                        parts = line.split()  # Split each line into its parts
                        if len(parts) == 2:  # Expecting two parts: time and distance
                            distance = float(parts[1])  # Convert the second part to a float
                            distance_buffer.append(distance)  # Add to the distance buffer
                            if len(distance_buffer) == 20:  # When 20 readings are collected, calculate average
                                avg_distance = sum(distance_buffer) / 20  # Calculate the average distance
                                print(f"Averaged distance: {avg_distance:.2f} mm")
                                distance_buffer.clear()  # Clear the buffer for the next set of readings
                except ValueError:
                    continue  # Skip lines that do not have valid data

            time.sleep(0.01)  # Small delay to avoid overwhelming the system

        # Save the collected data to a file
        saved_file_path = save_data_to_file(data_buffer)

    except Exception as e:
        print(f"Error: {e}")

    finally:
        if ser:
            ser.close()  # Close the serial connection
        collecting_data = False  # Stop the data collection process
        data_save_event.set()  # Signal that the data collection is complete
        global idle_running
        idle_running = True
        # Start the idle averaging process in a separate thread
        idle_thread = threading.Thread(target=idle_average, daemon=True)
        idle_thread.start()

# Function to model the motion of an anharmonic oscillator (for curve fitting)
def anharmonic_oscillator(t, A, omega, phi, alpha):
    return A * np.exp(-alpha * t) * np.cos(omega * t + phi)

# Function to plot the collected data
def plot_data():
    global saved_file_path, massSpring, last_averaged_distance
    if saved_file_path is None:
        print("No data file available to plot.")
        return

    try:
        # Read the saved data file
        with open(saved_file_path, 'r') as file:
            data = file.readlines()

        metadata = []
        # Extract metadata (information about the spring mass, duration, and last averaged distance)
        for line in data:
            if line.strip().startswith("Mass of Spring") or line.strip().startswith("Duration") or line.strip().startswith("Last Averaged Distance"):
                metadata.append(line.strip())  # Add relevant metadata lines

        if metadata:
            print("\n".join(metadata))  # Print metadata

        times, distances = [], []
        # Parse the time and distance values from the data
        for line in data:
            parts = line.split()
            if len(parts) == 2:
                try:
                    time_value = float(parts[0])  # Convert time to float
                    distance_value = float(parts[1])  # Convert distance to float
                    times.append(time_value)
                    distances.append(distance_value)
                except ValueError:
                    continue  # Skip any lines with invalid data

        if not times or not distances:
            print("No valid data to plot.")
            return

        # Convert time list to numpy array for curve fitting
        times = np.array(times)

        # Fit the data to an anharmonic oscillator model (optional)
        popt, _ = curve_fit(anharmonic_oscillator, times, distances, maxfev=10000)
        A, omega, phi, alpha = popt

        print(f"Fitted parameters: A = {A}, omega = {omega}, phi = {phi}, alpha = {alpha}")

        # Plot the collected data and the fitted curve
        plt.figure()
        plt.plot(times, distances, label="Collected Data")
        plt.plot(times, anharmonic_oscillator(times, *popt), 'r--', label="Fitted Curve")
        plt.xlabel('Time (s)')
        plt.ylabel('Distance (mm)')
        plt.legend()
        plt.show()

    except Exception as e:
        print(f"Error plotting data: {e}")

# Setting up the GUI using Tkinter
root = tk.Tk()
root.title("Spring Data Collection")

# Text widget to display serial data
text_widget = scrolledtext.ScrolledText(root, width=50, height=15)
text_widget.grid(row=0, column=0, padx=10, pady=10)

# Label to show the remaining time for data collection
time_remaining_label = tk.Label(root, text="Time Remaining: 0.0 s", font=("Arial", 12))
time_remaining_label.grid(row=1, column=0, padx=10, pady=10)

# Label to display the averaged distance
averaged_distance_label = tk.Label(root, text="Averaged Distance: N/A", font=("Arial", 12))
averaged_distance_label.grid(row=2, column=0, padx=10, pady=10)

# Function to start data collection when the button is pressed
def start_data_collection():
    global collecting_data, data_save_event
    port = find_esp32_port()  # Find the serial port of the ESP32
    collecting_data = True
    data_save_event.clear()  # Reset the event to track data collection status
    # Start data collection in a separate thread to avoid blocking the GUI
    collection_thread = threading.Thread(target=read_and_save_data_from_esp32, args=(port, 115200, text_widget, time_remaining_label), daemon=True)
    collection_thread.start()

# Function to stop data collection early
def stop_data_collection():
    global collecting_data
    collecting_data = False
    data_save_event.set()  # Signal that the data collection is complete

# Button to start data collection
start_button = tk.Button(root, text="Connect & Collect", command=start_data_collection, font=("Arial", 12))
start_button.grid(row=3, column=0, padx=10, pady=10)

# Button to stop data collection
stop_button = tk.Button(root, text="Stop Collection", command=stop_data_collection, font=("Arial", 12))
stop_button.grid(row=4, column=0, padx=10, pady=10)

# Button to plot the collected data
plot_button = tk.Button(root, text="Plot Data", command=plot_data, font=("Arial", 12))
plot_button.grid(row=5, column=0, padx=10, pady=10)

# Run the Tkinter event loop
root.mainloop()
