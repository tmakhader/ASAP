
module patchBlock #
(
  parameter N = 4,
  parameter K = 1024,
  parameter M = 5,
  parameter C = 6,
  parameter S = 1530,
  parameter CONTROL_WIDTH = C + S,
  parameter NUM_PLA = 12,
  parameter SRU_SEGMENT_SIZE = 8,
  parameter SMU_SEGMENT_SIZE = 64
)
(
  input clk,
  input cfgClk,
  input rst,
  input bitstreamSerialIn,
  input smuStreamValid,
  input sruStreamValid,
  input [K-1:0] p,
  input [CONTROL_WIDTH-1:0] qIn,
  output [CONTROL_WIDTH-1:0] qOut
);

  wire [M-1:0] trigger;

  smu
  #(
    .N(N),
    .K(K),
    .M(M),
    .SMU_SEGMENT_SIZE(SMU_SEGMENT_SIZE)
  )
  smu_inst
  (
    .clk(clk),
    .rst(rst),
    .cfgClk(cfgClk),
    .bitstreamSerialIn(bitstreamSerialIn),
    .bitstreamValid(smuStreamValid),
    .p(p),
    .trigger(trigger)
  );


  sru
  #(
    .M(M),
    .C(C),
    .S(S),
    .NUM_PLA(NUM_PLA),
    .SRU_SEGMENT_SIZE(SRU_SEGMENT_SIZE)
  )
  sru_inst
  (
    .clk(clk),
    .rst(rst),
    .cfgClk(cfgClk),
    .bitstreamSerialIn(bitstreamSerialIn),
    .bitstreamValid(sruStreamValid),
    .Qin(qIn),
    .Qout(qOut),
    .trigger(trigger)
  );


endmodule
