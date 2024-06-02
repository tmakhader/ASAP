from __future__ import absolute_import
from __future__ import print_function
import os
import logging                                                       # logger
#import pyfiglet                                                      # ASCII formatter (Just for tooling fun :) :))
import json
from pyverilog.vparser.parser import VerilogCodeParser               # PyVerilog Parser
from pyverilog.vparser.ast import *                                  # PyVerilog AST
from pyverilog.ast_code_generator.codegen import ASTCodeGenerator    # Pyverilog AST to verilog code generator

#--------------------------------------------- LOGGER SETUP----------------------------------------#
# Configure logging - Done at file top so that all classes have it accessible
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Setting up log file
#fileHandler = logging.FileHandler('ASAPInsertion.log', mode='w') 
#formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#fileHandler.setFormatter(formatter)
#logging.getLogger().addHandler(fileHandler)
#logging.info("Started Automatic, Scalable And Programmable (ASAP) tool for Hardware Patching...\n\n " + pyfiglet.figlet_format("ASAP  INSERTION"))
#--------------------------------------------------------------------------------------------------#

# Exception class for pragma parsing
class PragmaParsingError(Exception):
    pass


# Class to create structured log prints of complex objects
class LogStructuring:
    def __init__(self) -> None:
        pass

    def logDictInfo(self, dict):
        mapData = "\n"
        for key in dict:
            mapData += "%s --> %s\n"%(str(key), dict[key])
        return mapData
    
    # Method to create structured log of a list
    def logListInfo(self, list):
        listData = "\n"
        for value in list:
            listData += "%s\n"%(value)    
        return listData

    def logTreeInfo(self, tree, initialString = "", indent=0):
        for key, value in tree.items():
            initialString += ("\n" + "  " * indent + str(key[0]) + "(%s)"%(str(key[1])))
            if isinstance(value, dict):
                initialString = self.logTreeInfo(value, indent = indent + 1, initialString = initialString)
            else:
                initialString +=  ("\n" +"  " * (indent + 1) + str(value))
        return initialString
        


# Class to process filelist and extract pragmas and associated properties
class PragmaExtractor(LogStructuring):
    def __init__(self, filelist) -> None:
        super().__init__()  # LogStructuring constructor
        self.filelist = filelist
        logging.info("Pragma extractor initialized with %s"%(filelist))

    # This method parses the pragma in a line to returns two tuples
    # (start range, end range) for observe and (type, start range, end range) for control
    def pragmaParser(self, line):
        if "#pragma" in line:
            pragmaArgs = line.split("#pragma", 1)[1].strip().split()
            if "control" in pragmaArgs and "observe" in pragmaArgs:
                try:
                    observe_index = pragmaArgs.index("observe") + 1
                    control_index = pragmaArgs.index("control") + 2
                    control_type  = pragmaArgs[pragmaArgs.index("control") + 1]
                    observe_range = pragmaArgs[observe_index].split(':')
                    control_range = pragmaArgs[control_index].split(':')
                    return (int(observe_range[0]), int(observe_range[1])), \
                        (control_type, int(control_range[0]), int(control_range[1]))
                except (IndexError, ValueError):
                    logging.error("Found incorrect arguments for control/observe pragma in line \n%s"%(line))
                    raise PragmaParsingError("Invalid pragma directive: Insufficient or incorrect arguments for 'control' or 'observe'")
            elif "control" in pragmaArgs:
                try:
                    control_index = pragmaArgs.index("control") + 2
                    control_range = pragmaArgs[control_index].split(':')
                    control_type  = pragmaArgs[pragmaArgs.index("control") + 1]
                    return None, (control_type, int(control_range[0]), int(control_range[1]))
                except (IndexError, ValueError):
                    logging.error("Found incorrect arguments for control pragma in line \n%s"%(line))
                    raise PragmaParsingError("Invalid pragma directive: Insufficient or incorrect arguments for 'control'")
            elif "observe" in pragmaArgs:
                try:
                    observe_index = pragmaArgs.index("observe") + 1
                    observe_range = pragmaArgs[observe_index].split(':')
                    return (int(observe_range[0]), int(observe_range[1])), None
                except (IndexError, ValueError):
                    logging.error("Found incorrect arguments for observe pragma in line \n%s"%(line))
                    raise PragmaParsingError("Invalid pragma directive: Insufficient or incorrect arguments for 'observe'")
            else:
                    logging.error("Invalid pragma directive: Neither 'control' nor 'observe' found in \n%s"%(line))
                    raise PragmaParsingError("Invalid pragma directive: Neither 'control' nor 'observe' found")
        else:
            return None, None

    # Parses a file and populates a hash map with line # and observe, control args
    def fileParser(self, file):
        # Ensure that the file exists
        assert os.path.exists(file), "Verilog file %s in filelist doesn't exist"%(file)
        pragmaDict = {}
        with open(file, 'r') as f:
            for line_number, line in enumerate(f, start=1):
                observe, control = self.pragmaParser(line)
                if observe or control:
                    pragmaDict[line_number] = (observe, control)
        logging.info("Pragma distribution in file - %s is %s"%(file, self.logDictInfo(pragmaDict)))
        return pragmaDict
    
    # Goes through filelist, parses every file in the filelist for pragmas
    def filelistParse(self):
        # Ensure that the filelist exists
        assert os.path.exists(self.filelist), "Filelist %s doesn't exist"%(self.filelist)
        files = [filename.strip() for filename in open(self.filelist, 'r')]
        logging.info("List of files in filelist %s - %s"%(self.filelist, self.logListInfo(files)))
        return {file: self.fileParser(file) for file in files}


# Class to identify module instantiation hierarchy to perform various insertion operations
# The class expects top-module and a hash map of module to AST for tree population
class InstantiationTree:
    def __init__(self, topModule, moduleToAst):
        self.topModule = topModule
        self.moduleToAst = moduleToAst
        self.instanceTree = self.populateTree(moduleToAst[topModule], \
                          isTopModule=True)

    # Method used to recursively populate the instantiation tree
    def populateTree(self, ast, isTopModule = False):
        treeNode = {}
        if isTopModule:
            treeNode.update({("TOP", self.topModule):  \
                              self.populateTree(ast)})
        else:
            for item in ast.items:
                if isinstance(item, InstanceList):
                    for instance in item.instances:
                        treeNode.update({(instance.name, instance.module): \
                                        self.populateTree(self.moduleToAst[instance.module])})
        return treeNode if treeNode else None
    
    def populateSignalList(self, treeNode, moduleToObserveSignal, moduleToControlSignal, observeIndex = 0, controlIndex = 0):
        if treeNode is not None:
            observeSignalList = {}
            controlSignalList = {}
            for key, value in treeNode.items:
                observeSignals = moduleToObserveSignal[key[1]]
                controlSignals = moduleToControlSignal[key[1]]
                for signal in observeSignals:
                    observeSignalList.update({signal:[observeSignals[1] - observeSignals[0] + observeIndex, observeIndex]})
                    observeIndex +=  observeSignals[1] - observeSignals[0] + 1
                for signal in controlSignals:
                    controlSignalList.update({signal:[controlSignals[1] - controlSignals[0] + controlIndex, controlIndex]})
                    controlIndex +=  controlSignals[1] - controlSignals[0] + 1
                
                observeChild, controlChild = self.populateSignalList(value,                  \
                                                                     moduleToObserveSignal,  \
                                                                     moduleToControlSignal,  \
                                                                     observeIndex,           \
                                                                     controlIndex)
                observeSignalList.update(observeChild)
                controlSignalList.update(controlChild)

        return {key[0]:observeSignalList}, {key[0]:controlSignalList}
          

