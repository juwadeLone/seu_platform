`timescale 1ns/1ps
module tb_s3_lower_ecc_connectivity_v1;
localparam integer INPUT_BEATS=1792;
localparam integer CHECK_BEATS=768;
localparam integer VECTOR_BEATS=2560;
reg clk=0,rst=1,in_valid=0,in_last=0;
reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
wire clean_valid,clean_last,fault_valid,fault_last;
wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i;
wire signed[34:0]f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i;
wire[279:0]clean_word={c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i};
wire[279:0]fault_word={f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i};
reg[279:0]input_mem[0:VECTOR_BEATS-1];
reg signed[34:0]fault35;
integer input_index=0,cycle_count=0,output_count=0,errors=0,injections=0;

top_s3_subfft_ecc clean(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i
);
top_s3_subfft_ecc fault(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 fault_valid,fault_last,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i
);

initial begin
 wait(!rst);
 wait(fault.u.s1.out_count==8'd12&&fault.u.s1.work_valid&&fault.u.s1.work_second);
 @(negedge clk);
 fault35=fault.u.s1.protected_butterfly.lower_received_r[0]^35'sd1;
 force fault.u.s1.protected_butterfly.lower_received_r[0]=fault35;
 injections=injections+1;
 $display("INJECT S3 Stage1 lower arithmetic received bit0");
 @(posedge clk);#1;
 release fault.u.s1.protected_butterfly.lower_received_r[0];
end

always #5 clk=~clk;
initial begin
 $readmemh("experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",input_mem);
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
 if(clean_valid!==fault_valid)errors=errors+1;
 if(clean_last!==fault_last)errors=errors+1;
 if(clean_valid&&fault_valid)begin
  if(clean_word!==fault_word)begin
   errors=errors+1;
   if(errors<=8)$display("DATA_MISMATCH beat=%0d clean=%h fault=%h",output_count,clean_word,fault_word);
  end
  output_count=output_count+1;
  if(output_count==CHECK_BEATS)begin
   if(injections!=1)$fatal(1,"INJECTION_COUNT got=%0d expected=1",injections);
   if(errors==0)begin
    $display("PASS S3 lower ECC connectivity beats=%0d injections=%0d",output_count,injections);
    $finish;
   end
   else $fatal(1,"FAIL S3 lower ECC connectivity errors=%0d",errors);
  end
 end
 if(cycle_count>5000)$fatal(1,"TIMEOUT beats=%0d injections=%0d",output_count,injections);
end
endmodule
