#!/usr/bin/env python3
import struct
import time
import os
import sys
import subprocess
import glob
import pyautogui

class AdvancedGamepadReader:
    def __init__(self, device_path='/dev/input/js0', axis_count=4, output_type='keyboard', jump_button='A'):
        self.device_path = device_path
        self.axis_count = axis_count
        self.axis_values = [0.0] * axis_count
        self.output_type = output_type  # 'keyboard' or 'virtual_joystick'
        self.jump_button = jump_button  # 'A', 'B', 'X', 'Y' for virtual joystick, 'space' for keyboard

        # Initialize virtual gamepad if selected
        if self.output_type == 'virtual_joystick':
            try:
                import vgamepad
                self.vgamepad = vgamepad
                self.gamepad = vgamepad.VX360Gamepad()

                # Map button names to vgamepad constants
                self.button_map = {
                    'A': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A,
                    'B': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B,
                    'X': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X,
                    'Y': vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y
                }

                # Map button names to keyboard keys
                self.keyboard_jump_map = {
                    'A': 'space',  # Default space for A
                    'B': 'b',
                    'X': 'x',
                    'Y': 'y'
                }

                print(f"Virtual gamepad initialized with jump button: {jump_button}")
            except ImportError:
                print("vgamepad module not found. Falling back to keyboard output.")
                self.output_type = 'keyboard'
                self.vgamepad = None
                self.gamepad = None
        else:
            self.vgamepad = None
            self.gamepad = None
            # Map button names to keyboard keys for keyboard output
            self.keyboard_jump_map = {
                'A': 'space',  # Default space for A
                'B': 'b',
                'X': 'x',
                'Y': 'y'
            }

        # Configurable timing variables
        self.walking_hold_time = 0.5  # seconds to hold walking status
        self.flamingo_hold_time = 0.5  # seconds to detect flamingo stance
        self.jump_display_time = 1.0  # seconds to display jump status
        self.user_absent_time = 1.0  # seconds to detect user absence

        # Configurable detection threshold (5% of range)
        self.jump_absence_threshold_percent = 0.05  # 5% threshold

        # State tracking variables
        self.current_status = "Standing"
        self.previous_status = "Standing"  # Track previous status for callbacks
        self.status_start_time = time.time()
        self.last_walking_pattern_time = 0.0
        self.last_detected_side = None

        # Detection state tracking
        self.one_foot_start_time = 0.0
        self.both_sides_zero_start_time = 0.0
        self.pre_jump_status = "Standing"

    # Clean callback functions using the configured jump button
    def on_status_standing(self):
        """Called once when status changes to Standing"""
        if self.output_type == 'keyboard':
            pyautogui.keyUp('w')
        else:  # virtual_joystick
            if self.gamepad:
                # Reset right analog stick to center
                self.gamepad.left_joystick(0, 0)
                self.gamepad.update()

    def on_status_walking(self):
        """Called once when status changes to Walking"""
        if self.output_type == 'keyboard':
            pyautogui.keyDown('w')
        else:  # virtual_joystick
            if self.gamepad:
                # Move right analog stick up
                self.gamepad.left_joystick(0, -32767)  # x=0, y=full up
                self.gamepad.update()

    def on_status_flamingo(self):
        """Called once when status changes to Flamingo-ing"""
        if self.output_type == 'keyboard':
            pyautogui.keyUp('w')
        else:  # virtual_joystick
            if self.gamepad:
                # Reset right analog stick to center
                self.gamepad.right_joystick(0, 0)
                self.gamepad.update()

    def on_status_jump(self):
        """Called once when status changes to Jump!"""
        if self.output_type == 'keyboard':
            # Use the mapped keyboard key for the selected jump button
            jump_key = self.keyboard_jump_map.get(self.jump_button, 'space')
            pyautogui.press(jump_key)
        else:  # virtual_joystick
            if self.gamepad and self.jump_button in self.button_map:
                # Press and release the selected button
                button = self.button_map[self.jump_button]
                self.gamepad.press_button(button)
                self.gamepad.update()
                time.sleep(0.1)  # Brief press
                self.gamepad.release_button(button)
                self.gamepad.update()

    def on_status_user_absent(self):
        """Called once when status changes to User Absent"""
        # No action needed for user absence
        pass

    def clear_screen(self):
        """Clear the terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')

    def create_bar_with_fixed_range(self, value, bar_length=30):
        """Create a bar graph showing value with fixed range from -1.0 to -0.85"""
        min_val = -1.0
        max_val = -0.85
        midpoint = (min_val + max_val) / 2.0
        quarter = min_val + (max_val - min_val) * 0.25
        three_quarters = min_val + (max_val - min_val) * 0.75

        # Calculate normalized position (0 to 1) within the fixed range
        if max_val > min_val:
            normalized = (value - min_val) / (max_val - min_val)
        else:
            normalized = 0.5

        normalized = max(0.0, min(1.0, normalized))  # Clamp to 0-1 range
        bar_pos = int(normalized * bar_length)
        bar_pos = max(0, min(bar_pos, bar_length - 1))  # Clamp to bar length

        # Create the bar with markers
        bar = "["
        for i in range(bar_length):
            if i == bar_pos:
                bar += "|"  # Current value marker
            elif i == 0:
                bar += "<"  # Min marker (-1.0)
            elif i == bar_length - 1:
                bar += ">"  # Max marker (-0.85)
            elif i == int(0.25 * bar_length):
                bar += "1"  # 25% marker
            elif i == bar_length // 2:
                bar += "+"  # Midpoint marker (50%)
            elif i == int(0.75 * bar_length):
                bar += "3"  # 75% marker
            else:
                bar += " "
        bar += "]"

        return bar, min_val, max_val, midpoint, quarter, three_quarters

    def detect_jump_and_absence(self, left_avg, right_avg, current_time):
        """Detect jump and user absence patterns (highest priority)"""
        # Use configurable percentage threshold instead of exactly zero
        min_val = -1.0
        max_val = -0.85
        range_total = abs(max_val - min_val)
        threshold_value = range_total * self.jump_absence_threshold_percent

        # Check if both sides are below the threshold percentage of the range
        left_near_zero = abs(left_avg - min_val) < threshold_value
        right_near_zero = abs(right_avg - min_val) < threshold_value
        both_sides_near_zero = left_near_zero and right_near_zero

        if both_sides_near_zero:
            if self.both_sides_zero_start_time == 0:
                # Start timing near-zero state
                self.both_sides_zero_start_time = current_time
                self.pre_jump_status = self.current_status
            else:
                # Check if near-zero state has lasted long enough for user absence
                near_zero_duration = current_time - self.both_sides_zero_start_time
                if near_zero_duration >= self.user_absent_time and self.current_status != "User Absent":
                    return "User Absent"
        else:
            # No longer near-zero - check for jump detection
            if self.both_sides_zero_start_time > 0:
                near_zero_duration = current_time - self.both_sides_zero_start_time
                self.both_sides_zero_start_time = 0  # Reset zero tracking

                # If we were in near-zero state for a short time, it's a jump
                if near_zero_duration > 0 and near_zero_duration < self.user_absent_time:
                    return "Jump!"

        return None

    def detect_flamingo_stance(self, left_avg, right_avg, current_time):
        """Detect one-foot stance"""
        min_val = -1.0
        max_val = -0.85
        range_total = max_val - min_val
        fifty_percent_threshold = min_val + (range_total * 0.5)

        left_above_50 = left_avg > fifty_percent_threshold
        right_above_50 = right_avg > fifty_percent_threshold
        left_below_50 = left_avg < fifty_percent_threshold
        right_below_50 = right_avg < fifty_percent_threshold

        # Check for one-foot stance (only one side above 50%)
        one_foot_stance = (left_above_50 and right_below_50 and not left_below_50 and not right_above_50) or \
                         (right_above_50 and left_below_50 and not right_below_50 and not left_above_50)

        if one_foot_stance:
            if self.one_foot_start_time == 0:
                self.one_foot_start_time = current_time
            else:
                stance_duration = current_time - self.one_foot_start_time
                if stance_duration >= self.flamingo_hold_time:
                    return "Flamingo-ing"
        else:
            self.one_foot_start_time = 0  # Reset if stance is broken

        return None

    def detect_walking_pattern(self, left_avg, right_avg, current_time):
        """Detect walking pattern"""
        min_val = -1.0
        max_val = -0.85
        range_total = max_val - min_val
        fifty_percent_threshold = min_val + (range_total * 0.5)

        left_above_50 = left_avg > fifty_percent_threshold
        right_above_50 = right_avg > fifty_percent_threshold
        left_below_50 = left_avg < fifty_percent_threshold
        right_below_50 = right_avg < fifty_percent_threshold

        # Detect walking pattern: one side above 50%, the other below 50%
        new_walking_detected = False
        current_side = None

        if left_above_50 and right_below_50:
            new_walking_detected = True
            current_side = 'left'
        elif right_above_50 and left_below_50:
            new_walking_detected = True
            current_side = 'right'

        if new_walking_detected:
            # Check if this is a continuation (opposite side from last detection)
            if self.last_detected_side and current_side != self.last_detected_side:
                # This is the next step in the pattern
                self.last_walking_pattern_time = current_time
                self.last_detected_side = current_side
                return "Walking"
            elif not self.last_detected_side:
                # First detection
                self.last_walking_pattern_time = current_time
                self.last_detected_side = current_side
                return "Walking"
            else:
                # Same side detected again
                return "Walking"
        else:
            self.last_detected_side = None
            return None

    def determine_status(self, left_avg, right_avg):
        """Determine the current status based on all detection patterns"""
        current_time = time.time()

        # Priority 1: Jump and User Absence (highest priority)
        jump_absence_status = self.detect_jump_and_absence(left_avg, right_avg, current_time)
        if jump_absence_status:
            if jump_absence_status == "Jump!":
                # For jump, we want to display it briefly then return to previous status
                if self.current_status != "Jump!":
                    self.status_start_time = current_time
                    return "Jump!"
                elif current_time - self.status_start_time >= self.jump_display_time:
                    # Jump display time expired, return to previous status
                    return self.pre_jump_status
                else:
                    return "Jump!"
            else:
                # User Absent
                return "User Absent"

        # If we were showing Jump! but time expired, continue with normal detection
        if self.current_status == "Jump!" and current_time - self.status_start_time >= self.jump_display_time:
            # Continue with normal detection below
            pass

        # Priority 2: Flamingo stance
        flamingo_status = self.detect_flamingo_stance(left_avg, right_avg, current_time)
        if flamingo_status:
            return flamingo_status

        # Priority 3: Walking pattern
        walking_status = self.detect_walking_pattern(left_avg, right_avg, current_time)
        if walking_status:
            return walking_status

        # Priority 4: Handle walking status persistence
        if self.current_status == "Walking":
            time_since_walking = current_time - self.last_walking_pattern_time
            if time_since_walking <= self.walking_hold_time:
                return "Walking"

        # Default: Standing
        return "Standing"

    def update_status(self, left_avg, right_avg):
        """Update the current status and handle timing"""
        new_status = self.determine_status(left_avg, right_avg)

        # Only update start time if status actually changed
        if new_status != self.current_status:
            self.previous_status = self.current_status
            self.current_status = new_status
            self.status_start_time = time.time()

            # Call the appropriate callback function
            self.call_status_callback(new_status)

        return self.current_status

    def call_status_callback(self, status):
        """Call the appropriate callback function based on status change"""
        if status == "Standing":
            self.on_status_standing()
        elif status == "Walking":
            self.on_status_walking()
        elif status == "Flamingo-ing":
            self.on_status_flamingo()
        elif status == "Jump!":
            self.on_status_jump()
        elif status == "User Absent":
            self.on_status_user_absent()

    def print_axes(self):
        """Print all axis values in a formatted way"""
        # Calculate averages
        right_avg = (self.axis_values[0] + self.axis_values[1]) / 2.0
        left_avg = (self.axis_values[2] + self.axis_values[3]) / 2.0

        # Update status
        status = self.update_status(left_avg, right_avg)

        output = "Gamepad Axis Values:\n"
        output += "=" * 70 + "\n"
        output += f"Device: {self.device_path}\n"
        output += f"Status: {status}\n"
        output += f"Output Type: {self.output_type}\n"
        output += f"Jump Button: {self.jump_button}\n"
        output += f"Walking Hold: {self.walking_hold_time}s | "
        output += f"Flamingo Detect: {self.flamingo_hold_time}s | "
        output += f"Jump Display: {self.jump_display_time}s | "
        output += f"Absent Detect: {self.user_absent_time}s | "
        output += f"Jump/Absence Threshold: {self.jump_absence_threshold_percent*100:.1f}%\n"

        # Show time information based on current status
        current_time = time.time()
        status_duration = current_time - self.status_start_time

        if status == "Walking":
            output += f"Walking duration: {status_duration:.1f}s\n"
        elif status == "Flamingo-ing":
            output += f"Flamingo duration: {status_duration:.1f}s\n"
        elif status == "User Absent":
            output += f"Absent duration: {status_duration:.1f}s\n"
        elif status == "Jump!":
            time_remaining = self.jump_display_time - status_duration
            output += f"Jump display: {time_remaining:.1f}s remaining\n"
        elif status == "Standing":
            output += f"Standing duration: {status_duration:.1f}s\n"

        output += "-" * 70 + "\n"

        # Display individual axes with fixed range
        for i, value in enumerate(self.axis_values):
            bar, min_val, max_val, midpoint, quarter, three_quarters = self.create_bar_with_fixed_range(value)

            output += f"Axis {i}: {value:7.3f} "
            output += f"(range: {min_val:6.3f} to {max_val:6.3f}) "
            output += f"{bar}\n"

        output += "-" * 70 + "\n"

        # Display averages with fixed range bars
        right_bar, min_val, max_val, midpoint, quarter, three_quarters = self.create_bar_with_fixed_range(right_avg)
        output += f"Right:  {right_avg:7.3f} "
        output += f"(range: {min_val:6.3f} to {max_val:6.3f}) "
        output += f"{right_bar}\n"

        left_bar, min_val, max_val, midpoint, quarter, three_quarters = self.create_bar_with_fixed_range(left_avg)
        output += f"Left:   {left_avg:7.3f} "
        output += f"(range: {min_val:6.3f} to {max_val:6.3f}) "
        output += f"{left_bar}\n"

        # Add detection information with configurable threshold
        min_val = -1.0
        max_val = -0.85
        range_total = abs(max_val - min_val)
        threshold_value = range_total * self.jump_absence_threshold_percent
        fifty_percent_threshold = min_val + (max_val - min_val) * 0.5

        output += f"\nDetection thresholds:\n"
        output += f"Jump/Absence threshold: {threshold_value:.3f} from min value ({self.jump_absence_threshold_percent*100:.1f}%)\n"
        output += f"50% threshold: {fifty_percent_threshold:.3f}\n"
        output += "Detection Priorities:\n"
        output += "1. Jump/Absence: both sides within threshold of minimum (highest priority)\n"
        output += "2. Flamingo: one side >50% for detection time\n"
        output += "3. Walking: alternating sides >50%/ <50%\n"
        output += "4. Standing: default state\n"

        # Add legend for the bar markers
        output += "-" * 70 + "\n"
        output += "Bar legend: < -1.00 |current 1(25%) +(50%) 3(75%) > -0.85\n"
        output += "=" * 70 + "\n"
        output += "\nPress Ctrl+C to exit"
        print(output)

    def read_gamepad(self):
        """Read gamepad events and update axis values"""
        try:
            with open(self.device_path, 'rb') as gamepad:
                # Set the file descriptor to non-blocking mode
                import fcntl
                fd = gamepad.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

                print(f"Gamepad reader started on {self.device_path}")
                print(f"Output type: {self.output_type}")
                print(f"Jump button: {self.jump_button}")
                time.sleep(2)

                while True:
                    try:
                        event_data = gamepad.read(8)
                        if event_data and len(event_data) == 8:
                            timestamp, value, event_type, axis_number = struct.unpack('IhBB', event_data)

                            if event_type == 0x02 and axis_number < self.axis_count:
                                # Normalize axis value
                                normalized_value = value / 32767.0
                                self.axis_values[axis_number] = normalized_value

                                # Clear and update display
                                self.clear_screen()
                                self.print_axes()

                    except BlockingIOError:
                        # No data available, sleep briefly
                        time.sleep(0.01)

        except FileNotFoundError:
            print(f"Error: Gamepad device {self.device_path} not found.")
        except PermissionError:
            print(f"Error: Permission denied. Try running with sudo.")
        except KeyboardInterrupt:
            print("\nExiting gamepad reader...")
            # Clean up virtual gamepad
            if self.gamepad:
                self.gamepad.reset()
                self.gamepad.update()
        except Exception as e:
            print(f"Error: {e}")
            # Clean up virtual gamepad
            if self.gamepad:
                self.gamepad.reset()
                self.gamepad.update()

def scan_gamepad_devices():
    """Scan /dev/input/ for js# devices and return a list of available devices"""
    devices = glob.glob('/dev/input/js*')
    valid_devices = []

    for device in devices:
        if os.path.exists(device):
            valid_devices.append(device)

    return sorted(valid_devices)

