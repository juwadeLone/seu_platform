`timescale 1ns/1ps

// P2 owns its complete-stage TMR wrappers.  Each replica uses the canonical
// no-exchange PFFT primitive; only vote35 is a shared low-level primitive.
(* keep_hierarchy = "yes" *) module p2_tmr_pfft_stage4_no_exchange_v3 #(
 parameter integer DEPTH=128,parameter integer STAGE=1
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;
wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];
genvar g;
generate for(g=0;g<3;g=g+1)begin:rep
 (* keep = "true" *) pfft_stage4_sdf_no_exchange_v3 #(.DEPTH(DEPTH),.STAGE(STAGE))u(
  clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
  v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]
 );
end endgenerate
vote35 q0r(r0[0],r0[1],r0[2],out0_re);vote35 q0i(i0[0],i0[1],i0[2],out0_im);
vote35 q1r(r1[0],r1[1],r1[2],out1_re);vote35 q1i(i1[0],i1[1],i1[2],out1_im);
vote35 q2r(r2[0],r2[1],r2[2],out2_re);vote35 q2i(i2[0],i2[1],i2[2],out2_im);
vote35 q3r(r3[0],r3[1],r3[2],out3_re);vote35 q3i(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);
assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule


(* keep_hierarchy = "yes" *) module p2_tmr_pfft_stage9_no_exchange_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;
wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];
genvar g;
generate for(g=0;g<3;g=g+1)begin:rep
 (* keep = "true" *) pfft_stage9_no_exchange_v3 u(
  clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
  v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]
 );
end endgenerate
vote35 q0r(r0[0],r0[1],r0[2],out0_re);vote35 q0i(i0[0],i0[1],i0[2],out0_im);
vote35 q1r(r1[0],r1[1],r1[2],out1_re);vote35 q1i(i1[0],i1[1],i1[2],out1_im);
vote35 q2r(r2[0],r2[1],r2[2],out2_re);vote35 q2i(i2[0],i2[1],i2[2],out2_im);
vote35 q3r(r3[0],r3[1],r3[2],out3_re);vote35 q3i(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);
assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule


(* keep_hierarchy = "yes" *) module p2_tmr_pfft_stage10_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;
wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];
genvar g;
generate for(g=0;g<3;g=g+1)begin:rep
 (* keep = "true" *) pfft_stage10 u(
  clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
  v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]
 );
end endgenerate
vote35 q0r(r0[0],r0[1],r0[2],out0_re);vote35 q0i(i0[0],i0[1],i0[2],out0_im);
vote35 q1r(r1[0],r1[1],r1[2],out1_re);vote35 q1i(i1[0],i1[1],i1[2],out1_im);
vote35 q2r(r2[0],r2[1],r2[2],out2_re);vote35 q2i(i2[0],i2[1],i2[2],out2_im);
vote35 q3r(r3[0],r3[1],r3[2],out3_re);vote35 q3i(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);
assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule


(* keep_hierarchy = "yes" *) module p2_pfft_tmr_no_exchange_core_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[11:0]v,l;wire signed[34:0]r0[0:11],i0[0:11],r1[0:11],i1[0:11],r2[0:11],i2[0:11],r3[0:11],i3[0:11];
assign v[0]=in_valid;assign l[0]=in_last;assign r0[0]=in0_re;assign i0[0]=in0_im;assign r1[0]=in1_re;assign i1[0]=in1_im;assign r2[0]=in2_re;assign i2[0]=in2_im;assign r3[0]=in3_re;assign i3[0]=in3_im;
p2_tmr_pfft_stage4_no_exchange_v3 #(.DEPTH(128),.STAGE(1))s1(clk,rst,v[0],l[0],r0[0],i0[0],r1[0],i1[0],r2[0],i2[0],r3[0],i3[0],v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1]);
p2_tmr_pfft_stage4_no_exchange_v3 #(.DEPTH(64),.STAGE(2))s2(clk,rst,v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2]);
p2_tmr_pfft_stage4_no_exchange_v3 #(.DEPTH(32),.STAGE(3))s3(clk,rst,v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3]);
p2_tmr_pfft_stage4_no_exchange_v3 #(.DEPTH(16),.STAGE(4))s4(clk,rst,v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4]);
p2_tmr_pfft_stage4_no_exchange_v3 #(.DEPTH(8),.STAGE(5))s5(clk,rst,v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5]);
p2_tmr_pfft_stage4_no_exchange_v3 #(.DEPTH(4),.STAGE(6))s6(clk,rst,v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6]);
p2_tmr_pfft_stage4_no_exchange_v3 #(.DEPTH(2),.STAGE(7))s7(clk,rst,v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7]);
p2_tmr_pfft_stage4_no_exchange_v3 #(.DEPTH(1),.STAGE(8))s8(clk,rst,v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8]);
p2_tmr_pfft_stage9_no_exchange_v3 s9(clk,rst,v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8],v[9],l[9],r0[9],i0[9],r1[9],i1[9],r2[9],i2[9],r3[9],i3[9]);
p2_tmr_pfft_stage10_v3 s10(clk,rst,v[9],l[9],r0[9],i0[9],r1[9],i1[9],r2[9],i2[9],r3[9],i3[9],v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10]);
pfft_frame_pair_buffer_v5 buffer(clk,rst,v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10],v[11],l[11],r0[11],i0[11],r1[11],i1[11],r2[11],i2[11],r3[11],i3[11]);
assign out_valid=v[11];assign out_last=l[11];assign out0_re=r0[11];assign out0_im=i0[11];assign out1_re=r1[11];assign out1_im=i1[11];assign out2_re=r2[11];assign out2_im=i2[11];assign out3_re=r3[11];assign out3_im=i3[11];
endmodule

module top_p2_pfft_tmr(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
p2_pfft_tmr_no_exchange_core_v3 u(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);
endmodule
