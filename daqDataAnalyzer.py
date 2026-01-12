import sys, datetime, time, pickle
import numpy as np
import pandas as pd
import pywt

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog, QProgressDialog, QWidget
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.uic import loadUi
import pyqtgraph as pg

from scipy.signal import find_peaks

class loadingBarThread(QThread):
    progress = pyqtSignal(int)
    def __init__(self, inputFile, parent):
        self.inputFile = inputFile
        self.parent = parent
        super().__init__()
        print("[loadingBarThread] Loading bar initialized.")   
    
    def run(self):
        with open(self.inputFile, "rb") as f_in:
            fileLines = f_in.readlines()
            count = len(fileLines) + 10000   # 10k padding extra for those malformed double lines.
            timeIndex = np.array(np.zeros(count), dtype=np.float64)
            ch1 = np.array(np.zeros(count), dtype=np.float32)
            ch2 = np.array(np.zeros(count), dtype=np.float32)
            ch3 = np.array(np.zeros(count), dtype=np.float32)
            n = 0
            for line in fileLines:
                line = line.decode().rstrip()
                if len(line) == 0:
                    continue
                # Splitting using one white space (there are either 1 or 2 white places)
                # This will normally generate multiple empty strings, which are removed in the loop
                line = [i for i in line.split(" ") if i]
                # This splits also the date, which needs to be stitched back together
                
                timeIndex[n] = line[0]
                ch1[n] = float(line[1])
                ch2[n] = float(line[2])
                ch3[n] = float(line[3])
                        
                n += 1
                if n%1000 == 0:
                    print(f"Progress : {(n/count)*100:0.2f}%", end="\r")
                    self.progress.emit(int((n/count)*100))
    
            # Constructing the final data frame
            df1 = pd.DataFrame({"Channel 1": ch1, "Channel 2": ch2, "Channel 3": ch3}, index=timeIndex)
            #df1 = df1.iloc[:-6548]
            df1 = df1[df1.index != 0]
            df1 = df1.sort_index()

            df1.index = df1.index - min(df1.index)

            self.parent.data = df1.copy(deep=True)
            self.parent.dataOriginal = df1.copy(deep=True)
    
    def exit(self):
        exit()
        
class rawPlot(QWidget):
    def __init__(self):
        super().__init__()
        self.canvas = pg.GraphicsLayoutWidget()

