`timescale 1ns/1ps

(* keep_hierarchy = "yes" *) module p0_pfft_no_exchange_pipeline_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed [34:0] in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed [34:0] out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire [10:0] v,l;
wire signed [34:0] r0[0:10],i0[0:10],r1[0:10],i1[0:10],r2[0:10],i2[0:10],r3[0:10],i3[0:10];
assign v[0]=in_valid;assign l[0]=in_last;
assign r0[0]=in0_re;assign i0[0]=in0_im;assign r1[0]=in1_re;assign i1[0]=in1_im;
assign r2[0]=in2_re;assign i2[0]=in2_im;assign r3[0]=in3_re;assign i3[0]=in3_im;
pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(128),.STAGE(1)) s1(clk,rst,v[0],l[0],r0[0],i0[0],r1[0],i1[0],r2[0],i2[0],r3[0],i3[0],v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1]);
pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(64), .STAGE(2)) s2(clk,rst,v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2]);
pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(32), .STAGE(3)) s3(clk,rst,v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3]);
pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(16), .STAGE(4)) s4(clk,rst,v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4]);
pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(8),  .STAGE(5)) s5(clk,rst,v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5]);
pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(4),  .STAGE(6)) s6(clk,rst,v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6]);
pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(2),  .STAGE(7)) s7(clk,rst,v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7]);
pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(1),  .STAGE(8)) s8(clk,rst,v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8]);
pfft_stage9_no_exchange_v3 s9(clk,rst,v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8],v[9],l[9],r0[9],i0[9],r1[9],i1[9],r2[9],i2[9],r3[9],i3[9]);
pfft_stage10 s10(clk,rst,v[9],l[9],r0[9],i0[9],r1[9],i1[9],r2[9],i2[9],r3[9],i3[9],v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10]);
assign out_valid=v[10];assign out_last=l[10];
assign out0_re=r0[10];assign out0_im=i0[10];assign out1_re=r1[10];assign out1_im=i1[10];
assign out2_re=r2[10];assign out2_im=i2[10];assign out3_re=r3[10];assign out3_im=i3[10];
endmodule

(* keep_hierarchy = "yes" *) module p0_pfft_no_exchange_core_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed [34:0] in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed [34:0] out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire core_valid,core_last;
wire signed [34:0] c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i;
p0_pfft_no_exchange_pipeline_v3 core(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 core_valid,core_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i);
pfft_frame_pair_buffer_v5 buffer(clk,rst,core_valid,core_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,
 out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);
endmodule

module top_p0_pfft_unprotected(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
p0_pfft_no_exchange_core_v3 u(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);
endmodule
