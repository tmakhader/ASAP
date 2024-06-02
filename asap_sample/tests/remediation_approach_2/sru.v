module sru #(
    parameter  M                  =    6,                    // Maximum # of triggers (parallel SMU units) 
    parameter  C                  =    5,                    // Maximum # of clk signals under control
    parameter  S                  =    20,                   // Maximum # of signal bits under control
    parameter  NUM_PLA            =    5,                    // # of PLAs in the design
    parameter  SRU_SEGMENT_SIZE   =    3,                    // Maximum # of SMU trigger signal to determine patch control
    parameter  DECRYPT_KEY        =    32'h0000_0000,        // Decryption key for bit-stream

    // These are locally used parameters. Verilog doesn't allow declaration
    // of localparams in module param list. Hence declaring as mainline param
    parameter  CONTROL_WIDTH      =    C + S                 // Width of controllable signal set
) (
    // clk and reset signals
    input  wire                  clk,
    input  wire                  cfgClk,                    // cfg_clk
    input  wire                  rst,
    input  wire                  bitstreamSerialIn,          // Bit-Stream input
    input  wire                  bitstreamValid,             // Bit-stream valid
    input  wire                  GlobalFruEn,                // Lets you enable/disable FRU
    // Controllable signal set
    input  wire  [CONTROL_WIDTH-1:0]  Qin,                   // Controllable signal set input (In the order) -
                                                             // {FSM_STATE_INPUTS, FSM_STATE_OUTPUTS, CLKS, NON_FSM_SIGNALS}

    input  wire  [M-1:0]              trigger,

    output wire  [CONTROL_WIDTH-1:0]  Qout                   // Controllable signal set output (In the order) -
                                                             // {FSM_STATE_INPUTS, FSM_STATE_OUTPUTS, CLKS, NON_FSM_SIGNALS}
); 
    //                    Combinational Path in in SRU
    //
    //                 |\                        |\            
    //  Trigger  ------| \        ________       | \                Q'
    //  Trigger  ------|  |      |        |      |  \               |       
    //  Trigger  ------|  |------|  PLA   |------|   \              |
    //  Trigger  ------| /       |________|      |    |       ______|_________
    //                 |/                        |    |      |               |
    //                                           |    |------| SIGNAL FILTER |
    //                 |\                        |    |      |_______________|      
    //  Trigger  ------| \        ________       |    |             |
    //  Trigger  ------|  |      |        |      |   /              |
    //  Trigger  ------|  |------|  PLA   |------|  /               |
    //  Trigger  ------| /       |________|      | /                Q
    //                 |/                        |/
    //         Trigger Selector                 PLA Selector   

    // CfgRegFru constitite the constants for signal filters and PLA cfg_registers
    // The signal ordering is:    {RegMux                    --> Signal selector for PLAs
    //                             RegMintermORSelect,       --> Minterm selector for PLAs
    //                             RegSignalPlaSelect,       --> Register for selecting PLAs for signal control instances
    //                             RegClockPlaSelect,        --> Register for selecting PLAs for clock control instances
    //                             RegCtrlEnbSignal,         --> Control enable cfg for signal controls
    //                             RegCtrlEnbClock,          --> Control enable cfg for clock controls
    //                             RegClockConstSignals}     --> Constants for controllable signals' filters 

    // NOTE - To disable a signal filter, configure 
    // Constant cfg is required for each signal control bit
    localparam REG_CONST_LSB         = 0;                                     
    localparam REG_CONST_MSB         = REG_CONST_LSB + S - 1;
    // control enable cfg for clock control
    localparam REG_CLK_CTL_ENB_LSB   = REG_CONST_MSB + 1;
    localparam REG_CLK_CTL_ENB_MSB   = REG_CLK_CTL_ENB_LSB + C - 1;
    // control enable cfg for signal control
    localparam REG_SIG_CTL_ENB_LSB   = REG_CLK_CTL_ENB_MSB + 1;       
    localparam REG_SIG_CTL_ENB_MSB   = REG_SIG_CTL_ENB_LSB + S - 1;
    // PLA selector cfg for clock controls - Selects from NUM_PLA PLAs per controlled clock bit
    localparam REG_PLA_SEL_CLK_LSB   = REG_SIG_CTL_ENB_MSB + 1;
    localparam REG_PLA_SEL_CLK_MSB   = REG_PLA_SEL_CLK_LSB + (C * $clog2(NUM_PLA)) - 1;     
    // PLA selector cfg for signal controls - Selects from NUM_PLA PLAs per controlled signal bit
    localparam REG_PLA_SEL_SIG_LSB   = REG_PLA_SEL_CLK_MSB + 1;
    localparam REG_PLA_SEL_SIG_MSB   = REG_PLA_SEL_SIG_LSB + (S * $clog2(NUM_PLA)) - 1;      
    // Minterm selector cfg is required for all PLAs (NUM_PLA), and need to select minterms from 2**SRU_SEGMENT_SIZE
    localparam REG_MINTERM_LSB       = REG_PLA_SEL_SIG_MSB + 1; 
    localparam REG_MINTERM_MSB       = REG_MINTERM_LSB + (NUM_PLA * (2 ** SRU_SEGMENT_SIZE)) - 1;           
    // Trigger signal selector cfg is required for all PLAs, per PLA segment bit to select a trigger signal from M trigger signals
    localparam REG_SIG_SEL_LSB       = REG_MINTERM_MSB + 1; 
    localparam REG_SIG_SEL_MSB       = REG_SIG_SEL_LSB + (NUM_PLA * SRU_SEGMENT_SIZE * $clog2(M)) - 1;  
 
    // Net cfg width
    localparam CFG_SIZE              = REG_SIG_SEL_MSB - REG_CONST_LSB + 1;

    // Qin/Qout constitute the controllable input/output set
    // The signal ordering is:   {Signals,                   --> Signals under control horizon
    //                            ClkSignals}                --> Clk signals under control horizon

    localparam PART_SIGNAL_LSB      = 0;
    localparam PART_SIGNAL_MSB      = PART_SIGNAL_LSB + S - 1;                                      
    localparam PART_CLK_LSB         = PART_SIGNAL_MSB + 1;
    localparam PART_CLK_MSB         = PART_CLK_LSB + C - 1;    

    // Register sizes per PLA
    localparam REG_MUX_BITS_PER_PLA     = SRU_SEGMENT_SIZE * $clog2(M); 
    localparam REG_MINTERM_SEL_PER_PLA  = 2**SRU_SEGMENT_SIZE;

    wire [CFG_SIZE-1:0]                      CfgRegFru, CfgRegFruEncrypted;
    wire [REG_SIG_SEL_MSB-REG_SIG_SEL_LSB:0] RegMux;
    wire [REG_MINTERM_MSB-REG_MINTERM_LSB:0] RegMintermORSelect;
    wire                                     Pla[NUM_PLA-1:0];
    wire [PART_CLK_MSB:PART_SIGNAL_LSB]      FruEn;
    // Signals indicating completion of SRU bitstream interception
    wire                                     SruCfgDoneUnsynced;
    wire                                     DecryptionDone;
    reg                                      SruCfgDone;

    // Segmented PLA instantiation
    genvar g_pla;
    generate
        assign RegMux             =  CfgRegFru[REG_SIG_SEL_MSB:REG_SIG_SEL_LSB];
        assign RegMintermORSelect =  CfgRegFru[REG_MINTERM_MSB:REG_MINTERM_LSB];
        // Instantiate OUTPUT_SIZE # of SEGMENT_SIZE X 1 segmented PLU units
        for (g_pla = 0; g_pla < NUM_PLA; g_pla = g_pla + 1) begin  : genblk_pla
            sru_pla_unit #(
                .M                    ( M                ),
                .SEGMENT_SIZE         ( SRU_SEGMENT_SIZE )
            ) sru_pla_unit_inst (
                .Trigger              ( trigger                                                                           ),
                .RegMux               ( RegMux[(g_pla+1)*REG_MUX_BITS_PER_PLA-1 -: REG_MUX_BITS_PER_PLA]                  ),
                .RegMintermORSelect   ( RegMintermORSelect[(g_pla+1)*REG_MINTERM_SEL_PER_PLA-1 -:REG_MINTERM_SEL_PER_PLA] ),
                .Select               ( Pla[g_pla]                                                                        )
            );
        end
    endgenerate


    // Signal filter instantiation 
    genvar g_sru;

    // Signal filter logic block instantiation
    wire BypassEn[S-1:0];
    generate
        for (g_sru = 0; g_sru <= (PART_SIGNAL_MSB-PART_SIGNAL_LSB); g_sru = g_sru + 1) begin : genblk_signal
            assign BypassEn[g_sru] = Pla[CfgRegFru[g_sru + REG_PLA_SEL_SIG_LSB]];
            sru_signal_filter_unit sru_signal_filter_unit_inst (
                .Qin                  ( Qin[g_sru + PART_SIGNAL_LSB]     ),
                .BypassEn             ( BypassEn[g_sru]                  ),
                .RegConst             ( CfgRegFru[g_sru + REG_CONST_LSB] ),
                .FruEn                ( FruEn[g_sru + C]                 ),
                .Qout                 ( Qout[g_sru + PART_SIGNAL_LSB]    )
            );
        end
    endgenerate


    // Security clock gating logic block instantiation
    wire ClkGateEn[C-1:0];
    generate
        for (g_sru = 0; g_sru <= (PART_CLK_MSB-PART_CLK_LSB); g_sru = g_sru + 1) begin  : genblk_clk
            // Selector MUX that selects the appropriate PLA out signal for gating the clk  
            assign ClkGateEn[g_sru] = Pla[CfgRegFru[g_sru + REG_PLA_SEL_CLK_LSB]];
            sru_security_clock_gate sru_security_clock_gate_inst (
                .clk                ( Qin[g_sru + PART_CLK_LSB]  ),
                .gate_en            ( ClkGateEn[g_sru]           ),
                .FruEn              ( FruEn[g_sru]               ),
                .gated_clk          ( Qout[g_sru + PART_CLK_LSB] )
            );
        end
    endgenerate

    // Bitstream deserializer - To intercept cfg bits and program the cfg register
    bitstream_deserializer #(
        .CFG_SIZE           ( CFG_SIZE )
    ) sru_bitstream_deserializer_inst (
        .SerialIn           ( bitstreamSerialIn  ),
        .StreamValid        ( bitstreamValid     ),
        .clk                ( cfgClk             ),
        .rst                ( rst                ),
        .ParallelOut        ( CfgRegFruEncrypted ),
        .CfgDone            ( SruCfgDoneUnsynced )
    );

    genvar g_sru_en;
    // SRU is enabled upon 3 conditions being met
    // 1. SRU Encrypted Bitstream interecepted successfully
    // 2. SRU Bitstream decrypted
    // 3. Controls enabled via config
    generate
        for (g_sru_en = 0; g_sru_en < CONTROL_WIDTH; g_sru_en = g_sru_en + 1) begin  : genblk_cfg_vec2array
            assign FruEn[g_sru_en] = CfgRegFru[REG_CLK_CTL_ENB_LSB + g_sru_en]   & 
                                     SruCfgDone                                  &
                                     DecryptionDone;
        end
    endgenerate

    // Dual Flop - Sync logic to sync b/w d deserializer and 
    //             the SRU logic. Since, we know that the
    //             deserialized cfg is used only after CfgDone,
    //             syncing CfgDone should ensure appropriate
    //             Clock Domain Crossing (CDC) consistency 

    always @(posedge clk) begin
        SruCfgDone <= SruCfgDoneUnsynced;
    end

    // Bitstream decryption
    cfg_decrypt #(
        .CFG_SIZE          ( CFG_SIZE           ),
        .DECRYPT_KEY       ( DECRYPT_KEY        )
    ) fru_cfg_decrypt_inst (
        .EncryptedCfg      ( CfgRegFruEncrypted ),
        .DecryptedCfg      ( CfgRegFru          ),
        .DecryptionDone    ( DecryptionDone     )
    );
endmodule