class waveletPlot(QWidget):
    def __init__(self):
        super().__init__()
        self.waveletCanvas = pg.GraphicsLayoutWidget()

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        loadUi("daqDataAnalyzer.ui", self)

        self.setWindowTitle("My App")

        """
        #Loading menu actions
        """
        self.actionOpen.triggered.connect(self.loadFile)
        self.actionExit.triggered.connect(self.exitProgram)
        self.inputFile = ""

        self.data = None

        """
        #Raw plot tab
        """
        self.rawPlotUpdateBtn.clicked.connect(self.updateRawPlot)
        self.rawPlotBackBtn.setToolTip("Move window a step back")
        self.rawPlotBackBtn.clicked.connect(self.backButtonCallback)
        self.rawPlotForwardBtn.setToolTip("Move window a step forward")
        self.rawPlotForwardBtn.clicked.connect(self.forwardButtonCallback)
        self.rawWindowSizeSpinBox.setToolTip("Window size")
        self.rawWindowSizeSpinBox.valueChanged.connect(self.updateRawPlot)
        self.rawStepSizeSpinBox.setToolTip("Step size")
        self.rawWindowStartSpinBox.setToolTip("Window start position")
        self.rawWindowStartSpinBox.valueChanged.connect(self.updateRawPlot)
        self.downsamplingComboBox.setToolTip("Downsampling options")
        self.downsamplingComboBox.currentTextChanged.connect(self.downsamplingUpdate)
        ####
        self.rawPlotThreshold1.setToolTip("Threshold plot 1")
        self.rawPlotThreshold1.valueChanged.connect(lambda: self.updateTheshold(1))
        self.rawPlotThreshold2.setToolTip("Threshold plot 2")
        self.rawPlotThreshold2.valueChanged.connect(lambda: self.updateTheshold(2))
        self.rawPlotThreshold3.setToolTip("Threshold plot 3")
        self.rawPlotThreshold3.valueChanged.connect(lambda: self.updateTheshold(3))
        self.axisCh1ShiftSpinBox.valueChanged.connect(self.shiftChannelTime)
        self.axisCh2ShiftSpinBox.valueChanged.connect(self.shiftChannelTime)
        self.axisCh3ShiftSpinBox.valueChanged.connect(self.shiftChannelTime)
        ####
        self.selectChannelCBox.setToolTip("Select channel to analyze")
        self.selectChannelCBox.currentTextChanged.connect(self.updateWaveletPlot)
        self.waveletBackBtn.clicked.connect(self.backButtonCallback)
        self.waveletForwardBtn.clicked.connect(self.forwardButtonCallback)
        self.applyWaveletBtn.clicked.connect(self.applyWaveletFilter)
        self.refreshWaveletPlotBtn.clicked.connect(self.updateWaveletPlot)
        self.selectWaveletCBox.currentTextChanged.connect(self.updateWaveletPlot)
        self.waveletFamilyCBox.currentTextChanged.connect(self.updateWaveletCBox)
        for family in pywt.families():
            self.waveletFamilyCBox.addItem(family)
        """
        # Finding peaks tab
        """
        self.findPeaksBtn.clicked.connect(self.findPeaks)
        self.savePeaksBtn.clicked.connect(self.savePeaks)

        """
        # Raw data plotting
        """
        self.rawDataCanvas = pg.GraphicsLayoutWidget()
        self.rawPlotLayout.addWidget(self.rawDataCanvas)
        # PyQtGraph Plot item
        self.rawDataPlot1 = self.rawDataCanvas.addPlot(row=0, col=0)
        self.rawDataPlot2 = self.rawDataCanvas.addPlot(row=1, col=0)
        self.rawDataPlot3 = self.rawDataCanvas.addPlot(row=2, col=0)

        # Getting axis items
        self.ax1 = self.rawDataPlot1.getAxis("right")
        self.ax2 = self.rawDataPlot2.getAxis("right")
        self.ax3 = self.rawDataPlot3.getAxis("right")
        # Showing right axes on both left and right size
        for plot in [self.rawDataPlot1, self.rawDataPlot2, self.rawDataPlot3]:
            plot.showAxes((True, False, True, True))
            
        # Connect the signal for range change
        #self.rawDataPlot1.getViewBox().sigXRangeChanged.connect(self.axisRangeCallback)

        # X axis labels
        self.rawDataPlot1.setLabel("bottom", "Time", "s")
        self.rawDataPlot2.setLabel("bottom", "Time", "s")
        self.rawDataPlot3.setLabel("bottom", "Time", "s")
        # Y axis labels
        self.rawDataPlot1.setLabel("left", "Voltage", "V")
        self.rawDataPlot2.setLabel("left", "Voltage", "V")
        self.rawDataPlot3.setLabel("left", "Voltage", "V")

        self.rawDataLineColor1 = "#1f77b4"
        self.rawDataLineColor2 = "#ff7f0e"
        self.rawDataLineColor3 = "#d62728"
        self.backgroundColor = "#FFFFFF"

        self.rawDataCanvas.setBackground(self.backgroundColor)

        self.rawDataPen1 = pg.mkPen(color=self.rawDataLineColor1, width=2)
        self.rawDataPen2 = pg.mkPen(color=self.rawDataLineColor2, width=2)
        self.rawDataPen3 = pg.mkPen(color=self.rawDataLineColor3, width=2)
        # Raw data handle
        self.rawDataHandle1 = self.rawDataPlot1.plot(pen=self.rawDataPen1)
        self.rawDataHandle2 = self.rawDataPlot2.plot(pen=self.rawDataPen2)
        self.rawDataHandle3 = self.rawDataPlot3.plot(pen=self.rawDataPen3)

        """
        # Wavelet data plotting
        """
        self.waveletCanvas = pg.GraphicsLayoutWidget()
        self.waveletLayout.addWidget(self.waveletCanvas)

        # PyQtGraph Plot item
        self.waveletPlot1 = self.waveletCanvas.addPlot(row=0, col=0)
        self.waveletPlot2 = self.waveletCanvas.addPlot(row=1, col=0)

        # Setting background color
        self.waveletCanvas.setBackground(self.backgroundColor)

        self.waveletCanvas2 = pg.GraphicsLayoutWidget()
        self.waveletLayout.addWidget(self.waveletCanvas2)

        self.waveletPlot3 = self.waveletCanvas2.addPlot(row=0, col=0)
        self.waveletPlot4 = self.waveletCanvas2.addPlot(row=0, col=1)
        self.waveletPlot5 = self.waveletCanvas2.addPlot(row=0, col=2)
        self.waveletPlot6 = self.waveletCanvas2.addPlot(row=1, col=0)
        self.waveletPlot7 = self.waveletCanvas2.addPlot(row=1, col=1)
        self.waveletPlot8 = self.waveletCanvas2.addPlot(row=1, col=2)

        self.waveletCanvas2.setBackground(self.backgroundColor)

        # Getting axis items
        self.wvAx1 = self.waveletPlot1.getAxis("right")
        self.wvAx2 = self.waveletPlot2.getAxis("right")
        self.wvAx3 = self.waveletPlot3.getAxis("right")
        self.wvAx4 = self.waveletPlot4.getAxis("right")
        self.wvAx5 = self.waveletPlot5.getAxis("right")
        self.wvAx6 = self.waveletPlot6.getAxis("right")
        self.wvAx7 = self.waveletPlot7.getAxis("right")
        self.wvAx8 = self.waveletPlot8.getAxis("right")

        # Showing right axes on both left and right size
        for plot in [self.waveletPlot1, self.waveletPlot2, self.waveletPlot3, self.waveletPlot4, self.waveletPlot5, self.waveletPlot6]:
            plot.showAxes((True, False, True, True))

        # X axis labels
        self.waveletPlot1.setLabel("bottom", "Time", "s")
        self.waveletPlot2.setLabel("bottom", "Time", "s")
        self.waveletPlot3.setLabel("bottom", "", "")
        self.waveletPlot4.setLabel("bottom", "", "")
        self.waveletPlot5.setLabel("bottom", "", "")
        self.waveletPlot6.setLabel("bottom", "", "")
        self.waveletPlot7.setLabel("bottom", "", "")
        self.waveletPlot8.setLabel("bottom", "", "")

        # Y axis labels
        self.waveletPlot1.setLabel("left", "Voltage", "V")
        self.waveletPlot1.setLabel("top", "Original data")
        self.waveletPlot2.setLabel("left", "Voltage", "V")
        self.waveletPlot2.setLabel("top", "Filtered data")
        self.waveletPlot3.setLabel("left", "Intensity", "")
        self.waveletPlot3.setLabel("top", "Approximation coefficient (cA)")
        self.waveletPlot4.setLabel("left", "Intensity", "")
        self.waveletPlot4.setLabel("top", "Detailed coefficient (cD1)")
        self.waveletPlot5.setLabel("left", "Intensity", "")
        self.waveletPlot5.setLabel("top", "Detailed coefficient (cD2)")
        self.waveletPlot6.setLabel("left", "Intensity", "")
        self.waveletPlot6.setLabel("top", "Detailed coefficient (cD3)")
        self.waveletPlot7.setLabel("left", "Intensity", "")
        self.waveletPlot7.setLabel("top", "Detailed coefficient (cD4)")
        self.waveletPlot8.setLabel("left", "Intensity", "")
        self.waveletPlot8.setLabel("top", "Detailed coefficient (cD5)")

        self.waveletPen1 = pg.mkPen(color=self.rawDataLineColor1, width=2)
        self.waveletPen2 = pg.mkPen(color=self.rawDataLineColor2, width=2)
        self.waveletPen3 = pg.mkPen(color=self.rawDataLineColor3, width=2)
        self.waveletPen4 = pg.mkPen(color=self.rawDataLineColor1, width=2)
        self.waveletPen5 = pg.mkPen(color=self.rawDataLineColor2, width=2)
        self.waveletPen6 = pg.mkPen(color=self.rawDataLineColor3, width=2)
        self.waveletPen7 = pg.mkPen(color=self.rawDataLineColor3, width=2)
        self.waveletPen8 = pg.mkPen(color=self.rawDataLineColor3, width=2)


        # Wavelets data handle
        self.waveletHandle1 = self.waveletPlot1.plot(pen=self.waveletPen1)
        self.waveletHandle2 = self.waveletPlot2.plot(pen=self.waveletPen2)
        self.waveletHandle3 = self.waveletPlot3.plot(pen=self.waveletPen3)
        self.waveletHandle4 = self.waveletPlot4.plot(pen=self.waveletPen4)
        self.waveletHandle5 = self.waveletPlot5.plot(pen=self.waveletPen5)
        self.waveletHandle6 = self.waveletPlot6.plot(pen=self.waveletPen6)
        self.waveletHandle7 = self.waveletPlot7.plot(pen=self.waveletPen7)
        self.waveletHandle8 = self.waveletPlot8.plot(pen=self.waveletPen8)

    def shiftChannelTime(self):
        self.updateRawPlot()

    def updateWaveletCBox(self):
        currentFamily = self.waveletFamilyCBox.currentText()
        waveletList = pywt.wavelist(currentFamily)
        # Removing previous items in a combo box
        self.selectWaveletCBox.clear()
        
        for wavelet in waveletList:
            self.selectWaveletCBox.addItem(wavelet)

    def savePeaks(self):
        filename = self.filenameLineEdit.displayText()
        self.peakDict["index"] = self.data.index
        print(filename)
        with open(filename, "wb") as f:
            pickle.dump(self.peakDict, f)

    def downsamplingUpdate(self):
        currentValue = self.downsamplingComboBox.currentText()

        if currentValue == "No downsampling":
            # Downsampling is turned off
            self.rawDataPlot1.setDownsampling(ds=False)
            self.rawDataPlot2.setDownsampling(ds=False)
            self.rawDataPlot3.setDownsampling(ds=False)
        elif currentValue == "Subsample":
            # Downsampling
            self.rawDataPlot1.setDownsampling(ds=True, auto=True, mode="subsample")
            self.rawDataPlot2.setDownsampling(ds=True, auto=True, mode="subsample")
            self.rawDataPlot3.setDownsampling(ds=True, auto=True, mode="subsample")
        elif currentValue == "Mean":
            # Downsampling
            self.rawDataPlot1.setDownsampling(ds=True, auto=True, mode="mean")
            self.rawDataPlot2.setDownsampling(ds=True, auto=True, mode="mean")
            self.rawDataPlot3.setDownsampling(ds=True, auto=True, mode="mean")
        elif currentValue == "Peak":
            # Downsampling
            self.rawDataPlot1.setDownsampling(ds=True, auto=True, mode="peak")
            self.rawDataPlot2.setDownsampling(ds=True, auto=True, mode="peak")
            self.rawDataPlot3.setDownsampling(ds=True, auto=True, mode="peak")
        else:
            print(f"[MainWindow/downsamplingUpate] Error: unrecognized downsampling option ({currentValue}).")

    def updateTheshold(self, label):
        if label == 1:
            thresholdVal = self.rawPlotThreshold1.value()
            self.ax1.setTicks([[(thresholdVal,str(thresholdVal))],[]])
            self.ax1.setStyle(tickLength=-760)
        elif label == 2:
            thresholdVal = self.rawPlotThreshold2.value()
            self.ax2.setTicks([[(thresholdVal,str(thresholdVal))],[]])
            self.ax2.setStyle(tickLength=-760)
        else:
            thresholdVal = self.rawPlotThreshold3.value()
            self.ax3.setTicks([[(thresholdVal,str(thresholdVal))],[]])
            self.ax3.setStyle(tickLength=-760)
            

    def backButtonCallback(self):
        currentStart = self.rawWindowStartSpinBox.value()
        newStart = currentStart - self.rawStepSizeSpinBox.value()

        # Checking if start value is not lower than zero.
        if newStart > 0:
            self.rawWindowStartSpinBox.setValue(newStart)
            self.updateRawPlot()
        else:
            print("[MainWindow/backButtonCallback] Error: Plot start cannot be lower than zero!")

    def backWaveletButtonCallback(self):
        currentStart = self.rawWindowStartSpinBox.value()
        newStart = currentStart - self.rawStepSizeSpinBox.value()

        # Checking if start value is not lower than zero.
        if newStart > 0:
            self.rawWindowStartSpinBox.setValue(newStart)
            self.updateRawPlot()
            self.updateWaveletPlot()
        else:
            print("[MainWindow/backButtonCallback] Error: Plot start cannot be lower than zero!")

    def forwardButtonCallback(self):
        currentStart = self.rawWindowStartSpinBox.value()
        newStart = currentStart + self.rawStepSizeSpinBox.value()

        # Checking if the end value (start + window) is not larger than the dataset size
        if (newStart + self.rawWindowSizeSpinBox.value()) < len(self.data):
            self.rawWindowStartSpinBox.setValue(newStart)
            self.updateRawPlot()
        else:
            print("[MainWindow/backButtonCallback] Error: Attempting to plot values out of the range of the available data!")
    
    def forwardWaveletButtonCallback(self):
        currentStart = self.rawWindowStartSpinBox.value()
        newStart = currentStart + self.rawStepSizeSpinBox.value()

        # Checking if the end value (start + window) is not larger than the dataset size
        if (newStart + self.rawWindowSizeSpinBox.value()) < len(self.data):
            self.rawWindowStartSpinBox.setValue(newStart)
            self.updateRawPlot()
            self.updateWaveletPlot()
        else:
            print("[MainWindow/backButtonCallback] Error: Attempting to plot values out of the range of the available data!")
 

    def updateWaveletPlot(self):
        # User selected channel to analyze
        channel = self.selectChannelCBox.currentText()
        if channel == '':
            print(f"[updateWaveletPlot] No channel selected. Updating is deactivated.")
            return

        waveletFamily = self.waveletFamilyCBox.currentText()
        if waveletFamily == '':
            print(f"[updateWaveletPlot] No wavelet family selected. Updating deactivated.")
            return

        wavelet = self.selectWaveletCBox.currentText()
        if wavelet == '':
            print(f"[updateWaveletPlot] No wavelet selected. Updating deactivated.")
            return
        
        dataStart = self.rawWindowStartSpinBox.value()
        windowSize = self.rawWindowSizeSpinBox.value()

        df1 = self.dataOriginal.iloc[dataStart:dataStart+windowSize, :]

        # Updating line plot
        self.waveletPlot1.clear()
        self.waveletHandle1.setData(df1.index, df1[channel].values)
        self.waveletPlot1.addItem(self.waveletHandle1)

        # Calculating wavelets
        coefs = pywt.wavedec(df1[channel].values, wavelet=wavelet, level=5, mode="periodic")
        
        (cA5, cD5, cD4, cD3, cD2, cD1) = coefs

        filteredData = pywt.waverec((cA5, 0*cD5, 0*cD4, 0*cD3, 0*cD2, 0*cD1), wavelet=wavelet, mode='periodic')

        self.waveletPlot2.clear()
        self.waveletHandle2.setData(df1.index, filteredData)
        self.waveletPlot2.addItem(self.waveletHandle2)

        self.waveletPlot3.clear()
        self.waveletHandle3.setData(cA5)
        self.waveletPlot3.addItem(self.waveletHandle3)

        self.waveletPlot4.clear()
        self.waveletHandle4.setData(cD1)
        self.waveletPlot4.addItem(self.waveletHandle4)

        self.waveletPlot5.clear()
        self.waveletHandle5.setData(cD2)
        self.waveletPlot5.addItem(self.waveletHandle5)

        self.waveletPlot6.clear()
        self.waveletHandle6.setData(cD3)
        self.waveletPlot6.addItem(self.waveletHandle6)

        self.waveletPlot7.clear()
        self.waveletHandle7.setData(cD4)
        self.waveletPlot7.addItem(self.waveletHandle7)

        self.waveletPlot8.clear()
        self.waveletHandle8.setData(cD5)
        self.waveletPlot8.addItem(self.waveletHandle8)

    def updateRawPlot(self):

        dataStart = self.rawWindowStartSpinBox.value()
        windowSize = self.rawWindowSizeSpinBox.value()

        self.deltaXChannel1 = int(self.axisCh1ShiftSpinBox.value())
        self.deltaXChannel2 = int(self.axisCh2ShiftSpinBox.value())
        self.deltaXChannel3 = int(self.axisCh3ShiftSpinBox.value())

        seriesCh1 = self.data.iloc[dataStart+self.deltaXChannel1:dataStart+windowSize+self.deltaXChannel1, 0]
        seriesCh2 = self.data.iloc[dataStart+self.deltaXChannel2:dataStart+windowSize+self.deltaXChannel2, 1]
        seriesCh3 = self.data.iloc[dataStart+self.deltaXChannel3:dataStart+windowSize+self.deltaXChannel3, 2]
        #df1 = self.data.iloc[dataStart:dataStart+windowSize, :]
        

        # Updating line plot
        self.rawDataPlot1.clear()
        #self.rawDataHandle1.setData(df1Ch1.index, df1Ch1["Channel 1"].values)
        self.rawDataHandle1.setData(seriesCh1.index, seriesCh1.values)
        self.rawDataPlot1.addItem(self.rawDataHandle1)

        self.rawDataPlot2.clear()
        #self.rawDataHandle2.setData(df1.index, df1["Channel 2"].values)
        self.rawDataHandle2.setData(seriesCh2.index, seriesCh2.values)
        self.rawDataPlot2.addItem(self.rawDataHandle2)

        self.rawDataPlot3.clear()
        #self.rawDataHandle3.setData(df1.index, df1["Channel 3"].values)
        self.rawDataHandle3.setData(seriesCh3.index, seriesCh3.values)
        self.rawDataPlot3.addItem(self.rawDataHandle3)

        # Updating peaks if available
        if self.showFilteredPeaksCheckBox.isChecked():
            for channel, plot in zip(["Channel 1 filtered", "Channel 2 filtered", "Channel 3 filtered"], [self.rawDataPlot1, self.rawDataPlot2, self.rawDataPlot3]):
                selectedPeaks = np.where(np.logical_and(self.peakDict[channel]>=dataStart, self.peakDict[channel]<=dataStart+windowSize))
                peakValues = self.peakDict[channel][selectedPeaks]
                for value in peakValues:
                    Xposition = self.data.index[value]
                    line = pg.InfiniteLine(pos=Xposition, angle=90, pen='#2ca02c')
                    plot.addItem(line)
                
        if self.showRemovedPeaksCheckBox.isChecked():
            for channel, plot in zip(["Channel 1 removed", "Channel 2 removed", "Channel 3 removed"], [self.rawDataPlot1, self.rawDataPlot2, self.rawDataPlot3]):
                selectedPeaks = np.where(np.logical_and(self.peakDict[channel]>=dataStart, self.peakDict[channel]<=dataStart+windowSize))
                peakValues = self.peakDict[channel][selectedPeaks]
                for value in peakValues:
                    Xposition = self.data.index[value]
                    line = pg.InfiniteLine(pos=Xposition, angle=90, pen='#7f7f7f')
                    plot.addItem(line)
            #print() 

    def applyWaveletFilter(self):
        wavelet = self.selectWaveletCBox.currentText()
        if wavelet == '':
            print(f"[applyWaveletFilter] No wavelet selected. Applying filter aborted.")
        
        for channel in self.dataOriginal:
            
            data = self.dataOriginal[channel]
            # Calculating wavelets
            coefs = pywt.wavedec(data, wavelet, level=5, mode="periodic")
        
            (cA5, cD5, cD4, cD3, cD2, cD1) = coefs
            filteredData = pywt.waverec((cA5, 0*cD5, 0*cD4, 0*cD3, 0*cD2, 0*cD1), wavelet, mode='periodic')

            self.data[channel] = filteredData

    def loadFile(self):
        print("[MainWindow/loadFile] Load file clicked.")
        file = QFileDialog.getOpenFileName(self, "Open file")

        self.inputFile = file[0]
        print(self.inputFile)
        
        self.loadDAQData()

    def loadDAQData(self):

        self.progress_dialog = QProgressDialog("Task in progress...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Progress")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)

        self.loadingBar = loadingBarThread(self.inputFile, self)
        self.loadingBar.progress.connect(self.progress_dialog.setValue)
        self.loadingBar.finished.connect(self.progress_dialog.close)
        self.progress_dialog.canceled.connect(self.loadingBar.terminate)

        self.loadingBar.start()

    """"
    # Peak finding section
    """
    # self.currentPeaks, self.propertiesList = self._findPeaks(data=self.dfData)
    
    def findPeaks(self):
        self.peakDict = {"Channel 1": np.array([], dtype=int), 
                    "Channel 2": np.array([], dtype=int), 
                    "Channel 3": np.array([], dtype=int),
                    "Channel 1 filtered": np.array([], dtype=int), 
                    "Channel 2 filtered": np.array([], dtype=int), 
                    "Channel 3 filtered": np.array([], dtype=int),
                    "Channel 1 removed": np.array([], dtype=int), 
                    "Channel 2 removed": np.array([], dtype=int), 
                    "Channel 3 removed": np.array([], dtype=int)}

        localData = self.data.copy(deep=True)
        peakList = []
        propertiesList = []

        thresholds = [self.rawPlotThreshold1.value(), self.rawPlotThreshold2.value(), self.rawPlotThreshold3.value()]
        
        doublePeakDistance = self.doublePeakDistanceSpinBox.value()

        # For inverget peaks data is just inverted (-data)
        if self.invertedCh1Box.isChecked():
            localData["Channel 1"] = -localData["Channel 1"]
            thresholds[0] = -thresholds[0]
        
        if self.invertedCh2Box.isChecked():
            localData["Channel 2"] = -localData["Channel 2"]
            thresholds[1] = -thresholds[1]

        if self.invertedCh3Box.isChecked():
            localData["Channel 3"] = -localData["Channel 3"]
            thresholds[2] = -thresholds[2]

        if self.currentViewCheckBox.isChecked():
            currentMin = self.rawWindowStartSpinBox.value()
            currentMax = currentMin + self.rawWindowSizeSpinBox.value()
            localData = localData.iloc[currentMin:currentMax, :]

        width = self.peakWidthCBox.value()
        distance = self.peakDistanceCBox.value()

        # Only checking for channel 1 and channel 2. 
        # No peaks are retrieved for channel 3.
        # TODO: What is exactly peak width?
        for channel, threshold in zip(localData[0:3], thresholds):
            peaks, properties = find_peaks(localData[channel], height=threshold, width=width, distance=distance)

            # If we have more than one peak, let's see if we can merge some.
            # We are checking left ips to consider the moment the peak enters the laser beam
            # Left_ips are the left sides of peak. 
            # Left ips are floats so they need to be cast as integers first.
            
            peaks = properties["left_ips"].astype(int)

            #print(f"{channel}: {peaks}, type: {type(peaks)}")

            self.peakDict[channel] = np.sort(peaks)
            
        self.collapseDoublePeaks()
        print(self.peakDict)        

        self.updateRawPlot()

    def collapseDoublePeaks(self):
        doulePeakDistance = self.doublePeakDistanceSpinBox.value()*10
        print(f"Double peak distance : {doulePeakDistance}")
        
        for channel in ["Channel 1", "Channel 2", "Channel 3"]:
            leadingPeak = -1000000000
            for peak in self.peakDict[channel]:
                if (peak - leadingPeak) > doulePeakDistance:
                    self.peakDict[channel + " filtered"] = np.append(self.peakDict[channel + " filtered"], peak)
                    leadingPeak = peak
                else:
                    #print(f"Channel : {channel}, peak : {peak}, leading peak : {leadingPeak}, distance: {peak - leadingPeak}")
                    self.peakDict[channel + " removed"] = np.append(self.peakDict[channel + " removed"], peak)
    

    def exitProgram(self):
        print("[MainWindow] Exiting program.")
        #self.loadingBar.terminate()
        time.sleep(0.1)
        quit()




app = QApplication(sys.argv)

window = MainWindow()
window.show()

app.exec()