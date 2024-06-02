import tkinter as Tk
from   tkinter import scrolledtext
import threading
import logging
import pyfiglet                                                      # ASCII formatter (Just for tooling fun :) :))

## ASAP Packages
from ASAPInsertion import ASAPInsertion
from ASAPCompiler  import ASAPCompiler


class ASAPInsertionProcessor:
    def __init__(self, asapSpecFile, outputFolder):
        self.asapSpecFile = asapSpecFile
        self.outputFolder = outputFolder

    def run(self):
        # Run insertion
        ASAPInsertion(specFile      =  self.asapSpecFile, 
                      outputFolder  =  self.outputFolder)

class ASAPCompilationProcessor:
    def __init__(self, asapSpecFile, outputFolder, asapInterfaceFile, smuProgramFile, sruProgramFile):
        self.asapSpecFile      = asapSpecFile
        self.outputFolder      = outputFolder
        self.asapInterfaceFile = asapInterfaceFile
        self.smuProgramFile    = smuProgramFile
        self.sruProgramFile    = sruProgramFile

    def run(self):
        # Run insertion
        ASAPCompiler (asapSpecFile      =  self.asapSpecFile, 
                      asapInterfaceFile =  self.asapInterfaceFile,
                      outputFolder      =  self.outputFolder,
                      smuProgramFile    =  self.smuProgramFile,
                      sruProgramFile    =  self.sruProgramFile)

        

class GuiLogger(logging.Handler):
    def __init__(self, textArea):
        super().__init__()
        self.textArea = textArea

    def emit(self, record):
        msg = self.format(record)
        self.textArea.configure(state='normal')
        self.textArea.insert(Tk.END, msg + '\n')
        self.textArea.configure(state='disabled')
        self.textArea.yview(Tk.END)