# Class to parse the filelist
class VerilogParser(LogStructuring):
    def __init__(self, filelist, topModule) -> None:
        super().__init__()  # LogStructuring constructor
        self.filelist        = filelist
        logging.info("Parser initialized with %s"%(self.filelist))
        self.pragmaExtractor = PragmaExtractor(self.filelist)
        self.fileToPragma    = self.pragmaExtractor.filelistParse()
        self.fileToAst       = self.fileWiseAst()
        logging.info("File to AST hash map generated")
        self.moduleToAst     = self.moduleWiseAst()
        logging.info("Module to AST hash map generated")
        self.tree            = InstantiationTree(topModule, self.moduleToAst).instanceTree
        logging.info("Instantiation tree generated \n %s"%(self.logTreeInfo(self.tree)))

    def moduleWiseAst(self):
        moduleToAst = {}
        for file in self.fileToAst:
            ast = self.fileToAst[file]
            definitions = ast.description.definitions
            for definition in definitions:
                if isinstance(definition, ModuleDef):
                    moduleToAst.update({definition.name:definition})
        return moduleToAst

    # Source file to AST hash map
    def fileWiseAst(self):
        files = [filename.strip() for filename in open(self.filelist, 'r') if filename.strip()]
        assert all(os.path.exists(file) for file in files), "Not all files in the filelist are valid"
        fileToAst = {file: VerilogCodeParser([file]).parse() for file in files}
        if all(value is not None for value in fileToAst.values()):
            logging.info("Filewise AST generated")
        else:
            logging.warning("Invalid ASTs found during fileToAst generation")
        return fileToAst
    
    # Recursive method for AST traversal
    # This method finds Ports/Decl and check if there is a corresponding pragma
    # In effect: For a given file, find the
    # signal associated with each pragma and segregate the signals 
    # into signalToControl and signalToObserve maps.
    # signalToObserve - {<SIGNAL>:(START_INDEX, END_INDEX)}
    # signalToControl - {<SIGNAL>:(CONTROL_TYPE, START_INDEX, END_INDEX)}
    def traverseAst(self, astNode, lineToPragma, signalToControl, signalToObserve):
        if astNode is not None:
            childNodes = astNode.children()
            if isinstance(astNode, Input)  or  \
               isinstance(astNode, Output) or  \
               isinstance(astNode, Reg)    or  \
               isinstance(astNode, Wire): 
                # Check if the line has a pragma
                if astNode.lineno in lineToPragma:
                    # Check if there is an observe and control pragma
                    if lineToPragma[int(astNode.lineno)][0] and lineToPragma[int(astNode.lineno)][1]:
                        signalToObserve.update({astNode.name:(lineToPragma[int(astNode.lineno)][0][0],   \
                                                              lineToPragma[int(astNode.lineno)][0][1])})  
                        signalToControl.update({astNode.name:(lineToPragma[int(astNode.lineno)][1][0],   \
                                                              lineToPragma[int(astNode.lineno)][1][1],   \
                                                              lineToPragma[int(astNode.lineno)][1][2])}) 
                    # Check if there is only an observe pragma
                    elif lineToPragma[int(astNode.lineno)][0]:
                        signalToObserve.update({astNode.name:(lineToPragma[int(astNode.lineno)][0][0],   \
                                                              lineToPragma[int(astNode.lineno)][0][1])})  
                    
                    # Given pragma is exception protected, this one should be control pragma
                    else:
                        signalToControl.update({astNode.name:(lineToPragma[int(astNode.lineno)][1][0],   \
                                                              lineToPragma[int(astNode.lineno)][1][1],   \
                                                              lineToPragma[int(astNode.lineno)][1][2])}) 
            for childNode in childNodes:
                self.traverseAst(childNode, lineToPragma, signalToControl, signalToObserve)
        return 

    # For a given file, performs AST traversal on all modules to extract
    # signalToObserve - {<MODULE> : {<SIGNAL>:(START_INDEX, END_INDEX)}}
    # signalToControl - {<MODULE> : {<SIGNAL>:(CONTROL_TYPE, START_INDEX, END_INDEX)}}
    def signalToPragma(self, ast, lineToPragma):
        moduleDefs = ast.description.definitions
        moduleToSignalToControl = {}
        moduleToSignalToObserve = {}
        for moduleDef in moduleDefs:
            if isinstance(moduleDef, ModuleDef):
                signalToControlPerModule = {}
                signalToObservePerModule = {}
                self.traverseAst(moduleDef,                 \
                                 lineToPragma,              \
                                 signalToControlPerModule,  \
                                 signalToObservePerModule)
                moduleToSignalToControl.update({moduleDef.name:signalToControlPerModule})
                moduleToSignalToObserve.update({moduleDef.name:signalToObservePerModule})
        return moduleToSignalToObserve, moduleToSignalToControl

    # For all files in the file list creates the following hash maps:
    # Observability Map:   {<FILE>:{<MODULE>:{<SIGNAL>:(START_INDEX, END_INDEX)}}} 
    # Controllability Map: {<FILE>:{<MODULE>:{<SIGNAL>:(CONTROL_TYPE, START_INDEX, END_INDEX)}}} 
    def fileToModuleToSignalToPragma(self):
        fileToModuleToSignalToControl = {}
        fileToModuleToSignalToObserve = {}

        # For all files populates signals and appropriate observe/control properties
        for file in self.fileToAst:
            logging.info("Scanning AST of file - %s for observable/controllable signals"%(file))
            moduleToSignalToObserve, moduleToSignalToControl = self.signalToPragma(self.fileToAst[file], self.fileToPragma[file])
            if bool(moduleToSignalToObserve) | bool(moduleToSignalToControl):
                logging.info("AST traversal complete: Observable/Controllable signals found in file - %s"%(str(file)))
            else:
                logging.warning("AST traversal complete: No observable or controllable signals found in file - %s"%(str(file)))
            fileToModuleToSignalToObserve.update({file:moduleToSignalToObserve})
            fileToModuleToSignalToControl.update({file:moduleToSignalToControl})
        return fileToModuleToSignalToObserve, fileToModuleToSignalToControl



