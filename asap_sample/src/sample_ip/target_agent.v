

module target_agent #
(
  parameter D_S = 128
)
(
  input  wire [0:0]     access_en,
  output wire [D_S-1:0] priv_data
);
  localparam PRIV_DATA = 128'hABCD_ABCD_DABC_ABCD_ABCD_DABC_DABC_DABC;
  assign priv_data = (access_en)? PRIV_DATA : 128'd0;

endmodule

