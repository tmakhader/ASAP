

module software_adaptor #
(
  parameter PKT_S      = 32,
  parameter D_S        = 128,
  parameter KH_S       = 64,
  parameter DT_S       = 3
)
(
  input  wire [0:0]       clk,         // #pragma control clock 0:0
  input  wire [0:0]       rst,         // #pragma control signal 0:0
  input  wire [PKT_S-1:0] data_in,     // #pragma observe 31:0
  input  wire [0:0]       req_valid,   // #pragma observe 0:0
  input  wire [0:0]       rd_ready,
  output reg [PKT_S-1:0]  data_out,    // #pragma control signal 31:0
  output reg  [0:0]       rsp_valid,
  input  wire [D_S-1:0]   priv_data,
  output reg  [KH_S-1:0]  key_hash,
  output reg  [DT_S-1:0]  req_type,
  output reg  [0:0]       key_en
);

  localparam FH_S = 32;
  reg [1:0]             req_state;     // #pragma observe 1:0
  reg [1:0]             req_state_next;
  reg [1:0]             rsp_state;     // #pragma observe 1:0
  reg [1:0]             rsp_state_next;
  reg [KH_S-1:0]        key_hash_next;
  reg [2:0]             req_type_next;
  reg                   key_en_next;
  reg                   req_received;
  reg                   rsp_pending;
  wire                  rsp_pending_next;
  reg                   rsp_sent;

  always @(*) begin
      if( rst ) begin
           req_state_next = 2'b00;
      end else if( req_valid ) begin
      case(req_state)
           2'b00    : req_state_next = 2'b01;
           2'b01    : req_state_next = 2'b10;
           2'b10    : req_state_next = 2'b11;
           2'b11    : req_state_next = 2'b00;
           default  : req_state_next = 2'b00;
      endcase
    end else begin
      req_state_next = req_state;
    end
  end


  always @(*) begin
    if( rst ) begin
          rsp_state_next = 2'b00;
    end else if( rd_ready & rsp_pending ) begin
      case(rsp_state)
           2'b00   :   rsp_state_next   = 2'b01;
           2'b01   :   rsp_state_next   = 2'b10;
           2'b10   :   rsp_state_next   = 2'b11;
           2'b11   :   rsp_state_next   = 2'b00;
           default :   rsp_state_next = 2'b00;
      endcase
    end else begin
      rsp_state_next = rsp_state;
    end
  end


  always @(*) begin
    if( rst ) begin
          key_hash_next = { KH_S{ 1'b0 } };
          key_en_next = 1'b0;
          req_type_next = { DT_S{ 1'b0 } };
          req_received = 1'b0;
    end else begin
          case(req_state)
            2'b01: begin
                  key_hash_next   = key_hash;
                  key_en_next     = 1'b0;
                  req_type_next   = data_in[2:0];
                  req_received    = 1'b0;
            end
            2'b10: begin
                  key_hash_next   = { data_in, key_hash[FH_S-1:0] };
                  key_en_next     = 1'b0;
                  req_type_next   = req_type;
                  req_received    = 1'b0;
            end
            2'b11: begin
                  key_hash_next   = { key_hash[KH_S-1:FH_S], data_in };
                  key_en_next     = 1'b1;
                  req_type_next   = req_type;
                  req_received    = 1'b1;
            end
            default: begin
                  key_hash_next   = key_hash;
                  key_en_next     = 1'b0;
                  req_type_next   = req_type;
                  req_received    = 1'b0;
            end
            endcase
      end
   end

  assign rsp_pending_next = (rst)? 1'b0 : rsp_pending & ~rsp_sent | req_received;

  always @(*) begin
    if( rst ) begin
         rsp_valid = 1'b0;
         data_out = 32'd0;
         rsp_sent = 1'b0;
    end else begin
         case({ rd_ready, rsp_pending, rsp_state })
           4'b1_1_00: begin
                    rsp_valid = 1'b1;
                    data_out  = priv_data[31:0];
                    rsp_sent  = 1'b0;
           end
          4'b1_1_01: begin
                    rsp_valid = 1'b1;
                    data_out  = priv_data[63:32];
                    rsp_sent  = 1'b0;
           end
          4'b1_1_10: begin
                   rsp_valid = 1'b1;
                   data_out  = priv_data[95:64];
                   rsp_sent  = 1'b0;
           end
          4'b1_1_11: begin
                   rsp_valid = 1'b1;
                   data_out  = priv_data[127:96];
                   rsp_sent  = 1'b1;
           end
          default:  begin
                   rsp_valid = 1'b0;
                   data_out = 32'd0;
                   rsp_sent = 1'b0;
           end
        endcase
     end
  end


  always @(posedge clk) begin
    req_state    <= req_state_next;
    rsp_state    <= rsp_state_next;
    rsp_pending  <= rsp_pending_next;
    req_type     <= req_type_next;
    key_hash     <= key_hash_next;
    key_en       <= key_en_next;
  end
  
endmodule

