`timescale 1ns/1ps

// The clean symbols and the received symbols are separate ports.  Residuals
// are computed only from clean/pre-fault symbols; received faults therefore
// cannot cancel their own syndrome.
(* keep_hierarchy = "yes" *) module arithmetic_boundary_from_clean_v5(
 input wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,c4r,c4i,c5r,c5i,
 input wire signed[34:0]r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i,r4r,r4i,r5r,r5i,
 output wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i
);
(* keep = "true" *) wire signed[38:0]res0r=$signed(c4r)-($signed(c0r)+$signed(c1r)+$signed(c2r)+$signed(c3r));
(* keep = "true" *) wire signed[38:0]res0i=$signed(c4i)-($signed(c0i)+$signed(c1i)+$signed(c2i)+$signed(c3i));
(* keep = "true" *) wire signed[38:0]res1r=$signed(c5r)-($signed(c0r)-$signed(c1i)-$signed(c2r)+$signed(c3i));
(* keep = "true" *) wire signed[38:0]res1i=$signed(c5i)-($signed(c0i)+$signed(c1r)-$signed(c2i)-$signed(c3r));
arithmetic_corrector_643 u_corrector(
 r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i,r4r,r4i,r5r,r5i,
 res0r,res0i,res1r,res1i,d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i
);
endmodule


// Four protected operands are encoded before the operator.  All six streams
// execute the butterfly and twiddle independently; check symbols are never
// generated from the four functional results.
(* keep_hierarchy = "yes" *) module independent_butterfly_ecc_v5 #(
 parameter integer TRIVIAL_UPPER=0,
 parameter integer BYPASS_LOWER=0,
 parameter integer SUBFFT_SINGLE_ROTATION=0
)(
 input wire signed[34:0]a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,
 input wire signed[34:0]b0r,b0i,b1r,b1i,b2r,b2i,b3r,b3i,
 input wire [9:0]upper_exponent,input wire [9:0]lower_exponent,
 output wire signed[34:0]u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,
 output wire signed[34:0]l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i
);
wire signed[34:0] ar[0:5],ai[0:5],br[0:5],bi[0:5];
assign ar[0]=a0r;assign ai[0]=a0i;assign ar[1]=a1r;assign ai[1]=a1i;
assign ar[2]=a2r;assign ai[2]=a2i;assign ar[3]=a3r;assign ai[3]=a3i;
assign br[0]=b0r;assign bi[0]=b0i;assign br[1]=b1r;assign bi[1]=b1i;
assign br[2]=b2r;assign bi[2]=b2i;assign br[3]=b3r;assign bi[3]=b3i;
wire signed[34:0]a01r=a0r+a1r,a01i=a0i+a1i,a23r=a2r+a3r,a23i=a2i+a3i;
wire signed[34:0]b01r=b0r+b1r,b01i=b0i+b1i,b23r=b2r+b3r,b23i=b2i+b3i;
assign ar[4]=a01r+a23r;assign ai[4]=a01i+a23i;
assign br[4]=b01r+b23r;assign bi[4]=b01i+b23i;
wire signed[34:0]aw1r=-a1i,aw1i=a1r,aw2r=-a2r,aw2i=-a2i,aw3r=a3i,aw3i=-a3r;
wire signed[34:0]bw1r=-b1i,bw1i=b1r,bw2r=-b2r,bw2i=-b2i,bw3r=b3i,bw3i=-b3r;
assign ar[5]=(a0r+aw1r)+(aw2r+aw3r);assign ai[5]=(a0i+aw1i)+(aw2i+aw3i);
assign br[5]=(b0r+bw1r)+(bw2r+bw3r);assign bi[5]=(b0i+bw1i)+(bw2i+bw3i);

wire signed[34:0]upper_pre_r[0:5],upper_pre_i[0:5],lower_pre_r[0:5],lower_pre_i[0:5];
wire signed[34:0]upper_clean_r[0:5],upper_clean_i[0:5],lower_clean_r[0:5],lower_clean_i[0:5];
(* keep = "true" *) wire signed[34:0]upper_received_r[0:5],upper_received_i[0:5],lower_received_r[0:5],lower_received_i[0:5];
genvar g;
generate for(g=0;g<6;g=g+1)begin:operators
 wire signed[34:0]sumr=ar[g]+br[g],sumi=ai[g]+bi[g];
 wire signed[34:0]diffr=ar[g]-br[g],diffi=ai[g]-bi[g];
 assign upper_pre_r[g]=sumr>>>1;assign upper_pre_i[g]=sumi>>>1;
 assign lower_pre_r[g]=diffr>>>1;assign lower_pre_i[g]=diffi>>>1;
 if(SUBFFT_SINGLE_ROTATION!=0)begin:subfft_unrotated_upper
  assign upper_clean_r[g]=upper_pre_r[g];assign upper_clean_i[g]=upper_pre_i[g];
 end else if(TRIVIAL_UPPER!=0)begin:trivial_upper
  fft_complex_rotate_trivial_1024 upper_rotation(upper_pre_r[g],upper_pre_i[g],upper_exponent,upper_clean_r[g],upper_clean_i[g]);
 end else begin:generic_upper
  fft_complex_mul_q28 upper_rotation(upper_pre_r[g],upper_pre_i[g],upper_exponent,upper_clean_r[g],upper_clean_i[g]);
 end
 if(BYPASS_LOWER!=0)begin:bypass_lower
  assign lower_clean_r[g]=lower_pre_r[g];assign lower_clean_i[g]=lower_pre_i[g];
 end else begin:generic_lower
  fft_complex_mul_q28 lower_rotation(lower_pre_r[g],lower_pre_i[g],lower_exponent,lower_clean_r[g],lower_clean_i[g]);
 end
 assign upper_received_r[g]=upper_clean_r[g];assign upper_received_i[g]=upper_clean_i[g];
 assign lower_received_r[g]=lower_clean_r[g];assign lower_received_i[g]=lower_clean_i[g];
end endgenerate

arithmetic_boundary_from_clean_v5 upper_boundary(
 upper_received_r[0],upper_received_i[0],upper_received_r[1],upper_received_i[1],upper_received_r[2],upper_received_i[2],upper_received_r[3],upper_received_i[3],upper_received_r[4],upper_received_i[4],upper_received_r[5],upper_received_i[5],
 upper_clean_r[0],upper_clean_i[0],upper_clean_r[1],upper_clean_i[1],upper_clean_r[2],upper_clean_i[2],upper_clean_r[3],upper_clean_i[3],upper_clean_r[4],upper_clean_i[4],upper_clean_r[5],upper_clean_i[5],
 u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i
);
arithmetic_boundary_from_clean_v5 lower_boundary(
 lower_received_r[0],lower_received_i[0],lower_received_r[1],lower_received_i[1],lower_received_r[2],lower_received_i[2],lower_received_r[3],lower_received_i[3],lower_received_r[4],lower_received_i[4],lower_received_r[5],lower_received_i[5],
 lower_clean_r[0],lower_clean_i[0],lower_clean_r[1],lower_clean_i[1],lower_clean_r[2],lower_clean_i[2],lower_clean_r[3],lower_clean_i[3],lower_clean_r[4],lower_clean_i[4],lower_clean_r[5],lower_clean_i[5],
 l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i
);
endmodule


// Build only the two check-operator results.  The four functional results are
// supplied by the protected stage itself; this module therefore adds exactly
// two independent arithmetic streams rather than recomputing four shadow
// functional streams.  Both check operands are encoded before the butterfly.
(* keep_hierarchy = "yes" *) module independent_check_operator_pair_v5(
 input wire signed[34:0]a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,
 input wire signed[34:0]b0r,b0i,b1r,b1i,b2r,b2i,b3r,b3i,
 input wire branch_upper,input wire[9:0]exponent,
 output wire signed[34:0]c4r,c4i,c5r,c5i
);
wire signed[34:0]a01r=a0r+a1r,a01i=a0i+a1i,a23r=a2r+a3r,a23i=a2i+a3i;
wire signed[34:0]b01r=b0r+b1r,b01i=b0i+b1i,b23r=b2r+b3r,b23i=b2i+b3i;
wire signed[34:0]a4r=a01r+a23r,a4i=a01i+a23i,b4r=b01r+b23r,b4i=b01i+b23i;
wire signed[34:0]a1jr=-a1i,a1ji=a1r,a2nr=-a2r,a2ni=-a2i,a3njr=a3i,a3nji=-a3r;
wire signed[34:0]b1jr=-b1i,b1ji=b1r,b2nr=-b2r,b2ni=-b2i,b3njr=b3i,b3nji=-b3r;
wire signed[34:0]a5r=(a0r+a1jr)+(a2nr+a3njr),a5i=(a0i+a1ji)+(a2ni+a3nji);
wire signed[34:0]b5r=(b0r+b1jr)+(b2nr+b3njr),b5i=(b0i+b1ji)+(b2ni+b3nji);
wire signed[34:0]s4r=a4r+b4r,s4i=a4i+b4i,d4r=a4r-b4r,d4i=a4i-b4i;
wire signed[34:0]s5r=a5r+b5r,s5i=a5i+b5i,d5r=a5r-b5r,d5i=a5i-b5i;
wire signed[34:0]pre4r=branch_upper?(s4r>>>1):(d4r>>>1);
wire signed[34:0]pre4i=branch_upper?(s4i>>>1):(d4i>>>1);
wire signed[34:0]pre5r=branch_upper?(s5r>>>1):(d5r>>>1);
wire signed[34:0]pre5i=branch_upper?(s5i>>>1):(d5i>>>1);
fft_complex_mul_q28 check_operator0(pre4r,pre4i,exponent,c4r,c4i);
fft_complex_mul_q28 check_operator1(pre5r,pre5i,exponent,c5r,c5i);
endmodule


(* keep_hierarchy = "yes" *) module independent_rotation_ecc_v5 #(
 parameter integer TRIVIAL_ROTATION=0
)(
 input wire signed[34:0]a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,
 input wire [9:0]exponent,
 output wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i
);
wire signed[34:0]ar[0:5],ai[0:5],cr[0:5],ci[0:5];
(* keep = "true" *) wire signed[34:0]rr[0:5],ri[0:5];
assign ar[0]=a0r;assign ai[0]=a0i;assign ar[1]=a1r;assign ai[1]=a1i;
assign ar[2]=a2r;assign ai[2]=a2i;assign ar[3]=a3r;assign ai[3]=a3i;
wire signed[34:0]a01r=a0r+a1r,a01i=a0i+a1i,a23r=a2r+a3r,a23i=a2i+a3i;
assign ar[4]=a01r+a23r;assign ai[4]=a01i+a23i;
wire signed[34:0]w1r=-a1i,w1i=a1r,w2r=-a2r,w2i=-a2i,w3r=a3i,w3i=-a3r;
assign ar[5]=(a0r+w1r)+(w2r+w3r);assign ai[5]=(a0i+w1i)+(w2i+w3i);
genvar g;
generate for(g=0;g<6;g=g+1)begin:rotation
 if(TRIVIAL_ROTATION!=0)begin:trivial
  fft_complex_rotate_trivial_1024 u(ar[g],ai[g],exponent,cr[g],ci[g]);
 end else begin:generic
  fft_complex_mul_q28 u(ar[g],ai[g],exponent,cr[g],ci[g]);
 end
 assign rr[g]=cr[g];assign ri[g]=ci[g];
end endgenerate
arithmetic_boundary_from_clean_v5 boundary(
 rr[0],ri[0],rr[1],ri[1],rr[2],ri[2],rr[3],ri[3],rr[4],ri[4],rr[5],ri[5],
 cr[0],ci[0],cr[1],ci[1],cr[2],ci[2],cr[3],ci[3],cr[4],ci[4],cr[5],ci[5],
 d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i
);
endmodule


(* keep_hierarchy = "yes" *) module gao_corrector_743_v5(
 input wire signed[34:0]p0r,p0i,p1r,p1i,p2r,p2i,p3r,p3i,p4r,p4i,p5r,p5i,p6r,p6i,
 input wire signed[38:0]res0r,res0i,res1r,res1i,res2r,res2i,
 output reg signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i
);
reg signed[38:0]s0r,s0i,s1r,s1i,s2r,s2i,er,ei;reg[2:0]loc;reg found;
always @* begin
 s0r=$signed(p0r)+$signed(p2r)+$signed(p4r)+$signed(p6r)-res0r;s0i=$signed(p0i)+$signed(p2i)+$signed(p4i)+$signed(p6i)-res0i;
 s1r=$signed(p1r)+$signed(p2r)+$signed(p5r)+$signed(p6r)-res1r;s1i=$signed(p1i)+$signed(p2i)+$signed(p5i)+$signed(p6i)-res1i;
 s2r=$signed(p3r)+$signed(p4r)+$signed(p5r)+$signed(p6r)-res2r;s2i=$signed(p3i)+$signed(p4i)+$signed(p5i)+$signed(p6i)-res2i;
 d0r=p2r;d0i=p2i;d1r=p4r;d1i=p4i;d2r=p5r;d2i=p5i;d3r=p6r;d3i=p6i;found=0;loc=0;er=0;ei=0;
 if((s0r!=0)||(s0i!=0)||(s1r!=0)||(s1i!=0)||(s2r!=0)||(s2i!=0))begin
  if((s0r!=0||s0i!=0)&&(s1r==0&&s1i==0)&&(s2r==0&&s2i==0))begin loc=0;found=1;er=s0r;ei=s0i;end
  else if((s1r!=0||s1i!=0)&&(s0r==0&&s0i==0)&&(s2r==0&&s2i==0))begin loc=1;found=1;er=s1r;ei=s1i;end
  else if((s0r==s1r)&&(s0i==s1i)&&(s2r==0&&s2i==0))begin loc=2;found=1;er=s0r;ei=s0i;end
  else if((s2r!=0||s2i!=0)&&(s0r==0&&s0i==0)&&(s1r==0&&s1i==0))begin loc=3;found=1;er=s2r;ei=s2i;end
  else if((s0r==s2r)&&(s0i==s2i)&&(s1r==0&&s1i==0))begin loc=4;found=1;er=s0r;ei=s0i;end
  else if((s1r==s2r)&&(s1i==s2i)&&(s0r==0&&s0i==0))begin loc=5;found=1;er=s1r;ei=s1i;end
  else if((s0r==s1r)&&(s0i==s1i)&&(s0r==s2r)&&(s0i==s2i))begin loc=6;found=1;er=s0r;ei=s0i;end
  if(found)case(loc)
   2:begin d0r=p2r-er[34:0];d0i=p2i-ei[34:0];end
   4:begin d1r=p4r-er[34:0];d1i=p4i-ei[34:0];end
   5:begin d2r=p5r-er[34:0];d2i=p5i-ei[34:0];end
   6:begin d3r=p6r-er[34:0];d3i=p6i-ei[34:0];end
  endcase
 end
end
endmodule


(* keep_hierarchy = "yes" *) module gao_boundary_from_clean_v5(
 input wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,c4r,c4i,c5r,c5i,c6r,c6i,
 input wire signed[34:0]r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i,r4r,r4i,r5r,r5i,r6r,r6i,
 output wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i
);
(* keep = "true" *)wire signed[38:0]res0r=$signed(c0r)+$signed(c2r)+$signed(c4r)+$signed(c6r);
(* keep = "true" *)wire signed[38:0]res0i=$signed(c0i)+$signed(c2i)+$signed(c4i)+$signed(c6i);
(* keep = "true" *)wire signed[38:0]res1r=$signed(c1r)+$signed(c2r)+$signed(c5r)+$signed(c6r);
(* keep = "true" *)wire signed[38:0]res1i=$signed(c1i)+$signed(c2i)+$signed(c5i)+$signed(c6i);
(* keep = "true" *)wire signed[38:0]res2r=$signed(c3r)+$signed(c4r)+$signed(c5r)+$signed(c6r);
(* keep = "true" *)wire signed[38:0]res2i=$signed(c3i)+$signed(c4i)+$signed(c5i)+$signed(c6i);
gao_corrector_743_v5 u_corrector(
 r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i,r4r,r4i,r5r,r5i,r6r,r6i,
 res0r,res0i,res1r,res1i,res2r,res2i,d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i
);
endmodule

// ============================================================================
// SC-01: Gao-threshold versions (added 2026-08-10)
// arithmetic_boundary_from_clean_v5_thresholded wraps the thresholded
// arithmetic_corrector_643 and exposes detected/corrected/uncorrectable/
// error_location flags.
// ============================================================================
(* keep_hierarchy = "yes" *) module arithmetic_boundary_from_clean_v5_thresholded #(
 parameter integer THRESHOLD = 0
)(
 input wire signed[34:0]c0r,c0i,c1r,c1i,c2r,c2i,c3r,c3i,c4r,c4i,c5r,c5i,
 input wire signed[34:0]r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i,r4r,r4i,r5r,r5i,
 output wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 output wire detected,output wire corrected,output wire uncorrectable,output wire miscorrected,
 output wire[2:0] error_location
);
(* keep = "true" *) wire signed[38:0]res0r=$signed(c4r)-($signed(c0r)+$signed(c1r)+$signed(c2r)+$signed(c3r));
(* keep = "true" *) wire signed[38:0]res0i=$signed(c4i)-($signed(c0i)+$signed(c1i)+$signed(c2i)+$signed(c3i));
(* keep = "true" *) wire signed[38:0]res1r=$signed(c5r)-($signed(c0r)-$signed(c1i)-$signed(c2r)+$signed(c3i));
(* keep = "true" *) wire signed[38:0]res1i=$signed(c5i)-($signed(c0i)+$signed(c1r)-$signed(c2i)-$signed(c3r));
arithmetic_corrector_643_thresholded #(.THRESHOLD(THRESHOLD)) u_corrector(
 r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i,r4r,r4i,r5r,r5i,
 res0r,res0i,res1r,res1i,d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 detected,corrected,uncorrectable,miscorrected,error_location
);
endmodule

// Independent butterfly ECC with Gao-threshold correctors and a fault
// injection hook: when inject_enable is high, one bit of the received
// symbol (inject_symbol, 0..5) is flipped (inject_component: 0=real,1=imag,
// inject_bit: 0..34) BEFORE the corrector, i.e. on the received path while
// the residual is still computed from the clean symbols.
(* keep_hierarchy = "yes" *) module independent_butterfly_ecc_v5_thresholded #(
 parameter integer TRIVIAL_UPPER=0,
 parameter integer BYPASS_LOWER=0,
 parameter integer SUBFFT_SINGLE_ROTATION=0,
 parameter integer THRESHOLD=0
)(
 input wire signed[34:0]a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,
 input wire signed[34:0]b0r,b0i,b1r,b1i,b2r,b2i,b3r,b3i,
 input wire [9:0]upper_exponent,input wire [9:0]lower_exponent,
 input wire inject_enable,
 input wire [2:0]inject_symbol,
 input wire inject_component,
 input wire [5:0]inject_bit,
 output wire signed[34:0]u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,
 output wire signed[34:0]l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i,
 output wire up_detected,up_corrected,up_uncorrectable,up_miscorrected,output wire[2:0]up_error_location,
 output wire lo_detected,lo_corrected,lo_uncorrectable,lo_miscorrected,output wire[2:0]lo_error_location
);
wire signed[34:0] ar[0:5],ai[0:5],br[0:5],bi[0:5];
assign ar[0]=a0r;assign ai[0]=a0i;assign ar[1]=a1r;assign ai[1]=a1i;
assign ar[2]=a2r;assign ai[2]=a2i;assign ar[3]=a3r;assign ai[3]=a3i;
assign br[0]=b0r;assign bi[0]=b0i;assign br[1]=b1r;assign bi[1]=b1i;
assign br[2]=b2r;assign bi[2]=b2i;assign br[3]=b3r;assign bi[3]=b3i;
wire signed[34:0]a01r=a0r+a1r,a01i=a0i+a1i,a23r=a2r+a3r,a23i=a2i+a3i;
wire signed[34:0]b01r=b0r+b1r,b01i=b0i+b1i,b23r=b2r+b3r,b23i=b2i+b3i;
assign ar[4]=a01r+a23r;assign ai[4]=a01i+a23i;
assign br[4]=b01r+b23r;assign bi[4]=b01i+b23i;
wire signed[34:0]aw1r=-a1i,aw1i=a1r,aw2r=-a2r,aw2i=-a2i,aw3r=a3i,aw3i=-a3r;
wire signed[34:0]bw1r=-b1i,bw1i=b1r,bw2r=-b2r,bw2i=-b2i,bw3r=b3i,bw3i=-b3r;
assign ar[5]=(a0r+aw1r)+(aw2r+aw3r);assign ai[5]=(a0i+aw1i)+(aw2i+aw3i);
assign br[5]=(b0r+bw1r)+(bw2r+bw3r);assign bi[5]=(b0i+bw1i)+(bw2i+bw3i);

wire signed[34:0]upper_pre_r[0:5],upper_pre_i[0:5],lower_pre_r[0:5],lower_pre_i[0:5];
wire signed[34:0]upper_clean_r[0:5],upper_clean_i[0:5],lower_clean_r[0:5],lower_clean_i[0:5];
(* keep = "true" *) wire signed[34:0]upper_received_r[0:5],upper_received_i[0:5],lower_received_r[0:5],lower_received_i[0:5];
genvar g;
generate for(g=0;g<6;g=g+1)begin:operators
 wire signed[34:0]sumr=ar[g]+br[g],sumi=ai[g]+bi[g];
 wire signed[34:0]diffr=ar[g]-br[g],diffi=ai[g]-bi[g];
 assign upper_pre_r[g]=sumr>>>1;assign upper_pre_i[g]=sumi>>>1;
 assign lower_pre_r[g]=diffr>>>1;assign lower_pre_i[g]=diffi>>>1;
 if(SUBFFT_SINGLE_ROTATION!=0)begin:subfft_unrotated_upper
  assign upper_clean_r[g]=upper_pre_r[g];assign upper_clean_i[g]=upper_pre_i[g];
 end else if(TRIVIAL_UPPER!=0)begin:trivial_upper
  fft_complex_rotate_trivial_1024 upper_rotation(upper_pre_r[g],upper_pre_i[g],upper_exponent,upper_clean_r[g],upper_clean_i[g]);
 end else begin:generic_upper
  fft_complex_mul_q28 upper_rotation(upper_pre_r[g],upper_pre_i[g],upper_exponent,upper_clean_r[g],upper_clean_i[g]);
 end
 if(BYPASS_LOWER!=0)begin:bypass_lower
  assign lower_clean_r[g]=lower_pre_r[g];assign lower_clean_i[g]=lower_pre_i[g];
 end else begin:generic_lower
  fft_complex_mul_q28 lower_rotation(lower_pre_r[g],lower_pre_i[g],lower_exponent,lower_clean_r[g],lower_clean_i[g]);
 end
 wire signed[34:0]up_inj_r=(inject_enable&&(inject_symbol==g)&&(inject_component==0))?(upper_clean_r[g]^(35'sd1<<inject_bit)):upper_clean_r[g];
 wire signed[34:0]up_inj_i=(inject_enable&&(inject_symbol==g)&&(inject_component==1))?(upper_clean_i[g]^(35'sd1<<inject_bit)):upper_clean_i[g];
 wire signed[34:0]lo_inj_r=(inject_enable&&(inject_symbol==g)&&(inject_component==0))?(lower_clean_r[g]^(35'sd1<<inject_bit)):lower_clean_r[g];
 wire signed[34:0]lo_inj_i=(inject_enable&&(inject_symbol==g)&&(inject_component==1))?(lower_clean_i[g]^(35'sd1<<inject_bit)):lower_clean_i[g];
 assign upper_received_r[g]=up_inj_r;assign upper_received_i[g]=up_inj_i;
 assign lower_received_r[g]=lo_inj_r;assign lower_received_i[g]=lo_inj_i;
end endgenerate

arithmetic_boundary_from_clean_v5_thresholded #(.THRESHOLD(THRESHOLD)) upper_boundary(
 upper_clean_r[0],upper_clean_i[0],upper_clean_r[1],upper_clean_i[1],upper_clean_r[2],upper_clean_i[2],upper_clean_r[3],upper_clean_i[3],upper_clean_r[4],upper_clean_i[4],upper_clean_r[5],upper_clean_i[5],
 upper_received_r[0],upper_received_i[0],upper_received_r[1],upper_received_i[1],upper_received_r[2],upper_received_i[2],upper_received_r[3],upper_received_i[3],upper_received_r[4],upper_received_i[4],upper_received_r[5],upper_received_i[5],
 u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,
 up_detected,up_corrected,up_uncorrectable,up_miscorrected,up_error_location
);
arithmetic_boundary_from_clean_v5_thresholded #(.THRESHOLD(THRESHOLD)) lower_boundary(
 lower_clean_r[0],lower_clean_i[0],lower_clean_r[1],lower_clean_i[1],lower_clean_r[2],lower_clean_i[2],lower_clean_r[3],lower_clean_i[3],lower_clean_r[4],lower_clean_i[4],lower_clean_r[5],lower_clean_i[5],
 lower_received_r[0],lower_received_i[0],lower_received_r[1],lower_received_i[1],lower_received_r[2],lower_received_i[2],lower_received_r[3],lower_received_i[3],lower_received_r[4],lower_received_i[4],lower_received_r[5],lower_received_i[5],
 l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i,
 lo_detected,lo_corrected,lo_uncorrectable,lo_miscorrected,lo_error_location
);
endmodule

// ============================================================================
// SC-01 方案B: un-compensated wrappers (added 2026-08-10).
// No clean/received dual ports: the codeword feeds the corrector directly.
// ============================================================================
(* keep_hierarchy = "yes" *) module arithmetic_boundary_uncomp_v5 #(
 parameter integer THRESHOLD = 8
)(
 input wire signed[34:0]s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i,s4r,s4i,s5r,s5i,
 output wire signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 output wire detected,output wire corrected,output wire uncorrectable,
 output wire[2:0] error_location
);
arithmetic_corrector_643_uncomp #(.THRESHOLD(THRESHOLD)) u_corrector(
 s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i,s4r,s4i,s5r,s5i,
 d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 detected,corrected,uncorrectable,error_location
);
endmodule

// Un-compensated independent butterfly ECC: the six rotated codeword symbols
// feed the un-compensated corrector directly (no clean/received aliasing).
// Fault-injection hook flips one bit of the codeword before the corrector.
(* keep_hierarchy = "yes" *) module independent_butterfly_ecc_v5_uncomp #(
 parameter integer TRIVIAL_UPPER=0,
 parameter integer BYPASS_LOWER=0,
 parameter integer SUBFFT_SINGLE_ROTATION=0,
 parameter integer THRESHOLD=8
)(
 input wire signed[34:0]a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i,
 input wire signed[34:0]b0r,b0i,b1r,b1i,b2r,b2i,b3r,b3i,
 input wire [9:0]upper_exponent,input wire [9:0]lower_exponent,
 input wire inject_enable,
 input wire [2:0]inject_symbol,
 input wire inject_component,
 input wire [5:0]inject_bit,
 output wire signed[34:0]u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,
 output wire signed[34:0]l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i,
 output wire up_detected,up_corrected,up_uncorrectable,output wire[2:0]up_error_location,
 output wire lo_detected,lo_corrected,lo_uncorrectable,output wire[2:0]lo_error_location
);
wire signed[34:0] ar[0:5],ai[0:5],br[0:5],bi[0:5];
assign ar[0]=a0r;assign ai[0]=a0i;assign ar[1]=a1r;assign ai[1]=a1i;
assign ar[2]=a2r;assign ai[2]=a2i;assign ar[3]=a3r;assign ai[3]=a3i;
assign br[0]=b0r;assign bi[0]=b0i;assign br[1]=b1r;assign bi[1]=b1i;
assign br[2]=b2r;assign bi[2]=b2i;assign br[3]=b3r;assign bi[3]=b3i;
wire signed[34:0]a01r=a0r+a1r,a01i=a0i+a1i,a23r=a2r+a3r,a23i=a2i+a3i;
wire signed[34:0]b01r=b0r+b1r,b01i=b0i+b1i,b23r=b2r+b3r,b23i=b2i+b3i;
assign ar[4]=a01r+a23r;assign ai[4]=a01i+a23i;
assign br[4]=b01r+b23r;assign bi[4]=b01i+b23i;
wire signed[34:0]aw1r=-a1i,aw1i=a1r,aw2r=-a2r,aw2i=-a2i,aw3r=a3i,aw3i=-a3r;
wire signed[34:0]bw1r=-b1i,bw1i=b1r,bw2r=-b2r,bw2i=-b2i,bw3r=b3i,bw3i=-b3r;
assign ar[5]=(a0r+aw1r)+(aw2r+aw3r);assign ai[5]=(a0i+aw1i)+(aw2i+aw3i);
assign br[5]=(b0r+bw1r)+(bw2r+bw3r);assign bi[5]=(b0i+bw1i)+(bw2i+bw3i);

wire signed[34:0]upper_pre_r[0:5],upper_pre_i[0:5],lower_pre_r[0:5],lower_pre_i[0:5];
wire signed[34:0]upper_rot_r[0:5],upper_rot_i[0:5],lower_rot_r[0:5],lower_rot_i[0:5];
(* keep = "true" *) wire signed[34:0]upper_codeword_r[0:5],upper_codeword_i[0:5],lower_codeword_r[0:5],lower_codeword_i[0:5];
genvar g;
generate for(g=0;g<6;g=g+1)begin:operators
 wire signed[34:0]sumr=ar[g]+br[g],sumi=ai[g]+bi[g];
 wire signed[34:0]diffr=ar[g]-br[g],diffi=ai[g]-bi[g];
 assign upper_pre_r[g]=sumr>>>1;assign upper_pre_i[g]=sumi>>>1;
 assign lower_pre_r[g]=diffr>>>1;assign lower_pre_i[g]=diffi>>>1;
 if(SUBFFT_SINGLE_ROTATION!=0)begin:subfft_unrotated_upper
  assign upper_rot_r[g]=upper_pre_r[g];assign upper_rot_i[g]=upper_pre_i[g];
 end else if(TRIVIAL_UPPER!=0)begin:trivial_upper
  fft_complex_rotate_trivial_1024 upper_rotation(upper_pre_r[g],upper_pre_i[g],upper_exponent,upper_rot_r[g],upper_rot_i[g]);
 end else begin:generic_upper
  fft_complex_mul_q28 upper_rotation(upper_pre_r[g],upper_pre_i[g],upper_exponent,upper_rot_r[g],upper_rot_i[g]);
 end
 if(BYPASS_LOWER!=0)begin:bypass_lower
  assign lower_rot_r[g]=lower_pre_r[g];assign lower_rot_i[g]=lower_pre_i[g];
 end else begin:generic_lower
  fft_complex_mul_q28 lower_rotation(lower_pre_r[g],lower_pre_i[g],lower_exponent,lower_rot_r[g],lower_rot_i[g]);
 end
 wire signed[34:0]up_inj_r=(inject_enable&&(inject_symbol==g)&&(inject_component==0))?(upper_rot_r[g]^(35'sd1<<inject_bit)):upper_rot_r[g];
 wire signed[34:0]up_inj_i=(inject_enable&&(inject_symbol==g)&&(inject_component==1))?(upper_rot_i[g]^(35'sd1<<inject_bit)):upper_rot_i[g];
 wire signed[34:0]lo_inj_r=(inject_enable&&(inject_symbol==g)&&(inject_component==0))?(lower_rot_r[g]^(35'sd1<<inject_bit)):lower_rot_r[g];
 wire signed[34:0]lo_inj_i=(inject_enable&&(inject_symbol==g)&&(inject_component==1))?(lower_rot_i[g]^(35'sd1<<inject_bit)):lower_rot_i[g];
 assign upper_codeword_r[g]=up_inj_r;assign upper_codeword_i[g]=up_inj_i;
 assign lower_codeword_r[g]=lo_inj_r;assign lower_codeword_i[g]=lo_inj_i;
end endgenerate

arithmetic_boundary_uncomp_v5 #(.THRESHOLD(THRESHOLD)) upper_boundary(
 upper_codeword_r[0],upper_codeword_i[0],upper_codeword_r[1],upper_codeword_i[1],upper_codeword_r[2],upper_codeword_i[2],upper_codeword_r[3],upper_codeword_i[3],upper_codeword_r[4],upper_codeword_i[4],upper_codeword_r[5],upper_codeword_i[5],
 u0r,u0i,u1r,u1i,u2r,u2i,u3r,u3i,
 up_detected,up_corrected,up_uncorrectable,up_error_location
);
arithmetic_boundary_uncomp_v5 #(.THRESHOLD(THRESHOLD)) lower_boundary(
 lower_codeword_r[0],lower_codeword_i[0],lower_codeword_r[1],lower_codeword_i[1],lower_codeword_r[2],lower_codeword_i[2],lower_codeword_r[3],lower_codeword_i[3],lower_codeword_r[4],lower_codeword_i[4],lower_codeword_r[5],lower_codeword_i[5],
 l0r,l0i,l1r,l1i,l2r,l2i,l3r,l3i,
 lo_detected,lo_corrected,lo_uncorrectable,lo_error_location
);
endmodule
