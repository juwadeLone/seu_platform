`timescale 1ns/1ps

// S1-owned complete eight-stage SubFFT path.
module subfft_lane8_v5(
 input wire clk,input wire rst,input wire valid,input wire signed[34:0]in_re,in_im,
 output wire out_valid,output wire out_last,output wire signed[34:0]out_re,out_im
);
wire[8:0]v,l;wire signed[34:0]r[0:8],i[0:8];assign v[0]=valid;assign r[0]=in_re;assign i[0]=in_im;
r2sdf_lane_subfft_v5 #(.DEPTH(128),.STAGE(1))a(clk,rst,v[0],r[0],i[0],v[1],l[1],r[1],i[1]);
r2sdf_lane_subfft_v5 #(.DEPTH(64),.STAGE(2))b(clk,rst,v[1],r[1],i[1],v[2],l[2],r[2],i[2]);
r2sdf_lane_subfft_v5 #(.DEPTH(32),.STAGE(3))c(clk,rst,v[2],r[2],i[2],v[3],l[3],r[3],i[3]);
r2sdf_lane_subfft_v5 #(.DEPTH(16),.STAGE(4))d(clk,rst,v[3],r[3],i[3],v[4],l[4],r[4],i[4]);
r2sdf_lane_subfft_v5 #(.DEPTH(8),.STAGE(5))e(clk,rst,v[4],r[4],i[4],v[5],l[5],r[5],i[5]);
r2sdf_lane_subfft_v5 #(.DEPTH(4),.STAGE(6))f(clk,rst,v[5],r[5],i[5],v[6],l[6],r[6],i[6]);
r2sdf_lane_subfft_v5 #(.DEPTH(2),.STAGE(7))g(clk,rst,v[6],r[6],i[6],v[7],l[7],r[7],i[7]);
r2sdf_lane_subfft_v5 #(.DEPTH(1),.STAGE(8))h(clk,rst,v[7],r[7],i[7],v[8],l[8],r[8],i[8]);
assign out_valid=v[8];assign out_last=l[8];assign out_re=r[8];assign out_im=i[8];
endmodule

module top_s1_gao_subfft_ecc(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
wire signed[34:0]a01r=in0_re+in1_re,a01i=in0_im+in1_im,a02r=in0_re+in2_re,a02i=in0_im+in2_im,a12r=in1_re+in2_re,a12i=in1_im+in2_im;
wire signed[34:0]p0r=-(a01r+in3_re),p0i=-(a01i+in3_im),p1r=-(a02r+in3_re),p1i=-(a02i+in3_im),p3r=-(a12r+in3_re),p3i=-(a12i+in3_im);
wire signed[34:0]pr[0:6],pi[0:6],pathr[0:6],pathi[0:6];wire[6:0]pv,pl;
assign pr[0]=p0r;assign pi[0]=p0i;assign pr[1]=p1r;assign pi[1]=p1i;assign pr[2]=in0_re;assign pi[2]=in0_im;assign pr[3]=p3r;assign pi[3]=p3i;assign pr[4]=in1_re;assign pi[4]=in1_im;assign pr[5]=in2_re;assign pi[5]=in2_im;assign pr[6]=in3_re;assign pi[6]=in3_im;
genvar x;generate for(x=0;x<7;x=x+1)begin:paths (* keep = "true" *) subfft_lane8_v5 u(clk,rst,in_valid,pr[x],pi[x],pv[x],pl[x],pathr[x],pathi[x]);end endgenerate
(* keep = "true" *)wire signed[34:0]received_path_r[0:6],received_path_i[0:6];genvar y;
generate for(y=0;y<7;y=y+1)begin:received_boundary assign received_path_r[y]=pathr[y];assign received_path_i[y]=pathi[y];end endgenerate
wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i;
gao_boundary_from_clean_v5 boundary(pathr[0],pathi[0],pathr[1],pathi[1],pathr[2],pathi[2],pathr[3],pathi[3],pathr[4],pathi[4],pathr[5],pathi[5],pathr[6],pathi[6],received_path_r[0],received_path_i[0],received_path_r[1],received_path_i[1],received_path_r[2],received_path_i[2],received_path_r[3],received_path_i[3],received_path_r[4],received_path_i[4],received_path_r[5],received_path_i[5],received_path_r[6],received_path_i[6],d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i);
wire v9,l9;wire signed[34:0]s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i;
tmr_subfft_stage9_v5 s9(clk,rst,pv[0],pl[0],d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,v9,l9,s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i);
tmr_subfft_stage10_v5 s10(clk,rst,v9,l9,s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i,out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);
wire _unused=in_last;
endmodule