class Application(Tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ASAP Post-Silicon Remediation Tool GUI-MODE")

        # Create dropdown box
        self.option_var = Tk.StringVar()
        self.option_var.set("ASAP Insertion")  # Default option
        self.option_menu = Tk.OptionMenu(self, self.option_var, "ASAP Insertion", "ASAP Compiler", command=self.onOptionSelect)
        self.option_menu.grid(row=0, column=0, padx=10, pady=5)

        # Config file field
        self.configFileNameLabel = Tk.Label(self, text="ASAP Specification File")
        self.configFileNameLabel.grid(row=1, column=0, padx=10, pady=5)
        self.configFileNameEntry = Tk.Entry(self)
        self.configFileNameEntry.grid(row=1, column=1, padx=10, pady=5)

        # Output Folder
        self.outFolderNameLabel = Tk.Label(self, text="Output Folder Path")
        self.outFolderNameLabel.grid(row=2, column=0, padx=10, pady=5)
        self.outFolderNameEntry = Tk.Entry(self)
        self.outFolderNameEntry.grid(row=2, column=1, padx=10, pady=5)

       # Interface  File
        self.intFileNameLabel    = Tk.Label(self, text="Interface File Path")
        self.intFileNameEntry    = Tk.Entry(self)

        # SMU program file field
        self.asapSmuProgramLabel = Tk.Label(self, text="SMU Program File")
        self.asapSmuProgramEntry = Tk.Entry(self)

        # SRU program file field
        self.asapSruProgramLabel = Tk.Label(self, text="SRU Program File")
        self.asapSruProgramEntry = Tk.Entry(self)

        # Create "ASAP insert" button
        self.asapInsertButton    = Tk.Button(self, text="Start Insertion", command=self.startAsapInsert)
        self.asapInsertButton.grid(row=3, column=0, columnspan=2, pady=10)

        # Create "ASAP compile" button
        self.asapCompileButton = Tk.Button(self, text="Compile Program", command=self.startAsapCompile)

        # Create text area for logs
        self.logArea = scrolledtext.ScrolledText(self, state='disabled', width=120, height=30)
        self.logArea.grid(row=7, column=0, columnspan=2, padx=10, pady=10)


        # Set up logger
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        guiHandler = GuiLogger(self.logArea)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        guiHandler.setFormatter(formatter)
        self.logger.addHandler(guiHandler)

    def introLogInsertion(self):
        logging.info("Insertion Tool - Automatic, Scalable And Programmable (ASAP) Framework...\n\n " + pyfiglet.figlet_format("ASAP  INSERTION"))
        logging.info("!!!! Specify Spec file, Output folder in the provided text-box and press START INSERTION !!!! ")
        

    def introLogCompiler(self):
        logging.info("Compiler - Automatic, Scalable And Programmable (ASAP) Framework...\n\n " + pyfiglet.figlet_format("ASAP  COMPILER"))
        logging.info("!!!! Specify Spec file, Output folder, SMU/SRU program file in the provided text-box and press Compile Program !!!! ")

    def onOptionSelect(self, value):
        # If ASAP Insertion is selected, show the config file, output folder fields and compile button
        if value == "ASAP Insertion":
            self.clearLogs()
            self.configFileNameLabel.grid(row=1, column=0, padx=10, pady=5)
            self.configFileNameEntry.grid(row=1, column=1, padx=10, pady=5)
            self.outFolderNameLabel.grid(row=2, column=0, padx=10, pady=5)
            self.outFolderNameEntry.grid(row=2, column=1, padx=10, pady=5)
            self.asapInsertButton.grid(row=3, column=0, columnspan=2, pady=10)  
            self.intFileNameLabel.grid_forget()
            self.intFileNameEntry.grid_forget()
            self.asapSmuProgramLabel.grid_forget()
            self.asapSmuProgramEntry.grid_forget()
            self.asapSruProgramLabel.grid_forget()
            self.asapSruProgramEntry.grid_forget()
            self.asapCompileButton.grid_forget()
            self.introLogInsertion()  # Display introductory log for insertion
        # If ASAP Insertion is selected, show the config file, output folder fields and compile button
        elif value == "ASAP Compiler":
            self.clearLogs()
            self.configFileNameLabel.grid(row=1, column=0, padx=10, pady=5)
            self.configFileNameEntry.grid(row=1, column=1, padx=10, pady=5)
            self.outFolderNameLabel.grid(row=2, column=0, padx=10, pady=5)
            self.outFolderNameEntry.grid(row=2, column=1, padx=10, pady=5)
            self.intFileNameLabel.grid(row=3, column=0, padx=10, pady=5)
            self.intFileNameEntry.grid(row=3, column=1, padx=10, pady=5)
            self.asapSmuProgramLabel.grid(row=4, column=0, padx=10, pady=5)
            self.asapSmuProgramEntry.grid(row=4, column=1, padx=10, pady=5)
            self.asapSruProgramLabel.grid(row=5, column=0, padx=10, pady=5)
            self.asapSruProgramEntry.grid(row=5, column=1, padx=10, pady=5)
            self.asapCompileButton.grid(row=6, column=0, columnspan=2, pady=10)
            self.asapInsertButton.grid_forget()
            self.introLogCompiler()

    def startAsapInsert(self):
        # Get input values based on the selected option
        if self.option_var.get() == "ASAP Insertion":
            asapSpecFile = self.configFileNameEntry.get()
            outputFolder = self.outFolderNameEntry.get()

            # Start the ASAP insertion in a separate thread
            threading.Thread(target=self.runAsapInsertionProcessor, args=(asapSpecFile, outputFolder)).start()

    def clearLogs(self):
        # Clear the text displayed in the log area
        self.logArea.configure(state='normal')
        self.logArea.delete(1.0, Tk.END)
        self.logArea.configure(state='disabled')
    
    def startAsapCompile(self):
        # Get input values based on the selected option
        self.clearLogs()
        if self.option_var.get() == "ASAP Compiler":
            asapSpecFile = self.configFileNameEntry.get()
            outputFolder = self.outFolderNameEntry.get()
            asapInterfaceFile = self.intFileNameEntry.get()
            smuProgramFile = self.asapSmuProgramEntry.get()
            sruProgramFile = self.asapSruProgramEntry.get()

            # Start the ASAP compilation in a separate thread
            threading.Thread(target=self.runAsapCompilationProcessor, args=(asapSpecFile,       \
                                                                            outputFolder,       \
                                                                            asapInterfaceFile,  \
                                                                            smuProgramFile,     \
                                                                            sruProgramFile)).start()

    def runAsapInsertionProcessor(self, asapSpecFile, outputFolder):
        processor = ASAPInsertionProcessor(asapSpecFile, outputFolder)
        processor.run()

    def runAsapCompilationProcessor(self, asapSpecFile, outputFolder, asapInterfaceFile, smuProgramFile, sruProgramFile):
        processor = ASAPCompilationProcessor(asapSpecFile, outputFolder, asapInterfaceFile, smuProgramFile, sruProgramFile)
        processor.run()

if __name__ == "__main__":
    app = Application()
    app.mainloop()
