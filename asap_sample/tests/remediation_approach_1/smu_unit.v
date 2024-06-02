module smu_unit # (
    parameter  N                  =    2,   // Maximum # of cycles for observability
    parameter  K                  =    4,   // Maximum # of observable signal bits
    parameter  SMU_SEGMENT_SIZE   =    64,
    parameter  SMU_NUM_SEGMENTS   =   (K + SMU_SEGMENT_SIZE - 1)/SMU_SEGMENT_SIZE,  // # of segments
    parameter  BITS_NUM_SEGMENTS  =   (SMU_NUM_SEGMENTS == 1) ? 1 : $clog2(SMU_NUM_SEGMENTS)
) (
    // Clock, Reset signals
    input  wire                          clk,
    input  wire                          rst,

    // Observable input set and registers
    input  wire [K-1:0]                  i,                 // Observable signal input
    input  wire                          RegSmuEn,
    input  wire [BITS_NUM_SEGMENTS-1:0]  RegInpSel,         // Register to select relevant segment
    input  wire [SMU_SEGMENT_SIZE-1:0]   RegMask,           // Comparator Mask Register
    input  wire [SMU_SEGMENT_SIZE-1:0]   RegCmp,            // Register used for comparison
    input  wire [1:0]                    RegCmpSelect,      // Register used to select type of comparison
    input  wire [$clog2(N)-1:0]          RegFsmCmp,         // Register used for FSM state comparison 
    input  wire                          SmuEn,             // Signal used to enable SMU -
                                                            // SMU should only be enabled when cfg bitstream is 
                                                            // fully loaded.

    // Trigger signal
    output reg [$clog2(N)-1:0]          SmuState,           // # of patterns matched
    output wire                         trigger             // Output trigger signal
);

    wire [SMU_SEGMENT_SIZE-1:0]            MaskedCmpInp;
    wire                                   CmpEq;   
    wire                                   CmpGt;
    wire                                   CmpLt;
    reg                                    CmpSel;
    
    // StateMatch is the only memory element in smu_unit
    wire  [$clog2(N)-1:0]        SmuStateNext; 
    wire                         StateMatch;
    wire                         OverallSmuEn;
    wire                         gated_clk;
    wire [SMU_SEGMENT_SIZE-1:0]  p;
    wire [SMU_SEGMENT_SIZE-1:0]  SegmentedI[SMU_NUM_SEGMENTS-1:0];
     

    // Logic to select relevant segment of observable input set.
    genvar g_seg;
    generate
        for (g_seg = 0; g_seg < SMU_NUM_SEGMENTS; g_seg = g_seg + 1) begin  : genblk_seg 
            if ((g_seg + 1) * SMU_SEGMENT_SIZE > K) begin
                // Handle the case where the segment exceeds the length of 'i'
                assign SegmentedI[g_seg] = i[(K-1):g_seg*SMU_SEGMENT_SIZE];
            end else begin
                assign SegmentedI[g_seg] = i[(g_seg+1)*SMU_SEGMENT_SIZE-1 -: SMU_SEGMENT_SIZE];
            end
        end
    endgenerate

    assign OverallSmuEn = SmuEn & RegSmuEn;

    assign p          = SegmentedI[RegInpSel];

    // Logic to mask the input for comparison
    assign MaskedCmpInp      = (p & RegMask);

    // Comparator logic
    assign CmpEq = MaskedCmpInp == RegCmp;   // Compare if i == Reg
    assign CmpGt = MaskedCmpInp >  RegCmp;   // Compare if i > Reg
    assign CmpLt = MaskedCmpInp <  RegCmp;   // Compare if i < Reg

    // Cmp Select
    always @* begin 
        if (rst) begin
            CmpSel <= 1'b0;
        end else begin
            case (RegCmpSelect)
                2'b00  : CmpSel <= 1'b1;        // 00 is used for always active trigger. This is used
                                                // when we want to ascend to next cycle unconditionally    
                2'b11  : CmpSel <= CmpEq;       // 11 selects == op
                2'b01  : CmpSel <= CmpLt;       // 01 selects < op
                2'b10  : CmpSel <= CmpGt;       // 10 selects > op
            endcase
        end
    end

    // Check for pattern  match
    assign StateMatch = ~|(SmuState ^ RegFsmCmp);

    // Check for a multi-cycle pattern match (Given SMU is enabled)
    assign trigger = OverallSmuEn ? (StateMatch & CmpSel) : 1'b0;

    // SMU FSM Datapath - Update FSM when a Cmp match is found and we are not yet at the target pattern match state
    assign SmuStateNext = rst ? 0:
                          (CmpSel & ~StateMatch)  ?  (SmuState + 1'd1) : 
                          0 ;

    // SMU FSM FF
    always @(posedge gated_clk) begin
        SmuState <= SmuStateNext;
    end

    // Clock Gating logic - Used to enable/disable SMU
    assign gated_clk = clk & (OverallSmuEn | rst);
endmodule

