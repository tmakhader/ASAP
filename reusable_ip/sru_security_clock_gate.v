module sru_security_clock_gate (
    input    wire clk,
    input    wire gate_en,
    input    wire FruEn,
    output   wire gated_clk
);
    assign gated_clk = clk & (~FruEn | (gate_en & FruEn));

endmodule