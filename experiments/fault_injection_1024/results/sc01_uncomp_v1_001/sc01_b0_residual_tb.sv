`timescale 1ns/1ps
// ============================================================================
// SC-01 方案B 步骤1: 无故障 raw syndrome 残差测量 TB (sc01_b0_residual_tb)
// 例化原版 top_s3_subfft_ecc（零注入），逐拍读取 8 个 ECC stage x 2 boundaries
// 的 raw syndrome（arithmetic_boundary_from_clean_v5 内 res0r/res0i/res1r/res1i，
// 无故障时 c/r 同值，res* == raw syndrome），输出 CSV 供统计 M。
// CSV 行格式: beat stage boundary res0r res0i res1r res1i
// ============================================================================
module sc01_b0_residual_tb;
localparam integer INPUT_BEATS = 2560;   // 10 frames x 256
reg clk=0,rst=1,in_valid=0,in_last=0;
reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
wire out_valid,out_last;
wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im;
top_s3_subfft_ecc dut(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);

// raw syndrome taps: group index = 2*(stage-1) + boundary (0=upper,1=lower)
wire signed[38:0]r0r[0:15],r0i[0:15],r1r[0:15],r1i[0:15];
assign r0r[0]=dut.u.s1.protected_butterfly.upper_boundary.res0r;
assign r0i[0]=dut.u.s1.protected_butterfly.upper_boundary.res0i;
assign r1r[0]=dut.u.s1.protected_butterfly.upper_boundary.res1r;
assign r1i[0]=dut.u.s1.protected_butterfly.upper_boundary.res1i;
assign r0r[1]=dut.u.s1.protected_butterfly.lower_boundary.res0r;
assign r0i[1]=dut.u.s1.protected_butterfly.lower_boundary.res0i;
assign r1r[1]=dut.u.s1.protected_butterfly.lower_boundary.res1r;
assign r1i[1]=dut.u.s1.protected_butterfly.lower_boundary.res1i;
assign r0r[2]=dut.u.s2.protected_butterfly.upper_boundary.res0r;
assign r0i[2]=dut.u.s2.protected_butterfly.upper_boundary.res0i;
assign r1r[2]=dut.u.s2.protected_butterfly.upper_boundary.res1r;
assign r1i[2]=dut.u.s2.protected_butterfly.upper_boundary.res1i;
assign r0r[3]=dut.u.s2.protected_butterfly.lower_boundary.res0r;
assign r0i[3]=dut.u.s2.protected_butterfly.lower_boundary.res0i;
assign r1r[3]=dut.u.s2.protected_butterfly.lower_boundary.res1r;
assign r1i[3]=dut.u.s2.protected_butterfly.lower_boundary.res1i;
assign r0r[4]=dut.u.s3.protected_butterfly.upper_boundary.res0r;
assign r0i[4]=dut.u.s3.protected_butterfly.upper_boundary.res0i;
assign r1r[4]=dut.u.s3.protected_butterfly.upper_boundary.res1r;
assign r1i[4]=dut.u.s3.protected_butterfly.upper_boundary.res1i;
assign r0r[5]=dut.u.s3.protected_butterfly.lower_boundary.res0r;
assign r0i[5]=dut.u.s3.protected_butterfly.lower_boundary.res0i;
assign r1r[5]=dut.u.s3.protected_butterfly.lower_boundary.res1r;
assign r1i[5]=dut.u.s3.protected_butterfly.lower_boundary.res1i;
assign r0r[6]=dut.u.s4.protected_butterfly.upper_boundary.res0r;
assign r0i[6]=dut.u.s4.protected_butterfly.upper_boundary.res0i;
assign r1r[6]=dut.u.s4.protected_butterfly.upper_boundary.res1r;
assign r1i[6]=dut.u.s4.protected_butterfly.upper_boundary.res1i;
assign r0r[7]=dut.u.s4.protected_butterfly.lower_boundary.res0r;
assign r0i[7]=dut.u.s4.protected_butterfly.lower_boundary.res0i;
assign r1r[7]=dut.u.s4.protected_butterfly.lower_boundary.res1r;
assign r1i[7]=dut.u.s4.protected_butterfly.lower_boundary.res1i;
assign r0r[8]=dut.u.s5.protected_butterfly.upper_boundary.res0r;
assign r0i[8]=dut.u.s5.protected_butterfly.upper_boundary.res0i;
assign r1r[8]=dut.u.s5.protected_butterfly.upper_boundary.res1r;
assign r1i[8]=dut.u.s5.protected_butterfly.upper_boundary.res1i;
assign r0r[9]=dut.u.s5.protected_butterfly.lower_boundary.res0r;
assign r0i[9]=dut.u.s5.protected_butterfly.lower_boundary.res0i;
assign r1r[9]=dut.u.s5.protected_butterfly.lower_boundary.res1r;
assign r1i[9]=dut.u.s5.protected_butterfly.lower_boundary.res1i;
assign r0r[10]=dut.u.s6.protected_butterfly.upper_boundary.res0r;
assign r0i[10]=dut.u.s6.protected_butterfly.upper_boundary.res0i;
assign r1r[10]=dut.u.s6.protected_butterfly.upper_boundary.res1r;
assign r1i[10]=dut.u.s6.protected_butterfly.upper_boundary.res1i;
assign r0r[11]=dut.u.s6.protected_butterfly.lower_boundary.res0r;
assign r0i[11]=dut.u.s6.protected_butterfly.lower_boundary.res0i;
assign r1r[11]=dut.u.s6.protected_butterfly.lower_boundary.res1r;
assign r1i[11]=dut.u.s6.protected_butterfly.lower_boundary.res1i;
assign r0r[12]=dut.u.s7.protected_butterfly.upper_boundary.res0r;
assign r0i[12]=dut.u.s7.protected_butterfly.upper_boundary.res0i;
assign r1r[12]=dut.u.s7.protected_butterfly.upper_boundary.res1r;
assign r1i[12]=dut.u.s7.protected_butterfly.upper_boundary.res1i;
assign r0r[13]=dut.u.s7.protected_butterfly.lower_boundary.res0r;
assign r0i[13]=dut.u.s7.protected_butterfly.lower_boundary.res0i;
assign r1r[13]=dut.u.s7.protected_butterfly.lower_boundary.res1r;
assign r1i[13]=dut.u.s7.protected_butterfly.lower_boundary.res1i;
assign r0r[14]=dut.u.s8.protected_butterfly.upper_boundary.res0r;
assign r0i[14]=dut.u.s8.protected_butterfly.upper_boundary.res0i;
assign r1r[14]=dut.u.s8.protected_butterfly.upper_boundary.res1r;
assign r1i[14]=dut.u.s8.protected_butterfly.upper_boundary.res1i;
assign r0r[15]=dut.u.s8.protected_butterfly.lower_boundary.res0r;
assign r0i[15]=dut.u.s8.protected_butterfly.lower_boundary.res0i;
assign r1r[15]=dut.u.s8.protected_butterfly.lower_boundary.res1r;
assign r1i[15]=dut.u.s8.protected_butterfly.lower_boundary.res1i;

reg[279:0]input_mem[0:2560];
integer beat,g;
integer fh;
always #5 clk=~clk;
initial begin
 $readmemh("experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",input_mem);
 fh=$fopen("experiments/fault_injection_1024/results/sc01_uncomp_v1_001/residual_distribution.csv","w");
 $fdisplay(fh,"beat,stage,boundary,res0r,res0i,res1r,res1i");
 repeat(4)@(posedge clk);@(negedge clk);rst=0;
 for(beat=0;beat<INPUT_BEATS;beat=beat+1) begin
  in_valid=1;in_last=((beat%256)==255)?1'b1:1'b0;
  {in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im}=input_mem[beat];
  @(negedge clk);
  for(g=0;g<16;g=g+1) begin
   $fdisplay(fh,"%0d,%0d,%s,%0d,%0d,%0d,%0d",
     beat,(g/2)+1,((g%2)==0)?"upper":"lower",
     r0r[g],r0i[g],r1r[g],r1i[g]);
  end
 end
 in_valid=0;in_last=0;
 $fclose(fh);
 $display("RESIDUAL_SCAN done beats=%0d groups=16",INPUT_BEATS);
 $finish;
end
endmodule
