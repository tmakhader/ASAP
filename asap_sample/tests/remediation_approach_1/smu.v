module smu # (
    parameter  N                  =    2,             // Maximum # of cycles for observability
    parameter  K                  =    4,             // Maximum # of observable signal bits
    parameter  M                  =    6,             // Maximum # of triggers (parallel SMU units)    
    parameter  DECRYPT_KEY        =    32'h0000_0000, // Decryption key for bit-stream
    parameter  SMU_SEGMENT_SIZE   =    64             // Describes the size of smu_unit. For instance
                                                      // hardware complexity-wise this deploys a 64
                                                      // bit comperator
) (
    // Clk and Rst
    input  wire             clk,                     // clk
    input  wire             rst,                     // rst
    input  wire [K-1:0]     p,                       // K-bit observable input set 
    input  wire             bitstreamSerialIn,       // Bit-Stream input
    input  wire             bitstreamValid,
    input  wire             cfgClk,
    // M-bit trigger output
    output wire [M-1:0]     trigger
);

    // Internally generated local params
    localparam SMU_NUM_SEGMENTS   = (K + SMU_SEGMENT_SIZE - 1)/SMU_SEGMENT_SIZE;  // # of segments
    // When SMU_NUM_SEGMENTS = 1, BITS_NUM_SEGMENTS should be 1 due to arch
    // requirement for segment selection
    localparam BITS_NUM_SEGMENTS  = (SMU_NUM_SEGMENTS == 1) ? 1 : $clog2(SMU_NUM_SEGMENTS);

    // CfgRegSmu constitite the relevant configuration registers for SMU.
    // All these config fields are configured per smu state and smu unit
    // The signal ordering is:    {RegInpSel      --> Selects the relevant input segment for a SMU unit at a given time
    //                             RegCmp,        --> The comparison constant for an SMU unit at a given time
    //                             RegMask,       --> Input mask to select the relevant signal bits for SMU unit in selected segment at a given time
    //                             RegFsmCmp,     --> Selects the relevant FSM state at which the sequence ends
    //                             RegCmpSelect}  --> Selects the type of comparison for SMU unit at a given time


    // RegCmpSel - Register used to select the type of comparison
    localparam REG_CMP_SEL_LSB    = 0;
    localparam REG_CMP_SEL_MSB    = REG_CMP_SEL_LSB + 1;
    // RegFsmCmp - FSM limit register used to set the length of sequence mapped to a SMU unit
    localparam REG_FSM_CMP_LSB    = REG_CMP_SEL_MSB + 1;
    localparam REG_FSM_CMP_MSB    = REG_FSM_CMP_LSB + $clog2(N) - 1;
    // RegMask - MASK selecting relevant bits from the selected segment
    localparam REG_MASK_LSB       = REG_FSM_CMP_MSB + 1;
    localparam REG_MASK_MSB       = REG_MASK_LSB + SMU_SEGMENT_SIZE - 1;
    // RegCmpVal - The comparison value for the selected signal
    localparam REG_CMP_VAL_LSB    = REG_MASK_MSB + 1;
    localparam REG_CMP_VAL_MSB    = REG_CMP_VAL_LSB + SMU_SEGMENT_SIZE - 1;
    // RegInpSel Cfg - Selects the relevant input segment for a SMU unit
    localparam REG_INP_SEL_LSB    = REG_CMP_VAL_MSB + 1;
    localparam REG_INP_SEL_MSB    = REG_INP_SEL_LSB + BITS_NUM_SEGMENTS - 1;
    // RegSmuEn Cfg - Enables the SMU. If not triggered, SMU state would be pinned to 0 after reset
    localparam REG_SMU_ENB_LSB    = REG_INP_SEL_MSB + 1;
    localparam REG_SMU_ENB_MSB    = REG_SMU_ENB_LSB;
    
    // SMU unit cfg size and total cfg size
    localparam CFG_SMU_UNIT_SIZE  = REG_SMU_ENB_MSB - REG_CMP_SEL_LSB + 1;
    localparam SMU_CFG_SIZE       = N * M * CFG_SMU_UNIT_SIZE;

    // Configuration register per state for M X smu_unit 
    // This is muxed based on the SmuState of the corresponding smu_unit
    wire [$clog2(N)-1:0]                           SmuState[M-1:0];
    wire                                           SmuEn;
    wire                                           DecryptionDone;
    wire                                           SmuCfgDoneUnsynced;
    reg                                            SmuCfgDone;

    // Primary configuration array that is sequentially programmed during boot
    wire [SMU_CFG_SIZE-1:0]                       CfgRegSmuEncrypted;
    wire [SMU_CFG_SIZE-1:0]                       CfgRegSmuDecrypted;
    // NOTE - CfgRegSmu holds the same data has CfgRegSmuDecrypted. But CfgRegSmu is an 2-D array of vectors
    //        whereas CfgRegSmuDecrypted is a 3-D vector. The difference is that, CfgRegSmu being an array
    //        (also referred to as memory in Verilog LRM), lets you dynamically index it based on nets/variables
    //        This is required as we are required to provide cfgs per state, where state is an output from
    //        SMU.
    wire [CFG_SMU_UNIT_SIZE-1:0]                  CfgRegSmu[N-1:0][M-1:0];
    genvar g_smu;


    // Each block here signify a distinct trigger pattern detection logic
    // in same or distinct host logic systems
    generate
        for (g_smu = 0; g_smu < M; g_smu=g_smu+1) begin : genblk_smu
            smu_unit # (
                .N                   ( N ),
                .K                   ( K ),
                .SMU_SEGMENT_SIZE    ( SMU_SEGMENT_SIZE )
            
            ) smu_unit_inst (
                // Clk, Rst, observable input set, SMU enable signal
                .clk            ( clk ),
                .rst            ( rst ),
                .i              ( p ) , 
                .SmuEn          ( SmuEn ),  // SMU is enabled once the CfgReg is programmed    

                // Configuration Registers -- Function of SmuState and genvar g_smu
                .RegSmuEn       ( CfgRegSmu[SmuState[g_smu]][g_smu][REG_SMU_ENB_MSB:REG_SMU_ENB_LSB] ),
                .RegInpSel      ( CfgRegSmu[SmuState[g_smu]][g_smu][REG_INP_SEL_MSB:REG_INP_SEL_LSB] ),
                .RegMask        ( CfgRegSmu[SmuState[g_smu]][g_smu][REG_MASK_MSB:REG_MASK_LSB] ),
                .RegCmp         ( CfgRegSmu[SmuState[g_smu]][g_smu][REG_CMP_VAL_MSB:REG_CMP_VAL_LSB] ),
                .RegCmpSelect   ( CfgRegSmu[SmuState[g_smu]][g_smu][REG_CMP_SEL_MSB:REG_CMP_SEL_LSB]),
                .RegFsmCmp      ( CfgRegSmu[SmuState[g_smu]][g_smu][REG_FSM_CMP_MSB:REG_FSM_CMP_LSB]),

                // Trigger and pattern match state
                .trigger        ( trigger[g_smu]),
                .SmuState       ( SmuState[g_smu] )
            );
        end
    endgenerate

    // Connecting up CfgRegSmu array to flattened Cfg vector with appropriate indexing.
    genvar g_cfg_out, g_cfg_in;
    generate
        for (g_cfg_out = 0; g_cfg_out < N; g_cfg_out = g_cfg_out + 1) begin : genblk_cfg_out
            for (g_cfg_in = 0; g_cfg_in < M; g_cfg_in = g_cfg_in + 1) begin : genblk_cfg_in
                assign CfgRegSmu[g_cfg_out][g_cfg_in] = CfgRegSmuDecrypted[((g_cfg_out*M + g_cfg_in + 1)*CFG_SMU_UNIT_SIZE - 1) -: CFG_SMU_UNIT_SIZE];
            end
        end
    endgenerate

    // Module to interface a sequential cfg bitstream
    bitstream_deserializer # (
        .CFG_SIZE            ( N*M*CFG_SMU_UNIT_SIZE )
    ) deserializer_inst (
        .clk                 ( cfgClk ),
        .rst                 ( rst ),
        .SerialIn            ( bitstreamSerialIn ),
        .StreamValid         ( bitstreamValid ),
        .ParallelOut         ( CfgRegSmuEncrypted ),

        
        .CfgDone             ( SmuCfgDoneUnsynced )
    );


    // Dual Flop - Sync logic to sync b/w d deserializer and 
    //             the SMU logic. Since, we know that the
    //             deserialized cfg is used only after CfgDone,
    //             syncing CfgDone should ensure appropriate
    //             Clock Domain Crossing (CDC) consistency 

    always @(posedge clk) begin
        SmuCfgDone <= SmuCfgDoneUnsynced;
    end

    assign SmuEn =  SmuCfgDone    &
                    DecryptionDone;
    

    // Module to decrypt the cfg bitstream
    cfg_decrypt #(
        .CFG_SIZE       ( N*M*CFG_SMU_UNIT_SIZE ),
        .DECRYPT_KEY    ( DECRYPT_KEY )
    ) smu_cfg_decrypt_smu_inst (
        .EncryptedCfg   ( CfgRegSmuEncrypted ),
        .DecryptedCfg   ( CfgRegSmuDecrypted ),
        .DecryptionDone ( DecryptionDone ) 
    );

    
endmodule
