`timescale 1ns/1ps

module fft_complex_mul_q28(
    input  wire signed [34:0] in_re,
    input  wire signed [34:0] in_im,
    input  wire        [9:0] exponent,
    output wire signed [34:0] out_re,
    output wire signed [34:0] out_im
);
wire signed [29:0] coeff_re, coeff_im;
wire signed [64:0] product_rr = in_re * coeff_re;
wire signed [64:0] product_ii = in_im * coeff_im;
wire signed [64:0] product_ri = in_re * coeff_im;
wire signed [64:0] product_ir = in_im * coeff_re;
wire signed [65:0] wide_re = $signed(product_rr) - $signed(product_ii);
wire signed [65:0] wide_im = $signed(product_ri) + $signed(product_ir);
wire signed [65:0] shifted_re = wide_re >>> 28;
wire signed [65:0] shifted_im = wide_im >>> 28;
twiddle_rom_1024 u_rom(.exponent(exponent), .coeff_re(coeff_re), .coeff_im(coeff_im));
assign out_re = shifted_re[34:0];
assign out_im = shifted_im[34:0];
endmodule


// Exact rotations for the four trivial 1024-point twiddles.  The caller must
// prove that exponent is one of 0, 256, 512 or 768.  These cases use only
// wiring, real/imaginary exchange and two's-complement sign changes.
module fft_complex_rotate_trivial_1024(
    input  wire signed [34:0] in_re,
    input  wire signed [34:0] in_im,
    input  wire        [9:0] exponent,
    output reg  signed [34:0] out_re,
    output reg  signed [34:0] out_im
);
always @* begin
    case (exponent)
        10'd0: begin
            out_re = in_re;
            out_im = in_im;
        end
        10'd256: begin
            out_re = in_im;
            out_im = -in_re;
        end
        10'd512: begin
            out_re = -in_re;
            out_im = -in_im;
        end
        10'd768: begin
            out_re = -in_im;
            out_im = in_re;
        end
        default: begin
            out_re = in_re;
            out_im = in_im;
        end
    endcase
end
endmodule


module pfft_phi_calc #(
    parameter integer STAGE = 1
)(
    input wire [9:0] index,
    output reg [9:0] exponent
);
integer high_bit;
integer low_bit;
always @* begin
    exponent = 10'd0;
    for (high_bit = 1; high_bit < 10; high_bit = high_bit + 1) begin
        for (low_bit = 0; low_bit < high_bit; low_bit = low_bit + 1) begin
            if ((STAGE == (10 - low_bit - 1)) && index[high_bit] && index[low_bit])
                exponent = exponent + (10'd1 << (9 - high_bit + low_bit));
        end
    end
end
endmodule


module r2sdf_lane_subfft #(
    parameter integer DEPTH = 128,
    parameter integer STAGE = 1
)(
    input  wire clk,
    input  wire rst,
    input  wire in_valid,
    input  wire signed [34:0] in_re,
    input  wire signed [34:0] in_im,
    output reg  out_valid,
    output reg  out_last,
    output reg  signed [34:0] out_re,
    output reg  signed [34:0] out_im
);
localparam integer PHASE_W = (2*DEPTH <= 2) ? 1 : $clog2(2*DEPTH);
localparam integer STRIDE = 256 / (2*DEPTH);
reg [PHASE_W-1:0] phase;
reg primed;
reg [7:0] out_count;
(* keep = "true" *) reg signed [34:0] delay_re [0:DEPTH-1];
(* keep = "true" *) reg signed [34:0] delay_im [0:DEPTH-1];
integer address;
reg candidate_valid;
reg signed [34:0] candidate_re, candidate_im;
reg signed [34:0] store_re, store_im;
wire signed [34:0] sum_re_wrap = delay_re[address] + in_re;
wire signed [34:0] sum_im_wrap = delay_im[address] + in_im;
wire signed [34:0] diff_re_wrap = delay_re[address] - in_re;
wire signed [34:0] diff_im_wrap = delay_im[address] - in_im;
wire signed [34:0] upper_re = sum_re_wrap >>> 1;
wire signed [34:0] upper_im = sum_im_wrap >>> 1;
wire signed [34:0] lower_re = diff_re_wrap >>> 1;
wire signed [34:0] lower_im = diff_im_wrap >>> 1;
wire [9:0] lower_exponent = (address * STRIDE) << 2;
wire signed [34:0] lower_tw_re, lower_tw_im;
fft_complex_mul_q28 u_lower_twiddle(
    .in_re(lower_re), .in_im(lower_im), .exponent(lower_exponent),
    .out_re(lower_tw_re), .out_im(lower_tw_im)
);

always @* begin
    if (phase < DEPTH)
        address = phase;
    else
        address = phase - DEPTH;
    candidate_valid = 1'b0;
    candidate_re = 35'sd0;
    candidate_im = 35'sd0;
    store_re = in_re;
    store_im = in_im;
    if (phase < DEPTH) begin
        if (primed) begin
            candidate_valid = 1'b1;
            candidate_re = delay_re[address];
            candidate_im = delay_im[address];
        end
    end else begin
        candidate_valid = 1'b1;
        candidate_re = upper_re;
        candidate_im = upper_im;
        store_re = lower_tw_re;
        store_im = lower_tw_im;
    end
end

always @(posedge clk) begin
    if (rst) begin
        phase <= {PHASE_W{1'b0}};
        primed <= 1'b0;
        out_count <= 8'd0;
        out_valid <= 1'b0;
        out_last <= 1'b0;
        out_re <= 35'sd0;
        out_im <= 35'sd0;
    end else begin
        out_valid <= 1'b0;
        out_last <= 1'b0;
        if (in_valid) begin
            delay_re[address] <= store_re;
            delay_im[address] <= store_im;
            if (phase == (2*DEPTH-1)) begin
                phase <= {PHASE_W{1'b0}};
                primed <= 1'b1;
            end else begin
                phase <= phase + 1'b1;
            end
            if (candidate_valid) begin
                out_valid <= 1'b1;
                out_last <= (out_count == 8'd255);
                out_count <= out_count + 1'b1;
                out_re <= candidate_re;
                out_im <= candidate_im;
            end
        end
    end
end
endmodule


module subfft_stage4_sdf #(
    parameter integer DEPTH = 128,
    parameter integer STAGE = 1
)(
    input wire clk, input wire rst, input wire in_valid, input wire in_last,
    input wire signed [34:0] in0_re, in0_im, in1_re, in1_im,
    input wire signed [34:0] in2_re, in2_im, in3_re, in3_im,
    output wire out_valid, output wire out_last,
    output wire signed [34:0] out0_re, out0_im, out1_re, out1_im,
    output wire signed [34:0] out2_re, out2_im, out3_re, out3_im
);
wire [3:0] lane_valid, lane_last;
r2sdf_lane_subfft #(.DEPTH(DEPTH),.STAGE(STAGE)) l0(clk,rst,in_valid,in0_re,in0_im,lane_valid[0],lane_last[0],out0_re,out0_im);
r2sdf_lane_subfft #(.DEPTH(DEPTH),.STAGE(STAGE)) l1(clk,rst,in_valid,in1_re,in1_im,lane_valid[1],lane_last[1],out1_re,out1_im);
r2sdf_lane_subfft #(.DEPTH(DEPTH),.STAGE(STAGE)) l2(clk,rst,in_valid,in2_re,in2_im,lane_valid[2],lane_last[2],out2_re,out2_im);
r2sdf_lane_subfft #(.DEPTH(DEPTH),.STAGE(STAGE)) l3(clk,rst,in_valid,in3_re,in3_im,lane_valid[3],lane_last[3],out3_re,out3_im);
assign out_valid = lane_valid[0];
assign out_last = lane_last[0];
wire _unused = in_last ^ lane_last[1] ^ lane_last[2] ^ lane_last[3] ^ lane_valid[1] ^ lane_valid[2] ^ lane_valid[3];
endmodule


module r2sdf_lane_pfft #(
    parameter integer DEPTH = 128,
    parameter integer STAGE = 1,
    parameter integer LANE = 0
)(
    input wire clk, input wire rst, input wire in_valid,
    input wire signed [34:0] in_re, in_im,
    output reg out_valid, output reg out_last,
    output reg signed [34:0] out_re, out_im
);
localparam integer PHASE_W = (2*DEPTH <= 2) ? 1 : $clog2(2*DEPTH);
localparam [1:0] LANE_ID = LANE;
reg [PHASE_W-1:0] phase;
reg primed;
reg [7:0] out_count;
(* keep = "true" *) reg signed [34:0] delay_re [0:DEPTH-1];
(* keep = "true" *) reg signed [34:0] delay_im [0:DEPTH-1];
integer address;
reg candidate_valid;
reg signed [34:0] candidate_pre_re, candidate_pre_im;
reg signed [34:0] store_re, store_im;
wire signed [34:0] sum_re_wrap = delay_re[address] + in_re;
wire signed [34:0] sum_im_wrap = delay_im[address] + in_im;
wire signed [34:0] diff_re_wrap = delay_re[address] - in_re;
wire signed [34:0] diff_im_wrap = delay_im[address] - in_im;
wire signed [34:0] upper_re = sum_re_wrap >>> 1;
wire signed [34:0] upper_im = sum_im_wrap >>> 1;
wire signed [34:0] lower_re = diff_re_wrap >>> 1;
wire signed [34:0] lower_im = diff_im_wrap >>> 1;
wire [9:0] physical_index = {out_count, LANE_ID};
wire [9:0] exchanged_exponent;
wire signed [34:0] rotated_re, rotated_im;
pfft_phi_calc #(.STAGE(STAGE)) u_phi(.index(physical_index), .exponent(exchanged_exponent));
fft_complex_mul_q28 u_rotation(
    .in_re(candidate_pre_re), .in_im(candidate_pre_im), .exponent(exchanged_exponent),
    .out_re(rotated_re), .out_im(rotated_im)
);
always @* begin
    if (phase < DEPTH) address = phase; else address = phase - DEPTH;
    candidate_valid = 1'b0;
    candidate_pre_re = 35'sd0;
    candidate_pre_im = 35'sd0;
    store_re = in_re;
    store_im = in_im;
    if (phase < DEPTH) begin
        if (primed) begin
            candidate_valid = 1'b1;
            candidate_pre_re = delay_re[address];
            candidate_pre_im = delay_im[address];
        end
    end else begin
        candidate_valid = 1'b1;
        candidate_pre_re = upper_re;
        candidate_pre_im = upper_im;
        store_re = lower_re;
        store_im = lower_im;
    end
end
always @(posedge clk) begin
    if (rst) begin
        phase <= {PHASE_W{1'b0}}; primed <= 1'b0; out_count <= 8'd0;
        out_valid <= 1'b0; out_last <= 1'b0; out_re <= 35'sd0; out_im <= 35'sd0;
    end else begin
        out_valid <= 1'b0; out_last <= 1'b0;
        if (in_valid) begin
            delay_re[address] <= store_re; delay_im[address] <= store_im;
            if (phase == (2*DEPTH-1)) begin phase <= {PHASE_W{1'b0}}; primed <= 1'b1; end
            else phase <= phase + 1'b1;
            if (candidate_valid) begin
                out_valid <= 1'b1; out_last <= (out_count == 8'd255); out_count <= out_count + 1'b1;
                out_re <= rotated_re; out_im <= rotated_im;
            end
        end
    end
end
endmodule


module pfft_stage4_sdf #(
    parameter integer DEPTH = 128,
    parameter integer STAGE = 1
)(
    input wire clk, input wire rst, input wire in_valid, input wire in_last,
    input wire signed [34:0] in0_re, in0_im, in1_re, in1_im,
    input wire signed [34:0] in2_re, in2_im, in3_re, in3_im,
    output wire out_valid, output wire out_last,
    output wire signed [34:0] out0_re, out0_im, out1_re, out1_im,
    output wire signed [34:0] out2_re, out2_im, out3_re, out3_im
);
wire [3:0] lane_valid, lane_last;
r2sdf_lane_pfft #(.DEPTH(DEPTH),.STAGE(STAGE),.LANE(0)) l0(clk,rst,in_valid,in0_re,in0_im,lane_valid[0],lane_last[0],out0_re,out0_im);
r2sdf_lane_pfft #(.DEPTH(DEPTH),.STAGE(STAGE),.LANE(1)) l1(clk,rst,in_valid,in1_re,in1_im,lane_valid[1],lane_last[1],out1_re,out1_im);
r2sdf_lane_pfft #(.DEPTH(DEPTH),.STAGE(STAGE),.LANE(2)) l2(clk,rst,in_valid,in2_re,in2_im,lane_valid[2],lane_last[2],out2_re,out2_im);
r2sdf_lane_pfft #(.DEPTH(DEPTH),.STAGE(STAGE),.LANE(3)) l3(clk,rst,in_valid,in3_re,in3_im,lane_valid[3],lane_last[3],out3_re,out3_im);
assign out_valid = lane_valid[0]; assign out_last = lane_last[0];
wire _unused = in_last ^ lane_last[1] ^ lane_last[2] ^ lane_last[3] ^ lane_valid[1] ^ lane_valid[2] ^ lane_valid[3];
endmodule


module subfft_stage9(
    input wire clk, input wire rst, input wire in_valid, input wire in_last,
    input wire signed [34:0] in0_re, in0_im, in1_re, in1_im,
    input wire signed [34:0] in2_re, in2_im, in3_re, in3_im,
    output reg out_valid, output reg out_last,
    output reg signed [34:0] out0_re, out0_im, out1_re, out1_im,
    output reg signed [34:0] out2_re, out2_im, out3_re, out3_im
);
reg [7:0] beat_count;
function automatic [7:0] bit_reverse8(input [7:0] value);
integer i; begin for(i=0;i<8;i=i+1) bit_reverse8[i]=value[7-i]; end
endfunction
wire [7:0] k = bit_reverse8(beat_count);
wire signed [34:0] c0_re, c0_im, c1_re, c1_im, c2_re, c2_im, c3_re, c3_im;
assign c0_re=in0_re;
assign c0_im=in0_im;
fft_complex_mul_q28 m1(in1_re,in1_im,{2'b00,k},c1_re,c1_im);
fft_complex_mul_q28 m2(in2_re,in2_im,({2'b00,k} << 1),c2_re,c2_im);
fft_complex_mul_q28 m3(in3_re,in3_im,({2'b00,k} + ({2'b00,k} << 1)),c3_re,c3_im);
wire signed [34:0] s02r = c0_re + c2_re, s02i = c0_im + c2_im;
wire signed [34:0] d02r = c0_re - c2_re, d02i = c0_im - c2_im;
wire signed [34:0] s13r = c1_re + c3_re, s13i = c1_im + c3_im;
wire signed [34:0] d13r = c1_re - c3_re, d13i = c1_im - c3_im;
reg v1,l1; reg signed [34:0] a0r,a0i,a1r,a1i,a2r,a2i,a3r,a3i;
always @(posedge clk) begin
    if(rst) begin beat_count<=0; v1<=0; l1<=0; out_valid<=0; out_last<=0; end
    else begin
        v1<=in_valid; l1<=in_last; out_valid<=v1; out_last<=l1;
        if(in_valid) begin
            beat_count<=beat_count+1'b1;
            a0r<=s02r>>>1; a0i<=s02i>>>1; a2r<=d02r>>>1; a2i<=d02i>>>1;
            a1r<=s13r>>>1; a1i<=s13i>>>1; a3r<=d13i>>>1; a3i<=-(d13r>>>1);
        end
        if(v1) begin out0_re<=a0r;out0_im<=a0i;out1_re<=a1r;out1_im<=a1i;out2_re<=a2r;out2_im<=a2i;out3_re<=a3r;out3_im<=a3i; end
    end
end
endmodule


module subfft_stage10(
    input wire clk, input wire rst, input wire in_valid, input wire in_last,
    input wire signed [34:0] in0_re, in0_im, in1_re, in1_im,
    input wire signed [34:0] in2_re, in2_im, in3_re, in3_im,
    output reg out_valid, output reg out_last,
    output reg signed [34:0] out0_re, out0_im, out1_re, out1_im,
    output reg signed [34:0] out2_re, out2_im, out3_re, out3_im
);
wire signed [34:0] s01r=in0_re+in1_re,s01i=in0_im+in1_im,d01r=in0_re-in1_re,d01i=in0_im-in1_im;
wire signed [34:0] s23r=in2_re+in3_re,s23i=in2_im+in3_im,d23r=in2_re-in3_re,d23i=in2_im-in3_im;
reg v1,l1; reg signed [34:0] q0r,q0i,q1r,q1i,q2r,q2i,q3r,q3i;
always @(posedge clk) begin
    if(rst) begin v1<=0;l1<=0;out_valid<=0;out_last<=0;end
    else begin
        v1<=in_valid;l1<=in_last;out_valid<=v1;out_last<=l1;
        if(in_valid) begin q0r<=s01r>>>1;q0i<=s01i>>>1;q2r<=d01r>>>1;q2i<=d01i>>>1;q1r<=s23r>>>1;q1i<=s23i>>>1;q3r<=d23r>>>1;q3i<=d23i>>>1;end
        if(v1) begin out0_re<=q0r;out0_im<=q0i;out1_re<=q1r;out1_im<=q1i;out2_re<=q2r;out2_im<=q2i;out3_re<=q3r;out3_im<=q3i;end
    end
end
endmodule


module pfft_stage9(
    input wire clk, input wire rst, input wire in_valid, input wire in_last,
    input wire signed [34:0] in0_re, in0_im, in1_re, in1_im,
    input wire signed [34:0] in2_re, in2_im, in3_re, in3_im,
    output reg out_valid, output reg out_last,
    output reg signed [34:0] out0_re, out0_im, out1_re, out1_im,
    output reg signed [34:0] out2_re, out2_im, out3_re, out3_im
);
reg [7:0] beat_count;
wire signed [34:0] s02r=in0_re+in2_re,s02i=in0_im+in2_im,d02r=in0_re-in2_re,d02i=in0_im-in2_im;
wire signed [34:0] s13r=in1_re+in3_re,s13i=in1_im+in3_im,d13r=in1_re-in3_re,d13i=in1_im-in3_im;
wire signed [34:0] b0r=s02r>>>1,b0i=s02i>>>1,b1r=s13r>>>1,b1i=s13i>>>1,b2r=d02r>>>1,b2i=d02i>>>1,b3r=d13r>>>1,b3i=d13i>>>1;
wire [9:0] e0,e1,e2,e3;
pfft_phi_calc #(.STAGE(9)) p0({beat_count,2'd0},e0); pfft_phi_calc #(.STAGE(9)) p1({beat_count,2'd1},e1);
pfft_phi_calc #(.STAGE(9)) p2({beat_count,2'd2},e2); pfft_phi_calc #(.STAGE(9)) p3({beat_count,2'd3},e3);
wire signed [34:0] r0r,r0i,r1r,r1i,r2r,r2i,r3r,r3i;
fft_complex_mul_q28 m0(b0r,b0i,e0,r0r,r0i); fft_complex_mul_q28 m1(b1r,b1i,e1,r1r,r1i);
fft_complex_mul_q28 m2(b2r,b2i,e2,r2r,r2i); fft_complex_mul_q28 m3(b3r,b3i,e3,r3r,r3i);
reg v1,l1; reg signed [34:0] x0r,x0i,x1r,x1i,x2r,x2i,x3r,x3i;
always @(posedge clk) begin
 if(rst) begin beat_count<=0;v1<=0;l1<=0;out_valid<=0;out_last<=0;end else begin
  v1<=in_valid;l1<=in_last;out_valid<=v1;out_last<=l1;
  if(in_valid) begin beat_count<=beat_count+1'b1;x0r<=r0r;x0i<=r0i;x1r<=r1r;x1i<=r1i;x2r<=r2r;x2i<=r2i;x3r<=r3r;x3i<=r3i;end
  if(v1) begin out0_re<=x0r;out0_im<=x0i;out1_re<=x1r;out1_im<=x1i;out2_re<=x2r;out2_im<=x2i;out3_re<=x3r;out3_im<=x3i;end
 end
end
endmodule


module pfft_stage10(
    input wire clk, input wire rst, input wire in_valid, input wire in_last,
    input wire signed [34:0] in0_re, in0_im, in1_re, in1_im,
    input wire signed [34:0] in2_re, in2_im, in3_re, in3_im,
    output reg out_valid, output reg out_last,
    output reg signed [34:0] out0_re, out0_im, out1_re, out1_im,
    output reg signed [34:0] out2_re, out2_im, out3_re, out3_im
);
wire signed [34:0] s01r=in0_re+in1_re,s01i=in0_im+in1_im,d01r=in0_re-in1_re,d01i=in0_im-in1_im;
wire signed [34:0] s23r=in2_re+in3_re,s23i=in2_im+in3_im,d23r=in2_re-in3_re,d23i=in2_im-in3_im;
reg v1,l1; reg signed [34:0] q0r,q0i,q1r,q1i,q2r,q2i,q3r,q3i;
always @(posedge clk) begin
 if(rst) begin v1<=0;l1<=0;out_valid<=0;out_last<=0;end else begin
  v1<=in_valid;l1<=in_last;out_valid<=v1;out_last<=l1;
  if(in_valid) begin q0r<=s01r>>>1;q0i<=s01i>>>1;q1r<=d01r>>>1;q1i<=d01i>>>1;q2r<=s23r>>>1;q2i<=s23i>>>1;q3r<=d23r>>>1;q3i<=d23i>>>1;end
  if(v1) begin out0_re<=q0r;out0_im<=q0i;out1_re<=q1r;out1_im<=q1i;out2_re<=q2r;out2_im<=q2i;out3_re<=q3r;out3_im<=q3i;end
 end
end
endmodule


module pfft_frame_pair_delay(
    input wire clk, input wire rst, input wire in_valid, input wire in_last,
    input wire signed [34:0] in0_re,in0_im,in1_re,in1_im,in2_re,in2_im,in3_re,in3_im,
    output reg out_valid, output reg out_last,
    output reg signed [34:0] out0_re,out0_im,out1_re,out1_im,out2_re,out2_im,out3_re,out3_im
);
(* keep = "true" *) reg signed [34:0] bank_re [0:2047];
(* keep = "true" *) reg signed [34:0] bank_im [0:2047];
reg wr_bank; reg have_frame; reg [7:0] wr_addr;
integer wbase; integer rbase;
always @* begin
 wbase=(wr_bank?1024:0)+(wr_addr*4); rbase=(wr_bank?0:1024)+(wr_addr*4);
 out_valid=in_valid&&have_frame;out_last=out_valid&&(wr_addr==8'd255);
 out0_re=bank_re[rbase];out0_im=bank_im[rbase];out1_re=bank_re[rbase+1];out1_im=bank_im[rbase+1];
 out2_re=bank_re[rbase+2];out2_im=bank_im[rbase+2];out3_re=bank_re[rbase+3];out3_im=bank_im[rbase+3];
end
always @(posedge clk) begin
 if(rst) begin wr_bank<=0;have_frame<=0;wr_addr<=0;end else begin
  if(in_valid) begin
   bank_re[wbase]<=in0_re;bank_im[wbase]<=in0_im;bank_re[wbase+1]<=in1_re;bank_im[wbase+1]<=in1_im;
   bank_re[wbase+2]<=in2_re;bank_im[wbase+2]<=in2_im;bank_re[wbase+3]<=in3_re;bank_im[wbase+3]<=in3_im;
   if(wr_addr==8'd255) begin wr_addr<=0;wr_bank<=~wr_bank;have_frame<=1;end else wr_addr<=wr_addr+1'b1;
  end
 end
end
wire _unused = in_last;
endmodule