# Class to generate modified verilog code based on added pragmas
class VerilogGenerator(LogStructuring):
    def __init__(self, filewiseAst, 
                       moduleWiseAst,
                       outputFolder,
                       instanceTree, 
                       topModule,
                       fileToModuleToSignalToObserve,  
                       fileToModuleToSignalToControl,  
                       observePort, 
                       controlPortIn, 
                       controlPortOut) -> None:
        self.filewiseAst           = filewiseAst
        self.moduleWiseAst         = moduleWiseAst
        self.outputFolder          = outputFolder
        self.fileToModuleToSignalToObserve = fileToModuleToSignalToObserve
        self.fileToModuleToSignalToControl = fileToModuleToSignalToControl
        self.observePort                   = observePort
        self.controlPortIn                 = controlPortIn
        self.controlPortOut                = controlPortOut
        self.instanceTree                  = instanceTree
        self.topModule                     = topModule
        self.moduleToObservePortWidth      = {}
        self.moduleToControlPortWidth      = {} 
    
    # Create necessary tap (assignment )logic for observe signals to propagate to SMU
    #                         <Observation of controlled signals>
    #                  _________                               __________                                 
    #                 |         |                             |          |                             
    #    Driver ------| Wire/   | ----To SRU --- From SRU --- | Wire/(A')| -------- Loads 
    #                 |Reg(A/A')|                             |Reg(A'/A) |                              
    #                 |_________|                             |__________|
    #                      | 
    #                      |
    #                  ObservePort
    #                (SMU Observe Tap)   
    def createInternalObserveTaps(self, signalToObserve, sruDriverList):
        assignmentList = []
        observePortIndexLastInt = 0
        for signal in signalToObserve:
            # If the observed signal is in SRU driver list:
            # -- assign <observePortInt[<range>]> = <signal[OBSERVE_START:OBSERVE_END]> 
            if any(signal == controlSignal[0] for controlSignal in sruDriverList):
                logging.info("Observed port '%s' also found to be a controlled input. Tapping in to '%s' for observation" %(signal, \
                                                                                                                            signal))
                signalRangeLhs = signalToObserve[signal][0]
                signalRangeRhs = signalToObserve[signal][1]
                observePortRangeLhs = observePortIndexLastInt + (signalRangeLhs - signalRangeRhs)
                observePortRangeRhs = observePortIndexLastInt
                Lhs = Partselect(Identifier(self.observePort + "_int"),  \
                                IntConst(observePortRangeLhs), \
                                IntConst(observePortRangeRhs))
                Rhs = Partselect(Identifier(signal),  \
                                IntConst(signalRangeLhs), \
                                IntConst(signalRangeRhs))
                assignmentList.append(Assign(Lhs, Rhs))
                observePortIndexLastInt += (signalRangeLhs - signalRangeRhs) + 1
            # If the counter part (+/- "_controlled") of observed signal is in SRU sriver list as well,
            # -- we should observe this as the original observed signal would be the patched version
            # -- assign <observePortInt[<range>]> = <couterPart(signal)[OBSERVE_START:OBSERVE_END]> 
            elif any(self.signalCounterPart(signal) == controlSignal[0] for controlSignal in sruDriverList):
                logging.info("Observed port '%s' also found to be a controlled reg/wire/output. Tapping in to '%s' for observation" %(signal,  \
                                                                                                               self.signalCounterPart(signal)))
                signalRangeLhs = signalToObserve[signal][0]
                signalRangeRhs = signalToObserve[signal][1]
                observePortRangeLhs = observePortIndexLastInt + (signalRangeLhs - signalRangeRhs)
                observePortRangeRhs = observePortIndexLastInt
                Lhs = Partselect(Identifier(self.observePort + "_int"),  \
                                IntConst(observePortRangeLhs), \
                                IntConst(observePortRangeRhs))
                Rhs = Partselect(Identifier(self.signalCounterPart(signal)),  \
                                IntConst(signalRangeLhs), \
                                IntConst(signalRangeRhs))
                assignmentList.append(Assign(Lhs, Rhs))
                observePortIndexLastInt += (signalRangeLhs - signalRangeRhs) + 1
            # If the observed signal of the counterPart is not in SRU driver list,
            # it is not controlled and we can safely observe the original signal
            else:
                logging.info("Observed port '%s' or '%s' doesn't exist in SRU LoadList, Tapping in to '%s' for observation" %(signal,  \
                                                                                                     self.signalCounterPart(signal), \
                                                                                                                            signal))
                signalRangeLhs = signalToObserve[signal][0]
                signalRangeRhs = signalToObserve[signal][1]
                observePortRangeLhs = observePortIndexLastInt + (signalRangeLhs - signalRangeRhs)
                observePortRangeRhs = observePortIndexLastInt
                Lhs = Partselect(Identifier(self.observePort + "_int"),  \
                                IntConst(observePortRangeLhs), \
                                IntConst(observePortRangeRhs))
                Rhs = Partselect(Identifier(signal),  \
                                IntConst(signalRangeLhs), \
                                IntConst(signalRangeRhs))
                assignmentList.append(Assign(Lhs, Rhs))
                observePortIndexLastInt += (signalRangeLhs - signalRangeRhs) + 1
        return assignmentList, observePortIndexLastInt - 1
    
    def signalCounterPart(self, signal):
        if "controlled" in signal:
            return signal[0:signal.index("_controlled")-1]
        else:
            return signal + "_controlled"


    # Create necessary tap (assignment) logic for control signals to propagate to and from SRU   
    #                                         ________
    # signal 1 ---|      (SRU Input Tap)     |        |     (SRU Output Tap)  | --- signal' 1
    # signal 2 ---|------ controlPortIn- ----|  SRU   |------ControlPortOut---| --- signal' 2
    # ,,,,,,,, ---|                          |________|                       | --- ,,,,,,,,,
    def createInternalControlTaps(self, sruDriverList, sruLoadList):
        assignmentList = []
        controlPortInIndexLastInt  = 0
        controlPortOutIndexLastInt = 0
        # Internal input tap assignment - assign <controlPortInInt[range]]> = <signal[START:END]>;
        for signalNode in sruDriverList:
            signalRangeLhs = signalNode[1]
            signalRangeRhs = signalNode[2]
            controlPortRangeLhs = controlPortInIndexLastInt + (signalRangeLhs - signalRangeRhs)
            controlPortRangeRhs = controlPortInIndexLastInt
            Lhs = Partselect(Identifier(self.controlPortIn + "_int"), \
                            IntConst(controlPortRangeLhs),            \
                            IntConst(controlPortRangeRhs))
            Rhs = Partselect(Identifier(signalNode[0]),               \
                            IntConst(signalRangeLhs),                 \
                            IntConst(signalRangeRhs))
            assignmentList.append(Assign(Lhs, Rhs))
            controlPortInIndexLastInt +=  (signalRangeLhs - signalRangeRhs) + 1

        # Internal output tap assignment - assign <signal'[START:END]> = <controlPortOutInt[range]]>
        # FIXME (Not implemented)          assign <signal'[rest]> = <signal[rest]>
        for signalNode in sruLoadList:
            signalRangeLhs = signalNode[1]
            signalRangeRhs = signalNode[2]
            controlPortRangeLhs = controlPortOutIndexLastInt + (signalRangeLhs - signalRangeRhs)
            controlPortRangeRhs = controlPortOutIndexLastInt
            Lhs = Partselect(Identifier(signalNode[0]),                    \
                            IntConst(signalRangeLhs),                      \
                            IntConst(signalRangeRhs))
            Rhs = Partselect(Identifier(self.controlPortOut + "_int"),     \
                            IntConst(controlPortRangeLhs),                 \
                            IntConst(controlPortRangeRhs))
            assignmentList.append(Assign(Lhs, Rhs))
            controlPortOutIndexLastInt += ((signalRangeLhs - signalRangeRhs)) + 1
        
        assert (controlPortOutIndexLastInt == controlPortInIndexLastInt), "Control port in/out cannot be of different size"
        return assignmentList, controlPortInIndexLastInt - 1, controlPortOutIndexLastInt - 1
    
    # Method to check if a given signal name is an input to the module with given module name
    def isInputPortofModule(self, signalName, moduleName):
        moduleAst = self.moduleWiseAst[moduleName]
        for port in moduleAst.portlist.ports:
            if isinstance(port.first, Input):
                if port.first.name == signalName:
                    return True
        return False

    # This method is particulary used by traverseAstToModifyLHS for checking port modification
    # of module instance arguments. if an argument is an input of the instance, it shouldn't be
    # modified by traverseAstToModifyLHS.  
    def isInputTapToInstance(self, astNode, signal):
        if isinstance(astNode, Instance):
            portArgs    = astNode.portlist
            moduleName  = astNode.module
            for portArg in portArgs:
                if portArg.portname == signal:
                    return self.isInputPortofModule(signal, moduleName)
            return False
        else:
            return False

    # This method recursively traverses the AST to modify all drivers of a signal
    def traverseAstToModifyLHS(self, astNode, signal):
        # traverse the node if the nod is valid and it is not branching to an RHS assignment
        if astNode is not None and not isinstance(astNode, Rvalue) and not self.isInputTapToInstance(astNode, signal):
            childNodes = astNode.children()
            if isinstance(astNode, Identifier):
                if astNode.name == signal:
                    astNode.name = astNode.name  + "_controlled"
            for child in childNodes:
                self.traverseAstToModifyLHS(child, signal)
        return

    # This method recursively traverses the AST to modify all loads of a signal
    def traverseAstToModifyRHS(self, astNode, signal):
        # traverse the node if the nod is valid and it is not branching to an RHS assignment
        if astNode is not None and not isinstance(astNode, Lvalue):
            childNodes = astNode.children()
            if isinstance(astNode, Identifier):
                if astNode.name == signal:
                    astNode.name = astNode.name  + "_controlled"
            for child in childNodes:
                self.traverseAstToModifyRHS(child, signal)
        return
 
    # Method to modify controlled IO ports
    def ModifyControlledIOPorts(self, moduleDef, signalToControl):
        items = list(moduleDef.items) # Items include Decls, Assigns, Blocks etc
        ports = list(moduleDef.portlist.ports)
        newPorts = []
        sruDriverList = [] # Drivers of SRU input (each would be a tuple (signal, start_index, end_index))
        sruLoadList = []   # Loads for SRU output (each would be a tuple (signal, start_index, end_index))
        for port in ports:
            #                  ________                               _________                                 
            #                 |        |                             |         |                             
            #  Input(A) ------| Wire(A)| ----To SRU --- From SRU --- | Wire(A')| -------- Loads 
            #                 |        |                             |         |                              
            #                 |________|                             |_________|
            #                                                                                                                                                                           
            # If the controlled port is an Input wire A 
            # -- Declare a new wire A_controlled
            # -- Leave the input as is
            # -- Change all loads (RHS) of A to A_controlled 
            if isinstance(port.second, Wire) and isinstance(port.first, Input):
                newPorts.append(port)
                if port.first.name in signalToControl:
                    logging.info("-- Bits [%s:%s] of Input port '%s' found as '%s' controlled"%(signalToControl[port.first.name][1],  \
                                                                                            signalToControl[port.first.name][2],  \
                                                                                            port.first.name,                      \
                                                                                            signalToControl[port.first.name][0]))
                    logging.info("--- Bypassing load of '%s' via '%s' for SRU control"%(port.first.name,                          \
                                                                                      port.second.name + "_controlled"))
                    newWire  = Decl((Wire(name = port.second.name + "_controlled", \
                                          width = port.second.width,               \
                                          signed = port.second.signed,             \
                                          dimensions = port.second.dimensions),))
                    items.insert(0, newWire)
                    self.traverseAstToModifyRHS(moduleDef, port.first.name)
                    sruDriverList.append((port.second.name,                        \
                                          signalToControl[port.second.name][1],    \
                                          signalToControl[port.second.name][2]))
                    sruLoadList.append((port.second.name + "_controlled",
                                        signalToControl[port.second.name][1],      \
                                        signalToControl[port.second.name][2]))
            #                  _________                                     ________
            #                 |         |                                   |        |
            #  Drivers -------| Wire(A')| -------- To SRU ---- From SRU ----| Wire(A)| -- Output
            #                 |         |                                   |        |                    
            #                 |_________|                                   |________|   
            #                                                                   |
            #                                                                   |                                                            
            #                                                            To internal loads
            # If the controlled port is an Output wire
            # -- Declare a new wire A_controlled 
            # -- Leave the output as is
            # -- Change all drivers (LHS) of A to A_controlled
            elif isinstance(port.second, Wire) and isinstance(port.first, Output):
                newPorts.append(port)
                if port.first.name in signalToControl:
                    logging.info("-- Bits [%s:%s] of Output (wire) port '%s' found as '%s' controlled"%(signalToControl[port.first.name][1], \
                                                                                                    signalToControl[port.first.name][2], \
                                                                                                    port.first.name,                     \
                                                                                                    signalToControl[port.first.name][0]))
                    logging.info("--- Bypassing driver of '%s' via '%s' for SRU control"%(port.first.name,                               \
                                                                                          port.second.name + "_controlled"))
                    newWire  = Decl((Wire(name = port.second.name + "_controlled", \
                                          width = port.second.width,               \
                                          signed = port.second.signed,             \
                                          dimensions = port.second.dimensions),))
                    items.insert(0, newWire)
                    self.traverseAstToModifyLHS(moduleDef, port.first.name)
                    sruDriverList.append((port.second.name + "_controlled",        \
                                          signalToControl[port.second.name][1],    \
                                          signalToControl[port.second.name][2]))
                    sruLoadList.append((port.second.name,
                                        signalToControl[port.second.name][1],      \
                                        signalToControl[port.second.name][2]))
            #                  ________                                      ________
            #                 |        |                                    |        |
            #  Drivers -------| Reg(A')| -------- To SRU ---- From SRU ---- | Wire(A)| -- Output
            #                 |        |                                    |        |                 
            #                 |________|                                    |________|                           
            #                                                                   |
            #                                                                   |                                                            
            #                                                            To internal loads  
            # If the controlled port is an Output reg
            # -- Declare a new reg A_controlled
            # -- Change the output port type to wire
            # -- Change all drivers of A to A_controlled 
            elif isinstance(port.second, Reg) and isinstance(port.first, Output):
                if port.first.name in signalToControl:
                    logging.info("--Bits [%s:%s] of Output (reg) port '%s' found as '%s' controlled"%(signalToControl[port.first.name][1], \
                                                                                                  signalToControl[port.first.name][2], \
                                                                                                  port.first.name,                     \
                                                                                                  signalToControl[port.first.name][0]))
                    logging.info("--- Bypassing driver of '%s' via register '%s' for SRU control"%(port.first.name,                    \
                                                                                                   port.second.name + "_controlled"))
                    newReg   = Decl((Reg(name = port.second.name + "_controlled",  \
                                         width = port.second.width,                \
                                         signed = port.second.signed,
                                         dimensions = port.second.dimensions),))
                    items.insert(0, newReg)
                    portWire = Wire(name = port.second.name,                       \
                                    width = port.second.width,                     \
                                    signed = port.second.signed,                   \
                                    dimensions = port.second.dimensions)
                    newOutput = Output(name = port.first.name,                     \
                                       width = port.first.width)
                    newPort   = Ioport(first=newOutput, second=portWire)
                    newPorts.append(newPort) 
                    self.traverseAstToModifyLHS(moduleDef, port.first.name)
                    sruDriverList.append((port.second.name + "_controlled",        \
                                          signalToControl[port.second.name][1],    \
                                          signalToControl[port.second.name][2]))
                    sruLoadList.append((port.second.name,                          \
                                        signalToControl[port.second.name][1],      \
                                        signalToControl[port.second.name][2]))
                else:
                    newPorts.append(port)
            else:
                newPorts.append(port)
        moduleDef.items = tuple(items)
        moduleDef.portlist.ports = tuple(newPorts)
        return sruDriverList, sruLoadList
        

    # Method to modify controlled Reg/Wire declarations
    def ModifyControlledRegAndWires(self, moduleDef, signalToControl):
        items = list(moduleDef.items)
        newItems = []      # item list (to be converted to tuple) for new AST items
        sruDriverList = [] # Drivers of SRU input (each would be a tuple (signal, start_index, end_index))
        sruLoadList = []   # Loads for SRU output (each would be a tuple (signal, start_index, end_index))
        for item in items:
            if isinstance(item, Decl):
                #                 ________                                  ________
                #                |        |                                |        |
                #  Drivers ------| Reg(A')| ----- To SRU ---- From SRU --- | Wire(A)| --- Loads 
                #                |________|                                |________|
                #        
                # if a controlled signal is a reg declaration A  
                # -- Declare a new register - A_controlled
                # -- Convert the the register A to wire
                # -- Change all the drivers of A to A_controlled
                if isinstance(item.list[0], Reg):   # NOTE: item.list is a tuple
                    regDecl = item.list[0]
                    if regDecl.name in signalToControl:
                        logging.info("--Bits [%s:%s] of Register '%s' found as '%s' controlled"%(signalToControl[regDecl.name][1], \
                                                                                           signalToControl[regDecl.name][2],   \
                                                                                           regDecl.name,                       \
                                                                                           signalToControl[regDecl.name][0]))
                        logging.info("--- Bypassing driver of '%s' via register '%s' for SRU control"%(regDecl.name,           \
                                                                                                       regDecl.name,+ "_controlled"))
                        # Making a Declaration node passed with list (tuple) of the new register - A_controlled
                        newReg =  Decl((Reg(name = regDecl.name + "_controlled",   \
                                            width = regDecl.width,                 \
                                            signed = regDecl.signed,               \
                                            dimensions = regDecl.dimensions),))
                        # Making a Declaration node passed with list (tuple) of the register converted to wire
                        newWire = Decl((Wire(name = regDecl.name,                  \
                                            width = regDecl.width,                 \
                                            signed = regDecl.signed,               \
                                            dimensions = regDecl.dimensions),))
                        newItems.append(newWire)
                        newItems.append(newReg)
                        self.traverseAstToModifyLHS(moduleDef, regDecl.name)
                        sruDriverList.append((regDecl.name + "_controlled",        \
                                              signalToControl[regDecl.name][1],
                                              signalToControl[regDecl.name][2]))
                        sruLoadList.append((regDecl.name,
                                            signalToControl[regDecl.name][1],
                                            signalToControl[regDecl.name][2]))
                        

                    else:
                        newItems.append(item)
                #                 _________                                  ________
                #                |         |                                |        |
                #  Drivers ------| Wire(A')| ----- To SRU ---- From SRU --- | Wire(A)| --- Loads 
                #                |_________|                                |________|
                #        
                # if a controlled signal is a wire declaration A  
                # -- Declare a new wire - A_controlled
                # -- leave wire A as is
                # -- Change all drivers of A to A_controlled
                elif isinstance(item.list[0], Wire):
                    wireDecl = item.list[0]
                    if wireDecl.name in signalToControl:
                        logging.info("--Bits [%s:%s] of Wire '%s' found as '%s' controlled"%(signalToControl[wireDecl.name][1], \
                                                                                         signalToControl[wireDecl.name][2], \
                                                                                         wireDecl.name,                     \
                                                                                         signalToControl[wireDecl.name][0]))
                        logging.info("--- Bypassing driver of '%s' via wire '%s' for SRU control"%(wireDecl.name,       \
                                                                                                       wireDecl.name + "_controlled"))
                        # Making a Declaration node passed with list (tuple) of the new wire - A_controlled
                        newWire = Decl((Wire(name = wireDecl.name + "_controlled",  \
                                            width = wireDecl.width,                 \
                                            signed = wireDecl.signed,               \
                                            dimensions = wireDecl.dimensions),))
                        # Existing controlled wire will remain in place 
                        oldWire = Decl((Wire(name = wireDecl.name,                  \
                                            width = wireDecl.width,                 \
                                            signed = wireDecl.signed,               \
                                            dimensions = wireDecl.dimensions),))
                        newItems.append(newWire)
                        newItems.append(oldWire)    
                        self.traverseAstToModifyLHS(moduleDef, wireDecl.name)
                        sruDriverList.append((wireDecl.name + "_controlled",        \
                                              signalToControl[wireDecl.name][1],
                                              signalToControl[wireDecl.name][2]))
                        sruLoadList.append((wireDecl.name,
                                            signalToControl[wireDecl.name][1],      \
                                            signalToControl[wireDecl.name][2]))
                    else:
                        newItems.append(item)
                else:
                    newItems.append(item)
            else:
                newItems.append(item)
        moduleDef.items = tuple(newItems)
        return sruDriverList, sruLoadList


    def addModuleWiseLogicForControl(self, moduleNode, signalToControl):
        sruDriverListIo, sruLoadListIo   = self.ModifyControlledIOPorts(moduleNode, signalToControl)
        sruDriverListDec, sruLoadListDec = self.ModifyControlledRegAndWires(moduleNode, signalToControl)

        assignmentList, controlPortInIndexLastInt, controlPortOutIndexLastInt = self.createInternalControlTaps((sruDriverListIo + sruDriverListDec),
                                                                                                      (sruLoadListIo + sruLoadListDec))
        # Adding internal control wire 
        if controlPortInIndexLastInt >= 0:
            controlPortInWidthInt  =  Width(msb=IntConst(controlPortInIndexLastInt),  lsb=IntConst(0))
            controlPortOutWidthInt =  Width(msb=IntConst(controlPortOutIndexLastInt), lsb=IntConst(0))
            controlPortWireInInt   = Decl((Wire(self.controlPortIn  + "_int", width = controlPortInWidthInt),))
            controlPortWireOutInt  = Decl((Wire(self.controlPortOut + "_int", width = controlPortOutWidthInt),))
            itemsList = list(moduleNode.items)
            itemsList.insert(0, controlPortWireInInt)
            itemsList.insert(1, controlPortWireOutInt)
            for assignment in assignmentList:
                itemsList.append(assignment)
            moduleNode.items = tuple(itemsList)
        return sruDriverListIo + sruDriverListDec, controlPortInIndexLastInt + 1


    # This method modifies the module AST node to add observe ports and assignments
    def addModuleWiseLogicForObservation(self, moduleNode, signalToObserve, sruDriverList):
        assignmentList, observePortIndexLastInt = self.createInternalObserveTaps(signalToObserve, sruDriverList)
        if observePortIndexLastInt  >= 0:
            observePortIntWidth = Width(msb=IntConst(observePortIndexLastInt), lsb=IntConst(0))
            observePortWireInt = Decl((Wire(self.observePort + "_int", width = observePortIntWidth),))
            items_list = list(moduleNode.items)
            items_list.insert(0, observePortWireInt)
            for assignment in assignmentList:
                items_list.append(assignment)
            moduleNode.items = tuple(items_list)
        return observePortIndexLastInt + 1
    
    # This method does module-wise observe/control hooks for per-module signals
    def stageOneFileModifier(self, file, moduleToSignalToObserve, moduleToSignalToControl):
        ast = self.filewiseAst[file]
        moduleToControlWidth = {}
        moduleToObserveWidth = {}
        moduleDefs = ast.description.definitions
        for moduleDef in moduleDefs:
            if isinstance(moduleDef, ModuleDef):
                logging.info("Inserting control hooks in module - '%s'" %(moduleDef.name))
                sruDriverList, ControlWidth = self.addModuleWiseLogicForControl(moduleDef, moduleToSignalToControl[moduleDef.name])
                moduleToControlWidth.update({moduleDef.name:ControlWidth})
                logging.info("Control hooks insertion in module '%s' complete"%(moduleDef.name))
                logging.info("Inserting observation hooks in module - '%s'"%(moduleDef.name))
                observeWidth = self.addModuleWiseLogicForObservation(moduleDef, moduleToSignalToObserve[moduleDef.name], sruDriverList)
                moduleToObserveWidth.update({moduleDef.name:observeWidth})
                logging.info("Observation hooks insertion in module '%s' complete"%(moduleDef.name))
        return moduleToObserveWidth, moduleToControlWidth
    
    # Returns AST for a module (if it exists): Else returns None
    def getAstForModule(self, moduleName):
        for file in self.fileToModuleToSignalToObserve:
            ast = self.filewiseAst[file]
            for definition in ast.description.definitions:
                if isinstance(definition, ModuleDef):
                    if definition.name == moduleName:
                        return definition
        return None
    
    # Recursive method to insert control/observe hooks in the instantiation hierarchy
    # Sample Instance Tree - {(TOP, Sample):{(inst1, Or):None, (inst2, And):None}}
    #            (TOP, Sample)     
    #                 /\
    #                /  \
    #      (inst1, Or)  (inst2, And)
    #               |    |
    #               |    |
    #            None    None
    # In the above tree, top-module Sample has an instance each of Or and And modules, which are leaf instances
    # Node with value - None indicates a leaf module
    def insertInterModuleHooks(self, moduleNode, treeNode, 
                                                 moduleToObserveWidth,  \
                                                 moduleToControlWidth):   
        if moduleNode is not None:
            # The moduleNode is the current module being processed
            # The value of treeNode[moduleNode] are the instances of other modules within that module
            childModules = treeNode[moduleNode]
            # Tracker for width of observe/control ports hooked up in each instance within the module
            controlPortInstIndex = 0
            observePortInstIndex = 0
            # Get the AST for the current module being processed
            items = list(self.getAstForModule(moduleNode[1]).items)
            ports = list(self.getAstForModule(moduleNode[1]).portlist.ports)
            if childModules is not None:  # Check if this is not a leaf module
                # Non-leaf module operations
                for childModule in childModules:
                    logging.info("--- Adding instance hooks for child module instance '%s(%s)' of module '%s'" %(childModule[0], childModule[1], \
                                                                                                                 moduleNode[1]))
                    # Recurse through child instances before hooking up ports (only if it has not been traversed before
                    # no prevent duplicate hooks)
                    # This would update the controlPortWidth and observePortWidth 
                    if childModule[1] not in self.moduleToControlPortWidth and \
                       childModule[1] not in self.moduleToObservePortWidth:
                        self.insertInterModuleHooks(childModule, {childModule: treeNode[moduleNode][childModule]},  \
                                                                  moduleToObserveWidth,                             \
                                                                  moduleToControlWidth)

                    for item in items:
                        if isinstance(item, InstanceList):
                            instances = item.instances
                            for instance in instances:
                                if isinstance(instance, Instance):
                                    # Ports in the instance portlist
                                    instancePorts = list(instance.portlist)
                                    if instance.name == childModule[0] and self.moduleToObservePortWidth[childModule[1]] > 0:
                                        # Port-Mapping for observe port
                                        lhs = self.observePort
                                        Rhs = Partselect(Identifier(self.observePort + "_inst"),                                                      \
                                                         msb = IntConst(observePortInstIndex + self.moduleToObservePortWidth[childModule[1]] - 1),    \
                                                         lsb = IntConst(observePortInstIndex))
                                        
                                        instancePorts.append(PortArg(lhs,Rhs))
                                        observePortInstIndex += self.moduleToObservePortWidth[childModule[1]]
                                    if instance.name == childModule[0] and self.moduleToControlPortWidth[childModule[1]] > 0:
                                        # Port-Mapping for ControlIn port
                                        lhs = self.controlPortIn
                                        Rhs = Partselect(Identifier(self.controlPortIn + "_inst"),                                                    \
                                                         msb = IntConst(controlPortInstIndex + self.moduleToControlPortWidth[childModule[1]] - 1),    \
                                                         lsb = IntConst(controlPortInstIndex))
                                        instancePorts.append(PortArg(lhs,Rhs))
                                        # Port-Mapping for ControlOut port
                                        lhs = self.controlPortOut
                                        Rhs = Partselect(Identifier(self.controlPortOut + "_inst"),                                                   \
                                                         msb = IntConst(controlPortInstIndex + self.moduleToControlPortWidth[childModule[1]] - 1),    \
                                                         lsb = IntConst(controlPortInstIndex))
                                        instancePorts.append(PortArg(lhs,Rhs))
                                        controlPortInstIndex += self.moduleToControlPortWidth[childModule[1]]
                                    instance.portlist = tuple(instancePorts)
            # The mmodule has both internal and instance-wise observe ports
            if observePortInstIndex > 0 and moduleToObserveWidth[moduleNode[1]] > 0:
                logging.info("-- Module '%s' has both internal and instance-wise observe hooks - Concatenating them to the module observe port" %(moduleNode[1]))
                # Declare <observePort>_inst wire
                observePortInstWidth = Width(msb = IntConst(observePortInstIndex - 1), lsb = IntConst(0))
                items.insert(0, Decl((Wire(self.observePort + "_inst", width = observePortInstWidth),)))
                # Add assignment: assign <observePort> = {<obervePort>_int, <observePort>_inst}
                lhs = Identifier(self.observePort)
                concatWireOne = Identifier(self.observePort + "_int")
                concatWireTwo = Identifier(self.observePort + "_inst")
                rhs = Concat([concatWireOne, concatWireTwo])
                items.append(Assign(lhs, rhs))
                self.getAstForModule(moduleNode[1]).items = tuple(items)
            # The module has instance-wise but no internal observe ports
            elif observePortInstIndex > 0 and moduleToObserveWidth[moduleNode[1]] == 0:
                logging.info("-- Module '%s' has only observe hooks from instances - Assigning them to the module observe port" %(moduleNode[1]))
                # Declare <observePort>_inst wire
                observePortInstWidth = Width(msb = IntConst(observePortInstIndex - 1), lsb = IntConst(0))
                items.insert(0, Decl((Wire(self.observePort + "_inst", width = observePortInstWidth),)))
                # Add assignment: assign <observePort> = <observePort>_inst
                lhs = Identifier(self.observePort)
                rhs = Identifier(self.observePort + "_inst")
                items.append(Assign(lhs, rhs))
                self.getAstForModule(moduleNode[1]).items = tuple(items)

            # The module has internal but no instance-wise observe ports
            elif observePortInstIndex == 0 and moduleToObserveWidth[moduleNode[1]] > 0:
                logging.info("-- Module '%s' has only internal observe hooks - Assigning them to the module observe port" %(moduleNode[1]))
                # Add assignment: assign <observePort> = <observePort>_int
                lhs = Identifier(self.observePort)
                rhs = Identifier(self.observePort + "_int")
                items.append(Assign(lhs, rhs))  
                self.getAstForModule(moduleNode[1]).items = tuple(items)  

            else:
                logging.info("-- Module '%s' has neither internal not instance-wise observe hooks" %(moduleNode[1]))

            # The module has both internal and instance-wise control ports
            if controlPortInstIndex > 0 and moduleToControlWidth[moduleNode[1]] > 0:
                logging.info("-- Module '%s' has both internal and instance-wise control hooks - Concatenating them to the module control port" %(moduleNode[1]))
                # Declare wire <controlPortIn_inst>
                controlPortInstWidth = Width(msb = IntConst(controlPortInstIndex - 1), lsb = IntConst(0))
                items.insert(0, Decl((Wire(self.controlPortIn + "_inst", width = controlPortInstWidth),)))
                # Add assignment assign <controlPortIn> = {<controlPortIn>_int, <controlPortIn>_inst}
                lhs = Identifier(self.controlPortIn)
                concatWireOne = Identifier(self.controlPortIn + "_int")
                concatWireTwo = Identifier(self.controlPortIn + "_inst")
                rhs = Concat([concatWireOne, concatWireTwo])
                items.append(Assign(lhs, rhs))
                # Declare wire <controlPortOut_inst>
                items.insert(0, Decl((Wire(self.controlPortOut + "_inst", width = controlPortInstWidth),)))
                # Add assignment assign {<controlPortOut>_int, <controlPortOut>_inst} = <controlPortOut>
                concatWireOne = Identifier(self.controlPortOut + "_int")
                concatWireTwo = Identifier(self.controlPortOut + "_inst")
                lhs = Concat([concatWireOne, concatWireTwo])
                rhs = Identifier(self.controlPortOut)
                items.append(Assign(lhs, rhs))
                self.getAstForModule(moduleNode[1]).items = tuple(items)

            # The module has instance-wise but no internal control ports
            elif controlPortInstIndex > 0 and moduleToControlWidth[moduleNode[1]] == 0:
                logging.info("-- Module '%s' has only control hooks from instances - Assigning them to the module control port" %(moduleNode[1]))
                # Declare wire <controlPortIn_inst>
                controlPortInstWidth = Width(msb = IntConst(controlPortInstIndex - 1), lsb = IntConst(0))
                items.insert(0, Decl((Wire(self.controlPortIn + "_inst", width = controlPortInstWidth),)))
                # Add assignment assign <controlPortIn> = <controlPortIn>_inst
                lhs = Identifier(self.controlPortIn)
                rhs = Identifier(self.controlPortIn + "_inst")
                items.append(Assign(lhs, rhs))
                # Add assignment assign <controlPortOut> = <controlPortOut>_inst
                lhs = Identifier(self.controlPortOut + "_inst")
                rhs = Identifier(self.controlPortOut)
                items.append(Assign(lhs, rhs))
                self.getAstForModule(moduleNode[1]).items = tuple(items)  

            # The module has internal but no instance-wise control ports
            elif controlPortInstIndex == 0 and moduleToControlWidth[moduleNode[1]] > 0:
                logging.info("-- Module '%s' has only internal control hooks - Assigning them to the module control port" %(moduleNode[1]))
                # Add assignment assign <controlPortIn> = <controlPortIn>_int
                lhs = Identifier(self.controlPortIn)
                rhs = Identifier(self.controlPortIn + "_int")
                items.append(Assign(lhs, rhs))
                # Add assignment assign <controlPortOut> = <controlPortOut>_int
                lhs = Identifier(self.controlPortOut + "_int")
                rhs = Identifier(self.controlPortOut)
                items.append(Assign(lhs, rhs))
                self.getAstForModule(moduleNode[1]).items = tuple(items)  
            else:
                logging.info("-- Module '%s' has neither internal nor instance-wise control hooks" %(moduleNode[1]))

            # Final observe/control port width     
            self.moduleToObservePortWidth[moduleNode[1]] = observePortInstIndex + moduleToObserveWidth[moduleNode[1]]
            self.moduleToControlPortWidth[moduleNode[1]] = controlPortInstIndex + moduleToControlWidth[moduleNode[1]]
            
            # IO Port declaration for the current module
            if observePortInstIndex != 0 or moduleToObserveWidth[moduleNode[1]] != 0: 
                logging.info("-- Inserting primary observe port in module '%s'" %(moduleNode[1]))
                observePortTotalWidth = Width(msb = IntConst(self.moduleToObservePortWidth[moduleNode[1]]-1), lsb = IntConst(0))
                observePortOutput = Ioport(Output(self.observePort, width = observePortTotalWidth))
                ports.append(observePortOutput)
                self.getAstForModule(moduleNode[1]).portlist.ports = tuple(ports)
            if  controlPortInstIndex != 0 or moduleToControlWidth[moduleNode[1]] != 0:
                logging.info("-- Inserting primary control port in module '%s'" %(moduleNode[1]))
                controlPortTotalWidth = Width(msb = IntConst(self.moduleToControlPortWidth[moduleNode[1]]-1), lsb = IntConst(0))
                controlPortOutput = Ioport(Output(self.controlPortIn, width =controlPortTotalWidth))
                controlPortInput  = Ioport(Input(self.controlPortOut, width =controlPortTotalWidth))
                ports.extend([controlPortOutput, controlPortInput])
                self.getAstForModule(moduleNode[1]).portlist.ports = tuple(ports)
            
        else:
            return
    
    def stageTwoFileModifier(self, moduleToObserveWidth, moduleToControlWidth):
        # Top module node in instance tree
        topModuleNode = ("TOP", self.topModule)
        self.insertInterModuleHooks(moduleNode           = topModuleNode,        \
                                    treeNode             = self.instanceTree,    \
                                    moduleToControlWidth = moduleToControlWidth, \
                                    moduleToObserveWidth = moduleToObserveWidth)
        
    # Method to generate the observe/control signal map and signal to control type map
    # This map is used by ASAP compiler to generate bitstream  
    def getSignalList(self, treeNode, currentModule, moduleToObserveSignal, moduleToControlSignal, observeIndex = 0, controlIndex = 0):
        if treeNode is not None:
            observeSignalList = {}
            controlSignalList = {}
            # Records the type of controlled signal (signal/clock)
            signalToControlType = {}
            observeSignals = moduleToObserveSignal[currentModule[1]]
            controlSignals = moduleToControlSignal[currentModule[1]]

            # First: Update the list with signals of internal instances sequentially (use recursion)
            if treeNode[currentModule] is not None:
                for child in treeNode[currentModule]:
                    observeChild, controlChild,    \
                    controlTypeChild,              \
                    observeIndex, controlIndex = self.getSignalList(treeNode[currentModule], \
                                                                    child,                   \
                                                                    moduleToObserveSignal,   \
                                                                    moduleToControlSignal,   \
                                                                    observeIndex,            \
                                                                    controlIndex)
                    observeSignalList.update(observeChild)
                    controlSignalList.update(controlChild)
                    signalToControlType.update(controlTypeChild)
            # Second: Update the list with all the signals in the current module being processed
            for signal in observeSignals:
                observeSignalList.update({signal:[observeSignals[signal][0] - observeSignals[signal][1] + observeIndex, observeIndex]})
                observeIndex +=  observeSignals[signal][0] - observeSignals[signal][1] + 1
            for signal in controlSignals:
                controlSignalList.update({signal:[controlSignals[signal][1] - controlSignals[signal][2] + controlIndex, controlIndex]})
                signalToControlType.update({signal:controlSignals[signal][0]})
                controlIndex +=  controlSignals[signal][1] - controlSignals[signal][2] + 1
            
            return {currentModule[0]:observeSignalList}, {currentModule[0]:controlSignalList}, \
                   {currentModule[0]:signalToControlType}, observeIndex, controlIndex
        else:
            return None, None



    # This method modifies the AST for inserting observation/control hooks
    #            __________________________                   __________________________
    #           |                          |                  |                          |
    # AST ------|      Stage 1             |------------------|      Stage 2             |----- Modified AST
    #           | (Intra Module Insertion) |                  | (Inter Module Insertion) |
    #           |__________________________|                  |__________________________|
    #
    # Stage 1: Intra module insertion inserts patch hooks for signal observed/controlled within module
    # Stage 2: Inter module insertion connects up patch hooks between module hierarchies
    def astModifier(self):
        moduleToObserveWidth = {}
        moduleToControlWidth = {}
        consolidatedModuletoSignalToObserve = {}
        consolidatedModuletoSignalToControl = {}
        # STAGE - 1 (Intra module hook insertion)
        for file in self.fileToModuleToSignalToObserve :
            logging.info("Stage 1 AST modification: Inserting internal observe/control hooks in file - %s" %(file))
            moduleToObserveWidthPerFile, moduleToControlWidthPerFile =  self.stageOneFileModifier(file, self.fileToModuleToSignalToObserve[file], 
                                                                                                        self.fileToModuleToSignalToControl[file])
            logging.info("Stage 1 AST modification complete")
            moduleToObserveWidth.update(moduleToObserveWidthPerFile)
            moduleToControlWidth.update(moduleToControlWidthPerFile)
            consolidatedModuletoSignalToObserve.update(self.fileToModuleToSignalToObserve[file])
            consolidatedModuletoSignalToControl.update(self.fileToModuleToSignalToControl[file])

        # STAGE - 2 (Inter module hook insertion)   
        logging.info("Stage 2 AST modification: Connecting cross-module observe/control hooks")
        self.stageTwoFileModifier(moduleToObserveWidth, \
                                  moduleToControlWidth)
        logging.info("Stage 2 AST modification complete")

        # Generate signalMap
        observeSignalList, controlSignalList, signalToControlType, observeWidth, controlWidth = self.getSignalList(self.instanceTree,                    \
                                                                                                                   ("TOP", self.topModule),              \
                                                                                                                   consolidatedModuletoSignalToObserve,  \
                                                                                                                   consolidatedModuletoSignalToControl)
        logging.info("Net width of control signal = %d"%(controlWidth))
        logging.info("Net width of observe signal = %d"%(observeWidth))
        return observeSignalList, controlSignalList, signalToControlType

    def genModifiedVerilogFile(self, file):
        logging.info("Generating modified verilog files...")
        codegen = ASTCodeGenerator()
        newFilename = self.outputFolder + "/" + os.path.basename(file)
        verilogCode = codegen.visit(self.filewiseAst[file])
        with open(newFilename, "w") as f:
            f.write(str(verilogCode))
        logging.info("File write completed.")
    
    # This method generates new verilog code for each file in the filelist
    def generateVerilog(self):
        logging.info("Starting cross-module patch hook insertion.....")
        observeSignalList, controlSignalList, signalToControlType = self.astModifier()
        logging.info("Cross module patch hook insertion complete")
        for file in self.fileToModuleToSignalToObserve:
            self.genModifiedVerilogFile(file)
        return observeSignalList, controlSignalList, signalToControlType


