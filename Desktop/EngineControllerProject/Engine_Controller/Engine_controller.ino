#include <Servo.h>   // Arduino library used to control the choke servo motor
#include <math.h>    // Provides log() and pow() for the thermistor temperature calculation

// ================================================================
// PIN DEFINITIONS
// ================================================================

const int PIN_CHOKE_SERVO = 6;      // PWM-capable pin connected to the choke servo signal wire
const int PIN_STARTER = 8;          // Digital output controlling the starter relay/MOSFET
const int PIN_GAS_SOLENOID = 9;     // Digital output controlling the gas/fuel solenoid
const int PIN_OIL_PUMP = 10;        // Digital output controlling the oil pump
const int PIN_MAGNETO_KILL = 11;    // Digital output used to ground/kill the magneto ignition

const int PIN_THERMISTOR = A0;      // Analog input reading the 100k NTC thermistor voltage divider
const int PIN_O2_SENSOR = A1;       // Analog input reading the O2 sensor voltage

// ================================================================
// SERVO SETTINGS
// The servo controls the engine choke. Based on your testing, the
// physical servo response starts around 60 degrees, so the usable range
// is constrained between 60 and 90 degrees.
// ================================================================

Servo chokeServo;                   // Creates the servo object used to command the choke servo

const int CHOKE_CLOSED_SERVO_ANGLE = 60;      // Servo angle corresponding to choke closed
const int CHOKE_FULL_OPEN_SERVO_ANGLE = 90;   // Servo angle corresponding to choke fully open
const int CHOKE_STEP_DEGREES = 2;             // Amount the choke moves for each small open/close command

int chokeAngle = 0;                 // Stores the current commanded choke angle

// ================================================================
// ENGINE STATE VARIABLES
// These booleans track the current logical state of the engine outputs.
// The actual pins are updated later by setOutputStates().
// ================================================================

bool engineOn = false;              // True when the code considers the engine running/enabled
bool autoMode = false;              // True when automatic O2/temp-based control is enabled
bool gasOpen = false;               // True when the gas solenoid should be open
bool oilPumpOn = false;             // True when the oil pump should be running
bool magnetoKillOn = false;         // True when the magneto should be grounded/killed
bool starterOn = false;             // True while the starter should be energized

// These define whether an output turns ON when the Arduino pin is LOW.
// Active-low is common when a relay module or transistor circuit turns on
// by sinking current rather than sourcing it.
const bool GAS_SOLENOID_ACTIVE_LOW = true;
const bool MAGNETO_KILL_ACTIVE_LOW = true;

String lastCommand = "NONE";        // Stores the most recent command received over Serial

// ================================================================
// TIMING SETTINGS
// millis() timing is used for auto adjustment so the auto loop does not
// constantly change the choke/pump every cycle.
// ================================================================

unsigned long lastAutoAdjust = 0;                       // Time when auto control last adjusted outputs
const unsigned long AUTO_ADJUST_INTERVAL_MS = 5000;     // Auto control updates every 5 seconds

// ================================================================
// THERMISTOR CONSTANTS
// These are used for the Steinhart-Hart temperature equation for the
// 100k NTC thermistor and 100k fixed resistor voltage divider.
// ================================================================

const float R_FIXED = 100000.0;      // Fixed resistor value in the voltage divider, in ohms
const float A = 0.000827111;         // Steinhart-Hart coefficient A
const float B = 0.000208802;         // Steinhart-Hart coefficient B
const float C = 0.000000080592;      // Steinhart-Hart coefficient C

// ================================================================
// SENSOR FUNCTIONS
// These functions read the analog sensors and convert raw ADC readings
// into useful engineering values.
// ================================================================

float readO2Voltage() {
  // analogRead() returns a value from 0 to 1023 for 0 to 5 V on Arduino Uno.
  int raw = analogRead(PIN_O2_SENSOR);

  // Convert the raw ADC value to voltage.
  return raw * (5.0 / 1023.0);
}

