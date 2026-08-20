`timescale 1ns/1ps

// PFFT-RES-V3-001 P1 RTL.
//
// Every Stage-1--7 [6,4,3] group contains four functional butterflies and
// two check butterflies.  The six selected butterfly/feedback results share
// one six-lane post-selector rotation bank; upper and feedback rotations are
// never instantiated as separate multiplier banks.
(* keep_hierarchy = "yes" *) module p1_ecc_stage4_v3 #(
 parameter integer DEPTH=128,
 parameter integer STAGE=1
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output reg out_valid,output reg out_last,
 output reg signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
localparam integer PHASE_W=(2*DEPTH<=2)?1:$clog2(2*DEPTH);
localparam integer ADDR_W=(DEPTH<=1)?1:$clog2(DEPTH);
localparam integer SYNC_READ=(DEPTH==128);
reg[PHASE_W-1:0]phase;
reg primed;
reg[7:0]out_count;
wire phase_second=(phase>=DEPTH);
wire[ADDR_W-1:0]current_address=phase_second?phase-DEPTH:phase;

reg request_valid,request_second,request_primed;
reg[ADDR_W-1:0]request_address;
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
wire[69:0]mdata0,mdata1,mdata2,mdata3;
wire[3:0]mem_detected,mem_corrected;
secded_decode70 dec0(mcode0,mdata0,mem_detected[0],mem_corrected[0]);
secded_decode70 dec1(mcode1,mdata1,mem_detected[1],mem_corrected[1]);
secded_decode70 dec2(mcode2,mdata2,mem_detected[2],mem_corrected[2]);
secded_decode70 dec3(mcode3,mdata3,mem_detected[3],mem_corrected[3]);

wire signed[34:0]ar[0:5],ai[0:5],br[0:5],bi[0:5];
assign ar[0]=mdata0[69:35];assign ai[0]=mdata0[34:0];
assign ar[1]=mdata1[69:35];assign ai[1]=mdata1[34:0];
assign ar[2]=mdata2[69:35];assign ai[2]=mdata2[34:0];
assign ar[3]=mdata3[69:35];assign ai[3]=mdata3[34:0];
assign br[0]=b0r;assign bi[0]=b0i;assign br[1]=b1r;assign bi[1]=b1i;
assign br[2]=b2r;assign bi[2]=b2i;assign br[3]=b3r;assign bi[3]=b3i;

wire signed[34:0]a01r=ar[0]+ar[1],a01i=ai[0]+ai[1];
wire signed[34:0]a23r=ar[2]+ar[3],a23i=ai[2]+ai[3];
wire signed[34:0]b01r=br[0]+br[1],b01i=bi[0]+bi[1];
wire signed[34:0]b23r=br[2]+br[3],b23i=bi[2]+bi[3];
assign ar[4]=a01r+a23r;assign ai[4]=a01i+a23i;
assign br[4]=b01r+b23r;assign bi[4]=b01i+b23i;
assign ar[5]=(ar[0]-ai[1])+(-ar[2]+ai[3]);
assign ai[5]=(ai[0]+ar[1])+(-ai[2]-ar[3]);
assign br[5]=(br[0]-bi[1])+(-br[2]+bi[3]);
assign bi[5]=(bi[0]+br[1])+(-bi[2]-br[3]);

wire signed[34:0]upper_r[0:5],upper_i[0:5],lower_r[0:5],lower_i[0:5];
wire signed[34:0]selected_r[0:5],selected_i[0:5];
wire signed[34:0]rotated_r[0:5],rotated_i[0:5];
(* keep = "true" *)wire signed[34:0]received_r[0:5],received_i[0:5];
wire[9:0]group_exponent;
pfft_phi_calc #(.STAGE(STAGE)) phi_group({out_count,2'd0},group_exponent);

genvar g;
generate for(g=0;g<6;g=g+1)begin:complete_butterflies
 wire signed[34:0]sumr=ar[g]+br[g],sumi=ai[g]+bi[g];
 wire signed[34:0]diffr=ar[g]-br[g],diffi=ai[g]-bi[g];
 assign upper_r[g]=sumr>>>1;assign upper_i[g]=sumi>>>1;
 assign lower_r[g]=diffr>>>1;assign lower_i[g]=diffi>>>1;
 assign selected_r[g]=work_second?upper_r[g]:ar[g];
 assign selected_i[g]=work_second?upper_i[g]:ai[g];
 if(STAGE==1)begin:trivial_post_rotation
  fft_complex_rotate_trivial_1024 rotate(
   selected_r[g],selected_i[g],group_exponent,rotated_r[g],rotated_i[g]);
 end else begin:generic_post_rotation
  fft_complex_mul_q28 rotate(
   selected_r[g],selected_i[g],group_exponent,rotated_r[g],rotated_i[g]);
 end
 assign received_r[g]=rotated_r[g];
 assign received_i[g]=rotated_i[g];
end endgenerate

wire signed[34:0]decoded0r,decoded0i,decoded1r,decoded1i;
wire signed[34:0]decoded2r,decoded2i,decoded3r,decoded3i;
arithmetic_boundary_from_clean_v5 arithmetic_boundary(
 rotated_r[0],rotated_i[0],rotated_r[1],rotated_i[1],
 rotated_r[2],rotated_i[2],rotated_r[3],rotated_i[3],
 rotated_r[4],rotated_i[4],rotated_r[5],rotated_i[5],
 received_r[0],received_i[0],received_r[1],received_i[1],
 received_r[2],received_i[2],received_r[3],received_i[3],
 received_r[4],received_i[4],received_r[5],received_i[5],
 decoded0r,decoded0i,decoded1r,decoded1i,
 decoded2r,decoded2i,decoded3r,decoded3i
);

wire candidate_valid=work_second||((!work_second)&&work_primed);
wire signed[34:0]store0r=work_second?lower_r[0]:b0r;
wire signed[34:0]store0i=work_second?lower_i[0]:b0i;
wire signed[34:0]store1r=work_second?lower_r[1]:b1r;
wire signed[34:0]store1i=work_second?lower_i[1]:b1i;
wire signed[34:0]store2r=work_second?lower_r[2]:b2r;
wire signed[34:0]store2i=work_second?lower_i[2]:b2i;
wire signed[34:0]store3r=work_second?lower_r[3]:b3r;
wire signed[34:0]store3i=work_second?lower_i[3]:b3i;
wire[77:0]store_code0,store_code1,store_code2,store_code3;
secded_encode70 enc0({store0r,store0i},store_code0);
secded_encode70 enc1({store1r,store1i},store_code1);
secded_encode70 enc2({store2r,store2i},store_code2);
secded_encode70 enc3({store3r,store3i},store_code3);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem0(
 clk,in_valid,current_address,mcode0,work_valid,work_address,store_code0);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem1(
 clk,in_valid,current_address,mcode1,work_valid,work_address,store_code1);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem2(
 clk,in_valid,current_address,mcode2,work_valid,work_address,store_code2);
fft_memory_v5 #(.WIDTH(78),.DEPTH(DEPTH),.ADDR_W(ADDR_W))mem3(
 clk,in_valid,current_address,mcode3,work_valid,work_address,store_code3);

always@(posedge clk)begin
 if(rst)begin
  phase<=0;primed<=0;out_count<=0;
  request_valid<=0;request_second<=0;request_primed<=0;request_address<=0;
  q0r<=0;q0i<=0;q1r<=0;q1i<=0;q2r<=0;q2i<=0;q3r<=0;q3i<=0;
  out_valid<=0;out_last<=0;
  out0_re<=0;out0_im<=0;out1_re<=0;out1_im<=0;
  out2_re<=0;out2_im<=0;out3_re<=0;out3_im<=0;
 end else begin
  request_valid<=SYNC_READ?in_valid:1'b0;
  if(SYNC_READ&&in_valid)begin
   request_second<=phase_second;request_primed<=primed;
   request_address<=current_address;
   q0r<=in0_re;q0i<=in0_im;q1r<=in1_re;q1i<=in1_im;
   q2r<=in2_re;q2i<=in2_im;q3r<=in3_re;q3i<=in3_im;
  end
  if(in_valid)begin
   if(phase==(2*DEPTH-1))begin phase<=0;primed<=1;end
   else phase<=phase+1'b1;
  end
  out_valid<=0;out_last<=0;
  if(work_valid&&candidate_valid)begin
   out_valid<=1;out_last<=(out_count==8'd255);
   out_count<=out_count+1'b1;
   out0_re<=decoded0r;out0_im<=decoded0i;
   out1_re<=decoded1r;out1_im<=decoded1i;
   out2_re<=decoded2r;out2_im<=decoded2i;
   out3_re<=decoded3r;out3_im<=decoded3i;
  end
 end
end
wire _keep=^mem_detected^mem_corrected^in_last;
endmodule


// Stage 8 keeps four functional butterflies and exports their original A/B
// operands for the buffered exact-operator codewords.  Lanes 0/1 have only
// trivial exchanged rotations; lanes 2/3 retain one generic complex
// multiplier each.
(* keep_hierarchy = "yes" *) module p1_stage8_functional_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output reg out_valid,output reg out_last,
 output reg signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 output reg signed[34:0]op_a0_re,op_a0_im,op_a1_re,op_a1_im,op_a2_re,op_a2_im,op_a3_re,op_a3_im,
 output reg signed[34:0]op_b0_re,op_b0_im,op_b1_re,op_b1_im,op_b2_re,op_b2_im,op_b3_re,op_b3_im,
 output reg[9:0]op_exp0,op_exp1,op_exp2,op_exp3,
 output reg op_branch_upper
);
reg phase,primed;
reg[7:0]out_count;
wire[77:0]mcode0,mcode1,mcode2,mcode3;
wire[69:0]mdata0,mdata1,mdata2,mdata3;
wire[3:0]mem_detected,mem_corrected;
secded_decode70 dec0(mcode0,mdata0,mem_detected[0],mem_corrected[0]);
secded_decode70 dec1(mcode1,mdata1,mem_detected[1],mem_corrected[1]);
secded_decode70 dec2(mcode2,mdata2,mem_detected[2],mem_corrected[2]);
secded_decode70 dec3(mcode3,mdata3,mem_detected[3],mem_corrected[3]);
wire signed[34:0]a0r=mdata0[69:35],a0i=mdata0[34:0];
wire signed[34:0]a1r=mdata1[69:35],a1i=mdata1[34:0];
wire signed[34:0]a2r=mdata2[69:35],a2i=mdata2[34:0];
wire signed[34:0]a3r=mdata3[69:35],a3i=mdata3[34:0];

wire signed[34:0]sum0r=a0r+in0_re,sum0i=a0i+in0_im;
wire signed[34:0]sum1r=a1r+in1_re,sum1i=a1i+in1_im;
wire signed[34:0]sum2r=a2r+in2_re,sum2i=a2i+in2_im;
wire signed[34:0]sum3r=a3r+in3_re,sum3i=a3i+in3_im;
wire signed[34:0]diff0r=a0r-in0_re,diff0i=a0i-in0_im;
wire signed[34:0]diff1r=a1r-in1_re,diff1i=a1i-in1_im;
wire signed[34:0]diff2r=a2r-in2_re,diff2i=a2i-in2_im;
wire signed[34:0]diff3r=a3r-in3_re,diff3i=a3i-in3_im;
wire signed[34:0]upper0r=sum0r>>>1,upper0i=sum0i>>>1;
wire signed[34:0]upper1r=sum1r>>>1,upper1i=sum1i>>>1;
wire signed[34:0]upper2r=sum2r>>>1,upper2i=sum2i>>>1;
wire signed[34:0]upper3r=sum3r>>>1,upper3i=sum3i>>>1;
wire signed[34:0]lower0r=diff0r>>>1,lower0i=diff0i>>>1;
wire signed[34:0]lower1r=diff1r>>>1,lower1i=diff1i>>>1;
wire signed[34:0]lower2r=diff2r>>>1,lower2i=diff2i>>>1;
wire signed[34:0]lower3r=diff3r>>>1,lower3i=diff3i>>>1;

wire[9:0]exp0,exp1,exp2,exp3;
pfft_phi_calc #(.STAGE(8))phi0({out_count,2'd0},exp0);
pfft_phi_calc #(.STAGE(8))phi1({out_count,2'd1},exp1);
pfft_phi_calc #(.STAGE(8))phi2({out_count,2'd2},exp2);
pfft_phi_calc #(.STAGE(8))phi3({out_count,2'd3},exp3);
wire signed[34:0]pre0r=phase?upper0r:a0r,pre0i=phase?upper0i:a0i;
wire signed[34:0]pre1r=phase?upper1r:a1r,pre1i=phase?upper1i:a1i;
wire signed[34:0]pre2r=phase?upper2r:a2r,pre2i=phase?upper2i:a2i;
wire signed[34:0]pre3r=phase?upper3r:a3r,pre3i=phase?upper3i:a3i;
wire signed[34:0]candidate0r,candidate0i,candidate1r,candidate1i;
wire signed[34:0]candidate2r,candidate2i,candidate3r,candidate3i;
fft_complex_rotate_trivial_1024 rot0(pre0r,pre0i,exp0,candidate0r,candidate0i);
fft_complex_rotate_trivial_1024 rot1(pre1r,pre1i,exp1,candidate1r,candidate1i);
fft_complex_mul_q28 rot2(pre2r,pre2i,exp2,candidate2r,candidate2i);
fft_complex_mul_q28 rot3(pre3r,pre3i,exp3,candidate3r,candidate3i);

wire signed[34:0]store0r=phase?lower0r:in0_re,store0i=phase?lower0i:in0_im;
wire signed[34:0]store1r=phase?lower1r:in1_re,store1i=phase?lower1i:in1_im;
wire signed[34:0]store2r=phase?lower2r:in2_re,store2i=phase?lower2i:in2_im;
wire signed[34:0]store3r=phase?lower3r:in3_re,store3i=phase?lower3i:in3_im;
wire[77:0]store_code0,store_code1,store_code2,store_code3;
secded_encode70 enc0({store0r,store0i},store_code0);
secded_encode70 enc1({store1r,store1i},store_code1);
secded_encode70 enc2({store2r,store2i},store_code2);
secded_encode70 enc3({store3r,store3i},store_code3);
fft_memory_v5 #(.WIDTH(78),.DEPTH(1),.ADDR_W(1))mem0(
 clk,in_valid,1'b0,mcode0,in_valid,1'b0,store_code0);
fft_memory_v5 #(.WIDTH(78),.DEPTH(1),.ADDR_W(1))mem1(
 clk,in_valid,1'b0,mcode1,in_valid,1'b0,store_code1);
fft_memory_v5 #(.WIDTH(78),.DEPTH(1),.ADDR_W(1))mem2(
 clk,in_valid,1'b0,mcode2,in_valid,1'b0,store_code2);
fft_memory_v5 #(.WIDTH(78),.DEPTH(1),.ADDR_W(1))mem3(
 clk,in_valid,1'b0,mcode3,in_valid,1'b0,store_code3);

reg signed[34:0]pair_a0r,pair_a0i,pair_a1r,pair_a1i,pair_a2r,pair_a2i,pair_a3r,pair_a3i;
reg signed[34:0]pair_b0r,pair_b0i,pair_b1r,pair_b1i,pair_b2r,pair_b2i,pair_b3r,pair_b3i;
always@(posedge clk)begin
 if(rst)begin
  phase<=0;primed<=0;out_count<=0;out_valid<=0;out_last<=0;
  out0_re<=0;out0_im<=0;out1_re<=0;out1_im<=0;
  out2_re<=0;out2_im<=0;out3_re<=0;out3_im<=0;
  op_a0_re<=0;op_a0_im<=0;op_a1_re<=0;op_a1_im<=0;
  op_a2_re<=0;op_a2_im<=0;op_a3_re<=0;op_a3_im<=0;
  op_b0_re<=0;op_b0_im<=0;op_b1_re<=0;op_b1_im<=0;
  op_b2_re<=0;op_b2_im<=0;op_b3_re<=0;op_b3_im<=0;
  op_exp0<=0;op_exp1<=0;op_exp2<=0;op_exp3<=0;op_branch_upper<=0;
  pair_a0r<=0;pair_a0i<=0;pair_a1r<=0;pair_a1i<=0;
  pair_a2r<=0;pair_a2i<=0;pair_a3r<=0;pair_a3i<=0;
  pair_b0r<=0;pair_b0i<=0;pair_b1r<=0;pair_b1i<=0;
  pair_b2r<=0;pair_b2i<=0;pair_b3r<=0;pair_b3i<=0;
 end else begin
  out_valid<=0;out_last<=0;
  if(in_valid)begin
   if(phase)begin
    pair_a0r<=a0r;pair_a0i<=a0i;pair_a1r<=a1r;pair_a1i<=a1i;
    pair_a2r<=a2r;pair_a2i<=a2i;pair_a3r<=a3r;pair_a3i<=a3i;
    pair_b0r<=in0_re;pair_b0i<=in0_im;pair_b1r<=in1_re;pair_b1i<=in1_im;
    pair_b2r<=in2_re;pair_b2i<=in2_im;pair_b3r<=in3_re;pair_b3i<=in3_im;
    primed<=1;
   end
   phase<=~phase;
   if(phase||primed)begin
    out_valid<=1;out_last<=(out_count==8'd255);
    out_count<=out_count+1'b1;
    out0_re<=candidate0r;out0_im<=candidate0i;
    out1_re<=candidate1r;out1_im<=candidate1i;
    out2_re<=candidate2r;out2_im<=candidate2i;
    out3_re<=candidate3r;out3_im<=candidate3i;
    op_exp0<=exp0;op_exp1<=exp1;op_exp2<=exp2;op_exp3<=exp3;
    op_branch_upper<=phase;
    if(phase)begin
     op_a0_re<=a0r;op_a0_im<=a0i;op_a1_re<=a1r;op_a1_im<=a1i;
     op_a2_re<=a2r;op_a2_im<=a2i;op_a3_re<=a3r;op_a3_im<=a3i;
     op_b0_re<=in0_re;op_b0_im<=in0_im;op_b1_re<=in1_re;op_b1_im<=in1_im;
     op_b2_re<=in2_re;op_b2_im<=in2_im;op_b3_re<=in3_re;op_b3_im<=in3_im;
    end else begin
     op_a0_re<=pair_a0r;op_a0_im<=pair_a0i;op_a1_re<=pair_a1r;op_a1_im<=pair_a1i;
     op_a2_re<=pair_a2r;op_a2_im<=pair_a2i;op_a3_re<=pair_a3r;op_a3_im<=pair_a3i;
     op_b0_re<=pair_b0r;op_b0_im<=pair_b0i;op_b1_re<=pair_b1r;op_b1_im<=pair_b1i;
     op_b2_re<=pair_b2r;op_b2_im<=pair_b2i;op_b3_re<=pair_b3r;op_b3_im<=pair_b3i;
    end
   end
  end
 end
end
wire _keep=^mem_detected^mem_corrected^in_last;
endmodule




// Active one-server Stage-8 scheduler.
//
// The schedule releases exactly 512 [6,4,3] codeword tasks in each
// two-frame/512-beat period.  Cross-frame tasks are urgent; same-frame tasks
// are background work.  The active memory map has no combinational RAM read:
//
// * twelve 512x78 F/A/B histories use one synchronous read and one write;
// * the 128-entry background FIFO uses a registered head and a synchronous
//   dual-port tail RAM (the same-cycle arrival is the audited 129th skid);
// * corrected tasks are written once into one of two 512x312 result banks,
//   so no result RAM has more than one write in a cycle; and
// * result-bank reads are issued one cycle before the fixed output slot, with
//   explicit same-address forwarding.
//
// One and only one independent_check_operator_pair_v5 is reachable here.
(* keep_hierarchy = "yes" *) module p1_stage8_single_check_pair_scheduler_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 input wire signed[34:0]op_a0_re,op_a0_im,op_a1_re,op_a1_im,op_a2_re,op_a2_im,op_a3_re,op_a3_im,
 input wire signed[34:0]op_b0_re,op_b0_im,op_b1_re,op_b1_im,op_b2_re,op_b2_im,op_b3_re,op_b3_im,
 input wire[9:0]op_exp0,op_exp1,op_exp2,op_exp3,
 input wire op_branch_upper,
 output reg out_valid,output reg out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
localparam[2:0]TASK_SAME0=3'd0;
localparam[2:0]TASK_SAME_PAIR=3'd1;
localparam[2:0]TASK_CROSS_NORMAL=3'd2;
localparam[2:0]TASK_CROSS_A=3'd3;
localparam[2:0]TASK_CROSS_B=3'd4;
localparam integer FIXED_DELAY_CYCLES=258;
localparam integer TASK_TAG_W=23;
localparam integer TASK_PAYLOAD_W=TASK_TAG_W+(12*78);
localparam integer BACKGROUND_PREISSUE_CAPACITY=129;
localparam integer BACKGROUND_STORED_CAPACITY=128;

reg[8:0]source_address;
wire[7:0]source_beat=source_address[7:0];
wire source_second_frame=source_address[8];

wire[77:0]current_f0,current_f1,current_f2,current_f3;
wire[77:0]current_a0,current_a1,current_a2,current_a3;
wire[77:0]current_b0,current_b1,current_b2,current_b3;
secded_encode70 current_f_enc0({in0_re,in0_im},current_f0);
secded_encode70 current_f_enc1({in1_re,in1_im},current_f1);
secded_encode70 current_f_enc2({in2_re,in2_im},current_f2);
secded_encode70 current_f_enc3({in3_re,in3_im},current_f3);
secded_encode70 current_a_enc0({op_a0_re,op_a0_im},current_a0);
secded_encode70 current_a_enc1({op_a1_re,op_a1_im},current_a1);
secded_encode70 current_a_enc2({op_a2_re,op_a2_im},current_a2);
secded_encode70 current_a_enc3({op_a3_re,op_a3_im},current_a3);
secded_encode70 current_b_enc0({op_b0_re,op_b0_im},current_b0);
secded_encode70 current_b_enc1({op_b1_re,op_b1_im},current_b1);
secded_encode70 current_b_enc2({op_b2_re,op_b2_im},current_b2);
secded_encode70 current_b_enc3({op_b3_re,op_b3_im},current_b3);

// Each history is a simple dual-port memory: the current beat writes one
// address while the read port prefetches the historical operand needed by the
// next valid beat.  Gaps in in_valid merely hold the registered read value.
(* ram_style = "block" *)reg[77:0]functional_history0[0:511];
(* ram_style = "block" *)reg[77:0]functional_history1[0:511];
(* ram_style = "block" *)reg[77:0]functional_history2[0:511];
(* ram_style = "block" *)reg[77:0]functional_history3[0:511];
(* ram_style = "block" *)reg[77:0]operand_a_history0[0:511];
(* ram_style = "block" *)reg[77:0]operand_a_history1[0:511];
(* ram_style = "block" *)reg[77:0]operand_a_history2[0:511];
(* ram_style = "block" *)reg[77:0]operand_a_history3[0:511];
(* ram_style = "block" *)reg[77:0]operand_b_history0[0:511];
(* ram_style = "block" *)reg[77:0]operand_b_history1[0:511];
(* ram_style = "block" *)reg[77:0]operand_b_history2[0:511];
(* ram_style = "block" *)reg[77:0]operand_b_history3[0:511];

reg[77:0]historical_f0,historical_f1,historical_f2,historical_f3;
reg[77:0]historical_a0,historical_a1,historical_a2,historical_a3;
reg[77:0]historical_b0,historical_b1,historical_b2,historical_b3;

// For an address s, these ports fetch what address s+1 can consume.
// Lane 0/1 normally need (s+1)-2; the beat-254 CROSS_A exception needs
// (s+1)-256.  Lane 2/3 cross groups always need (s+1)-256.
wire[8:0]history01_read_address=
 (source_second_frame&&(source_beat==8'd253))?
 (source_address-9'd255):(source_address-9'd1);
wire[8:0]history23_read_address=source_address-9'd255;

always@(posedge clk)begin
 if(in_valid)begin
  historical_f0<=functional_history0[history01_read_address];
  historical_f1<=functional_history1[history01_read_address];
  historical_a0<=operand_a_history0[history01_read_address];
  historical_a1<=operand_a_history1[history01_read_address];
  historical_b0<=operand_b_history0[history01_read_address];
  historical_b1<=operand_b_history1[history01_read_address];
  historical_f2<=functional_history2[history23_read_address];
  historical_f3<=functional_history3[history23_read_address];
  historical_a2<=operand_a_history2[history23_read_address];
  historical_a3<=operand_a_history3[history23_read_address];
  historical_b2<=operand_b_history2[history23_read_address];
  historical_b3<=operand_b_history3[history23_read_address];

  functional_history0[source_address]<=current_f0;
  functional_history1[source_address]<=current_f1;
  functional_history2[source_address]<=current_f2;
  functional_history3[source_address]<=current_f3;
  operand_a_history0[source_address]<=current_a0;
  operand_a_history1[source_address]<=current_a1;
  operand_a_history2[source_address]<=current_a2;
  operand_a_history3[source_address]<=current_a3;
  operand_b_history0[source_address]<=current_b0;
  operand_b_history1[source_address]<=current_b1;
  operand_b_history2[source_address]<=current_b2;
  operand_b_history3[source_address]<=current_b3;
 end
end

function automatic[TASK_PAYLOAD_W-1:0]pack_task;
 input[TASK_TAG_W-1:0]tag;
 input[77:0]f0,f1,f2,f3;
 input[77:0]a0,a1,a2,a3;
 input[77:0]b0,b1,b2,b3;
 begin
  pack_task={tag,f0,f1,f2,f3,a0,a1,a2,a3,b0,b1,b2,b3};
 end
endfunction

wire same0_arrival=(source_beat==8'd0);
wire same_pair_arrival=(source_beat[1:0]==2'd3)||
 ((source_beat[1:0]==2'd0)&&(source_beat!=8'd0));
wire background_arrival_valid=in_valid&&(same0_arrival||same_pair_arrival);
wire[2:0]background_arrival_kind=same0_arrival?TASK_SAME0:TASK_SAME_PAIR;
wire[22:0]background_arrival_tag={
 background_arrival_kind,source_address,op_branch_upper,op_exp0};
wire[TASK_PAYLOAD_W-1:0]same0_payload=pack_task(
 background_arrival_tag,
 current_f0,current_f1,current_f2,current_f3,
 current_a0,current_a1,current_a2,current_a3,
 current_b0,current_b1,current_b2,current_b3);
wire[TASK_PAYLOAD_W-1:0]same_pair_payload=pack_task(
 background_arrival_tag,
 historical_f0,historical_f1,current_f0,current_f1,
 historical_a0,historical_a1,current_a0,current_a1,
 historical_b0,historical_b1,current_b0,current_b1);
wire[TASK_PAYLOAD_W-1:0]background_arrival_payload=
 same0_arrival?same0_payload:same_pair_payload;

reg[1:0]urgent_arrival_count;
reg[TASK_PAYLOAD_W-1:0]urgent_arrival_payload0,urgent_arrival_payload1;
reg[22:0]urgent_tag0,urgent_tag1;
always@*begin
 urgent_arrival_count=0;
 urgent_arrival_payload0=0;
 urgent_arrival_payload1=0;
 urgent_tag0=0;
 urgent_tag1=0;
 if(in_valid&&source_second_frame)begin
  if(source_beat==8'd254)begin
   urgent_arrival_count=2;
   urgent_tag0={TASK_CROSS_A,source_address,op_branch_upper,op_exp0};
   urgent_tag1={TASK_CROSS_B,source_address,op_branch_upper,op_exp2};
   urgent_arrival_payload0=pack_task(
    urgent_tag0,
    historical_f0,historical_f1,current_f0,current_f1,
    historical_a0,historical_a1,current_a0,current_a1,
    historical_b0,historical_b1,current_b0,current_b1);
   urgent_arrival_payload1=pack_task(
    urgent_tag1,
    historical_f2,historical_f3,current_f2,current_f3,
    historical_a2,historical_a3,current_a2,current_a3,
    historical_b2,historical_b3,current_b2,current_b3);
  end else if(((source_beat>=8'd1)&&(source_beat<=8'd253))||
              (source_beat==8'd255))begin
   urgent_arrival_count=1;
   urgent_tag0={
    TASK_CROSS_NORMAL,source_address,op_branch_upper,op_exp2};
   urgent_arrival_payload0=pack_task(
    urgent_tag0,
    historical_f2,historical_f3,current_f2,current_f3,
    historical_a2,historical_a3,current_a2,current_a3,
    historical_b2,historical_b3,current_b2,current_b3);
  end
 end
end

// Urgent storage is a small register skid queue.  Background payloads use a
// registered head plus a synchronous BRAM tail.  The background count is the
// number of stored entries after the fall-through issue slot.
reg[TASK_PAYLOAD_W-1:0]urgent_fifo[0:3];
reg[1:0]urgent_rd_ptr,urgent_wr_ptr;
reg[2:0]urgent_count;
reg[TASK_PAYLOAD_W-1:0]background_head;
(* ram_style = "block" *)reg[TASK_PAYLOAD_W-1:0]background_fifo[0:127];
reg[6:0]background_rd_ptr,background_wr_ptr;
reg[8:0]background_count;
reg queue_overflow;

reg issue_valid;
reg[TASK_PAYLOAD_W-1:0]issue_payload;
reg issue_urgent_existing,issue_urgent_direct;
reg issue_background_existing,issue_background_direct;
always@*begin
 issue_valid=0;
 issue_payload=0;
 issue_urgent_existing=0;
 issue_urgent_direct=0;
 issue_background_existing=0;
 issue_background_direct=0;
 if(urgent_count!=0)begin
  issue_valid=1;
  issue_payload=urgent_fifo[urgent_rd_ptr];
  issue_urgent_existing=1;
 end else if(urgent_arrival_count!=0)begin
  issue_valid=1;
  issue_payload=urgent_arrival_payload0;
  issue_urgent_direct=1;
 end else if(background_count!=0)begin
  issue_valid=1;
  issue_payload=background_head;
  issue_background_existing=1;
 end else if(background_arrival_valid)begin
  issue_valid=1;
  issue_payload=background_arrival_payload;
  issue_background_direct=1;
 end
end

wire background_enqueue=
 background_arrival_valid&&!issue_background_direct;
wire background_pop=issue_background_existing;

always@(posedge clk)begin
 if(rst)begin
  urgent_rd_ptr<=0;
  urgent_wr_ptr<=0;
  urgent_count<=0;
  background_head<=0;
  background_rd_ptr<=0;
  background_wr_ptr<=0;
  background_count<=0;
  queue_overflow<=0;
 end else begin
  // Existing urgent work always issues first.  New urgent work occupies only
  // the storage left after that issue.  With an empty queue, payload0 falls
  // through and only the second beat-254 task enters the skid register.
  if(urgent_count!=0)begin
   urgent_rd_ptr<=urgent_rd_ptr+1'b1;
   case(urgent_arrival_count)
    0:urgent_count<=urgent_count-1'b1;
    1:begin
     urgent_fifo[urgent_wr_ptr]<=urgent_arrival_payload0;
     urgent_wr_ptr<=urgent_wr_ptr+1'b1;
     urgent_count<=urgent_count;
    end
    2:begin
     if(urgent_count>=3'd4)queue_overflow<=1;
     else begin
      urgent_fifo[urgent_wr_ptr]<=urgent_arrival_payload0;
      urgent_fifo[urgent_wr_ptr+1'b1]<=urgent_arrival_payload1;
      urgent_wr_ptr<=urgent_wr_ptr+2'd2;
      urgent_count<=urgent_count+1'b1;
     end
    end
   endcase
  end else if(urgent_arrival_count==2)begin
   urgent_fifo[urgent_wr_ptr]<=urgent_arrival_payload1;
   urgent_wr_ptr<=urgent_wr_ptr+1'b1;
   urgent_count<=1;
  end

  case({background_enqueue,background_pop})
   2'b10:begin
    if(background_count==BACKGROUND_STORED_CAPACITY)
     queue_overflow<=1;
    else if(background_count==0)begin
     background_head<=background_arrival_payload;
     background_count<=1;
    end else begin
     background_fifo[background_wr_ptr]<=background_arrival_payload;
     background_wr_ptr<=background_wr_ptr+1'b1;
     background_count<=background_count+1'b1;
    end
   end
   2'b01:begin
    if(background_count==1)
     background_count<=0;
    else begin
     background_head<=background_fifo[background_rd_ptr];
     background_rd_ptr<=background_rd_ptr+1'b1;
     background_count<=background_count-1'b1;
    end
   end
   2'b11:begin
    if(background_count==1)begin
     background_head<=background_arrival_payload;
     background_count<=1;
    end else begin
     background_head<=background_fifo[background_rd_ptr];
     background_fifo[background_wr_ptr]<=background_arrival_payload;
     background_rd_ptr<=background_rd_ptr+1'b1;
     background_wr_ptr<=background_wr_ptr+1'b1;
     background_count<=background_count;
    end
   end
  endcase
 end
end

wire[22:0]issue_tag;
wire[77:0]task_f0_code,task_f1_code,task_f2_code,task_f3_code;
wire[77:0]task_a0_code,task_a1_code,task_a2_code,task_a3_code;
wire[77:0]task_b0_code,task_b1_code,task_b2_code,task_b3_code;
assign{
 issue_tag,
 task_f0_code,task_f1_code,task_f2_code,task_f3_code,
 task_a0_code,task_a1_code,task_a2_code,task_a3_code,
 task_b0_code,task_b1_code,task_b2_code,task_b3_code
}=issue_payload;
wire[2:0]issue_kind=issue_tag[22:20];
wire[8:0]issue_address=issue_tag[19:11];
wire issue_branch=issue_tag[10];
wire[9:0]issue_exponent=issue_tag[9:0];

wire[69:0]task_f0,task_f1,task_f2,task_f3;
wire[69:0]task_a0,task_a1,task_a2,task_a3;
wire[69:0]task_b0,task_b1,task_b2,task_b3;
wire[11:0]task_detected,task_corrected;
secded_decode70 task_f_dec0(task_f0_code,task_f0,task_detected[0],task_corrected[0]);
secded_decode70 task_f_dec1(task_f1_code,task_f1,task_detected[1],task_corrected[1]);
secded_decode70 task_f_dec2(task_f2_code,task_f2,task_detected[2],task_corrected[2]);
secded_decode70 task_f_dec3(task_f3_code,task_f3,task_detected[3],task_corrected[3]);
secded_decode70 task_a_dec0(task_a0_code,task_a0,task_detected[4],task_corrected[4]);
secded_decode70 task_a_dec1(task_a1_code,task_a1,task_detected[5],task_corrected[5]);
secded_decode70 task_a_dec2(task_a2_code,task_a2,task_detected[6],task_corrected[6]);
secded_decode70 task_a_dec3(task_a3_code,task_a3,task_detected[7],task_corrected[7]);
secded_decode70 task_b_dec0(task_b0_code,task_b0,task_detected[8],task_corrected[8]);
secded_decode70 task_b_dec1(task_b1_code,task_b1,task_detected[9],task_corrected[9]);
secded_decode70 task_b_dec2(task_b2_code,task_b2,task_detected[10],task_corrected[10]);
secded_decode70 task_b_dec3(task_b3_code,task_b3,task_detected[11],task_corrected[11]);

wire signed[34:0]check4r,check4i,check5r,check5i;
independent_check_operator_pair_v5 shared_check_pair(
 task_a0[69:35],task_a0[34:0],task_a1[69:35],task_a1[34:0],
 task_a2[69:35],task_a2[34:0],task_a3[69:35],task_a3[34:0],
 task_b0[69:35],task_b0[34:0],task_b1[69:35],task_b1[34:0],
 task_b2[69:35],task_b2[34:0],task_b3[69:35],task_b3[34:0],
 issue_branch,issue_exponent,check4r,check4i,check5r,check5i
);

// Stable Stage-8 arithmetic-connectivity injection boundary.  The clean
// reference never depends on these aliases; forcing received_* therefore
// changes only the received symbol and cannot cancel its own syndrome.
(* keep = "true" *)wire signed[34:0]received_f0r,received_f0i;
(* keep = "true" *)wire signed[34:0]received_f1r,received_f1i;
(* keep = "true" *)wire signed[34:0]received_f2r,received_f2i;
(* keep = "true" *)wire signed[34:0]received_f3r,received_f3i;
(* keep = "true" *)wire signed[34:0]received_c4r,received_c4i;
(* keep = "true" *)wire signed[34:0]received_c5r,received_c5i;
assign received_f0r=task_f0[69:35];assign received_f0i=task_f0[34:0];
assign received_f1r=task_f1[69:35];assign received_f1i=task_f1[34:0];
assign received_f2r=task_f2[69:35];assign received_f2i=task_f2[34:0];
assign received_f3r=task_f3[69:35];assign received_f3i=task_f3[34:0];
assign received_c4r=check4r;assign received_c4i=check4i;
assign received_c5r=check5r;assign received_c5i=check5i;

wire signed[34:0]decoded0r,decoded0i,decoded1r,decoded1i;
wire signed[34:0]decoded2r,decoded2i,decoded3r,decoded3i;
arithmetic_boundary_from_clean_v5 shared_arithmetic_boundary(
 task_f0[69:35],task_f0[34:0],task_f1[69:35],task_f1[34:0],
 task_f2[69:35],task_f2[34:0],task_f3[69:35],task_f3[34:0],
 check4r,check4i,check5r,check5i,
 received_f0r,received_f0i,received_f1r,received_f1i,
 received_f2r,received_f2i,received_f3r,received_f3i,
 received_c4r,received_c4i,received_c5r,received_c5i,
 decoded0r,decoded0i,decoded1r,decoded1i,
 decoded2r,decoded2i,decoded3r,decoded3i
);

wire[77:0]decoded_code0,decoded_code1,decoded_code2,decoded_code3;
secded_encode70 decoded_enc0({decoded0r,decoded0i},decoded_code0);
secded_encode70 decoded_enc1({decoded1r,decoded1i},decoded_code1);
secded_encode70 decoded_enc2({decoded2r,decoded2i},decoded_code2);
secded_encode70 decoded_enc3({decoded3r,decoded3i},decoded_code3);
wire[311:0]task_result_pack={
 decoded_code0,decoded_code1,decoded_code2,decoded_code3};

// A task is stored once, by its release address.  result01 contains SAME0,
// SAME_PAIR and CROSS_A groups; result23 contains SAME0, CROSS_NORMAL and
// CROSS_B groups.  SAME0 writes both independent banks, still one write per
// bank in that cycle.
(* ram_style = "block" *)reg[311:0]result01_memory[0:511];
(* ram_style = "block" *)reg[311:0]result23_memory[0:511];
wire task_writes_result01=issue_valid&&(
 (issue_kind==TASK_SAME0)||(issue_kind==TASK_SAME_PAIR)||
 (issue_kind==TASK_CROSS_A));
wire task_writes_result23=issue_valid&&(
 (issue_kind==TASK_SAME0)||(issue_kind==TASK_CROSS_NORMAL)||
 (issue_kind==TASK_CROSS_B));
always@(posedge clk)begin
 if(task_writes_result01)
  result01_memory[issue_address]<=task_result_pack;
 if(task_writes_result23)
  result23_memory[issue_address]<=task_result_pack;
end

function automatic[8:0]result01_slot;
 input[8:0]address;
 reg[7:0]beat;
 begin
  beat=address[7:0];
  if(beat==8'd0)
   result01_slot=address;
  else if(beat==8'd254)
   result01_slot=address[8]?address:(address+9'd256);
  else if((beat[1:0]==2'd1)||(beat[1:0]==2'd2))
   result01_slot=address+9'd2;
  else
   result01_slot=address;
 end
endfunction

function automatic result01_second_half;
 input[8:0]address;
 reg[7:0]beat;
 begin
  beat=address[7:0];
  if(beat==8'd0)
   result01_second_half=1'b0;
  else if(beat==8'd254)
   result01_second_half=address[8];
  else
   result01_second_half=
    !((beat[1:0]==2'd1)||(beat[1:0]==2'd2));
 end
endfunction

function automatic[8:0]result23_slot;
 input[8:0]address;
 begin
  if(address[7:0]==8'd0)
   result23_slot=address;
  else if(!address[8])
   result23_slot=address+9'd256;
  else
   result23_slot=address;
 end
endfunction

function automatic result23_second_half;
 input[8:0]address;
 begin
  result23_second_half=
   (address[7:0]==8'd0)?1'b1:address[8];
 end
endfunction

reg[FIXED_DELAY_CYCLES-1:0]valid_delay,last_delay;
reg[8:0]address_delay[0:FIXED_DELAY_CYCLES-1];
wire[8:0]prefetch_source_address=
 address_delay[FIXED_DELAY_CYCLES-2];
wire[8:0]prefetch_slot01=result01_slot(prefetch_source_address);
wire[8:0]prefetch_slot23=result23_slot(prefetch_source_address);
reg[311:0]result01_read_data,result23_read_data;

// Synchronous result-bank reads.  The bypass gives deterministic write-first
// behavior without relying on a vendor RAM collision mode.
always@(posedge clk)begin
 if(rst)begin
  result01_read_data<=0;
  result23_read_data<=0;
 end else if(valid_delay[FIXED_DELAY_CYCLES-2])begin
  if(task_writes_result01&&(issue_address==prefetch_slot01))
   result01_read_data<=task_result_pack;
  else
   result01_read_data<=result01_memory[prefetch_slot01];
  if(task_writes_result23&&(issue_address==prefetch_slot23))
   result23_read_data<=task_result_pack;
  else
   result23_read_data<=result23_memory[prefetch_slot23];
 end
end

wire[8:0]emit_source_address=
 address_delay[FIXED_DELAY_CYCLES-1];
wire[8:0]emit_slot01=result01_slot(emit_source_address);
wire[8:0]emit_slot23=result23_slot(emit_source_address);
wire emit_uses_current01=
 task_writes_result01&&(issue_address==emit_slot01);
wire emit_uses_current23=
 task_writes_result23&&(issue_address==emit_slot23);
wire[311:0]emit_pack01=
 emit_uses_current01?task_result_pack:result01_read_data;
wire[311:0]emit_pack23=
 emit_uses_current23?task_result_pack:result23_read_data;
wire emit_second01=result01_second_half(emit_source_address);
wire emit_second23=result23_second_half(emit_source_address);
wire[77:0]emit_selected0=
 emit_second01?emit_pack01[155:78]:emit_pack01[311:234];
wire[77:0]emit_selected1=
 emit_second01?emit_pack01[77:0]:emit_pack01[233:156];
wire[77:0]emit_selected2=
 emit_second23?emit_pack23[155:78]:emit_pack23[311:234];
wire[77:0]emit_selected3=
 emit_second23?emit_pack23[77:0]:emit_pack23[233:156];

reg[77:0]emit_code0,emit_code1,emit_code2,emit_code3;
integer delay_index_v3;
always@(posedge clk)begin
 if(rst)begin
  source_address<=0;
  valid_delay<=0;
  last_delay<=0;
  out_valid<=0;
  out_last<=0;
  emit_code0<=0;emit_code1<=0;emit_code2<=0;emit_code3<=0;
  for(delay_index_v3=0;delay_index_v3<FIXED_DELAY_CYCLES;
      delay_index_v3=delay_index_v3+1)
   address_delay[delay_index_v3]<=0;
 end else begin
  out_valid<=valid_delay[FIXED_DELAY_CYCLES-1];
  out_last<=last_delay[FIXED_DELAY_CYCLES-1];
  valid_delay<={valid_delay[FIXED_DELAY_CYCLES-2:0],in_valid};
  last_delay<={last_delay[FIXED_DELAY_CYCLES-2:0],in_valid&&in_last};
  address_delay[0]<=source_address;
  for(delay_index_v3=1;delay_index_v3<FIXED_DELAY_CYCLES;
      delay_index_v3=delay_index_v3+1)
   address_delay[delay_index_v3]<=address_delay[delay_index_v3-1];
  if(in_valid)
   source_address<=source_address+1'b1;
  if(valid_delay[FIXED_DELAY_CYCLES-1])begin
   emit_code0<=emit_selected0;emit_code1<=emit_selected1;
   emit_code2<=emit_selected2;emit_code3<=emit_selected3;
  end
 end
end

wire[69:0]emit_data0,emit_data1,emit_data2,emit_data3;
wire[3:0]emit_detected,emit_corrected;
secded_decode70 emit_dec0(emit_code0,emit_data0,emit_detected[0],emit_corrected[0]);
secded_decode70 emit_dec1(emit_code1,emit_data1,emit_detected[1],emit_corrected[1]);
secded_decode70 emit_dec2(emit_code2,emit_data2,emit_detected[2],emit_corrected[2]);
secded_decode70 emit_dec3(emit_code3,emit_data3,emit_detected[3],emit_corrected[3]);
assign out0_re=emit_data0[69:35];assign out0_im=emit_data0[34:0];
assign out1_re=emit_data1[69:35];assign out1_im=emit_data1[34:0];
assign out2_re=emit_data2[69:35];assign out2_im=emit_data2[34:0];
assign out3_re=emit_data3[69:35];assign out3_im=emit_data3[34:0];
wire _keep_v3=queue_overflow^issue_urgent_direct^op_exp1[0]^op_exp3[0]^
 (BACKGROUND_PREISSUE_CAPACITY==129)^
 ^task_detected^ ^task_corrected^ ^emit_detected^ ^emit_corrected;
endmodule


// Exchanged Stage 9 has two generic lanes (1 and 3); lanes 0 and 2 are
// specialized to trivial rotations.  A single output register is used here.
// Together with the single-register Stage 10 this recovers the two cycles
// added by the 258-cycle Stage-8 scheduler versus the old 256-cycle buffer.
(* keep_hierarchy = "yes" *) module p1_pfft_stage9_exchange_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output reg out_valid,output reg out_last,
 output reg signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
reg[7:0]beat_count;
wire signed[34:0]s02r=in0_re+in2_re,s02i=in0_im+in2_im;
wire signed[34:0]d02r=in0_re-in2_re,d02i=in0_im-in2_im;
wire signed[34:0]s13r=in1_re+in3_re,s13i=in1_im+in3_im;
wire signed[34:0]d13r=in1_re-in3_re,d13i=in1_im-in3_im;
wire signed[34:0]b0r=s02r>>>1,b0i=s02i>>>1;
wire signed[34:0]b1r=s13r>>>1,b1i=s13i>>>1;
wire signed[34:0]b2r=d02r>>>1,b2i=d02i>>>1;
wire signed[34:0]b3r=d13r>>>1,b3i=d13i>>>1;
wire[9:0]e0,e1,e2,e3;
pfft_phi_calc #(.STAGE(9))p0({beat_count,2'd0},e0);
pfft_phi_calc #(.STAGE(9))p1({beat_count,2'd1},e1);
pfft_phi_calc #(.STAGE(9))p2({beat_count,2'd2},e2);
pfft_phi_calc #(.STAGE(9))p3({beat_count,2'd3},e3);
wire signed[34:0]r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i;
fft_complex_rotate_trivial_1024 rot0(b0r,b0i,e0,r0r,r0i);
fft_complex_mul_q28 rot1(b1r,b1i,e1,r1r,r1i);
fft_complex_rotate_trivial_1024 rot2(b2r,b2i,e2,r2r,r2i);
fft_complex_mul_q28 rot3(b3r,b3i,e3,r3r,r3i);
always@(posedge clk)begin
 if(rst)begin
  beat_count<=0;out_valid<=0;out_last<=0;
  out0_re<=0;out0_im<=0;out1_re<=0;out1_im<=0;
  out2_re<=0;out2_im<=0;out3_re<=0;out3_im<=0;
 end else begin
  out_valid<=in_valid;out_last<=in_valid&&in_last;
  if(in_valid)begin
   beat_count<=beat_count+1'b1;
   out0_re<=r0r;out0_im<=r0i;out1_re<=r1r;out1_im<=r1i;
   out2_re<=r2r;out2_im<=r2i;out3_re<=r3r;out3_im<=r3i;
  end
 end
end
endmodule


(* keep_hierarchy = "yes" *) module p1_pfft_stage10_single_cycle_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output reg out_valid,output reg out_last,
 output reg signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire signed[34:0]s01r=in0_re+in1_re,s01i=in0_im+in1_im;
wire signed[34:0]d01r=in0_re-in1_re,d01i=in0_im-in1_im;
wire signed[34:0]s23r=in2_re+in3_re,s23i=in2_im+in3_im;
wire signed[34:0]d23r=in2_re-in3_re,d23i=in2_im-in3_im;
always@(posedge clk)begin
 if(rst)begin
  out_valid<=0;out_last<=0;
  out0_re<=0;out0_im<=0;out1_re<=0;out1_im<=0;
  out2_re<=0;out2_im<=0;out3_re<=0;out3_im<=0;
 end else begin
  out_valid<=in_valid;out_last<=in_valid&&in_last;
  if(in_valid)begin
   out0_re<=s01r>>>1;out0_im<=s01i>>>1;
   out1_re<=d01r>>>1;out1_im<=d01i>>>1;
   out2_re<=s23r>>>1;out2_im<=s23i>>>1;
   out3_re<=d23r>>>1;out3_im<=d23i>>>1;
  end
 end
end
endmodule


(* keep_hierarchy = "yes" *) module p1_tmr_pfft_stage9_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;
wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];
genvar g9;
generate for(g9=0;g9<3;g9=g9+1)begin:replicas
 (* keep = "true" *)p1_pfft_stage9_exchange_v3 u(
  clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
  in2_re,in2_im,in3_re,in3_im,v[g9],l[g9],
  r0[g9],i0[g9],r1[g9],i1[g9],r2[g9],i2[g9],r3[g9],i3[g9]);
end endgenerate
vote35 q0r(r0[0],r0[1],r0[2],out0_re);vote35 q0i(i0[0],i0[1],i0[2],out0_im);
vote35 q1r(r1[0],r1[1],r1[2],out1_re);vote35 q1i(i1[0],i1[1],i1[2],out1_im);
vote35 q2r(r2[0],r2[1],r2[2],out2_re);vote35 q2i(i2[0],i2[1],i2[2],out2_im);
vote35 q3r(r3[0],r3[1],r3[2],out3_re);vote35 q3i(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);
assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule


(* keep_hierarchy = "yes" *) module p1_tmr_pfft_stage10_v3(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;
wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];
genvar g10;
generate for(g10=0;g10<3;g10=g10+1)begin:replicas
 (* keep = "true" *)p1_pfft_stage10_single_cycle_v3 u(
  clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
  in2_re,in2_im,in3_re,in3_im,v[g10],l[g10],
  r0[g10],i0[g10],r1[g10],i1[g10],r2[g10],i2[g10],r3[g10],i3[g10]);
end endgenerate
vote35 q0r(r0[0],r0[1],r0[2],out0_re);vote35 q0i(i0[0],i0[1],i0[2],out0_im);
vote35 q1r(r1[0],r1[1],r1[2],out1_re);vote35 q1i(i1[0],i1[1],i1[2],out1_im);
vote35 q2r(r2[0],r2[1],r2[2],out2_re);vote35 q2i(i2[0],i2[1],i2[2],out2_im);
vote35 q3r(r3[0],r3[1],r3[2],out3_re);vote35 q3i(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);
assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule


// P1-RTL-V4-001 Stage 8 boundary: triplicate the complete functional stage.
// The legacy single-check-pair scheduler remains in this source only as
// historical V3 provenance and is not reachable from the V4 top-level.
(* keep_hierarchy = "yes" *) module p1_tmr_pfft_stage8_v4(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[2:0]v,l;
wire signed[34:0]r0[0:2],i0[0:2],r1[0:2],i1[0:2],r2[0:2],i2[0:2],r3[0:2],i3[0:2];
wire signed[34:0]oa0r[0:2],oa0i[0:2],oa1r[0:2],oa1i[0:2],oa2r[0:2],oa2i[0:2],oa3r[0:2],oa3i[0:2];
wire signed[34:0]ob0r[0:2],ob0i[0:2],ob1r[0:2],ob1i[0:2],ob2r[0:2],ob2i[0:2],ob3r[0:2],ob3i[0:2];
wire[9:0]oe0[0:2],oe1[0:2],oe2[0:2],oe3[0:2];
wire obranch[0:2];
genvar g8;
generate for(g8=0;g8<3;g8=g8+1)begin:replicas
 (* keep = "true" *)p1_stage8_functional_v3 u(
  clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
  in2_re,in2_im,in3_re,in3_im,v[g8],l[g8],
  r0[g8],i0[g8],r1[g8],i1[g8],r2[g8],i2[g8],r3[g8],i3[g8],
  oa0r[g8],oa0i[g8],oa1r[g8],oa1i[g8],oa2r[g8],oa2i[g8],oa3r[g8],oa3i[g8],
  ob0r[g8],ob0i[g8],ob1r[g8],ob1i[g8],ob2r[g8],ob2i[g8],ob3r[g8],ob3i[g8],
  oe0[g8],oe1[g8],oe2[g8],oe3[g8],obranch[g8]);
end endgenerate
vote35 q0r(r0[0],r0[1],r0[2],out0_re);vote35 q0i(i0[0],i0[1],i0[2],out0_im);
vote35 q1r(r1[0],r1[1],r1[2],out1_re);vote35 q1i(i1[0],i1[1],i1[2],out1_im);
vote35 q2r(r2[0],r2[1],r2[2],out2_re);vote35 q2i(i2[0],i2[1],i2[2],out2_im);
vote35 q3r(r3[0],r3[1],r3[2],out3_re);vote35 q3i(i3[0],i3[1],i3[2],out3_im);
assign out_valid=(v[0]&v[1])|(v[0]&v[2])|(v[1]&v[2]);
assign out_last=(l[0]&l[1])|(l[0]&l[2])|(l[1]&l[2]);
endmodule


// Four Stage-10 butterflies are collected from two adjacent four-lane beats.
// Four A operands and four B operands are encoded independently before six
// complete butterfly operators.  Upper and lower results have separate
// arithmetic correction boundaries and are serialized back into two beats.
(* keep_hierarchy = "yes" *) module p1_stage10_two_beat_ecc_v4(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output reg out_valid,output reg out_last,
 output reg signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
reg pair_phase;
reg signed[34:0]a0r,a0i,b0r,b0i,a1r,a1i,b1r,b1i;
reg pending_valid,pending_last;
reg signed[34:0]pending0_re,pending0_im,pending1_re,pending1_im;
reg signed[34:0]pending2_re,pending2_im,pending3_re,pending3_im;

wire signed[34:0]u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i;
wire signed[34:0]l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i;
(* keep = "true" *) independent_butterfly_ecc_v5 #(
 .TRIVIAL_UPPER(1),.BYPASS_LOWER(1)
) four_butterfly_codeword(
 a0r,a0i,a1r,a1i,in0_re,in0_im,in2_re,in2_im,
 b0r,b0i,b1r,b1i,in1_re,in1_im,in3_re,in3_im,
 10'd0,10'd0,
 u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,
 l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i
);

always@(posedge clk)begin
 if(rst)begin
  pair_phase<=0;pending_valid<=0;pending_last<=0;
  out_valid<=0;out_last<=0;
  a0r<=0;a0i<=0;b0r<=0;b0i<=0;a1r<=0;a1i<=0;b1r<=0;b1i<=0;
  pending0_re<=0;pending0_im<=0;pending1_re<=0;pending1_im<=0;
  pending2_re<=0;pending2_im<=0;pending3_re<=0;pending3_im<=0;
  out0_re<=0;out0_im<=0;out1_re<=0;out1_im<=0;
  out2_re<=0;out2_im<=0;out3_re<=0;out3_im<=0;
 end else begin
  out_valid<=0;out_last<=0;
  if(pending_valid)begin
   out_valid<=1;out_last<=pending_last;pending_valid<=0;
   out0_re<=pending0_re;out0_im<=pending0_im;
   out1_re<=pending1_re;out1_im<=pending1_im;
   out2_re<=pending2_re;out2_im<=pending2_im;
   out3_re<=pending3_re;out3_im<=pending3_im;
  end
  if(in_valid)begin
   if(!pair_phase)begin
    a0r<=in0_re;a0i<=in0_im;b0r<=in1_re;b0i<=in1_im;
    a1r<=in2_re;a1i<=in2_im;b1r<=in3_re;b1i<=in3_im;
    pair_phase<=1;
   end else begin
    pair_phase<=0;
    out_valid<=1;out_last<=0;
    out0_re<=u0r;out0_im<=u0i;out1_re<=l0r;out1_im<=l0i;
    out2_re<=u1r;out2_im<=u1i;out3_re<=l1r;out3_im<=l1i;
    pending_valid<=1;pending_last<=in_last;
    pending0_re<=u2r;pending0_im<=u2i;pending1_re<=l2r;pending1_im<=l2i;
    pending2_re<=u3r;pending2_im<=u3i;pending3_re<=l3r;pending3_im<=l3i;
   end
  end
 end
end
endmodule


(* keep_hierarchy = "yes" *) module p1_pfft_ecc_core_v4(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire[11:0]v,l;
wire signed[34:0]r0[0:11],i0[0:11],r1[0:11],i1[0:11],r2[0:11],i2[0:11],r3[0:11],i3[0:11];
assign v[0]=in_valid;assign l[0]=in_last;
assign r0[0]=in0_re;assign i0[0]=in0_im;assign r1[0]=in1_re;assign i1[0]=in1_im;
assign r2[0]=in2_re;assign i2[0]=in2_im;assign r3[0]=in3_re;assign i3[0]=in3_im;
p1_ecc_stage4_v3 #(.DEPTH(128),.STAGE(1))s1(clk,rst,v[0],l[0],r0[0],i0[0],r1[0],i1[0],r2[0],i2[0],r3[0],i3[0],v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1]);
p1_ecc_stage4_v3 #(.DEPTH(64),.STAGE(2))s2(clk,rst,v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2]);
p1_ecc_stage4_v3 #(.DEPTH(32),.STAGE(3))s3(clk,rst,v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3]);
p1_ecc_stage4_v3 #(.DEPTH(16),.STAGE(4))s4(clk,rst,v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4]);
p1_ecc_stage4_v3 #(.DEPTH(8),.STAGE(5))s5(clk,rst,v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5]);
p1_ecc_stage4_v3 #(.DEPTH(4),.STAGE(6))s6(clk,rst,v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6]);
p1_ecc_stage4_v3 #(.DEPTH(2),.STAGE(7))s7(clk,rst,v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7]);

p1_tmr_pfft_stage8_v4 s8(
 clk,rst,v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],
 v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8]);
p1_tmr_pfft_stage9_v3 s9(
 clk,rst,v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8],
 v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10]);
p1_stage10_two_beat_ecc_v4 s10(
 clk,rst,v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10],
 v[11],l[11],r0[11],i0[11],r1[11],i1[11],r2[11],i2[11],r3[11],i3[11]);
assign out_valid=v[11];assign out_last=l[11];
assign out0_re=r0[11];assign out0_im=i0[11];
assign out1_re=r1[11];assign out1_im=i1[11];
assign out2_re=r2[11];assign out2_im=i2[11];
assign out3_re=r3[11];assign out3_im=i3[11];
endmodule


module top_p1_pfft_ecc(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
p1_pfft_ecc_core_v4 u(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
 in2_re,in2_im,in3_re,in3_im,out_valid,out_last,
 out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);
endmodule
