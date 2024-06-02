
module patchBlock #
(
  parameter N = 5,
  parameter K = 40,
  parameter M = 5,
  parameter C = 2,
  parameter S = 36,
  parameter CONTROL_WIDTH = C + S,
  parameter NUM_PLA = 5,
  parameter SRU_SEGMENT_SIZE = 3,
  parameter SMU_SEGMENT_SIZE = 5
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

  wire [CONTROL_WIDTH-1:0] qInInternal;
  wire [CONTROL_WIDTH-1:0] qOutInternal;
  assign qInInternal[36:36] = qIn[0:0];
  assign qOut[0:0] = qOutInternal[36:36];
  assign qInInternal[37:37] = qIn[34:34];
  assign qOut[34:34] = qOutInternal[37:37];
  assign qInInternal[0:0] = qIn[1:1];
  assign qOut[1:1] = qOutInternal[0:0];
  assign qInInternal[32:1] = qIn[33:2];
  assign qOut[33:2] = qOutInternal[32:1];
  assign qInInternal[33:33] = qIn[35:35];
  assign qOut[35:35] = qOutInternal[33:33];
  assign qInInternal[34:34] = qIn[36:36];
  assign qOut[36:36] = qOutInternal[34:34];
  assign qInInternal[35:35] = qIn[37:37];
  assign qOut[37:37] = qOutInternal[35:35];
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
    .Qin(qInInternal),
    .Qout(qOutInternal),
    .trigger(trigger)
  );


endmodule
