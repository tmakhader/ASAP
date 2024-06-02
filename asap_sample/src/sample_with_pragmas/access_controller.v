

module access_controller #
(
  parameter KH_S = 64,
  parameter DT_S = 3,
  parameter ACR_S = 8
)
(
  input  wire [0:0] clk,                 // #pragma control clock 0:0
  input  wire [0:0] rst,                 // #pragma control signal 0:0
  input  wire [KH_S-1:0] key_hash,
  input  wire [0:0] key_en,              // #pragma observe 0:0
  input  wire [DT_S-1:0] req_type,
  input  wire [DT_S*ACR_S-1:0] access_reg,
  output wire access_en
);

  localparam IND_S      = $clog2(ACR_S);
  localparam DEHASH_KEY = 32'hDEADBEEF;
  localparam FH_S       = 32;
  reg  [IND_S-1:0]   key_index;
  reg  [IND_S-1:0]   key_index_next;
  wire [KH_S-1:0]    xored_key_hash;

  assign xored_key_hash = key_hash[KH_S-1:FH_S] ^ key_hash[FH_S-1:0] ^ DEHASH_KEY;

  always @(*) begin
    if( rst ) begin
          key_index_next = 3'd0;
    end else if(key_en) begin
         case(xored_key_hash)
               32'hABCD_ABCD : key_index_next = 3'd3;
               32'hBCDA_BCDA : key_index_next = 3'd4;
               default       : key_index_next = 3'd0;
      endcase
    end else begin
      key_index_next = key_index;
    end
  end


  always @(posedge clk) begin
       key_index <= key_index_next;
  end

  assign access_en = access_reg[req_type * ACR_S + key_index];

endmodule

