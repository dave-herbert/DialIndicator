/*

  Read data from an import/Chinese dial indicator or digital calipers

  Copyright (C) 2023  Dave Herbert

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.

DialIndicator:

  Program to test various versions of how to read Digital Dial
  Indicator/ Calipers/Tire Gauge.

  The protocol for an import (Chinese) Digital Dial Indicator
  (Calipers/Tire Gauge, ...) is the same for all devices. Those
  devices typically run on LR44 battery at 1.5 volts. It's best to
  level shift the device clock and data to 5V. This can be done with 2
  2N2222 BJT transistors, one for clock, and one for data. In this
  configuration, the logic is reversed as the HIGH value of 1.5V from
  the device will become LOW, and the LOW from the device will become
  HIGH (5V). (See diagrams below)

  When connected as below, the measurement will be printed on the
  serial monitor every time it is changed.

Hardware:

  1 Arduino UNO (or equivalent)
  1 Device (Dial Indicator, Calipers, Tire Gauge, ... with data port)
  1 Breadboard to connect things together
  2 2N2222 BJT NPN transistors (can change with other NPNs as well)
  1 510Ω Resistor for voltage divider
  1 220Ω Resistor for voltage divider
  2 1kΩ Pull up resistors for data and clock
  2 10kΩ Current limiting resistors for data and clock
  
Tested Setup:

  o To provide power to the Vcc pin of the device, a voltage divider
    can be used. Arduino 5V -> R1 (510Ω) \ R2 (220Ω) -> GND
                                          +-> Vcc of device
  o Connect all grounds together
  o Device Clock 2N2222 BJT NPN Transistor
    - 5V -> R3 (1kΩ) -> \--> Transistor Collector 
                         +-> Arduino Pin 2 (Associated with INT0)
    - Device Clock Line -> R4 (10kΩ) -> Transistor Base 
    - Transistor Emitter -> GND
  o Device Data 2N2222 BJT NPN Transistor
    - 5V -> R5 (1kΩ) -> \--> Transistor Collector 
                         +-> Arduino Pin 4
    - Device Data Line -> R6 (10kΩ) -> Transistor Base 
    - Transistor Emitter -> GND

Algorithm:

  This code uses an external interrupt on trailing edge of the clock
  line to indicate when to read data. Each data bit will be added to a
  temporary buffer until all 24 bits of data have been read. A timer
  interrupt is used to detect when a full 24 bits have been read.
  Since the data burst is short compared to the length of the gap
  between bursts, if the timer interrupt sees no change in the bits
  read count, it means the data is incomplete and will be
  discarded. If 24 bits have been read then it indicates that an
  entire data burst has been read.

  Arduino can handle input interrupts only in digital pin 2
  ISR(INT0_vect) and digital pin 3 ISR(INT_vect). Other MCUs support
  more. This code assumes the clock pin (and subsequent interrupt) are
  on Pin 2.

Data Protocol:

  The data from the indicator comes in 24 bits, with the least
  significant bit coming first. The last four bits coming over the
  line appear to be metadata with one bit for the sign and another
  refering to inch vs mm mode.

  After reversing the bits to place them in the right order, bits[0 -
  19] are the data bits, bit[20]: 0:positive, 1: negative, bit[23]: 0:
  mm, 1: inches. The data value should be divided by 100 for mm and
  200 for inches.

Data Port On Indicator/Calipers:

             DEVICE
      | |    PIN OUT    | |
      | |   | |   | |   | |
     |   | |   | |   | |   |
     |   | | C | |   | |   |
     |   | | l | | D | |   |
     | V | | o | | a | | G |
     | c | | c | | t | | N |
     | c | | k | | a | | D |
 ----+---+-+---+-+---+-+---+---- <-- Board Edge

Clock and Data Lines:

  The clock is high (1.5V) by default, transistions to low, then the
  data line is set (either low for 1 or high for 0) and can be read on
  the clock pulse trailing edge.

      ---+   +---+   +---+   +---+   +----- 1.5V
Clock:   |   |   |   |   |   |   |   |
         +---+   +---+   +---+   +---+      0V
             v       v       v       v
      -----+ v +---+---+---+ v +---+---+--- 1.5V
 Data:     | v |     v     | v |     v 
           +---+     v     +---+     v      0V
             0       1       0       1

  In this diagram of a nibble of data, the data is 0101, however since
  the data comes in reverse order, the data is 1010. Since the data is
  below the threshold of what the AtMega can read, it needs to be
  shifted.  In my case, I use two 2N2222 BJT resistors (one for clock
  and one for data) to shift the data to 5V, however, it also inverts
  it. The resultant signal would be:

  Inverted and voltage shifted Clock and Data.

         +---+   +---+   +---+   +---+      5V
         |   |   |   |   |   |   |   |
Clock:   |   |   |   |   |   |   |   |
         |   |   |   |   |   |   |   |
      ---+   +---+   +---+   +---+   +----- 0V
             v       v       v       v
           +---+     v     +---+     v      5V
           | v |     v     | v |     v  
 Data:     | v |     v     | v |     v  
           | v |     v     | v |     v  
      -----+ v +---+---+---+ v +---+---+--- 0V
             0       1       0       1

Timing:
  Nibble Timing:

   2.2ms >|                                        |<  
   1.6ms >|                           |<  
   440µs >|       |<  
   312µs >|   |<
          |   | 
       ---+   +---+   +---+   +---+   +------------+   +---+   +---+   +-  ...
          |   |   |   |   |   |   |   |            |   |   |   |   |   |
          +---+   +---+   +---+   +---+            +---+   +---+   +---+

  Data Burst Timing (all 24 bits plus data burst gap):

    172ms >|                                         |<
     13ms >|                           |<
       ----DDDD-DDDD-DDDD-DDDD-DDDD-DDDD-------------DDDD-DDDD-DDDD-...
*/


