#!/bin/bash

# Print the contents
#echo "Filelist string - $file_contents"

# run iverilog simulation 
## Uncomment the below sim command to run with ASAP patch
iverilog -s top_tb -o sim software_adaptor.v access_controller.v target_agent.v top.v bitstream_deserializer.v sru_pla_unit.v sru_security_clock_gate.v sru_signal_filter_unit.v cfg_decrypt.v sru.v smu_unit.v smu.v asapTop.v top_tb.v
# Generate waveform
vvp sim