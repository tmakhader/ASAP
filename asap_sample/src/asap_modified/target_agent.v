

module target_agent #
(
  parameter D_S = 128
)
(
  input wire [0:0] access_en,
  output wire [D_S-1:0] priv_data,
  output [0:0] observe_port,
  output [0:0] control_port_in,
  input [0:0] control_port_out
);

  wire [0:0] observe_port_int;
  wire [0:0] control_port_in_int;
  wire [0:0] control_port_out_int;
  wire [0:0] access_en_controlled;
  localparam PRIV_DATA = 128'hABCD_ABCD_DABC_ABCD_ABCD_DABC_DABC_DABC;
  assign priv_data = (access_en_controlled)? PRIV_DATA : 128'd0;
  assign control_port_in_int[0:0] = access_en[0:0];
  assign access_en_controlled[0:0] = control_port_out_int[0:0];
  assign observe_port_int[0:0] = access_en[0:0];
  assign observe_port = observe_port_int;
  assign control_port_in = control_port_in_int;
  assign control_port_out_int = control_port_out;

endmodule

