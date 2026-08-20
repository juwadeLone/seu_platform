`timescale 1ns/1ps
// Isolated S1 DUT: per-stage XOR on 7 SDF lanes + K_S1-style H*received
// thresholded Gao decoder. Does not modify K_S1 or projects/S1.

module gao_corrector_743_thresholded_mid #(
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

module subfft_lane8_injectable(
 input wire clk,input wire rst,input wire valid,
 input wire signed[34:0]in_re,in_im,
 input wire inject_enable,
 input wire [3:0]inject_stage,
 input wire inject_component,
 input wire [5:0]inject_bit,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out_re,out_im,
 output wire [7:0] stage_out_valid
);
 wire signed[34:0] raw_r[1:8], raw_i[1:8], fwd_r[0:8], fwd_i[0:8];
 wire raw_v[0:8], raw_l[1:8];
 assign fwd_r[0]=in_re; assign fwd_i[0]=in_im;
 assign raw_v[0]=valid;
 genvar k;
 generate
  for(k=1;k<=8;k=k+1) begin:inj
   localparam integer DEPTH = (k==1)?128:(k==2)?64:(k==3)?32:(k==4)?16:(k==5)?8:(k==6)?4:(k==7)?2:1;
   r2sdf_lane_subfft_v5 #(.DEPTH(DEPTH),.STAGE(k)) st(
    clk,rst,raw_v[k-1],
    fwd_r[k-1],fwd_i[k-1],
    raw_v[k],raw_l[k],raw_r[k],raw_i[k]
   );
   assign fwd_r[k]=(inject_enable&&(inject_stage==k[3:0])&&(inject_component==1'b0))
                    ?(raw_r[k]^(35'sd1<<inject_bit)):raw_r[k];
   assign fwd_i[k]=(inject_enable&&(inject_stage==k[3:0])&&(inject_component==1'b1))
                    ?(raw_i[k]^(35'sd1<<inject_bit)):raw_i[k];
   assign stage_out_valid[k-1]=raw_v[k];
  end
 endgenerate
 assign out_valid=raw_v[8]; assign out_last=raw_l[8];
 assign out_re=fwd_r[8]; assign out_im=fwd_i[8];
endmodule

module top_s1_midstage_thresholded #(
 parameter integer THRESHOLD = 0
)(
 input wire clk,input wire rst,input wire in_valid,input wire in_last,
 input wire signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 input wire inject_enable,
 input wire [2:0]inject_path,
 input wire [3:0]inject_stage,
 input wire inject_component,
 input wire [5:0]inject_bit,
 output wire out_valid,output wire out_last,
 output wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im,
 output wire detected,output wire corrected,output wire uncorrectable,
 output wire [2:0] error_location,
 output wire inject_window
);
wire signed[34:0]a01r=in0_re+in1_re,a01i=in0_im+in1_im;
wire signed[34:0]a02r=in0_re+in2_re,a02i=in0_im+in2_im;
wire signed[34:0]a12r=in1_re+in2_re,a12i=in1_im+in2_im;
wire signed[34:0]p0r=-(a01r+in3_re),p0i=-(a01i+in3_im);
wire signed[34:0]p1r=-(a02r+in3_re),p1i=-(a02i+in3_im);
wire signed[34:0]p3r=-(a12r+in3_re),p3i=-(a12i+in3_im);
wire signed[34:0]pr[0:6],pi[0:6],pathr[0:6],pathi[0:6];
wire[6:0]pv,pl;
wire [7:0] stage_v[0:6];
assign pr[0]=p0r;assign pi[0]=p0i;assign pr[1]=p1r;assign pi[1]=p1i;
assign pr[2]=in0_re;assign pi[2]=in0_im;assign pr[3]=p3r;assign pi[3]=p3i;
assign pr[4]=in1_re;assign pi[4]=in1_im;assign pr[5]=in2_re;assign pi[5]=in2_im;
assign pr[6]=in3_re;assign pi[6]=in3_im;
genvar x;
generate for(x=0;x<7;x=x+1) begin:paths
 wire this_en = inject_enable && (inject_path==x[2:0]);
 subfft_lane8_injectable u(
  clk,rst,in_valid,pr[x],pi[x],
  this_en,inject_stage,inject_component,inject_bit,
  pv[x],pl[x],pathr[x],pathi[x],stage_v[x]
 );
end endgenerate
assign inject_window = (inject_stage>=4'd1)&&(inject_stage<=4'd8)
                       ? stage_v[inject_path][inject_stage-1] : 1'b0;

wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i;
gao_corrector_743_thresholded_mid #(.THRESHOLD(THRESHOLD)) u_corrector(
 pathr[0],pathi[0],pathr[1],pathi[1],pathr[2],pathi[2],pathr[3],pathi[3],
 pathr[4],pathi[4],pathr[5],pathi[5],pathr[6],pathi[6],
 39'sd0,39'sd0,39'sd0,39'sd0,39'sd0,39'sd0,
 d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 detected,corrected,uncorrectable,error_location
);
wire v9,l9;wire signed[34:0]s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i;
tmr_subfft_stage9_v5 s9(clk,rst,pv[0],pl[0],d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,v9,l9,s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i);
tmr_subfft_stage10_v5 s10(clk,rst,v9,l9,s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i,out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);
wire _unused=in_last;
endmodule
