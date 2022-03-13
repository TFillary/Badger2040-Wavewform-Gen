# Badger2040-Wavewform-Gen
A Square wave generator with duty cycle control for a Rasberry Pi Pico which uses the Pimoroni Badger2040 screen and the Qw/ST connector to access PIO pins.
Streams 10 bits to a single pin in a single cycle under DMA control - 10 bits is used for duty cycle manipulation, hence the maximum frequency is 1/10 of the pico 
frequency of 125Mhz.

# Controls
  - Button a - steps through the duty cycles available
  - Buttons b & c - select the frequency increment, either 1Khz or 10Khz
  - Button Up - increases the frequency by the increment
  - Button Down - decreases the frequency by the increment

# Conclusion
Although not tested, it should be possible to set the frequency down to 200hz if the frequency increment
was modified.  Lack of available buttons limited this.

Equally it should be possible to set the frequency up to 12.5Mhz, but I only have the Scoppy android
application and an RP2040 so can't verify signals above around 250Khz. See https://github.com/fhdm-dev/scoppy/
for further details.

## So for under £20 I now have a squarewave generator and oscilloscope for basic testing with minimal hardware.

![Image (3)](https://user-images.githubusercontent.com/30411837/158058018-6ba69ec9-be68-4abf-aebd-8aea493093e8.jpeg)
![Image (2)](https://user-images.githubusercontent.com/30411837/158058055-a5f1c5da-77f5-4df7-a934-13947e2c6e24.jpeg)
