module bitstream_deserializer #(
    parameter CFG_SIZE = 100            // Number of bits to store
)(
    input  wire SerialIn,                    // Single-bit input to stream data
    input  wire StreamValid,                 // Valid bit indicating input stream is valid
    input  wire clk,                         // Clock input
    input  wire rst,                         // Reset input
    output wire CfgDone,                     // Signal to indicate that bit-stream has been completely loaded.
                                             // For correct programming, CongigDoneOut should always match is 
    output reg [CFG_SIZE-1:0] ParallelOut    // Output register to store N bits
);

    reg  [$clog2(CFG_SIZE)-1:0] StreamBitCount;      // Register used to count valid bits in bitstream during cfg
    wire [$clog2(CFG_SIZE)-1:0] StreamBitCountNext;  
    reg  [CFG_SIZE-1:0]         ParallelOutNext;

    // Deserialization logic
    always @(*) begin
        if ( rst ) begin
            ParallelOutNext = 0;
        end else if ( StreamValid ) begin
            ParallelOutNext = { ParallelOut[CFG_SIZE-2:0], SerialIn };
        end else begin
            ParallelOutNext = ParallelOut;
        end
    end 

    // Logic to count valid input bits during bitstream deserialization
    assign StreamBitCountNext = rst         ? 1'b0:
                                StreamValid ? StreamBitCount + 1'b1 : StreamBitCount;

    // Memory logic for BitStreamCount and ParallelBitstream output
    always @(posedge clk) begin
        StreamBitCount <= StreamBitCountNext;
        ParallelOut    <= ParallelOutNext;
    end

    // CfgDone indicates that bitstream loading is complete
    assign CfgDone = (StreamBitCount == CFG_SIZE);

endmodule
