from typing import List
import ply.lex as lex
import logging                                                       # logger
import pyfiglet                                                      # ASCII formatter (Just for tooling fun :) :))
import re                                                            # Regex
import sys
from typing import Union
import math
from   functools import reduce
import copy
import json
from enum import Enum

#--------------------------------------------- LOGGER SETUP----------------------------------------#
# Configure logging - Done at file top so that all classes have it accessible
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Setting up log file
fileHandler = logging.FileHandler('ASAPCompiler.log', mode='w') 
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fileHandler.setFormatter(formatter)
logging.getLogger().addHandler(fileHandler)
logging.info("Started Automatic, Scalable And Programmable (ASAP) tool for Hardware Patching...\n\n " + pyfiglet.figlet_format("ASAP COMPILER"))
#--------------------------------------------------------------------------------------------------#


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
    
    def logSRUOrderedMap(self,orderedMap):
        data = ""
        for cfgType in SRUCfgType:
            if cfgType in [SRUCfgType.PLA_SEL, SRUCfgType.CNTL_ENB, SRUCfgType.CONSTANT]:
                for controlType in ControlType:
                    data += "\n For configType - %s, controlType %s, ordered config is %s"%(str(cfgType),
                                                                                            str(controlType),
                                                                                            self.logDictInfo(orderedMap[cfgType.value][controlType.value]))
            else:
                data += "\n For configType - %s, ordered config is %s"%(str(cfgType),
                                                                        self.logDictInfo(orderedMap[cfgType.value]))
        return data
    
    def logSMUOrderedMap(self, orderedMap, numTriggers, seqDepth):
        data = ""
        for trigger in range(0,numTriggers):
            for cycle in range(0, seqDepth):
                for cfgtype in SMUCfgType:
                    data += "\n For trigger %d, in cycle %d, CfgType %s is %s"%(trigger,
                                                                                cycle,
                                                                                str(cfgtype),
                                                                                orderedMap[cycle][trigger][cfgtype.value])
                data += "\n"
        return data


        

# **************************** <SMU PATCH FILE (<name>.asap.smu) GRAMMER> *************************************
# Every observable sequence is enclosed within - {}
# Within an observable sequence, a pattern is enclosed within <>
# There can be multiple patterns in a sequence.
# A pattern can have multiple 'pattern tokens' enclosed within ()
# One can have any number of pattern tokens in a pattern. 
# We have two possible operation between tokens - & and |
# Example sequence - 
# seq s0 {
#  (TOP.A[1:0] == 2'b00)
#  (TOP.inst1.inter[1:0] > 2'b10)
# }
#Given below is the AST for the above sequence. A SequenceList may have multiple sequences
#
#SequenceList(List(Sequences))
#  |
#  +-- Sequence(List(Pattern), name = "s0")
#        |
#        +-- Pattern (Variable, Comparison, Constant)
#        |     |
#        |     +-- Variable (name = TOP.A, msb = 1, lsb = 0)
#        |     +-- Comparison (operator = "==")      
#        |     +-- Const (width = 2, binaryValue = "00")     
#        |     |     
#        |          
#        |
#        +-- Pattern (Variable, Comparison, Constant)
#              |
#              +-- Variable (name = TOP.inst1.inter, msb = 1, lsb = 0)
#              +-- Comparison (operator = ">")
#              +-- Const (width = 2, binaryValue = "10")

#
# Refer the code for detailed analysis of the structures

#  ****  AST Structures for ASAP-SMU Programming Language **** #

# A Const is always a sized binary representation like 3'b010.
# For 3'b010, width = 3, binaryValue = 010
class Const:
    def __init__(self, width:int, binaryValue:str):
        self.width = width
        self.binaryValue = binaryValue

    def __repr__(self):
        return f'Constant({self.width}\'b{self.binaryValue})'

# A variable is always a partselected var like A[1:0]
# It may also have hierarchy in name - e.g. TOP.inst1.sig[1:0]
# In that case, TOP.inst1.sig becomes name, msb = 1, lsb = 0        
class Variable:
    def __init__(self, name:str, msb:int, lsb:int):
        self.name = name
        self.msb  = msb
        self.lsb  = lsb

    def __repr__(self):
        return f'Variable({self.name}[{self.msb}:{self.lsb}])'


# Comparison node - Can be either '<' or '>' or '=='
class Comparison:
    def __init__(self, operator: str):
        self.operator = operator

    def __repr__(self) -> str:
        return f'Comparison({self.operator})'


# Pattern AST Node
# A Pattern is always an comparison operation statement with LHS and RHS. e.g. A[1:0] == 2'b00 / A[1:0] > 2'b01 /  A[1:0] < 2'b11 
# Here RHS is a variable representing a part-selected signal (being observed). RHS is a constant (Const node)
# Additionally, there would be a comparison (Comparison node) operation
class Pattern:
    def __init__(self, lhs: Variable, opType: Comparison, rhs: Const):
        self.lhs = lhs
        self.opType = opType 
        self.rhs = rhs

    def __repr__(self):
        return f'Pattern({self.lhs} {self.opType} {self.rhs})'


# Sequence AST node - Contains a list of all patterns in the sequence
class Sequence:
    def __init__(self, patterns: List['Pattern'], name: str):
        self.patterns = patterns if patterns is not None else []
        self.name = name

    def addPatterns(self, pattern):
        self.patterns.append(pattern)

    def __repr__(self):
        return f'Sequence({self.name} {self.patterns})'
    

# Top-level AST node - Conatains a list of all sequences in SMU patch code
class SequenceList:
    def __init__(self, sequences:List['Sequence']):
        self.sequences = sequences if sequences is not None else []

    def addSequences(self, sequence):
        self.sequences.append(sequence)

    def __repr__(self):
        return f'SequenceList([{self.sequences}])'
    

# **************************** <SRU PATCH FILE (<name>.asap.sru) GRAMMER> *************************************
# Every signal begins with type of <type of control> and <name>
# The details of a signal control is always enclosed within {}
# Given below is a sample of signal control
# signal s0 {
#  control = <SOP expression of pattern sequence triggers>
#  constant = binary bit vector
# }
# Given below is is a sample of clock control
# clock c0 {
#  control = <SOP expression of pattern sequence triggers>
# }
# ControlNodeList(List(Union(Signal, Clock)))
#   |
#   +-- Signal (Variable, PosExpr, Const)    
#       |
#       +-- Variable (name = TOP.A, msb = 1, lsb = 0)
#       +-- PosExpr (operator = "==")      
#       +-- Const (width = 2, binaryValue = "00")     
#        
#   +-- Clock (Variable, PosExpr)    
#       |
#       +-- Variable (name = TOP.A, msb = 1, lsb = 0)
#       +-- PosExpr (operator = "==")      



# AST node for holding POS expressions
# The node does additional functions like finding all the associated variables and the expanded minterms
class PosExpr(LogStructuring):
    def __init__(self, expr:str) -> None:
        self.expr = expr
        self.exprTokens  = self.getExprTokens(expr)
        self.VarList     = self.getVarList()

    def getExprTokens(self, expr):
        return  [token.strip() for token in expr.split('+')]
    
    def getVarList(self):
        varList = set()
        for token in self.exprTokens:
            # Use regular expression to find variables and complements
            matches = re.findall(r'([a-zA-Z0-9]+)(?:\')?', token)
            for match in matches:
                varList.add(match)
        return list(varList)
    
    # Returns the set of exprtokens
    def getExprSet(self):
        return frozenset(self.exprTokens)

    def __repr__(self):
        return f'PosExpr({self.expr})'


