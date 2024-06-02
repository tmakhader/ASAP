

module top #
(
  parameter PKT_S = 32,
  parameter D_S = 128,
  parameter KH_S = 64,
  parameter DT_S = 3,
  parameter ACR_S = 8
)
(
  input wire clk,
  input wire rst,
  input wire [PKT_S-1:0] data_in,
  input wire req_valid,
  input wire [0:0] rd_ready,
  output wire [PKT_S-1:0] data_out,
  output wire rsp_valid,
  input wire [DT_S*ACR_S-1:0] access_reg,
  output [39:0] observe_port,
  output [37:0] control_port_in,
  input [37:0] control_port_out
);

  wire [36:0] control_port_out_inst;
  wire [36:0] control_port_in_inst;
  wire [38:0] observe_port_inst;
  wire [0:0] observe_port_int;
  wire [0:0] control_port_in_int;
  wire [0:0] control_port_out_int;
  wire [0:0] rd_ready_controlled;
  localparam FH_S = 32;
  wire [KH_S-1:0] key_hash;
  wire [DT_S-1:0] req_type;
  wire [D_S-1:0] priv_data;
  wire key_en;
  wire access_en;

  software_adaptor
  #(
    .PKT_S(PKT_S),
    .D_S(D_S),
    .KH_S(KH_S),
    .DT_S(DT_S)
  )
  adaptor
  (
    .clk(clk),
    .rst(rst),
    .data_in(data_in),
    .req_valid(req_valid),
    .rd_ready(rd_ready_controlled),
    .data_out(data_out),
    .rsp_valid(rsp_valid),
    .priv_data(priv_data),
    .key_hash(key_hash),
    .req_type(req_type),
    .key_en(key_en),
    .observe_port(observe_port_inst[36:0]),
    .control_port_in(control_port_in_inst[33:0]),
    .control_port_out(control_port_out_inst[33:0])
  );


  access_controller
  #(
    .DT_S(DT_S),
    .KH_S(KH_S),
    .ACR_S(ACR_S)
  )
  controller
  (
    .clk(clk),
    .rst(rst),
    .key_en(key_en),
    .key_hash(key_hash),
    .req_type(req_type),
    .access_reg(access_reg),
    .access_en(access_en),
    .observe_port(observe_port_inst[37:37]),
    .control_port_in(control_port_in_inst[35:34]),
    .control_port_out(control_port_out_inst[35:34])
  );


  target_agent
  #(
    .D_S(D_S)
  )
  agent
  (
    .access_en(access_en),
    .priv_data(priv_data),
    .observe_port(observe_port_inst[38:38]),
    .control_port_in(control_port_in_inst[36:36]),
    .control_port_out(control_port_out_inst[36:36])
  );

  assign control_port_in_int[0:0] = rd_ready[0:0];
  assign rd_ready_controlled[0:0] = control_port_out_int[0:0];
  assign observe_port_int[0:0] = rd_ready[0:0];
  assign observe_port = { observe_port_int, observe_port_inst };
  assign control_port_in = { control_port_in_int, control_port_in_inst };
  assign { control_port_out_int, control_port_out_inst } = control_port_out;

endmodule

