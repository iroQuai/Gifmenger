#!/usr/bin/env python
# editted by gifmenger@stijnbiemans.nl 
# created by steve@stevesiden.com
# modified from chris@drumminhands.com
# see instructions at http://www.drumminhands.com/2014/06/15/raspberry-pi-photo-booth/

import os
import glob
import time
import traceback
from time import sleep
import atexit
import RPi.GPIO as GPIO  # using physical pin numbering change in future?
import picamera   # http://picamera.readthedocs.org/en/release-1.4/install2.html
import sys
import socket
import pygame  # pygame for displaying images
import config
import shutil
import random  # for choosing random status update
from PIL import Image, ImageDraw, ImageFont # for creating mosaics and other basic image things. use Pillow implementation
from twython import Twython # twitter library

########################
### System Config ###
########################

post_online_now = 1  # default 0. Change to 1 if you want to upload pics IMMEDIATELY
post_online_idle = 1 # default 1. change to 0 if you dont want to upload pics even when idle
backup_pics = 1  # backup pics = 1, no backup, change to 0
fullscreen = 1  # set pygame to be fullscreen or not - useful for debugging
real_path = os.path.dirname(os.path.realpath(__file__)) # path of code for references to pictures
idle_time = 20  # time in seconds to wait to idle stuff
missedfile_appendix = "-FILENOTUPLOADED" # thing added to end of file if it wasnt uploaded

photobooth_in_use = False
time_since_last_use =0
time_gap=1 # debounce time - duration before photos can be taken again

########################
### Camera Config ###
########################

# 2592x1944 1296x972 1296x730 640x480 - use one of these to keep sensor full size
# this is 1.25 size of 640x480 - this allows keeps correct aspect ratio but maximises the use of the screen.
# images resized by gpu when taking picture as its quicker
pixel_width = 800
pixel_height = 600

camera_vflip = False
camera_hflip = True

total_pics = 4  # number of pics to be taken
capture_delay = 1  # delay between pics
prep_delay = 5  # number of seconds at step 1 as users prep to have photo taken
restart_delay = 10  # how long to display finished message before beginning a new session


########################
### Gif Config ###
########################

gif_delay = 25  # How much time between frames in the animated gif - in 100ths of second
gif_width = 640  #  dimensions of the gif to be uploaded - based on the maximum size twitter allows, make integer scale factor of the image resolution for faster scaling
gif_height = 480

########################
### Monitor Config ###
########################

monitor_w = 1024  #1024 # this is res of makibes 7" screen
monitor_h = 600  #600
replay_delay = (1.0 * gif_delay) / 100  # how much to wait in-between showing pics on-screen after taking
replay_cycles = 3  # how many times to show each photo on-screen after taking

########################
### Countdown Config ###
########################

fnt = ImageFont.truetype(real_path + "/assets/FreeSerif.ttf", 200) #font used to overlay on pictures during countdown
countdown_number = 3  # time to countdown with overlay before starting 3
countdown_time = .5
overlay_alpha = 28  # opacity of overlay during countdown 28

overlaytext_x = monitor_w / 2  # monitor_w / 2 - 100
overlaytext_y = monitor_h / 2  # monitor_h / 4 -50

########################
### Internet Config ###
########################

test_server = 'www.google.com'

#setup the twitter api client
twitter_api = Twython(
    config.twitter_CONSUMER_KEY,
    config.twitter_CONSUMER_SECRET,
    config.twitter_ACCESS_KEY,
    config.twitter_ACCESS_SECRET,
)

hashtags = "#gifmengsel #test"

statuses = [
    "Beep Boop! I was programmed to love!",
    "Weddings are fun! Beep Boop!",
    "Beep Boop! A memento of the day!",
    "Don't they look great!?",
    "I'm ready for my close up",
    "Smile! You're on Clarl cam!",
    "Say cheese! You're crackers!",
    "I heart Clarl!"
]

####################
### GPIO Config ####
####################

# LED pins

countdown_led1_pin = 2  # 
countdown_led2_pin = 3  # 
countdown_led3_pin = 4  #

countdown_array = [ countdown_led1_pin, countdown_led2_pin, countdown_led3_pin]

idle_led_pin = 12 # voor de rode knop + evt 'klaar voor gebruik' lampje

photo_indicator_pin = 17  # 
processing_indicator_pin = 22  # 
uploading_indicator_pin = 27   #