# AST node for Signal control node
class Signal:
    def __init__(self, signal: Variable, trigger: PosExpr, constant: Const):
        self.signal   = signal
        self.trigger  = trigger
        self.constant = constant

    def __repr__(self):
        return f'Signal({self.signal}, {self.trigger}, {self.constant}'


# AST node for Clock control node
class Clock:
    def __init__(self, signal: Variable, trigger: PosExpr):
        self.signal  = signal
        self.trigger = trigger

    def __repr__(self):
        return f'Clock({self.signal}, {self.trigger})'
    

# Top-level AST Node - Holds a list of all control nodes (Signal/Clock types)
class ControlNodeList:
    def __init__(self, controlBlocks:List['Union[Signal, Clock]']):
        self.controlNodes = controlBlocks if controlBlocks is not None else []

    def addControlNode(self, controlNode):
        self.controlNodes.append(controlNode)

    def __repr__(self):
        return f'ControlNodeList({self.controlNodes})'    
    

# Base lexer class for definiting ignore/error rules - To be used by both SMU and SRU lexers
class BaseLexer:
    # Ignored characters shared by all lexer classes
    t_ignore = ' \t\n'

    def t_error(self, t):
        logging.info("Lexer error: Illegal character '%s'" % t.value[0])
        t.lexer.skip(1)


# Lexer Class for tokenizing SMU patch code
class ASAPSmuLexer(BaseLexer):
    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def __init__(self, **kwargs):
    # Token definitions for SMU Programming language
        self.tokens = (
            'SEQUENCE_START',  # '{' Marks the beginning of a sequence
            'SEQUENCE_END',    # '}' Marks the end of a sequence
            'PATTERN_START',   # '(' Marks the start of a pattern
            'PATTERN_END',     # ')' Marks the end of a pattern
            'VARIABLE',        # '<Starts with an small/cap alphabet>, <Followed by alpha numeric chars>, <have multiple '.'s, <Has part select>>'
            'COMPARISON',      # Either of </>/==
            'CONST'            # A binary number with size. e.g. 2'b00, 5'b10101 
        )

        # Regular expression patterns for SMU Programming language tokens
        self.t_SEQUENCE_START = r'[a-zA-Z_][a-zA-Z_0-9]*\s*{'
        self.t_SEQUENCE_END   = r'}'
        self.t_PATTERN_START  = r'\('
        self.t_PATTERN_END    = r'\)'
        self.t_VARIABLE       = r'[a-zA-Z_][a-zA-Z_0-9]*(?:\.[a-zA-Z_][a-zA-Z_0-9]*)*\[[0-9]+:[0-9]+\]'
        self.t_COMPARISON     = r'[><=]=?'
        self.t_CONST          = r'[0-9]+\'[bB][01]+'
        self.build(**kwargs)


# Lexer Class for tokenizing SRU patch code
class ASAPSruLexer(BaseLexer):
    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def __init__(self, **kwargs):
        # Token definitions for SRU Programming language
        self.tokens = (
            'CLOCK',            # 'clock' string indicates start of a clock control block defintion
            'SIGNAL',           # 'signal' string indicates the start of signal control block defintion
            'BLOCK_START',      # '{' Marks the beginning of a control block
            'BLOCK_END',        # '}' Marks the end of a control block
            'NAME',             # String indicating NAME of signal - 
            'TRIGGER',          # trigger = (<POS string>)
            'CONSTANT'          # binary bit-vector constant
        )

        # Regular expression patterns for SRU Programming language tokens
        self.t_CLOCK = r'clock'
        self.t_SIGNAL = r'signal'
        self.t_BLOCK_START= r'\{'
        self.t_NAME = r'name\s*=\s*[a-zA-Z_][a-zA-Z_0-9]*(?:\.[a-zA-Z_][a-zA-Z_0-9]*)*\[[0-9]+:[0-9]+\]'
        self.t_TRIGGER = r'trigger\s*=\s*\(([^()]+)\)'
        self.t_CONSTANT = r'constant\s*=\s*\d*[1-9]\d*\'[bB][01]+'
        self.t_BLOCK_END = r'\}'
        self.build(**kwargs)


# SRU Parser class - Performs lexical analysis on SRU code and generates AST
class ASAPSruParser:
    def __init__(self, asapSruFile) -> None:
        self.asapSruFile = asapSruFile
        self.sruLexer = ASAPSruLexer()
        self.controlNodeList = ControlNodeList([])
        with open(asapSruFile, "r") as file:
            sruCode = file.read() 
            try:
                logging.info("Running lexical analysis on ASAP-SRU patch file - '%s'"%(self.asapSruFile))
                self.sruLexer.lexer.input(sruCode)
            except Exception as e:
                logging.info(str(e))
                logging.info("Lexical analysis failed.")
                exit(1)
            logging.info("Lexical analysis successyfully completed.")
        self.parse()
        logging.info("Generated AST for SRU patch script - \n %s"%(self.controlNodeList))

    def extractVariableInfo(self, variable):
        # Define a regular expression pattern to match VAR_NAME, MSB, and LSB
        if len(variable.split('=')) != 2:
            raise Exception("Syntax Error: name assignment %s incorrect"%(variable))
        else:
            varName = variable.split('=')[1].strip()
        pattern = r'(?P<name>[a-zA-Z_][a-zA-Z_0-9]*(?:\.[a-zA-Z_][a-zA-Z_0-9]*)*)\[(?P<msb>\d+):(?P<lsb>\d+)\]'
        
        # Match the pattern in the input string
        match = re.match(pattern, varName)
        
        if match:
            # Extract matched groups
            name = match.group('name')
            msb  = int(match.group('msb'))
            lsb  = int(match.group('lsb'))
            
            return name, msb, lsb
        else:
            raise Exception("Syntax Error: Invalid variable string format - %s" %(varName))

    def extractConstInfo(self, const):
        if len(const.split('=')) != 2:
            raise Exception("Syntax Error: constant assignment '%s' is incorrect"%(const))
        else:
            constVal = const.split('=')[1].strip()
        # Define a regular expression pattern to match WIDTH and BINARY_VALUE
        pattern = r'(?P<width>\d+)\'b(?P<binary_value>[01]+)'

        # Match the pattern in the input string
        match = re.match(pattern, constVal)
        
        if match:
            # Extract matched groups
            width = int(match.group('width'))
            binaryValue = match.group('binary_value')
            
            return width, binaryValue
        else:
            raise Exception("Invalid constant string format - %s" %(constVal))
    
    def extractPosExpr(self, expr):
        if len(expr.split('=')) != 2:
            raise Exception("Syntax Error: Trigger assignment '%s' is incorrect"%(expr))
        else:
            trigExpr = expr.split('=')[1]
        match = re.search(r'\((.*?)\)', trigExpr)

        if match:
            posExpr = match.group(1)
        else:
            raise Exception("Incorrect POS expression - %s"%(expr))
        return posExpr

    def parse(self):
        logging.info("Parsing %s"%(self.asapSruFile))
        currentToken = self.sruLexer.lexer.token()
        while currentToken:
            try:
                if currentToken.type == "SIGNAL":
                    blockStart = self.sruLexer.lexer.token()
                    if blockStart.type == "BLOCK_START":
                        varToken, trigToken, constToken = None, None, None
                        argToken1 = self.sruLexer.lexer.token()
                        argToken2 = self.sruLexer.lexer.token()
                        argToken3 = self.sruLexer.lexer.token()
                        for token in [argToken1, argToken2, argToken3]:
                            if token.type == "NAME" and varToken is None:
                                varToken = token
                            elif token.type == "TRIGGER" and trigToken is None:
                                trigToken = token
                            elif token.type == "CONSTANT" and constToken is None:
                                constToken = token
                            else:
                                raise Exception("Syntax Error: Illegal arguments for SIGNAL block defintion in lineno %s"%(str(currentToken.lineno)))
                        varName, msb, lsb  = self.extractVariableInfo(varToken.value)
                        logging.info("- Creating signal control for signal - %s" %(varName))
                        newVar = Variable(name = varName,
                                          msb  = msb,
                                          lsb  = lsb)
                        width, binVal  = self.extractConstInfo(constToken.value)
                        logging.info("- Bypass constant for signal is %s"%(binVal))
                        newConst = Const(width       = width,
                                         binaryValue = binVal)
                        posExpr = self.extractPosExpr(trigToken.value)
                        newPosExpr = PosExpr(expr = posExpr)
                        newSignalNode = Signal(signal   = newVar,  \
                                               trigger  = newPosExpr, \
                                               constant = newConst)
                        self.controlNodeList.addControlNode(newSignalNode)
                        blockEnd = self.sruLexer.lexer.token()
                        if blockEnd.type != "BLOCK_END":
                            raise Exception("Syntax Error: Expected end of signal definition - received token %s"%(blockEnd.type))
                        currentToken = self.sruLexer.lexer.token()
                    else:
                        raise Exception("Syntax Error: Signal block should start with '{' received token - %s"%(blockStart.type))
                elif currentToken.type == "CLOCK":
                    blockStart = self.sruLexer.lexer.token()
                    if blockStart.type == "BLOCK_START":
                        varToken, trigToken = None, None
                        argToken1 = self.sruLexer.lexer.token()
                        argToken2 = self.sruLexer.lexer.token()
                        for token in [argToken1, argToken2]:
                            if token.type == "NAME" and varToken is None:
                                varToken = token
                            elif token.type == "TRIGGER" and trigToken is None:
                                trigToken = token
                            else:
                                raise Exception("Syntax Error: Illegal arguments for SIGNAL block defintion in lineno %s"%(str(currentToken.lineno)))
                        varName, msb, lsb  = self.extractVariableInfo(varToken.value)
                        logging.info("- Creating clock control for signal - %s" %(varName))
                        newVar = Variable(name = varName,
                                          msb  = msb,
                                          lsb  = lsb)
                        posExpr = self.extractPosExpr(trigToken.value)
                        newPosExpr = PosExpr(expr = posExpr)
                        newClockNode = Clock(signal    = newVar,  \
                                             trigger   = newPosExpr)
                        self.controlNodeList.addControlNode(newClockNode)
                        blockEnd = self.sruLexer.lexer.token()
                        if blockEnd.type != "BLOCK_END":
                            raise Exception("Syntax Error: Expected end of signal definition - received token %s"%(blockEnd.type))
                        currentToken = self.sruLexer.lexer.token()
                    else:
                        raise Exception("Syntax Error: Signal block should start with '{' received token - %s"%(blockStart.type))
                else:
                    raise Exception("Control nodes can either be SIGNAL/CLOCK - Received token %s"%(currentToken.type))
            except Exception as e:
                logging.error(str(e))
                logging.error("SRU Patch code parsing failed")
                exit(1)