float readTemperatureF() {
  // Read the voltage divider connected to the thermistor.
  int raw = analogRead(PIN_THERMISTOR);

  // If raw is 0 or 1023, the calculation would divide by zero or become invalid.
  // Returning -999.9 makes it obvious that the sensor reading is bad/disconnected.
  if (raw <= 0 || raw >= 1023) {
    return -999.9;
  }

  // Convert ADC reading into thermistor resistance.
  // This assumes the thermistor and fixed resistor are wired as expected
  // in a 100k/100k voltage divider.
  float resistance = R_FIXED / ((1023.0 / raw) - 1.0);

  // Natural log of thermistor resistance, needed for Steinhart-Hart.
  float logR = log(resistance);

  // Apply the Steinhart-Hart equation to convert resistance to temperature in Kelvin.
  float tempK = 1.0 / (A + B * logR + C * pow(logR, 3));

  // Convert Kelvin to Celsius, then Celsius to Fahrenheit.
  float tempC = tempK - 273.15;
  return (tempC * 9.0 / 5.0) + 32.0;
}

// ================================================================
// SERVO CONTROL
// These functions control the choke angle. The applyChokeAngle() function
// enforces the tested usable range so commands cannot drive the servo
// outside the intended 60-90 degree range.
// ================================================================

void applyChokeAngle() {
  // Keep chokeAngle within the physical/tested range.
  chokeAngle = constrain(chokeAngle, CHOKE_CLOSED_SERVO_ANGLE, CHOKE_FULL_OPEN_SERVO_ANGLE);

  // Command the servo to move to the desired angle.
  chokeServo.write(chokeAngle);

  // Small delay gives the servo time to physically move before another command.
  delay(150);
}

void chokeOpenStep() {
  // Open choke by a small increment.
  chokeAngle += CHOKE_STEP_DEGREES;
  applyChokeAngle();
}

void chokeCloseStep() {
  // Close choke by a small increment.
  chokeAngle -= CHOKE_STEP_DEGREES;
  applyChokeAngle();
}

void chokeFullOpen() {
  // Jump directly to the fully open choke angle.
  chokeAngle = CHOKE_FULL_OPEN_SERVO_ANGLE;
  applyChokeAngle();
}

void chokeFullClosed() {
  // Jump directly to the fully closed choke angle.
  chokeAngle = CHOKE_CLOSED_SERVO_ANGLE;
  applyChokeAngle();
}

// ================================================================
// OUTPUT CONTROL
// These functions translate the logical state variables into actual
// Arduino pin voltages.
// ================================================================

void writeOutput(int pin, bool on, bool activeLow) {
  // If activeLow is true: ON = LOW and OFF = HIGH.
  // If activeLow is false: ON = HIGH and OFF = LOW.
  digitalWrite(pin, activeLow ? (on ? LOW : HIGH) : (on ? HIGH : LOW));
}

void setOutputStates() {
  // Starter is currently written as active-low: starterOn true sends LOW.
  // This matches a relay/module where LOW energizes the input.
  digitalWrite(PIN_STARTER, starterOn ? LOW : HIGH);

  // Gas solenoid is also written as active-low here.
  // NOTE: GAS_SOLENOID_ACTIVE_LOW is defined above but not used in this line.
  digitalWrite(PIN_GAS_SOLENOID, gasOpen ? LOW : HIGH);

  // Oil pump is active-high: HIGH turns pump on, LOW turns pump off.
  digitalWrite(PIN_OIL_PUMP, oilPumpOn ? HIGH : LOW);

  // Magneto kill uses the helper function because it is defined as active-low.
  // When magnetoKillOn is true, this grounds/kills the ignition through the driver circuit.
  writeOutput(PIN_MAGNETO_KILL, magnetoKillOn, MAGNETO_KILL_ACTIVE_LOW);
}

// ================================================================
// ENGINE CONTROL
// These functions define the main actions commanded from the website:
// start, stop, enable auto mode, and disable auto mode.
// ================================================================