# Button pins

Start_Photobooth_pin = 23  # pin for the big red button to start the photobooth going
Exit_Photobooth_pin = 24   # pin for button to end program
button3_pin = 25  # extra button for something

GPIO.setmode(GPIO.BCM)  # use the normal wiring numbering
GPIO.setwarnings(False)  # ignore warnings if cleanup didnt run somehow
GPIO.setup(Start_Photobooth_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # falling edge detection on button 1
GPIO.setup(Exit_Photobooth_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # falling edge detection on button 2
GPIO.setup(button3_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # falling edge detection on button 3

#################
### Functions ###
#################


def cleanup():
    print('Ended abruptly')
    GPIO.cleanup()
    pygame.quit()


def shut_it_down():
    print "Shutting down..."
    #GPIO.output(led1_pin,True)
    GPIO.output(photo_indicator_pin, True)
    #GPIO.output(led3_pin,True)
    #GPIO.output(led4_pin,True)
    os.system("sudo halt")


def led_init():
    GPIO.setup(countdown_led1_pin,GPIO.OUT)
    GPIO.setup(countdown_led2_pin,GPIO.OUT)
    GPIO.setup(countdown_led3_pin,GPIO.OUT)
    GPIO.setup(photo_indicator_pin,GPIO.OUT)
    GPIO.setup(processing_indicator_pin,GPIO.OUT)
    GPIO.setup(uploading_indicator_pin,GPIO.OUT)
    GPIO.setup(idle_led_pin,GPIO.OUT)

def led_all_off():
    # set all low
    GPIO.output(countdown_led1_pin,0)
    GPIO.output(countdown_led2_pin,0)
    GPIO.output(countdown_led3_pin,0)
    GPIO.output(photo_indicator_pin,0)
    GPIO.output(processing_indicator_pin,0)
    GPIO.output(uploading_indicator_pin,0)
    GPIO.output(idle_led_pin,0)

def led_all_on():
    # set all low
    GPIO.output(countdown_led1_pin,1)
    GPIO.output(countdown_led2_pin,1)
    GPIO.output(countdown_led3_pin,1)
    GPIO.output(photo_indicator_pin,1)
    GPIO.output(processing_indicator_pin,1)
    GPIO.output(uploading_indicator_pin,1)
    GPIO.output(idle_led_pin,1)

def exit_photobooth(self):
    print "Photo booth app ended. RPi still running"
    led_all_on()
    sleep(1)
    led_all_off()
    sleep(1)
    led_all_on()
    sleep(1)
    led_all_off()
    cleanup()
    raise SystemExit


def clear_pics(foo): #why is this function being passed an arguments?
    #delete files in folder on startup
    files = glob.glob(config.file_path + '*')
    for f in files:
        os.remove(f)
    #light the lights in series to show completed
    print "Deleted previous pics"
    #GPIO.output(led1_pin,False) #turn off the lights
    #GPIO.output(photo_indicator_pin, False)
    #GPIO.output(led3_pin,False)
    #GPIO.output(led4_pin,False)


def is_connected():
    try:
    # see if we can resolve the host name -- tells us if there is
    # a DNS listening
        host = socket.gethostbyname(test_server)
    # connect to the host -- tells us if the host is actually
    # reachable
        s = socket.create_connection((host, 80), 2)
        return True
    except:
        pass
    return False


def upload_single_missingfile():
    checkstr = config.file_path + "*" + missedfile_appendix + "*"
    #print "Checking with string :" + checkstr
    filesnotuploaded = glob.glob(config.file_path + "*" + missedfile_appendix + "*")
    print "found following files : "
    print filesnotuploaded
    numfound = len(filesnotuploaded)
    print "numfound : " + str(numfound)
    if numfound > 0:
        targetint = random.randint(0,numfound-1)
        print "targentint : " + str(targetint)
        target_name = os.path.basename(filesnotuploaded[targetint])
        print "current file :" + target_name
        name_split = str.split(target_name, missedfile_appendix)
        filetoupload = name_split[0]
        if os.path.exists(config.file_path + filetoupload + ".gif"):
            try:
                tweet_pics(filetoupload)
                pics_backup(filetoupload)
                gif_backup(filetoupload)
                print "tweeting ok"
                os.remove(config.file_path + target_name)
            except Exception, e:
                tb = sys.exc_info()[2]
                traceback.print_exception(e.__class__, e, tb)           
                print "tweeting didnt work, keeping failure flag"
        else:
            print "couldnt find gif deleting backupflag"
            os.remove(photopath + target_name)
    else:
        print "no missing uploads found"


def idle_stuff():
    connected = is_connected()
    
    if connected and post_online_idle: # if we have internet AND we are set to upload when idle
        print "uploading missing files"
        upload_single_missingfile()
    else:
        print "not connected :("


def init_pygame():
    pygame.init()  # start the pygame instance
    # set screen size
    if fullscreen:
        size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
    else:
        size = [monitor_w, monitor_h]
    # more pygame setup
    pygame.display.set_caption('Photo Booth Pics')
    pygame.mouse.set_visible(False)  # hide the mouse cursor
    # return the pygame object with correct size
    if fullscreen:
        return pygame.display.set_mode(size, pygame.FULLSCREEN)
    else:
        return pygame.display.set_mode(size)


def makeoverlay(string_to_display):
    # create image size of monitor - this can be any arbitrary size
    img_orig = Image.new("RGB", (monitor_w, monitor_h))  # no inputs mean filled with black
    # create drawing object
    draw = ImageDraw.Draw(img_orig)
    # draw text in image, this should *hopefully* be in the middle of the display
    draw.text((overlaytext_x, overlaytext_y), string_to_display, (255, 255, 255),
              font=fnt)  # text is white using font defined above
    # pad the image into the allowed buffer size of multiples of 32 * 16
    img_padded = Image.new('RGB', (
        ((img_orig.size[0] + 31) // 32) * 32,
        ((img_orig.size[1] + 15) // 16) * 16,
    ))
    # Paste the original image into the padded one
    img_padded.paste(img_orig, (0, 0))
    return img_padded


def countdown_overlay(camera):
    # display countdown as overlay on preview

    # start with no overlay
    overlay_renderer = None

    # loop through countdown values (3,2,1) displaying text
    for j in range(1, countdown_number + 1):
        # create image with text located in centre - correct size
        overlay_cur = makeoverlay(str((countdown_number + 1) - j))
        # overlay this on screen, starting overlay if necessary
        if not overlay_renderer:
            overlay_renderer = camera.add_overlay(overlay_cur.tostring(), layer=3, size=overlay_cur.size, alpha=overlay_alpha)
        else:
            overlay_renderer.update(overlay_cur.tostring())
        GPIO.output(countdown_array[j -1], True) 
        time.sleep(countdown_time)

    # when this is finished, hide overlay by making it blank DO WE NEED THIS? CANT WE SET LAYER TO 2 OR REMOVE IT?
    #overlay_cur = makeoverlay("")
    #overlay_renderer.update(overlay_cur.tostring())
    camera.remove_overlay(overlay_renderer)


def show_image(img_fname, screen=0):
    if not screen:
        screen = init_pygame()
    img = pygame.image.load(img_fname)
    img_h = img.get_height()
    img_w = img.get_width()

    if img_h == monitor_h and img_w == monitor_w:
        #img = pygame.transform.scale(img)
        offset_x = 0
        offset_y = 0
    else:
        y_scale_factor = monitor_h / (1.0 * img_h)  # force float
        transform_y = int(img_h * y_scale_factor)
        transform_x = int(img_w * y_scale_factor)
        offset_x = (monitor_w - transform_x) / 2
        offset_y = 0
        img = pygame.transform.scale(img, (transform_x, transform_y))
    screen.blit(img, (offset_x, offset_y))
    pygame.display.flip()  # update the display


def tweet_pics(jpg_group):
    # get filename for this group of photos
    now = jpg_group
    fname = config.file_path + now + '.gif'
    # choose new status from list and at the hashtags
    status_choice = random.choice(statuses)
    status_total = status_choice + " " + hashtags
    print "Tweeting: " + fname + " with status : " + status_total
    twitter_photo = open(fname, 'rb')  # open file
    response = twitter_api.upload_media(media=twitter_photo)  # upload to twitter
    # update status with image and new status
    twitter_api.update_status(media_ids=[response['media_id']], status=status_total)


def display_pics(jpg_group):
    # display all of the images with the same name
    # make a pygame screen object, reusing this each time prevents the black screen between each image
    screen = init_pygame()
    for i in range(0, replay_cycles):  # show pics a few times
        for i in range(1, total_pics+1):  # show each pic
            filename = config.file_path + jpg_group + "-0" + str(i) + ".jpg"
            show_image(filename,screen)
            time.sleep(replay_delay)  # pause


def pics_backup(now):
    # copy the pictures into the backup folder
    print "Backing Up Photos " + now
    shutil.copy(config.file_path + now + '-01.jpg', config.backup_path)
    shutil.copy(config.file_path + now + '-02.jpg', config.backup_path)
    shutil.copy(config.file_path + now + '-03.jpg', config.backup_path)
    shutil.copy(config.file_path + now + '-04.jpg', config.backup_path)
    #shutil.copy(config.file_path + now + '.gif', config.backup_path)
    

def gif_backup(now):
    print "Backing Up gif " + now
    shutil.copy(config.file_path + now + '.gif', config.backup_path)


# define the photo taking function for when the big button is pressed

def photobooth_callback(self):
    #global variables for checking if button is in use
    global time_since_last_use
    global photobooth_in_use

    # time since last called
    duration = time.time() - time_since_last_use

    if duration > time_gap:
        if not photobooth_in_use:
            print "photobooth not in use so we can use it"
            start_photobooth(self)
            print "callback done"
            time_since_last_use=time.time()
        else:
            print "photobooth assets already in use, doing nothing"


def start_photobooth(self):
    global photobooth_in_use
    photobooth_in_use = True # set global variable in use
    GPIO.output(idle_led_pin, True)
    ################################# Begin Step 1 #################################
    screen = init_pygame() # start pygame screen
    
    show_image(real_path + "/assets/blank.png",screen) # show blank screen when loading
    print "Get Ready"
    GPIO.output(idle_led_pin, False) #idle knop uitzetten
    #GPIO.output(photo_indicator_pin, False)  #turn big led off

    show_image(real_path + "/assets/instructions.png", screen) # display instructions - this saying takes 4 photos etc.

    #  flash the leds for more indication
    led_all_on()
    sleep(1.0*prep_delay/6)
    led_all_off()
    sleep(1.0*prep_delay/6)
    led_all_on()
    sleep(1.0*prep_delay/6)
    led_all_off()
    sleep(1.0*prep_delay/6)
    led_all_on()
    sleep(1.0*prep_delay/6)
    led_all_off()
    sleep(1.0*prep_delay/6)

    show_image(real_path + "/assets/blank.png", screen)
    #setup camera
    camera = picamera.PiCamera()
    camera.resolution = (pixel_width, pixel_height)
    camera.vflip = camera_vflip
    camera.hflip = camera_hflip
    camera.start_preview()

    sleep(1) # warm up camera - this lets it settle focus colour balance etc.

    ################################# Begin Step 2 #################################
    print "Taking pics"
    now = time.strftime("%Y%m%d%H%M%S") # get the current date and time for the start of the filename
    try: # take the photos
        #for i, filename in enumerate(camera.capture_continuous(config.file_path + now + '-' + '{counter:02d}.jpg')):
        for i in range(0, total_pics):
            countdown_overlay(camera)
            filename = config.file_path + now + '-0' + str(i+1) + '.jpg'
            GPIO.output(photo_indicator_pin, True)  # turn on the LED
            camera.capture(filename, resize=(gif_width, gif_height)) # TAKE ACTUAL PHOTO
            print(filename)
            led_all_off()
            sleep(capture_delay)  # pause in-between shots
            if i == total_pics-1:
                break
    finally:
        camera.stop_preview()
        camera.close()
        
    ########################### Begin Step 3 #################################

    GPIO.output(processing_indicator_pin, True)  # turn on the LED

    print "Creating an animated gif"
      
    show_image(real_path + "/assets/processing.png",screen) # show processing info
    pics_backup(now)  # backup pictures into folder *BEFORE* they get resized

    # prepare the gif conversion string
    graphicsmagick = "gm convert -size " + str(gif_width) + "x" + str(gif_height) + " -delay " + str(gif_delay) + " " + config.file_path + now + "*.jpg " + config.file_path + now + ".gif"
    os.system(graphicsmagick) # make the .gif

    needtobackup = 1
    if post_online_now:  # turn off posting pics online in the variable declarations at the top of this document
        print "Uploading to twitter Please check @Gifmengsels soon."
        show_image(real_path + "/assets/uploading.png",screen)
        connected = is_connected() # check to see if you have an internet connection
        if not connected:
            needtobackup = 1
        while connected:
            try:
                print "We have internet. Uploading now"
                GPIO.output(uploading_indicator_pin, True)  # turn on the LED
                tweet_pics(now)  # tweet pictures  - THIS IS WHERE WE SHOULD HAVE A TIMEOUT SET SOMEHOW
                gif_backup(now)
                needtobackup = 0
                print "tweeting ok"
                break
            except ValueError:
                print "Oops. No internect connection. Upload later."
                needtobackup = 1

    if needtobackup:
        try:  # make a text file as a note to upload the .gif later
            file_flag = open(config.file_path + now + "-FILENOTUPLOADED.txt",'w')   # Trying to create a new file or open one
            file_flag.close()
        except:
            print('Something went wrong. Could not write file.')
            #sys.exit(0) # quit Python

    # turn off the leds now

    GPIO.output(processing_indicator_pin, False)  # turn on the LED
    GPIO.output(uploading_indicator_pin, False)  # turn on the LED

    ########################### Begin Step 4 #################################

    #GPIO.output(led4_pin,True) #turn on the LED
    try:
        display_pics(now) # display all the pictures in sequence - this is faster than showing the gif
    except Exception, e:
        tb = sys.exc_info()[2]
        traceback.print_exception(e.__class__, e, tb)

    print "All Photobooth stuff Done"

    if post_online_now or post_online_idle:
        show_image(real_path + "/assets/finished_connected.png",screen)
    else:
        show_image(real_path + "/assets/finished_offline.png",screen)
    
    time.sleep(restart_delay)
    pygame.quit()  # we are done with this instance of pygame
    show_image(real_path + "/assets/intro.png")
    GPIO.output(idle_led_pin,1) #idle knop aanzetten
    #GPIO.output(photo_indicator_pin, True)  # turn on the LED
    photobooth_in_use = False
    


########################################################################################################################

####################
### Main Program ###
####################

# add cleanup command to atexit, to ensure it runs when program stops for whatever reason
atexit.register(cleanup)

led_init()
#start with all leds off
led_all_off()

### GPIO SETUP ###

# when a falling edge is detected on button2_pin and button3_pin, regardless of whatever
# else is happening in the program, their function will be run

# Shut down Pi
GPIO.add_event_detect(button3_pin, GPIO.FALLING, callback=shut_it_down, bouncetime=300)

# Button to close python
GPIO.add_event_detect(Exit_Photobooth_pin, GPIO.FALLING, callback=exit_photobooth, bouncetime=2000) #use button to exit python. Good while developing

# Start Photobooth
GPIO.add_event_detect(Start_Photobooth_pin, GPIO.FALLING, callback=photobooth_callback, bouncetime=300) #button to start photobooth

# Check which frame buffer drivers are available
# Start with fbcon since directfb hangs with composite output
drivers = ['fbcon', 'directfb', 'svgalib']
found = False
for driver in drivers:
    # Make sure that SDL_VIDEODRIVER is set
    if not os.getenv('SDL_VIDEODRIVER'):
        os.putenv('SDL_VIDEODRIVER', driver)
    try:
        pygame.display.init()
    except pygame.error:
        print 'Driver: {0} failed.'.format(driver)
        continue
    found = True
    break

if not found:
    raise Exception('No suitable video driver found!')


print "Deleting old files"
# delete files in folder on startup
#files = glob.glob(config.file_path + '*')
#for f in files:
#    os.remove(f)

print "Photo booth app running..."
# light up the lights to show the app is running

led_all_on()

time.sleep(3)

led_all_off()

show_image(real_path + "/assets/intro.png")

#turn on the LED in the big button
#GPIO.output(photo_indicator_pin, True)

tstart = time.time()

# MAIN LOOP
try:
    while True:
        tcurrent = time.time()
        # if idle time reached, then run the commands in the idle function, like upload
        if ((tcurrent - tstart) > idle_time) and not photobooth_in_use:
            print "do idle stuff"
            idle_stuff()
            tstart = tcurrent
        else:
            time.sleep(.1)
finally:
    cleanup()
    print "finally bit"

#except KeyboardInterrupt:
#    print "Interupt keyboard"
#    cleanup()

cleanup()  # cleanup on normal exit

