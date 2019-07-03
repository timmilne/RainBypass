import urllib2
import json
import time
import RPi.GPIO as GPIO ##Import GPIO library
import os

## Setup GPIO I/O PIns to output mode
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)
GPIO.setup(7, GPIO.OUT) ## This pin controls relay switch. When ON/True, watering is disabled and the yellow light is illuminated. Default OFF
GPIO.setup(11, GPIO.OUT) ## This pin controls red light that is illuminated when there is a data error
GPIO.setup(13, GPIO.OUT) ## This pin controls blue light when watering enabled
GPIO.setup(15, GPIO.OUT) ## This pin controls green light when system ok

darkSkyKey = "f050a1d8c2e5a35e5dbbd81b43e2ba28" ## Enter your DarkSky key acquired by joining weather DarkSky api program
latLon = "0,0" ## Latitude/Longitude for the weather request - string
lastRain = 0 ## Hold epoch of last rain - float
checkIncrement = 0  ## Amount of time between weather forecast requests - integer
daysDisabled = 0 ## Days to disable systems prior to and after rain - integer
rainForecasted = False ## Is rain forecasted within daysDisabled forecast range - Boolean, global

## Define conditions that will disable watering: rain (in icon or precipType)
## DarkSky: https://darksky.net/dev/docs#response-format
possibleConditions = ["rain",
                      ]

##This funtion gets the path of this file.  When run at startup, we need full path to access config file
##To run this file automatically at startup, change permission of this file to execute
##If using wireless for network adapter, make sure wireless settings are configured correctly in wlan config so wifi device is available on startup
##edit /etc/rc.local file 'sudo pico /etc/rc.local'
##add "python /home/pi/working-python/weather-json.py &" before line "exit 0"
def GetProgramDir():
   try:  ## If running from command line __file__ path is defined
      return os.path.dirname(os.path.abspath(__file__)) + "/"
   except:  ## If __file__ is undefined, we are running from idle ide, which doesn't use this var
      return os.getcwd() + "/"

## Load values from config file, or create it and get values
try: ## see if config file exists
    configFile = open(GetProgramDir() + "bypass.cfg","r")  ## Attempt to open existing cfg file
    print "Config file found, loading previous values..."
    latLon = configFile.readline().rstrip() ## lat/lon is a string
    daysDisabled = int(configFile.readline()) ## Convert second line to int and store in daysDisabled var
    checkIncrement = int(configFile.readline()) ## Conver third line to int and store in checkIncrement var
    configFile.close()
except: ## Exception: config file does not exist, create new
    print "Config file not found, creating new..."

    ## Request lat/long for request
    latLon = raw_input("Enter lat,lon (comma separated): ")

    ## input number of days system will be disabled prior to rain, and after rain
    daysDisabled = int(raw_input("Enter number of days to disable system prior/after rain (between 1 and 9): "))

    ## request number of checks in 24 hour period
    checkIncrement = int(raw_input("Enter number of times you want to check forecast per 24-hour period (no more than 500, try 24, or once per hour): "))
    checkIncrement = 86400/checkIncrement ## This is the wait interval between each check in seconds
    
    ## Save user input to new config file
    configFile = open(GetProgramDir() + "bypass.cfg","w")
    configFile.write(latLon + "\n" + str(daysDisabled) + "\n" + str(checkIncrement) + "\n") ## Write each item to new line
    configFile.close()

## Show values/interval used to check weatherc
print "Checking forecast for lat/lon: " + latLon
print "System will be disabled for " + str(daysDisabled) + " days prior to and after rain"
print "System will wait " + str(checkIncrement) + " seconds between checks"
print "     or " + str(float(checkIncrement) / 60) + " minute(s) between checks"
print "     or " + str(float(checkIncrement) / 3600) + " hour(s) between checks"