void startEngine() {
  // Mark the engine as on and disable auto mode during manual start.
  engineOn = true;
  autoMode = false;

  // Allow ignition, open gas, and turn on oil pump before cranking.
  magnetoKillOn = false;
  gasOpen = true;
  oilPumpOn = true;

  // Open choke before attempting to start.
  chokeFullOpen();

  // Energize starter for 2 seconds.
  starterOn = true;
  setOutputStates();
  delay(2000);

  // Turn starter off after the pulse.
  starterOn = false;
  setOutputStates();
}

void stopEngine() {
  // Mark engine and auto mode as off.
  engineOn = false;
  autoMode = false;

  // Shut off fuel and oil pump, make sure starter is off, and enable magneto kill.
  gasOpen = false;
  oilPumpOn = false;
  starterOn = false;
  magnetoKillOn = true;

  // Apply output states to the actual pins.
  setOutputStates();

  // Keep kill active briefly to make sure the engine shuts down.
  delay(1500);
}

void enableAuto() {
  // Enable automatic control and mark the engine as active.
  autoMode = true;
  engineOn = true;

  // Prepare the engine outputs for running.
  magnetoKillOn = false;
  gasOpen = true;
  oilPumpOn = true;

  setOutputStates();
}

void disableAuto() {
  // Disables automatic adjustment, but does not shut the engine off.
  autoMode = false;
}

// ================================================================
// AUTO CONTROL
// In auto mode, the code periodically checks temperature and O2 voltage.
// It then adjusts the oil pump and choke based on simple thresholds.
// ================================================================

void autoControlLoop() {
  // Auto control only runs if both autoMode and engineOn are true.
  if (!autoMode || !engineOn) return;

  // Only adjust every AUTO_ADJUST_INTERVAL_MS milliseconds.
  unsigned long now = millis();
  if (now - lastAutoAdjust < AUTO_ADJUST_INTERVAL_MS) return;

  // Save the time of this adjustment.
  lastAutoAdjust = now;

  // Read current sensor values.
  float tempF = readTemperatureF();
  float o2V = readO2Voltage();

  // Oil pump hysteresis:
  // Above 120 F, turn pump on.
  // Below 100 F, turn pump off.
  // Between 100-120 F, keep the previous state.
  if (tempF > 120.0) oilPumpOn = true;
  else if (tempF < 100.0) oilPumpOn = false;

  // Basic O2-based choke control:
  // Low O2 voltage closes the choke.
  // High O2 voltage opens the choke.
  // Middle range leaves the choke unchanged.
  if (o2V < 0.35) chokeFullClosed();
  else if (o2V > 0.75) chokeFullOpen();

  // Apply any changed output states.
  setOutputStates();
}

// ================================================================
// STATUS REPORTING
// Sends a JSON-like status message over Serial so the Pi/BeagleBone backend
// can read current states and display them on the website.
// ================================================================

void sendStatus() {
  Serial.print("{");
  Serial.print("\"engineOn\":"); Serial.print(engineOn ? "true" : "false");
  Serial.print(",\"autoMode\":"); Serial.print(autoMode ? "true" : "false");
  Serial.print(",\"starterOn\":"); Serial.print(starterOn ? "true" : "false");
  Serial.print(",\"gasOpen\":"); Serial.print(gasOpen ? "true" : "false");
  Serial.print(",\"oilPumpOn\":"); Serial.print(oilPumpOn ? "true" : "false");
  Serial.print(",\"magnetoKillOn\":"); Serial.print(magnetoKillOn ? "true" : "false");
  Serial.print(",\"chokeAngle\":"); Serial.print(chokeAngle);
  Serial.print(",\"temperatureF\":"); Serial.print(readTemperatureF(), 2);
  Serial.print(",\"o2Voltage\":"); Serial.print(readO2Voltage(), 3);
  Serial.print(",\"lastCommand\":\""); Serial.print(lastCommand); Serial.print("\"");
  Serial.println("}");
}

// ================================================================
// COMMAND HANDLER
// Reads commands sent by the website/backend over USB Serial and calls
// the matching engine control function.
// ================================================================