# This class reorders the controlMap to generate controls in the order requried by SRU
# If the arch requirements of SRU changes, this has to be changed.
class ControlSignalMappingModel:
    def __init__(self, controllabilityMap, controlTypeMap) -> None:
        self.controllabilityMap = controllabilityMap
        self.controlTypeMap     = controlTypeMap
        logging.info("Original control map - %s"%(self.controllabilityMap))
        self.controlledSignalMap, self.numSignalControls  = self.controlReorder(0,                       \
                                                                                self.controllabilityMap, \
                                                                                self.controlTypeMap,     \
                                                                                "signal")     
        logging.info("Signal control size = %d"%(self.numSignalControls))
        logging.info("Reordered signal control map - %s"%(self.controlledSignalMap))
        self.controlledClkMap, self.numClkControls = self.controlReorder(self.numSignalControls,  \
                                                                         self.controllabilityMap, \
                                                                         self.controlTypeMap,     \
                                                                         "clock")  
        self.numClkControls = self.numClkControls - self.numSignalControls
        logging.info("Clock control size = %d"%(self.numClkControls))
        logging.info("Reordered clock control map - %s"%(self.controlledClkMap))
        # Merge signal and clock control maps in the order {signal control, clock control}


    
    def controlReorder(self, currentIndex, currentControlMap, currentTypeMap, signalType):
        reorderedControlMap = {}
        for element in currentControlMap:
            if isinstance(currentControlMap[element], dict):
                child, currentIndex = self.controlReorder(currentIndex,               \
                                                          currentControlMap[element], \
                                                          currentTypeMap[element],    \
                                                          signalType) 
                if child:
                    reorderedControlMap.update({element:child})
            else:
                if currentTypeMap[element] == signalType:
                    reorderedLsb = currentIndex
                    reorderedMsb = currentIndex + (currentControlMap[element][0] - currentControlMap[element][1])
                    reorderedControlMap.update({element:[reorderedMsb, reorderedLsb]})
                    currentIndex += ((currentControlMap[element][0] - currentControlMap[element][1]) + 1)
        return reorderedControlMap, currentIndex


