`timescale 1ns/1ps

// PFFT-RES-V3-001 connectivity qualification.
//
// This is deliberately a clean-versus-fault paired test.  It does not replace
// the project bit-exact tests; it proves that each named protection boundary is
// connected to the active top-level output and masks the injected one-cycle
// fault used here.
module pfft_connectivity_spot_tb_v3;
localparam integer INPUT_BEATS = 1792;
localparam integer VECTOR_BEATS = 2560;
localparam integer CHECK_BEATS = 1024;
localparam integer EXPECTED_P1_INJECTIONS = 6;
localparam integer EXPECTED_P2_INJECTIONS = 1;

reg clk = 1'b0;
reg rst = 1'b1;
reg in_valid = 1'b0;
reg in_last = 1'b0;
reg signed [34:0] in0_re,in0_im,in1_re,in1_im;
reg signed [34:0] in2_re,in2_im,in3_re,in3_im;
reg [279:0] input_mem [0:VECTOR_BEATS-1];

wire p1_clean_valid,p1_clean_last,p1_fault_valid,p1_fault_last;
wire signed [34:0] p1c0r,p1c0i,p1c1r,p1c1i,p1c2r,p1c2i,p1c3r,p1c3i;
wire signed [34:0] p1f0r,p1f0i,p1f1r,p1f1i,p1f2r,p1f2i,p1f3r,p1f3i;
wire [279:0] p1_clean_word =
 {p1c0r,p1c0i,p1c1r,p1c1i,p1c2r,p1c2i,p1c3r,p1c3i};
wire [279:0] p1_fault_word =
 {p1f0r,p1f0i,p1f1r,p1f1i,p1f2r,p1f2i,p1f3r,p1f3i};

wire p2_clean_valid,p2_clean_last,p2_fault_valid,p2_fault_last;
wire signed [34:0] p2c0r,p2c0i,p2c1r,p2c1i,p2c2r,p2c2i,p2c3r,p2c3i;
wire signed [34:0] p2f0r,p2f0i,p2f1r,p2f1i,p2f2r,p2f2i,p2f3r,p2f3i;
wire [279:0] p2_clean_word =
 {p2c0r,p2c0i,p2c1r,p2c1i,p2c2r,p2c2i,p2c3r,p2c3i};
wire [279:0] p2_fault_word =
 {p2f0r,p2f0i,p2f1r,p2f1i,p2f2r,p2f2i,p2f3r,p2f3i};

integer input_index = 0;
integer cycle_count = 0;
integer p1_output_count = 0;
integer p2_output_count = 0;
integer p1_errors = 0;
integer p2_errors = 0;
integer p1_injections = 0;
integer p2_injections = 0;
reg p1_done = 1'b0;
reg p2_done = 1'b0;
reg [77:0] p1_fault78;
reg signed [34:0] p1_fault35;
reg signed [34:0] p2_fault35;

top_p1_pfft_ecc clean_p1(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
 in2_re,in2_im,in3_re,in3_im,p1_clean_valid,p1_clean_last,
 p1c0r,p1c0i,p1c1r,p1c1i,p1c2r,p1c2i,p1c3r,p1c3i
);
top_p1_pfft_ecc fault_p1(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
 in2_re,in2_im,in3_re,in3_im,p1_fault_valid,p1_fault_last,
 p1f0r,p1f0i,p1f1r,p1f1i,p1f2r,p1f2i,p1f3r,p1f3i
);
top_p2_pfft_tmr clean_p2(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
 in2_re,in2_im,in3_re,in3_im,p2_clean_valid,p2_clean_last,
 p2c0r,p2c0i,p2c1r,p2c1i,p2c2r,p2c2i,p2c3r,p2c3i
);
top_p2_pfft_tmr fault_p2(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,
 in2_re,in2_im,in3_re,in3_im,p2_fault_valid,p2_fault_last,
 p2f0r,p2f0i,p2f1r,p2f1i,p2f2r,p2f2i,p2f3r,p2f3i
);

always #5 clk = ~clk;

initial begin
 $readmemh(
  "experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",
  input_mem
 );
 repeat(4) @(posedge clk);
 @(negedge clk);
 rst = 1'b0;
 for(input_index=0;input_index<INPUT_BEATS;input_index=input_index+1)begin
  in_valid = 1'b1;
  in_last = ((input_index%256)==255);
  {in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im} =
   input_mem[input_index];
  @(negedge clk);
 end
 in_valid = 1'b0;
 in_last = 1'b0;
end

// P1 Stage 1: one SECDED codeword fault and one arithmetic-code received
// symbol fault.
initial begin
 wait(!rst);
 wait(fault_p1.u.s1.work_valid && fault_p1.u.s1.candidate_valid);
 @(negedge clk);
 p1_fault78 = fault_p1.u.s1.mcode0 ^ 78'd1;
 force fault_p1.u.s1.mcode0 = p1_fault78;
 p1_injections = p1_injections + 1;
 $display("INJECT_V3 P1_STAGE1_SECDED");
 @(posedge clk); #1;
 release fault_p1.u.s1.mcode0;

 wait(fault_p1.u.s1.work_valid && fault_p1.u.s1.work_second &&
      (fault_p1.u.s1.out_count==8'd8));
 @(negedge clk);
 p1_fault35 = fault_p1.u.s1.received_r[0] ^ 35'sd1;
 force fault_p1.u.s1.received_r[0] = p1_fault35;
 p1_injections = p1_injections + 1;
 $display("INJECT_V3 P1_STAGE1_ARITHMETIC");
 @(posedge clk); #1;
 release fault_p1.u.s1.received_r[0];

 // P1 Stage 8 same-frame arithmetic boundary.
 wait(fault_p1.u.scheduler.issue_valid &&
      (fault_p1.u.scheduler.issue_kind==3'd1) &&
      (fault_p1.u.scheduler.issue_address==9'd3));
 @(negedge clk);
 p1_fault35 = fault_p1.u.scheduler.received_f0r ^ 35'sd1;
 force fault_p1.u.scheduler.received_f0r = p1_fault35;
 p1_injections = p1_injections + 1;
 $display("INJECT_V3 P1_STAGE8_SAME_FRAME_ARITHMETIC");
 @(posedge clk); #1;
 release fault_p1.u.scheduler.received_f0r;

 // P1 Stage 8 pending SECDED storage on a cross-frame task.
 wait(fault_p1.u.scheduler.issue_valid &&
      (fault_p1.u.scheduler.issue_kind==3'd2) &&
      (fault_p1.u.scheduler.issue_address==9'd266));
 @(negedge clk);
 p1_fault78 = fault_p1.u.scheduler.task_f0_code ^ 78'd1;
 force fault_p1.u.scheduler.task_f0_code = p1_fault78;
 p1_injections = p1_injections + 1;
 $display("INJECT_V3 P1_STAGE8_PENDING_SECDED");
 @(posedge clk); #1;
 release fault_p1.u.scheduler.task_f0_code;

 // P1 Stage 8 cross-frame arithmetic boundary.
 wait(fault_p1.u.scheduler.issue_valid &&
      (fault_p1.u.scheduler.issue_kind==3'd2) &&
      (fault_p1.u.scheduler.issue_address==9'd276));
 @(negedge clk);
 p1_fault35 = fault_p1.u.scheduler.received_f0r ^ 35'sd1;
 force fault_p1.u.scheduler.received_f0r = p1_fault35;
 p1_injections = p1_injections + 1;
 $display("INJECT_V3 P1_STAGE8_CROSS_FRAME_ARITHMETIC");
 @(posedge clk); #1;
 release fault_p1.u.scheduler.received_f0r;

 // P1 Stage 9: one complete replica before the voter.
 wait(fault_p1.u.s9.v[0]);
 @(negedge clk);
 p1_fault35 = fault_p1.u.s9.r0[0] ^ 35'sd1;
 force fault_p1.u.s9.r0[0] = p1_fault35;
 p1_injections = p1_injections + 1;
 $display("INJECT_V3 P1_STAGE9_TMR_REPLICA");
 @(posedge clk); #1;
 release fault_p1.u.s9.r0[0];
end

// P2 Stage 1: one complete replica before the voter.
initial begin
 wait(!rst);
 wait(fault_p2.u.s1.v[0]);
 @(negedge clk);
 p2_fault35 = fault_p2.u.s1.r0[0] ^ 35'sd1;
 force fault_p2.u.s1.r0[0] = p2_fault35;
 p2_injections = p2_injections + 1;
 $display("INJECT_V3 P2_STAGE1_TMR_REPLICA");
 @(posedge clk); #1;
 release fault_p2.u.s1.r0[0];
end

always @(posedge clk) if(!rst) begin
 cycle_count = cycle_count + 1;

 if(!p1_done)begin
  if(p1_clean_valid!==p1_fault_valid)begin
   p1_errors = p1_errors + 1;
   if(p1_errors<=8)
    $display("P1_VALID_MISMATCH cycle=%0d",cycle_count);
  end
  if(p1_clean_last!==p1_fault_last)begin
   p1_errors = p1_errors + 1;
   if(p1_errors<=8)
    $display("P1_LAST_MISMATCH cycle=%0d",cycle_count);
  end
  if(p1_clean_valid && p1_fault_valid)begin
   if(p1_clean_word!==p1_fault_word)begin
    p1_errors = p1_errors + 1;
    if(p1_errors<=8)
     $display("P1_DATA_MISMATCH beat=%0d",p1_output_count);
   end
   p1_output_count = p1_output_count + 1;
   if(p1_output_count==CHECK_BEATS)
    p1_done = 1'b1;
  end
 end

 if(!p2_done)begin
  if(p2_clean_valid!==p2_fault_valid)begin
   p2_errors = p2_errors + 1;
   if(p2_errors<=8)
    $display("P2_VALID_MISMATCH cycle=%0d",cycle_count);
  end
  if(p2_clean_last!==p2_fault_last)begin
   p2_errors = p2_errors + 1;
   if(p2_errors<=8)
    $display("P2_LAST_MISMATCH cycle=%0d",cycle_count);
  end
  if(p2_clean_valid && p2_fault_valid)begin
   if(p2_clean_word!==p2_fault_word)begin
    p2_errors = p2_errors + 1;
    if(p2_errors<=8)
     $display("P2_DATA_MISMATCH beat=%0d",p2_output_count);
   end
   p2_output_count = p2_output_count + 1;
   if(p2_output_count==CHECK_BEATS)
    p2_done = 1'b1;
  end
 end

 if(p1_done && p2_done)begin
  if(p1_injections!=EXPECTED_P1_INJECTIONS)
   $fatal(1,"P1_INJECTION_COUNT got=%0d expected=%0d",
          p1_injections,EXPECTED_P1_INJECTIONS);
  if(p2_injections!=EXPECTED_P2_INJECTIONS)
   $fatal(1,"P2_INJECTION_COUNT got=%0d expected=%0d",
          p2_injections,EXPECTED_P2_INJECTIONS);
  if((p1_errors==0)&&(p2_errors==0))begin
   $display(
    "PASS_V3_CONNECTIVITY p1_beats=%0d p2_beats=%0d p1_injections=%0d p2_injections=%0d",
    p1_output_count,p2_output_count,p1_injections,p2_injections
   );
   $finish;
  end
  $fatal(1,"FAIL_V3_CONNECTIVITY p1_errors=%0d p2_errors=%0d",
         p1_errors,p2_errors);
 end

 if(cycle_count>6000)
  $fatal(1,
   "TIMEOUT_V3_CONNECTIVITY p1_beats=%0d p2_beats=%0d p1_injections=%0d p2_injections=%0d",
   p1_output_count,p2_output_count,p1_injections,p2_injections);
end
endmodule
