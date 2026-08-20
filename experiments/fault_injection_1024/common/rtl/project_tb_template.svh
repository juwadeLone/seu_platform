`timescale 1ns/1ps
module `PROJECT_TB_NAME;
localparam integer INPUT_BEATS=2560;
localparam integer EXPECTED_BEATS=2048;
localparam integer EXPECTED_LATENCY=`PROJECT_PFFT ? 525 : 268;
reg clk=0,rst=1,in_valid=0,in_last=0;
reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
wire out_valid,out_last;
wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im;
reg[279:0]input_mem[0:INPUT_BEATS-1],expected_mem[0:EXPECTED_BEATS-1];
wire[279:0]packed_output={out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im};
integer input_index=0,output_index=0,cycle_count=0,first_input=-1,first_output=-1,errors=0;
`PROJECT_TOP dut(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,out_valid,out_last,out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);
always #5 clk=~clk;
initial begin
 $readmemh("experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",input_mem);
 if(`PROJECT_PFFT)$readmemh("experiments/fault_injection_1024/common/vectors/qualification_pfft_expected_8frames.hex",expected_mem);
 else $readmemh("experiments/fault_injection_1024/common/vectors/qualification_subfft_expected_8frames.hex",expected_mem);
 repeat(4)@(posedge clk);@(negedge clk);rst=0;
 for(input_index=0;input_index<INPUT_BEATS;input_index=input_index+1)begin
  in_valid=1;in_last=((input_index%256)==255);
  {in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im}=input_mem[input_index];
  @(negedge clk);
 end
 in_valid=0;in_last=0;
end
always@(posedge clk)if(!rst)begin
 cycle_count=cycle_count+1;
 if(in_valid&&first_input<0)first_input=cycle_count;
 if(out_valid)begin
  if(first_output<0)first_output=cycle_count;
  if(output_index<EXPECTED_BEATS)begin
   if(packed_output!==expected_mem[output_index])begin errors=errors+1;if(errors<=8)$display("MISMATCH architecture=%s beat=%0d",`PROJECT_ID,output_index);end
   if(out_last!==((output_index%256)==255))errors=errors+1;
   output_index=output_index+1;
   if(output_index==EXPECTED_BEATS)begin
    if((first_output-first_input)!=EXPECTED_LATENCY)errors=errors+1;
    if(errors==0)begin $display("PASS architecture=%s beats=%0d latency=%0d",`PROJECT_ID,output_index,first_output-first_input);$finish;end
    else $fatal(1,"FAIL architecture=%s errors=%0d",`PROJECT_ID,errors);
   end
  end
 end
 if(cycle_count>6000)$fatal(1,"TIMEOUT architecture=%s beats=%0d",`PROJECT_ID,output_index);
end
endmodule