# This class generates the top-level patch block comprising of SMU and SRU block with appropriate connectivity
class TopPatchBlockGenerator:
    def __init__(self, 
                 topFileName,
                 # SMU Params and Vars
                 smuModuleName,       \
                 smuSegmentSize,      \
                 observeSignalList,   \
                 maxTriggers,         \
                 maxseqDepth,         \
                 # SRU Params and vars
                 sruModuleName,       \
                 sruSegmentSize,      \
                 sruNumPla,           \
                 controlSignalList,   \
                 signalToControlType, \
                ) -> None:
        
        
        self.topFileName         = topFileName
        # SMU Params and required vars
        self.smuModuleName       = smuModuleName
        self.observeSignalList   = observeSignalList
        self.smuSegmentSize      = smuSegmentSize
        self.maxTriggers         = maxTriggers
        self.maxseqDepth         = maxseqDepth
        self.observeSize         = self.getMaximalIndexInMap(self.observeSignalList, 0) + 1
        # SRU Params and required Vars
        self.sruModuleName       = sruModuleName
        self.controlSignalList   = controlSignalList
        self.signalToControlType = signalToControlType
        self.sruSegmentSize      = sruSegmentSize
        self.sruNumPla           = sruNumPla
        self.controlSize         = self.getMaximalIndexInMap(self.controlSignalList, 0) + 1
        # Top-model related vars
        self.reorderMap          = ControlSignalMappingModel(self.controlSignalList,   \
                                                             self.signalToControlType)
    
    def getTopIOAndParams(self):
        paramMap = {  "N"                   :  Parameter('N', Rvalue(IntConst(self.maxseqDepth))),
                      "K"                   :  Parameter('K', Rvalue(IntConst(self.observeSize))),
                      "M"                   :  Parameter('M', Rvalue(IntConst(self.maxTriggers))),
                      "C"                   :  Parameter('C', Rvalue(IntConst(self.reorderMap.numClkControls))),
                      "S"                   :  Parameter('S', Rvalue(IntConst(self.reorderMap.numSignalControls))),
                      "CONTROL_WIDTH"       :  Parameter('CONTROL_WIDTH', Rvalue(Plus(Identifier('C'), Identifier('S')))),
                      "NUM_PLA"             :  Parameter('NUM_PLA', Rvalue(IntConst(self.sruNumPla))),
                      "SRU_SEGMENT_SIZE"    :  Parameter("SRU_SEGMENT_SIZE", Rvalue(IntConst(self.sruSegmentSize))),
                      "SMU_SEGMENT_SIZE"    :  Parameter("SMU_SEGMENT_SIZE", Rvalue(IntConst(self.smuSegmentSize))) 
        }

        portMap = { "clkPort"               :  Ioport(Input('clk')),
                    "cfgClkPort"            :  Ioport(Input('cfgClk')),
                    "rstPort"               :  Ioport(Input('rst')),
                    "bitstreamSerialInPort" :  Ioport(Input('bitstreamSerialIn')),
                    "smuStreamValidPort"    :  Ioport(Input('smuStreamValid')),
                    "sruStreamValidPort"    :  Ioport(Input('sruStreamValid')),
                    # Observable input vector
                    "p"                     :  Ioport(Input('p', width = Width(
                                                                           Minus(Identifier('K'), IntConst('1')), 
                                                                           IntConst('0')
                                                                          )
                                                           )
                                                     ),
                    # Controllable signal input
                    "qIn"                   :  Ioport(Input('qIn', width = Width(
                                                                            Minus(Identifier('CONTROL_WIDTH'), IntConst('1')), 
                                                                            IntConst('0')
                                                                          )   
                                                            )
                                                     ),  
                    # Controlled signal output  
                    "qOut"                   : Ioport(Output('qOut', width = Width(
                                                                             Minus(Identifier('CONTROL_WIDTH'), IntConst('1')), 
                                                                             IntConst('0')
                                                                          )   
                                                            )
                                                     )                                               
                                                      
        }  
        paramList = Paramlist([paramMap[param] for param in paramMap])
        portList  = Portlist([portMap[port] for port in portMap])
        return portList, paramList  
    
    # This method retrieves the maximum LSB indices of signals in a given signal tree
    def getMaximalIndexInMap(self, signalMap, maxIndex):
        for key in signalMap:
            if isinstance(signalMap[key], dict):
                maxIndex = self.getMaximalIndexInMap(signalMap[key], maxIndex)
            else:
                # Find if LSB > maximal index
                if maxIndex < signalMap[key][0]:
                    maxIndex = signalMap[key][0]
        return maxIndex


    def originalToRearrangedControlMapping(self, primaryControlNode, referenceNode, signalMapList:list):
        for key in primaryControlNode:
            if isinstance(primaryControlNode[key], dict):
                self.originalToRearrangedControlMapping(primaryControlNode[key], referenceNode[key], signalMapList)
            elif isinstance(primaryControlNode[key], list):
                signalMapList.append((primaryControlNode[key],referenceNode[key]),)
            else:
                raise Exception("Invalid signal Map") 
        return signalMapList

    # The actual control signals coming into this module may not be ordered as per SRU
    # requirement -- ({Clock controls, Signal controls})
    # This method provides assignments for re-arranging the controls
    def getRearrangedControlAssignments(self):
        items = []
        items.append(Wire("qInInternal",  width = Width(Minus(Identifier('CONTROL_WIDTH'), IntConst('1')), IntConst('0'))))
        items.append(Wire("qOutInternal", width = Width(Minus(Identifier('CONTROL_WIDTH'), IntConst('1')), IntConst('0'))))
        signalMapList = []
        self.originalToRearrangedControlMapping(self.reorderMap.controlledClkMap, \
                                                self.controlSignalList,           \
                                                signalMapList)
        self.originalToRearrangedControlMapping(self.reorderMap.controlledSignalMap, \
                                                self.controlSignalList,           \
                                                signalMapList)
        for item in signalMapList:
            newInpAssignNode = Assign(
                Lvalue(Partselect(Identifier('qInInternal'), 
                                  msb = IntConst(str(item[0][0])),
                                  lsb = IntConst(str(item[0][1])))),
                Rvalue(Partselect(Identifier('qIn'),
                                  msb = IntConst(str(item[1][0])),
                                  lsb = IntConst(str(item[1][1]))))
            )
            newOutAssignNode = Assign(
                Lvalue(Partselect(Identifier('qOut'), 
                                  msb = IntConst(str(item[1][0])),
                                  lsb = IntConst(str(item[1][1])))),
                Rvalue(Partselect(Identifier('qOutInternal'),
                                  msb = IntConst(str(item[0][0])),
                                  lsb = IntConst(str(item[0][1]))))
            )
            items.extend([newInpAssignNode, newOutAssignNode])
        return items
    


    # This method generates the SMU instance. It also generates the trigger declaration
    # as trigger is an internal signal that is connected to SRU
    def getSmuAndSruInstances(self):
        items = []
        items.append(Wire("trigger",  width = Width(Minus(Identifier('M'), IntConst('1')), IntConst('0'))))
        smuPortArgMap = {
            "clk"                 : "clk",
            "rst"                 : "rst",
            "cfgClk"              : "cfgClk",
            "bitstreamSerialIn"   : "bitstreamSerialIn",
            "bitstreamValid"      : "smuStreamValid",
            "p"                   : "p",
            "trigger"             : "trigger"
        }
        smuParamMap = {
            "N"                   :  "N",
            "K"                   :  "K",
            "M"                   :  "M",
            "SMU_SEGMENT_SIZE"    : "SMU_SEGMENT_SIZE"
         }
        sruPortArgMap = {
            "clk"                 : "clk",
            "rst"                 : "rst",
            "cfgClk"              : "cfgClk",
            "bitstreamSerialIn"   : "bitstreamSerialIn",
            "bitstreamValid"      : "sruStreamValid",
            "Qin"                 : "qInInternal",
            "Qout"                : "qOutInternal",
            "trigger"             : "trigger"
        }
        sruParamMap = {
            "M"                   :  "M",
            "C"                   :  "C",
            "S"                   :  "S",
            "NUM_PLA"             :  "NUM_PLA",
            "SRU_SEGMENT_SIZE"    : "SRU_SEGMENT_SIZE"
         }
        
        ## Construction of SMU instance
        portlist = []
        paramlist = []
        for port in smuPortArgMap:
            portArg = PortArg(
                portname = port,
                argname  = Identifier(smuPortArgMap[port])
            )
            portlist.append(portArg)
        for param in smuParamMap:
            paramNode = ParamArg(
                paramname = param,
                argname   = Identifier(smuParamMap[param])
            )
            paramlist.append(paramNode)

        smuInstance = Instance(
            module         = self.smuModuleName,
            name           = "smu_inst",
            portlist       = tuple(portlist),
            parameterlist  = tuple(paramlist)
        )

        smuInstanceList = InstanceList(
            module        = self.smuModuleName,
            parameterlist = smuInstance.parameterlist,
            instances     = [smuInstance]
        )

        ## Construction of SRU instance
        portlist = []
        paramlist = []
        for port in sruPortArgMap:
            portArg = PortArg(
                portname = port,
                argname  = Identifier(sruPortArgMap[port])
            )
            portlist.append(portArg)
        for param in sruParamMap:
            paramNode = ParamArg(
                paramname = param,
                argname   = Identifier(sruParamMap[param])
            )
            paramlist.append(paramNode)

        sruInstance = Instance(
            module        = self.sruModuleName,
            name          = "sru_inst",
            portlist      = tuple(portlist),
            parameterlist = tuple(paramlist)
        )

        sruInstanceList = InstanceList(
            module        = self.sruModuleName,
            parameterlist = sruInstance.parameterlist,
            instances     = [sruInstance]
        )
        items.extend([smuInstanceList, sruInstanceList])
        return items
    
    # Method to generate TOP-MODULE
    def generateTopModule(self):
        portList, paramList = self.getTopIOAndParams()
        controlAssignItems  = self.getRearrangedControlAssignments()
        instanceItems       = self.getSmuAndSruInstances()

        items = []
        items.extend(controlAssignItems)
        items.extend(instanceItems)

        topModule = ModuleDef(
            name       = "patchBlock",
            items      = items,
            paramlist  = paramList,
            portlist   = portList
        )
        codeGen = ASTCodeGenerator()
        verilogCode = codeGen.visit(topModule)
        with open(self.topFileName, "w") as f:
            f.write(str(verilogCode))


