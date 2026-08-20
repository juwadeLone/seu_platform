`timescale 1ns/1ps
module tb_p2_no_framebuf_v1;
localparam integer INPUT_BEATS=2560;
localparam integer EXPECTED_BEATS=2048;
reg clk=0,rst=1,in_valid=0,in_last=0;
reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
wire out_valid,out_last;
wire signed[34:0]out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im;
reg[279:0]input_mem[0:INPUT_BEATS-1];
reg[279:0]expected_mem[0:EXPECTED_BEATS-1];
wire[279:0]packed_output={
 out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im};
integer input_index=0,output_index=0,cycle_count=0;
integer first_input=-1,first_output=-1;
integer errors=0,gap_errors=0,last_errors=0,data_errors=0;
integer frame_count=0,frame_beat_count=0;
reg output_started=0;

top_p2_pfft_tmr_no_framebuf_v1 dut(
 clk,rst,in_valid,in_last,
 in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 out_valid,out_last,
 out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im);

always #5 clk=~clk;
initial begin
 $readmemh(
  "experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",
  input_mem);
 $readmemh(
  "experiments/fault_injection_1024/projects/P2/vectors/qualification_p2_no_exchange_expected_8frames.hex",
  expected_mem);
 repeat(4)@(posedge clk);@(negedge clk);rst=0;
 for(input_index=0;input_index<INPUT_BEATS;input_index=input_index+1)begin
  in_valid=1;in_last=((input_index%256)==255);
  {in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im}=
   input_mem[input_index];
  @(negedge clk);
 end
 in_valid=0;in_last=0;
end

always@(posedge clk)if(!rst)begin
 cycle_count=cycle_count+1;
 if(in_valid&&first_input<0)first_input=cycle_count;
 if(output_started&&(output_index<EXPECTED_BEATS)&&!out_valid)begin
  errors=errors+1;gap_errors=gap_errors+1;
  if(gap_errors<=8)
   $display("OUT_VALID_GAP cycle=%0d after_beat=%0d",
    cycle_count,output_index-1);
 end
 if(out_valid)begin
  if(!output_started)output_started=1;
  if(first_output<0)first_output=cycle_count;
  if(output_index>=EXPECTED_BEATS)
   $fatal(1,"EXTRA_OUTPUT cycle=%0d",cycle_count);
  if(packed_output!==expected_mem[output_index])begin
   errors=errors+1;data_errors=data_errors+1;
   if(data_errors<=8)$display("MISMATCH beat=%0d",output_index);
  end
  if(out_last!==((frame_beat_count==255)?1'b1:1'b0))begin
   errors=errors+1;last_errors=last_errors+1;
   if(last_errors<=8)
    $display("OUT_LAST_ERROR frame=%0d frame_beat=%0d value=%0b",
     frame_count,frame_beat_count,out_last);
  end
  if(frame_beat_count==255)begin
   frame_beat_count=0;frame_count=frame_count+1;
  end else frame_beat_count=frame_beat_count+1;
  output_index=output_index+1;
  if(output_index==EXPECTED_BEATS)begin
   if(frame_count!=8||frame_beat_count!=0)begin
    errors=errors+1;
    $display("FRAME_BOUNDARY_ERROR frames=%0d residual=%0d",
     frame_count,frame_beat_count);
   end
   if(errors==0)begin
    $display(
     "PASS_P2_NO_FRAMEBUF beats=%0d frames=%0d measured_latency=%0d gaps=0 last_errors=0 data_errors=0",
     output_index,frame_count,first_output-first_input);
    $finish;
   end else
    $fatal(1,
     "FAIL_P2_NO_FRAMEBUF errors=%0d data=%0d gaps=%0d last=%0d frames=%0d",
     errors,data_errors,gap_errors,last_errors,frame_count);
  end
 end
 if(cycle_count>6000)
  $fatal(1,"TIMEOUT beats=%0d frames=%0d",output_index,frame_count);
end
endmodule