// Input Pins
#define INDICATOR_CLOCK 2  // Can only be 2 or 3 on Uno
#define INDICATOR_DATA 4  // Can be any input pin

// Set INVERTED to true of the data from the device is inverted.
#define INVERTED true
#if INVERTED
// Sync and data input are default low
#define TRAILING_EDGE FALLING
#else  // Non-inverted
// Sync and data input are default high
#define TRAILING_EDGE RISING
#endif

// Set HEARTBEAT_MS to the number of milliseconds to re-issue measurement
// even if it has not changed.
#define HEARTBEAT_MS 2000

// Toggle Output Pin PORTB4/D12 on ISR.
// When set to true, will set the output pin to HIGH
// in the ISR when it first sees 24 bits read. It gets cleared
// on the next call to the ISR.
#define DEBUG_OUTPUT_PIN true

// Indicator/Caliper bit constants/masks
#define DATA_MASK        0x0FFFFF   // Lower 20 bits of data packet
#define INCH_MM_MASK     0x800000   // Bit 23
#define SIGN_MASK        0x100000   // Bit 20
#define PACKET_BIT_COUNT 24

volatile uint32_t next_bit = 1;  // Shifts left for each bit read from data
volatile uint8_t bits_read = 0;
volatile uint8_t prev_bits_read = 0;
volatile uint32_t data_buffer = 0; // Space to hold data read bit by bit
volatile uint32_t data = -1; // Space to hold data from data_buffer
volatile bool data_ready = false;  // True when data is ready to use

// Used in loop() to detect changes in output.
uint32_t prev_data = -1; // Last data bits copied from data variable


void setup() {
  //start serial connection
  Serial.begin(115200);
  /* Debugging output pin for oscilloscope (Digital Pin 12) */
#if DEBUG_OUTPUT_PIN
  bitSet(DDRB, DDB4); // PORTB4 / D12
#endif

  // Prepare the clock and data pins for input
  pinMode(INDICATOR_DATA, INPUT);
  pinMode(INDICATOR_CLOCK, INPUT);
  attachInterrupt(digitalPinToInterrupt(INDICATOR_CLOCK),
  		  indicatorClockInterrupt,
  		  TRAILING_EDGE);
  TCCR2A = 0;
  TCCR2B = 0;
  // Set Timer2 prescaler to 1024
  bitSet(TCCR2B, CS22);
  bitSet(TCCR2B, CS21);
  bitSet(TCCR2B, CS20);
  bitSet(TIMSK2, TOIE2); // Enable the ISR
}


