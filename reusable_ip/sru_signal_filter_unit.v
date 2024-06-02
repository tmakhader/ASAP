// The Signal Filter Unit is a simple MUX that selects between input signal and a constant
module sru_signal_filter_unit (
    input  wire           Qin,          // Controllable input signal
    input  wire           BypassEn,     // PLA output
    input  wire           RegConst,     // Constant value
    input  wire           FruEn,        // Enable signal for the filter 
    output wire           Qout          // Filtered output
);
       
    // Filtering output based on BypassEn
    assign Qout = ( (BypassEn & FruEn) & RegConst ) | 
                  (~(BypassEn & FruEn) & Qin );

endmodule