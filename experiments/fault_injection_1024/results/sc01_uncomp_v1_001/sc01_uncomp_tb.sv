`timescale 1ns/1ps
// ============================================================================
// SC-01 方案B un-compensated fault-injection testbench.
// clean = original top_s3_subfft_ecc (golden reference); fault =
// top_s3_subfft_ecc_uncomp (raw-syndrome threshold corrector, no residual
// compensation, THRESHOLD param).
//
// Injection: upper codeword of the un-compensated butterfly (inject port),
// 8 stages x 6 symbols x 2 components x 35 bits = 3360 trials.
//
// Dual-criterion classification per trial (all output beats compared):
//   corrected_bitexact : detected && corrected && fault_out == clean_out
//   corrected_bounded  : detected && corrected && |fault_out-clean_out| <= tau
//   detected_only      : detected && !corrected
//   silent_bounded     : !detected && |diff| <= tau
//   silent_unbounded   : !detected && |diff| > tau
//   miscorrection      : corrected && |diff| > tau   (must be 0)
//
// Usage: vvp sim +THRESHOLD=8
// ============================================================================
module sc01_uncomp_fault_injection_tb;
parameter integer THRESHOLD    = 8;
parameter integer STAGE_MIN    = 1;
parameter integer STAGE_MAX    = 8;
parameter integer SYMBOL_MIN   = 0;
parameter integer SYMBOL_MAX   = 5;
localparam integer N_STAGES    = STAGE_MAX - STAGE_MIN + 1;
localparam integer N_SYMBOLS   = SYMBOL_MAX - SYMBOL_MIN + 1;
localparam integer TRIALS_PER_SYMBOL = 70;   // 35 bits x 2 components
localparam integer TOTAL_TRIALS = N_STAGES * N_SYMBOLS * TRIALS_PER_SYMBOL;
localparam integer FRAME_BEATS = 512;        // two frames
localparam integer MAX_MONITOR_CYCLES = 6000;

reg clk=0,rst=1,in_valid=0,in_last=0;
reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
reg inject_enable=0;
reg [2:0]inject_symbol=0;
reg inject_component=0;
reg [5:0]inject_bit=0;

wire clean_valid,clean_last,fault_valid,fault_last;
wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i;
wire[7:0]fdet,fcor,func;wire[23:0]floc;

reg[279:0]input_mem[0:511];
integer trial,stage_now,symbol_now,component_now,bit_now;
integer det_seen,cor_seen,unc_seen;reg[2:0]loc_seen;
integer mismatch_seen,bounded_seen,out_beats,mon;
integer max_diff;
integer n_cbitexact=0,n_cbounded=0,n_detected_only=0,n_silent_bounded=0,n_silent_unbounded=0,n_miscorrection=0;
integer injected;integer k;
reg signed[35:0]diff_r,diff_i;

top_s3_subfft_ecc clean(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i
);
top_s3_subfft_ecc_uncomp #(.THRESHOLD(THRESHOLD)) fault(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 inject_enable,inject_symbol,inject_component,inject_bit,
 fault_valid,fault_last,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i,
 fdet[0],fcor[0],func[0],floc[2:0],
 fdet[1],fcor[1],func[1],floc[5:3],
 fdet[2],fcor[2],func[2],floc[8:6],
 fdet[3],fcor[3],func[3],floc[11:9],
 fdet[4],fcor[4],func[4],floc[14:12],
 fdet[5],fcor[5],func[5],floc[17:15],
 fdet[6],fcor[6],func[6],floc[20:18],
 fdet[7],fcor[7],func[7],floc[23:21]
);

function check_window;
 input [3:0]stage;
 begin
  check_window=1'b0;
  case(stage)
   1: check_window=fault.u.s1.work_valid&&fault.u.s1.work_second;
   2: check_window=fault.u.s2.work_valid&&fault.u.s2.work_second;
   3: check_window=fault.u.s3.work_valid&&fault.u.s3.work_second;
   4: check_window=fault.u.s4.work_valid&&fault.u.s4.work_second;
   5: check_window=fault.u.s5.work_valid&&fault.u.s5.work_second;
   6: check_window=fault.u.s6.work_valid&&fault.u.s6.work_second;
   7: check_window=fault.u.s7.work_valid&&fault.u.s7.work_second;
   8: check_window=fault.u.s8.work_valid&&fault.u.s8.work_second;
  endcase
 end
endfunction

always #5 clk=~clk;

task run_one_trial;
 input [3:0]stage;
 input [2:0]symbol;
 input [0:0]component;
 input [5:0]bitpos;
 begin
  rst=1;inject_enable=0;in_valid=0;in_last=0;
  repeat(2)@(posedge clk);@(negedge clk);rst=0;
  injected=0;
  for(k=0;k<FRAME_BEATS;k=k+1) begin
   in_valid=1;in_last=(k==FRAME_BEATS-1)?1'b1:1'b0;
   {in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im}=input_mem[k];
   @(negedge clk);
   if((injected==0)&&check_window(stage)) begin
    inject_symbol=symbol;inject_component=component;inject_bit=bitpos;
    inject_enable=1;injected=1;
   end
  end
  in_valid=0;in_last=0;
  if(injected==0) begin
   wait(check_window(stage));
   @(negedge clk);
   inject_symbol=symbol;inject_component=component;inject_bit=bitpos;
   inject_enable=1;injected=1;
  end
  @(posedge clk);#1;
  det_seen=fdet[stage-1];cor_seen=fcor[stage-1];unc_seen=func[stage-1];loc_seen=floc[(stage-1)*3+:3];
  inject_enable=0;
  // monitor the top-level output stream until the frame ends
  mismatch_seen=0;bounded_seen=1;max_diff=0;out_beats=0;mon=0;
  while(mon<=MAX_MONITOR_CYCLES) begin
   @(posedge clk);#1;
   mon=mon+1;
   if(fault_valid) begin
    out_beats=out_beats+1;
    diff_r=$signed(c0r)-$signed(f0r);
    diff_i=$signed(c0i)-$signed(f0i);
    if((c0r!==f0r)||(c0i!==f0i)||(c1r!==f1r)||(c1i!==f1i)||(c2r!==f2r)||(c2i!==f2i)||(c3r!==f3r)||(c3i!==f3i)) mismatch_seen=1;
    // per-lane bounded check: |diff| <= THRESHOLD on both components of all four lanes
    if((diff_r<(-$signed(THRESHOLD)))||(diff_r>$signed(THRESHOLD))||(diff_i<(-$signed(THRESHOLD)))||(diff_i>$signed(THRESHOLD))) bounded_seen=0;
    diff_r=$signed(c1r)-$signed(f1r);
    diff_i=$signed(c1i)-$signed(f1i);
    if((diff_r<(-$signed(THRESHOLD)))||(diff_r>$signed(THRESHOLD))||(diff_i<(-$signed(THRESHOLD)))||(diff_i>$signed(THRESHOLD))) bounded_seen=0;
    diff_r=$signed(c2r)-$signed(f2r);
    diff_i=$signed(c2i)-$signed(f2i);
    if((diff_r<(-$signed(THRESHOLD)))||(diff_r>$signed(THRESHOLD))||(diff_i<(-$signed(THRESHOLD)))||(diff_i>$signed(THRESHOLD))) bounded_seen=0;
    diff_r=$signed(c3r)-$signed(f3r);
    diff_i=$signed(c3i)-$signed(f3i);
    if((diff_r<(-$signed(THRESHOLD)))||(diff_r>$signed(THRESHOLD))||(diff_i<(-$signed(THRESHOLD)))||(diff_i>$signed(THRESHOLD))) bounded_seen=0;
    if(fault_last) mon=MAX_MONITOR_CYCLES+2;
   end
  end
  if(mon!=(MAX_MONITOR_CYCLES+2)) begin
   $display("WARN trial stage=%0d symbol=%0d component=%0d bit=%0d: monitor timeout, out_beats=%0d",stage,symbol,component,bitpos,out_beats);
  end
  // dual-criterion classification
  if((det_seen!=0)&&(cor_seen!=0)) begin
   if(mismatch_seen==0) begin n_cbitexact=n_cbitexact+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=1 corrected=1 location=%0d match=1 category=corrected_bitexact",stage,symbol,component?"imag":"real",bitpos,loc_seen); end
   else if(bounded_seen!=0) begin n_cbounded=n_cbounded+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=1 corrected=1 location=%0d match=0 category=corrected_bounded",stage,symbol,component?"imag":"real",bitpos,loc_seen); end
   else begin n_miscorrection=n_miscorrection+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=1 corrected=1 location=%0d match=0 category=MISCORRECTION",stage,symbol,component?"imag":"real",bitpos,loc_seen); end
  end else if((det_seen!=0)&&(cor_seen==0)) begin
   n_detected_only=n_detected_only+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=1 corrected=0 location=%0d match=0 category=detected_only",stage,symbol,component?"imag":"real",bitpos,loc_seen);
  end else begin
   if(bounded_seen!=0) begin n_silent_bounded=n_silent_bounded+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=0 corrected=0 location=- match=0 category=silent_bounded",stage,symbol,component?"imag":"real",bitpos); end
   else begin n_silent_unbounded=n_silent_unbounded+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=0 corrected=0 location=- match=0 category=silent_unbounded",stage,symbol,component?"imag":"real",bitpos); end
  end
 end
endtask

initial begin
 $readmemh("experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",input_mem);
 $display("SC01_UNCOMP_RTL threshold=%0d stages=%0d..%0d symbols=%0d..%0d total_trials=%0d",THRESHOLD,STAGE_MIN,STAGE_MAX,SYMBOL_MIN,SYMBOL_MAX,TOTAL_TRIALS);
 trial=0;
 for(stage_now=STAGE_MIN;stage_now<=STAGE_MAX;stage_now=stage_now+1) begin
  for(symbol_now=SYMBOL_MIN;symbol_now<=SYMBOL_MAX;symbol_now=symbol_now+1) begin
   for(component_now=0;component_now<=1;component_now=component_now+1) begin
    for(bit_now=0;bit_now<35;bit_now=bit_now+1) begin
     run_one_trial(stage_now,symbol_now,component_now,bit_now);
     trial=trial+1;
    end
   end
  end
 end
 $display("SUMMARY threshold=%0d total=%0d corrected_bitexact=%0d corrected_bounded=%0d detected_only=%0d silent_bounded=%0d silent_unbounded=%0d miscorrection=%0d",
   THRESHOLD,TOTAL_TRIALS,n_cbitexact,n_cbounded,n_detected_only,n_silent_bounded,n_silent_unbounded,n_miscorrection);
 $display("SUMMARY recovery_bitexact=%0.2f%%",100.0*n_cbitexact/TOTAL_TRIALS);
 $display("SUMMARY recovery_bounded=%0.2f%%",100.0*(n_cbitexact+n_cbounded)/TOTAL_TRIALS);
 $display("SUMMARY detection_rate=%0.2f%%",100.0*(n_cbitexact+n_cbounded+n_detected_only)/TOTAL_TRIALS);
 $finish;
end
endmodule