class ASAPInsertion:
    def __init__(self, specFile, outputFolder):
        # Semi-Static Constants - Please don't change these as of now due to code dependency
        OBSERVE_PORT_NAME     = "observe_port"
        CONTROL_PORT_IN_NAME  = "control_port_in"
        CONTROL_PORT_OUT_NAME = "control_port_out"
        SMU_MODULE_NAME       = "smu"
        SRU_MODULE_NAME       = "sru"
        TOP_FILE_NAME         = outputFolder + "/asapTop.v"
        ASAP_INTERFACE_FILE   = outputFolder + "/asap_interface.json"

        paramMap = {}
        # asap_param.txt has all the relevant configurable params for ASAP architecture
        with open(specFile, "r") as paramFile:
            for line in paramFile:
                assert len(line.split('=')) == 2, "Incorrect param specififed in %s"%(specFile)
                paramMap.update({line.split('=')[0].strip(): line.split('=')[1].strip()})
                
        # SMU Params
        TOP_MODULE        = paramMap['TOP_MODULE']
        FILELIST          = paramMap['FILELIST']
        SMU_SEGMENT_SIZE  = int(paramMap['SMU_SEGMENT_SIZE'])
        MAX_SEQ_DEPTH     = int(paramMap['MAX_SEQ_DEPTH'])
        MAX_TRIGGERS      = int(paramMap['MAX_TRIGGERS'])
        
        # SRU PARAMS
        SRU_SEGMENT_SIZE  = int(paramMap['SRU_SEGMENT_SIZE'])
        SRU_NUM_PLA       = int(paramMap['SRU_NUM_PLA'])

        # Make sure all provided paths exists
        assert os.path.exists(specFile), "Specification file %s doesn't exist"%(specFile)
        assert os.path.exists(outputFolder), "Output folder %s doesn't exist"%(outputFolder)
        assert os.path.exists(FILELIST), "Filelist %s doesn't exist"%(FILELIST)

        logging.info("Verilog signal parsing started for filelist %s"%(FILELIST))
        ## Instantiating parser
        parser = VerilogParser(FILELIST, TOP_MODULE)
        fileToModuleToSignalToObserve, fileToModuleToSignalToControl = parser.fileToModuleToSignalToPragma()
        filewiseAst = parser.fileToAst
        moduleWiseAst = parser.moduleToAst
        ## Instantiating the insertion class
        verilogGenerator = VerilogGenerator(filewiseAst,                      \
                                            moduleWiseAst,                    \
                                            outputFolder,                     \
                                            parser.tree,                      \
                                            TOP_MODULE,                       \
                                            fileToModuleToSignalToObserve,    \
                                            fileToModuleToSignalToControl,    \
                                            OBSERVE_PORT_NAME,                \
                                            CONTROL_PORT_IN_NAME,             \
                                            CONTROL_PORT_OUT_NAME)
        observeSignalList, controlSignalList, signalToControlType = verilogGenerator.generateVerilog()
        # Writing observability/controllability in to interface JSON file
        ioData = {
            'OBSERVABILITY_MAP'    : observeSignalList,
            'CONTROLLABILITY_MAP'  : controlSignalList,
            'CONTROL_TYPE_MAP'     : signalToControlType
        }

        # Write the SMU/SRU observe/control interface information to asap_interface.json file for ASAP compiler
        with open(ASAP_INTERFACE_FILE, "w") as ioFile:
            json.dump(ioData, ioFile, indent = 4)  
        logging.info("Observed signal map - %s"%(observeSignalList))
        logging.info("Controlled signal map - %s"%(controlSignalList))
        logging.info("control type map - %s"%(signalToControlType))


        # Instance of top-module generator
        top = TopPatchBlockGenerator(
            topFileName          = TOP_FILE_NAME,
            smuModuleName        = SMU_MODULE_NAME,
            smuSegmentSize       = SMU_SEGMENT_SIZE,
            observeSignalList    = observeSignalList,
            maxTriggers          = MAX_TRIGGERS,
            maxseqDepth          = MAX_SEQ_DEPTH,
            sruModuleName        = SRU_MODULE_NAME,
            sruSegmentSize       = SRU_SEGMENT_SIZE,
            sruNumPla            = SRU_NUM_PLA,
            controlSignalList    = controlSignalList,
            signalToControlType  = signalToControlType
        )
        top.generateTopModule()