# SMU Parser class - Performs lexical analysis and parses the SMU code to generate AST                    
class ASAPSmuParser:
    def __init__(self, asapSmuFile) -> None:
        self.asapSmuFile = asapSmuFile
        self.smuLexer = ASAPSmuLexer()
        with open(asapSmuFile, "r") as file:
            smuCode = file.read() 
            try:
                logging.info("Running lexical analysis on ASAP-SMU patch file - '%s'"%(self.asapSmuFile))
                self.smuLexer.lexer.input(smuCode)
            except Exception as e:
                logging.info(str(e))
                logging.error("Lexical analysis failed.")
                exit(1)
            logging.info("Lexical analysis successyfully completed.")
        self.sequenceList = SequenceList([])
        self.parse()
        logging.info("Generated AST for SMU patch script - \n %s"%(self.sequenceList))

    def extractVariableInfo(self, variable):
        # Define a regular expression pattern to match VAR_NAME, MSB, and LSB
        pattern = r'(?P<name>[a-zA-Z_][a-zA-Z_0-9]*(?:\.[a-zA-Z_][a-zA-Z_0-9]*)*)\[(?P<msb>\d+):(?P<lsb>\d+)\]'
        
        # Match the pattern in the input string
        match = re.match(pattern, variable)
        
        if match:
            # Extract matched groups
            name = match.group('name')
            msb  = int(match.group('msb'))
            lsb  = int(match.group('lsb'))
            
            return name, msb, lsb
        else:
            raise Exception("Invalid variable string format - %s" %(variable))

    def extractConstInfo(self, const):
        # Define a regular expression pattern to match WIDTH and BINARY_VALUE
        pattern = r'(?P<width>\d+)\'b(?P<binary_value>[01]+)'
        
        # Match the pattern in the input string
        match = re.match(pattern, const)
        if match:
            # Extract matched groups
            width = int(match.group('width'))
            binaryValue = match.group('binary_value')
            
            return width, binaryValue
        else:
            raise Exception("Syntax Error - Invalid constant string format - %s" %(const))

    def parse(self):
        currentToken = self.smuLexer.lexer.token()
        logging.info("Parsing %s"%(self.asapSmuFile))
        while currentToken:
            try:
                if currentToken.type == "SEQUENCE_START":
                    seqName = currentToken.value.rstrip('{').strip()
                    newSequence = Sequence(patterns = [],     \
                                           name     = seqName)
                    currentToken = self.smuLexer.lexer.token()
                    while currentToken.type != "SEQUENCE_END":
                        if currentToken.type == "PATTERN_START":
                            nextToken =  self.smuLexer.lexer.token()
                            # Checking if the pattern is non-empty
                            if nextToken.type == "VARIABLE":
                                varToken   = nextToken
                                compToken  = self.smuLexer.lexer.token()
                                constToken = self.smuLexer.lexer.token()
                                # Parsing the variable
                                if varToken.type == "VARIABLE":
                                    varName, msb, lsb  = self.extractVariableInfo(varToken.value)
                                    newVar = Variable(name = varName, \
                                                      msb  = msb,     \
                                                      lsb  = lsb)
                                else:
                                    raise Exception("Syntax Error - Expected a VARIABLE token. Received token %s" % varToken.type)
                                # Parsing the comparison operation
                                if compToken.type == "COMPARISON":
                                    compType  = compToken.value
                                    newComp = Comparison(operator = compType)
                                else:
                                    raise Exception("Syntax Error - Expected a COMPARISON token. Received token %s" % compToken.type)
                                # Parsing the Const value
                                if constToken.type == "CONST":
                                    width, binVal  = self.extractConstInfo(constToken.value)
                                    newConst = Const(width       = width, \
                                                     binaryValue = binVal)
                                else:
                                    raise Exception("Syntax Error - Expected a CONST token. Received token %s" % constToken.type)
                                patternEndToken = self.smuLexer.lexer.token()
                                # Parsing end of pattern
                                if  patternEndToken.type == "PATTERN_END":
                                    newPattern = Pattern(lhs    = newVar,   \
                                                         opType = newComp,  \
                                                         rhs    = newConst)
                                    newSequence.addPatterns(newPattern)
                                else:
                                    raise Exception("Syntax Error - Pattern should end with ')'. Received token %s" % patternEndToken.type)
                                currentToken = self.smuLexer.lexer.token()
                            # Checking if the pattern is empty
                            elif nextToken.type == "PATTERN_END":
                                newPattern = Pattern(lhs    = None,  \
                                                     opType = None,  \
                                                     rhs    = None)
                                newSequence.addPatterns(newPattern)
                                currentToken = self.smuLexer.lexer.token()
                            # Illegal pattern
                            else:
                                raise Exception("Syntax Error - Pattern is neither empty nor valid -  Received token %s" % currentToken.type)
                        else:
                            raise Exception("Syntax Error - Pattern should begin with '(' Received token %s" % currentToken.type)

                    self.sequenceList.addSequences(newSequence)
                    currentToken = self.smuLexer.lexer.token()
                else:
                    raise Exception("Syntax Error - Sequence should start with '{{' Received token %s" % currentToken.type)
            except Exception as e:
                logging.error(str(e))
                logging.error("Parsing failed")
                exit(1)
        logging.info("Parsed %s successfully - AST generated"%(self.asapSmuFile))