/* Variables set in the loop when data is processed */
float measurement = 0.0;
bool inch_mm = false;

void displayMeasurement() {
  //Serial.print(F("Measurement: "));
  if (inch_mm) {
    Serial.print(measurement, 4);
    Serial.println(F(" inches"));
  } else {
    Serial.print(measurement, 2);
    Serial.println(F(" mm"));
  }
}

#if HEARTBEAT_MS > 0
unsigned long last_output_ms = 0;
#endif

void loop() {
  uint32_t data_local;  // Local copy of data to process
  bool sign; // Extracted from data, true: positive, false: negative
  
  if (data_ready) {
    // Consume data
    noInterrupts();  // Disable interrupts to do an atomic read of data
    data_local = data;
    interrupts();
    data_ready = false;
    // Only output data when it is different from the last reading
    // OR passed HEARTBEAT if enabled.
#if HEARTBEAT_MS > 0
    bool do_output = (data_local != prev_data ||
		      (millis() - last_output_ms) >= HEARTBEAT_MS);
#else
    bool do_output = data_local != prev_data;
#endif
    if (do_output) {
#if HEARTBEAT_MS
      last_output_ms = millis();
#endif
      // Process the new data value
      sign = data_local & SIGN_MASK;
      inch_mm = data_local & INCH_MM_MASK;
      prev_data = data_local;
      measurement = float(data_local & DATA_MASK);
      if (inch_mm) {
	measurement /= 2000.0;
      }
      else {
	measurement /= 100.0;
      }
      if (sign) {
	measurement = -measurement;
      }
      displayMeasurement();
    }
  }
  delay(50);
}


/*
** Interrupt that triggers when clock data signals.
** This interrupt is configured to run on the trailing clock
** edge (the time at which the data bit is ready to read).
*/
void indicatorClockInterrupt() {
  // If this is the first bit read, start the timer
#if defined(TOGGLE_ON_CLOCK)
  bitToggle(PORTB, PORTB4);
#endif

  // Read data from data pin
  bool data_bit = digitalRead(INDICATOR_DATA);

  // Add data to data_buffer
#if INVERTED
  // 0 -> 1 (set bit), 1 -> 0 (nop)
  if (!data_bit) {
    data_buffer |= next_bit;
  }
#else
  // 1 -> 1 (set bit), 0 -> 0 (nop)
  if (data_bit) {
    data_buffer |= next_bit;
  }
#endif
  
  bits_read++;
  // Shift bit position for next bit to be read
  next_bit <<= 1;
}

/*
** Timer overflow interrupt that gets called approximately once
** every 16.4ms
*/ 
ISR(TIMER2_OVF_vect) {
  // Set the output pin when data is ready, clear when not
  if (bits_read) {
    if (bits_read == PACKET_BIT_COUNT) {
#if DEBUG_OUTPUT_PIN
      bitSet(PORTB, PORTB4);
#endif
      // Copy
      data = data_buffer;
      data_ready = true;  // loop() sets this to false.
      prev_bits_read = bits_read; // Sets this to clear in next block
    }
    if (bits_read == prev_bits_read) {
      // Clear
      // Initialize variables for next data burst
      data_buffer = 0;
      bits_read = 0;
      prev_bits_read = 0;
      next_bit = 1;
    } else {
#if DEBUG_OUTPUT_PIN
      bitClear(PORTB, PORTB4);
#endif
    }
  } else {
#if DEBUG_OUTPUT_PIN
    bitClear(PORTB, PORTB4);
#endif
  }
  prev_bits_read = bits_read;
}
