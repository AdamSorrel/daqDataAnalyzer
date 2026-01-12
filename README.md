# DAQ data analyzer

This is a program that was designed to help visualize and to some extent analyze data from the DAQ related to a Raman flow (LINK).  

## Running the program

The program usues python v3.11.5 a PyQt6 graphical user interface and has a few basic requirements listed bellow:
- PyWavelets (v1.8.0)
- pandas (v2.0.3)
- numpy (v1.26.0)
- pyqtgraph (v0.13.3)
- scipy (v1.11.13)

Other versions of these packages might work, but have not been tested. 

## Loading data

Upon loading the GUI, the data can be loaded using the item "File" in the menu bar on the top of the screen and inside a button "Open". This will open a dialog to select a text file with the DAQ data. Data is expectedin a tab separated format with the first column being the time stamp in UNIX format and the remaining columns are channel values 1 to 3 respectively. 

> [!NOTE]
> Data loading progress is shown in a progress bar as well as printed in a command line where the program has been started. However, the data will only be shown upon refreshing the screen with one of the arrows in the "Raw data plot" widget or upon clicking the button "update".

## Data view adjustment

On the top of the "Raw data plot" widget, you can see arrows to move up and down the data points. The step size of this movement is adjusted in the counter on the right of the arrows. All elements are labelled with text which should appear upon hovering over the element and waiting for a moment. 

The window size (width of the viewed area) can be adjusted in the middle counter and the position of the beginning of the current window can be set manually in the third counter.

With larger window widths (more data visualized), it is a good idea to downsample the data to speed the visualization. This can be done in the rightmost part of the top panel. Several options are available, all of which are largely equivalent. The view will be automatically updated upon a selection choice. These options do not have any effect on the dataset and are fully reversible.

## Setting a threshold value for peak detection

