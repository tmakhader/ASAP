

module top #
(
  parameter PKT_S   = 32,
  parameter D_S     = 128,
  parameter KH_S    = 64,
  parameter DT_S    = 3,
  parameter ACR_S   = 8
)
(
  input  wire                  clk,
  input  wire                  rst,
  input  wire  [PKT_S-1:0]     data_in,
  input  wire                  req_valid,
  input  wire  [0:0]           rd_ready,
  output wire  [PKT_S-1:0]     data_out,
  output wire                  rsp_valid,
  input  wire [DT_S*ACR_S-1:0] access_reg
);

  localparam FH_S = 32;

  wire [KH_S-1:0] key_hash;
  wire [DT_S-1:0] req_type;
  wire [D_S-1:0]  priv_data;
  wire            key_en;
  wire            access_en;

  software_adaptor #(
       .PKT_S                   ( PKT_S ),
       .D_S                     ( D_S   ),
       .KH_S                    ( KH_S  ),
       .DT_S                    ( DT_S  )
  )  adaptor  (
       .clk                     ( clk       ),
       .rst                     ( rst       ),
       .data_in                 ( data_in   ),
       .req_valid               ( req_valid ),
       .rd_ready                ( rd_ready  ),
       .data_out                ( data_out  ),
       .rsp_valid               ( rsp_valid ),
       .priv_data               ( priv_data ),
       .key_hash                ( key_hash  ),
       .req_type                ( req_type  ),
       .key_en                  ( key_en    )
  );


  access_controller #(
       .DT_S                    ( DT_S  ),
       .KH_S                    ( KH_S  ),
       .ACR_S                   ( ACR_S )
  ) controller (
       .clk                     ( clk        ),
       .rst                     ( rst        ),
       .key_en                  ( key_en     ),
       .key_hash                ( key_hash   ),
       .req_type                ( req_type   ),
       .access_reg              ( access_reg ),
       .access_en               ( access_en  )
  );


  target_agent #(
       .D_S                     ( D_S )
  ) agent (
       .access_en               ( access_en ),
       .priv_data               ( priv_data )
  );
endmodule

