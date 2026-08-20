`timescale 1ns/1ps
// Isolated S1 Gao [7,4,3] thresholded decoder + received-path inject hook.
// Does not modify K_S1 or projects/S1 source. THRESHOLD=0 reduces to exact
// gao_corrector_743_v5.

module gao_corrector_743_thresholded #(
 parameter integer THRESHOLD = 0
)(
 input wire signed[34:0]p0r,p0i,p1r,p1i,p2r,p2i,p3r,p3i,p4r,p4i,p5r,p5i,p6r,p6i,
 input wire signed[38:0]res0r,res0i,res1r,res1i,res2r,res2i,
 output reg signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 output reg detected, output reg corrected, output reg uncorrectable,
 output reg [2:0] error_location
);
function [38:0] abs39;
 input signed [38:0] value;
 begin
  abs39 = value[38] ? (~value + 39'sd1) : value;
 end
endfunction
reg signed[38:0]s0r,s0i,s1r,s1i,s2r,s2i,er,ei;
reg[38:0]th;
reg found;
always @* begin
 s0r=$signed(p0r)+$signed(p2r)+$signed(p4r)+$signed(p6r)-res0r;
 s0i=$signed(p0i)+$signed(p2i)+$signed(p4i)+$signed(p6i)-res0i;
 s1r=$signed(p1r)+$signed(p2r)+$signed(p5r)+$signed(p6r)-res1r;
 s1i=$signed(p1i)+$signed(p2i)+$signed(p5i)+$signed(p6i)-res1i;
 s2r=$signed(p3r)+$signed(p4r)+$signed(p5r)+$signed(p6r)-res2r;
 s2i=$signed(p3i)+$signed(p4i)+$signed(p5i)+$signed(p6i)-res2i;
 d0r=p2r;d0i=p2i;d1r=p4r;d1i=p4i;d2r=p5r;d2i=p5i;d3r=p6r;d3i=p6i;
 detected=0;corrected=0;uncorrectable=0;error_location=0;found=0;er=0;ei=0;
 th=THRESHOLD;
 if((abs39(s0r)>th)||(abs39(s0i)>th)||(abs39(s1r)>th)||(abs39(s1i)>th)||(abs39(s2r)>th)||(abs39(s2i)>th)) begin
  detected=1;
  if((abs39(s0r)>th||abs39(s0i)>th)&&(abs39(s1r)<=th&&abs39(s1i)<=th)&&(abs39(s2r)<=th&&abs39(s2i)<=th)) begin
   found=1;error_location=0;er=s0r;ei=s0i;
  end else if((abs39(s1r)>th||abs39(s1i)>th)&&(abs39(s0r)<=th&&abs39(s0i)<=th)&&(abs39(s2r)<=th&&abs39(s2i)<=th)) begin
   found=1;error_location=1;er=s1r;ei=s1i;
  end else if((abs39(s0r-s1r)<=th)&&(abs39(s0i-s1i)<=th)&&(abs39(s2r)<=th&&abs39(s2i)<=th)) begin
   found=1;error_location=2;er=s0r;ei=s0i;
  end else if((abs39(s2r)>th||abs39(s2i)>th)&&(abs39(s0r)<=th&&abs39(s0i)<=th)&&(abs39(s1r)<=th&&abs39(s1i)<=th)) begin
   found=1;error_location=3;er=s2r;ei=s2i;
  end else if((abs39(s0r-s2r)<=th)&&(abs39(s0i-s2i)<=th)&&(abs39(s1r)<=th&&abs39(s1i)<=th)) begin
   found=1;error_location=4;er=s0r;ei=s0i;
  end else if((abs39(s1r-s2r)<=th)&&(abs39(s1i-s2i)<=th)&&(abs39(s0r)<=th&&abs39(s0i)<=th)) begin
   found=1;error_location=5;er=s1r;ei=s1i;
  end else if((abs39(s0r-s1r)<=th)&&(abs39(s0i-s1i)<=th)&&(abs39(s0r-s2r)<=th)&&(abs39(s0i-s2i)<=th)) begin
   found=1;error_location=6;er=s0r;ei=s0i;
  end
  if(found) begin
   corrected=1;
   case(error_location)
    2:begin d0r=p2r-er[34:0];d0i=p2i-ei[34:0];end
    4:begin d1r=p4r-er[34:0];d1i=p4i-ei[34:0];end
    5:begin d2r=p5r-er[34:0];d2i=p5i-ei[34:0];end
    6:begin d3r=p6r-er[34:0];d3i=p6i-ei[34:0];end
    default: ;
   endcase
  end else uncorrectable=1;
 end
end
endmodule

module gao_boundary_from_clean_v5_thresholded #(
 parameter integer THRESHOLD = 0
)(
 input wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,c4r,c4i,c5r,c5i,c6r,c6i,
 input wire signed[34:0]r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i,r4r,r4i,r5r,r5i,r6r,r6i,
 output wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 output wire detected, output wire corrected, output wire uncorrectable,
 output wire [2:0] error_location
);
(* keep = "true" *)wire signed[38:0]res0r=$signed(c0r)+$signed(c2r)+$signed(c4r)+$signed(c6r);
(* keep = "true" *)wire signed[38:0]res0i=$signed(c0i)+$signed(c2i)+$signed(c4i)+$signed(c6i);
(* keep = "true" *)wire signed[38:0]res1r=$signed(c1r)+$signed(c2r)+$signed(c5r)+$signed(c6r);
(* keep = "true" *)wire signed[38:0]res1i=$signed(c1i)+$signed(c2i)+$signed(c5i)+$signed(c6i);
(* keep = "true" *)wire signed[38:0]res2r=$signed(c3r)+$signed(c4r)+$signed(c5r)+$signed(c6r);
(* keep = "true" *)wire signed[38:0]res2i=$signed(c3i)+$signed(c4i)+$signed(c5i)+$signed(c6i);
gao_corrector_743_thresholded #(.THRESHOLD(THRESHOLD)) u_corrector(
 r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i,r4r,r4i,r5r,r5i,r6r,r6i,
 res0r,res0i,res1r,res1i,res2r,res2i,d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 detected,corrected,uncorrectable,error_location
);
endmodule

module top_s1_gao_subfft_ecc_thresholded #(
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
 output wire detected,output wire corrected,output wire uncorrectable,
 output wire [2:0] error_location
);
wire signed[34:0]a01r=in0_re+in1_re,a01i=in0_im+in1_im;
wire signed[34:0]a02r=in0_re+in2_re,a02i=in0_im+in2_im;
wire signed[34:0]a12r=in1_re+in2_re,a12i=in1_im+in2_im;
wire signed[34:0]p0r=-(a01r+in3_re),p0i=-(a01i+in3_im);
wire signed[34:0]p1r=-(a02r+in3_re),p1i=-(a02i+in3_im);
wire signed[34:0]p3r=-(a12r+in3_re),p3i=-(a12i+in3_im);
wire signed[34:0]pr[0:6],pi[0:6],pathr[0:6],pathi[0:6];
wire[6:0]pv,pl;
assign pr[0]=p0r;assign pi[0]=p0i;assign pr[1]=p1r;assign pi[1]=p1i;
assign pr[2]=in0_re;assign pi[2]=in0_im;assign pr[3]=p3r;assign pi[3]=p3i;
assign pr[4]=in1_re;assign pi[4]=in1_im;assign pr[5]=in2_re;assign pi[5]=in2_im;
assign pr[6]=in3_re;assign pi[6]=in3_im;
genvar x;
generate for(x=0;x<7;x=x+1)begin:paths
 (* keep = "true" *) subfft_lane8_v5 u(clk,rst,in_valid,pr[x],pi[x],pv[x],pl[x],pathr[x],pathi[x]);
end endgenerate

wire signed[34:0]received_path_r[0:6],received_path_i[0:6];
genvar y;
generate for(y=0;y<7;y=y+1)begin:received_boundary
 assign received_path_r[y]=(inject_enable&&(inject_symbol==y[2:0])&&(inject_component==1'b0))?(pathr[y]^(35'sd1<<inject_bit)):pathr[y];
 assign received_path_i[y]=(inject_enable&&(inject_symbol==y[2:0])&&(inject_component==1'b1))?(pathi[y]^(35'sd1<<inject_bit)):pathi[y];
end endgenerate

wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i;
gao_boundary_from_clean_v5_thresholded #(.THRESHOLD(THRESHOLD)) boundary(
 pathr[0],pathi[0],pathr[1],pathi[1],pathr[2],pathi[2],pathr[3],pathi[3],
 pathr[4],pathi[4],pathr[5],pathi[5],pathr[6],pathi[6],
 received_path_r[0],received_path_i[0],received_path_r[1],received_path_i[1],
 received_path_r[2],received_path_i[2],received_path_r[3],received_path_i[3],
 received_path_r[4],received_path_i[4],received_path_r[5],received_path_i[5],
 received_path_r[6],received_path_i[6],
 d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 detected,corrected,uncorrectable,error_location
);
wire v9,l9;wire signed[34:0]s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i;
tmr_subfft_stage9_v5 s9(clk,rst,pv[0],pl[0],d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,v9,l9,s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i);
tmr_subfft_stage10_v5 s10(clk,rst,v9,l9,s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i,out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);
wire _unused=in_last;
endmodule
