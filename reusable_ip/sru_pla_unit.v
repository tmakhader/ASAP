// Implementation of a full-fledged SEGMENT_SIZE X 1 PLA with input selection
// customization. Note that SEGMENT size should be at max limited to 4 for 
// better timing convergence. This should be reasonable if we can limit control
// selection based on 4 distinct observable patterns (triggers) at a time.

module sru_pla_unit #(
    parameter M              = 2,
    parameter SEGMENT_SIZE   = 2
) (
    input  wire [M-1:0]                                        Trigger,
    input  wire [$clog2(M)*SEGMENT_SIZE-1:0]                   RegMux,
    input  wire [2**SEGMENT_SIZE-1:0]                          RegMintermORSelect,
    output reg                                                 Select
);

    wire      MuxedInp[SEGMENT_SIZE-1:0];
    reg       Minterms[2**SEGMENT_SIZE-1:0];

    // There are 3 stages in segmented PLA generation - 
    // 1. Trigger Selection - Select SEGMENT_SIZE # of trigger signals from M based on 
    //                        RegMux
    // 2. Minterm Generation - In this stage we generate all possible minterms using the.
    //                         selected signals. For a PLA of segment size 2, we will have 4 minterms
    // 3. Minterm ORing - At this stage we need to OR multiple minterms based on RegMintermORSelect
    // This logic enables us to generate a select logic based on any logical combination of
    // SEGMENT_SIZE # of trigger signals.


    genvar var;
    wire [$clog2(M)-1:0] InpSel[SEGMENT_SIZE-1:0];
    wire                 TrigArray[M-1:0];
    wire [$clog2(M)-1:0]  testBit;

    assign testBit = InpSel[0]; 
    generate
        // Logic to convert trigger from vector to array for dynamic indexing
        for (var = 0; var < M; var = var + 1) begin  : genblk_vec_2_array
            assign TrigArray[var] = Trigger[var];
        end

        // Trigger selection logic
        for (var = 0; var < SEGMENT_SIZE; var = var + 1) begin  : genblk_inp_sel
            assign InpSel[var]   = RegMux[(var+1)*$clog2(M)-1 -: $clog2(M)];
            assign MuxedInp[var] = TrigArray[InpSel[var]];
        end
    endgenerate


    integer g_pla, g_pla_in;
    // Minterm generator block
    always@(*) begin 
        for (g_pla = 0; g_pla < 2**SEGMENT_SIZE; g_pla = g_pla + 1) begin 
            Minterms[g_pla] = 1'b1;
            for (g_pla_in = 0; g_pla_in < SEGMENT_SIZE; g_pla_in = g_pla_in + 1) begin
                if (g_pla & (1<<g_pla_in)) begin
                    Minterms[g_pla] = Minterms[g_pla] &  MuxedInp[g_pla_in];
                end else begin
                    Minterms[g_pla] = Minterms[g_pla] & ~MuxedInp[g_pla_in];
                end
            end
        end
    end

    // Minterm selector block
    //assign Select = 1'b0;

    always@(*) begin
        Select = 1'b0;
        for (g_pla = 0; g_pla < 2**SEGMENT_SIZE; g_pla = g_pla + 1) begin
            Select = Select | (Minterms[g_pla] & RegMintermORSelect[g_pla]);
        end
    end
    
endmodule

