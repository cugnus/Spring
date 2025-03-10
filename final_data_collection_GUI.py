
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

# Global variables
saved_file_path = None
collecting_data = False
data_save_event = threading.Event()
collect_time = 10  # Default collection time in seconds
distance_buffer = []  # Buffer used in the data collection function
last_averaged_distance = None

# Global flag to control idle averaging
idle_running = True

def find_esp32_port():
    ports = [port for port in os.listdir('/dev/') if port.startswith('ttyACM') or port.startswith('ttyUSB')]
    if not ports:
        raise Exception("No serial ports found. Ensure your ESP32 is connected.")
    return f"/dev/{ports[0]}"

def save_data_to_file(data):
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Spring")
    if not os.path.exists(desktop_path):
        os.makedirs(desktop_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"spring_{timestamp}.txt"
    file_path = os.path.join(desktop_path, filename)

    metadata = f"Mass of Spring: {massSpring} kg\nDuration: {collect_time} seconds\nLast Averaged Distance: {last_averaged_distance:.2f} mm\n\n"
    try:
        with open(file_path, 'w') as file:
            file.write(metadata)
            file.write(data)
        print(f"Data saved to: {file_path}")
    except Exception as e:
        print(f"Error saving data: {e}")
        file_path = None
    return file_path

def idle_average():
    global idle_running, averaged_distance_label, last_averaged_distance
    local_buffer = []
    ser = None

    try:
        port = find_esp32_port()
        ser = serial.Serial(port, 115200, timeout=0.01)
        time.sleep(2)

        while idle_running:
            while ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                data_str = data.decode('utf-8')

                try:
                    lines = data_str.splitlines()
                    for line in lines:
                        parts = line.split()
                        if len(parts) == 2:
                            try:
                                distance = float(parts[1])
                            except ValueError:
                                continue

                            local_buffer.append(distance)
                            if len(local_buffer) > 100:
                                local_buffer.pop(0)

                            if len(local_buffer) == 100:
                                avg_distance = sum(local_buffer) / 100
                                last_averaged_distance = avg_distance
                                averaged_distance_label.after(0, 
                                    lambda avg=avg_distance: averaged_distance_label.config(text=f"Averaged Distance: {avg:.2f} mm"))

                except Exception as e:
                    print(f"Idle averaging processing error: {e}")

            time.sleep(0.01)

    except Exception as e:
        print(f"Idle averaging error: {e}")

    finally:
        if ser:
            ser.close()

def read_and_save_data_from_esp32(port, baud, text_widget, time_remaining_label):
    global collecting_data, saved_file_path, distance_buffer
    ser = None
    data_buffer = ""
    start_time = time.time()

    try:
        ser = serial.Serial(port, baud, timeout=0.01)
        print(f"Connected to ESP32 on {port}")
        time.sleep(2)

        while collecting_data:
            elapsed_time = time.time() - start_time
            remaining_time = max(0, collect_time - elapsed_time)
            time_remaining_label.after(0, lambda rt=remaining_time: time_remaining_label.config(text=f"Time Remaining: {rt:.1f} s"))
            if elapsed_time >= collect_time:
                print(f"Collection complete: {collect_time}s reached.")
                break
            while ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                data_str = data.decode('utf-8')
                data_buffer += data_str
                text_widget.insert(tk.END, data_str)
                text_widget.see(tk.END)
                try:
                    lines = data_str.splitlines()
                    for line in lines:
                        parts = line.split()
                        if len(parts) == 2:
                            distance = float(parts[1])
                            distance_buffer.append(distance)
                            if len(distance_buffer) == 20:
                                avg_distance = sum(distance_buffer) / 20
                                print(f"Averaged distance: {avg_distance:.2f} mm")
                                distance_buffer.clear()
                except ValueError:
                    continue
            time.sleep(0.01)

        saved_file_path = save_data_to_file(data_buffer)

    except Exception as e:
        print(f"Error: {e}")

    finally:
        if ser:
            ser.close()
        collecting_data = False
        data_save_event.set()
        global idle_running
        idle_running = True
        idle_thread = threading.Thread(target=idle_average, daemon=True)
        idle_thread.start()
        
def anharmonic_oscillator(t, A, omega, phi, alpha):
    return A * np.exp(-alpha * t) * np.cos(omega * t + phi)

def plot_data():
    global saved_file_path, massSpring, last_averaged_distance
    if saved_file_path is None:
        print("No data file available to plot.")
        return

    try:
        with open(saved_file_path, 'r') as file:
            data = file.readlines()

        metadata = []
        for line in data:
            if line.strip().startswith("Mass of Spring") or line.strip().startswith("Duration") or line.strip().startswith("Last Averaged Distance"):
                metadata.append(line.strip())
            else:
                break

        if metadata:
            print("\n".join(metadata))

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
            print("No valid data points available for plotting.")
            return

        # Convert lists to NumPy arrays
        times = np.array(times)
        distances = np.array(distances)

        # Check for NaNs or Infs
        if np.any(np.isnan(times)) or np.any(np.isnan(distances)):
            print("Warning: NaNs found in data.")
        if np.any(np.isinf(times)) or np.any(np.isinf(distances)):
            print("Warning: Infs found in data.")

        if times.size > 0:
            first_time = times[0]
            times = times - first_time

        eqmPosition = last_averaged_distance
        print(f"Equilibrium Position: {eqmPosition:.2f} mm")

        numberCrossings, first_crossing, last_crossing, skip_time = 0, None, None, 0.3
        for i in range(1, len(distances)):
            if last_crossing and (times[i] - last_crossing) < skip_time:
                continue
            if distances[i - 1] < eqmPosition <= distances[i]:
                numberCrossings += 1
                last_crossing = times[i]
                if first_crossing is None:
                    first_crossing = times[i]

        if numberCrossings > 1 and first_crossing and last_crossing:
            oscillationPeriod = (last_crossing - first_crossing) / (numberCrossings - 1)
            springConstant = (4 * math.pi**2 * massSpring) / (oscillationPeriod**2)
            print(f"Oscillation Period: {oscillationPeriod:.2f} s")
            print(f"Spring Constant: {springConstant:.2f} N/m")
        else:
            print("Not enough crossings to calculate oscillation period and spring constant.")
            oscillationPeriod = None
            springConstant = None

        plt.figure(figsize=(10, 6))
        plt.plot(times, distances, label="Distance vs Time")
        plt.axhline(y=eqmPosition, color='r', linestyle='--', label="Equilibrium Position")
        plt.xlabel('Time (s)')
        plt.ylabel('Distance (mm)')

        if oscillationPeriod and springConstant:
            title = f'Oscillation\nPeriod: {oscillationPeriod:.2f}s, Spring Constant: {springConstant:.2f}N/m'
            subtitle = f'\nFile: {os.path.basename(saved_file_path)}'
            plt.title(f'{title}\n{subtitle}')
        else:
            plt.title('Oscillation Data')

        plt.legend()
        plt.grid()

        metadata_text = '\n'.join(metadata)
        plt.figtext(0.1, 0.01, metadata_text, wrap=True, horizontalalignment='left', fontsize=8)

        # Fit anharmonic oscillator model
        try:
            popt, _ = curve_fit(anharmonic_oscillator, times, distances, p0=[max(distances), 2*np.pi/oscillationPeriod if oscillationPeriod else 1, 0, 0.1])
        except Exception as e:
            print(f"Error during curve fitting: {e}")
            return

        # Create new figure for the oscillator model and its derivatives
        fig2, ax2 = plt.subplots(figsize=(10, 6))
        
        # Plot the fitted model
        ax2.plot(times, anharmonic_oscillator(times, *popt), label="Anharmonic Oscillator Model", color='blue')
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Distance (mm)', color='blue')
        ax2.tick_params(axis='y', labelcolor='blue')

        # Calculate and plot the first derivative (speed)
        ax2_2 = ax2.twinx()
        speed = np.gradient(anharmonic_oscillator(times, *popt), times)
        ax2_2.plot(times, speed, label="Speed", color='green')
        ax2_2.set_ylabel('Speed (mm/s)', color='green')
        ax2_2.tick_params(axis='y', labelcolor='green')

        # Calculate and plot the second derivative (acceleration)
        ax2_3 = ax2.twinx()
        ax2_3.spines['right'].set_position(('outward', 60))
        acceleration = np.gradient(speed, times)
        ax2_3.plot(times, acceleration, label="Acceleration", color='red')
        ax2_3.set_ylabel('Acceleration (mm/s²)', color='red')
        ax2_3.tick_params(axis='y', labelcolor='red')

        ax2.set_title("Anharmonic Oscillator Model and Derivatives")
        ax2.legend(loc='upper left')
        ax2_2.legend(loc='upper right')
        ax2_3.legend(loc='lower right')

        ax2.grid()
        plt.tight_layout()
        plt.show()

    except Exception as e:
        print(f"Error while plotting data: {e}")

def start_data_collection(text_widget, time_remaining_label):
    global collecting_data, data_save_event, idle_running
    idle_running = False
    collecting_data = True
    data_save_event.clear()
    
    time.sleep(10)

    ESP32_PORT = find_esp32_port()
    BAUD_RATE = 115200
    thread = threading.Thread(target=read_and_save_data_from_esp32, args=(ESP32_PORT, BAUD_RATE, text_widget, time_remaining_label))
    thread.start()

def stop_data_collection():
    global collecting_data
    collecting_data = False
    print("Manual stop requested.")

def plot_collected_data():
    global data_save_event
    data_save_event.wait()
    plot_data()

def retrieve_and_analyze_file():
    global saved_file_path
    initial_dir = os.path.join(os.path.expanduser("~"), "Desktop", "Spring")
    file_path = filedialog.askopenfilename(initialdir=initial_dir,
                                           title="Select file for analysis",
                                           filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
    if file_path:
        saved_file_path = file_path
        plot_data()

def main():
    global massSpring, collect_time, averaged_distance_label, idle_running

    root = tk.Tk()
    root.title("ESP32 Data Logger")

    frame = tk.Frame(root, padx=10, pady=10)
    frame.pack()

    text_widget = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=60, height=20)
    text_widget.grid(row=0, column=0, columnspan=4)

    time_remaining_label = tk.Label(frame, text="Time Remaining: 0.0 s")
    time_remaining_label.grid(row=6, column=0, columnspan=4, pady=(10, 0))
    time_remaining_label.config(fg="red", font=("Arial", 12))

    tk.Button(frame, text="Connect & Collect", command=lambda: start_data_collection(text_widget, time_remaining_label)).grid(row=1, column=0)
    tk.Button(frame, text="Stop Collection", command=stop_data_collection).grid(row=1, column=1)
    tk.Button(frame, text="Plot Data", command=plot_collected_data).grid(row=1, column=2)
    tk.Button(frame, text="Exit", command=root.quit).grid(row=1, column=3)
    tk.Button(frame, text="Retrieve & Analyze File", command=retrieve_and_analyze_file).grid(row=5, column=0, columnspan=4, pady=(10,0))

    tk.Label(frame, text="Mass of Spring (kg):").grid(row=2, column=0, pady=(10, 0))
    mass_entry = tk.Entry(frame, width=10)
    mass_entry.grid(row=2, column=1, pady=(10, 0))
    mass_entry.insert(0, str(massSpring))

    def update_mass():
        global massSpring
        try:
            massSpring = float(mass_entry.get())
            print(f"Updated massSpring to {massSpring:.3f} kg")
        except ValueError:
            print("Invalid mass value. Please enter a numeric value.")

    tk.Button(frame, text="Update Mass", command=update_mass).grid(row=2, column=2, pady=(10, 0))

    tk.Label(frame, text="Collection Time (s):").grid(row=3, column=0, pady=(10, 0))
    time_entry = tk.Entry(frame, width=10)
    time_entry.grid(row=3, column=1, pady=(10, 0))
    time_entry.insert(0, str(collect_time))

    def update_time():
        global collect_time
        try:
            collect_time = int(time_entry.get())
            print(f"Updated collection time to {collect_time}s")
        except ValueError:
            print("Invalid time value. Please enter a valid integer.")

    tk.Button(frame, text="Update Time", command=update_time).grid(row=3, column=2, pady=(10, 0))

    averaged_distance_label = tk.Label(frame, text="Averaged Distance: 0.00 mm")
    averaged_distance_label.grid(row=4, column=0, columnspan=4, pady=(10, 0))
    averaged_distance_label.config(fg="blue", font=("Arial", 12))

    idle_running = True
    idle_thread = threading.Thread(target=idle_average, daemon=True)
    idle_thread.start()

    root.mainloop()

if __name__ == "__main__":
    main()
