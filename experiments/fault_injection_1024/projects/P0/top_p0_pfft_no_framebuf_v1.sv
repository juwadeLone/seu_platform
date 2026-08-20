`timescale 1ns/1ps

// Isolated experiment top. The canonical P0 FFT pipeline is unchanged; only
// the terminal pfft_frame_pair_buffer_v5 wrapper is bypassed.
module top_p0_pfft_no_framebuf_v1(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
p0_pfft_no_exchange_pipeline_v3 u_pipeline(
 clk,rst,in_valid,in_last,
 in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 out_valid,out_last,
 out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
endmodule
