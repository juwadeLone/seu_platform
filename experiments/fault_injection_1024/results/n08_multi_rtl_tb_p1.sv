`timescale 1ns/1ps
// N08 P1 RTL multi-fault TB.  P1 eligible stages are 1..7 and 10, matching
// the N08 contract; no functional-model injection is used.
module n08_multi_rtl_tb_p1;
parameter integer THRESHOLD=3;parameter integer K_MODE=2;parameter integer TRIALS=500;
localparam integer FRAME_BEATS=512;localparam integer MAX_WAIT=14000;
reg clk=0,rst=1,in_valid=0,in_last=0;reg signed[34:0]in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im;
reg[7:0]inj_en=0,inj_comp=0;reg[23:0]inj_sym=0;reg[47:0]inj_bit=0;
wire cv,cl,fv,fl;wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i;
wire[279:0]cw={c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i};wire[279:0]fw={f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i};
wire[6:0]fdet,fcor,func;wire[20:0]floc;wire fsu,fsuc,fsun;wire[2:0]fsul;wire fsl,fslo,fsln;wire[2:0]fsll;
reg[279:0]input_mem[0:511];reg[3:0]stage[0:7];reg[2:0]symbol[0:7];reg component[0:7];reg[5:0]bitpos[0:7];reg done[0:7];
integer fs0,fy0,fc0,fb0,fs1,fy1,fc1,fb1,fs2,fy2,fc2,fb2,fs3,fy3,fc3,fb3,fs4,fy4,fc4,fb4,fs5,fy5,fc5,fb5,fs6,fy6,fc6,fb6,fs7,fy7,fc7,fb7;
reg[4095:0]site_line;integer site_fd,site_rc,site_trial;integer trial,e,q,inj_count,wait_cycles,monitor_cycles,out_beats,mismatch_seen,seen_last,det_seen,cor_seen,unc_seen;
integer n_corrected=0,n_detected_only=0,n_bounded=0,n_unbounded=0,n_miscorr=0,n_timeout=0;reg monitor_active;

top_p1_pfft_ecc clean(clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,cv,cl,c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i);
n08_p1_multifault_top #(.THRESHOLD(THRESHOLD)) fault(
 clk,rst,in_valid,in_last,in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,inj_en,inj_sym,inj_comp,inj_bit,
 fv,fl,f0r,f0i,f1r,f1i,f2r,f2i,f3r,f3i,fdet,fcor,func,floc,fsu,fsuc,fsun,fsul,fsl,fslo,fsln,fsll);
always #5 clk=~clk;
always @(posedge clk)begin #1;if(monitor_active&&fv)begin out_beats=out_beats+1;if(cw!==fw)mismatch_seen=1;if(fl)seen_last=1;end end
function stage_window;input[3:0]s;begin case(s)
 1:stage_window=fault.u.s1.work_valid&&fault.u.s1.work_second;2:stage_window=fault.u.s2.work_valid&&fault.u.s2.work_second;
 3:stage_window=fault.u.s3.work_valid&&fault.u.s3.work_second;4:stage_window=fault.u.s4.work_valid&&fault.u.s4.work_second;
 5:stage_window=fault.u.s5.work_valid&&fault.u.s5.work_second;6:stage_window=fault.u.s6.work_valid&&fault.u.s6.work_second;
 7:stage_window=fault.u.s7.work_valid&&fault.u.s7.work_second;10:stage_window=(fault.u.s10.pair_phase==1'b1);default:stage_window=0;
 endcase end endfunction
task capture_flag;input integer x;begin case(stage[x])
 1:begin det_seen=det_seen|fdet[0];cor_seen=cor_seen|fcor[0];unc_seen=unc_seen|func[0];end
 2:begin det_seen=det_seen|fdet[1];cor_seen=cor_seen|fcor[1];unc_seen=unc_seen|func[1];end
 3:begin det_seen=det_seen|fdet[2];cor_seen=cor_seen|fcor[2];unc_seen=unc_seen|func[2];end
 4:begin det_seen=det_seen|fdet[3];cor_seen=cor_seen|fcor[3];unc_seen=unc_seen|func[3];end
 5:begin det_seen=det_seen|fdet[4];cor_seen=cor_seen|fcor[4];unc_seen=unc_seen|func[4];end
 6:begin det_seen=det_seen|fdet[5];cor_seen=cor_seen|fcor[5];unc_seen=unc_seen|func[5];end
 7:begin det_seen=det_seen|fdet[6];cor_seen=cor_seen|fcor[6];unc_seen=unc_seen|func[6];end
 10:begin det_seen=det_seen|fsu|fsl;cor_seen=cor_seen|fsuc|fslo;unc_seen=unc_seen|fsun|fsln;end
 endcase end endtask
task load_site;begin
 site_line=0;$fgets(site_line,site_fd);
 if(K_MODE==2)site_rc=$sscanf(site_line,"%d,%d:%d:%d:%d;%d:%d:%d:%d",site_trial,fs0,fy0,fc0,fb0,fs1,fy1,fc1,fb1);
 else if(K_MODE==5)site_rc=$sscanf(site_line,"%d,%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d",site_trial,fs0,fy0,fc0,fb0,fs1,fy1,fc1,fb1,fs2,fy2,fc2,fb2,fs3,fy3,fc3,fb3,fs4,fy4,fc4,fb4);
 else site_rc=$sscanf(site_line,"%d,%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d;%d:%d:%d:%d",site_trial,fs0,fy0,fc0,fb0,fs1,fy1,fc1,fb1,fs2,fy2,fc2,fb2,fs3,fy3,fc3,fb3,fs4,fy4,fc4,fb4,fs5,fy5,fc5,fb5,fs6,fy6,fc6,fb6,fs7,fy7,fc7,fb7);
 if(site_rc<1+4*K_MODE)$display("FATAL site parse trial=%0d rc=%0d",trial,site_rc);
 stage[0]=fs0;symbol[0]=fy0;component[0]=fc0;bitpos[0]=fb0;stage[1]=fs1;symbol[1]=fy1;component[1]=fc1;bitpos[1]=fb1;
 if(K_MODE>=5)begin stage[2]=fs2;symbol[2]=fy2;component[2]=fc2;bitpos[2]=fb2;stage[3]=fs3;symbol[3]=fy3;component[3]=fc3;bitpos[3]=fb3;stage[4]=fs4;symbol[4]=fy4;component[4]=fc4;bitpos[4]=fb4;end
 if(K_MODE==8)begin stage[5]=fs5;symbol[5]=fy5;component[5]=fc5;bitpos[5]=fb5;stage[6]=fs6;symbol[6]=fy6;component[6]=fc6;bitpos[6]=fb6;stage[7]=fs7;symbol[7]=fy7;component[7]=fc7;bitpos[7]=fb7;end
 end endtask
task inject_ready;integer x;begin
 inj_en=0;for(x=0;x<K_MODE;x=x+1)if(!done[x]&&stage_window(stage[x]))begin
  inj_en[stage[x]==10?7:stage[x]-1]=1;inj_sym[(stage[x]==10?7:stage[x]-1)*3 +: 3]=symbol[x];inj_comp[stage[x]==10?7:stage[x]-1]=component[x];inj_bit[(stage[x]==10?7:stage[x]-1)*6 +: 6]=bitpos[x];done[x]=1;inj_count=inj_count+1;
  $display("INJECT trial=%0d stage=%0d symbol=%0d component=%0d bit=%0d",trial,stage[x],symbol[x],component[x],bitpos[x]);end
 end endtask
task run_trial;begin
 load_site;for(q=0;q<8;q=q+1)done[q]=0;inj_en=0;inj_count=0;det_seen=0;cor_seen=0;unc_seen=0;monitor_active=0;mismatch_seen=0;out_beats=0;seen_last=0;
 rst=1;in_valid=0;in_last=0;repeat(2)@(posedge clk);@(negedge clk);rst=0;monitor_active=1;
 for(q=0;q<FRAME_BEATS;q=q+1)begin in_valid=1;in_last=(q==FRAME_BEATS-1);{in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im}=input_mem[q];@(negedge clk);inject_ready;if(inj_en!=0)begin @(posedge clk);#1;for(e=0;e<K_MODE;e=e+1)if(done[e])capture_flag(e);inj_en=0;end end
 in_valid=0;in_last=0;wait_cycles=0;while(inj_count<K_MODE&&wait_cycles<MAX_WAIT)begin @(negedge clk);inject_ready;if(inj_en!=0)begin @(posedge clk);#1;for(e=0;e<K_MODE;e=e+1)if(done[e])capture_flag(e);inj_en=0;end wait_cycles=wait_cycles+1;end
 if(inj_count!=K_MODE)$display("WARN trial=%0d injected=%0d expected=%0d",trial,inj_count,K_MODE);monitor_cycles=0;while(!seen_last&&monitor_cycles<MAX_WAIT)begin @(posedge clk);monitor_cycles=monitor_cycles+1;end
 if(!seen_last)begin n_timeout=n_timeout+1;$display("TRIAL trial=%0d k=%0d injected=%0d match=%0d category=TIMEOUT",trial,K_MODE,inj_count,!mismatch_seen);end
 else if(!mismatch_seen&&cor_seen)begin n_corrected=n_corrected+1;$display("TRIAL trial=%0d k=%0d injected=%0d detected=%0d corrected=1 match=1 category=corrected",trial,K_MODE,inj_count,det_seen);end
 else if(!mismatch_seen&&!det_seen)begin n_bounded=n_bounded+1;$display("TRIAL trial=%0d k=%0d injected=%0d detected=0 corrected=0 match=1 category=silent_bounded_residual",trial,K_MODE,inj_count);end
 else if(mismatch_seen&&cor_seen)begin n_miscorr=n_miscorr+1;$display("TRIAL trial=%0d k=%0d injected=%0d detected=%0d corrected=1 match=0 category=MISCORRECTION",trial,K_MODE,inj_count,det_seen);end
 else if(mismatch_seen&&det_seen)begin n_detected_only=n_detected_only+1;$display("TRIAL trial=%0d k=%0d injected=%0d detected=1 corrected=0 match=0 category=detected_only",trial,K_MODE,inj_count);end
 else begin n_unbounded=n_unbounded+1;$display("TRIAL trial=%0d k=%0d injected=%0d detected=0 corrected=0 match=0 category=silent_unbounded",trial,K_MODE,inj_count);end monitor_active=0;
 end endtask
initial begin
 $readmemh("experiments/fault_injection_1024/common/vectors/qualification_input_10frames.hex",input_mem);if(!$value$plusargs("SITE=%s",site_line))site_line="experiments/fault_injection_1024/results/n08_multi_k2_p1_v1_001/sites_k2.csv";
 site_fd=$fopen(site_line,"r");if(!site_fd)$finish;$fgets(site_line,site_fd);$display("N08_P1_RTL threshold=%0d k=%0d trials=%0d site=%s",THRESHOLD,K_MODE,TRIALS,site_line);
 for(trial=0;trial<TRIALS;trial=trial+1)run_trial;
 $display("SUMMARY arch=P1 k=%0d total=%0d corrected=%0d detected_only=%0d silent_bounded_residual=%0d miscorrection=%0d silent_unbounded=%0d timeout=%0d",K_MODE,TRIALS,n_corrected,n_detected_only,n_bounded,n_miscorr,n_unbounded,n_timeout);$fclose(site_fd);$finish;
end
endmodule
