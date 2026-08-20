`timescale 1ns/1ps

module ecc_stage4_v5 #(
 parameter integer DEPTH=128,
 parameter integer STAGE=1,
 parameter integer PFFT_MODE=0
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output reg out_valid,output reg out_last,
 output reg signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
localparam integer PHASE_W=(2*DEPTH<=2)?1:$clog2(2*DEPTH);
localparam integer ADDR_W=(DEPTH<=1)?1:$clog2(DEPTH);
localparam integer STRIDE=256/(2*DEPTH);
localparam integer SYNC_READ=(DEPTH==128);
localparam integer HETEROGENEOUS_STAGE8=(PFFT_MODE!=0)&&(STAGE==8);
reg[PHASE_W-1:0]phase;reg primed;reg[7:0]out_count;
wire phase_second=(phase>=DEPTH);
wire[ADDR_W-1:0]current_address=phase_second?phase-DEPTH:phase;

reg request_valid,request_second,request_primed;reg[ADDR_W-1:0]request_address;
reg signed[34:0]q0r,q0i,q1r,q1i,q2r,q2i,q3r,q3i;
wire work_valid=SYNC_READ?request_valid:in_valid;
wire work_second=SYNC_READ?request_second:phase_second;
wire work_primed=SYNC_READ?request_primed:primed;
wire[ADDR_W-1:0]work_address=SYNC_READ?request_address:current_address;
wire signed[34:0]b0r=SYNC_READ?q0r:in0_re,b0i=SYNC_READ?q0i:in0_im;
wire signed[34:0]b1r=SYNC_READ?q1r:in1_re,b1i=SYNC_READ?q1i:in1_im;
wire signed[34:0]b2r=SYNC_READ?q2r:in2_re,b2i=SYNC_READ?q2i:in2_im;
wire signed[34:0]b3r=SYNC_READ?q3r:in3_re,b3i=SYNC_READ?q3i:in3_im;

wire[77:0]mcode0,mcode1,mcode2,mcode3;
wire[69:0]mdata0,mdata1,mdata2,mdata3;wire[3:0]mem_detected,mem_corrected;
secded_decode70 dec0(mcode0,mdata0,mem_detected[0],mem_corrected[0]);
secded_decode70 dec1(mcode1,mdata1,mem_detected[1],mem_corrected[1]);
secded_decode70 dec2(mcode2,mdata2,mem_detected[2],mem_corrected[2]);
secded_decode70 dec3(mcode3,mdata3,mem_detected[3],mem_corrected[3]);
wire signed[34:0]a0r=mdata0[69:35],a0i=mdata0[34:0],a1r=mdata1[69:35],a1i=mdata1[34:0];
wire signed[34:0]a2r=mdata2[69:35],a2i=mdata2[34:0],a3r=mdata3[69:35],a3i=mdata3[34:0];
wire[9:0]sub_lower_exponent=(work_address*STRIDE)<<2;
wire[9:0]p_exponent;
pfft_phi_calc #(.STAGE(STAGE)) phi_group({out_count,2'd0},p_exponent);
wire[9:0]upper_exponent=PFFT_MODE?p_exponent:10'd0;
wire[9:0]lower_exponent=PFFT_MODE?10'd0:sub_lower_exponent;
wire signed[34:0]u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i;
independent_butterfly_ecc_v5 #(
 .TRIVIAL_UPPER((PFFT_MODE!=0)&&(STAGE==1)),
 .BYPASS_LOWER(PFFT_MODE!=0),
 .SUBFFT_SINGLE_ROTATION(PFFT_MODE==0)
) protected_butterfly(
 a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,b0r,b0i,b1r,b1i,b2r,b2i,b3r,b3i,
 upper_exponent,lower_exponent,u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i
);
wire signed[34:0]rot0r,rot0i,rot1r,rot1i,rot2r,rot2i,rot3r,rot3i;
generate
 if(PFFT_MODE!=0)begin:with_pfft_feedback_rotation
  independent_rotation_ecc_v5 #(
   .TRIVIAL_ROTATION(STAGE==1)
  ) protected_feedback_rotation(
   a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,p_exponent,
   rot0r,rot0i,rot1r,rot1i,rot2r,rot2i,rot3r,rot3i
  );
 end else begin:without_subfft_feedback_rotation
  assign rot0r=0;assign rot0i=0;assign rot1r=0;assign rot1i=0;
  assign rot2r=0;assign rot2i=0;assign rot3r=0;assign rot3i=0;
 end
endgenerate

// Stage 8 has heterogeneous per-lane exponents.  Its functional path remains
// exact here; the adjacent-frame group checker is implemented after Stage 8.
wire signed[34:0]raw_sum0r=a0r+b0r,raw_sum0i=a0i+b0i,raw_diff0r=a0r-b0r,raw_diff0i=a0i-b0i;
wire signed[34:0]raw_sum1r=a1r+b1r,raw_sum1i=a1i+b1i,raw_diff1r=a1r-b1r,raw_diff1i=a1i-b1i;
wire signed[34:0]raw_sum2r=a2r+b2r,raw_sum2i=a2i+b2i,raw_diff2r=a2r-b2r,raw_diff2i=a2i-b2i;
wire signed[34:0]raw_sum3r=a3r+b3r,raw_sum3i=a3i+b3i,raw_diff3r=a3r-b3r,raw_diff3i=a3i-b3i;
wire signed[34:0]raw_upper0r=raw_sum0r>>>1,raw_upper0i=raw_sum0i>>>1,raw_lower0r=raw_diff0r>>>1,raw_lower0i=raw_diff0i>>>1;
wire signed[34:0]raw_upper1r=raw_sum1r>>>1,raw_upper1i=raw_sum1i>>>1,raw_lower1r=raw_diff1r>>>1,raw_lower1i=raw_diff1i>>>1;
wire signed[34:0]raw_upper2r=raw_sum2r>>>1,raw_upper2i=raw_sum2i>>>1,raw_lower2r=raw_diff2r>>>1,raw_lower2i=raw_diff2i>>>1;
wire signed[34:0]raw_upper3r=raw_sum3r>>>1,raw_upper3i=raw_sum3i>>>1,raw_lower3r=raw_diff3r>>>1,raw_lower3i=raw_diff3i>>>1;
wire[9:0]lane_exp0,lane_exp1,lane_exp2,lane_exp3;
pfft_phi_calc #(.STAGE(STAGE)) phi0({out_count,2'd0},lane_exp0);
pfft_phi_calc #(.STAGE(STAGE)) phi1({out_count,2'd1},lane_exp1);
pfft_phi_calc #(.STAGE(STAGE)) phi2({out_count,2'd2},lane_exp2);
pfft_phi_calc #(.STAGE(STAGE)) phi3({out_count,2'd3},lane_exp3);
wire signed[34:0]hetero_upper0r,hetero_upper0i,hetero_upper1r,hetero_upper1i,hetero_upper2r,hetero_upper2i,hetero_upper3r,hetero_upper3i;
wire signed[34:0]hetero_feedback0r,hetero_feedback0i,hetero_feedback1r,hetero_feedback1i,hetero_feedback2r,hetero_feedback2i,hetero_feedback3r,hetero_feedback3i;
fft_complex_mul_q28 hm0u(raw_upper0r,raw_upper0i,lane_exp0,hetero_upper0r,hetero_upper0i);
fft_complex_mul_q28 hm1u(raw_upper1r,raw_upper1i,lane_exp1,hetero_upper1r,hetero_upper1i);
fft_complex_mul_q28 hm2u(raw_upper2r,raw_upper2i,lane_exp2,hetero_upper2r,hetero_upper2i);
fft_complex_mul_q28 hm3u(raw_upper3r,raw_upper3i,lane_exp3,hetero_upper3r,hetero_upper3i);
fft_complex_mul_q28 hm0f(a0r,a0i,lane_exp0,hetero_feedback0r,hetero_feedback0i);
fft_complex_mul_q28 hm1f(a1r,a1i,lane_exp1,hetero_feedback1r,hetero_feedback1i);
fft_complex_mul_q28 hm2f(a2r,a2i,lane_exp2,hetero_feedback2r,hetero_feedback2i);
fft_complex_mul_q28 hm3f(a3r,a3i,lane_exp3,hetero_feedback3r,hetero_feedback3i);

wire signed[34:0]candidate0r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper0r:u0r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback0r:rot0r):a0r);
wire signed[34:0]candidate0i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper0i:u0i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback0i:rot0i):a0i);
wire signed[34:0]candidate1r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper1r:u1r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback1r:rot1r):a1r);
wire signed[34:0]candidate1i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper1i:u1i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback1i:rot1i):a1i);
wire signed[34:0]candidate2r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper2r:u2r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback2r:rot2r):a2r);
wire signed[34:0]candidate2i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper2i:u2i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback2i:rot2i):a2i);
wire signed[34:0]candidate3r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper3r:u3r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback3r:rot3r):a3r);
wire signed[34:0]candidate3i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper3i:u3i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback3i:rot3i):a3i);
wire candidate_valid=work_second||((!work_second)&&work_primed);
wire signed[34:0]store0r=work_second?(HETEROGENEOUS_STAGE8?raw_lower0r:l0r):b0r,store0i=work_second?(HETEROGENEOUS_STAGE8?raw_lower0i:l0i):b0i;
wire signed[34:0]store1r=work_second?(HETEROGENEOUS_STAGE8?raw_lower1r:l1r):b1r,store1i=work_second?(HETEROGENEOUS_STAGE8?raw_lower1i:l1i):b1i;
wire signed[34:0]store2r=work_second?(HETEROGENEOUS_STAGE8?raw_lower2r:l2r):b2r,store2i=work_second?(HETEROGENEOUS_STAGE8?raw_lower2i:l2i):b2i;
wire signed[34:0]store3r=work_second?(HETEROGENEOUS_STAGE8?raw_lower3r:l3r):b3r,store3i=work_second?(HETEROGENEOUS_STAGE8?raw_lower3i:l3i):b3i;
wire[77:0]store_code0,store_code1,store_code2,store_code3;
secded_encode70 enc0({store0r,store0i},store_code0);secded_encode70 enc1({store1r,store1i},store_code1);
secded_encode70 enc2({store2r,store2i},store_code2);secded_encode70 enc3({store3r,store3i},store_code3);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem0(clk,in_valid,current_address,mcode0,work_valid,work_address,store_code0);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem1(clk,in_valid,current_address,mcode1,work_valid,work_address,store_code1);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem2(clk,in_valid,current_address,mcode2,work_valid,work_address,store_code2);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem3(clk,in_valid,current_address,mcode3,work_valid,work_address,store_code3);

always@(posedge clk)begin
 if(rst)begin phase<=0;primed<=0;out_count<=0;request_valid<=0;request_second<=0;request_primed<=0;request_address<=0;
  q0r<=0;q0i<=0;q1r<=0;q1i<=0;q2r<=0;q2i<=0;q3r<=0;q3i<=0;out_valid<=0;out_last<=0;
  out0_re<=0;out0_im<=0;out1_re<=0;out1_im<=0;out2_re<=0;out2_im<=0;out3_re<=0;out3_im<=0;
 end else begin
  request_valid<=SYNC_READ?in_valid:1'b0;
  if(SYNC_READ&&in_valid)begin request_second<=phase_second;request_primed<=primed;request_address<=current_address;
   q0r<=in0_re;q0i<=in0_im;q1r<=in1_re;q1i<=in1_im;q2r<=in2_re;q2i<=in2_im;q3r<=in3_re;q3i<=in3_im;end
  if(in_valid)begin if(phase==(2*DEPTH-1))begin phase<=0;primed<=1;end else phase<=phase+1'b1;end
  out_valid<=0;out_last<=0;
  if(work_valid&&candidate_valid)begin out_valid<=1;out_last<=(out_count==8'd255);out_count<=out_count+1'b1;
   out0_re<=candidate0r;out0_im<=candidate0i;out1_re<=candidate1r;out1_im<=candidate1i;
   out2_re<=candidate2r;out2_im<=candidate2i;out3_re<=candidate3r;out3_im<=candidate3i;end
 end
end
wire _keep=^mem_detected^mem_corrected^in_last;
endmodule


(* keep_hierarchy = "yes" *) module tmr_subfft_stage4_v5 #(
 parameter integer DEPTH=128,parameter integer STAGE=1
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];genvar g;
generate for(g=0;g<3;g=g+1)begin:rep
 (* keep = "true" *) subfft_stage4_sdf_v5 #(.DEPTH(DEPTH),.STAGE(STAGE))u(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]);
end endgenerate
vote35 q0r(r0[0],r0[1],r0[2],out0_re);vote35 q0i(i0[0],i0[1],i0[2],out0_im);vote35 q1r(r1[0],r1[1],r1[2],out1_re);vote35 q1i(i1[0],i1[1],i1[2],out1_im);
vote35 q2r(r2[0],r2[1],r2[2],out2_re);vote35 q2i(i2[0],i2[1],i2[2],out2_im);vote35 q3r(r3[0],r3[1],r3[2],out3_re);vote35 q3i(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule

(* keep_hierarchy = "yes" *) module tmr_pfft_stage4_v5 #(
 parameter integer DEPTH=128,parameter integer STAGE=1
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];genvar g;
generate for(g=0;g<3;g=g+1)begin:rep
 (* keep = "true" *) pfft_stage4_sdf_v5 #(.DEPTH(DEPTH),.STAGE(STAGE))u(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]);
end endgenerate
vote35 q0r(r0[0],r0[1],r0[2],out0_re);vote35 q0i(i0[0],i0[1],i0[2],out0_im);vote35 q1r(r1[0],r1[1],r1[2],out1_re);vote35 q1i(i1[0],i1[1],i1[2],out1_im);
vote35 q2r(r2[0],r2[1],r2[2],out2_re);vote35 q2i(i2[0],i2[1],i2[2],out2_im);vote35 q3r(r3[0],r3[1],r3[2],out3_re);vote35 q3i(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule

(* keep_hierarchy = "yes" *) module tmr_subfft_stage9_v5(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];genvar g;
generate for(g=0;g<3;g=g+1)begin:rep (* keep = "true" *) subfft_stage9 u(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]);end endgenerate
vote35 a0(r0[0],r0[1],r0[2],out0_re);vote35 b0(i0[0],i0[1],i0[2],out0_im);vote35 a1(r1[0],r1[1],r1[2],out1_re);vote35 b1(i1[0],i1[1],i1[2],out1_im);vote35 a2(r2[0],r2[1],r2[2],out2_re);vote35 b2(i2[0],i2[1],i2[2],out2_im);vote35 a3(r3[0],r3[1],r3[2],out3_re);vote35 b3(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule

(* keep_hierarchy = "yes" *) module tmr_subfft_stage10_v5(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];genvar g;
generate for(g=0;g<3;g=g+1)begin:rep (* keep = "true" *) subfft_stage10 u(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]);end endgenerate
vote35 a0(r0[0],r0[1],r0[2],out0_re);vote35 b0(i0[0],i0[1],i0[2],out0_im);vote35 a1(r1[0],r1[1],r1[2],out1_re);vote35 b1(i1[0],i1[1],i1[2],out1_im);vote35 a2(r2[0],r2[1],r2[2],out2_re);vote35 b2(i2[0],i2[1],i2[2],out2_im);vote35 a3(r3[0],r3[1],r3[2],out3_re);vote35 b3(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule

(* keep_hierarchy = "yes" *) module tmr_pfft_stage9_v5(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];genvar g;
generate for(g=0;g<3;g=g+1)begin:rep (* keep = "true" *) pfft_stage9 u(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]);end endgenerate
vote35 a0(r0[0],r0[1],r0[2],out0_re);vote35 b0(i0[0],i0[1],i0[2],out0_im);vote35 a1(r1[0],r1[1],r1[2],out1_re);vote35 b1(i1[0],i1[1],i1[2],out1_im);vote35 a2(r2[0],r2[1],r2[2],out2_re);vote35 b2(i2[0],i2[1],i2[2],out2_im);vote35 a3(r3[0],r3[1],r3[2],out3_re);vote35 b3(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule

(* keep_hierarchy = "yes" *) module tmr_pfft_stage10_v5(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];genvar g;
generate for(g=0;g<3;g=g+1)begin:rep (* keep = "true" *) pfft_stage10 u(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,v[g],l[g],r0[g],i0[g],r1[g],i1[g],r2[g],i2[g],r3[g],i3[g]);end endgenerate
vote35 a0(r0[0],r0[1],r0[2],out0_re);vote35 b0(i0[0],i0[1],i0[2],out0_im);vote35 a1(r1[0],r1[1],r1[2],out1_re);vote35 b1(i1[0],i1[1],i1[2],out1_im);vote35 a2(r2[0],r2[1],r2[2],out2_re);vote35 b2(i2[0],i2[1],i2[2],out2_im);vote35 a3(r3[0],r3[1],r3[2],out3_re);vote35 b3(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule

// ============================================================================
// SC-01: Gao-threshold version of ecc_stage4_v5 (added 2026-08-10).
// Uses independent_butterfly_ecc_v5_thresholded (THRESHOLD parameter), passes
// the fault-injection hook through, and exposes the upper/lower boundary
// corrector flags for testbench classification.
// ============================================================================
module ecc_stage4_v5_thresholded #(
 parameter integer DEPTH=128,
 parameter integer STAGE=1,
 parameter integer PFFT_MODE=0,
 parameter integer THRESHOLD=0
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 input wire inject_enable,
 input wire [2:0]inject_symbol,
 input wire inject_component,
 input wire [5:0]inject_bit,
 output reg out_valid,output reg out_last,
 output reg signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 output wire up_detected,up_corrected,up_uncorrectable,up_miscorrected,output wire[2:0]up_error_location,
 output wire lo_detected,lo_corrected,lo_uncorrectable,lo_miscorrected,output wire[2:0]lo_error_location
);
localparam integer PHASE_W=(2*DEPTH<=2)?1:$clog2(2*DEPTH);
localparam integer ADDR_W=(DEPTH<=1)?1:$clog2(DEPTH);
localparam integer STRIDE=256/(2*DEPTH);
localparam integer SYNC_READ=(DEPTH==128);
localparam integer HETEROGENEOUS_STAGE8=(PFFT_MODE!=0)&&(STAGE==8);
reg[PHASE_W-1:0]phase;reg primed;reg[7:0]out_count;
wire phase_second=(phase>=DEPTH);
wire[ADDR_W-1:0]current_address=phase_second?phase-DEPTH:phase;

reg request_valid,request_second,request_primed;reg[ADDR_W-1:0]request_address;
reg signed[34:0]q0r,q0i,q1r,q1i,q2r,q2i,q3r,q3i;
wire work_valid=SYNC_READ?request_valid:in_valid;
wire work_second=SYNC_READ?request_second:phase_second;
wire work_primed=SYNC_READ?request_primed:primed;
wire[ADDR_W-1:0]work_address=SYNC_READ?request_address:current_address;
wire signed[34:0]b0r=SYNC_READ?q0r:in0_re,b0i=SYNC_READ?q0i:in0_im;
wire signed[34:0]b1r=SYNC_READ?q1r:in1_re,b1i=SYNC_READ?q1i:in1_im;
wire signed[34:0]b2r=SYNC_READ?q2r:in2_re,b2i=SYNC_READ?q2i:in2_im;
wire signed[34:0]b3r=SYNC_READ?q3r:in3_re,b3i=SYNC_READ?q3i:in3_im;

wire[77:0]mcode0,mcode1,mcode2,mcode3;
wire[69:0]mdata0,mdata1,mdata2,mdata3;wire[3:0]mem_detected,mem_corrected;
secded_decode70 dec0(mcode0,mdata0,mem_detected[0],mem_corrected[0]);
secded_decode70 dec1(mcode1,mdata1,mem_detected[1],mem_corrected[1]);
secded_decode70 dec2(mcode2,mdata2,mem_detected[2],mem_corrected[2]);
secded_decode70 dec3(mcode3,mdata3,mem_detected[3],mem_corrected[3]);
wire signed[34:0]a0r=mdata0[69:35],a0i=mdata0[34:0],a1r=mdata1[69:35],a1i=mdata1[34:0];
wire signed[34:0]a2r=mdata2[69:35],a2i=mdata2[34:0],a3r=mdata3[69:35],a3i=mdata3[34:0];
wire[9:0]sub_lower_exponent=(work_address*STRIDE)<<2;
wire[9:0]p_exponent;
pfft_phi_calc #(.STAGE(STAGE)) phi_group({out_count,2'd0},p_exponent);
wire[9:0]upper_exponent=PFFT_MODE?p_exponent:10'd0;
wire[9:0]lower_exponent=PFFT_MODE?10'd0:sub_lower_exponent;
wire signed[34:0]u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i;
independent_butterfly_ecc_v5_thresholded #(
 .TRIVIAL_UPPER((PFFT_MODE!=0)&&(STAGE==1)),
 .BYPASS_LOWER(PFFT_MODE!=0),
 .SUBFFT_SINGLE_ROTATION(PFFT_MODE==0),
 .THRESHOLD(THRESHOLD)
) protected_butterfly(
 a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,b0r,b0i,b1r,b1i,b2r,b2i,b3r,b3i,
 upper_exponent,lower_exponent,
 inject_enable,inject_symbol,inject_component,inject_bit,
 u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i,
 up_detected,up_corrected,up_uncorrectable,up_miscorrected,up_error_location,
 lo_detected,lo_corrected,lo_uncorrectable,lo_miscorrected,lo_error_location
);
wire signed[34:0]rot0r,rot0i,rot1r,rot1i,rot2r,rot2i,rot3r,rot3i;
generate
 if(PFFT_MODE!=0)begin:with_pfft_feedback_rotation
  independent_rotation_ecc_v5 #(
   .TRIVIAL_ROTATION(STAGE==1)
  ) protected_feedback_rotation(
   a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,p_exponent,
   rot0r,rot0i,rot1r,rot1i,rot2r,rot2i,rot3r,rot3i
  );
 end else begin:without_subfft_feedback_rotation
  assign rot0r=0;assign rot0i=0;assign rot1r=0;assign rot1i=0;
  assign rot2r=0;assign rot2i=0;assign rot3r=0;assign rot3i=0;
 end
endgenerate

// Stage 8 has heterogeneous per-lane exponents.  Its functional path remains
// exact here; the adjacent-frame group checker is implemented after Stage 8.
wire signed[34:0]raw_sum0r=a0r+b0r,raw_sum0i=a0i+b0i,raw_diff0r=a0r-b0r,raw_diff0i=a0i-b0i;
wire signed[34:0]raw_sum1r=a1r+b1r,raw_sum1i=a1i+b1i,raw_diff1r=a1r-b1r,raw_diff1i=a1i-b1i;
wire signed[34:0]raw_sum2r=a2r+b2r,raw_sum2i=a2i+b2i,raw_diff2r=a2r-b2r,raw_diff2i=a2i-b2i;
wire signed[34:0]raw_sum3r=a3r+b3r,raw_sum3i=a3i+b3i,raw_diff3r=a3r-b3r,raw_diff3i=a3i-b3i;
wire signed[34:0]raw_upper0r=raw_sum0r>>>1,raw_upper0i=raw_sum0i>>>1,raw_lower0r=raw_diff0r>>>1,raw_lower0i=raw_diff0i>>>1;
wire signed[34:0]raw_upper1r=raw_sum1r>>>1,raw_upper1i=raw_sum1i>>>1,raw_lower1r=raw_diff1r>>>1,raw_lower1i=raw_diff1i>>>1;
wire signed[34:0]raw_upper2r=raw_sum2r>>>1,raw_upper2i=raw_sum2i>>>1,raw_lower2r=raw_diff2r>>>1,raw_lower2i=raw_diff2i>>>1;
wire signed[34:0]raw_upper3r=raw_sum3r>>>1,raw_upper3i=raw_sum3i>>>1,raw_lower3r=raw_diff3r>>>1,raw_lower3i=raw_diff3i>>>1;
wire[9:0]lane_exp0,lane_exp1,lane_exp2,lane_exp3;
pfft_phi_calc #(.STAGE(STAGE)) phi0({out_count,2'd0},lane_exp0);
pfft_phi_calc #(.STAGE(STAGE)) phi1({out_count,2'd1},lane_exp1);
pfft_phi_calc #(.STAGE(STAGE)) phi2({out_count,2'd2},lane_exp2);
pfft_phi_calc #(.STAGE(STAGE)) phi3({out_count,2'd3},lane_exp3);
wire signed[34:0]hetero_upper0r,hetero_upper0i,hetero_upper1r,hetero_upper1i,hetero_upper2r,hetero_upper2i,hetero_upper3r,hetero_upper3i;
wire signed[34:0]hetero_feedback0r,hetero_feedback0i,hetero_feedback1r,hetero_feedback1i,hetero_feedback2r,hetero_feedback2i,hetero_feedback3r,hetero_feedback3i;
fft_complex_mul_q28 hm0u(raw_upper0r,raw_upper0i,lane_exp0,hetero_upper0r,hetero_upper0i);
fft_complex_mul_q28 hm1u(raw_upper1r,raw_upper1i,lane_exp1,hetero_upper1r,hetero_upper1i);
fft_complex_mul_q28 hm2u(raw_upper2r,raw_upper2i,lane_exp2,hetero_upper2r,hetero_upper2i);
fft_complex_mul_q28 hm3u(raw_upper3r,raw_upper3i,lane_exp3,hetero_upper3r,hetero_upper3i);
fft_complex_mul_q28 hm0f(a0r,a0i,lane_exp0,hetero_feedback0r,hetero_feedback0i);
fft_complex_mul_q28 hm1f(a1r,a1i,lane_exp1,hetero_feedback1r,hetero_feedback1i);
fft_complex_mul_q28 hm2f(a2r,a2i,lane_exp2,hetero_feedback2r,hetero_feedback2i);
fft_complex_mul_q28 hm3f(a3r,a3i,lane_exp3,hetero_feedback3r,hetero_feedback3i);

wire signed[34:0]candidate0r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper0r:u0r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback0r:rot0r):a0r);
wire signed[34:0]candidate0i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper0i:u0i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback0i:rot0i):a0i);
wire signed[34:0]candidate1r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper1r:u1r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback1r:rot1r):a1r);
wire signed[34:0]candidate1i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper1i:u1i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback1i:rot1i):a1i);
wire signed[34:0]candidate2r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper2r:u2r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback2r:rot2r):a2r);
wire signed[34:0]candidate2i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper2i:u2i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback2i:rot2i):a2i);
wire signed[34:0]candidate3r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper3r:u3r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback3r:rot3r):a3r);
wire signed[34:0]candidate3i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper3i:u3i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback3i:rot3i):a3i);
wire candidate_valid=work_second||((!work_second)&&work_primed);
wire signed[34:0]store0r=work_second?(HETEROGENEOUS_STAGE8?raw_lower0r:l0r):b0r,store0i=work_second?(HETEROGENEOUS_STAGE8?raw_lower0i:l0i):b0i;
wire signed[34:0]store1r=work_second?(HETEROGENEOUS_STAGE8?raw_lower1r:l1r):b1r,store1i=work_second?(HETEROGENEOUS_STAGE8?raw_lower1i:l1i):b1i;
wire signed[34:0]store2r=work_second?(HETEROGENEOUS_STAGE8?raw_lower2r:l2r):b2r,store2i=work_second?(HETEROGENEOUS_STAGE8?raw_lower2i:l2i):b2i;
wire signed[34:0]store3r=work_second?(HETEROGENEOUS_STAGE8?raw_lower3r:l3r):b3r,store3i=work_second?(HETEROGENEOUS_STAGE8?raw_lower3i:l3i):b3i;
wire[77:0]store_code0,store_code1,store_code2,store_code3;
secded_encode70 enc0({store0r,store0i},store_code0);secded_encode70 enc1({store1r,store1i},store_code1);
secded_encode70 enc2({store2r,store2i},store_code2);secded_encode70 enc3({store3r,store3i},store_code3);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem0(clk,in_valid,current_address,mcode0,work_valid,work_address,store_code0);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem1(clk,in_valid,current_address,mcode1,work_valid,work_address,store_code1);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem2(clk,in_valid,current_address,mcode2,work_valid,work_address,store_code2);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem3(clk,in_valid,current_address,mcode3,work_valid,work_address,store_code3);

always@(posedge clk)begin
 if(rst)begin phase<=0;primed<=0;out_count<=0;request_valid<=0;request_second<=0;request_primed<=0;request_address<=0;
  q0r<=0;q0i<=0;q1r<=0;q1i<=0;q2r<=0;q2i<=0;q3r<=0;q3i<=0;out_valid<=0;out_last<=0;
  out0_re<=0;out0_im<=0;out1_re<=0;out1_im<=0;out2_re<=0;out2_im<=0;out3_re<=0;out3_im<=0;
 end else begin
  request_valid<=SYNC_READ?in_valid:1'b0;
  if(SYNC_READ&&in_valid)begin request_second<=phase_second;request_primed<=primed;request_address<=current_address;
   q0r<=in0_re;q0i<=in0_im;q1r<=in1_re;q1i<=in1_im;q2r<=in2_re;q2i<=in2_im;q3r<=in3_re;q3i<=in3_im;end
  if(in_valid)begin if(phase==(2*DEPTH-1))begin phase<=0;primed<=1;end else phase<=phase+1'b1;end
  out_valid<=0;out_last<=0;
  if(work_valid&&candidate_valid)begin out_valid<=1;out_last<=(out_count==8'd255);out_count<=out_count+1'b1;
   out0_re<=candidate0r;out0_im<=candidate0i;out1_re<=candidate1r;out1_im<=candidate1i;
   out2_re<=candidate2r;out2_im<=candidate2i;out3_re<=candidate3r;out3_im<=candidate3i;end
 end
end
wire _keep=^mem_detected^mem_corrected^in_last;
endmodule

// ============================================================================
// SC-01 方案B: un-compensated version of ecc_stage4_v5 (added 2026-08-10).
// Uses independent_butterfly_ecc_v5_uncomp (THRESHOLD parameter); passes the
// fault-injection hook through; exposes upper/lower corrector flags.
// ============================================================================
module ecc_stage4_v5_uncomp #(
 parameter integer DEPTH=128,
 parameter integer STAGE=1,
 parameter integer PFFT_MODE=0,
 parameter integer THRESHOLD=8
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 input wire inject_enable,
 input wire [2:0]inject_symbol,
 input wire inject_component,
 input wire [5:0]inject_bit,
 output reg out_valid,output reg out_last,
 output reg signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 output wire up_detected,up_corrected,up_uncorrectable,output wire[2:0]up_error_location,
 output wire lo_detected,lo_corrected,lo_uncorrectable,output wire[2:0]lo_error_location
);
localparam integer PHASE_W=(2*DEPTH<=2)?1:$clog2(2*DEPTH);
localparam integer ADDR_W=(DEPTH<=1)?1:$clog2(DEPTH);
localparam integer STRIDE=256/(2*DEPTH);
localparam integer SYNC_READ=(DEPTH==128);
localparam integer HETEROGENEOUS_STAGE8=(PFFT_MODE!=0)&&(STAGE==8);
reg[PHASE_W-1:0]phase;reg primed;reg[7:0]out_count;
wire phase_second=(phase>=DEPTH);
wire[ADDR_W-1:0]current_address=phase_second?phase-DEPTH:phase;

reg request_valid,request_second,request_primed;reg[ADDR_W-1:0]request_address;
reg signed[34:0]q0r,q0i,q1r,q1i,q2r,q2i,q3r,q3i;
wire work_valid=SYNC_READ?request_valid:in_valid;
wire work_second=SYNC_READ?request_second:phase_second;
wire work_primed=SYNC_READ?request_primed:primed;
wire[ADDR_W-1:0]work_address=SYNC_READ?request_address:current_address;
wire signed[34:0]b0r=SYNC_READ?q0r:in0_re,b0i=SYNC_READ?q0i:in0_im;
wire signed[34:0]b1r=SYNC_READ?q1r:in1_re,b1i=SYNC_READ?q1i:in1_im;
wire signed[34:0]b2r=SYNC_READ?q2r:in2_re,b2i=SYNC_READ?q2i:in2_im;
wire signed[34:0]b3r=SYNC_READ?q3r:in3_re,b3i=SYNC_READ?q3i:in3_im;

wire[77:0]mcode0,mcode1,mcode2,mcode3;
wire[69:0]mdata0,mdata1,mdata2,mdata3;wire[3:0]mem_detected,mem_corrected;
secded_decode70 dec0(mcode0,mdata0,mem_detected[0],mem_corrected[0]);
secded_decode70 dec1(mcode1,mdata1,mem_detected[1],mem_corrected[1]);
secded_decode70 dec2(mcode2,mdata2,mem_detected[2],mem_corrected[2]);
secded_decode70 dec3(mcode3,mdata3,mem_detected[3],mem_corrected[3]);
wire signed[34:0]a0r=mdata0[69:35],a0i=mdata0[34:0],a1r=mdata1[69:35],a1i=mdata1[34:0];
wire signed[34:0]a2r=mdata2[69:35],a2i=mdata2[34:0],a3r=mdata3[69:35],a3i=mdata3[34:0];
wire[9:0]sub_lower_exponent=(work_address*STRIDE)<<2;
wire[9:0]p_exponent;
pfft_phi_calc #(.STAGE(STAGE)) phi_group({out_count,2'd0},p_exponent);
wire[9:0]upper_exponent=PFFT_MODE?p_exponent:10'd0;
wire[9:0]lower_exponent=PFFT_MODE?10'd0:sub_lower_exponent;
wire signed[34:0]u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i;
independent_butterfly_ecc_v5_uncomp #(
 .TRIVIAL_UPPER((PFFT_MODE!=0)&&(STAGE==1)),
 .BYPASS_LOWER(PFFT_MODE!=0),
 .SUBFFT_SINGLE_ROTATION(PFFT_MODE==0),
 .THRESHOLD(THRESHOLD)
) protected_butterfly(
 a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,b0r,b0i,b1r,b1i,b2r,b2i,b3r,b3i,
 upper_exponent,lower_exponent,
 inject_enable,inject_symbol,inject_component,inject_bit,
 u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i,
 up_detected,up_corrected,up_uncorrectable,up_error_location,
 lo_detected,lo_corrected,lo_uncorrectable,lo_error_location
);
wire signed[34:0]rot0r,rot0i,rot1r,rot1i,rot2r,rot2i,rot3r,rot3i;
generate
 if(PFFT_MODE!=0)begin:with_pfft_feedback_rotation
  independent_rotation_ecc_v5 #(
   .TRIVIAL_ROTATION(STAGE==1)
  ) protected_feedback_rotation(
   a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,p_exponent,
   rot0r,rot0i,rot1r,rot1i,rot2r,rot2i,rot3r,rot3i
  );
 end else begin:without_subfft_feedback_rotation
  assign rot0r=0;assign rot0i=0;assign rot1r=0;assign rot1i=0;
  assign rot2r=0;assign rot2i=0;assign rot3r=0;assign rot3i=0;
 end
endgenerate

// Stage 8 has heterogeneous per-lane exponents.  Its functional path remains
// exact here; the adjacent-frame group checker is implemented after Stage 8.
wire signed[34:0]raw_sum0r=a0r+b0r,raw_sum0i=a0i+b0i,raw_diff0r=a0r-b0r,raw_diff0i=a0i-b0i;
wire signed[34:0]raw_sum1r=a1r+b1r,raw_sum1i=a1i+b1i,raw_diff1r=a1r-b1r,raw_diff1i=a1i-b1i;
wire signed[34:0]raw_sum2r=a2r+b2r,raw_sum2i=a2i+b2i,raw_diff2r=a2r-b2r,raw_diff2i=a2i-b2i;
wire signed[34:0]raw_sum3r=a3r+b3r,raw_sum3i=a3i+b3i,raw_diff3r=a3r-b3r,raw_diff3i=a3i-b3i;
wire signed[34:0]raw_upper0r=raw_sum0r>>>1,raw_upper0i=raw_sum0i>>>1,raw_lower0r=raw_diff0r>>>1,raw_lower0i=raw_diff0i>>>1;
wire signed[34:0]raw_upper1r=raw_sum1r>>>1,raw_upper1i=raw_sum1i>>>1,raw_lower1r=raw_diff1r>>>1,raw_lower1i=raw_diff1i>>>1;
wire signed[34:0]raw_upper2r=raw_sum2r>>>1,raw_upper2i=raw_sum2i>>>1,raw_lower2r=raw_diff2r>>>1,raw_lower2i=raw_diff2i>>>1;
wire signed[34:0]raw_upper3r=raw_sum3r>>>1,raw_upper3i=raw_sum3i>>>1,raw_lower3r=raw_diff3r>>>1,raw_lower3i=raw_diff3i>>>1;
wire[9:0]lane_exp0,lane_exp1,lane_exp2,lane_exp3;
pfft_phi_calc #(.STAGE(STAGE)) phi0({out_count,2'd0},lane_exp0);
pfft_phi_calc #(.STAGE(STAGE)) phi1({out_count,2'd1},lane_exp1);
pfft_phi_calc #(.STAGE(STAGE)) phi2({out_count,2'd2},lane_exp2);
pfft_phi_calc #(.STAGE(STAGE)) phi3({out_count,2'd3},lane_exp3);
wire signed[34:0]hetero_upper0r,hetero_upper0i,hetero_upper1r,hetero_upper1i,hetero_upper2r,hetero_upper2i,hetero_upper3r,hetero_upper3i;
wire signed[34:0]hetero_feedback0r,hetero_feedback0i,hetero_feedback1r,hetero_feedback1i,hetero_feedback2r,hetero_feedback2i,hetero_feedback3r,hetero_feedback3i;
fft_complex_mul_q28 hm0u(raw_upper0r,raw_upper0i,lane_exp0,hetero_upper0r,hetero_upper0i);
fft_complex_mul_q28 hm1u(raw_upper1r,raw_upper1i,lane_exp1,hetero_upper1r,hetero_upper1i);
fft_complex_mul_q28 hm2u(raw_upper2r,raw_upper2i,lane_exp2,hetero_upper2r,hetero_upper2i);
fft_complex_mul_q28 hm3u(raw_upper3r,raw_upper3i,lane_exp3,hetero_upper3r,hetero_upper3i);
fft_complex_mul_q28 hm0f(a0r,a0i,lane_exp0,hetero_feedback0r,hetero_feedback0i);
fft_complex_mul_q28 hm1f(a1r,a1i,lane_exp1,hetero_feedback1r,hetero_feedback1i);
fft_complex_mul_q28 hm2f(a2r,a2i,lane_exp2,hetero_feedback2r,hetero_feedback2i);
fft_complex_mul_q28 hm3f(a3r,a3i,lane_exp3,hetero_feedback3r,hetero_feedback3i);

wire signed[34:0]candidate0r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper0r:u0r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback0r:rot0r):a0r);
wire signed[34:0]candidate0i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper0i:u0i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback0i:rot0i):a0i);
wire signed[34:0]candidate1r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper1r:u1r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback1r:rot1r):a1r);
wire signed[34:0]candidate1i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper1i:u1i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback1i:rot1i):a1i);
wire signed[34:0]candidate2r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper2r:u2r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback2r:rot2r):a2r);
wire signed[34:0]candidate2i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper2i:u2i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback2i:rot2i):a2i);
wire signed[34:0]candidate3r=work_second?(HETEROGENEOUS_STAGE8?hetero_upper3r:u3r):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback3r:rot3r):a3r);
wire signed[34:0]candidate3i=work_second?(HETEROGENEOUS_STAGE8?hetero_upper3i:u3i):(PFFT_MODE?(HETEROGENEOUS_STAGE8?hetero_feedback3i:rot3i):a3i);
wire candidate_valid=work_second||((!work_second)&&work_primed);
wire signed[34:0]store0r=work_second?(HETEROGENEOUS_STAGE8?raw_lower0r:l0r):b0r,store0i=work_second?(HETEROGENEOUS_STAGE8?raw_lower0i:l0i):b0i;
wire signed[34:0]store1r=work_second?(HETEROGENEOUS_STAGE8?raw_lower1r:l1r):b1r,store1i=work_second?(HETEROGENEOUS_STAGE8?raw_lower1i:l1i):b1i;
wire signed[34:0]store2r=work_second?(HETEROGENEOUS_STAGE8?raw_lower2r:l2r):b2r,store2i=work_second?(HETEROGENEOUS_STAGE8?raw_lower2i:l2i):b2i;
wire signed[34:0]store3r=work_second?(HETEROGENEOUS_STAGE8?raw_lower3r:l3r):b3r,store3i=work_second?(HETEROGENEOUS_STAGE8?raw_lower3i:l3i):b3i;
wire[77:0]store_code0,store_code1,store_code2,store_code3;
secded_encode70 enc0({store0r,store0i},store_code0);secded_encode70 enc1({store1r,store1i},store_code1);
secded_encode70 enc2({store2r,store2i},store_code2);secded_encode70 enc3({store3r,store3i},store_code3);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem0(clk,in_valid,current_address,mcode0,work_valid,work_address,store_code0);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem1(clk,in_valid,current_address,mcode1,work_valid,work_address,store_code1);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem2(clk,in_valid,current_address,mcode2,work_valid,work_address,store_code2);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem3(clk,in_valid,current_address,mcode3,work_valid,work_address,store_code3);

always@(posedge clk)begin
 if(rst)begin phase<=0;primed<=0;out_count<=0;request_valid<=0;request_second<=0;request_primed<=0;request_address<=0;
  q0r<=0;q0i<=0;q1r<=0;q1i<=0;q2r<=0;q2i<=0;q3r<=0;q3i<=0;out_valid<=0;out_last<=0;
  out0_re<=0;out0_im<=0;out1_re<=0;out1_im<=0;out2_re<=0;out2_im<=0;out3_re<=0;out3_im<=0;
 end else begin
  request_valid<=SYNC_READ?in_valid:1'b0;
  if(SYNC_READ&&in_valid)begin request_second<=phase_second;request_primed<=primed;request_address<=current_address;
   q0r<=in0_re;q0i<=in0_im;q1r<=in1_re;q1i<=in1_im;q2r<=in2_re;q2i<=in2_im;q3r<=in3_re;q3i<=in3_im;end
  if(in_valid)begin if(phase==(2*DEPTH-1))begin phase<=0;primed<=1;end else phase<=phase+1'b1;end
  out_valid<=0;out_last<=0;
  if(work_valid&&candidate_valid)begin out_valid<=1;out_last<=(out_count==8'd255);out_count<=out_count+1'b1;
   out0_re<=candidate0r;out0_im<=candidate0i;out1_re<=candidate1r;out1_im<=candidate1i;
   out2_re<=candidate2r;out2_im<=candidate2i;out3_re<=candidate3r;out3_im<=candidate3i;end
 end
end
wire _keep=^mem_detected^mem_corrected^in_last;
endmodule
