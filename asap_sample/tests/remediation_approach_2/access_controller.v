

module access_controller #
(
  parameter KH_S = 64,
  parameter DT_S = 3,
  parameter ACR_S = 8
)
(
  input wire [0:0] clk,
  input wire [0:0] rst,
  input wire [KH_S-1:0] key_hash,
  input wire [0:0] key_en,
  input wire [DT_S-1:0] req_type,
  input wire [DT_S*ACR_S-1:0] access_reg,
  output wire access_en,
  output [0:0] observe_port,
  output [1:0] control_port_in,
  input [1:0] control_port_out
);

  wire [0:0] observe_port_int;
  wire [1:0] control_port_in_int;
  wire [1:0] control_port_out_int;
  wire [0:0] rst_controlled;
  wire [0:0] clk_controlled;
  localparam IND_S = $clog2(ACR_S);
  localparam DEHASH_KEY = 32'hDEADBEEF;
  localparam FH_S = 32;
  reg [IND_S-1:0] key_index;
  reg [IND_S-1:0] key_index_next;
  wire [KH_S-1:0] xored_key_hash;
  assign xored_key_hash = key_hash[KH_S-1:FH_S] ^ key_hash[FH_S-1:0] ^ DEHASH_KEY;

  always @(*) begin
    if(rst_controlled) begin
      key_index_next = 3'd0;
    end else if(key_en) begin
      case(xored_key_hash)
        32'hABCD_ABCD: key_index_next = 3'd3;
        32'hBCDA_BCDA: key_index_next = 3'd4;
        default: key_index_next = 3'd0;
      endcase
    end else begin
      key_index_next = key_index;
    end
  end


  always @(posedge clk_controlled) begin
    key_index <= key_index_next;
  end

  assign access_en = access_reg[req_type * ACR_S + key_index];
  assign control_port_in_int[0:0] = clk[0:0];
  assign control_port_in_int[1:1] = rst[0:0];
  assign clk_controlled[0:0] = control_port_out_int[0:0];
  assign rst_controlled[0:0] = control_port_out_int[1:1];
  assign observe_port_int[0:0] = key_en[0:0];
  assign observe_port = observe_port_int;
  assign control_port_in = control_port_in_int;
  assign control_port_out_int = control_port_out;

endmodule

