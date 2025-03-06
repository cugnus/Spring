# Import necessary libraries
# These are pre-written code modules that provide useful functions for our program.
import serial  # Used to communicate with the ESP32 over a serial connection (like USB).
import time  # Provides functions to handle time-related tasks, like waiting.
import os  # Helps interact with the operating system, like creating files or folders.
from datetime import datetime  # Used to get the current date and time for saving files.
import threading  # Allows running multiple tasks at the same time (e.g., collecting data while the program continues).
import matplotlib.pyplot as plt  # Used to create graphs and plots.

# User-configurable variables
# These are values that you can change to suit your needs.
massSpring = 0.609  # The mass of the spring in kilograms (kg).
collect_time = 10  # How long the program will collect data, in seconds.

# Global variables
# These are variables that can be accessed from anywhere in the program.
saved_file_path = None  # This will store the location of the saved data file.
data_save_event = threading.Event()  # Used to signal when data saving is complete.

# Function to find the ESP32's serial port
# The ESP32 is a microcontroller, and this function finds where it's connected to the computer.
def find_esp32_port():
    # Look for all serial ports that start with 'ttyACM' or 'ttyUSB' (common names for ESP32 connections).
    ports = [port for port in os.listdir('/dev/') if port.startswith('ttyACM') or port.startswith('ttyUSB')]
    if not ports:  # If no ports are found, raise an error.
        raise Exception("No serial ports found. Ensure your ESP32 is connected.")
    return f"/dev/{ports[0]}"  # Return the first port found.

# Function to save the collected data to a file
# This function takes the data as input and saves it to a file on your desktop.
def save_data_to_file(data):
    # Create a folder on the desktop called "Spring" to store the data.
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Spring")
    os.makedirs(desktop_path, exist_ok=True)  # Create the folder if it doesn't already exist.
    
    # Get the current date and time to create a unique filename.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(desktop_path, f"spring_{timestamp}.txt")
    
    # Add some metadata to the file (information about the experiment).
    metadata = f"Mass of Spring: {massSpring} kg\nDuration: {collect_time} seconds\n\n"
    
    try:
        # Open the file in write mode and save the metadata and data.
        with open(file_path, 'w') as file:
            file.write(metadata + data)
        print(f"Data saved to: {file_path}")
    except Exception as e:  # If something goes wrong, print an error message.
        print(f"Error saving data: {e}")
        file_path = None  # Set the file path to None if saving fails.
    return file_path  # Return the path where the file was saved.

# Function to read data from the ESP32 and save it
# This function connects to the ESP32, collects data, and saves it to a file.
def read_and_save_data():
    global saved_file_path  # Use the global variable to store the file path.
    try:
        # Find the ESP32's serial port and connect to it.
        port = find_esp32_port()
        ser = serial.Serial(port, 115200, timeout=0.01)  # Set up the serial connection.
        time.sleep(2)  # Wait 2 seconds to allow the connection to stabilize.
        
        start_time = time.time()  # Record the start time of data collection.
        data_buffer = ""  # Create an empty string to store the collected data.
        
        # Collect data for the specified duration (collect_time).
        while time.time() - start_time < collect_time:
            # Check if there is data available from the ESP32.
            while ser.in_waiting > 0:
                # Read the data and decode it from bytes to a string.
                data_str = ser.read(ser.in_waiting).decode('utf-8')
                data_buffer += data_str  # Add the new data to the buffer.
            time.sleep(0.01)  # Wait a short time before checking for more data.
        
        # Save the collected data to a file.
        saved_file_path = save_data_to_file(data_buffer)
    except Exception as e:  # If something goes wrong, print an error message.
        print(f"Error: {e}")
    finally:
        ser.close()  # Close the serial connection.
        data_save_event.set()  # Signal that data saving is complete.

# Function to plot the collected data
# This function reads the saved data and creates a graph.
def plot_data():
    global saved_file_path, massSpring  # Use the global variables for the file path and spring mass.
    if saved_file_path is None:  # If no file was saved, print a message and exit.
        print("No data file available to plot.")
        return
    try:
        # Open the saved file and read the data.
        with open(saved_file_path, 'r') as file:
            data = file.readlines()
        
        # Create empty lists to store time and distance values.
        times, distances = [], []
        
        # Loop through each line in the file.
        for line in data:
            parts = line.strip().split(" ")  # Split the line into time and distance values.
            if len(parts) == 2:  # Check if the line contains two values.
                try:
                    # Convert the values to numbers and add them to the lists.
                    times.append(float(parts[0]))
                    distances.append(float(parts[1]))
                except ValueError:  # Skip lines that can't be converted to numbers.
                    continue
        
        if not distances:  # If no valid data was found, print a message and exit.
            print("No valid data points available for plotting.")
            return
        
        # Adjust the time values so they start at 0.
        times = [t - times[0] for t in times[1:]]
        distances = distances[1:]  # Remove the first distance value to match the adjusted times.
        
        # Calculate the equilibrium position (average distance).
        eqmPosition = sum(distances) / len(distances)
        print(f"Equilibrium Position: {eqmPosition:.2f} mm")
        
        # Count oscillations by detecting zero crossings.
        oscillation_count = 0
        previous_distance = distances[0] - eqmPosition  # Subtract equilibrium to center the data.
        for i in range(1, len(distances)):
            current_distance = distances[i] - eqmPosition
            # Detect when the spring crosses the equilibrium position (zero crossing).
            if previous_distance < 0 and current_distance >= 0:
                oscillation_count += 0.5  # Half oscillation (moving upward).
            elif previous_distance > 0 and current_distance <= 0:
                oscillation_count += 0.5  # Half oscillation (moving downward).
            previous_distance = current_distance
        
        # Each full oscillation consists of two zero crossings (upward and downward).
        full_oscillations = int(oscillation_count // 1)
        print(f"Number of full oscillations: {full_oscillations}")
        
        # Create a plot using matplotlib.
        fig, ax = plt.subplots()
        ax.plot(times, distances, label="Spring Motion")  # Plot the distance over time.
        ax.axhline(y=eqmPosition, color='r', linestyle='--', label="Equilibrium Position")  # Add a horizontal line for the equilibrium position.
        ax.set_xlabel("Time (s)")  # Label the x-axis.
        ax.set_ylabel("Distance (mm)")  # Label the y-axis.
        ax.set_title("Spring Motion Over Time")  # Add a title to the plot.
        ax.legend()  # Show the legend.
        plt.show()  # Display the plot.
    except Exception as e:  # If something goes wrong, print an error message.
        print(f"Plotting error: {e}")

# Main function to run the program
# This is the starting point of the program.
def main():
    input("Press Enter to start data collection...")  # Wait for the user to press Enter.
    data_thread = threading.Thread(target=read_and_save_data)  # Create a new thread to collect data.
    data_thread.start()  # Start the data collection thread.
    data_thread.join()  # Wait for the data collection to finish.
    input("Press Enter to plot the data...")  # Wait for the user to press Enter again.
    plot_data()  # Plot the collected data.

# Run the program
# This line ensures the program starts when you run the script.
if __name__ == "__main__":
    main()
