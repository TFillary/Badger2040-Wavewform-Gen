# Square wave generator with duty cycle control for Rasberry Pi Pico
# Uses Pimoroni Badger 2040 screen and the Qw/ST connector to access PIO pins
# Streams 10 bits to a single pin - 10 bits used for duty cycle manipulation, hence the maximum frequency
# is 1/10 of the pico frequency of 125Mhz.
#
# Button a - steps through the duty cycles available
# Buttons b & c - select the frequency increment, either 1Khz or 10Khz
# Button Up - increases the frequency by the increment
# Button Down - decreases the frequency by the increment
#
# Although not tested, it should be possible to set the frequency down to 200hz if the frequency increment
# was modified.  Lack of available buttons limited this.
# Equally it should be possible to set the frequency up to 12.5Mhz, but I only have the Scoppy android
# application and an RP2040 so can't verify signals above around 250Khz. See https://github.com/fhdm-dev/scoppy/
# for further details.
#
# T. Fillary - 13-03-22

import time
import machine
from machine import Pin, mem32, freq
import badger2040
from badger2040 import WIDTH
from rp2 import PIO, StateMachine, asm_pio
from array import array
from utime import sleep

fclock=freq() #clock frequency of the pico
freq_set = 20000 #Default starting frequency
old_freq = freq_set 
duty = 50 # Default to 50/50 Duty Cycle - Note the single duty is for the highs only, lows are calculated
old_duty = duty
cycle_bits = 10  # 10 bits per waveform cycle

MAX_BATTERY_VOLTAGE = 4.0
MIN_BATTERY_VOLTAGE = 3.2

font_sizes = (0.5, 0.7, 0.9)

# Approximate center lines for buttons A, B and C
centers = (41, 147, 253)

adjustment_txt = ("Duty", "+1K", "+10K")
increments = (10, 1000, 10000)
freq_increment_val = increments[1] # Default to lowest frequency increment

# DMA constants
DMA_BASE=0x50000000
CH0_READ_ADDR  =DMA_BASE+0x000
CH0_WRITE_ADDR =DMA_BASE+0x004
CH0_TRANS_COUNT=DMA_BASE+0x008
CH0_CTRL_TRIG  =DMA_BASE+0x00c
CH0_AL1_CTRL   =DMA_BASE+0x010
CH1_READ_ADDR  =DMA_BASE+0x040
CH1_WRITE_ADDR =DMA_BASE+0x044
CH1_TRANS_COUNT=DMA_BASE+0x048
CH1_CTRL_TRIG  =DMA_BASE+0x04c

PIO0_BASE     =0x50200000
PIO0_BASE_TXF0=PIO0_BASE+0x10
PIO0_SM0_CLKDIV=PIO0_BASE+0xc8

def set_clock_div():
    div=fclock/(freq_set*cycle_bits)
    clkdiv=int(div)+1
    clkdiv_frac=0 #fractional clock division results in jitter
    mem32[PIO0_SM0_CLKDIV]=(clkdiv<<16)|(clkdiv_frac<<8)

def set_duty_cycle():
    # Sets the appropriate bits in the lower bits for the desired duty cycle specified by duty
    highcount = int(duty/cycle_bits) # Just need to specify how many msbs to set high (1), Low bits calculated
    lowcount = int(cycle_bits - highcount)
    wave[0] = 0xffffffff << lowcount  #Shift in the number of low bits needed

# Setup to stream cycle_bits bits through 1 PIO 
@asm_pio(out_init=PIO.OUT_HIGH,
         out_shiftdir=PIO.SHIFT_RIGHT, autopull=True, pull_thresh=cycle_bits)

def stream():
    out(pins,1)

# Start state machine before DMA set up - State machine set to pico default freq of 125Mhz, clock div controls the actual execution speed
sm = StateMachine(0, stream, freq=fclock, out_base=Pin(5))
sm.active(1)

set_clock_div() # set up state clock divisor for the streaming frequency required