def select_device_with_zenity(devices):
    """Use Zenity to create a selection dialog for available devices"""
    if not devices:
        print("No gamepad devices found in /dev/input/")
        return None

    # Prepare the Zenity command
    zenity_cmd = [
        'zenity', '--list',
        '--title', 'Select Wii Balance Board Device',
        '--text', 'Choose the gamepad device to use:',
        '--column', 'Device Path',
        '--column', 'Device Name',
        '--width=500', '--height=400'
    ]

    # Add device entries with descriptive names
    for device in devices:
        device_name = f"Wii Balance Board ({os.path.basename(device)})"
        zenity_cmd.extend([device, device_name])

    try:
        # Run Zenity and capture the selected device
        result = subprocess.run(zenity_cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            return None
    except FileNotFoundError:
        print("Zenity not found. Please install zenity or use manual selection.")
        return None
    except Exception as e:
        print(f"Error using Zenity: {e}")
        return None

def select_output_type_with_zenity():
    """Use Zenity to select between keyboard and virtual joystick output"""
    zenity_cmd = [
        'zenity', '--list',
        '--title', 'Select Output Type',
        '--text', 'Choose how you want to control the game:',
        '--column', 'Type',
        '--column', 'Description',
        '--width=500', '--height=300'
    ]

    # Add output type options
    zenity_cmd.extend([
        'keyboard', 'Keyboard output (pyautogui) - Presses W and selected jump key',
        'virtual_joystick', 'Virtual joystick (vgamepad) - Right stick up and selected button'
    ])

    try:
        # Run Zenity and capture the selected output type
        result = subprocess.run(zenity_cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            return None
    except FileNotFoundError:
        print("Zenity not found. Using keyboard output as default.")
        return 'keyboard'
    except Exception as e:
        print(f"Error using Zenity: {e}")
        return 'keyboard'

def select_jump_button_with_zenity():
    """Use Zenity to select the jump button"""
    zenity_cmd = [
        'zenity', '--list',
        '--title', 'Select Jump Button',
        '--text', 'Choose which button should be used for jumping:',
        '--column', 'Button',
        '--column', 'Description',
        '--width=500', '--height=300'
    ]

    # Add button options
    zenity_cmd.extend([
        'A', 'A Button (Keyboard: Space) - Standard jump button',
        'B', 'B Button (Keyboard: B) - Alternative jump button',
        'X', 'X Button (Keyboard: X) - Alternative jump button',
        'Y', 'Y Button (Keyboard: Y) - Alternative jump button'
    ])

    try:
        # Run Zenity and capture the selected button
        result = subprocess.run(zenity_cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            return 'A'  # Default to A if no selection
    except FileNotFoundError:
        print("Zenity not found. Using A button as default.")
        return 'A'
    except Exception as e:
        print(f"Error using Zenity: {e}")
        return 'A'

def manual_device_selection(devices):
    """Fallback manual selection if Zenity is not available"""
    if not devices:
        print("No gamepad devices found.")
        return None

    print("\nAvailable gamepad devices:")
    for i, device in enumerate(devices):
        print(f"{i + 1}. {device}")

    while True:
        try:
            choice = input(f"\nSelect device (1-{len(devices)}): ").strip()
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(devices):
                    return devices[index]
            print("Invalid selection. Please try again.")
        except KeyboardInterrupt:
            print("\nSelection cancelled.")
            return None

def manual_output_type_selection():
    """Fallback manual selection for output type"""
    print("\nSelect output type:")
    print("1. Keyboard output (pyautogui) - Presses W and selected jump key")
    print("2. Virtual joystick (vgamepad) - Right stick up and selected button")

    while True:
        try:
            choice = input("\nSelect output type (1-2): ").strip()
            if choice == '1':
                return 'keyboard'
            elif choice == '2':
                return 'virtual_joystick'
            else:
                print("Invalid selection. Please try again.")
        except KeyboardInterrupt:
            print("\nSelection cancelled. Using keyboard as default.")
            return 'keyboard'

def manual_jump_button_selection():
    """Fallback manual selection for jump button"""
    print("\nSelect jump button:")
    print("1. A Button (Keyboard: Space) - Standard jump button")
    print("2. B Button (Keyboard: B) - Alternative jump button")
    print("3. X Button (Keyboard: X) - Alternative jump button")
    print("4. Y Button (Keyboard: Y) - Alternative jump button")

    while True:
        try:
            choice = input("\nSelect jump button (1-4): ").strip()
            if choice == '1':
                return 'A'
            elif choice == '2':
                return 'B'
            elif choice == '3':
                return 'X'
            elif choice == '4':
                return 'Y'
            else:
                print("Invalid selection. Please try again.")
        except KeyboardInterrupt:
            print("\nSelection cancelled. Using A button as default.")
            return 'A'

def main():
    # Scan for available devices
    devices = scan_gamepad_devices()

    if not devices:
        print("No gamepad devices found in /dev/input/")
        print("Please make sure your Wii Balance Board is connected and paired.")
        return

    # Try to use Zenity for device selection
    selected_device = select_device_with_zenity(devices)

    # Fallback to manual selection if Zenity failed or was cancelled
    if not selected_device:
        selected_device = manual_device_selection(devices)

    if not selected_device:
        print("No device selected. Exiting.")
        return

    # Verify the selected device exists
    if not os.path.exists(selected_device):
        print(f"Selected device {selected_device} not found.")
        return

    # Select output type
    output_type = select_output_type_with_zenity()
    if not output_type:
        output_type = manual_output_type_selection()

    # Select jump button
    jump_button = select_jump_button_with_zenity()
    if not jump_button:
        jump_button = manual_jump_button_selection()

    print(f"Advanced Gamepad Axis Reader with Fixed Range (-1.00 to -0.85)")
    print(f"Using device: {selected_device}")
    print(f"Output type: {output_type}")
    print(f"Jump button: {jump_button}")

    reader = AdvancedGamepadReader(selected_device, output_type=output_type, jump_button=jump_button)
    reader.read_gamepad()

if __name__ == "__main__":
    main()
