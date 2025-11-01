Named after the Rick and Morty device that powered a mini universe inside a car battery.

This project is a python based script for converting a Wii balance board into a "run in blace" monodirectional VR treadmill, by emulating either the W key, or joystick input for a gamepad controller. 

It measures the 4 corners of the balance board's analog weight sensors, avarages the left and right sensors, and looks for foot step padderns, to translate into a joystick or W key input. It also detects (albeit delayed) jumps via some kind of coding wizardry that I still don't fully understand.

Fair warning this project is JANK and mostly AI generated code from Deepseek, claud, and ChatGPT. theres features that do not work for some reason and idk why, and future prospects for this project beyond my abilities. I'm not a programmer, I'm just a 3D artist who wants to get a workout while in VR. Also this project only works on linux so far, I don't use Windows, and its detecting balance board inputs from the "dev/js#" path, which as far as I'm aware is a linux only thing. 

I'm not great at maintaining git repos either, but please feel free to contribute, cuz I barely understand what I'm doing and could use the help of some real programmers.

If you want to try this program, In the repo I've included the conda environment that I developed the program it in, which includes the dependancies. you should be able to set up the environment with 
```conda env create -f goobleboxvr.yml``` 
Also included is the Icon, desktop entry, and shell script for initializing gooblebox. I did NOT update the paths in the script and desktop entry, so you will have to replace the file path's manually. I'm so sorry, I honestly have no clue how to make user agnostic paths. in bash shell script. other than that ,once file paths are updated, running the script, or the desktop entry should bootup the python script.

again if you'd like to contribute and make my code not jank garbage, send a PR and dm me on discord, so I can check it out, or feel free to fork it into something way better.
Thanks FOSS community!
