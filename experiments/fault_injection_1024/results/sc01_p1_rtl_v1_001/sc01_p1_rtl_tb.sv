`timescale 1ns/1ps
// ============================================================================
// SC-01 P1 RTL fault-injection testbench.
// clean = original top_p1_pfft_ecc (golden reference); fault =
// top_p1_pfft_ecc_thresholded (injection hook + thresholded correctors).
//
// Trial space (tau sweepable via THRESHOLD):
//   stages 1-7 : received path of p1_ecc_stage4_v3_thresholded
//                7 stages x 6 symbols x 2 components x 35 bits = 2940
//   stage 10   : upper received path of independent_butterfly_ecc_v5_thresholded
//                6 symbols x 2 components x 35 bits = 420
//   total 3360 trials (same count as S3)
//
// Injection timing:
//   stages 1-7 : work_valid && work_second (upper output beat)
//   stage 10   : pair_phase == 1 (second beat, butterfly execution)
//
// Four-class classification identical to the S3 testbench.
// Usage: vvp sim +THRESHOLD=0
// ============================================================================
module sc01_p1_fault_injection_tb;
parameter integer THRESHOLD    = 0;
parameter integer STAGE_MODE   = 0;   // 0 = full (3360), 1 = stages 1-7 only (2940), 2 = stage 10 only (420)
localparam integer TRIALS_ST17 = 2940;   // 7 stages x 420
localparam integer TRIALS_S10  = 420;    // 1 stage x 420
localparam integer TOTAL_TRIALS = (STAGE_MODE==2)?TRIALS_S10:((STAGE_MODE==1)?TRIALS_ST17:(TRIALS_ST17+TRIALS_S10));
localparam integer FRAME_BEATS = 512;    // two frames (pipeline fill + full output)
localparam integer MAX_MONITOR_CYCLES = 8000;

reg clk=0,rst=1,in_valid=0,in_last=0;
reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
reg inject_enable=0;
reg [2:0]inject_symbol=0;
reg inject_component=0;
reg [5:0]inject_bit=0;

wire clean_valid,clean_last,fault_valid,fault_last;
wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i;
wire[279:0]clean_word={c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i};
wire[279:0]fault_word={f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i};
wire[6:0]fdet,fcor,func;wire[20:0]floc;
wire fs10up_det,fs10up_cor,fs10up_unc;wire[2:0]fs10up_loc;
wire fs10lo_det,fs10lo_cor,fs10lo_unc;wire[2:0]fs10lo_loc;

reg[279:0]input_mem[0:511];
integer trial,stage_now,symbol_now,component_now,bit_now;
integer det_seen,cor_seen,unc_seen;reg[2:0]loc_seen;
integer mismatch_seen,out_beats,mon,out_frames;
integer n_corrected=0,n_detected_only=0,n_silent_bounded=0,n_miscorrection=0,n_silent_unbounded=0,n_corrected_no_flag=0;
integer injected;integer k;integer r;

top_p1_pfft_ecc clean(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i
);
top_p1_pfft_ecc_thresholded #(.THRESHOLD(THRESHOLD)) fault(
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
 fs10up_det,fs10up_cor,fs10up_unc,fs10up_loc,
 fs10lo_det,fs10lo_cor,fs10lo_unc,fs10lo_loc
);

// Window predicate: the fault stage is emitting an upper (second-phase) output
// beat (stages 1-7) or is in the butterfly-execution beat (stage 10).
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
   10: check_window=fault.u.s10.pair_phase==1'b1;
   default: check_window=1'b0;
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
  if(stage==10) begin
   det_seen=fs10up_det;cor_seen=fs10up_cor;unc_seen=fs10up_unc;loc_seen=fs10up_loc;
  end else begin
   det_seen=fdet[stage-1];cor_seen=fcor[stage-1];unc_seen=func[stage-1];loc_seen=floc[(stage-1)*3+:3];
  end
  inject_enable=0;
  // monitor the top-level output stream until the frame ends
  mismatch_seen=0;out_beats=0;mon=0;
  while(mon<=MAX_MONITOR_CYCLES) begin
   @(posedge clk);#1;
   mon=mon+1;
   if(fault_valid) begin
    out_beats=out_beats+1;
    if(clean_word!==fault_word) mismatch_seen=1;
    if(fault_last) mon=MAX_MONITOR_CYCLES+2;   // normal frame end sentinel
   end
  end
  if(mon!=(MAX_MONITOR_CYCLES+2)) begin
   $display("WARN trial stage=%0d symbol=%0d component=%0d bit=%0d: monitor timeout, out_beats=%0d",stage,symbol,component,bitpos,out_beats);
  end
  // classify
  if(mismatch_seen==0) begin
   if((det_seen!=0)&&(cor_seen!=0)) begin n_corrected=n_corrected+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=1 corrected=1 location=%0d match=1 category=corrected",stage,symbol,component?"imag":"real",bitpos,loc_seen); end
   else if(det_seen==0) begin n_silent_bounded=n_silent_bounded+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=0 corrected=0 location=- match=0 category=silent_bounded_residual",stage,symbol,component?"imag":"real",bitpos); end
   else begin n_corrected_no_flag=n_corrected_no_flag+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=1 corrected=0 location=%0d match=0 category=corrected_no_flag",stage,symbol,component?"imag":"real",bitpos,loc_seen); end
  end else begin
   if((det_seen!=0)&&(cor_seen==0)) begin n_detected_only=n_detected_only+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=1 corrected=0 location=%0d match=0 category=detected_only",stage,symbol,component?"imag":"real",bitpos,loc_seen); end
   else if(cor_seen!=0) begin n_miscorrection=n_miscorrection+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=1 corrected=1 location=%0d match=0 category=MISCORRECTION",stage,symbol,component?"imag":"real",bitpos,loc_seen); end
   else begin n_silent_unbounded=n_silent_unbounded+1; $display("TRIAL stage=%0d symbol=%0d component=%s bit=%0d detected=0 corrected=0 location=- match=0 category=silent_unbounded",stage,symbol,component?"imag":"real",bitpos); end
  end
 end
endtask

initial begin
 $readmemh("experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",input_mem);
 $display("SC01_P1_RTL threshold=%0d stage_mode=%0d total_trials=%0d (stages1-7=%0d, stage10=%0d)",THRESHOLD,STAGE_MODE,TOTAL_TRIALS,TRIALS_ST17,TRIALS_S10);
 trial=0;
 // stages 1-7
 if(STAGE_MODE!=2) begin
  for(stage_now=1;stage_now<=7;stage_now=stage_now+1) begin
   for(symbol_now=0;symbol_now<=5;symbol_now=symbol_now+1) begin
    for(component_now=0;component_now<=1;component_now=component_now+1) begin
     for(bit_now=0;bit_now<35;bit_now=bit_now+1) begin
      run_one_trial(stage_now,symbol_now,component_now,bit_now);
      trial=trial+1;
     end
    end
   end
  end
 end
 // stage 10 (upper branch)
 if(STAGE_MODE!=1) begin
  for(symbol_now=0;symbol_now<=5;symbol_now=symbol_now+1) begin
   for(component_now=0;component_now<=1;component_now=component_now+1) begin
    for(bit_now=0;bit_now<35;bit_now=bit_now+1) begin
     run_one_trial(10,symbol_now,component_now,bit_now);
     trial=trial+1;
    end
   end
  end
 end
 $display("SUMMARY threshold=%0d total=%0d corrected=%0d detected_only=%0d silent_bounded_residual=%0d miscorrection=%0d silent_unbounded=%0d corrected_no_flag=%0d",
   THRESHOLD,TOTAL_TRIALS,n_corrected,n_detected_only,n_silent_bounded,n_miscorrection,n_silent_unbounded,n_corrected_no_flag);
 $display("SUMMARY recovery_rate=%0.2f%%",100.0*(n_corrected+n_silent_bounded)/TOTAL_TRIALS);
 $finish;
end
endmodule