# Type of cfgs in SMU
class SMUCfgType(Enum):
    SMU_ENB  = 0
    INP_SEL  = 1
    CMP_VAL  = 2
    MASK     = 3
    FSM_CMP  = 4
    CMP_SEL  = 5


class ASAPSmuCompiler(LogStructuring):
    def __init__(self, asapSmuFile,      \
                       outputFolder,     \
                       maxSeqDepth,      \
                       maxTriggers,      \
                       segmentSize,      \
                       observabilityMap) -> None:
        self.asapSmuFile         = asapSmuFile
        self.outputFolder        = outputFolder
        self.sequenceList        = ASAPSmuParser(self.asapSmuFile).sequenceList
        self.maxSeqDepth         = maxSeqDepth
        self.maxTriggers         = maxTriggers
        self.segmentSize         = segmentSize
        self.observableSignalMap = observabilityMap
        self.maskWidth           = self.segmentSize
        self.cmpValWidth         = self.segmentSize
        # The following three lines of code internally determines the width of observable signal set
        self.maxObserveWidth     = 0
        self.setMaxObserveIndex(self.observableSignalMap)
        self.maxObserveWidth+=1
        self.numSegments         = math.ceil(self.maxObserveWidth/segmentSize)
        self.inpSelWidth         = math.ceil(math.log2(self.numSegments))
        self.fsmCmpWidth         = math.ceil(math.log2(self.maxSeqDepth))
        self.cmpSelMap        = {"=="   : "11",
                                 ">"    : "10",
                                 "<"    : "01",
                                 "PASS" : "00"}
        self.cfgSizeMap = {
            SMUCfgType.SMU_ENB : 1,
            SMUCfgType.INP_SEL : int(math.ceil(math.log2(self.numSegments))),
            SMUCfgType.CMP_VAL : self.segmentSize,
            SMUCfgType.MASK    : self.segmentSize,
            SMUCfgType.FSM_CMP : int(math.ceil(math.log2(self.maxSeqDepth))),
            SMUCfgType.CMP_SEL : 2  # Determined based on cmpSelMap
        }
        orderedCfgPerUnit = {triggerIndex:["0"*self.cfgSizeMap[SMUCfgType.SMU_ENB],
                                           "0"*self.cfgSizeMap[SMUCfgType.INP_SEL],
                                           "0"*self.cfgSizeMap[SMUCfgType.CMP_VAL],
                                           "0"*self.cfgSizeMap[SMUCfgType.MASK],
                                           "0"*self.cfgSizeMap[SMUCfgType.FSM_CMP],
                                           "0"*self.cfgSizeMap[SMUCfgType.CMP_SEL]] for triggerIndex in range(0, self.maxTriggers)}
        # Ordered cfg for SMU is indexed as orderedCfg[<CYCLE #>][<TRIGGER INDEX>][<CFG TYPE>]
        self.orderedCfg = {cycleIndex:copy.deepcopy(orderedCfgPerUnit) for cycleIndex in range(0, self.maxSeqDepth)}
        self.cmpSelWidth         = 2
        self.CfgSizePerSmuState  = self.cmpValWidth +  \
                                   self.maskWidth   +  \
                                   self.inpSelWidth +  \
                                   self.fsmCmpWidth +  \
                                   self.cmpSelWidth   
        self.CfgSizePerSmu       = self.CfgSizePerSmuState * self.maxSeqDepth
        self.CfgSize             = self.maxTriggers * self.CfgSizePerSmu      
        logging.info("Observable signal map - %s"%(self.logDictInfo(self.observableSignalMap))) 
        logging.info("Observable signal width = %d"%(self.maxObserveWidth))
        logging.info("SMU Segment size - %d"%(self.segmentSize))
        logging.info("Number of segments - %d"%(self.numSegments))

    def setMaxObserveIndex(self, currentNode):
        for key in currentNode:
            if isinstance(currentNode[key], list):
                observedMsb = currentNode[key][0]
                if observedMsb > self.maxObserveWidth:
                    self.maxObserveWidth = observedMsb
            elif isinstance(currentNode[key], dict):
                self.setMaxObserveIndex(currentNode[key])
        return 

    # This method returns the segment index and the bit index within the segment for
    # a given bit in observable signal set
    def getSegmentAndPosition(self, bitPosition:int):
        return (bitPosition // self.segmentSize), (bitPosition % self.segmentSize)
        
    # Method to retrieve observable signal index of a given signal
    def getObserveIndex(self, signal:str):
        signalKeys = signal.split(".")
        index = self.observableSignalMap
        for key in signalKeys:
            index = index[key]
            if index is None:
                return None
        return index

    # Method to retrieve relative signal mask and compVal constant
    def getMaskAndCompValForSegment(self, segmentBitPositionLsb, patternMsb, patternLsb, constant:Const):
        mask = 0
        numSetBits = patternMsb - patternLsb + 1
        # patternLsb is the offset from segmentBitPositionLsb, which points to the concerned part of the observed signal
        mask  =  ((1 << numSetBits) - 1) << (patternLsb + segmentBitPositionLsb)
        intConst = int(constant.binaryValue, 2)
        const =  intConst << (patternLsb  + segmentBitPositionLsb)

        return format(mask,  '0{}b'.format(self.cfgSizeMap[SMUCfgType.MASK] )), \
               format(const, '0{}b'.format(self.cfgSizeMap[SMUCfgType.CMP_VAL]))
    
    # Method to generate cfg for a pattern
    def getCfgForPattern(self, pattern:Pattern):
        signal   = pattern.lhs
        cmpOp    = pattern.opType
        constant = pattern.rhs
        # Compute mask, cmpVal, inpSel only if all three pattern components are defined
        logging.info("--- Generating cfg for %s"%(str(pattern)))
        if all(entity is not None for entity in [signal, cmpOp, constant]):
            try:
                [observedMsb, observedLsb] = self.getObserveIndex(signal.name) 
                logging.info("---- Original signal position among observed signals = %d:%d"%(observedMsb, observedLsb))
                if observedMsb < observedLsb:
                    raise Exception("MSB index is less than LSB for signal %s in pattern %s"%(signal.name, str(pattern)))
                elif signal.lsb not in range(0, observedMsb - observedLsb + 1) or signal.msb not in range(0, observedMsb - observedLsb + 1):
                    raise Exception("Observed signal index %d:%d of signal %s not within actual observed range of %d:%d" %(signal.msb,  \
                                                                                                                           signal.lsb,  \
                                                                                                                           signal.name, \
                                                                                                                           observedMsb - observedLsb, \
                                                                                                                           0))
            except KeyError:
                logging.error("Invalid observable signal found in pattern - %s"%(str(signal.name)))
                exit(1)
            except Exception as e:
                logging.error(str(e))
                exit(1)
            # NOTE - Here, we assume a signal will always entirely fall within the same segment
            segmentIndex, segmentBitPosition = self.getSegmentAndPosition(observedLsb)
            segmentBitPositionMsb = segmentBitPosition + (observedMsb - observedLsb)
            logging.info("---- Segment position of signal = %d:%d"%(segmentBitPositionMsb, segmentBitPosition))
            assert observedMsb >= observedLsb, "Incorrect signal indexing for signal  %s in pattern %s"%(signal.name, str(pattern))
            assert segmentBitPositionMsb < self.segmentSize, "Boundary error for %s in pattern %s. A signal should always fall within a single segment"%(signal.name, \
                                                                                                                                                         str(pattern))
            try:
                mask, compVal = self.getMaskAndCompValForSegment(segmentBitPosition,   \
                                                                 signal.msb,           \
                                                                 signal.lsb,           \
                                                                 constant)
                # This conditional checks if compVal is set for any bit outside masked zone.
                # If so, it is a compile bug.
                if (~int(mask, 2) & int(compVal, 2)):
                    raise Exception("Compile Error: Non-zero Compval generated outside masked area for %s"%(pattern))
            except Exception as e:
                logging.error(str(e))
                exit(1)
            
            inpSel = format(segmentIndex, '0{}b'.format(self.cfgSizeMap[SMUCfgType.INP_SEL]))
        else:
            logging.info("")
            mask    = format(0, '0{}b'.format(self.cfgSizeMap[SMUCfgType.MASK]))
            compVal = format(0, '0{}b'.format(self.cfgSizeMap[SMUCfgType.CMP_VAL]))
            inpSel  = format(0, '0{}b'.format(self.cfgSizeMap[SMUCfgType.INP_SEL]))
        try:
           if cmpOp is not None: 
                cmpSel = self.cmpSelMap[cmpOp.operator]
           else: # Pass cycle for empty pattern
                cmpSel = self.cmpSelMap["PASS"]
        except KeyError as e:
            logging.error("Invalid comparison operation in pattern - %s"%str(pattern))
            exit(1)
        logging.info("---- Cfg for %s :\n  InpSel (Segment #) - %s\n  Mask - %s\n  cmpVal - %s\n  cmpSel ('00':PASS, 01:'<', 10:'>', 11: '==')  - %s"%(pattern, \
                                                                                                                                                       inpSel,  \
                                                                                                                                                       mask,    \
                                                                                                                                                       compVal, \
                                                                                                                                                       cmpSel))

        return inpSel, mask, compVal, cmpSel 
    
    # Method to generate cfg for a sequence and set them in ordered cfg map
    def setCfgForSequence(self, sequence:Sequence, triggerIndex:int):
        try:
            if len(sequence.patterns) > self.maxSeqDepth:
                raise Exception("Sequence - %s has %d patterns that is more than the maximum # of patterns - %d"%(sequence.name,          \
                                                                                                                  len(sequence.patterns), \
                                                                                                                  self.maxSeqDepth))
        except Exception as e:
            logging.info(str(e))
            exit(1)
        for cycleIndex, pattern in enumerate(sequence.patterns):
            inpSel, mask, compVal, cmpSel = self.getCfgForPattern(pattern)
            smuEnb = format(1, '0{}b'.format(1))
            fsmCmp = format(len(sequence.patterns) - 1, '0{}b'.format(math.ceil(math.log2(self.maxSeqDepth))))
            self.orderedCfg[cycleIndex][triggerIndex][SMUCfgType.SMU_ENB.value] = smuEnb
            self.orderedCfg[cycleIndex][triggerIndex][SMUCfgType.INP_SEL.value] = inpSel
            self.orderedCfg[cycleIndex][triggerIndex][SMUCfgType.MASK.value]    = mask
            self.orderedCfg[cycleIndex][triggerIndex][SMUCfgType.CMP_VAL.value] = compVal
            self.orderedCfg[cycleIndex][triggerIndex][SMUCfgType.CMP_SEL.value] = cmpSel
            self.orderedCfg[cycleIndex][triggerIndex][SMUCfgType.FSM_CMP.value] = fsmCmp
        logging.info("-- Cfg generation for sequence %s complete."%(sequence.name))
    
    # Method to get cfg for SMU
    # Order of cfgs per sequence - <RegFsmCmp, RegInpSel, RegMask, RegCompVal, RegCmpSel>
    def setCfg(self, sequenceList:SequenceList):
        nameToTriggerIndex = {}
        # Each sequence gets mapped to a SMU and is assigned a trigger index
        for triggerIndex, sequence in enumerate(sequenceList.sequences):
            logging.info("-- Generating cfg for sequence %s"%(sequence.name))
            nameToTriggerIndex[sequence.name] = triggerIndex
            self.setCfgForSequence(sequence, triggerIndex) 
        return nameToTriggerIndex
    
    # This is the sole method that determines the actual ordering of elements of SMU ordered cfg
    # in the programmable cfg stream. 
    def getCfgStreamFromOrderedCfg(self):
        cfgStream = ""
        for cycle in range(0, self.maxSeqDepth):
            for trigger in range(0, self.maxTriggers):
                # Using reversed as indeing in SMUCfgType is opposite to that of actual register cfg
                for cfgType in reversed(SMUCfgType):
                    cfgStream = self.orderedCfg[cycle][trigger][cfgType.value] + cfgStream
        return cfgStream

    # Method writes the SMU bitsream and returns mapping information of sequences
    def generateProgram(self):
        logging.info("Compiling file %s"%(self.asapSmuFile))
        nameToTriggerIndex = self.setCfg(self.sequenceList)
        logging.info("Compilation complete.")
        for seqName in nameToTriggerIndex:
            logging.info("Sequence %s mapped to SMU unit with trigger index - %d" %(seqName,                     \
                                                                                    nameToTriggerIndex[seqName]))
        logging.info("SMU Ordered cfg is - %s"%(self.logSMUOrderedMap(self.orderedCfg, self.maxTriggers, self.maxSeqDepth)))
        logging.info("SMU trigger index map - %s"%(self.logDictInfo(nameToTriggerIndex)))
        cfgStream = self.getCfgStreamFromOrderedCfg()
        logging.info("Size of SMU cfg - %d"%(len(cfgStream)))
        logging.info("SMU Cfg stream - \n  %s"%(cfgStream))
        with open(self.outputFolder + "/smu.stream", "w") as outFile:
            for bit in cfgStream:
                outFile.write(" %s"%(bit))
        return nameToTriggerIndex
    
# Enum class for SRU control types
class ControlType(Enum):
    SIGNAL = 0
    CLOCK = 1

# Enum class for SRU cfg type
class SRUCfgType(Enum):
    PLA_SEL     = 0
    CNTL_ENB    = 1
    CONSTANT    = 2
    TRIG_SEL    = 3
    MINTERM_SEL = 4

    
# SRU compiler compiles the AST to generate the cfg.
# Cfg for SRU is complex as it have definite signal bit to SRU unit mapping
# unlike SMU where a signal can be easily associated with any SMU unit,
# Hence we create this class for clubbing control configs with the
# appropriate signals being controlled. We create a data collection
# object that collects cfgs for each signal bit being controlled.
# The class is also provided with control signal to control index info
# so that post configuration of the convenient dictionary, the class 
# auto-generates the ordered cfg.
class ASAPSruCompiler(LogStructuring):
    def __init__(self, sruPatchFile,         \
                       outputFolder,         \
                       sruSegmentSize,       \
                       maxTriggers,          \
                       numClkControls,       \
                       numSignalControls,    \
                       nameToTriggerIndex,   \
                       numPLA,               \
                       controlledSignalMap,  \
                       controlledClkMap):
        # Trigger name to trigger index mapping
        self.nameToTriggerIndex    = nameToTriggerIndex  
        # Size of SRU segments     
        self.sruSegmentSize        = sruSegmentSize
        # Maximum # of SMU triggers
        self.maxTriggers           = maxTriggers
        # # of Clk signals being controlled
        self.numClkControls        = numClkControls
        # # of PLAs in the SRU
        self.numPLA                = numPLA
        # # of signals being controlled
        self.numSignalControls     = numSignalControls
        # dict of signals being controlled and their index in control signal q
        self.controlledSignalMap   = controlledSignalMap
        # dict of clock signals beign controlled and their index in control signal q
        self.controlledClkMap      = controlledClkMap
        # total control width
        self.controlWidth          = self.numClkControls + self.numSignalControls
        # Patch file
        self.sruPatchFile          = sruPatchFile
        # Output folder
        self.outputFolder          = outputFolder
        # Parse the SRU Patch file to generate AST
        self.sruParser             = ASAPSruParser(self.sruPatchFile)

        # Initialize the ordered signal cfg - CFG bits concerning each signal under control and PLAs
        # The order of definition here should be with respect tot the order in CfgType, ControlType Enums
        self.orderedCfg = [[{}, {}], # PLA_SEL  signal/clock
                           [{}, {}], # CNTL_ENB for signal/clock
                           [{}, {}], # CONSTANT for signal/clock (CONSTANT for clock is don't care. done for code symmetry)
                           {},       # TRIG_SEL 
                           {}        # MINTERM_SEL
                          ]
        # Initialize the ordered PLA cfg - CFG bits converning each PLAs

        # ControlSignalMap for Signal/Clock controls
        self.controlMap = {
            ControlType.SIGNAL : self.controlledSignalMap, \
            ControlType.CLOCK  : self.controlledClkMap
        }

        # Cfg Sizes initialization 
        self.cfgSizeMap = {
            # PLA_SEL, CNTL_ENB, CONSTANT are required for every signal bit being controlled
            # All these sizes are per controlled signal bit
            SRUCfgType.PLA_SEL     : int(math.ceil(math.log2(numPLA))),
            SRUCfgType.CNTL_ENB    : 1,
            SRUCfgType.CONSTANT    : 1,
            # TRIG_SEL, MINTERM_SEL concerns PLA cfg and are are not availbale per signal bit being controlled
            # All these sizes are per PLA unit
            SRUCfgType.TRIG_SEL    : int(math.ceil(math.log2(self.maxTriggers))*self.sruSegmentSize),
            SRUCfgType.MINTERM_SEL : int(math.pow(2, self.sruSegmentSize))
        }
        logging.info("Cfg Size Map - %s"%(self.logDictInfo(self.cfgSizeMap)))

        # Initialize the ordered controlled signal / PLA cfgs with signal map
        for  cfgType in SRUCfgType:
            if cfgType in [SRUCfgType.PLA_SEL, SRUCfgType.CNTL_ENB, SRUCfgType.CONSTANT]:
                for controlType in ControlType:
                    # Initialize the Cfg map with signal to control bit map
                    self.orderedCfg[cfgType.value][controlType.value] = copy.deepcopy(self.controlMap[controlType])
                    # Initialize the control bit past of cfg map with initialize cfg
                    self.initalizeCfg(self.orderedCfg[cfgType.value][controlType.value], \
                                      self.cfgSizeMap[cfgType])
            else:
                # TRIG_SEL/MINTERM_SEL is per PLU. Initialize orderedCfg for these for each PLUs
                self.orderedCfg[cfgType.value] = {index:("0"*self.cfgSizeMap[cfgType]) for index in range(0, self.numPLA)}


    # Method to initialize trigger sel cfg for the signal/clock control
    def initalizeCfg(self, currentNode, cfgSize):
        for key in currentNode:
            if isinstance(currentNode[key], dict):
                self.initalizeCfg(currentNode[key], cfgSize)
            # This comparison is to make sure we do not traverse the same node already traversed
            elif isinstance(currentNode[key], list):
                signalMsb = currentNode[key][0]
                signalLsb = currentNode[key][1]
                cfg       = format(0, '0{}b'.format(cfgSize*(signalMsb - signalLsb + 1)))
                currentNode[key] = cfg

    # This method is used to get distinct POS expressions used as triggers
    # Two POS expressions are equivalent if two distinct POS expressions
    # has the exact same # and type of expression tokens/minterms this is
    # achieved in code using sets
    # Each distinct POS expression is mapped to distinct PLA units
    def getDistinctPOSExpr(self, controlList: ControlNodeList):
        distinctPOSExpr = set()
        for node in controlList.controlNodes:
            exprTokenSet = frozenset(node.trigger.exprTokens)
            distinctPOSExpr.add(exprTokenSet)
        return distinctPOSExpr
    
    
    # Helper method used to find all variables in a POS expression
    def getVarsInExprSet(self, exprSet):
        varList = set()
        for token in exprSet:
            # Use regular expression to find variables and complements
            matches = re.findall(r'([a-zA-Z0-9]+)(?:\')?', token)
            for match in matches:
                varList.add(match)
        return list(varList)
    
    # Method used to get trigger select cfg for a PLA unit
    # Each POS expression gets mapped to a PLA unit
    def getTrigSelectCfgForExpr(self, exprSet:set):
        try:
            vars = self.getVarsInExprSet(exprSet)
            if len(vars) > self.sruSegmentSize:
                raise Exception("More variables in POS expression %s than the SRU segment size %s"%(exprSet, self.sruSegmentSize))
        except Exception as e:
            logging.error(str(e))
            exit(1)
        trigSelCfg = ""
        varToPlaIndexMap = {}
        try:
            for index, var in enumerate(vars):
                if var in self.nameToTriggerIndex:
                    triggerIndex = self.nameToTriggerIndex[var]
                    # Latest configuration should be appended towards the MSB side
                    trigSelCfg = format(triggerIndex, '0{}b'.format(int(self.cfgSizeMap[SRUCfgType.TRIG_SEL]/self.sruSegmentSize))) + trigSelCfg
                    varToPlaIndexMap[var] = index
                else:
                    raise Exception("Trigger %s in POS expression %s not programmed in SMU patch"%(var, exprSet))
            trigSelCfg = format(int(trigSelCfg, 2), '0{}b'.format(self.cfgSizeMap[SRUCfgType.TRIG_SEL]))
        except Exception as e:
            logging.error(str(e))
            exit(1)
        return trigSelCfg, varToPlaIndexMap

    # Method used to get complimented and non-complimented terms in an expression token
    def getComplimentAndNonComplimentVars(self, exprToken):
        vars = [var.strip() for var in str(exprToken).split('.')]
        return [var.rstrip("'") for var in vars if var.endswith("'")], [var for var in vars if not var.endswith("'")]
            
    # Method used to select relevant minterms representing the POS expr to be programmed
    # to a PLA unit. It needs a mapping of trigger to PLA index and an token set of the
    # POS expression
    def getMintermCfgForExpr(self, exprSet: set, varToPlaIndexMap: dict):
        numMinterms = 2 ** self.sruSegmentSize
        mintermCfg = [False] * numMinterms  # Initialize mintermCfg as a list of False
        for i in range(numMinterms):
            binary = bin(i)[2:].zfill(self.sruSegmentSize)  # Convert i to binary string
            for exprToken in exprSet:
                cmpVars, nonCmpVars = self.getComplimentAndNonComplimentVars(exprToken)
                if all(binary[::-1][varToPlaIndexMap[var]] == '1' for var in nonCmpVars) and \
                   all(binary[::-1][varToPlaIndexMap[var]] == '0' for var in cmpVars):
                    mintermCfg[i] = True
        # Reversing the cfg list as Cfg follows bit ordering which goes MSB --> LSB
        mintermCfg.reverse()
        CfgStr = ''.join('1' if bit else '0' for bit in mintermCfg)
        return CfgStr

    # This method is used to derive PLA config for all POS expressions
    # It returns 3 maps - 1. Expression to mapped PLA index,
    # 2. Expression to PLA config
    def getPLAConfig(self, distinctPOSExpr):
        exprToPlaMap, exprToTrigSelCfg, exprToMintermCfg,  = {}, {}, {}
        for plaIndex, exprSet in enumerate(distinctPOSExpr):
            exprToPlaMap[exprSet] = plaIndex
            exprToTrigSelCfg[exprSet], \
            varToPlaIndexMap          = self.getTrigSelectCfgForExpr(exprSet)
            exprToMintermCfg[exprSet] = self.getMintermCfgForExpr(exprSet, varToPlaIndexMap)
            logging.info("Mapping POS expression - %s to PLA - %d"%(str(exprSet), plaIndex))
            logging.info("--Trigger signal mapping - %s"%(self.logDictInfo(varToPlaIndexMap)))
            logging.info("--Minterm select cfg - %s"%(exprToMintermCfg[exprSet]))
        return exprToPlaMap, exprToTrigSelCfg, exprToMintermCfg
            
    # Method to derive cfgs (PLA_SEL, CNTL_ENB) for a clock control
    def getCfgForClkControl(self, clkControl: Clock, exprToPlaMap: dict):
        try:
            logging.info("Configuring clock control for control node - %s"%(clkControl))
            plaIndexForTrigger = exprToPlaMap[clkControl.trigger.getExprSet()]
            plaSelCfg = format(plaIndexForTrigger, '0{}b'.format(self.cfgSizeMap[SRUCfgType.PLA_SEL]))
            cntlEnbCfg = "1"
            logging.info("Cfg For %s\n  CNTL_ENB (Control Enable) - %s\n  PLA_SEL - %s" %(str(clkControl),cntlEnbCfg, plaSelCfg))
            if clkControl.signal.msb != clkControl.signal.lsb:
                raise Exception("Multi-bit CLK signals are not supported - found violation for clock signal %s" %(clkControl.signal.name))
        except Exception as e:
            logging.error(str(e))
            exit(1)
        return plaSelCfg, cntlEnbCfg

    # Method to derive cfgs (PLA_SEL, CNTL_ENB, CONSTANT) for signal control 
    def getCfgForSignalControl(self, sigControl: Signal, exprToPlaMap: dict):
        logging.info("Configuring signal control for control node - %s"%(sigControl))
        try:
            plaIndexForTrigger = exprToPlaMap[sigControl.trigger.getExprSet()]
        except KeyError:
            logging.error("POS expression %s not found to be mapped to any PLAs"%(str(sigControl.trigger.getExprSet())))
            exit(1)
        plaSelCfg = format(plaIndexForTrigger, '0{}b'.format(self.cfgSizeMap[SRUCfgType.PLA_SEL]))*(sigControl.signal.msb - sigControl.signal.lsb + 1)
        cntlEnbCfg = "1"*(sigControl.signal.msb - sigControl.signal.lsb + 1)
        constCfg = format(int(sigControl.constant.binaryValue, 2), '0{}b'.format(sigControl.constant.width))
        logging.info("Cfg for %s\n  CNTL_ENB (Control Enable) - %s\n  PLA_SEL - %s\n  CONSTANT - %s" %(str(sigControl),cntlEnbCfg, plaSelCfg, constCfg))
        return plaSelCfg, cntlEnbCfg, constCfg

    # Since orderedMap is in the form of a tree, you have to traverse the tree to set 
    # cfg for the right signal node
    # This method traverses the Cfg tree and sets the cfg for the provided hierarchical signal
    def setCfgForOrderedMap(self, signalName:str, cfgMap, cfg):
        signalKeys = signalName.split(".")
        index = cfgMap
        for key in signalKeys:
            try:
                # If index[key] is str, it is definititely a cfg
                if isinstance(index[key], str):
                    index[key] = cfg
                # else keep going inside until the leaf node
                else:
                    index = index[key]
            except KeyError as e:
                logging.error("Illegal signal name - %s"%(signalName))
                exit(1)
            if index is None:
                raise Exception("Empty/Un-initilized cfg map")

    # Manager method that derives each type of configuration and set them to the ordered
    # cfg object. 
    def setSruCfg(self, controlNodeList:ControlNodeList):
    # --- Task 1: Configure the PLAs - This is common for both Clock and Signal control
        try: 
            # Get all the distinct POS expressions in the SRU patch program 
            distinctPOSExpr = self.getDistinctPOSExpr(controlNodeList)
            if len(distinctPOSExpr) > self.numPLA:
                raise Exception("There are more distinct POS expressions than the available # of PLAs")
            else:
                exprToPlaMap, exprToTrigSelCfg, exprToMintermCfg = self.getPLAConfig(distinctPOSExpr)
                for expr in exprToPlaMap:
                    # Setting ordered cfg for PLA (TRIG_SEL and MINTERM_SEL)
                    self.orderedCfg[SRUCfgType.TRIG_SEL.value][exprToPlaMap[expr]]    = exprToTrigSelCfg[expr]
                    self.orderedCfg[SRUCfgType.MINTERM_SEL.value][exprToPlaMap[expr]] = exprToMintermCfg[expr]
        except Exception as e:
            logging.error(str(e))
            exit(1)
    # -- Task 2: Configure the control filters (clock/signal). Control filters require PLA_SEL (for triggers)
    #            CNTL_ENB for enabling the control filter, CONSTANT (for bypass - signal control only)  
        try:
            for controlNode in controlNodeList.controlNodes:
                # Generating Cfg for signal control nodes
                if isinstance(controlNode, Signal):
                    plaSelCfg, cntlEnbCfg, constCfg = self.getCfgForSignalControl(controlNode, exprToPlaMap)
                    # Setting PLA_SEL for a signal control unit
                    self.setCfgForOrderedMap(controlNode.signal.name,                                   \
                                             self.orderedCfg[SRUCfgType.PLA_SEL.value][ControlType.SIGNAL.value],   \
                                             plaSelCfg)
                    # Setting CNTL_ENB for a signal control unit
                    self.setCfgForOrderedMap(controlNode.signal.name,                                   \
                                             self.orderedCfg[SRUCfgType.CNTL_ENB.value][ControlType.SIGNAL.value],  \
                                             cntlEnbCfg)
                    # Setting CONSTANT for a signal control unit 
                    self.setCfgForOrderedMap(controlNode.signal.name,                                   \
                                             self.orderedCfg[SRUCfgType.CONSTANT.value][ControlType.SIGNAL.value],  \
                                             constCfg)
                # Generating Cfg for clock control nodes
                elif isinstance(controlNode, Clock):
                    plaSelCfg, cntlEnbCfg = self.getCfgForClkControl(controlNode, exprToPlaMap)
                    # Setting PLA_SEL for a clock control unit
                    self.setCfgForOrderedMap(controlNode.signal.name,
                                             self.orderedCfg[SRUCfgType.PLA_SEL.value][ControlType.CLOCK.value],    \
                                             plaSelCfg)
                    # Setting CONSTANT for a clock control unit 
                    self.setCfgForOrderedMap(controlNode.signal.name,
                                             self.orderedCfg[SRUCfgType.CNTL_ENB.value][ControlType.CLOCK.value],   \
                                             cntlEnbCfg)
                else:
                    raise Exception("Illegal controlNode type - %s"%(type(controlNode)))     
        except Exception as e:
            logging.error(str(e))
            exit(1)   
        logging.info("Ordered config map - %s"%(self.logSRUOrderedMap(self.orderedCfg)))
    
    # Method to find signal with the given LSB
    def getSignalForConnectionIndexLsb(self, signalMap, index, signalKeys, sizeRange, nameList=None):
        if nameList is None:
            nameList = []

        for key in signalMap:
            if isinstance(signalMap[key], dict):
                nameList.append(key)
                signalKeys, sizeRange = self.getSignalForConnectionIndexLsb(signalMap[key], index, signalKeys, sizeRange, nameList)
                nameList.pop()  # Remove the last element after recursion
            else:
                if signalMap[key][1] == index:
                    nameList.append(key)
                    signalKeys, sizeRange = nameList[:], signalMap[key]
                    nameList.pop()  # Remove the last element after finding the signal
        return signalKeys, sizeRange
    
    # This method retrieves the minimum and maximum LSB indices of signals in a given signal tree
    def getMinimalAndMaximalIndexLsbInMap(self, signalMap, minIndex, maxIndex):
        for key in signalMap:
            if isinstance(signalMap[key], dict):
                minIndex, maxIndex = self.getMinimalAndMaximalIndexLsbInMap(signalMap[key], minIndex, maxIndex)
            else:
                # Find if LSB < minimal index
                if minIndex > signalMap[key][1]:
                    minIndex = signalMap[key][1]
                # Find if LSB > maximal index
                if maxIndex < signalMap[key][1]:
                    maxIndex = signalMap[key][1]
        return minIndex, maxIndex

    # Given a cfg, it returns the serialized cfg in connection order
    def getCfgInConnectionOrder(self, cfgMap, controlMap):
        startIndex, maxIndex = self.getMinimalAndMaximalIndexLsbInMap(controlMap, sys.maxsize, 0)
        cfg = ""
        while startIndex <= maxIndex:
            signalKeys, sizeRange = self.getSignalForConnectionIndexLsb(controlMap, startIndex, None, None)
            if signalKeys is None or sizeRange is None:
                # Reached if getSignalForConnectionIndexLsb doesn't successfully get a signal with LSB = startIndex
                raise Exception("Invalid signal start index - %d"%(startIndex))
            index = copy.deepcopy(cfgMap)
            for key in signalKeys:
                index = index[key]
                if index is None:
                    raise Exception("Invalid configuration found while generating cfg stream")
            cfg = index + cfg
            [signalMsb, signalLsb] = sizeRange
            startIndex += (signalMsb - signalLsb + 1)
        return cfg
    
    # Get the SMU cfg stream - This method accumulates the cfg in the order required by SRU
    def getCfgStreamFromOrderedCfg(self):
        cfgStream = ""
        # Constant
        cfgStream = self.getCfgInConnectionOrder(self.orderedCfg[SRUCfgType.CONSTANT.value][ControlType.SIGNAL.value], \
                                                 self.controlMap[ControlType.SIGNAL]) + cfgStream
        # Control Enable Select ([signal, clock])
        for controlType in reversed(ControlType):
            cfgStream = self.getCfgInConnectionOrder(self.orderedCfg[SRUCfgType.CNTL_ENB.value][controlType.value], \
                                                     self.controlMap[controlType]) + cfgStream
        # PLA sel ([signal, clock])
        for controlType in reversed(ControlType):
            cfgStream = self.getCfgInConnectionOrder(self.orderedCfg[SRUCfgType.PLA_SEL.value][controlType.value], \
                                                     self.controlMap[controlType]) + cfgStream
        # Minterm select
        for plaIndex in self.orderedCfg[SRUCfgType.MINTERM_SEL.value]:
            cfgStream = self.orderedCfg[SRUCfgType.MINTERM_SEL.value][plaIndex] + cfgStream
        # Trigger select
        for plaIndex in self.orderedCfg[SRUCfgType.TRIG_SEL.value]:
            cfgStream = self.orderedCfg[SRUCfgType.TRIG_SEL.value][plaIndex] + cfgStream
        return cfgStream

    # Method writes the SMU bitsream and returns mapping information of sequences
    def generateProgram(self):
        logging.info("Compiling file %s"%(self.sruPatchFile))
        controlNodeList = self.sruParser.controlNodeList
        self.setSruCfg(controlNodeList)
        logging.info("Compilation complete.")
        cfgStream = self.getCfgStreamFromOrderedCfg()
        logging.info("Size of SRU cfg - %d"%(len(cfgStream)))
        logging.info("SRU Cfg stream - \n  %s"%(cfgStream))
        with open(self.outputFolder + "/sru.stream", "w") as outFile:
            for bit in cfgStream:
                outFile.write(" %s"%(bit))
   

class ControlSignalMappingModel:
    def __init__(self, controllabilityMap, controlTypeMap) -> None:
        self.controllabilityMap = controllabilityMap
        self.controlTypeMap     = controlTypeMap
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
                  
                                    

class ASAPCompiler:
    def __init__(self, asapSpecFile, asapInterfaceFile, outputFolder, smuProgramFile, sruProgramFile):
        paramMap = {}
        # asap_param.txt has all the relevant configurable params for ASAP architecture
        with open(asapSpecFile, "r") as paramFile:
            for line in paramFile:
                assert len(line.split('=')) == 2, "Incorrect param specififed in %s"%(asapSpecFile)
                paramMap.update({line.split('=')[0].strip(): line.split('=')[1].strip()})

        # asap_interface.txt generated by ASAP Insertion tool has the relevant observe/control signal mapping information
        with open(asapInterfaceFile, "r") as ioFile:
            ioMap = json.load(ioFile)

        # SRU PARAMS
        SRU_SEGMENT_SIZE    = int(paramMap['SRU_SEGMENT_SIZE'])
        SRU_NUM_PLA         = int(paramMap['SRU_NUM_PLA'])

        # SMU Params
        SMU_SEGMENT_SIZE    = int(paramMap['SMU_SEGMENT_SIZE'])
        MAX_SEQ_DEPTH       = int(paramMap['MAX_SEQ_DEPTH'])
        MAX_TRIGGERS        = int(paramMap['MAX_TRIGGERS'])

        # IO Interface Maps for SMU/SRU
        OBSERVABILITY_MAP   = ioMap['OBSERVABILITY_MAP']
        CONTROLLABILITY_MAP = ioMap['CONTROLLABILITY_MAP']
        CONTROL_TYPE_MAP    = ioMap['CONTROL_TYPE_MAP']



        # Defining SMU compiler object
        smuCompiler = ASAPSmuCompiler(smuProgramFile,
                                      outputFolder,
                                      MAX_SEQ_DEPTH,
                                      MAX_TRIGGERS,
                                      SMU_SEGMENT_SIZE,
                                      OBSERVABILITY_MAP)
        nameToTriggerIndex = smuCompiler.generateProgram()

        # Emulating control map re-ordering for SRU arch requirement
        reorderMap = ControlSignalMappingModel(CONTROLLABILITY_MAP,
                                            CONTROL_TYPE_MAP)
        
        # Defining SRU compiler object
        sruCompiler = ASAPSruCompiler(sruProgramFile,
                                      outputFolder,
                                      SRU_SEGMENT_SIZE,
                                      MAX_TRIGGERS,
                                      reorderMap.numClkControls,
                                      reorderMap.numSignalControls,
                                      nameToTriggerIndex,
                                      SRU_NUM_PLA,
                                      reorderMap.controlledSignalMap,
                                      reorderMap.controlledClkMap)
        sruCompiler.generateProgram()




