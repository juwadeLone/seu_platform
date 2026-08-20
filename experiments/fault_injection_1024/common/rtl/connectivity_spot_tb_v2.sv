`timescale 1ns/1ps
module tb_top_connectivity_v5;
parameter integer CASE_ID=0;
localparam integer INPUT_BEATS=1792;
localparam integer VECTOR_BEATS=2560;
localparam integer CHECK_BEATS=(CASE_ID>=3)?1024:768;
localparam integer EXPECTED_INJECTIONS=(CASE_ID==2)?3:((CASE_ID==3)?6:1);
reg clk=0,rst=1,in_valid=0,in_last=0;
reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
wire clean_valid,clean_last,fault_valid,fault_last;
wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i;
wire[279:0]clean_word={c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i};
wire[279:0]fault_word={f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i};
reg[279:0]input_mem[0:VECTOR_BEATS-1];
reg[77:0]fault78;reg signed[34:0]fault35;
integer input_index=0,cycle_count=0,output_count=0,errors=0,injections=0;

generate
 if(CASE_ID==0)begin:g_s1
  top_s1_gao_subfft_ecc clean(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i);
  top_s1_gao_subfft_ecc fault(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,fault_valid,fault_last,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i);
  initial begin
   wait(!rst);wait(fault.pv[0]&&fault.pv[1]&&fault.pv[2]&&fault.pv[3]&&fault.pv[4]&&fault.pv[5]&&fault.pv[6]);
   @(negedge clk);fault35=fault.received_path_r[2]^35'sd1;
   force fault.received_path_r[2]=fault35;injections=injections+1;$display("INJECT S1 Gao received path2 bit0");
   @(posedge clk);#1;release fault.received_path_r[2];
  end
 end else if(CASE_ID==1)begin:g_s2
  top_s2_subfft_tmr clean(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i);
  top_s2_subfft_tmr fault(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,fault_valid,fault_last,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i);
  initial begin
   wait(!rst);wait(fault.u.s1.v[0]);@(negedge clk);fault35=fault.u.s1.r0[0]^35'sd1;
   force fault.u.s1.r0[0]=fault35;injections=injections+1;$display("INJECT S2 Stage1 replica0 bit0");
   @(posedge clk);#1;release fault.u.s1.r0[0];
  end
 end else if(CASE_ID==2)begin:g_s3
  top_s3_subfft_ecc clean(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i);
  top_s3_subfft_ecc fault(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,fault_valid,fault_last,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i);
  initial begin
   wait(!rst);wait(fault.u.s1.work_valid&&fault.u.s1.candidate_valid);@(negedge clk);
   fault78=fault.u.s1.mcode0^78'd1;force fault.u.s1.mcode0=fault78;injections=injections+1;$display("INJECT S3 Stage1 SECDED codeword bit0");
   @(posedge clk);#1;release fault.u.s1.mcode0;
   wait(fault.u.s1.out_count==8'd8&&fault.u.s1.work_valid&&fault.u.s1.work_second);@(negedge clk);
   fault35=fault.u.s1.protected_butterfly.upper_received_r[0]^35'sd1;force fault.u.s1.protected_butterfly.upper_received_r[0]=fault35;injections=injections+1;$display("INJECT S3 Stage1 arithmetic received bit0");
   @(posedge clk);#1;release fault.u.s1.protected_butterfly.upper_received_r[0];
   wait(fault.u.s9.v[0]);@(negedge clk);fault35=fault.u.s9.r0[0]^35'sd1;force fault.u.s9.r0[0]=fault35;injections=injections+1;$display("INJECT S3 Stage9 replica0 bit0");
   @(posedge clk);#1;release fault.u.s9.r0[0];
  end
 end else if(CASE_ID==3)begin:g_p1
  top_p1_pfft_ecc clean(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i);
  top_p1_pfft_ecc fault(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,fault_valid,fault_last,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i);
  initial begin
   wait(!rst);wait(fault.u.s1.work_valid&&fault.u.s1.candidate_valid);@(negedge clk);
   fault78=fault.u.s1.mcode0^78'd1;force fault.u.s1.mcode0=fault78;injections=injections+1;$display("INJECT P1 Stage1 SECDED codeword bit0");
   @(posedge clk);#1;release fault.u.s1.mcode0;
   wait(fault.u.s1.out_count==8'd8&&fault.u.s1.work_valid&&fault.u.s1.work_second);@(negedge clk);
   fault35=fault.u.s1.protected_butterfly.upper_received_r[0]^35'sd1;force fault.u.s1.protected_butterfly.upper_received_r[0]=fault35;injections=injections+1;$display("INJECT P1 Stage1 arithmetic received bit0");
   @(posedge clk);#1;release fault.u.s1.protected_butterfly.upper_received_r[0];
   wait(fault.u.pair.in_valid&&(fault.u.pair.input_beat==8'd3));@(negedge clk);
   fault35=fault.u.pair.samep_r0r^35'sd1;force fault.u.pair.samep_r0r=fault35;injections=injections+1;$display("INJECT P1 Stage8 same-frame received bit0");
   @(posedge clk);#1;release fault.u.pair.samep_r0r;
   wait(fault.u.pair.out_valid&&fault.u.pair.cycle_pair_second&&(fault.u.pair.cycle_beat==8'd10));@(negedge clk);
   fault78=fault.u.pair.pending_r_f0^78'd1;force fault.u.pair.pending_r_f0=fault78;injections=injections+1;$display("INJECT P1 Stage8 pending BRAM codeword bit0");
   @(posedge clk);#1;release fault.u.pair.pending_r_f0;
   wait(fault.u.pair.out_valid&&fault.u.pair.cycle_pair_second&&(fault.u.pair.cycle_beat==8'd20));@(negedge clk);
   fault35=fault.u.pair.crossn_r0r^35'sd1;force fault.u.pair.crossn_r0r=fault35;injections=injections+1;$display("INJECT P1 Stage8 cross-frame arithmetic received bit0");
   @(posedge clk);#1;release fault.u.pair.crossn_r0r;
   wait(fault.u.s9.v[0]&&fault.u.pair.cycle_pair_second&&(fault.u.pair.cycle_beat==8'd30));@(negedge clk);
   fault35=fault.u.s9.r0[0]^35'sd1;force fault.u.s9.r0[0]=fault35;injections=injections+1;$display("INJECT P1 Stage9 replica0 bit0");
   @(posedge clk);#1;release fault.u.s9.r0[0];
  end
 end else begin:g_p2
  top_p2_pfft_tmr clean(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i);
  top_p2_pfft_tmr fault(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,fault_valid,fault_last,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i);
  initial begin
   wait(!rst);wait(fault.u.s1.v[0]);@(negedge clk);fault35=fault.u.s1.r0[0]^35'sd1;
   force fault.u.s1.r0[0]=fault35;injections=injections+1;$display("INJECT P2 Stage1 replica0 bit0");
   @(posedge clk);#1;release fault.u.s1.r0[0];
  end
 end
endgenerate

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
 if(clean_valid!==fault_valid)begin errors=errors+1;if(errors<=8)$display("VALID_MISMATCH case=%0d cycle=%0d",CASE_ID,cycle_count);end
 if(clean_last!==fault_last)begin errors=errors+1;if(errors<=8)$display("LAST_MISMATCH case=%0d cycle=%0d",CASE_ID,cycle_count);end
 if(clean_valid&&fault_valid)begin
  if(clean_word!==fault_word)begin errors=errors+1;if(errors<=8)$display("DATA_MISMATCH case=%0d beat=%0d clean=%h fault=%h",CASE_ID,output_count,clean_word,fault_word);end
  output_count=output_count+1;
  if(output_count==CHECK_BEATS)begin
   if(injections!=EXPECTED_INJECTIONS)$fatal(1,"INJECTION_COUNT case=%0d got=%0d expected=%0d",CASE_ID,injections,EXPECTED_INJECTIONS);
   if(errors==0)begin $display("PASS connectivity case=%0d beats=%0d injections=%0d",CASE_ID,output_count,injections);$finish;end
   else $fatal(1,"FAIL connectivity case=%0d errors=%0d",CASE_ID,errors);
  end
 end
 if(cycle_count>5000)$fatal(1,"TIMEOUT connectivity case=%0d beats=%0d injections=%0d",CASE_ID,output_count,injections);
end
endmodule