#2-channel chained DMA. channel 0 does the transfer, channel 1 reconfigures
p_ar=array('I',[0]) #global 1-element array 
@micropython.viper
def startDMA(ar,nword):
    p=ptr32(ar)
    mem32[CH0_READ_ADDR]=p
    mem32[CH0_WRITE_ADDR]=PIO0_BASE_TXF0
    mem32[CH0_TRANS_COUNT]=nword
    IRQ_QUIET=0x1 #do not generate an interrupt
    TREQ_SEL=0x00 #wait for PIO0_TX0
    CHAIN_TO=1    #start channel 1 when done
    RING_SEL=0
    RING_SIZE=0   #no wrapping
    INCR_WRITE=0  #for write to array
    INCR_READ=1   #for read from array
    DATA_SIZE=2   #32-bit word transfer
    HIGH_PRIORITY=1
    EN=1
    CTRL0=(IRQ_QUIET<<21)|(TREQ_SEL<<15)|(CHAIN_TO<<11)|(RING_SEL<<10)|(RING_SIZE<<9)|(INCR_WRITE<<5)|(INCR_READ<<4)|(DATA_SIZE<<2)|(HIGH_PRIORITY<<1)|(EN<<0)
    mem32[CH0_AL1_CTRL]=CTRL0
    
    p_ar[0]=p
    mem32[CH1_READ_ADDR]=ptr(p_ar)
    mem32[CH1_WRITE_ADDR]=CH0_READ_ADDR
    mem32[CH1_TRANS_COUNT]=1
    IRQ_QUIET=0x1 #do not generate an interrupt
    TREQ_SEL=0x3f #no pacing
    CHAIN_TO=0    #start channel 0 when done
    RING_SEL=0
    RING_SIZE=0   #no wrapping
    INCR_WRITE=0  #single write
    INCR_READ=0   #single read
    DATA_SIZE=2   #32-bit word transfer
    HIGH_PRIORITY=1
    EN=1
    CTRL1=(IRQ_QUIET<<21)|(TREQ_SEL<<15)|(CHAIN_TO<<11)|(RING_SEL<<10)|(RING_SIZE<<9)|(INCR_WRITE<<5)|(INCR_READ<<4)|(DATA_SIZE<<2)|(HIGH_PRIORITY<<1)|(EN<<0)
    mem32[CH1_CTRL_TRIG]=CTRL1


#setup waveform.
nsamp=4 #must be a multiple of 4 - 4bytes in single 32 bit word
wave=array("I",[0]*nsamp)
set_duty_cycle() # sets the appropriate bits in the wave lower n bits for the desired duty cycle

startDMA(wave,int(nsamp/4))

button_a = machine.Pin(badger2040.BUTTON_A, machine.Pin.IN, machine.Pin.PULL_DOWN)
button_b = machine.Pin(badger2040.BUTTON_B, machine.Pin.IN, machine.Pin.PULL_DOWN)
button_c = machine.Pin(badger2040.BUTTON_C, machine.Pin.IN, machine.Pin.PULL_DOWN)
button_up = machine.Pin(badger2040.BUTTON_UP, machine.Pin.IN, machine.Pin.PULL_DOWN)
button_down = machine.Pin(badger2040.BUTTON_DOWN, machine.Pin.IN, machine.Pin.PULL_DOWN)

# Inverted. For reasons.
button_user = machine.Pin(badger2040.BUTTON_USER, machine.Pin.IN, machine.Pin.PULL_UP)

# Battery measurement
vbat_adc = machine.ADC(badger2040.PIN_BATTERY)
vref_adc = machine.ADC(badger2040.PIN_1V2_REF)
vref_en = machine.Pin(badger2040.PIN_VREF_POWER)
vref_en.init(machine.Pin.OUT)
vref_en.value(0)

display = badger2040.Badger2040()

def map_value(input, in_min, in_max, out_min, out_max):
    return (((input - in_min) * (out_max - out_min)) / (in_max - in_min)) + out_min


