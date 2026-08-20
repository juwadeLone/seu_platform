`timescale 1ns/1ps
// S1 mid-stage inject TB. 8 stages x 7 paths x 2 x 35 = 3920.
// Clean = original top_s1_gao_subfft_ecc.
// Fault = top_s1_midstage_thresholded (per-stage XOR, H*received, tau).
module sc01_s1_midstage_tb;
parameter integer THRESHOLD  = 5;
parameter integer STAGE_MIN  = 1;
parameter integer STAGE_MAX  = 1;
parameter integer PATH_MIN   = 0;
parameter integer PATH_MAX   = 6;
localparam integer N_STAGES = STAGE_MAX - STAGE_MIN + 1;
localparam integer N_PATHS  = PATH_MAX - PATH_MIN + 1;
localparam integer TOTAL_TRIALS = N_STAGES * N_PATHS * 70;
localparam integer FRAME_BEATS = 512;
localparam integer MAX_MONITOR_CYCLES = 12000;

reg clk=0,rst=1,in_valid=0,in_last=0;
reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
reg inject_enable=0;
reg [2:0]inject_path=0;
reg [3:0]inject_stage=1;
reg inject_component=0;
reg [5:0]inject_bit=0;

wire clean_valid,clean_last,fault_valid,fault_last;
wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i;
wire[279:0]clean_word={c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i};
wire[279:0]fault_word={f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i};
wire fdet,fcor,func;wire[2:0]floc;
wire inject_window;

reg[279:0]input_mem[0:511];
integer trial,stage_now,path_now,component_now,bit_now;
integer det_seen,cor_seen,unc_seen;reg[2:0]loc_seen;
integer mismatch_seen,out_beats,mon,injected,k,path_mismatch_latched;
integer n_corrected=0,n_detected_only=0,n_silent_bounded=0,n_miscorrection=0,n_silent_unbounded=0,n_corrected_no_flag=0;

top_s1_gao_subfft_ecc clean(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 clean_valid,clean_last,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i
);
top_s1_midstage_thresholded #(.THRESHOLD(THRESHOLD)) fault(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
 inject_enable,inject_path,inject_stage,inject_component,inject_bit,
 fault_valid,fault_last,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i,
 fdet,fcor,func,floc,inject_window
);

always #5 clk=~clk;

task sample_decoder_if_diverged;
 input integer pth;
 begin
  if((fault.pv[0]!=0) && (path_mismatch_latched==0)) begin
   if((fault.pathr[pth]!==clean.pathr[pth])||(fault.pathi[pth]!==clean.pathi[pth])) begin
    path_mismatch_latched=1;
    det_seen=fdet;cor_seen=fcor;unc_seen=func;loc_seen=floc;
   end
  end
 end
endtask

task run_one_trial;
 input [3:0]stage;
 input [2:0]path;
 input [0:0]component;
 input [5:0]bitpos;
 begin
  rst=1;inject_enable=0;in_valid=0;in_last=0;
  inject_stage=stage;inject_path=path;inject_component=component;inject_bit=bitpos;
  repeat(2)@(posedge clk);@(negedge clk);rst=0;
  injected=0;
  for(k=0;k<FRAME_BEATS;k=k+1) begin
   in_valid=1;in_last=(k==FRAME_BEATS-1)?1'b1:1'b0;
   {in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im}=input_mem[k];
   @(negedge clk);
   if((injected==0)&&inject_window) begin
    inject_enable=1;injected=1;
   end
  end
  in_valid=0;in_last=0;
  if(injected==0) begin
   wait(inject_window);
   @(negedge clk);
   inject_enable=1;injected=1;
  end
  @(posedge clk);#1;
  path_mismatch_latched=0;det_seen=0;cor_seen=0;unc_seen=0;loc_seen=0;
  sample_decoder_if_diverged(path);
  inject_enable=0;
  mismatch_seen=0;out_beats=0;mon=0;
  while(mon<=MAX_MONITOR_CYCLES) begin
   @(posedge clk);#1;
   mon=mon+1;
   sample_decoder_if_diverged(path);
   if(fault_valid) begin
    out_beats=out_beats+1;
    if(clean_word!==fault_word) mismatch_seen=1;
    if(fault_last) mon=MAX_MONITOR_CYCLES+2;
   end
  end
  if(mon!=(MAX_MONITOR_CYCLES+2)) begin
   $display("WARN trial stage=%0d path=%0d component=%0d bit=%0d: monitor timeout, out_beats=%0d injected=%0d",stage,path,component,bitpos,out_beats,injected);
  end
  if(mismatch_seen==0) begin
   if((det_seen!=0)&&(cor_seen!=0)) begin n_corrected=n_corrected+1; $display("TRIAL stage=%0d path=%0d component=%s bit=%0d detected=1 corrected=1 location=%0d match=1 category=corrected",stage,path,component?"imag":"real",bitpos,loc_seen); end
   else if(det_seen==0) begin n_silent_bounded=n_silent_bounded+1; $display("TRIAL stage=%0d path=%0d component=%s bit=%0d detected=0 corrected=0 location=- match=0 category=silent_bounded_residual",stage,path,component?"imag":"real",bitpos); end
   else begin n_corrected_no_flag=n_corrected_no_flag+1; $display("TRIAL stage=%0d path=%0d component=%s bit=%0d detected=1 corrected=0 location=%0d match=0 category=corrected_no_flag",stage,path,component?"imag":"real",bitpos,loc_seen); end
  end else begin
   if((det_seen!=0)&&(cor_seen==0)) begin n_detected_only=n_detected_only+1; $display("TRIAL stage=%0d path=%0d component=%s bit=%0d detected=1 corrected=0 location=%0d match=0 category=detected_only",stage,path,component?"imag":"real",bitpos,loc_seen); end
   else if(cor_seen!=0) begin n_miscorrection=n_miscorrection+1; $display("TRIAL stage=%0d path=%0d component=%s bit=%0d detected=1 corrected=1 location=%0d match=0 category=MISCORRECTION",stage,path,component?"imag":"real",bitpos,loc_seen); end
   else begin n_silent_unbounded=n_silent_unbounded+1; $display("TRIAL stage=%0d path=%0d component=%s bit=%0d detected=0 corrected=0 location=- match=0 category=silent_unbounded",stage,path,component?"imag":"real",bitpos); end
  end
 end
endtask

initial begin
 $readmemh("experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",input_mem);
 $display("SC01_S1_MIDSTAGE threshold=%0d stages=%0d..%0d paths=%0d..%0d total_trials=%0d",THRESHOLD,STAGE_MIN,STAGE_MAX,PATH_MIN,PATH_MAX,TOTAL_TRIALS);
 trial=0;
 for(stage_now=STAGE_MIN;stage_now<=STAGE_MAX;stage_now=stage_now+1) begin
  for(path_now=PATH_MIN;path_now<=PATH_MAX;path_now=path_now+1) begin
   for(component_now=0;component_now<=1;component_now=component_now+1) begin
    for(bit_now=0;bit_now<35;bit_now=bit_now+1) begin
     run_one_trial(stage_now[3:0],path_now[2:0],component_now[0:0],bit_now[5:0]);
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
