`define SECURITY_BUG_STIMULUS
//`define ASAP_ENABLE
module top_tb;
    // Parameter definitions
    localparam   PKT_S = 32;
    localparam   D_S   = 128;
    localparam   KH_S  = 64;
    localparam   DT_S  = 3;
    localparam   ACR_S = 8;
    localparam   PRIVILEGED_TYPE = 3'd2;
    localparam   DEHASH_KEY      = 32'hDEADBEEF;
`ifdef ASAP_ENABLE
    localparam   SMU_CFG_SIZE      = 475;
    localparam   SRU_CFG_SIZE      = 273;
    localparam   SMU_OBSERVE_WIDTH = 40;
    localparam   SRU_CONTROL_WIDTH = 38;
`endif 


    // clk and reset
    reg                clk = 1'b0;
    reg                rst = 1'b1;
    // Software request interface
    reg  [PKT_S-1:0]   data_in = 0;
    reg                req_valid = 0;
    // Availability of response queue to accept responses
    reg                rd_ready = 0;
    // Software response interface
    wire  [PKT_S-1:0]  data_out;
    wire               rsp_valid;

    // SMU/SRU related definitions
`ifdef ASAP_ENABLE
    // SMU/SRU cfg reg
    reg                           cfg_clk = 0;
    reg                           patch_blk_rst = 0;
    reg                           smu_stream_valid = 0;
    reg                           serial_in = 0;
    // smu_cfg, sru_cfg needs to be array/memory as we are using readmemb to read cfg data from strem file
    reg                           smu_cfg[SMU_CFG_SIZE-1:0];
    reg                           sru_cfg[SRU_CFG_SIZE-1:0];
    reg                           sru_stream_valid = 0;
    reg   [7:0]                   byte_data = 0;
    integer                       f; // file handle
    integer                       index, msb, lsb;

    // Connections from ASAP inserted RTL logic to ASAP patch block
    wire  [SMU_OBSERVE_WIDTH-1:0] observe_port;
    wire  [SRU_CONTROL_WIDTH-1:0] control_port_in;
    wire  [SRU_CONTROL_WIDTH-1:0] control_port_out;
`endif 

    // Privileged data from target agent
    wire  [D_S-1:0]    priv_data_in;
    // access_reg is placed outside this module under consideration 
    reg [DT_S-1:0][ACR_S-1:0]  access_reg = 0;
        
    // Clock simulation
    always begin
        #5 clk = ~clk;
    end

`ifdef ASAP_ENABLE
    always begin
        #5 cfg_clk = ~cfg_clk;
    end
`endif

    // Initializing access register
    integer i;
    initial begin
        for(i = 0; i < DT_S; i++) begin
            // Just for test purposes, PRIVILEGED_TYPE is the only data type with data access,
            // provided the requesting agent provides the right key such that the key hash
            // indexes to the tight access_index (in this case - 3 or 4)
            if (i == PRIVILEGED_TYPE) begin
                access_reg[i] = 8'b0001_1000;
            end else begin
                access_reg[0] = 8'b0000_0000;
            end
        end
        $display("Initialized value of access_reg[PRIV_TYPE] to %b", access_reg[PRIVILEGED_TYPE]);
    end 

    // This task is used to send a privileged software request
    task send_privileged_software_req;
        begin
                // Set req valid to 1 until all the four flits are sent
                    req_valid = 1'b1;

                // Send in software request in 4 flits
                    // First flit - The software adaptor doesn't use the first flit. So it may be zero
                    data_in   = 32'd0;
                    // Second flit - The msb 3 bits forms the data type / request type
                #10 data_in   = {29'd0, PRIVILEGED_TYPE};   
                    // Third flit - Sends the MSB 32 bits of the key hash
                #10 data_in = DEHASH_KEY;
                    // fourth flit - Sends in the rest of key_hash data
                #10 data_in   = 32'hABCD_ABCD;  
                // Unset reqvalid once the request is sent
                #10 req_valid = 1'b0;
        end
    endtask

    // This task is used to send a malicious/unprivileged software request
    task send_malicious_software_req;
        begin
                // Set req valid to 1 until all the four flits are sent
                    req_valid = 1'b1;
                // Send in software request in 4 flits
                    // First flit - The software adaptor doesn't use the first flit. So it may be zero
                    data_in   = 32'd0;
                    // Second flit - The msb 3 bits forms the data type / request type
                #10 data_in   = {29'd0, PRIVILEGED_TYPE};   
                    // Third flit - Sends the MSB 32 bits of the key hash
                #10 data_in   = $random;
                    // fourth flit - Sends in the rest of key_hash data
                #10 data_in   = $random;  
                // Unset reqvalid once the request is sent
                #10 req_valid = 0;
        end
    endtask

