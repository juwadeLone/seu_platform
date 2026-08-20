`timescale 1ns/1ps

// ============================================================================
// SC-01: P1 Gao-threshold / fault-injection versions (added 2026-08-10).
// P1 stages 1-7 (p1_ecc_stage4_v3) wire arithmetic_boundary_from_clean_v5
// correctly (clean->c ports, received->r ports); these thresholded copies add
// a fault-injection hook on the received path and expose the corrector flags.
// P1 stage 10 (p1_stage10_two_beat_ecc_v4) instantiates the ORIGINAL
// independent_butterfly_ecc_v5 whose boundary ports are reversed (the S3 bug);
// the thresholded copy uses independent_butterfly_ecc_v5_thresholded.
// ============================================================================

(* keep_hierarchy = "yes" *) module p1_ecc_stage4_v3_thresholded #(
 parameter integer DEPTH=128,
 parameter integer STAGE=1,
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
 output wire detected,corrected,uncorrectable,miscorrected,
 output wire [2:0] error_location
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
 wire signed[34:0]recv_inj_r=(inject_enable&&(inject_symbol==g)&&(inject_component==0))?(rotated_r[g]^(35'sd1<<inject_bit)):rotated_r[g];
 wire signed[34:0]recv_inj_i=(inject_enable&&(inject_symbol==g)&&(inject_component==1))?(rotated_i[g]^(35'sd1<<inject_bit)):rotated_i[g];
 assign received_r[g]=recv_inj_r;
 assign received_i[g]=recv_inj_i;
end endgenerate

wire signed[34:0]decoded0r,decoded0i,decoded1r,decoded1i;
wire signed[34:0]decoded2r,decoded2i,decoded3r,decoded3i;
arithmetic_boundary_from_clean_v5_thresholded #(.THRESHOLD(THRESHOLD)) arithmetic_boundary(
 rotated_r[0],rotated_i[0],rotated_r[1],rotated_i[1],
 rotated_r[2],rotated_i[2],rotated_r[3],rotated_i[3],
 rotated_r[4],rotated_i[4],rotated_r[5],rotated_i[5],
 received_r[0],received_i[0],received_r[1],received_i[1],
 received_r[2],received_i[2],received_r[3],received_i[3],
 received_r[4],received_i[4],received_r[5],received_i[5],
 decoded0r,decoded0i,decoded1r,decoded1i,
 decoded2r,decoded2i,decoded3r,decoded3i,
 detected,corrected,uncorrectable,miscorrected,error_location
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


// ---------------------------------------------------------------------------
// P1 stage 10: two-beat time-aligned [6,4,3] ECC with the thresholded
// independent butterfly (fixes the reversed boundary ports of the original).
// ---------------------------------------------------------------------------
(* keep_hierarchy = "yes" *) module p1_stage10_two_beat_ecc_v4_thresholded #(
 parameter integer THRESHOLD = 0
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
reg pair_phase;
reg signed[34:0]a0r,a0i,b0r,b0i,a1r,a1i,b1r,b1i;
reg pending_valid,pending_last;
reg signed[34:0]pending0_re,pending0_im,pending1_re,pending1_im;
reg signed[34:0]pending2_re,pending2_im,pending3_re,pending3_im;

wire signed[34:0]u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i;
wire signed[34:0]l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i;
(* keep = "true" *) independent_butterfly_ecc_v5_thresholded #(
 .TRIVIAL_UPPER(1),.BYPASS_LOWER(1),.THRESHOLD(THRESHOLD)
) four_butterfly_codeword(
 a0r,a0i,a1r,a1i,in0_re,in0_im,in2_re,in2_im,
 b0r,b0i,b1r,b1i,in1_re,in1_im,in3_re,in3_im,
 10'd0,10'd0,
 inject_enable,inject_symbol,inject_component,inject_bit,
 u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,
 l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i,
 up_detected,up_corrected,up_uncorrectable,up_miscorrected,up_error_location,
 lo_detected,lo_corrected,lo_uncorrectable,lo_miscorrected,lo_error_location
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


// ---------------------------------------------------------------------------
// P1 thresholded top: stages 1-7 thresholded (injection hook), stage 8/9 TMR
// unchanged, stage 10 thresholded (corrected boundary ports).
// ---------------------------------------------------------------------------
(* keep_hierarchy = "yes" *) module p1_pfft_ecc_core_v4_thresholded #(
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
 output wire det1,cor1,unc1,output wire[2:0]loc1,
 output wire det2,cor2,unc2,output wire[2:0]loc2,
 output wire det3,cor3,unc3,output wire[2:0]loc3,
 output wire det4,cor4,unc4,output wire[2:0]loc4,
 output wire det5,cor5,unc5,output wire[2:0]loc5,
 output wire det6,cor6,unc6,output wire[2:0]loc6,
 output wire det7,cor7,unc7,output wire[2:0]loc7,
 output wire s10up_det,s10up_cor,s10up_unc,output wire[2:0]s10up_loc,
 output wire s10lo_det,s10lo_cor,s10lo_unc,output wire[2:0]s10lo_loc
);
wire[11:0]v,l;
wire signed[34:0]r0[0:11],i0[0:11],r1[0:11],i1[0:11],r2[0:11],i2[0:11],r3[0:11],i3[0:11];
assign v[0]=in_valid;assign l[0]=in_last;
assign r0[0]=in0_re;assign i0[0]=in0_im;assign r1[0]=in1_re;assign i1[0]=in1_im;
assign r2[0]=in2_re;assign i2[0]=in2_im;assign r3[0]=in3_re;assign i3[0]=in3_im;
p1_ecc_stage4_v3_thresholded #(.DEPTH(128),.STAGE(1),.THRESHOLD(THRESHOLD))s1(
 clk,rst,v[0],l[0],r0[0],i0[0],r1[0],i1[0],r2[0],i2[0],r3[0],i3[0],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],
 det1,cor1,unc1,misc1_unused,loc1);
p1_ecc_stage4_v3_thresholded #(.DEPTH(64),.STAGE(2),.THRESHOLD(THRESHOLD))s2(
 clk,rst,v[1],l[1],r0[1],i0[1],r1[1],i1[1],r2[1],i2[1],r3[1],i3[1],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],
 det2,cor2,unc2,misc2_unused,loc2);
p1_ecc_stage4_v3_thresholded #(.DEPTH(32),.STAGE(3),.THRESHOLD(THRESHOLD))s3(
 clk,rst,v[2],l[2],r0[2],i0[2],r1[2],i1[2],r2[2],i2[2],r3[2],i3[2],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],
 det3,cor3,unc3,misc3_unused,loc3);
p1_ecc_stage4_v3_thresholded #(.DEPTH(16),.STAGE(4),.THRESHOLD(THRESHOLD))s4(
 clk,rst,v[3],l[3],r0[3],i0[3],r1[3],i1[3],r2[3],i2[3],r3[3],i3[3],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],
 det4,cor4,unc4,misc4_unused,loc4);
p1_ecc_stage4_v3_thresholded #(.DEPTH(8),.STAGE(5),.THRESHOLD(THRESHOLD))s5(
 clk,rst,v[4],l[4],r0[4],i0[4],r1[4],i1[4],r2[4],i2[4],r3[4],i3[4],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],
 det5,cor5,unc5,misc5_unused,loc5);
p1_ecc_stage4_v3_thresholded #(.DEPTH(4),.STAGE(6),.THRESHOLD(THRESHOLD))s6(
 clk,rst,v[5],l[5],r0[5],i0[5],r1[5],i1[5],r2[5],i2[5],r3[5],i3[5],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],
 det6,cor6,unc6,misc6_unused,loc6);
p1_ecc_stage4_v3_thresholded #(.DEPTH(2),.STAGE(7),.THRESHOLD(THRESHOLD))s7(
 clk,rst,v[6],l[6],r0[6],i0[6],r1[6],i1[6],r2[6],i2[6],r3[6],i3[6],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],
 det7,cor7,unc7,misc7_unused,loc7);

p1_tmr_pfft_stage8_v4 s8(
 clk,rst,v[7],l[7],r0[7],i0[7],r1[7],i1[7],r2[7],i2[7],r3[7],i3[7],
 v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8]);
p1_tmr_pfft_stage9_v3 s9(
 clk,rst,v[8],l[8],r0[8],i0[8],r1[8],i1[8],r2[8],i2[8],r3[8],i3[8],
 v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10]);
p1_stage10_two_beat_ecc_v4_thresholded #(.THRESHOLD(THRESHOLD))s10(
 clk,rst,v[10],l[10],r0[10],i0[10],r1[10],i1[10],r2[10],i2[10],r3[10],i3[10],
 inject_enable,inject_symbol,inject_component,inject_bit,
 v[11],l[11],r0[11],i0[11],r1[11],i1[11],r2[11],i2[11],r3[11],i3[11],
 s10up_det,s10up_cor,s10up_unc,s10up_misc_unused,s10up_loc,
 s10lo_det,s10lo_cor,s10lo_unc,s10lo_misc_unused,s10lo_loc);
assign out_valid=v[11];assign out_last=l[11];
assign out0_re=r0[11];assign out0_im=i0[11];
assign out1_re=r1[11];assign out1_im=i1[11];
assign out2_re=r2[11];assign out2_im=i2[11];
assign out3_re=r3[11];assign out3_im=i3[11];
endmodule

module top_p1_pfft_ecc_thresholded #(
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
 output wire det1,cor1,unc1,output wire[2:0]loc1,
 output wire det2,cor2,unc2,output wire[2:0]loc2,
 output wire det3,cor3,unc3,output wire[2:0]loc3,
 output wire det4,cor4,unc4,output wire[2:0]loc4,
 output wire det5,cor5,unc5,output wire[2:0]loc5,
 output wire det6,cor6,unc6,output wire[2:0]loc6,
 output wire det7,cor7,unc7,output wire[2:0]loc7,
 output wire s10up_det,s10up_cor,s10up_unc,output wire[2:0]s10up_loc,
 output wire s10lo_det,s10lo_cor,s10lo_unc,output wire[2:0]s10lo_loc
);
p1_pfft_ecc_core_v4_thresholded #(.THRESHOLD(THRESHOLD)) u(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
 in2_re,in2_im,in3_re,in3_im,
 inject_enable,inject_symbol,inject_component,inject_bit,
 out_valid,out_last,
 out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 det1,cor1,unc1,loc1,
 det2,cor2,unc2,loc2,
 det3,cor3,unc3,loc3,
 det4,cor4,unc4,loc4,
 det5,cor5,unc5,loc5,
 det6,cor6,unc6,loc6,
 det7,cor7,unc7,loc7,
 s10up_det,s10up_cor,s10up_unc,s10up_loc,
 s10lo_det,s10lo_cor,s10lo_unc,s10lo_loc
);
endmodule
