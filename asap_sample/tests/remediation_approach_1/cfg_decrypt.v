module cfg_decrypt # (
    parameter CFG_SIZE      = 100,
    parameter DECRYPT_KEY   = 32'h0000_0000 
) (
    input  wire [CFG_SIZE-1: 0]     EncryptedCfg,
    output wire [CFG_SIZE-1: 0]     DecryptedCfg,
    output wire                     DecryptionDone
);
    assign DecryptedCfg   = EncryptedCfg ^ {$bits(CFG_SIZE){DECRYPT_KEY}};
    assign DecryptionDone = 1'b1;

endmodule