`ifdef ASAP_ENABLE
    // Task to configure smu_cfg
    task configure_smu;
        begin
            for (index = 0; index < SMU_CFG_SIZE; index = index + 1) begin
                #10 smu_stream_valid = 1'b1;
                serial_in = smu_cfg[index];
            end
            #10 smu_stream_valid = 1'b0;
        end
    endtask
`endif 

`ifdef ASAP_ENABLE
    // Task to configure sru_cfg
    task configure_sru;
        begin
            for (index = 0; index < SRU_CFG_SIZE; index = index + 1) begin
                #10 sru_stream_valid = 1'b1;
                serial_in = sru_cfg[index];
            end
            #10 sru_stream_valid = 1'b0;
        end
    endtask
`endif 

    // Simulation interface to send in data to software adaptor
    initial begin
        $dumpfile("waveform.vcd");
        $dumpvars(0, top_tb);

`ifdef ASAP_ENABLE
        $readmemb("../smu.stream", smu_cfg);
        $readmemb("../sru.stream", sru_cfg);
        $write("\nLoaded SMU Config: ");
        for (index = SMU_CFG_SIZE-1; index > 0; index = index - 1) begin
            $write("%b",smu_cfg[index]);
        end
        $write("\n");
        $write("\nLoaded SRU Config: ");
        for (index = SRU_CFG_SIZE-1; index > 0; index = index - 1)  begin
            $write("%b",sru_cfg[index]);
        end
        $write("\n");

`endif 


// Reset sequence for patch block
         rst  = 1'b1; // Main IP in reset mode
`ifdef ASAP_ENABLE
             patch_blk_rst  = 1'b1;
         #20 patch_blk_rst  = 1'b0;
`endif 

// Programming sequenc efor SMU/SRU
`ifdef ASAP_ENABLE
        // Program SMU and SRU using the smu.stream and sru.stream bitstream files
         configure_smu;
         // Minor delay b/w SMU and SRU configuration
         #100;
         configure_sru;
`endif 

        // IP rst runs for 4 clock cycles - quiescence period
         #20 rst  = 1'b0;
   
         #20 send_privileged_software_req;
        // Wait for 5 cycles to simulate availability of software read queue 
         #10  rd_ready = 1'b1; 
 
`ifndef SECURITY_BUG_STIMULUS
         #50  rd_ready = 1'b0; 
`endif

        // Sending the malicious request - Note that queue was read queue was already ready when 
        // we received this request, hence, response
         #50 send_malicious_software_req;

`ifndef SECURITY_BUG_STIMULUS
         #50 rd_ready = 1'b1; 
`endif
  
         #100 $finish;
    end

    top #(
        .PKT_S    ( PKT_S ),
        .D_S      ( D_S  ),
        .KH_S     ( KH_S  ),
        .DT_S     ( DT_S  ),
        .ACR_S    ( ACR_S )        
    ) top_inst (
       .clk              (   clk              ),
       .rst              (   rst              ),
       .data_in          (   data_in          ),
       .req_valid        (   req_valid        ),
       .rd_ready         (   rd_ready         ),
       .data_out         (   data_out         ),
       .rsp_valid        (   rsp_valid        ),
`ifdef ASAP_ENABLE
       .observe_port     (   observe_port     ),
       .control_port_in  (   control_port_in  ),
       .control_port_out (   control_port_out ),
`endif 
       .access_reg       (   access_reg       )
    );

// ASAP Patch block instance
`ifdef ASAP_ENABLE
    patchBlock patch_inst (
       .clk                  (    clk               ),
       .cfgClk               (    cfg_clk           ),
       .rst                  (    patch_blk_rst     ),
       .bitstreamSerialIn    (    serial_in         ),
       .smuStreamValid       (    smu_stream_valid  ),
       .sruStreamValid       (    sru_stream_valid  ),
       .p                    (    observe_port      ),
       .qIn                  (    control_port_in   ),
       .qOut                 (    control_port_out  )
    );
`endif  


    initial begin
        $monitor("Value of data_in at time %d = %h", $time, data_in);
    end
endmodule