`timescale 1ns/1ps
// N08-only wrapper.  Existing stage RTL is reused unchanged; this added top
// gives each eligible stage an independent one-cycle injection hook.
module n08_s3_multifault_core #(
 parameter integer THRESHOLD = 2
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 input wire [7:0] inject_enable,
 input wire [23:0] inject_symbol,
 input wire [7:0] inject_component,
 input wire [47:0] inject_bit,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 output wire [7:0] up_detected,up_corrected,up_uncorrectable,
 output wire [23:0] up_error_location
);
wire[10:0]v,l;
wire signed[34:0]r0[0:10],i0[0:10],r1[0:10],i1[0:10],r2[0:10],i2[0:10],r3[0:10],i3[0:10];
wire [7:0] up_misc_unused,lo_det_unused,lo_cor_unused,lo_unc_unused,lo_misc_unused;
wire [23:0] lo_loc_unused;
assign v[0]=in_valid;assign l[0]=in_last;
assign r0[0]=in0_re;assign i0[0]=in0_im;assign r1[0]=in1_re;assign i1[0]=in1_im;
assign r2[0]=in2_re;assign i2[0]=in2_im;assign r3[0]=in3_re;assign i3[0]=in3_im;

ecc_stage4_v5_thresholded #(.DEPTH(128),.STAGE(1),.PFFT_MODE(0),.THRESHOLD(THRESHOLD)) s1(
 clk,rst,v[0],l[0],r0[0],i0[0],r1[0],i1[0],r2[0],i2[0],r3[0],i3[0],
 inject_enable[0],inject_symbol[2:0],inject_component[0],inject_bit[5:0],
 v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],
 up_detected[0],up_corrected[0],up_uncorrectable[0],up_misc_unused[0],up_error_location[2:0],
 lo_det_unused[0],lo_cor_unused[0],lo_unc_unused[0],lo_misc_unused[0],lo_loc_unused[2:0]);
ecc_stage4_v5_thresholded #(.DEPTH(64),.STAGE(2),.PFFT_MODE(0),.THRESHOLD(THRESHOLD)) s2(
 clk,rst,v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],
 inject_enable[1],inject_symbol[5:3],inject_component[1],inject_bit[11:6],
 v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],
 up_detected[1],up_corrected[1],up_uncorrectable[1],up_misc_unused[1],up_error_location[5:3],
 lo_det_unused[1],lo_cor_unused[1],lo_unc_unused[1],lo_misc_unused[1],lo_loc_unused[5:3]);
ecc_stage4_v5_thresholded #(.DEPTH(32),.STAGE(3),.PFFT_MODE(0),.THRESHOLD(THRESHOLD)) s3(
 clk,rst,v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],
 inject_enable[2],inject_symbol[8:6],inject_component[2],inject_bit[17:12],
 v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],
 up_detected[2],up_corrected[2],up_uncorrectable[2],up_misc_unused[2],up_error_location[8:6],
 lo_det_unused[2],lo_cor_unused[2],lo_unc_unused[2],lo_misc_unused[2],lo_loc_unused[8:6]);
ecc_stage4_v5_thresholded #(.DEPTH(16),.STAGE(4),.PFFT_MODE(0),.THRESHOLD(THRESHOLD)) s4(
 clk,rst,v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],
 inject_enable[3],inject_symbol[11:9],inject_component[3],inject_bit[23:18],
 v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],
 up_detected[3],up_corrected[3],up_uncorrectable[3],up_misc_unused[3],up_error_location[11:9],
 lo_det_unused[3],lo_cor_unused[3],lo_unc_unused[3],lo_misc_unused[3],lo_loc_unused[11:9]);
ecc_stage4_v5_thresholded #(.DEPTH(8),.STAGE(5),.PFFT_MODE(0),.THRESHOLD(THRESHOLD)) s5(
 clk,rst,v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],
 inject_enable[4],inject_symbol[14:12],inject_component[4],inject_bit[29:24],
 v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],
 up_detected[4],up_corrected[4],up_uncorrectable[4],up_misc_unused[4],up_error_location[14:12],
 lo_det_unused[4],lo_cor_unused[4],lo_unc_unused[4],lo_misc_unused[4],lo_loc_unused[14:12]);
ecc_stage4_v5_thresholded #(.DEPTH(4),.STAGE(6),.PFFT_MODE(0),.THRESHOLD(THRESHOLD)) s6(
 clk,rst,v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],
 inject_enable[5],inject_symbol[17:15],inject_component[5],inject_bit[35:30],
 v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],
 up_detected[5],up_corrected[5],up_uncorrectable[5],up_misc_unused[5],up_error_location[17:15],
 lo_det_unused[5],lo_cor_unused[5],lo_unc_unused[5],lo_misc_unused[5],lo_loc_unused[17:15]);
ecc_stage4_v5_thresholded #(.DEPTH(2),.STAGE(7),.PFFT_MODE(0),.THRESHOLD(THRESHOLD)) s7(
 clk,rst,v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],
 inject_enable[6],inject_symbol[20:18],inject_component[6],inject_bit[41:36],
 v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],
 up_detected[6],up_corrected[6],up_uncorrectable[6],up_misc_unused[6],up_error_location[20:18],
 lo_det_unused[6],lo_cor_unused[6],lo_unc_unused[6],lo_misc_unused[6],lo_loc_unused[20:18]);
ecc_stage4_v5_thresholded #(.DEPTH(1),.STAGE(8),.PFFT_MODE(0),.THRESHOLD(THRESHOLD)) s8(
 clk,rst,v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],
 inject_enable[7],inject_symbol[23:21],inject_component[7],inject_bit[47:42],
 v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8],
 up_detected[7],up_corrected[7],up_uncorrectable[7],up_misc_unused[7],up_error_location[23:21],
 lo_det_unused[7],lo_cor_unused[7],lo_unc_unused[7],lo_misc_unused[7],lo_loc_unused[23:21]);
tmr_subfft_stage9_v5 s9(clk,rst,v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8],v[9],l[9],r0[9],i0[9],r1[9],i1[9],r2[9],i2[9],r3[9],i3[9]);
tmr_subfft_stage10_v5 s10(clk,rst,v[9],l[9],r0[9],i0[9],r1[9],i1[9],r2[9],i2[9],r3[9],i3[9],v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10]);
assign out_valid=v[10];assign out_last=l[10];
assign out0_re=r0[10];assign out0_im=i0[10];assign out1_re=r1[10];assign out1_im=i1[10];
assign out2_re=r2[10];assign out2_im=i2[10];assign out3_re=r3[10];assign out3_im=i3[10];
endmodule

module n08_s3_multifault_top #(
 parameter integer THRESHOLD = 2
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 input wire [7:0] inject_enable,input wire [23:0] inject_symbol,
 input wire [7:0] inject_component,input wire [47:0] inject_bit,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 output wire [7:0] up_detected,up_corrected,up_uncorrectable,
 output wire [23:0] up_error_location
);
n08_s3_multifault_core #(.THRESHOLD(THRESHOLD)) u(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 inject_enable,inject_symbol,inject_component,inject_bit,
 out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 up_detected,up_corrected,up_uncorrectable,up_error_location);
endmodule