def CheckWeather():

    ## This function will modify the following variables in the main scope
    global rainForecasted
    global lastRain
    
    while True: ## Loop this forever
        try:
            ##Gather inputs
            ##Request Weather Data
            options = "?exclude=currently,minutely,hourly,alerts,flags"
            darkSkyURL = "https://api.darksky.net/forecast/" + darkSkyKey + "/" + latLon + options
            print "Weather service URL: " + darkSkyURL + "\n"
            request = urllib2.Request(darkSkyURL) ## 8-day forecast
            response = urllib2.urlopen(request)

            ## Parse json into array with only time, icon, precipIntensity, precipProbably and precipType
            jsonData = json.load(response)

            print "\n### START DarkSky Data ###"
            ## Extract the times
            forecastTimes = ExtractValues(jsonData, 'time')
            print("forecastTimes: ", forecastTimes)

            ## Extract the forecast icons (remove the summary icon)
            forecastIcons = ExtractValues(jsonData, 'icon')
            del forecastIcons[0]
            print("8 Day Forecast: ", forecastIcons)

            ## Extract the precipProbabilities
            forecastProbabilities = ExtractValues(jsonData, 'precipProbability')
            print("forecastProbabilities: ", forecastProbabilities)

            ## Extract the precipIntensities
            forecastIntensities = ExtractValues(jsonData, 'precipIntensity')
            print("forecastIntensities: ", forecastIntensities)
            
            ## Extract the precipTypes
            forecastTypes = ExtractValues(jsonData, 'precipType')
            print("forecastTypes: ", forecastTypes)
            print "### END DarkSky Data ###"

            ##Check current day for rain
            print "\n### START Checking if raining TODAY ###"
            if(CheckCondition(forecastIcons[0])): ## If is raining today
                lastRain = float(forecastTimes[0]) ## Save current rain forecast as last rain globally
                print "It will rain today. Storing current epoch as 'last rain': " + str(lastRain)
            else:
                print "No rain today"
            print "### END Checking if raining now ###\n"

            ##Check if rain is forecast within current range not to exceed forecast
            forecastRange = range(1, (1+(daysDisabled if daysDisabled < len(forecastTimes) else len(forecastTimes))))
            print "### START Checking for rain in forecast range ###"
            for x in forecastRange:
                print "Checking " + str(forecastTimes[x]) + " for rain conditions:"
                if(CheckCondition(forecastIcons[x])):
                   print("Rain has been forecast. Disabling watering")
                   rainForecasted = True ##Set global variable outside function scope
                   break
                else:
                   print("No rain found for day ", x, " in forecast. Watering may commence")
                   rainForecasted = False ##Set global variable outside function scope
            print "### END Checking if rain in forecast range ###\n"

            ## Now that we know current conditions and forecast, modify watering schedule
            ModifyWatering()

            GPIO.output(11,False) ## Turn off red data error light if on, routine successful
            GPIO.output(15,True)  ## Turn on the green status indicator light
            print "\nChecking forecast again in " + str(checkIncrement / 60) + " minute(s)"
            time.sleep(checkIncrement)
            
        except: ## Data unavailable - either connection error, or network error
            GPIO.output(11,True)  ## Turn on red data error light, routine unsuccessful
            GPIO.output(15,False) ## Turn off the green status indicator light
            GPIO.output(13,False) ## Turn off the blue watering indicator light
            print "Error contacting darksky.com. Trying again in " + str(checkIncrement / 60) + " minute(s)"
            time.sleep(checkIncrement)  ## Reattempt connection in 1 increment

def ExtractValues(obj, key):
    ## Pull all values of spceified key from nested JSON.
    arr = []

    def ExtractValue(obj, arr, key):
        ## Recursive search for values of key in JSON tree.    
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    ExtractValue(v, arr, key)
                elif k == key:
                    arr.append(v)
        elif isinstance(obj, list):
            for item in obj:
                ExtractValue(item, arr, key)
        return arr

    results = ExtractValue(obj, arr, key)
    return results

def CheckCondition(value):
    for x in possibleConditions:
        if value == x:
            print 'Rain condition found';
            return True

def ModifyWatering():
    print "\nLast rain from forecast timestamp: " + str(lastRain)
    print "Current Time: " + str(time.time())
    print "Days since last rain: " + str((time.time() - lastRain)/86400 )
    print "Seconds since last rain: " + str(time.time() - lastRain)
    print "Days disabled in seconds: " + str(daysDisabled * 86400)
    print "Has NOT rained within daysDisabled range: " + str(time.time() - lastRain >= daysDisabled * 86400)

    if(rainForecasted == False and time.time() - lastRain >= daysDisabled * 86400):
        print "Hasn't rained in a while, and not expected to rain. Watering enabled."
        GPIO.output(7,False) ## Turn off relay switch and the yellow light, enable watering
        GPIO.output(13,True) ## Turn on blue light
        GPIO.output(15,False) ## Turn on green light
    else:
        GPIO.output(7,True) ## Turn on relay switch and the yellow light, disable watering
        GPIO.output(13,False) ## Turn off blue light
        GPIO.output(15,True) ## Turn on green light
        if(rainForecasted):
            print "Rain is forecasted, or raining today. Watering Disabled"
        else:
            print "Rain not in forecast, but it has rained recently. Watering Disabled"
        
## Init Forecast method
CheckWeather()
