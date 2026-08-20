`timescale 1ns/1ps

module vote35(input wire [34:0] a,b,c,output wire [34:0] y);
assign y=(a&b)|(a&c)|(b&c);
endmodule

module secded_encode70(input wire [69:0] data,output reg [77:0] codeword);
integer position,payload_index,parity_position;
reg parity,overall;
always @* begin
 codeword=78'd0;payload_index=0;
 for(position=1;position<=77;position=position+1) begin
  if((position&(position-1))!=0) begin codeword[position-1]=data[payload_index];payload_index=payload_index+1;end
 end
 for(parity_position=1;parity_position<=64;parity_position=parity_position<<1) begin
  parity=0;
  for(position=1;position<=77;position=position+1) if((position&parity_position)!=0) parity=parity^codeword[position-1];
  codeword[parity_position-1]=parity;
 end
 overall=0;for(position=0;position<77;position=position+1) overall=overall^codeword[position];codeword[77]=overall;
end
endmodule

module secded_decode70(input wire [77:0] codeword,output reg [69:0] data,output reg detected,output reg corrected);
integer position,payload_index,parity_position;
reg [6:0] syndrome;reg overall,parity;reg [77:0] fixed;
always @* begin
 syndrome=0;
 for(parity_position=1;parity_position<=64;parity_position=parity_position<<1) begin
  parity=0;for(position=1;position<=77;position=position+1) if((position&parity_position)!=0) parity=parity^codeword[position-1];
  if(parity) syndrome=syndrome|parity_position;
 end
 overall=0;for(position=0;position<78;position=position+1) overall=overall^codeword[position];
 fixed=codeword;detected=0;corrected=0;
 if((syndrome!=0)&&overall) begin fixed[syndrome-1]=~fixed[syndrome-1];detected=1;corrected=1;end
 else if((syndrome==0)&&overall) begin fixed[77]=~fixed[77];detected=1;corrected=1;end
 else if((syndrome!=0)&&!overall) detected=1;
 data=0;payload_index=0;
 for(position=1;position<=77;position=position+1) if((position&(position-1))!=0) begin data[payload_index]=fixed[position-1];payload_index=payload_index+1;end
end
endmodule

(* keep_hierarchy = "yes" *) module arithmetic_corrector_643(
 input wire signed[34:0]s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i,s4r,s4i,s5r,s5i,
 input wire signed[38:0]res0r,res0i,res1r,res1i,
 output reg signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i
);
reg signed[38:0]raw0r,raw0i,raw1r,raw1i,sy0r,sy0i,sy1r,sy1i,er,ei;reg[2:0]loc;reg found;
always @* begin
 raw0r=$signed(s4r)-($signed(s0r)+$signed(s1r)+$signed(s2r)+$signed(s3r));
 raw0i=$signed(s4i)-($signed(s0i)+$signed(s1i)+$signed(s2i)+$signed(s3i));
 raw1r=$signed(s5r)-($signed(s0r)-$signed(s1i)-$signed(s2r)+$signed(s3i));
 raw1i=$signed(s5i)-($signed(s0i)+$signed(s1r)-$signed(s2i)-$signed(s3r));
 sy0r=raw0r-res0r;sy0i=raw0i-res0i;sy1r=raw1r-res1r;sy1i=raw1i-res1i;
 d0r=s0r;d0i=s0i;d1r=s1r;d1i=s1i;d2r=s2r;d2i=s2i;d3r=s3r;d3i=s3i;loc=0;found=0;er=0;ei=0;
 if((sy0r!=0)||(sy0i!=0)||(sy1r!=0)||(sy1i!=0)) begin
  if((sy1r==sy0r)&&(sy1i==sy0i))begin loc=0;found=1;end
  else if((sy1r==-sy0i)&&(sy1i==sy0r))begin loc=1;found=1;end
  else if((sy1r==-sy0r)&&(sy1i==-sy0i))begin loc=2;found=1;end
  else if((sy1r==sy0i)&&(sy1i==-sy0r))begin loc=3;found=1;end
  else if((sy1r==0)&&(sy1i==0))begin loc=4;found=1;end
  else if((sy0r==0)&&(sy0i==0))begin loc=5;found=1;end
  if(found) begin
   if(loc<4)begin er=-sy0r;ei=-sy0i;end else if(loc==4)begin er=sy0r;ei=sy0i;end else begin er=sy1r;ei=sy1i;end
   case(loc)
    0:begin d0r=s0r-er[34:0];d0i=s0i-ei[34:0];end
    1:begin d1r=s1r-er[34:0];d1i=s1i-ei[34:0];end
    2:begin d2r=s2r-er[34:0];d2i=s2i-ei[34:0];end
    3:begin d3r=s3r-er[34:0];d3i=s3i-ei[34:0];end
   endcase
  end
 end
end
endmodule

// ============================================================================
// SC-01: Gao-threshold version of arithmetic_corrector_643 (added 2026-08-10)
// Detection: a syndrome component is treated as zero iff |value| <= THRESHOLD.
// Pattern matching: threshold-tolerant comparison instead of exact equality.
// If multiple locations match, the one with the smallest post-correction
// residual (L1 norm over the four syndrome components) is selected.
// THRESHOLD=0 reduces to the exact original behaviour.
// ============================================================================
(* keep_hierarchy = "yes" *) module arithmetic_corrector_643_thresholded #(
    parameter integer THRESHOLD = 0
)(
 input wire signed[34:0]s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i,s4r,s4i,s5r,s5i,
 input wire signed[38:0]res0r,res0i,res1r,res1i,
 output reg signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 output reg detected,           // 0 = no error beyond threshold, 1 = error detected
 output reg corrected,          // 0 = not corrected, 1 = corrected
 output reg uncorrectable,      // 1 = detected but no valid correction
 output reg miscorrected,       // 1 = corrected output differs from golden (decided externally by TB)
 output reg [2:0] error_location // corrected symbol location (0..5)
);
function [38:0] abs39;
 input signed [38:0] value;
 begin
  abs39 = value[38] ? (~value + 39'sd1) : value;
 end
endfunction
reg signed[38:0]raw0r,raw0i,raw1r,raw1i,sy0r,sy0i,sy1r,sy1i,er,ei;
reg[2:0]loc;
reg found;
reg[38:0]th;
reg[41:0]norm,best_norm;
always @* begin
 raw0r=$signed(s4r)-($signed(s0r)+$signed(s1r)+$signed(s2r)+$signed(s3r));
 raw0i=$signed(s4i)-($signed(s0i)+$signed(s1i)+$signed(s2i)+$signed(s3i));
 raw1r=$signed(s5r)-($signed(s0r)-$signed(s1i)-$signed(s2r)+$signed(s3i));
 raw1i=$signed(s5i)-($signed(s0i)+$signed(s1r)-$signed(s2i)-$signed(s3r));
 sy0r=raw0r-res0r;sy0i=raw0i-res0i;sy1r=raw1r-res1r;sy1i=raw1i-res1i;
 d0r=s0r;d0i=s0i;d1r=s1r;d1i=s1i;d2r=s2r;d2i=s2i;d3r=s3r;d3i=s3i;
 detected=0;corrected=0;uncorrectable=0;miscorrected=0;error_location=0;loc=0;er=0;ei=0;
 th = THRESHOLD;   // zero-extended into the 39-bit comparison domain
 if((abs39(sy0r)>th)||(abs39(sy0i)>th)||(abs39(sy1r)>th)||(abs39(sy1i)>th)) begin
  detected=1;
  found=0;best_norm=42'h3FFFFFFFFF;
  // location 0 (functional 0): sy1 ~= sy0
  if((abs39(sy1r-sy0r)<=th)&&(abs39(sy1i-sy0i)<=th)) begin
   norm=abs39(sy1r-sy0r)+abs39(sy1i-sy0i);
   if(norm<best_norm)begin best_norm=norm;loc=0;found=1;end
  end
  // location 1 (functional 1): sy1 ~= rotate_j(sy0)  => sy1r ~= -sy0i, sy1i ~= sy0r
  if((abs39(sy1r+sy0i)<=th)&&(abs39(sy1i-sy0r)<=th)) begin
   norm=abs39(sy1r+sy0i)+abs39(sy1i-sy0r);
   if(norm<best_norm)begin best_norm=norm;loc=1;found=1;end
  end
  // location 2 (functional 2): sy1 ~= -sy0
  if((abs39(sy1r+sy0r)<=th)&&(abs39(sy1i+sy0i)<=th)) begin
   norm=abs39(sy1r+sy0r)+abs39(sy1i+sy0i);
   if(norm<best_norm)begin best_norm=norm;loc=2;found=1;end
  end
  // location 3 (functional 3): sy1 ~= -rotate_j(sy0) => sy1r ~= sy0i, sy1i ~= -sy0r
  if((abs39(sy1r-sy0i)<=th)&&(abs39(sy1i+sy0r)<=th)) begin
   norm=abs39(sy1r-sy0i)+abs39(sy1i+sy0r);
   if(norm<best_norm)begin best_norm=norm;loc=3;found=1;end
  end
  // location 4 (check0): sy1 ~= 0
  if((abs39(sy1r)<=th)&&(abs39(sy1i)<=th)) begin
   norm=abs39(sy1r)+abs39(sy1i);
   if(norm<best_norm)begin best_norm=norm;loc=4;found=1;end
  end
  // location 5 (check1): sy0 ~= 0
  if((abs39(sy0r)<=th)&&(abs39(sy0i)<=th)) begin
   norm=abs39(sy0r)+abs39(sy0i);
   if(norm<best_norm)begin best_norm=norm;loc=5;found=1;end
  end
  if(found) begin
   corrected=1;error_location=loc;
   if(loc<4)begin er=-sy0r;ei=-sy0i;end
   case(loc)
    0:begin d0r=s0r-er[34:0];d0i=s0i-ei[34:0];end
    1:begin d1r=s1r-er[34:0];d1i=s1i-ei[34:0];end
    2:begin d2r=s2r-er[34:0];d2i=s2i-ei[34:0];end
    3:begin d3r=s3r-er[34:0];d3i=s3i-ei[34:0];end
    default: ; // locations 4/5 are check symbols: functional outputs pass through
   endcase
  end else begin
   uncorrectable=1;
  end
 end
end
endmodule

// ============================================================================
// SC-01 方案B: un-compensated Gao-threshold corrector (added 2026-08-10).
// NO residual/clean reference inputs (author constraint: residual compensation
// is physically unrealizable in hardware). syndrome = raw syndrome computed
// directly from the codeword; detection |syndrome component| > THRESHOLD.
// Pattern-match tolerance TOL = 2*THRESHOLD for functional locations; check
// locations use |syndrome| <= THRESHOLD. Multiple matching locations: pick
// the smallest post-correction residual; exact tie between different
// locations -> uncorrectable (no blind correction).
// NOTE: corrected output = clean + rho (inherent residual pollution), this is
// the mathematical essence of plan B, not a bug.
// ============================================================================
(* keep_hierarchy = "yes" *) module arithmetic_corrector_643_uncomp #(
    parameter integer THRESHOLD = 8
)(
 input wire signed[34:0]s0r,s0i,s1r,s1i,s2r,s2i,s3r,s3i,s4r,s4i,s5r,s5i,
 output reg signed[34:0]d0r,d0i,d1r,d1i,d2r,d2i,d3r,d3i,
 output reg detected,
 output reg corrected,
 output reg uncorrectable,
 output reg [2:0] error_location
);
function [38:0] abs39;
 input signed [38:0] value;
 begin
  abs39 = value[38] ? (~value + 39'sd1) : value;
 end
endfunction
reg signed[38:0]sy0r,sy0i,sy1r,sy1i,er,ei;
reg[2:0]loc;
reg found,ambiguous;
reg[38:0]th,tol;
reg[41:0]norm,best_norm;
always @* begin
 sy0r=$signed(s4r)-($signed(s0r)+$signed(s1r)+$signed(s2r)+$signed(s3r));
 sy0i=$signed(s4i)-($signed(s0i)+$signed(s1i)+$signed(s2i)+$signed(s3i));
 sy1r=$signed(s5r)-($signed(s0r)-$signed(s1i)-$signed(s2r)+$signed(s3i));
 sy1i=$signed(s5i)-($signed(s0i)+$signed(s1r)-$signed(s2i)-$signed(s3r));
 d0r=s0r;d0i=s0i;d1r=s1r;d1i=s1i;d2r=s2r;d2i=s2i;d3r=s3r;d3i=s3i;
 detected=0;corrected=0;uncorrectable=0;error_location=0;loc=0;er=0;ei=0;
 th = THRESHOLD;
 tol = THRESHOLD + THRESHOLD;
 if((abs39(sy0r)>th)||(abs39(sy0i)>th)||(abs39(sy1r)>th)||(abs39(sy1i)>th)) begin
  detected=1;
  found=0;ambiguous=0;best_norm=42'h3FFFFFFFFF;
  // location 0: sy1 ~= sy0
  if((abs39(sy1r-sy0r)<=tol)&&(abs39(sy1i-sy0i)<=tol)) begin
   norm=abs39(sy1r-sy0r)+abs39(sy1i-sy0i);
   if(norm<best_norm)begin best_norm=norm;loc=0;found=1;ambiguous=0;end
   else if((norm==best_norm)&&found&&(loc!=0)) ambiguous=1;
  end
  // location 1: sy1 ~= rotate_j(sy0)
  if((abs39(sy1r+sy0i)<=tol)&&(abs39(sy1i-sy0r)<=tol)) begin
   norm=abs39(sy1r+sy0i)+abs39(sy1i-sy0r);
   if(norm<best_norm)begin best_norm=norm;loc=1;found=1;ambiguous=0;end
   else if((norm==best_norm)&&found&&(loc!=1)) ambiguous=1;
  end
  // location 2: sy1 ~= -sy0
  if((abs39(sy1r+sy0r)<=tol)&&(abs39(sy1i+sy0i)<=tol)) begin
   norm=abs39(sy1r+sy0r)+abs39(sy1i+sy0i);
   if(norm<best_norm)begin best_norm=norm;loc=2;found=1;ambiguous=0;end
   else if((norm==best_norm)&&found&&(loc!=2)) ambiguous=1;
  end
  // location 3: sy1 ~= -rotate_j(sy0)
  if((abs39(sy1r-sy0i)<=tol)&&(abs39(sy1i+sy0r)<=tol)) begin
   norm=abs39(sy1r-sy0i)+abs39(sy1i+sy0r);
   if(norm<best_norm)begin best_norm=norm;loc=3;found=1;ambiguous=0;end
   else if((norm==best_norm)&&found&&(loc!=3)) ambiguous=1;
  end
  // location 4 (check0): sy1 ~= 0 (residual only)
  if((abs39(sy1r)<=th)&&(abs39(sy1i)<=th)) begin
   norm=abs39(sy1r)+abs39(sy1i);
   if(norm<best_norm)begin best_norm=norm;loc=4;found=1;ambiguous=0;end
   else if((norm==best_norm)&&found&&(loc!=4)) ambiguous=1;
  end
  // location 5 (check1): sy0 ~= 0 (residual only)
  if((abs39(sy0r)<=th)&&(abs39(sy0i)<=th)) begin
   norm=abs39(sy0r)+abs39(sy0i);
   if(norm<best_norm)begin best_norm=norm;loc=5;found=1;ambiguous=0;end
   else if((norm==best_norm)&&found&&(loc!=5)) ambiguous=1;
  end
  if(found&&(!ambiguous)) begin
   corrected=1;error_location=loc;
   if(loc<4)begin er=-sy0r;ei=-sy0i;end
   case(loc)
    0:begin d0r=s0r-er[34:0];d0i=s0i-ei[34:0];end
    1:begin d1r=s1r-er[34:0];d1i=s1i-ei[34:0];end
    2:begin d2r=s2r-er[34:0];d2i=s2i-ei[34:0];end
    3:begin d3r=s3r-er[34:0];d3i=s3i-ei[34:0];end
    default: ; // locations 4/5 are check symbols: functional outputs pass through
   endcase
  end else begin
   uncorrectable=1;
  end
 end
end
endmodule
