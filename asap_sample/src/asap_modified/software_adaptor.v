

module software_adaptor #
(
  parameter PKT_S = 32,
  parameter D_S = 128,
  parameter KH_S = 64,
  parameter DT_S = 3
)
(
  input wire [0:0] clk,
  input wire [0:0] rst,
  input wire [PKT_S-1:0] data_in,
  input wire [0:0] req_valid,
  input wire [0:0] rd_ready,
  output wire [PKT_S-1:0] data_out,
  output reg [0:0] rsp_valid,
  input wire [D_S-1:0] priv_data,
  output reg [KH_S-1:0] key_hash,
  output reg [DT_S-1:0] req_type,
  output reg [0:0] key_en,
  output [36:0] observe_port,
  output [33:0] control_port_in,
  input [33:0] control_port_out
);

  wire [36:0] observe_port_int;
  wire [33:0] control_port_in_int;
  wire [33:0] control_port_out_int;
  reg [PKT_S-1:0] data_out_controlled;
  wire [0:0] rst_controlled;
  wire [0:0] clk_controlled;
  localparam FH_S = 32;
  reg [1:0] req_state;
  reg [1:0] req_state_next;
  reg [1:0] rsp_state;
  reg [1:0] rsp_state_next;
  reg [KH_S-1:0] key_hash_next;
  reg [2:0] req_type_next;
  reg key_en_next;
  reg req_received;
  reg rsp_pending;
  wire rsp_pending_next;
  reg rsp_sent;

  always @(*) begin
    if(rst_controlled) begin
      req_state_next = 2'b00;
    end else if(req_valid) begin
      case(req_state)
        2'b00: req_state_next = 2'b01;
        2'b01: req_state_next = 2'b10;
        2'b10: req_state_next = 2'b11;
        2'b11: req_state_next = 2'b00;
        default: req_state_next = 2'b00;
      endcase
    end else begin
      req_state_next = req_state;
    end
  end


  always @(*) begin
    if(rst_controlled) begin
      rsp_state_next = 2'b00;
    end else if(rd_ready & rsp_pending) begin
      case(rsp_state)
        2'b00: rsp_state_next = 2'b01;
        2'b01: rsp_state_next = 2'b10;
        2'b10: rsp_state_next = 2'b11;
        2'b11: rsp_state_next = 2'b00;
        default: rsp_state_next = 2'b00;
      endcase
    end else begin
      rsp_state_next = rsp_state;
    end
  end


  always @(*) begin
    if(rst_controlled) begin
      key_hash_next = { KH_S{ 1'b0 } };
      key_en_next = 1'b0;
      req_type_next = { DT_S{ 1'b0 } };
      req_received = 1'b0;
    end else begin
      case(req_state)
        2'b01: begin
          key_hash_next = key_hash;
          key_en_next = 1'b0;
          req_type_next = data_in[2:0];
          req_received = 1'b0;
        end
        2'b10: begin
          key_hash_next = { data_in, key_hash[FH_S-1:0] };
          key_en_next = 1'b0;
          req_type_next = req_type;
          req_received = 1'b0;
        end
        2'b11: begin
          key_hash_next = { key_hash[KH_S-1:FH_S], data_in };
          key_en_next = 1'b1;
          req_type_next = req_type;
          req_received = 1'b1;
        end
        default: begin
          key_hash_next = key_hash;
          key_en_next = 1'b0;
          req_type_next = req_type;
          req_received = 1'b0;
        end
      endcase
    end
  end

  assign rsp_pending_next = (rst_controlled)? 1'b0 : rsp_pending & ~rsp_sent | req_received;

  always @(*) begin
    if(rst_controlled) begin
      rsp_valid = 1'b0;
      data_out_controlled = 32'd0;
      rsp_sent = 1'b0;
    end else begin
      case({ rd_ready, rsp_pending, rsp_state })
        4'b1_1_00: begin
          rsp_valid = 1'b1;
          data_out_controlled = priv_data[31:0];
          rsp_sent = 1'b0;
        end
        4'b1_1_01: begin
          rsp_valid = 1'b1;
          data_out_controlled = priv_data[63:32];
          rsp_sent = 1'b0;
        end
        4'b1_1_10: begin
          rsp_valid = 1'b1;
          data_out_controlled = priv_data[95:64];
          rsp_sent = 1'b0;
        end
        4'b1_1_11: begin
          rsp_valid = 1'b1;
          data_out_controlled = priv_data[127:96];
          rsp_sent = 1'b1;
        end
        default: begin
          rsp_valid = 1'b0;
          data_out_controlled = 32'd0;
          rsp_sent = 1'b0;
        end
      endcase
    end
  end


  always @(posedge clk_controlled) begin
    req_state <= req_state_next;
    rsp_state <= rsp_state_next;
    rsp_pending <= rsp_pending_next;
    req_type <= req_type_next;
    key_hash <= key_hash_next;
    key_en <= key_en_next;
  end

  assign control_port_in_int[0:0] = clk[0:0];
  assign control_port_in_int[1:1] = rst[0:0];
  assign control_port_in_int[33:2] = data_out_controlled[31:0];
  assign clk_controlled[0:0] = control_port_out_int[0:0];
  assign rst_controlled[0:0] = control_port_out_int[1:1];
  assign data_out[31:0] = control_port_out_int[33:2];
  assign observe_port_int[31:0] = data_in[31:0];
  assign observe_port_int[32:32] = req_valid[0:0];
  assign observe_port_int[34:33] = req_state[1:0];
  assign observe_port_int[36:35] = rsp_state[1:0];
  assign observe_port = observe_port_int;
  assign control_port_in = control_port_in_int;
  assign control_port_out_int = control_port_out;

endmodule