def get_battery_level():
    # Enable the onboard voltage reference
    vref_en.value(1)

    # Calculate the logic supply voltage, as will be lower that the usual 3.3V when running off low batteries
    vdd = 1.24 * (65535 / vref_adc.read_u16())
    vbat = (vbat_adc.read_u16() / 65535) * 3 * vdd  # 3 in this is a gain, not rounding of 3.3V

    # Disable the onboard voltage reference
    vref_en.value(0)

    # Convert the voltage to a level to display onscreen
    return int(map_value(vbat, MIN_BATTERY_VOLTAGE, MAX_BATTERY_VOLTAGE, 0, 4))


def draw_battery(level, x, y):
    # Outline
    display.thickness(1)
    display.pen(15)
    display.rectangle(x, y, 19, 10)
    # Terminal
    display.rectangle(x + 19, y + 3, 2, 4)
    display.pen(0)
    display.rectangle(x + 1, y + 1, 17, 8)
    if level < 1:
        display.pen(0)
        display.line(x + 3, y, x + 3 + 10, y + 10)
        display.line(x + 3 + 1, y, x + 3 + 11, y + 10)
        display.pen(15)
        display.line(x + 2 + 2, y - 1, x + 4 + 12, y + 11)
        display.line(x + 2 + 3, y - 1, x + 4 + 13, y + 11)
        return
    # Battery Bars
    display.pen(15)
    for i in range(4):
        if level / 4 > (1.0 * i) / 4:
            display.rectangle(i * 4 + x + 2, y + 2, 3, 6)



def render():
    global centers, adjustment_tx, incerments
    display.pen(15)
    display.clear()
    display.pen(0)
    display.thickness(2)

    display.text("Frequency:",20,50,0.7) 
    display.text("{:3.3f} KHz".format(freq_set/1000), 150, 50, 0.7)

    display.text("Duty:",20,80,0.7) 
    display.text("{:d}/{:d}".format(duty, (100-duty)), 100, 80, 0.7)


    for i in range(len(adjustment_txt)):
        x = centers[i]-30
        display.text(adjustment_txt[i], x, 120, 0.7)


    display.pen(0)
    display.rectangle(0, 0, WIDTH, 16)
    display.thickness(1)
    draw_battery(get_battery_level(), WIDTH - 22 - 3, 3)
    display.pen(15)
    display.text("badgerOS", 3, 8, 0.4)

    display.update()

def button(pin):
    global freq_set, old_freq, increments, freq_increment_val, duty

    if button_user.value():  # User button is NOT held down
        if pin == button_a:
            duty = duty + increments[0]
            if duty == 100: #wrap duty between 90 and 10 - must always have at least one bit high
                duty = 10
            render()
        if pin == button_b:
            freq_increment_val = increments[1]
        if pin == button_c:
            freq_increment_val = increments[2]
        if pin == button_up:
            freq_set = min(10000000,(freq_set + freq_increment_val)) #No more than 10Mhz
            render()
        if pin == button_down:
            freq_set = max(1000,(freq_set - freq_increment_val)) #No less then 1Khz
            render()
    else:  # User button IS held down
        if pin == button_up:
            pass # add required function
            render()
        if pin == button_down:
            pass # add required function
            render()
        if pin == button_a:
            pass # add required function
            #inverted = not inverted
            #display.invert(inverted)
            render()


display.update_speed(badger2040.UPDATE_MEDIUM)
render()
display.update_speed(badger2040.UPDATE_FAST)


# Wait for wakeup button to be released
while button_a.value() or button_b.value() or button_c.value() or button_up.value() or button_down.value():
    pass


while True:
    if button_a.value():
        button(button_a)
    if button_b.value():
        button(button_b)
    if button_c.value():
        button(button_c)

    if button_up.value():
        button(button_up)
    if button_down.value():
        button(button_down)

    if freq_set != old_freq:
        set_clock_div() # set up state clock divisor for the streaming frequency required
        old_freq = freq_set
    
    if duty != old_duty:
        set_duty_cycle()
        old_duty = duty
    
    time.sleep(0.01)
