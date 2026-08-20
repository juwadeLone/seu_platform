`timescale 1ns/1ps

// ============================================================================
// SC-01: Gao-threshold version of the S3 (per-stage ECC) SubFFT top (added
// 2026-08-10). Stages 1-8 use ecc_stage4_v5_thresholded; stages 9-10 keep
// the original TMR stages. The fault-injection hook (inject_enable/
// inject_symbol/inject_component/inject_bit) is passed to every ECC stage and
// the upper-boundary corrector flags of stages 1-8 are exposed for the
// testbench four-class classification.
// ============================================================================
module subfft_ecc_core_v5_thresholded #(
 parameter integer THRESHOLD = 0
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 input wire inject_enable,
 input wire [2:0]inject_symbol,
 input wire inject_component,
 input wire [5:0]inject_bit,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 output wire up_detected0,up_corrected0,up_uncorrectable0,output wire[2:0]up_error_location0,
 output wire up_detected1,up_corrected1,up_uncorrectable1,output wire[2:0]up_error_location1,
 output wire up_detected2,up_corrected2,up_uncorrectable2,output wire[2:0]up_error_location2,
 output wire up_detected3,up_corrected3,up_uncorrectable3,output wire[2:0]up_error_location3,
 output wire up_detected4,up_corrected4,up_uncorrectable4,output wire[2:0]up_error_location4,
 output wire up_detected5,up_corrected5,up_uncorrectable5,output wire[2:0]up_error_location5,
 output wire up_detected6,up_corrected6,up_uncorrectable6,output wire[2:0]up_error_location6,
 output wire up_detected7,up_corrected7,up_uncorrectable7,output wire[2:0]up_error_location7
);
wire[10:0]v,l;wire signed[34:0]r0[0:10],i0[0:10],r1[0:10],i1[0:10],r2[0:10],i2[0:10],r3[0:10],i3[0:10];
wire up_miscorrected_unused0,lo_detected_unused0,lo_corrected_unused0,lo_uncorrectable_unused0,lo_miscorrected_unused0;wire[2:0]lo_error_location_unused0;
wire up_miscorrected_unused1,lo_detected_unused1,lo_corrected_unused1,lo_uncorrectable_unused1,lo_miscorrected_unused1;wire[2:0]lo_error_location_unused1;
wire up_miscorrected_unused2,lo_detected_unused2,lo_corrected_unused2,lo_uncorrectable_unused2,lo_miscorrected_unused2;wire[2:0]lo_error_location_unused2;
wire up_miscorrected_unused3,lo_detected_unused3,lo_corrected_unused3,lo_uncorrectable_unused3,lo_miscorrected_unused3;wire[2:0]lo_error_location_unused3;
wire up_miscorrected_unused4,lo_detected_unused4,lo_corrected_unused4,lo_uncorrectable_unused4,lo_miscorrected_unused4;wire[2:0]lo_error_location_unused4;
wire up_miscorrected_unused5,lo_detected_unused5,lo_corrected_unused5,lo_uncorrectable_unused5,lo_miscorrected_unused5;wire[2:0]lo_error_location_unused5;
wire up_miscorrected_unused6,lo_detected_unused6,lo_corrected_unused6,lo_uncorrectable_unused6,lo_miscorrected_unused6;wire[2:0]lo_error_location_unused6;
wire up_miscorrected_unused7,lo_detected_unused7,lo_corrected_unused7,lo_uncorrectable_unused7,lo_miscorrected_unused7;wire[2:0]lo_error_location_unused7;
assign v[0]=in_valid;assign l[0]=in_last;assign r0[0]=in0_re;assign i0[0]=in0_im;assign r1[0]=in1_re;assign i1[0]=in1_im;assign r2[0]=in2_re;assign i2[0]=in2_im;assign r3[0]=in3_re;assign i3[0]=in3_im;
ecc_stage4_v5_thresholded #(.DEPTH(128),.STAGE(1),.PFFT_MODE(0),.THRESHOLD(THRESHOLD))s1(
 clk,rst,v[0],l[0],r0[0],i0[0],r1[0],i1[0],r2[0],i2[0],r3[0],i3[0],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],
 up_detected0,up_corrected0,up_uncorrectable0,up_miscorrected_unused0,up_error_location0,
 lo_detected_unused0,lo_corrected_unused0,lo_uncorrectable_unused0,lo_miscorrected_unused0,lo_error_location_unused0
);
ecc_stage4_v5_thresholded #(.DEPTH(64),.STAGE(2),.PFFT_MODE(0),.THRESHOLD(THRESHOLD))s2(
 clk,rst,v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],
 up_detected1,up_corrected1,up_uncorrectable1,up_miscorrected_unused1,up_error_location1,
 lo_detected_unused1,lo_corrected_unused1,lo_uncorrectable_unused1,lo_miscorrected_unused1,lo_error_location_unused1
);
ecc_stage4_v5_thresholded #(.DEPTH(32),.STAGE(3),.PFFT_MODE(0),.THRESHOLD(THRESHOLD))s3(
 clk,rst,v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],
 up_detected2,up_corrected2,up_uncorrectable2,up_miscorrected_unused2,up_error_location2,
 lo_detected_unused2,lo_corrected_unused2,lo_uncorrectable_unused2,lo_miscorrected_unused2,lo_error_location_unused2
);
ecc_stage4_v5_thresholded #(.DEPTH(16),.STAGE(4),.PFFT_MODE(0),.THRESHOLD(THRESHOLD))s4(
 clk,rst,v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],
 up_detected3,up_corrected3,up_uncorrectable3,up_miscorrected_unused3,up_error_location3,
 lo_detected_unused3,lo_corrected_unused3,lo_uncorrectable_unused3,lo_miscorrected_unused3,lo_error_location_unused3
);
ecc_stage4_v5_thresholded #(.DEPTH(8),.STAGE(5),.PFFT_MODE(0),.THRESHOLD(THRESHOLD))s5(
 clk,rst,v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],
 up_detected4,up_corrected4,up_uncorrectable4,up_miscorrected_unused4,up_error_location4,
 lo_detected_unused4,lo_corrected_unused4,lo_uncorrectable_unused4,lo_miscorrected_unused4,lo_error_location_unused4
);
ecc_stage4_v5_thresholded #(.DEPTH(4),.STAGE(6),.PFFT_MODE(0),.THRESHOLD(THRESHOLD))s6(
 clk,rst,v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],
 up_detected5,up_corrected5,up_uncorrectable5,up_miscorrected_unused5,up_error_location5,
 lo_detected_unused5,lo_corrected_unused5,lo_uncorrectable_unused5,lo_miscorrected_unused5,lo_error_location_unused5
);
ecc_stage4_v5_thresholded #(.DEPTH(2),.STAGE(7),.PFFT_MODE(0),.THRESHOLD(THRESHOLD))s7(
 clk,rst,v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],
 up_detected6,up_corrected6,up_uncorrectable6,up_miscorrected_unused6,up_error_location6,
 lo_detected_unused6,lo_corrected_unused6,lo_uncorrectable_unused6,lo_miscorrected_unused6,lo_error_location_unused6
);
ecc_stage4_v5_thresholded #(.DEPTH(1),.STAGE(8),.PFFT_MODE(0),.THRESHOLD(THRESHOLD))s8(
 clk,rst,v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8],
 up_detected7,up_corrected7,up_uncorrectable7,up_miscorrected_unused7,up_error_location7,
 lo_detected_unused7,lo_corrected_unused7,lo_uncorrectable_unused7,lo_miscorrected_unused7,lo_error_location_unused7
);
tmr_subfft_stage9_v5 s9(clk,rst,v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8],v[9],l[9],r0[9],i0[9],r1[9],i1[9],r2[9],i2[9],r3[9],i3[9]);
tmr_subfft_stage10_v5 s10(clk,rst,v[9],l[9],r0[9],i0[9],r1[9],i1[9],r2[9],i2[9],r3[9],i3[9],v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10]);
assign out_valid=v[10];assign out_last=l[10];assign out0_re=r0[10];assign out0_im=i0[10];assign out1_re=r1[10];assign out1_im=i1[10];assign out2_re=r2[10];assign out2_im=i2[10];assign out3_re=r3[10];assign out3_im=i3[10];
endmodule

module top_s3_subfft_ecc_thresholded #(
 parameter integer THRESHOLD = 0
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 input wire inject_enable,
 input wire [2:0]inject_symbol,
 input wire inject_component,
 input wire [5:0]inject_bit,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 output wire up_detected0,up_corrected0,up_uncorrectable0,output wire[2:0]up_error_location0,
 output wire up_detected1,up_corrected1,up_uncorrectable1,output wire[2:0]up_error_location1,
 output wire up_detected2,up_corrected2,up_uncorrectable2,output wire[2:0]up_error_location2,
 output wire up_detected3,up_corrected3,up_uncorrectable3,output wire[2:0]up_error_location3,
 output wire up_detected4,up_corrected4,up_uncorrectable4,output wire[2:0]up_error_location4,
 output wire up_detected5,up_corrected5,up_uncorrectable5,output wire[2:0]up_error_location5,
 output wire up_detected6,up_corrected6,up_uncorrectable6,output wire[2:0]up_error_location6,
 output wire up_detected7,up_corrected7,up_uncorrectable7,output wire[2:0]up_error_location7
);
subfft_ecc_core_v5_thresholded #(.THRESHOLD(THRESHOLD)) u(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 inject_enable,inject_symbol,inject_component,inject_bit,
 out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 up_detected0,up_corrected0,up_uncorrectable0,up_error_location0,
 up_detected1,up_corrected1,up_uncorrectable1,up_error_location1,
 up_detected2,up_corrected2,up_uncorrectable2,up_error_location2,
 up_detected3,up_corrected3,up_uncorrectable3,up_error_location3,
 up_detected4,up_corrected4,up_uncorrectable4,up_error_location4,
 up_detected5,up_corrected5,up_uncorrectable5,up_error_location5,
 up_detected6,up_corrected6,up_uncorrectable6,up_error_location6,
 up_detected7,up_corrected7,up_uncorrectable7,up_error_location7
);
endmodule