void handleCommand(String cmd) {
  // Echo the received command for debugging in the Serial Monitor/logs.
  Serial.print("Received: ");
  Serial.println(cmd);

  // Remove whitespace/newline characters and make command uppercase.
  cmd.trim();
  cmd.toUpperCase();

  // Ignore blank commands.
  if (cmd.length() == 0) return;

  // Store command for status reporting.
  lastCommand = cmd;

  // Match the command text and run the correct action.
  if (cmd == "START") {
    startEngine();
  } else if (cmd == "STOP") {
    stopEngine();
  } else if (cmd == "AUTO_ON") {
    enableAuto();
  } else if (cmd == "AUTO_OFF") {
    disableAuto();
  } else if (cmd == "CHOKE_OPEN") {
    chokeOpenStep();
  } else if (cmd == "CHOKE_CLOSE") {
    chokeCloseStep();
  } else if (cmd == "CHOKE_FULL_OPEN") {
    chokeFullOpen();
  } else if (cmd == "CHOKE_FULL_CLOSED") {
    chokeFullClosed();
  } else if (cmd == "STATUS") {
    // No action needed. The code will send status below.
  } else if (cmd == "TEST_PINS") {
    testPins();
  } else {
    // Unknown command response for debugging/backend error handling.
    Serial.println("{\"error\":\"unknown command\"}");
    return;
  }

  // Send updated state after handling the command.
  sendStatus();
}

// ================================================================
// TEST FUNCTION
// TEST_PINS turns each output on and off for bench testing.
// IMPORTANT: Use caution if real engine hardware is connected, because this
// can energize starter, gas solenoid, oil pump, and magneto kill outputs.
// ================================================================

void testPins() {
  int pins[] = {PIN_STARTER, PIN_GAS_SOLENOID, PIN_OIL_PUMP, PIN_MAGNETO_KILL};

  // Pulse each output HIGH for 1 second, then LOW for 0.5 seconds.
  // NOTE: This does not account for active-low logic, so active-low devices
  // may behave opposite from what you expect during this test.
  for (int i = 0; i < 4; i++) {
    digitalWrite(pins[i], HIGH);
    delay(1000);
    digitalWrite(pins[i], LOW);
    delay(500);
  }

  // Also test the servo movement range.
  chokeFullClosed();
  delay(1000);
  chokeFullOpen();
}

// ================================================================
// SETUP
// Runs once when the Arduino powers on or resets.
// Initializes Serial, pin modes, safe default output states, and servo.
// ================================================================

void setup() {
  // Start USB serial communication with the Pi/BeagleBone/backend.
  Serial.begin(9600);

  // Configure all control pins as outputs.
  pinMode(PIN_STARTER, OUTPUT);
  pinMode(PIN_GAS_SOLENOID, OUTPUT);
  pinMode(PIN_OIL_PUMP, OUTPUT);
  pinMode(PIN_MAGNETO_KILL, OUTPUT);

  // Safe startup states:
  // starter off, gas off, oil pump off, magneto kill off.
  // These assume starter/gas/magneto kill are active-low and oil pump is active-high.
  digitalWrite(PIN_STARTER, HIGH);
  digitalWrite(PIN_GAS_SOLENOID, HIGH);
  digitalWrite(PIN_OIL_PUMP, LOW);
  digitalWrite(PIN_MAGNETO_KILL, HIGH);

  // Attach the servo signal pin.
  chokeServo.attach(PIN_CHOKE_SERVO);

  // Initialize chokeAngle to 0, then command servo to 0 degrees.
  // NOTE: This is outside the later constrained 60-90 degree range.
  // If you want startup to match the controlled range, use chokeFullClosed() instead.
  chokeAngle = 0;
  chokeServo.write(chokeAngle);

  // Give hardware time to settle, then report that Arduino is ready.
  delay(1000);
  Serial.println("{\"status\":\"Arduino ready\"}");
}

// ================================================================
// MAIN LOOP
// Runs continuously after setup(). It checks for serial commands and runs
// auto control if enabled.
// ================================================================

void loop() {
  // If the backend sent a command over USB Serial, read it up to the newline.
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    handleCommand(cmd);
  }

  // Run automatic control logic when auto mode is enabled.
  autoControlLoop();
}
